"""C3.6b inactive discovery on disposable sources; no source imports/execution."""
from dataclasses import FrozenInstanceError, replace
from types import SimpleNamespace
import threading

import pytest

from models.dependency_disposition import DependencyPolicy
from models.project_relationships import SourceLocation, SymbolKind
from models.target_discovery import TargetIdentityResult, TargetIdentityStatus as Status
from services import project_access as access, scoped_target_discovery as discovery
from services import scoped_relationship_answer as construction
from services.cancellation import OperationCancelled
from services.project_analysis_request import AnalysisRequest, AnalysisBudget, AnalysisLimits


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setattr(access, "_projects", {})
    monkeypatch.setattr(access, "_revision", access._revision)
    monkeypatch.setattr(access, "_active", access._active)
    access.register_project("Jarvis", tmp_path)
    access.select_project("Jarvis")

    def write(path, text):
        file = tmp_path / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text, encoding="utf-8", newline="\n")
        return file

    write("voice.py", "def Speak():\n    pass\nclass Speaker:\n    @classmethod\n    def Speak(cls):\n        pass\n")
    write("app/run.py", "from voice import Speak\ndef Run():\n    Speak()\n")
    return SimpleNamespace(root=tmp_path, write=write, request=AnalysisRequest.capture)


def discover(project, target="voice.py::Speak", **kwargs):
    request = kwargs.pop("request", None) or project.request()
    return discovery.discover_target_identity(f"Within app, what directly calls {target}?", request, **kwargs)


@pytest.mark.parametrize("target,kind", [("Speak", SymbolKind.FUNCTION), ("Speaker.Speak", SymbolKind.METHOD)])
def test_exact_file_qualified_definitions_are_distinct(project, target, kind):
    handle = discover(project, "voice.py::" + target)
    result = handle.result
    assert result.status == Status.EXACT, result.reasons
    assert result.target.qualified_name == target and result.target.kind == kind
    assert result.lookup_files == ("voice.py",) and result.search_files == ("app/run.py",)
    assert result.support_budget_files == ("voice.py",)
    assert result.target.definition.project == handle.request.identity
    assert result.policy.policy_id == DependencyPolicy().policy_id
    assert not result.publication_enabled and not result.omission_enabled


def test_qualified_discovery_precedes_unconditional_support_admission_without_activating_it(project, monkeypatch):
    for i in range(7):
        project.write(f"helper{i}.py", f"def helper{i}():\n    pass\n")
    project.write("app/run.py", "from voice import Speak\n" +
        "".join(f"import helper{i}\n" for i in range(7)) + "def Run():\n    Speak()\n")
    early = discover(project)
    assert early.result.status == Status.EXACT and early.result.lookup_files == ("voice.py",)
    assert dict(early.request.budget.usage.consumed)["python_files"] == 1
    assert discover(project, "Speak").result.reasons == ("support_file_limit",)
    monkeypatch.setattr(discovery, "discover_target_identity", lambda *a, **k: pytest.fail("inactive planner activated"))
    answer = construction.prepare_scoped_caller_answer("Within app, what calls voice.py::Speak?", project.request())
    assert answer.status == "refused" and answer.reasons == ("support_file_limit",)


def test_unqualified_lookup_keeps_all_direct_import_domains(project):
    project.write("other.py", "def Speak():\n    pass\ndef Unused():\n    pass\n")
    project.write("app/run.py", "from voice import Speak\nfrom other import Unused\ndef Run():\n    Speak()\n")
    result = discover(project, "Speak").result
    assert result.status == Status.AMBIGUOUS and result.target is None
    assert {s.definition.path for s in result.candidates} == {"voice.py", "other.py"}
    assert result.lookup_files == ("app/run.py", "other.py", "voice.py")


def test_duplicate_definitions_in_one_file_remain_ambiguous(project):
    project.write("voice.py", "def Speak():\n    pass\ndef Speak():\n    pass\n")
    result = discover(project).result
    assert result.status == Status.AMBIGUOUS and len(result.candidates) == 2
    assert len({s.symbol_id for s in result.candidates}) == 2


def test_qualified_identity_does_not_narrow_declared_search_membership(project):
    project.write("app/other.py", "from voice import Speak\ndef Other():\n    Speak()\n")
    result = discover(project).result
    assert result.status == Status.EXACT and result.lookup_files == ("voice.py",)
    assert result.search_files == ("app/other.py", "app/run.py")


