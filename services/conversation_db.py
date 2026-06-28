from datetime import datetime, UTC

from models.memory import SessionLocal
from models.session import Session
from models.conversation import Conversation

current_session = None


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


def save_message(role, message):

    if current_session is None:
        return

    db = SessionLocal()

    conversation = Conversation(
        session_id=current_session.id,
        role=role,
        message=message,
    )

    db.add(conversation)

    db.commit()

    db.close()


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
        }
        for message in messages
    ]