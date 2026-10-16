from datetime import datetime, UTC
from dataclasses import dataclass
import re

from sqlalchemy import func, or_, and_

from models.memory import SessionLocal
from models.session import Session
from models.conversation import Conversation

current_session = None

MAX_RECALL_SESSIONS = 3
MAX_RECALL_MESSAGES = 60
MAX_RECALL_CANDIDATES = 400


@dataclass
class HistoricalSelection:
    records: list
    partial: bool = False
    candidate_limited: bool = False


def capture_recall_cutoff():
    """Capture an insertion watermark before the current request is saved."""
    with SessionLocal() as db:
        return db.query(func.max(Conversation.id)).scalar() or 0


def _historical_record(row):
    return {
        "id": row.id, "session_id": row.session_id,
        "timestamp": row.timestamp, "role": row.role,
        "source": row.source, "content": row.message,
        "playback_status": row.playback_status or "unknown",
    }


def _adjacent(db, row, *, following):
    physical = db.query(Conversation).filter(Conversation.session_id == row.session_id)
    comparison = Conversation.timestamp > row.timestamp if following else Conversation.timestamp < row.timestamp
    tie = Conversation.id > row.id if following else Conversation.id < row.id
    order = (Conversation.timestamp.asc(), Conversation.id.asc()) if following else (
        Conversation.timestamp.desc(), Conversation.id.desc())
    return physical.filter(or_(comparison, and_(Conversation.timestamp == row.timestamp, tie))).order_by(*order).first()


def _is_recall_or_control(row):
    # Local imports avoid an archive/classifier import cycle. This is the same
    # deterministic classifier used by live routing, including legacy requests.
    from services.historical_recall import classify_historical_recall
    from services.conversation_lifecycle import is_conversation_end
    from services.code_intent import is_conversation_summary_phrase
    return (row.source == "historical_recall" or (row.role == "user" and (
        classify_historical_recall(row.message or "") is not None
        or is_conversation_summary_phrase(row.message or "")
        or is_conversation_end(row.message or ""))))


def _meaningful(db, row):
    if _is_recall_or_control(row):
        return False
    if row.role == "assistant":
        previous = _adjacent(db, row, following=False)
        # Also exclude responses to recognizable legacy recall requests whose
        # response source was not labeled. Keep all physical rows as barriers.
        if previous is not None and _is_recall_or_control(previous):
            return False
    return row.role in {"user", "assistant"}