def test_import_aliases_do_not_choose_a_convenient_definition(project):
    project.write("other.py", "def Speak():\n    pass\n")
    project.write("app/run.py", "from voice import Speak as Pick\nfrom other import Speak as Pick\ndef Run():\n    Pick()\n")
    assert discover(project, "Pick").result.status == Status.UNRESOLVED
    assert discover(project, "Speak").result.status == Status.AMBIGUOUS
    # A physical file-qualified identity does not certify this caller binding.
    assert discover(project).result.status == Status.EXACT


def test_reexports_are_not_followed_as_definitions(project):
    project.write("bridge.py", "from voice import Speak as Announce\n")
    project.write("app/run.py", "from bridge import Announce\ndef Run():\n    Announce()\n")
    for target in ("Announce", "bridge.py::Announce", "Speak"):
        result = discover(project, target).result
        assert result.status == Status.UNRESOLVED and result.target is None
    assert discover(project).result.status == Status.EXACT


@pytest.mark.parametrize("code", [
    "if True:\n    def Speak():\n        pass\n",
    "def Speak():\n    pass\nSpeak = None\n",
    "def decorate(f):\n    return f\n@decorate\ndef Speak():\n    pass\n",
    "def Speak():\n    pass\nfrom other import Speak\n",
    "def Speak():\n    pass\nfrom other import *\n",
    "def Speak():\n    pass\nSpeak.flag = True\n",
])
def test_unstable_target_bindings_are_unresolved(project, code):
    project.write("voice.py", code)
    result = discover(project).result
    assert result.status == Status.UNRESOLVED and result.reasons == ("target_binding_unproven",)


def test_module_package_alternatives_are_not_resolved_by_member_convenience(project):
    project.write("voice/__init__.py", "def Speak():\n    pass\n")
    result = discover(project, "Speak").result
    assert result.status == Status.AMBIGUOUS
    assert {s.definition.path for s in result.candidates} == {"voice.py", "voice/__init__.py"}


def test_denied_import_alternative_is_unknown_not_absent(project, monkeypatch):
    original = construction._scope_inventory

    def excluded(*a, **k):
        roots, search, inventory, denied = original(*a, **k)
        return roots, search, inventory, tuple(sorted(denied + (("voice/__init__.py", "link_or_reparse_exclusion"),)))

    monkeypatch.setattr(construction, "_scope_inventory", excluded)
    result = discover(project, "Speak").result
    assert result.status == Status.REFUSED and result.reasons == ("target_lookup_alternative_unavailable",)


@pytest.mark.parametrize("target,status", [
    ("missing.py::Speak", Status.UNRESOLVED), ("voice.py::Missing", Status.UNRESOLVED),
    ("data/hidden.py::Speak", Status.REFUSED), ("credentials.py::Speak", Status.REFUSED),
    ("../outside.py::Speak", Status.REFUSED), ("C:/outside.py::Speak", Status.REFUSED),
    ("/outside.py::Speak", Status.REFUSED),
])
def test_missing_excluded_and_unauthorized_paths_fail_closed(project, target, status):
    project.write("data/hidden.py", "def Speak():\n    pass\n")
    project.write("credentials.py", "def Speak():\n    pass\n")
    result = discover(project, target).result
    assert result.status == status and result.target is None


def test_duplicate_target_basenames_require_clarification(project):
    project.write("other/voice.py", "def Speak():\n    pass\n")
    result = discover(project).result
    assert result.status == Status.AMBIGUOUS and result.file_options == ("other/voice.py", "voice.py")
    assert result.lookup_files == ()
    assert discover(project, "./voice.py::Speak").result.status == Status.EXACT


@pytest.mark.parametrize("change", ["source", "negative_source", "new_file", "alternative"])
def test_source_and_inventory_changes_refuse_before_use(project, change):
    project.write("other.py", "def Unused():\n    pass\n")
    project.write("app/run.py", "from voice import Speak\nfrom other import Unused\ndef Run():\n    Speak()\n")
    handle = discover(project, "Speak")
    assert handle.result.status == Status.EXACT
    if change == "source":
        project.write("voice.py", "def Speak():\n    return 2\n")
    elif change == "negative_source":
        project.write("other.py", "def Speak():\n    pass\ndef Unused():\n    pass\n")
    elif change == "new_file":
        project.write("app/new.py", "def Speak():\n    pass\n")
    else:
        project.write("voice/__init__.py", "def Speak():\n    pass\n")
    fresh = discovery.revalidate_target_identity(handle)
    assert fresh.status == Status.REFUSED and fresh.target is None
    assert fresh.reasons == ("target_discovery_changed",)


