"""Exact fixture assertions for the explicit C2 path; never execute fixture code."""
from dataclasses import replace
import hashlib
import threading

import pytest

from models.project_relationships import RelationshipKind, Resolution, SymbolKind
from models.source_evidence import RetrievalLimits, RetrievalStatus
from services import project_access as access
from services.project_analysis_index import analyze_project_relationships
from services.project_analysis_request import AnalysisLimits, AnalysisRequest
from services.project_target import resolve_analysis_target


@pytest.fixture
def project(tmp_path):
    old = access._projects.copy(), access._active, access._revision
    access.register_project("fixture", tmp_path)
    access.select_project("fixture")
    def write(path, text):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target
    yield write
    access._projects, access._active, access._revision = old


def analyze(**kwargs):
    # A deterministic clock exercises accounting without CI timing assumptions.
    return analyze_project_relationships(AnalysisRequest.capture(clock=lambda: 0, **kwargs))


def calls(result):
    return [r for r in result.relationships if r.kind == RelationshipKind.CALLS]


def confirmed(result):
    return {(r.origin.definition.path, r.origin.qualified_name, r.target.definition.path, r.target.qualified_name)
            for r in calls(result) if r.resolution == Resolution.CONFIRMED_STATIC}


def test_exact_lexical_symbols_and_call_ownership(project):
    text = ("def leaf():\n    pass\n"
            "def outer():\n    leaf()\n    def inner():\n        leaf()\n    inner()\n"
            "class One:\n    def run(self):\n        leaf()\n"
            "class Two:\n    def run(self):\n        leaf()\n"
            "async def Async():\n    leaf()\n"
            "outer()\n")
    path = project("main.py", text)
    result = analyze()
    assert {(s.qualified_name, s.kind) for s in result.symbols} == {
        ("<module>", SymbolKind.MODULE), ("leaf", SymbolKind.FUNCTION), ("outer", SymbolKind.FUNCTION),
        ("outer.<locals>.inner", SymbolKind.FUNCTION), ("One", SymbolKind.CLASS), ("One.run", SymbolKind.METHOD),
        ("Two", SymbolKind.CLASS), ("Two.run", SymbolKind.METHOD), ("Async", SymbolKind.ASYNC_FUNCTION)}
    assert confirmed(result) == {("main.py", origin, "main.py", target) for origin, target in [
        ("outer", "leaf"), ("outer.<locals>.inner", "leaf"), ("outer", "outer.<locals>.inner"),
        ("One.run", "leaf"), ("Two.run", "leaf"), ("Async", "leaf"), ("<module>", "outer")]}
    assert len(calls(result)) == 7
    edge = next(r for r in calls(result) if r.origin.qualified_name == "outer.<locals>.inner")
    assert (edge.location.path, edge.location.start_line, edge.location.end_line,
            edge.location.start_column, edge.location.end_column) == ("main.py", 6, 6, 8, 14)
    assert edge.location.digest == hashlib.sha256(path.read_bytes()).hexdigest()
    assert result.snapshot.coverage.complete


def test_nested_class_qualified_identity_and_static_methods(project):
    project("main.py", "class Outer:\n    class Inner:\n        @staticmethod\n        def run():\n            pass\n"
            "class Other:\n    @classmethod\n    def run(cls):\n        pass\n"
            "def entry():\n    Outer.Inner.run()\n    Other.run()\n")
    result = analyze()
    assert confirmed(result) == {("main.py", "entry", "main.py", "Outer.Inner.run"),
                                 ("main.py", "entry", "main.py", "Other.run")}


def test_absolute_relative_alias_and_module_imports(project):
    project("pkg/__init__.py", "PACKAGE = True\n")
    project("pkg/worker.py", "def Save():\n    pass\nasync def wait():\n    pass\n"
            "class Tools:\n    @staticmethod\n    def run():\n        pass\n")
    project("pkg/client.py", "from .worker import Save as save\nfrom . import worker as w\n"
            "from pkg.worker import Tools as T\nimport pkg.worker as mod\nimport pkg.worker\n"
            "def entry():\n    save()\n    w.Save()\n    mod.Save()\n    pkg.worker.Save()\n    T.run()\n")
    result = analyze()
    assert confirmed(result) == {("pkg/client.py", "entry", "pkg/worker.py", name) for name in ("Save", "Tools.run")}
    assert len(calls(result)) == 5
    imports = [r for r in result.relationships if r.kind == RelationshipKind.IMPORTS]
    assert len(imports) == 5 and all(r.resolution == Resolution.CONFIRMED_STATIC for r in imports)
    first = next(r for r in imports if r.alias == "save")
    assert (first.imported_module, first.imported_member, first.relative_level,
            first.bound_name, first.lexical_scope, first.expression, first.location.start_line) == (
        "worker", "Save", 1, "save", "<module>", "from .worker import Save as save", 1)
    assert all(r.supporting_sources for r in calls(result))


