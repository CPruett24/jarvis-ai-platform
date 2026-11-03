"""C3.5a internal dispatch only, with disposable authorized source and no delivery."""
import copy
from dataclasses import replace
import re
import threading

import pytest

from models.project_scope import ScopeKind, CompletenessClaim
from models.project_relationships import SourceLocation
from models.scoped_validation import ScopedValidationOutcome
from services import project_access as access
from services import scoped_relationship_answer as answers
from services.scoped_relationship_request import parse_scoped_caller_request as parse
from services.project_analysis_request import AnalysisRequest, AnalysisLimits
from services.project_analysis_cache import read_analysis_source
from services.cancellation import OperationCancelled


@pytest.fixture
def project(tmp_path):
    old = access._projects.copy(), access._active, access._revision
    access._projects = {}
    access.register_project("Jarvis", tmp_path)
    access.select_project("Jarvis")

    def write(path, text):
        file = tmp_path / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text, encoding="utf-8", newline="\n")
        return file

    write("services/speaker.py", "def speak():\n    pass\ndef Speak():\n    pass\n")
    write("commands/run.py", "from services.speaker import speak\ndef Run():\n    speak()\n")

    def request(**kwargs):
        return AnalysisRequest.capture(clock=kwargs.pop("clock", lambda: 0), **kwargs)

    yield write, request, tmp_path
    access._projects, access._active, access._revision = old


@pytest.mark.parametrize("sentence,kind,target,path,project_name", [
    ("What functions call speak in my Jarvis project?", ScopeKind.PROJECT_PYTHON, "speak", None, "Jarvis"),
    ("Which functions directly call speak?", None, "speak", None, None),
    ("Show callers of services/speaker.py::speak", None, "speak", "services/speaker.py", None),
    ("Within commands, what calls speak?", ScopeKind.DIRECTORY, "speak", None, None),
    ("In this file, which functions call speak?", ScopeKind.FILES, "speak", None, None),
    ("What functions call the Speak function in project Jarvis?", ScopeKind.PROJECT_PYTHON, "Speak", None, "Jarvis"),
    ("Please show direct callers of services/speaker.py::Speak within commands", ScopeKind.DIRECTORY, "Speak", "services/speaker.py", None),
    ("Who calls Outer.<locals>.inner in file commands/run.py?", ScopeKind.FILES, "Outer.<locals>.inner", None, None),
])
def test_natural_grammar_preserves_exact_identifiers(sentence, kind, target, path, project_name):
    intent = parse(sentence)
    assert intent.direct and not intent.error
    assert (intent.scope_kind, intent.qualified_name, intent.filename, intent.project_qualifier) == (kind, target, path, project_name)


@pytest.mark.parametrize("sentence", [
    "Trace services/speaker.py::speak reverse", "Who indirectly calls speak in my project?",
    "Show caller chains of speak within commands", "Which functions directly or indirectly call speak?",
    "Who transitively calls speak?", "Show recursive callers of speak",
])
def test_transitive_requests_are_not_downgraded(project, monkeypatch, sentence):
    _, request, _ = project
    monkeypatch.setattr(answers, "analyze_scoped_callers", lambda *a, **k: pytest.fail("direct analysis used"))
    intent = parse(sentence)
    assert intent is not None and not intent.direct
    result = answers.prepare_scoped_caller_answer(sentence, request())
    assert result.defer_to_c2 and not result.relationships


@pytest.mark.parametrize("sentence", ["What is a call graph?", "What did we discuss yesterday?",
    "What does speak call?", "What does speaker.py import?", "Explain commands/run.py"])
def test_other_requests_remain_outside_c3(project, sentence):
    _, request, _ = project
    assert parse(sentence) is None
    assert answers.prepare_scoped_caller_answer(sentence, request()).defer_to_c2


@pytest.mark.parametrize("sentence", ["In Jarvis, what is OOP?", "Explain inheritance in Python",
    "Within commands, what does Run call?", "Within commands, what does speaker.py import?"])
def test_scope_words_do_not_steal_unrelated_requests(sentence):
    assert parse(sentence) is None


@pytest.mark.parametrize("sentence", ["Which functions directly call speak?", "Show callers of services/speaker.py::speak",
    "What functions call?", "What functions call file.py::?", "In this file, who calls speak?"])
