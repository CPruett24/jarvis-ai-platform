"""Conservative prompt selection; never turns conversation text into memory."""

import re

MAX_MEMORY_ITEMS = 8
MAX_MEMORY_CONTEXT_CHARS = 2400

_STOP_WORDS = set("what which who how do does did have has i me my you your about remember know told using use one as an a the of on in to for explain more simply that it this worked".split())
_GROUPS = (
    {"project", "projects", "programming", "code", "application", "applications", "app", "apps", "built", "developed"},
    {"preference", "preferences", "prefer", "favorite", "favourite"},
)


def _terms(text):
    words = set(re.findall(r"[a-z0-9]+", text.lower())) - _STOP_WORDS
    for group in _GROUPS:
        if words & group:
            words |= group
    return words


def _personal_intent(text):
    return bool(re.search(
        r"\bmy\b|\b(?:have|did|do|am) i\b|\bi (?:prefer|like|worked|built|used)\b|"
        r"\b(?:remember|know) about me\b|\b(?:i told you|you remember|you recall)\b",
        text.lower(),
    ))


def select_memory_information(question, items, history=()):
    """Return original items, ranked by overlap and content, within wire budgets.

    A low-overlap follow-up may inherit intent only from the previous user
    request. Assistant text never supplies retrieval intent or search terms.
    Oversized items are skipped intact rather than truncating their meaning.
    """
    query = question
    if not _personal_intent(query):
        followup = re.match(
            r"^(?:what about\b|how does that\b|can you explain that\b|"
            r"explain that\b|tell me more\b)", question.lower().strip(),
        )
        if not followup:
            return []
        previous = [m["content"] for m in history if m["role"] == "user"]
        # The builder is called after adding the current user turn.
        if previous and previous[-1] == question:
            previous.pop()
        if not previous or not _personal_intent(previous[-1]):
            return []
        query = previous[-1] + " " + question

    terms = _terms(query)
    broad_recall = bool(re.search(
        r"(?:remember|know|recall) about me\b|what (?:do you remember|have i told you)\??$",
        query.lower().strip(),
    ))
    ranked = []
    for item in items:
        score = len(terms & _terms(item.content))
        if score or broad_recall:
            ranked.append((-score, item.content, item))
    ranked.sort(key=lambda row: (row[0], row[1]))
    selected = []
    size = 0
    for _, _, item in ranked:
        cost = len(f"[{item.source.value}] {item.content}") + bool(selected)
        if size + cost > MAX_MEMORY_CONTEXT_CHARS:
            continue
        selected.append(item)
        size += cost
        if len(selected) == MAX_MEMORY_ITEMS:
            break
    return selected