def test_package_initialization_and_empty_module_are_parseable(project):
    project("pkg/__init__.py", "")
    project("pkg/worker.py", "def run():\n    pass\n")
    project("entry.py", "from pkg import worker\nworker.run()\n")
    result = analyze()
    assert result.snapshot.coverage.complete
    assert set(result.snapshot.coverage.parsed) == {"pkg/__init__.py", "pkg/worker.py", "entry.py"}
    assert confirmed(result) == {("entry.py", "<module>", "pkg/worker.py", "run")}


@pytest.mark.parametrize("statement,expression,reason", [
    ("from worker import missing", "missing()", "imported_member_not_defined"),
    ("from facade import run", "run()", "reexport_unsupported"),
    ("from worker import *", "run()", "shadowed_reassigned_or_wildcard_binding"),
    ("import outside", "outside.run()", "module_not_in_authorized_inventory"),
])
def test_unsupported_imports_are_not_invented_or_called_external(project, statement, expression, reason):
    project("worker.py", "def run():\n    pass\n")
    project("facade.py", "from worker import run\n")
    project("client.py", statement + "\n" + expression + "\n")
    result = analyze()
    edge = next(r for r in calls(result) if r.origin.definition.path == "client.py")
    assert edge.resolution == Resolution.UNRESOLVED and edge.target is None and edge.reason == reason


@pytest.mark.parametrize("body", [
    "def entry(run):\n    run()\n",
    "def entry():\n    run = lambda: None\n    run()\n",
    "run = lambda: None\nrun()\n",
    "def entry(obj):\n    obj.run()\n",
    "def entry():\n    globals()['run'] = None\n    run()\n",
    "def entry(value):\n    match value:\n        case {'run': run}:\n            run()\n",
])
def test_shadowing_reassignment_and_receivers_remain_unresolved(project, body):
    project("worker.py", "def run():\n    pass\n")
    project("client.py", "from worker import run\n" + body)
    result = analyze()
    edges = [r for r in calls(result) if r.expression.endswith("run")]
    assert edges and all(r.resolution == Resolution.UNRESOLVED for r in edges)


def test_monkey_patching_decorators_inheritance_and_callbacks_are_conservative(project):
    project("main.py", "def run():\n    pass\nclass A:\n    @staticmethod\n    def method():\n        pass\n"
            "class B(A):\n    pass\nA.method = run\n"
            "def entry(callback):\n    callback()\n    A.method()\n    B.method()\n"
            "    __import__('worker').run()\n")
    result = analyze()
    assert not confirmed(result)
    assert all(r.target is None for r in calls(result))


def test_ambiguous_definitions_and_case_preserving_target_resolution(project):
    project("a/mod.py", "def Run():\n    pass\ndef run():\n    pass\n")
    project("b/mod.py", "def Run():\n    pass\n")
    project("duplicate.py", "def run():\n    pass\ndef run():\n    pass\nrun()\n")
    result = analyze()
    ambiguous = next(r for r in calls(result) if r.origin.definition.path == "duplicate.py")
    assert ambiguous.resolution == Resolution.AMBIGUOUS and len(ambiguous.candidates) == 2
    assert resolve_analysis_target(result, "mod.py")["status"] == "ambiguous"
    assert resolve_analysis_target(result, "a/mod.py", "Run")["status"] == "resolved"
    assert resolve_analysis_target(result, "a/mod.py", "RUN")["status"] == "not_found"
    assert resolve_analysis_target(result, qualified_name="Run")["status"] == "ambiguous"
    assert resolve_analysis_target(result, "../mod.py")["status"] == "not_found"