def test_clarifications_do_not_run_analysis_or_discovery(project, monkeypatch, sentence):
    _, request, _ = project
    for name in ("analyze_scoped_callers", "discover", "validate_scoped_callers"):
        monkeypatch.setattr(answers, name, lambda *a, **k: pytest.fail("clarification performed caller analysis"))
    result = answers.prepare_scoped_caller_answer(sentence, request())
    assert result.status == "clarification" and result.reasons
    assert not result.relationships and not result.references and not result.publication_enabled


@pytest.mark.parametrize("sentence", [
    "Within commands, what calls speak?", "Who calls services/speaker.py::speak in file commands/run.py?",
    "What functions call speak in my Jarvis project?", "What functions call speak in my project?",
])
def test_complete_scope_answers_have_validated_citations(project, sentence):
    _, request, _ = project
    result = answers.prepare_scoped_caller_answer(sentence, request())
    assert result.status == "complete", (result.text, result.reasons)
    assert result.validation.publication_eligible and not result.publication_enabled
    assert "Run" in result.text and "directly calls speak" in result.text
    assert "Complete direct static caller list within" in result.text
    assert "runtime execution" in result.text
    assert "[commands/run.py:" in result.text and "[services/speaker.py:" in result.text
    assert all(ref.source_id in {e.source_id for e in result.validation.evidence.excerpts} for ref in result.references)


def test_explicit_current_file_requires_matching_captured_source(project):
    _, request, _ = project
    declaration = request()
    excerpt = read_analysis_source(declaration, "commands/run.py").excerpts[0]
    location = SourceLocation.from_excerpt(declaration.identity, excerpt)
    result = answers.prepare_scoped_caller_answer("In this file, who calls speak?", request(), current_file=location)
    assert result.status == "complete", result.reasons
    assert result.scope.search_files == ("commands/run.py",)


def test_stale_current_file_context_refuses(project):
    write, request, _ = project
    captured = request()
    location = SourceLocation.from_excerpt(captured.identity, read_analysis_source(captured, "commands/run.py").excerpts[0])
    write("commands/run.py", "from services.speaker import speak\ndef NewRun():\n    speak()\n")
    result = answers.prepare_scoped_caller_answer("In this file, who calls speak?", request(), current_file=location)
    assert result.status == "refused" and "current_file_context_stale" in result.reasons


@pytest.mark.parametrize("mode", ["unknown", "inactive", "ambiguous"])
def test_project_qualifiers_never_authorize_or_switch(project, monkeypatch, mode):
    _, request, root = project
    captured = request()
    if mode == "ambiguous":
        access.register_project("JARVIS", root)
        sentence = "Who calls speak in my Jarvis project?"
    else:
        sentence = "Who calls speak in my Other project?"
        if mode == "inactive":
            other = root / "other"
            other.mkdir()
            access.register_project("Other", other)
    original = access._projects.copy(), access._active
    monkeypatch.setattr(answers, "analyze_scoped_callers", lambda *a, **k: pytest.fail("wrong project analyzed"))
    result = answers.prepare_scoped_caller_answer(sentence, captured)
    assert result.status == ("refused" if mode == "inactive" else "clarification")
    assert (access._projects, access._active) == original


@pytest.mark.parametrize("target", ["missing", "speak", "services/speaker.py::speak"])
def test_target_clarification_and_qualified_disambiguation(project, monkeypatch, target):
    write, request, _ = project
    write("commands/duplicate.py", "def speak():\n    pass\n")
    result = answers.prepare_scoped_caller_answer(f"Within commands, what calls {target}?", request())
    if "::" in target:
        assert result.status == "complete", result.reasons
    else:
        assert result.status == "clarification" and not result.relationships
        if target == "speak":
            assert set(result.target_options) == {"./commands/duplicate.py::speak", "./services/speaker.py::speak"}


@pytest.mark.parametrize("code", [
    "from services.speaker import speak as say\ndef Run():\n    say()\n",
    "import services.speaker as output\ndef Run():\n    output.speak()\n",
])
def test_alias_callers(project, code):
    write, request, _ = project
    write("commands/run.py", code)
    result = answers.prepare_scoped_caller_answer("Within commands, what calls speak?", request())
    assert result.status == "complete", result.reasons
    assert result.relationships[0].origin.qualified_name == "Run"


