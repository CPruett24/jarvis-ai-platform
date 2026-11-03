"""C3.3 only inspects disposable source data; no routing or publication."""
import ast
from dataclasses import replace
import hashlib
import threading

import pytest

from models.project_scope import (
    AnalysisScope, SupportClosure, ScopeKind, QuerySemantics, CoverageStatus, CompletenessClaim,
)
from models.project_relationships import (
    SourceLocation, RelationshipKind, RelationshipRecord, Resolution, SymbolRecord, SymbolKind,
)
from services import project_access as access, scoped_relationship_analysis as engine
from services.project_analysis_cache import read_analysis_source
from services.project_analysis_request import AnalysisRequest, AnalysisLimits
from services.project_symbol_index import extract_scoped_symbols
from services.cancellation import OperationCancelled


@pytest.fixture
def project(tmp_path):
    previous = access._projects.copy(), access._active, access._revision
    access.register_project("scoped", tmp_path)
    access.select_project("scoped")
    def write(name, text):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        return path
    write("voice.py", "def Speak():\n    pass\n")
    write("app/run.py", "from voice import Speak\ndef run():\n    Speak()\n")
    def prepare(search=("app/run.py",), support=("voice.py",), kind=ScopeKind.FILES,
                roots=None, target_path="voice.py", target_name="Speak", exclusions=(), limits=None, event=None, clock=lambda: 0):
        # Declaration capture is a separate trusted fixture setup action. The
        # analyzed request starts fresh; its budget is never reset by the engine.
        declaration = AnalysisRequest.capture(clock=lambda: 0)
        source = read_analysis_source(declaration, target_path).excerpts[0]
        module = extract_scoped_symbols(ast.parse(source.text), source, declaration)
        target = next(s.symbol for s in module.scopes if s.symbol.qualified_name == target_name)
        sources = tuple(SourceLocation.from_excerpt(declaration.identity,
            read_analysis_source(declaration, path).excerpts[0]) for path in support)
        if roots is None:
            roots = search if kind == ScopeKind.FILES else ("app",) if kind == ScopeKind.DIRECTORY else ()
        scope = AnalysisScope(declaration.identity, kind, roots, search,
            SupportClosure(declaration.identity, support, sources, True, 1 if support else 0),
            target, RelationshipKind.CALLS, "reverse", QuerySemantics.DIRECT, excluded_paths=exclusions)
        request = AnalysisRequest.capture(limits=limits, cancellation_event=event, clock=clock)
        return scope, request
    yield write, prepare, tmp_path
    access._projects, access._active, access._revision = previous


def test_exact_source_backed_direct_caller_and_identity(project):
    _, prepare, _ = project
    scope, request = prepare()
    result = engine.analyze_scoped_callers(scope, request)
    assert result.target_status == "resolved" and result.result.coverage.status == CoverageStatus.COMPLETE
    assert result.scope_id == scope.scope_id
    edge, = result.verified_callers
    digest = hashlib.sha256(b"from voice import Speak\ndef run():\n    Speak()\n").hexdigest()
    source_id = "S" + hashlib.sha256(f"{request.context}:app/run.py:1:{digest}".encode()).hexdigest()[:12]
    def location(start, end, column, end_column):
        return SourceLocation(request.identity, "app/run.py", source_id, digest, start, end, column, end_column)
    expected = RelationshipRecord(RelationshipKind.CALLS,
        SymbolRecord("run", SymbolKind.FUNCTION, location(2, 3, 0, 11)), scope.target,
        "Speak", location(3, 3, 4, 11), Resolution.CONFIRMED_STATIC, "lexical_or_imported_binding",
        supporting_sources=(location(1, 1, 18, 23),))
    assert edge == expected and edge.relationship_id == expected.relationship_id
    assert result.result.claim == CompletenessClaim.NONE
    assert not result.publication_ready and not result.freshness_verified
    assert result.usage.consumed == request.budget.usage.consumed