def test_failures_unsupported_and_exclusions_are_visible_without_execution(project):
    project("broken.py", "def broken(:\n")
    project("a.js", "throw new Error('must not execute')\n")
    project("safe.py", "raise RuntimeError('must not execute')\ndef run():\n    pass\n")
    project(".env", "SECRET=not-read\n")
    project("secret.py", "must_not_read\n")
    result = analyze()
    coverage = result.snapshot.coverage
    assert {d.path for d in coverage.parse_failures} == {"broken.py"}
    assert {d.path for d in coverage.unsupported} == {"a.js"}
    assert set(coverage.discovered) == {"a.js", "broken.py", "safe.py", ".env", "secret.py"}
    assert {d.path for d in coverage.excluded} == {".env", "secret.py"}
    assert not coverage.complete
    assert any(s.qualified_name == "run" for s in result.symbols)


def test_separately_authorized_projects_never_share_symbols(project, tmp_path):
    project("worker.py", "def first():\n    pass\n")
    first = analyze()
    second_root = tmp_path / "second-root"
    second_root.mkdir()
    (second_root / "worker.py").write_text("def second():\n    pass\n")
    access.register_project("second", second_root)
    access.select_project("second")
    second = analyze()
    assert first.snapshot.project != second.snapshot.project
    assert not {s.symbol_id for s in first.symbols} & {s.symbol_id for s in second.symbols}
    assert {s.qualified_name for s in second.symbols} == {"<module>", "second"}
    from services.project_analysis_index import get_project_analysis_index
    with pytest.raises(access.ProjectAccessError):
        get_project_analysis_index()


@pytest.mark.parametrize("action", ["revision", "revoke"])
def test_stale_authorization_is_rejected(project, monkeypatch, action):
    project("main.py", "def run():\n    pass\n")
    from services import project_analysis_cache
    original = project_analysis_cache.read_analysis_source
    def changed(request, path):
        result = original(request, path)
        if action == "revision":
            access.register_project("fixture", request.context.root)
        else:
            access.revoke_project("fixture")
        return result
    monkeypatch.setattr(project_analysis_cache, "read_analysis_source", changed)
    with pytest.raises(access.ProjectAccessError):
        analyze()


@pytest.mark.parametrize("limits,resource", [
    ({"python_files": 1}, "python_files"), ({"source_bytes": 5}, "source_bytes"),
    ({"ast_nodes": 2}, "ast_nodes"), ({"ast_nodes_per_file": 2}, "ast_nodes_per_file"),
    ({"relationships": 1}, "relationships"),
])
def test_shared_budget_exhaustion_preserves_partial_coverage(project, limits, resource):
    project("a.py", "def run():\n    pass\nrun()\nrun()\n")
    project("b.py", "def run():\n    pass\n")
    request = AnalysisRequest.capture(limits=replace(AnalysisLimits(), **limits), clock=lambda: 0)
    result = analyze_project_relationships(request)
    assert not result.snapshot.coverage.complete
    assert resource in request.budget.usage.exhausted
    usage = dict(request.budget.usage.consumed)
    assert usage[resource] <= getattr(request.budget.limits, resource) if resource in usage else True


def test_cancellation_during_parse_returns_diagnostic_coverage(project, monkeypatch):
    project("main.py", "def run():\n    pass\n")
    event = threading.Event()
    from services import project_analysis_cache
    original = project_analysis_cache.read_analysis_source
    def cancel(request, path):
        result = original(request, path)
        event.set()
        return result
    monkeypatch.setattr(project_analysis_cache, "read_analysis_source", cancel)
    result = analyze(cancellation_event=event)
    assert result.snapshot.coverage.cancelled and not result.snapshot.coverage.complete
    assert not result.relationships


def test_partial_inventory_cannot_confirm_import_bindings(project, monkeypatch):
    project("a.py", "from b import run\nrun()\n")
    project("b.py", "def run():\n    pass\n")
    from services import project_retrieval
    original = project_retrieval.discover
    def partial(*args, **kwargs):
        result = original(*args, **kwargs)
        result.status = RetrievalStatus.PARTIAL
        result.limits_reached.append("entries")
        return result
    monkeypatch.setattr(project_retrieval, "discover", partial)
    result = analyze()
    assert not result.snapshot.coverage.discovery_complete and not confirmed(result)
    assert all(r.resolution == Resolution.INCOMPLETE for r in result.relationships)