def test_findings_only_does_not_silently_claim_completeness(project):
    write, request, _ = project
    write("commands/run.py", "from services.speaker import speak\ndef Run(callback):\n    speak()\n    callback()\n")
    sentence = "Within commands, what calls speak?"
    complete = answers.prepare_scoped_caller_answer(sentence, request())
    assert complete.status == "refused" and not complete.relationships
    assert "Run" not in complete.text and "relevant_unresolved_boundaries" in complete.text
    result = answers.prepare_scoped_caller_answer(sentence, request(), claim=CompletenessClaim.FINDINGS_ONLY)
    assert result.status == "findings_only", result.reasons
    assert "Verified direct static findings" in result.text and "Additional callers may exist" in result.text
    assert "Complete direct" not in result.text


@pytest.mark.parametrize("dynamic", [False, True])
def test_empty_complete_vs_incomplete_results(project, dynamic):
    write, request, _ = project
    write("commands/run.py", "def Run(callback):\n    " + ("callback()" if dynamic else "pass") + "\n")
    result = answers.prepare_scoped_caller_answer("Within commands, what calls services/speaker.py::speak?", request())
    assert result.status == ("refused" if dynamic else "complete"), result.reasons
    assert not result.relationships
    assert ("No direct static callers" in result.text) == (not dynamic)


def test_no_silent_project_scope_narrowing(project):
    write, request, _ = project
    write("outside.py", "from services.speaker import speak\ndef Outside():\n    speak()\n")
    project_result = answers.prepare_scoped_caller_answer("What functions call speak in my Jarvis project?", request())
    directory = answers.prepare_scoped_caller_answer("Within commands, what calls speak?", request())
    assert project_result.status == directory.status == "complete"
    assert {e.origin.qualified_name for e in project_result.relationships} == {"Run", "Outside"}
    assert {e.origin.qualified_name for e in directory.relationships} == {"Run"}
    assert project_result.scope.kind == ScopeKind.PROJECT_PYTHON
    assert set(project_result.scope.search_files) == {"outside.py", "commands/run.py", "services/speaker.py"}


@pytest.mark.parametrize("path", ["../outside", "C:/Windows", ".git", "services/speaker.py"])
def test_unsafe_or_wrong_kind_directory_scopes_refuse(project, path):
    _, request, _ = project
    result = answers.prepare_scoped_caller_answer(f"Within directory {path}, what calls speak?", request())
    assert result.status == "refused" and not result.relationships


def test_validator_refusal_releases_no_facts(project, monkeypatch):
    _, request, _ = project
    monkeypatch.setattr(answers, "validate_scoped_callers", lambda candidate, scope, request, **k:
        ScopedValidationOutcome(scope.scope_id, k["claim"], refusal_reasons=("proof_dependency_changed",)))
    result = answers.prepare_scoped_caller_answer("Within commands, what calls speak?", request())
    assert result.status == "refused" and result.reasons == ("proof_dependency_changed",)
    assert "Run" not in result.text and not result.references


def test_forged_analyzer_relationship_is_rejected_by_real_validator(project, monkeypatch):
    _, request, _ = project
    original = answers.analyze_scoped_callers

    def forge(*args):
        candidate = original(*args)
        edge, = candidate.verified_callers
        return replace(candidate, result=replace(candidate.result, relationships=(
            replace(edge, origin=replace(edge.origin, qualified_name="InventedCaller")),)))

    monkeypatch.setattr(answers, "analyze_scoped_callers", forge)
    result = answers.prepare_scoped_caller_answer("Within commands, what calls speak?", request())
    assert result.status == "refused" and "InventedCaller" not in result.text


@pytest.mark.parametrize("change", ["source", "inventory", "revoke", "cancel", "deadline"])
def test_mid_operation_changes_do_not_return_late_facts(project, monkeypatch, change):
    write, request, root = project
    event = threading.Event()
    now = [0]
    captured = request(cancellation_event=event, clock=lambda: now[0])
    original = answers.validate_scoped_callers

    def changed(*args, **kwargs):
        if change == "source":
            write("commands/run.py", "from services.speaker import speak\ndef Changed():\n    speak()\n")
        elif change == "inventory":
            write("commands/new.py", "from services.speaker import speak\nspeak()\n")
        elif change == "revoke":
            access.revoke_project("Jarvis")
        elif change == "cancel":
            event.set()
        else:
            now[0] = 5
        return original(*args, **kwargs)

    monkeypatch.setattr(answers, "validate_scoped_callers", changed)
    if change == "cancel":
        with pytest.raises(OperationCancelled):
            answers.prepare_scoped_caller_answer("Within commands, what calls speak?", captured)
    else:
        result = answers.prepare_scoped_caller_answer("Within commands, what calls speak?", captured)
        assert result.status == "refused" and not result.relationships and not result.references