@pytest.mark.parametrize("text,origin", [
    ("from voice import Speak as say\ndef run():\n    say()\n", "run"),
    ("import voice as output\ndef run():\n    output.Speak()\n", "run"),
    ("import voice\ndef run():\n    voice.Speak()\n", "run"),
    ("def Speak():\n    pass\ndef run():\n    Speak()\n", "run"),
])
def test_aliases_module_aliases_and_local_calls(project, text, origin):
    write, prepare, _ = project
    write("app/run.py", text)
    local = text.startswith("def Speak")
    scope, request = prepare(target_path="app/run.py" if local else "voice.py", support=() if local else ("voice.py",))
    result = engine.analyze_scoped_callers(scope, request)
    assert [r.origin.qualified_name for r in result.verified_callers] == [origin]
    assert result.verified_callers[0].target == scope.target


def test_same_name_other_module_is_not_the_target(project):
    write, prepare, _ = project
    write("other.py", "def Speak():\n    pass\n")
    write("app/run.py", "from other import Speak\ndef run():\n    Speak()\n")
    scope, request = prepare(support=("voice.py", "other.py"))
    result = engine.analyze_scoped_callers(scope, request)
    assert result.target_status == "resolved" and not result.verified_callers
    assert result.result.claim == CompletenessClaim.NONE


def test_unread_import_module_alternative_is_not_disambiguated_by_scope(project):
    write, prepare, _ = project
    write("voice/__init__.py", "def Speak():\n    pass\n")
    scope, request = prepare()
    result = engine.analyze_scoped_callers(scope, request)
    assert not result.verified_callers
    assert result.boundaries and result.result.coverage.status == CoverageStatus.INCOMPLETE


def test_duplicate_definitions_and_stale_target_are_rejected(project):
    write, prepare, _ = project
    write("voice.py", "def Speak():\n    pass\ndef Speak():\n    pass\n")
    scope, request = prepare()
    result = engine.analyze_scoped_callers(scope, request)
    assert result.target_status == "ambiguous" and len(result.target_candidates) == 2
    assert not result.verified_callers
    write("voice.py", "def Speak():\n    pass\n")
    scope, request = prepare()
    write("voice.py", "def Speak():\n    return 1\n")
    assert engine.analyze_scoped_callers(scope, request).target_status == "stale"


@pytest.mark.parametrize("text", [
    "from voice import Speak\ndef run(Speak):\n    Speak()\n",
    "from voice import Speak\nSpeak = None\ndef run():\n    Speak()\n",
    "if True:\n    from voice import Speak\ndef run():\n    Speak()\n",
    "def run(obj):\n    obj.Speak()\n",
    "def run(callback):\n    callback()\n",
    "from missing import Speak\ndef run():\n    Speak()\n",
])
def test_unavailable_or_dynamic_bindings_are_not_verified(project, text):
    write, prepare, _ = project
    write("app/run.py", text)
    scope, request = prepare()
    result = engine.analyze_scoped_callers(scope, request)
    assert not result.verified_callers and result.boundaries
    assert all(r.resolution != Resolution.CONFIRMED_STATIC for r in result.boundaries)


def test_conditional_target_and_reexport_are_not_verified(project):
    write, prepare, _ = project
    write("voice.py", "if True:\n    def Speak():\n        pass\n")
    scope, request = prepare()
    assert engine.analyze_scoped_callers(scope, request).target_status == "unsupported"
    write("voice.py", "def Speak():\n    pass\n")
    write("bridge.py", "from voice import Speak\n")
    write("app/run.py", "from bridge import Speak\ndef run():\n    Speak()\n")
    scope, request = prepare(support=("voice.py", "bridge.py"))
    result = engine.analyze_scoped_callers(scope, request)
    assert not result.verified_callers and any(r.reason == "reexport_unsupported" for r in result.boundaries)


@pytest.mark.parametrize("mutation", ["output.Speak = None", "setattr(output, 'Speak', None)"])
def test_cross_module_mutation_taints_target(project, mutation):
    write, prepare, _ = project
    write("app/patch.py", "import voice as output\n" + mutation + "\n")
    scope, request = prepare(search=("app/run.py", "app/patch.py"))
    result = engine.analyze_scoped_callers(scope, request)
    assert not result.verified_callers
    assert any(r.reason == "conditional_or_mutated_target" for r in result.boundaries)