def get_historical_messages(*, cutoff, previous_session=False, start=None,
                            end=None, topic=None):
    """Bounded archive reads only; never restore live state or migrate a database.

    Naive date boundaries are UTC. SQL LIKE is a bound coarse filter; Python
    token boundaries reject substring matches within the bounded candidate set.
    """
    with SessionLocal() as db:
        base = db.query(Conversation).filter(
            Conversation.id <= cutoff,
            Conversation.session_id.isnot(None),
            or_(Conversation.source.is_(None),
                Conversation.source != "historical_recall"),
        )
        if start is not None:
            base = base.filter(Conversation.timestamp >= start)
        if end is not None:
            base = base.filter(Conversation.timestamp < end)
        descending = (Conversation.timestamp.desc(), Conversation.id.desc())
        partial = False
        candidate_limited = False

        if previous_session:
            if current_session is not None:
                base = base.filter(Conversation.session_id != current_session.id)

        if topic:
            terms = re.findall(r"[\w%_]+", topic.lower())
            if not terms:
                return HistoricalSelection([])
            candidates = base
            for term in terms:
                escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                candidates = candidates.filter(
                    Conversation.message.ilike(f"%{escaped}%", escape="\\")
                )
            rows = candidates.order_by(*descending).limit(MAX_RECALL_CANDIDATES + 1).all()
            candidate_limited = len(rows) > MAX_RECALL_CANDIDATES
            patterns = [re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)", re.I)
                        for term in terms]
            matches = [row for row in rows[:MAX_RECALL_CANDIDATES]
                       if all(pattern.search(row.message or "") for pattern in patterns)
                       and _meaningful(db, row)]
            if previous_session and matches:
                matches = [row for row in matches if row.session_id == matches[0].session_id]
            selected = {}
            sessions = set()
            relationships = {}
            for row in matches:
                if row.session_id not in sessions and len(sessions) == MAX_RECALL_SESSIONS:
                    partial = True
                    continue
                sessions.add(row.session_id)
                selected[row.id] = row
                if len(selected) == MAX_RECALL_MESSAGES:
                    partial = True
                    break
            direct_ids = set(selected)
            # Only immediate opposite-role neighbors establish a recorded pair.
            # Query physical neighbors first: an excluded recap is a barrier,
            # not permission to attach a later answer to an earlier question.
            for row in list(selected.values()):
                if row.role == "user":
                    adjacent = _adjacent(db, row, following=True)
                    expected_role = "assistant"
                elif row.role == "assistant":
                    adjacent = _adjacent(db, row, following=False)
                    expected_role = "user"
                else:
                    continue
                valid = (adjacent is not None and adjacent.role == expected_role
                         and _meaningful(db, adjacent)
                         and base.filter(Conversation.id == adjacent.id).first() is not None)
                if row.role == "user":
                    relationships[row.id] = adjacent.id if valid else None
                if valid:
                    if adjacent.id not in selected and len(selected) >= MAX_RECALL_MESSAGES:
                        partial = True
                        continue
                    selected[adjacent.id] = adjacent
                    if adjacent.role == "user":
                        relationships[adjacent.id] = row.id
            rows = list(selected.values())
        else:
            candidates = base.order_by(*descending).limit(MAX_RECALL_CANDIDATES + 1).all()
            candidate_limited = len(candidates) > MAX_RECALL_CANDIDATES
            meaningful = [row for row in candidates[:MAX_RECALL_CANDIDATES] if _meaningful(db, row)]
            session_ids = list(dict.fromkeys(row.session_id for row in meaningful))
            if previous_session:
                # A later session containing only unanswered fragments must not
                # hide an earlier recorded exchange. Never merge their turns.
                from services.historical_recall import _supported_definition
                supported_sessions = list(dict.fromkeys(row.session_id for row in meaningful
                    if row.role == "assistant" and row.source != "router"
                    and _supported_definition(_historical_record(row))))
                answered_sessions = list(dict.fromkeys(row.session_id for row in meaningful
                    if row.role == "assistant" and row.source != "router" and (row.message or "").strip()))
                session_ids = supported_sessions or answered_sessions or session_ids
            session_limit = 1 if previous_session else MAX_RECALL_SESSIONS
            partial = not previous_session and len(session_ids) > session_limit
            session_ids = session_ids[:session_limit]
            rows = [row for row in meaningful if row.session_id in session_ids]
            partial |= len(rows) > MAX_RECALL_MESSAGES
            rows = rows[:MAX_RECALL_MESSAGES]

        rows.sort(key=lambda row: (row.timestamp, row.id))
        records = [_historical_record(row) for row in rows]
        for row, record in zip(rows, records):
            if topic:
                record["relevance"] = "direct" if record["id"] in direct_ids else "context"
                if record["role"] == "user":
                    record["answer_id"] = relationships.get(record["id"])
            elif row.role == "user":
                adjacent = _adjacent(db, row, following=True)
                valid = (adjacent is not None and adjacent.role == "assistant"
                         and _meaningful(db, adjacent)
                         and base.filter(Conversation.id == adjacent.id).first() is not None)
                record["answer_id"] = adjacent.id if valid else None
        return HistoricalSelection(records,
                                   partial or candidate_limited, candidate_limited)


def start_session():

    global current_session

    db = SessionLocal()

    current_session = Session()

    db.add(current_session)

    db.commit()

    db.refresh(current_session)

    db.close()


def end_session():

    global current_session

    if current_session is None:
        return

    db = SessionLocal()

    session = db.get(Session, current_session.id)

    if session:

        session.ended_at = datetime.now(UTC)

        db.commit()

    db.close()

    current_session = None


def save_message(
    role,
    message,
    source=None,
):

    if current_session is None:
        return

    db = SessionLocal()

    conversation = Conversation(
        session_id=current_session.id,
        role=role,
        message=message,
        source=source,
    )

    db.add(conversation)

    db.commit()

    record_id = conversation.id
    db.close()

    return record_id


def update_playback_status(record_id, status):
    if status not in {"unknown", "completed", "interrupted", "timed_out", "failed"}:
        raise ValueError("Invalid playback status")
    with SessionLocal() as db:
        row = db.get(Conversation, record_id)
        if row is not None and row.role == "assistant":
            row.playback_status = status
            db.commit()


def get_recent_messages(limit=20):

    db = SessionLocal()

    messages = (
        db.query(Conversation)
        .order_by(Conversation.timestamp.desc())
        .limit(limit)
        .all()
    )

    db.close()

    messages.reverse()

    return [
        {
            "role": message.role,
            "content": message.message,
            "timestamp": message.timestamp,
            "session_id": message.session_id,
            "source": message.source,
        }
        for message in messages
    ]