def test_already_cancelled_request_propagates(project):
    _, request, _ = project
    event = threading.Event()
    captured = request(cancellation_event=event)
    event.set()
    with pytest.raises(OperationCancelled):
        answers.prepare_scoped_caller_answer("Who calls speak in my project?", captured)
    with pytest.raises(OperationCancelled):
        answers.prepare_scoped_caller_answer("Trace speak reverse", captured)


def test_shared_budget_is_not_renewed(project):
    _, request, _ = project
    captured = request(limits=replace(AnalysisLimits(), python_files=3))
    budget = captured.budget
    result = answers.prepare_scoped_caller_answer("Within commands, what calls speak?", captured)
    assert result.status == "refused" and captured.budget is budget
    assert "budget" in result.text


def test_source_references_cover_the_actual_call_and_definition(project):
    _, request, _ = project
    result = answers.prepare_scoped_caller_answer("Within commands, what calls speak?", request())
    assert result.status == "complete"
    edge, = result.relationships
    refs = result.references
    assert any(r.path == edge.location.path and r.start_line <= edge.location.start_line <= r.end_line for r in refs)
    assert any(r.path == edge.origin.definition.path and r.start_line <= edge.origin.definition.start_line <= r.end_line for r in refs)
    assert any(r.path == edge.target.definition.path and r.start_line <= edge.target.definition.start_line <= r.end_line for r in refs)
    for path, start, end in re.findall(r"\[([^\]:]+):(\d+)–(\d+)\]", result.text):
        assert any(r.path == path and r.start_line == int(start) and r.end_line == int(end) for r in refs)


def test_fabricated_answer_reference_cannot_reuse_valid_eligibility(project):
    _, request, _ = project
    result = answers.prepare_scoped_caller_answer("Within commands, what calls speak?", request())
    with pytest.raises(ValueError, match="validated source windows"):
        replace(result, references=(replace(result.references[0], path="invented.py"),) + result.references[1:])


def test_orchestration_never_calls_delivery_ai_or_history(project, monkeypatch):
    _, request, _ = project
    from commands import router
    from services import speaker, conversation_service, status_service, ai_service

    def forbidden(*a, **k):
        pytest.fail("C3 internal work reached a live publication/model endpoint")

    for owner, names in [(router, ("process", "execute_registered_capability", "speak", "add_message", "ask_ai")),
                         (speaker, ("speak",)), (conversation_service, ("add_message", "save_message")),
                         (status_service, ("update_status", "update_last_response")),
                         (ai_service, ("ask_ai", "chat", "stream_ai_response"))]:
        for name in names:
            monkeypatch.setattr(owner, name, forbidden)
    result = answers.prepare_scoped_caller_answer("Within commands, what calls speak?", request())
    assert result.status == "complete" and not hasattr(result, "response") and not result.publication_enabled


def test_existing_c2_live_routing_stays_separate(project, monkeypatch):
    _, _, _ = project
    from commands import router
    from services.code_intent import resolve_relationship_request
    from types import SimpleNamespace
    heard = []
    monkeypatch.setattr(answers, "prepare_scoped_caller_answer", lambda *a, **k: pytest.fail("C3 live routing enabled"))
    monkeypatch.setattr(router, "execute_registered_capability", lambda name, *a, **k:
        heard.append(name) or SimpleNamespace(success=False))
    assert resolve_relationship_request("Who calls speak in my Jarvis project?")["qualified_name"] == "speak"
    router.process("Who calls speak in my Jarvis project?", allow_interruption=False)
    assert heard == ["multi_file_reasoning"]


@pytest.mark.parametrize("identifier", ["trace", "chain", "recursive", "indirectly"])
def test_target_identifiers_are_not_query_semantics(identifier):
    intent = parse(f"Within commands, who calls services/speaker.py::{identifier}?")
    assert intent.direct and intent.qualified_name == identifier


@pytest.mark.parametrize("sentence", ["In Jarvis, who calls speak?", "Who calls speak in Jarvis?",
    "Within commands, who calls speak in file commands/run.py?"])