def test_support_does_not_become_caller_scope_or_read_unrelated_files(project, monkeypatch):
    write, prepare, _ = project
    write("voice.py", "def Speak():\n    pass\ndef support_caller():\n    Speak()\n")
    write("unrelated.py", "raise RuntimeError('MUST NEVER EXECUTE')\n")
    scope, request = prepare()
    paths = []
    original = engine.read_analysis_source
    def spy(request, path):
        paths.append(path)
        return original(request, path)
    monkeypatch.setattr(engine, "read_analysis_source", spy)
    result = engine.analyze_scoped_callers(scope, request)
    assert [r.origin.qualified_name for r in result.verified_callers] == ["run"]
    assert set(paths) == {"app/run.py", "voice.py"}
    assert dict(result.usage.consumed)["python_files"] == 2


@pytest.mark.parametrize("kind", [ScopeKind.FILES, ScopeKind.DIRECTORY, ScopeKind.PROJECT_PYTHON])
def test_declared_scope_kinds_and_documentation(project, kind):
    write, prepare, _ = project
    write("app/README.md", "not Python; Speak() is just text\n")
    project_scope = kind == ScopeKind.PROJECT_PYTHON
    scope, request = prepare(kind=kind, search=("app/run.py", "voice.py") if project_scope else ("app/run.py",),
                             support=() if project_scope else ("voice.py",))
    result = engine.analyze_scoped_callers(scope, request)
    assert result.result.coverage.status == CoverageStatus.COMPLETE
    assert len(result.verified_callers) == 1
    if kind != ScopeKind.FILES:
        assert result.result.coverage.non_python_files == ("app/README.md",)


def test_membership_changes_and_explicit_test_exclusion(project):
    write, prepare, _ = project
    write("app/tests/check.py", "from voice import Speak\ndef test_call():\n    Speak()\n")
    scope, request = prepare(kind=ScopeKind.DIRECTORY)
    result = engine.analyze_scoped_callers(scope, request)
    assert "search_membership_changed" in result.diagnostics
    assert result.result.coverage.status == CoverageStatus.INCOMPLETE
    assert [r.origin.qualified_name for r in result.verified_callers] == ["run"]
    scope, request = prepare(kind=ScopeKind.DIRECTORY, exclusions=("app/tests",))
    assert engine.analyze_scoped_callers(scope, request).result.coverage.status == CoverageStatus.COMPLETE
    scope, request = prepare(kind=ScopeKind.DIRECTORY, search=("app/run.py", "app/tests/check.py"))
    assert len(engine.analyze_scoped_callers(scope, request).verified_callers) == 2


@pytest.mark.parametrize("mode", ["invalid", "missing", "unreadable", "excluded"])
def test_required_python_failures_are_visible(project, monkeypatch, mode):
    from models.source_evidence import RetrievalResult, RetrievalStatus
    write, prepare, root = project
    if mode == "invalid":
        write("app/run.py", "def invalid(:\n")
    search = ("data/hidden.py",) if mode == "excluded" else ("app/run.py",)
    scope, request = prepare(search=search)
    if mode == "missing":
        (root / "app/run.py").rename(root / "app/removed.txt")
    if mode == "unreadable":
        original = engine.read_analysis_source
        monkeypatch.setattr(engine, "read_analysis_source", lambda r, p:
            RetrievalResult(r.context.project_id, r.context.revision, "read", RetrievalStatus.READ_ERROR)
            if p == "app/run.py" else original(r, p))
    result = engine.analyze_scoped_callers(scope, request)
    assert result.result.coverage.status == CoverageStatus.INCOMPLETE
    assert result.result.coverage.limitations and not result.verified_callers


