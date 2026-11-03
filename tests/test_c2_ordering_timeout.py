"""Optional ordering cannot borrow a new deadline or bypass publication checks."""
from types import SimpleNamespace
import threading

import pytest
import httpx

from test_c2_acceptance import fixture, run
from services import ai_service, project_access as access, project_relationship_capability as adapter
from services.project_analysis_request import AnalysisBudget, AnalysisRequest
from services.project_analysis_index import analyze_project_relationships
from services.project_graph import build_relationship_graph, traverse_relationships
from services.project_relationship_answer import answer_relationships
from models.project_relationships import RelationshipKind
from services.cancellation import OperationCancelled
from commands import router


def prepared():
    now = [0.0]
    event = threading.Event()
    request = AnalysisRequest(access.get_project(), AnalysisBudget(cancellation_event=event, clock=lambda: now[0]))
    analysis = analyze_project_relationships(request)
    graph = build_relationship_graph(analysis, request, RelationshipKind.CALLS)
    trace = traverse_relationships(graph, request, qualified_name="route")
    return now, event, request, analysis, trace


@pytest.mark.parametrize("mode", ["slow", "timeout", "invalid", "insufficient", "unsupported"])
def test_optional_failure_preserves_deterministic_answer(fixture, monkeypatch, mode):
    now, _, request, analysis, trace = prepared()
    calls = []
    def provider(**kwargs):
        calls.append(kwargs)
        now[0] += kwargs["timeout_seconds"]
        if mode in {"slow", "timeout"}:
            raise httpx.ReadTimeout("optional transport timed out")
        return {"message": {"content": '{"order":["invented"]}'}}
    monkeypatch.setattr(ai_service, "bounded_relationship_chat", None if mode == "unsupported" else provider)
    if mode == "insufficient":
        now[0] = 4.0
    answer = answer_relationships(analysis, trace, request, use_model=True)
    assert answer.success and not answer.used_model_order
    assert "Confirmed static call" in answer.text and "invented" not in answer.text
    assert len(calls) == (0 if mode in {"insufficient", "unsupported"} else 2)
    assert all(0 < call["timeout_seconds"] <= 0.4 for call in calls)
    assert sum(call["timeout_seconds"] for call in calls) <= 1
    assert request.budget.remaining_seconds > 0


def test_retry_cannot_spend_publication_reserve(fixture, monkeypatch):
    now, _, request, analysis, trace = prepared()
    calls = []
    def provider(**kwargs):
        calls.append(kwargs)
        now[0] += 1.1
        return {"message": {"content": "invalid"}}
    monkeypatch.setattr(ai_service, "bounded_relationship_chat", provider)
    assert answer_relationships(analysis, trace, request, use_model=True).success
    assert len(calls) == 1


@pytest.mark.parametrize("failure", ["deadline", "cancelled", "stale", "revoked"])
def test_provider_return_does_not_override_failure(fixture, monkeypatch, failure):
    root, _, heard, history = fixture
    now, event, request, analysis, trace = prepared()
    def provider(**kwargs):
        if failure == "deadline":
            now[0] = 5
        elif failure == "cancelled":
            event.set()
        elif failure == "stale":
            (root / "root.py").write_text("def route():\n    pass\n")
        else:
            access.revoke_project("acceptance")
        return {"message": {"content": "invalid"}}
    monkeypatch.setattr(ai_service, "bounded_relationship_chat", provider)
    if failure == "cancelled":
        with pytest.raises(OperationCancelled):
            answer_relationships(analysis, trace, request, use_model=True)
    else:
        assert not answer_relationships(analysis, trace, request, use_model=True).success
    assert not heard and not history


def test_actual_router_timeout_fallback_and_no_late_effects(fixture, monkeypatch):
    from services import conversation_manager as conversation
    from commands.registry import COMMAND_REGISTRY
    calls = []
    def timeout(**kwargs):
        calls.append(kwargs)
        raise httpx.ReadTimeout("bounded timeout")
    monkeypatch.setattr(ai_service, "bounded_relationship_chat", timeout)
    def optional(**kwargs):
        return adapter.relationship_capability(**kwargs, use_model=True)
    monkeypatch.setitem(COMMAND_REGISTRY, "project_relationships", {"function": optional})
    assert run("What calls SaveHistory?").success and len(calls) == 2
    before = conversation.get_topic()
    event = threading.Event()
    def cancel(**kwargs):
        event.set()
        raise httpx.ReadTimeout("cancelled")
    monkeypatch.setattr(ai_service, "bounded_relationship_chat", cancel)
    _, _, heard, history = fixture
    saved, spoken = list(history), list(heard)
    with pytest.raises(OperationCancelled):
        router.execute_registered_capability("multi_file_reasoning", dict(context=access.get_project(),
            operation="trace", qualified_name="route"), cancellation_event=event)
    assert history == saved and heard == spoken and conversation.get_topic() == before


def test_transport_timeout_is_request_local(monkeypatch):
    seen = []
    class Client:
        def __init__(self, **kwargs):
            seen.append(kwargs)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            seen.append("closed")
        def chat(self, **kwargs):
            raise httpx.ReadTimeout("deadline")
    monkeypatch.setattr("ollama.Client", Client)
    with pytest.raises(httpx.ReadTimeout):
        ai_service.bounded_relationship_chat(timeout_seconds=0.2, model="fixture")
    assert seen[0]["timeout"] == 0.2 and not seen[0]["trust_env"] and not seen[0]["follow_redirects"]
    assert seen[-1] == "closed"