def test_mid_discovery_source_change_is_detected(project, monkeypatch):
    original = discovery.resolve_analysis_target

    def changed(*a, **k):
        selected = original(*a, **k)
        project.write("voice.py", "def Speak():\n    return 3\n")
        return selected

    monkeypatch.setattr(discovery, "resolve_analysis_target", changed)
    result = discover(project).result
    assert result.status == Status.REFUSED and result.reasons == ("target_sources_changed",)


@pytest.mark.parametrize("change", ["revision", "active", "qualifier"])
def test_authorization_is_captured_never_inferred_or_switched(project, change):
    request = project.request()
    if change == "revision":
        access.register_project("Jarvis", project.root)
    elif change == "active":
        access.register_project("Other", project.root)
        access.select_project("Other")
    command = ("Within app, what calls voice.py::Speak?" if change != "qualifier" else
        "Within the app directory of my Other project, what calls voice.py::Speak?")
    before = access._projects.copy(), access._active, access._revision
    result = discovery.discover_target_identity(command, request).result
    assert result.status != Status.EXACT and result.target is None
    assert (access._projects, access._active, access._revision) == before


def test_authorization_changes_between_discovery_and_use_refuse(project):
    handle = discover(project)
    assert handle.result.status == Status.EXACT
    access.register_project("Jarvis", project.root)
    result = discovery.revalidate_target_identity(handle)
    assert result.status == Status.REFUSED
    assert result.reasons == ("target_authorization_or_containment_changed",)


@pytest.mark.parametrize("mode", ["ambiguous", "unknown", "inactive"])
def test_named_project_qualifiers_fail_closed_before_source_reads(project, monkeypatch, mode):
    qualifier = "Other"
    if mode == "ambiguous":
        access.register_project("JARVIS", project.root)
        qualifier = "Jarvis"
    elif mode == "inactive":
        access.register_project("Other", project.root)
    request = project.request()
    monkeypatch.setattr(discovery, "read_analysis_source", lambda *a, **k: pytest.fail("unauthorized source read"))
    result = discovery.discover_target_identity(
        f"Within the app directory of my {qualifier} project, who calls voice.py::Speak?", request).result
    assert result.status == (Status.REFUSED if mode == "inactive" else Status.UNRESOLVED)
    assert result.target is None and dict(request.budget.usage.consumed)["source_bytes"] == 0


def test_nonexact_discovery_cannot_hide_cancellation_or_deadline(project):
    now, event = [0.0], threading.Event()
    handle = discover(project, "Missing", request=project.request(clock=lambda: now[0], cancellation_event=event))
    assert handle.result.status == Status.UNRESOLVED
    now[0] = 5.0
    assert discovery.revalidate_target_identity(handle).reasons == ("target_discovery_budget_exhausted:seconds",)
    event.set()
    with pytest.raises(OperationCancelled):
        discovery.revalidate_target_identity(handle)


def test_local_payload_limit_is_preserved(project):
    result = discover(project, request=project.request(limits=replace(AnalysisLimits(), payload_bytes=100))).result
    assert result.status == Status.REFUSED and result.reasons == ("target_discovery_payload_limit",)


def test_candidate_overflow_refuses_instead_of_sampling(project):
    project.write("voice.py", "def Speak():\n    pass\n" * 33)
    result = discover(project).result
    assert result.status == Status.REFUSED and result.reasons == ("target_candidate_limit",)
    assert result.target is None and result.candidates == ()


@pytest.mark.parametrize("resource,value", [("python_files", 1), ("source_bytes", 8), ("ast_nodes", 1), ("relationships", 1), ("file_bytes", 8), ("ast_nodes_per_file", 1)])
def test_shared_limits_refuse_without_partial_target(project, resource, value):
    if resource == "relationships":
        project.write("app/run.py", "import voice\nfrom voice import Speak\ndef Run():\n    Speak()\n")
    request = project.request(limits=replace(AnalysisLimits(), **{resource: value}))
    result = discover(project, "Speak", request=request).result
    assert result.status == Status.REFUSED and result.target is None
    assert request.budget.usage.exhausted or result.reasons[0].startswith("target_source_limit:")