@pytest.mark.parametrize("resource,value", [("python_files", 1), ("source_bytes", 8), ("ast_nodes", 1), ("relationships", 1)])
def test_shared_resource_exhaustion_is_explicit(project, resource, value):
    _, prepare, _ = project
    scope, request = prepare(limits=replace(AnalysisLimits(), **{resource: value}))
    result = engine.analyze_scoped_callers(scope, request)
    assert result.result.coverage.status == CoverageStatus.INCOMPLETE
    assert result.result.coverage.extraction_truncated
    assert "budget:" + resource in result.diagnostics
    assert dict(result.usage.consumed)[resource] <= value


@pytest.mark.parametrize("phase", ["before", "read", "calls"])
def test_cancellation_propagates(project, monkeypatch, phase):
    _, prepare, _ = project
    event = threading.Event()
    scope, request = prepare(event=event)
    if phase == "before":
        event.set()
    else:
        name = "read_analysis_source" if phase == "read" else "resolve_source_calls"
        original = getattr(engine, name)
        def cancel(*a, **k):
            event.set()
            return original(*a, **k)
        monkeypatch.setattr(engine, name, cancel)
    with pytest.raises(OperationCancelled):
        engine.analyze_scoped_callers(scope, request)


def test_deadline_is_not_reset(project, monkeypatch):
    _, prepare, _ = project
    now = [0.0]
    scope, request = prepare(clock=lambda: now[0])
    original = engine.read_analysis_source
    def expire(*a, **k):
        now[0] = 6
        return original(*a, **k)
    monkeypatch.setattr(engine, "read_analysis_source", expire)
    result = engine.analyze_scoped_callers(scope, request)
    assert "budget:seconds" in result.diagnostics and not result.verified_callers


@pytest.mark.parametrize("mode", ["revoke", "revision", "other_root"])
def test_authorization_changes_rejected(project, mode, tmp_path):
    _, prepare, _ = project
    scope, request = prepare()
    if mode == "revoke":
        access.revoke_project("scoped")
    elif mode == "revision":
        access.register_project("scoped", request.context.root)
    else:
        access.register_project("other", tmp_path)
        access.select_project("other")
    with pytest.raises(access.ProjectAccessError):
        engine.analyze_scoped_callers(scope, request)


def test_source_change_during_calls_discards_candidates(project, monkeypatch):
    write, prepare, _ = project
    scope, request = prepare()
    original = engine.resolve_source_calls
    def changed(*a, **k):
        yield from original(*a, **k)
        write("voice.py", "def Speak():\n    return 99\n")
    monkeypatch.setattr(engine, "resolve_source_calls", changed)
    result = engine.analyze_scoped_callers(scope, request)
    assert result.result.coverage.source_changed and not result.verified_callers


def test_deterministic_records_and_unsupported_queries(project):
    _, prepare, _ = project
    scope, request = prepare()
    first = engine.analyze_scoped_callers(scope, request)
    scope, request = prepare()
    second = engine.analyze_scoped_callers(scope, request)
    assert first.result == second.result and first.fingerprints == second.fingerprints
    with pytest.raises(ValueError):
        engine.analyze_scoped_callers(replace(scope, semantics=QuerySemantics.TRANSITIVE), request)


def test_path_traversal_is_rejected_by_scope(project):
    _, prepare, _ = project
    scope, _ = prepare()
    with pytest.raises(ValueError):
        replace(scope, roots=("../outside.py",), search_files=("../outside.py",))


def test_two_parsed_module_alternatives_do_not_resolve_by_member_presence(project):
    write, prepare, _ = project
    write("voice/__init__.py", "def other():\n    pass\n")
    scope, request = prepare(support=("voice.py", "voice/__init__.py"))
    result = engine.analyze_scoped_callers(scope, request)
    assert not result.verified_callers
    assert any(edge.reason == "ambiguous_module_path" for edge in result.boundaries)