def test_discovery_and_reads_use_one_inventory_and_actual_byte_charges(project, monkeypatch):
    first = project("a.py", "from b import run\nrun()\n")
    second = project("b.py", "def run():\n    pass\n")
    from services import project_retrieval
    original = project_retrieval.discover
    inventories = []
    def discover(*args, **kwargs):
        inventories.append(True)
        return original(*args, **kwargs)
    monkeypatch.setattr(project_retrieval, "discover", discover)
    request = AnalysisRequest.capture(clock=lambda: 0)
    result = analyze_project_relationships(request)
    usage = dict(request.budget.usage.consumed)
    assert len(inventories) == 1
    assert usage["source_bytes"] == first.stat().st_size + second.stat().st_size
    assert usage["python_files"] == 2 and usage["relationships"] == len(result.relationships)
    assert int(dict(result.snapshot.options)["discovery_entries"]) >= 2


def test_duplicate_alias_occurrences_have_distinct_source_locations(project):
    project("worker.py", "def run():\n    pass\n")
    project("client.py", "from worker import run, run\nrun()\n")
    result = analyze()
    imports = [r for r in result.relationships if r.kind == RelationshipKind.IMPORTS]
    assert len(imports) == 2 and len({r.relationship_id for r in imports}) == 2
    assert {r.location.start_column for r in imports} == {19, 24}


def test_cross_module_monkey_patching_cannot_confirm_export_calls(project):
    project("worker.py", "def run():\n    pass\n")
    project("patch.py", "import worker\nworker.run = None\n")
    project("client.py", "from worker import run\nrun()\n")
    result = analyze()
    assert not confirmed(result)


def test_reassigned_and_conditional_import_targets_are_unresolved(project):
    project("pkg/__init__.py", "def run():\n    pass\nrun = None\n")
    project("conditional.py", "if flag:\n    class A:\n        @staticmethod\n        def run():\n            pass\n")
    project("client.py", "from pkg import run\nimport conditional\nrun()\nconditional.A.run()\n")
    assert not confirmed(analyze())


def test_relative_import_cannot_escape_authorized_package(project):
    project("pkg/client.py", "from ...outside import run\nrun()\n")
    result = analyze()
    assert not confirmed(result)
    assert all(r.reason == "relative_import_outside_package" for r in result.relationships)


def test_unreadable_source_retains_explicit_coverage(project, monkeypatch):
    project("a.py", "pass\n")
    from services import project_analysis_cache
    from models.source_evidence import RetrievalResult
    def denied(request, path):
        return RetrievalResult(request.context.project_id, request.context.revision, "read",
                               RetrievalStatus.DENIED, error="fixture read denied")
    monkeypatch.setattr(project_analysis_cache, "read_analysis_source", denied)
    result = analyze()
    assert result.snapshot.coverage.skipped[0].reason == "fixture read denied"
    assert not result.snapshot.coverage.complete


def test_expired_request_during_discovery_is_incomplete(project):
    project("a.py", "pass\n")
    tick = [0]
    def clock():
        tick[0] += 1
        return tick[0]
    result = analyze_project_relationships(AnalysisRequest.capture(clock=clock))
    assert not result.snapshot.coverage.complete
    assert "seconds" in result.snapshot.coverage.budget_exhausted


def test_ambiguous_module_is_not_disambiguated_by_missing_attribute(project):
    project("worker.py", "def run():\n    pass\n")
    project("worker/__init__.py", "pass\n")
    project("client.py", "import worker\nworker.run()\n")
    result = analyze()
    assert not confirmed(result)
    assert next(r for r in result.relationships if r.kind == RelationshipKind.IMPORTS).resolution == Resolution.AMBIGUOUS


@pytest.mark.parametrize("patch", ["vars(worker)['run'] = None", "worker.__dict__['run'] = None",
                                   "setattr(worker, 'run', None)"])
def test_reflective_monkey_patching_is_not_a_confirmed_call(project, patch):
    project("worker.py", "def run():\n    pass\n")
    project("patch.py", "import worker\n" + patch + "\n")
    project("client.py", "from worker import run\nrun()\n")
    assert not confirmed(analyze())


def test_metaclass_dispatch_and_decorated_functions_are_unresolved(project):
    project("main.py", "class A(metaclass=Meta):\n    @staticmethod\n    def run():\n        pass\n"
            "@replace_function\ndef decorated():\n    pass\nA.run()\ndecorated()\n")
    assert not confirmed(analyze())