def test_ambiguous_or_conflicting_scope_does_not_run_analysis(project, monkeypatch, sentence):
    _, request, _ = project
    monkeypatch.setattr(answers, "discover", lambda *a, **k: pytest.fail("ambiguous scope discovered"))
    result = answers.prepare_scoped_caller_answer(sentence, request())
    assert result.status == "clarification" and not result.relationships


def test_simulated_listener_preserves_intent_without_c3_publication(project, monkeypatch):
    write, request, _ = project
    from services import listener
    write("commands/run.py", "from services.speaker import Speak as Say\ndef Run():\n    Say()\n")

    class Microphone:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    from types import SimpleNamespace
    phrase = "Within commands, which functions directly call services/speaker.py::Speak?"
    monkeypatch.setattr(listener, "microphone", Microphone())
    monkeypatch.setattr(listener.recognizer, "listen", lambda *a, **k:
        SimpleNamespace(frame_data=b"00", sample_rate=1, sample_width=1))
    monkeypatch.setattr(listener, "transcribe_audio", lambda *a: phrase)
    captured = listener.listen_for_speech_result()
    assert captured.text == phrase
    result = answers.prepare_scoped_caller_answer(captured.text, request())
    assert result.status == "complete" and result.scope.target.qualified_name == "Speak"
    assert not result.publication_enabled


def test_cancelled_after_validation_does_not_escape_as_internal_facts(project, monkeypatch):
    _, request, _ = project
    event = threading.Event()
    captured = request(cancellation_event=event)
    original = answers.validate_scoped_callers

    def validate(*a, **k):
        outcome = original(*a, **k)
        assert outcome.publication_eligible
        event.set()
        return outcome

    monkeypatch.setattr(answers, "validate_scoped_callers", validate)
    with pytest.raises(OperationCancelled):
        answers.prepare_scoped_caller_answer("Within commands, what calls speak?", captured)


def test_analysis_source_edit_after_declaration_does_not_rebase_scope_silently(project, monkeypatch):
    write, request, _ = project
    original = answers.analyze_scoped_callers

    def analyze(*a):
        write("commands/run.py", "from services.speaker import speak\ndef Different():\n    speak()\n")
        return original(*a)

    monkeypatch.setattr(answers, "analyze_scoped_callers", analyze)
    result = answers.prepare_scoped_caller_answer("Within commands, what calls speak?", request())
    assert result.status == "refused" and not result.relationships


def test_support_cannot_expand_silently_beyond_one_hop(project):
    write, request, _ = project
    write("bridge.py", "from services.speaker import speak\n")
    write("commands/run.py", "from bridge import speak\ndef Run():\n    speak()\n")
    result = answers.prepare_scoped_caller_answer("Within commands, what calls services/speaker.py::speak?", request())
    assert result.status == "refused" and not result.relationships


def test_support_selection_does_not_truncate_to_fit(project):
    write, request, _ = project
    for i in range(7):
        write(f"module{i}.py", f"def helper{i}():\n    pass\n")
    write("commands/run.py", "from services.speaker import speak\n" +
        "".join(f"import module{i}\n" for i in range(7)) + "def Run():\n    speak()\n")
    result = answers.prepare_scoped_caller_answer("Within commands, what calls speak?", request())
    assert result.status == "refused" and result.reasons == ("support_file_limit",)


def test_incomplete_project_is_not_replaced_with_file_results(project):
    write, request, _ = project
    write("broken.py", "def broken(:\n")
    result = answers.prepare_scoped_caller_answer("What calls speak in my Jarvis project?", request())
    assert result.status == "refused" and not result.relationships
    assert "scope_source_parse_failed" in result.text


def test_qualified_filename_does_not_implicitly_limit_search_to_target_file(project):
    _, request, _ = project
    result = answers.prepare_scoped_caller_answer("Show callers of services/speaker.py::speak", request(),
        claim=CompletenessClaim.FINDINGS_ONLY)
    assert result.status == "clarification" and result.scope is None


@pytest.mark.parametrize("mode", ["findings_only", CompletenessClaim.NONE, CompletenessClaim.PROJECT_COMPLETE])
def test_unsupported_claim_or_wrong_scope_refuses(project, mode):
    _, request, _ = project
    result = answers.prepare_scoped_caller_answer("Within commands, what calls speak?", request(), claim=mode)
    assert result.status == "refused" and not result.relationships