def test_original_request_and_deadline_are_never_renewed(project, monkeypatch):
    now = [0.0]
    request = project.request(clock=lambda: now[0])
    handle = discover(project, request=request)
    assert handle.result.status == Status.EXACT
    before = dict(request.budget.usage.consumed)
    monkeypatch.setattr(AnalysisBudget, "__init__", lambda *a, **k: pytest.fail("fresh budget created"))
    monkeypatch.setattr(AnalysisRequest, "capture", lambda *a, **k: pytest.fail("fresh request captured"))
    same = discovery.revalidate_target_identity(handle)
    assert same == handle.result and handle.request is request
    assert dict(request.budget.usage.consumed)["python_files"] > before["python_files"]
    now[0] = 5.0
    refused = discovery.revalidate_target_identity(handle)
    assert refused.status == Status.REFUSED and refused.reasons == ("target_discovery_budget_exhausted:seconds",)


@pytest.mark.parametrize("phase", ["before", "read", "use"])
def test_cancellation_propagates(project, monkeypatch, phase):
    event = threading.Event()
    request = project.request(cancellation_event=event)
    if phase == "before":
        event.set()
    elif phase == "read":
        original = discovery.read_analysis_source

        def cancelled(*a, **k):
            result = original(*a, **k)
            event.set()
            return result

        monkeypatch.setattr(discovery, "read_analysis_source", cancelled)
    else:
        handle = discover(project, request=request)
        event.set()
    with pytest.raises(OperationCancelled):
        discovery.revalidate_target_identity(handle) if phase == "use" else discover(project, request=request)


@pytest.mark.parametrize("code", ["def broken(:\n", "\x00", "not python syntax\n"])
def test_unreadable_or_invalid_lookup_sources_refuse(project, code):
    project.write("voice.py", code)
    result = discover(project).result
    assert result.status == Status.REFUSED and result.target is None


def test_source_is_never_executed_and_case_is_preserved(project):
    project.write("Mixed.PY", "def sPeAk():\n    pass\nraise RuntimeError('MUST NOT EXECUTE')\n")
    handle = discover(project, "Mixed.PY::sPeAk")
    assert handle.result.status == Status.EXACT
    assert handle.result.target.definition.path == "Mixed.PY" and handle.result.target.qualified_name == "sPeAk"
    assert discovery.revalidate_target_identity(handle) == handle.result


def test_current_file_requires_explicit_fresh_provenance(project):
    request = project.request()
    excerpt = discovery.read_analysis_source(request, "app/run.py").excerpts[0]
    source = SourceLocation.from_excerpt(request.identity, excerpt)
    command = "In this file, what calls voice.py::Speak?"
    assert discovery.discover_target_identity(command, request).result.status == Status.UNRESOLVED
    handle = discovery.discover_target_identity(command, request, current_file=source)
    assert handle.result.status == Status.EXACT and set(handle.result.lookup_files) == {"voice.py", "app/run.py"}
    project.write("app/run.py", "def Changed():\n    pass\n")
    assert discovery.revalidate_target_identity(handle).status == Status.REFUSED


@pytest.mark.parametrize("field,value", [("status", "exact"), ("target", None), ("proof_dependencies", ()), ("policy", "unconditional-one-hop"), ("schema_version", "future")])
def test_discovery_contract_rejects_contradictory_metadata(project, field, value):
    result = discover(project).result
    with pytest.raises(ValueError):
        replace(result, **{field: value})
    with pytest.raises(FrozenInstanceError):
        result.target = None


def test_discovery_has_no_scope_or_publication_authority(project):
    handle = discover(project)
    assert handle.result.discovery_id.startswith("C3Target")
    assert not handle.result.publication_enabled and not handle.result.omission_enabled
    assert not hasattr(handle.result, "publication_eligible")
    assert discovery.revalidate_target_identity(discover(project, "Missing")).status == Status.REFUSED


@pytest.mark.parametrize("change", ["project", "source_digest", "candidate_source"])
def test_identity_snapshot_requires_consistent_project_and_provenance(project, change):
    result = discover(project).result
    assert isinstance(result, TargetIdentityResult)
    with pytest.raises(ValueError):
        if change == "project":
            replace(result, project=replace(result.project, authorization_revision=result.project.authorization_revision + 1))
        elif change == "source_digest":
            replace(result, proof_dependencies=(replace(result.proof_dependencies[0], digest="b" * 64),))
        else:
            target = replace(result.target, definition=replace(result.target.definition, source_id="not-the-source"))
            replace(result, target=target, candidates=(target,))
