import pytest
from models.source_evidence import RetrievalLimits, RetrievalResult, RetrievalStatus, SourceExcerpt


def test_failure_carries_no_success_or_excerpts():
    result = RetrievalResult("jarvis", 1, "read", RetrievalStatus.DENIED, error="excluded")
    assert not result.success
    assert result.excerpts == []


def test_limits_and_ranges_are_validated():
    with pytest.raises(ValueError):
        RetrievalLimits(max_lines=0)
    with pytest.raises(ValueError):
        SourceExcerpt("S1", "jarvis", 1, "a.py", 1, 2, "one", "now", (), "hash")


def test_project_topic_is_invalidated_by_selection_or_revision(tmp_path):
    from services import project_access as access, conversation_manager as conversation
    projects, active, revision = access._projects.copy(), access._active, access._revision
    old_topic = conversation._current_topic
    try:
        access.register_project("fixture", tmp_path)
        access.select_project("fixture")
        conversation.set_topic({"type": "file", "filename": "a.py"})
        assert conversation.get_topic()["project_id"] == "fixture"
        access.register_project("fixture", tmp_path)
        assert conversation.get_topic() is None
    finally:
        access._projects, access._active, access._revision = projects, active, revision
        conversation._current_topic = old_topic