def test_missing_support_and_one_hop_boundary(project):
    write, prepare, _ = project
    scope, request = prepare()
    scope = replace(scope, support=SupportClosure(scope.project, ("voice.py", "absent.py")))
    result = engine.analyze_scoped_callers(scope, request)
    assert not result.verified_callers and not result.result.coverage.scope.support.complete
    assert any(d.path == "absent.py" for d in result.result.coverage.limitations)
    write("helper.py", "def help_out():\n    pass\n")
    write("voice.py", "from helper import help_out\ndef Speak():\n    pass\n")
    scope, request = prepare(support=("voice.py", "helper.py"))
    result = engine.analyze_scoped_callers(scope, request)
    assert "support_depth_boundary" in result.diagnostics and not result.verified_callers
    assert result.scope_id == scope.scope_id


@pytest.mark.parametrize("phase", ["calls", "assembly"])
@pytest.mark.parametrize("change", ["revoke", "cancel", "deadline"])
def test_active_request_checked_during_work_and_before_return(project, monkeypatch, phase, change):
    _, prepare, _ = project
    event, now = threading.Event(), [0.0]
    scope, request = prepare(event=event, clock=lambda: now[0])
    def invalidate():
        if change == "revoke":
            access.revoke_project("scoped")
        elif change == "cancel":
            event.set()
        else:
            now[0] = 6
    if phase == "calls":
        original = engine.resolve_source_calls
        def intercept(*a, **k):
            yield from original(*a, **k)
            invalidate()
        monkeypatch.setattr(engine, "resolve_source_calls", intercept)
    else:
        original = engine.ScopedRelationshipResult
        def intercept(*a, **k):
            result = original(*a, **k)
            invalidate()
            return result
        monkeypatch.setattr(engine, "ScopedRelationshipResult", intercept)
    if change == "deadline":
        result = engine.analyze_scoped_callers(scope, request)
        assert result.result.coverage.status == CoverageStatus.INCOMPLETE
        assert result.result.coverage.extraction_truncated and "budget:seconds" in result.diagnostics
        assert not result.publication_ready
    else:
        with pytest.raises(OperationCancelled if change == "cancel" else access.ProjectAccessError):
            engine.analyze_scoped_callers(scope, request)


@pytest.mark.parametrize("new_path", ["app/new.py", "voice/__init__.py"])
def test_new_caller_or_import_alternative_invalidates_snapshot(project, monkeypatch, new_path):
    write, prepare, _ = project
    scope, request = prepare(kind=ScopeKind.DIRECTORY)
    original = engine.resolve_source_calls
    def changed(*a, **k):
        yield from original(*a, **k)
        write(new_path, "def Speak():\n    pass\n")
    monkeypatch.setattr(engine, "resolve_source_calls", changed)
    result = engine.analyze_scoped_callers(scope, request)
    assert result.result.coverage.source_changed and not result.verified_callers
    assert "source_or_inventory_changed" in result.diagnostics


def test_reparse_boundary_is_denied_without_symlink_privileges(project, monkeypatch):
    from pathlib import Path
    from types import SimpleNamespace
    _, prepare, root = project
    scope, request = prepare()
    original = Path.lstat
    def lstat(path):
        if path == root / "app/run.py":
            return SimpleNamespace(st_mode=0o100644, st_file_attributes=0x400)
        return original(path)
    monkeypatch.setattr(Path, "lstat", lstat)
    result = engine.analyze_scoped_callers(scope, request)
    assert not result.verified_callers
    assert any(d.path == "app/run.py" and d.reason == "excluded_required_python"
               for d in result.result.coverage.limitations)


def test_hard_link_to_outside_source_is_denied(project, tmp_path_factory):
    import os
    _, prepare, root = project
    scope, request = prepare()
    outside = tmp_path_factory.mktemp("outside_authorized_root")
    (root / "app/run.py").rename(root / "app/original.txt")
    (outside / "external.py").write_text("from voice import Speak\nSpeak()\n", encoding="utf-8")
    os.link(outside / "external.py", root / "app/run.py")
    result = engine.analyze_scoped_callers(scope, request)
    assert not result.verified_callers
    assert any(d.reason == "excluded_required_python" for d in result.result.coverage.limitations)
