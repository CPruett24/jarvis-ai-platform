"""C3.4 disposable authorized source fixtures; never import fixture code."""
import ast
import copy
from dataclasses import replace
import os
import threading

import pytest

from models.project_scope import (
    AnalysisScope, SupportClosure, ScopeKind, QuerySemantics, CompletenessClaim,
    EvidenceSelection, CoverageStatus,
)
from models.project_relationships import RelationshipKind, Resolution
from services import project_access as access
from services import scoped_relationship_validation as validation
from services.scoped_relationship_analysis import analyze_scoped_callers
from services.project_analysis_cache import read_analysis_source
from services.project_analysis_request import AnalysisRequest, AnalysisLimits
from services.project_symbol_index import extract_scoped_symbols
from models.project_relationships import SourceLocation

FINDINGS = CompletenessClaim.FINDINGS_ONLY
COMPLETE = CompletenessClaim.SCOPED_COMPLETE


@pytest.fixture
def project(tmp_path):
    previous = access._projects.copy(), access._active, access._revision
    access.register_project("validation", tmp_path)
    access.select_project("validation")

    def write(path, text):
        file = tmp_path / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text, encoding="utf-8", newline="\n")
        return file

    write("voice.py", "def Speak():\n    pass\n")
    write("app/run.py", "from voice import Speak\ndef run():\n    Speak()\n")

    def analyze(search=("app/run.py",), support=("voice.py",), kind=ScopeKind.FILES,
                roots=None, target_path="voice.py", target_name="Speak", limits=None, event=None,
                clock=lambda: 0, exclusions=()):
        declaration = AnalysisRequest.capture(clock=lambda: 0)
        read = read_analysis_source(declaration, target_path)
        assert read.success and read.excerpts, (read.status, read.error, read.limits_reached)
        source = read.excerpts[0]
        module = extract_scoped_symbols(ast.parse(source.text), source, declaration)
        target = next(s.symbol for s in module.scopes if s.symbol.qualified_name == target_name)
        sources = tuple(SourceLocation.from_excerpt(declaration.identity,
            read_analysis_source(declaration, path).excerpts[0]) for path in support)
        roots = roots if roots is not None else search if kind == ScopeKind.FILES else ("app",) if kind == ScopeKind.DIRECTORY else ()
        scope = AnalysisScope(declaration.identity, kind, roots, search,
            SupportClosure(declaration.identity, support, sources, True, 1 if support else 0),
            target, RelationshipKind.CALLS, "reverse", QuerySemantics.DIRECT, excluded_paths=exclusions)
        request = AnalysisRequest.capture(limits=limits, cancellation_event=event, clock=clock)
        candidate = analyze_scoped_callers(scope, request)
        return scope, request, candidate

    yield write, analyze, tmp_path
    access._projects, access._active, access._revision = previous


def check(scope, request, candidate, **kwargs):
    return validation.validate_scoped_callers(candidate, scope, request, **kwargs)


@pytest.mark.parametrize("claim", [FINDINGS, COMPLETE])
def test_real_caller_is_independently_verified_without_delivery(project, monkeypatch, claim):
    _, analyze, _ = project
    scope, request, candidate = analyze()
    # Validator cannot use the analyzer again or any presentation/action endpoint.
    import services.scoped_relationship_analysis as analyzer
    monkeypatch.setattr(analyzer, "analyze_scoped_callers", lambda *a, **k: pytest.fail("analyzer trusted"))
    from services import speaker, conversation_service, status_service
    from commands import router
    for owner, name in [(speaker, "speak"), (conversation_service, "add_message"),
                        (status_service, "update_status"), (router, "process")]:
        monkeypatch.setattr(owner, name, lambda *a, **k: pytest.fail("delivery side effect"))
    result = check(scope, request, candidate, claim=claim)
    assert result.publication_eligible, result.refusal_reasons
    assert not result.publication_enabled and not candidate.publication_ready
    assert result.evidence_status == result.authorization_status == result.freshness_status == "verified"
    assert result.completeness_status == ("not_claimed" if claim == FINDINGS else "complete")
    assert len(result.evidence.relationship_ids) == 1


@pytest.mark.parametrize("code,local", [
    ("from voice import Speak as say\ndef run():\n    say()\n", False),
    ("import voice as output\ndef run():\n    output.Speak()\n", False),
    ("import voice\ndef run():\n    voice.Speak()\n", False),
    ("def Speak():\n    pass\ndef run():\n    Speak()\n", True),
])
def test_alias_and_lexical_proofs(project, code, local):
    write, analyze, _ = project
    write("app/run.py", code)
    scope, request, candidate = analyze(target_path="app/run.py" if local else "voice.py", support=() if local else ("voice.py",))
    assert check(scope, request, candidate).publication_eligible


def test_findings_are_distinct_from_complete_scope(project):
    write, analyze, _ = project
    write("app/run.py", "from voice import Speak\ndef run(callback):\n    Speak()\n    callback()\n")
    scope, request, candidate = analyze()
    result = check(scope, request, candidate)
    assert result.publication_eligible and result.completeness_status == "not_claimed"
    assert "additional callers may exist" in result.claim_qualification
    refused = check(scope, request, candidate, claim=COMPLETE)
    assert not refused.publication_eligible
    assert "relevant_unresolved_boundaries" in refused.refusal_reasons


@pytest.mark.parametrize("code", [
    "from voice import Speak\ndef run(Speak):\n    Speak()\n",
    "from voice import Speak\nSpeak = None\ndef run():\n    Speak()\n",
    "if True:\n    from voice import Speak\ndef run():\n    Speak()\n",
    "def run(obj):\n    obj.Speak()\n",
    "def run(callback):\n    callback()\n",
    "from voice import Speak\nfrom other import Speak\ndef run():\n    Speak()\n",
])
def test_unsafe_bindings_cannot_be_promoted(project, code):
    write, analyze, _ = project
    _, _, genuine = analyze()
    write("app/run.py", code)
    scope, request, candidate = analyze()
    assert not check(scope, request, candidate).publication_eligible
    forged = copy.deepcopy(candidate)
    object.__setattr__(forged.result, "relationships", genuine.result.relationships)
    assert not check(scope, request, forged).publication_eligible


@pytest.mark.parametrize("code", [
    "if True:\n    def Speak():\n        pass\n",
    "def Speak():\n    pass\ndef Speak():\n    pass\n",
])
def test_conditional_and_duplicate_target(project, code):
    write, analyze, _ = project
    write("voice.py", code)
    scope, request, candidate = analyze()
    assert not check(scope, request, candidate).publication_eligible


def test_forged_verified_edge_with_current_fingerprints(project):
    write, analyze, _ = project
    write("app/run.py", "from voice import Speak\ndef run(Speak):\n    Speak()\n")
    scope, request, candidate = analyze()
    boundary, = candidate.boundaries
    edge = replace(boundary, target=scope.target, resolution=Resolution.CONFIRMED_STATIC,
                   reason="lexical_or_imported_binding")
    forged = replace(candidate, result=replace(candidate.result, relationships=(edge,),
                                               resolution=Resolution.CONFIRMED_STATIC))
    result = check(scope, request, forged)
    assert result.refusal_reasons == ("relationship_proof_mismatch_or_omission",)


def test_omitted_uncertain_boundary_does_not_prove_completeness(project):
    write, analyze, _ = project
    write("app/run.py", "from voice import Speak\ndef run(callback):\n    Speak()\n    callback()\n")
    scope, request, candidate = analyze()
    forged = replace(candidate, result=replace(candidate.result, relationships=candidate.verified_callers,
                                               resolution=Resolution.CONFIRMED_STATIC))
    assert not check(scope, request, forged, claim=COMPLETE).publication_eligible


@pytest.mark.parametrize("mutation", ["output.Speak = None", "setattr(output, 'Speak', None)"])
def test_cross_file_mutation_proof_dependency(project, mutation):
    write, analyze, _ = project
    write("app/patch.py", "import voice as output\n" + mutation + "\n")
    scope, request, candidate = analyze(search=("app/run.py", "app/patch.py"))
    assert not check(scope, request, candidate).publication_eligible


@pytest.mark.parametrize("field", ["location", "origin", "target", "support", "missing_edge", "missing_fingerprint", "scope", "coverage", "resolution"])
def test_forged_analyzer_metadata_is_not_proof(project, field):
    _, analyze, _ = project
    scope, request, candidate = analyze()
    forged = copy.deepcopy(candidate)
    edge = forged.result.relationships[0]
    if field == "location":
        object.__setattr__(edge, "location", replace(edge.location, start_line=2))
    elif field in {"origin", "target"}:
        object.__setattr__(edge, field, replace(getattr(edge, field), qualified_name="invented"))
    elif field == "support":
        object.__setattr__(edge, "supporting_sources", ())
    elif field == "missing_edge":
        object.__setattr__(forged.result, "relationships", ())
    elif field == "missing_fingerprint":
        object.__setattr__(forged, "fingerprints", forged.fingerprints[:1])
    elif field == "scope":
        object.__setattr__(forged.result.coverage.scope, "excluded_paths", ("app/run.py",))
    elif field == "coverage":
        object.__setattr__(forged.result.coverage, "parsed_files", ())
    elif field == "resolution":
        object.__setattr__(forged.result, "resolution", Resolution.UNRESOLVED)
    result = check(scope, request, forged, claim=COMPLETE)
    assert not result.publication_eligible


@pytest.mark.parametrize("field", ["text", "source_id", "support", "dependencies", "relationship_ids", "claim", "inventory"])
def test_fabricated_citations_and_packets(project, field):
    _, analyze, _ = project
    scope, request, candidate = analyze()
    packet = validation.collect_scoped_caller_evidence(candidate, scope, request)
    if field == "text":
        packet = replace(packet, excerpts=(replace(packet.excerpts[0], text="fake\n" * (packet.excerpts[0].end_line-packet.excerpts[0].start_line) + "fake"),) + packet.excerpts[1:])
    elif field == "source_id":
        packet = replace(packet, excerpts=(replace(packet.excerpts[0], source_id="invented"),) + packet.excerpts[1:])
    elif field == "support":
        packet = replace(packet, supports=())
    elif field == "dependencies":
        packet = replace(packet, proof_dependencies=())
    elif field == "relationship_ids":
        packet = replace(packet, relationship_ids=())
    elif field == "claim":
        packet = replace(packet, claim=COMPLETE)
    elif field == "inventory":
        packet = replace(packet, source_inventory=())
    result = check(scope, request, candidate, evidence=packet)
    assert not result.publication_eligible


def test_collected_packet_can_be_revalidated(project):
    _, analyze, _ = project
    scope, request, candidate = analyze()
    packet = validation.collect_scoped_caller_evidence(candidate, scope, request)
    assert check(scope, request, candidate, evidence=packet).publication_eligible


def test_same_name_is_not_exact_target_and_support_is_not_search(project):
    write, analyze, _ = project
    write("other.py", "def Speak():\n    pass\n")
    write("voice.py", "def Speak():\n    pass\ndef support_caller():\n    Speak()\n")
    write("app/run.py", "from other import Speak\ndef run():\n    Speak()\n")
    scope, request, candidate = analyze(support=("voice.py", "other.py"))
    result = check(scope, request, candidate, claim=COMPLETE)
    assert result.publication_eligible, result.refusal_reasons
    assert result.evidence.relationship_ids == ()
    assert not check(scope, request, candidate).publication_eligible


@pytest.mark.parametrize("change", ["new_caller", "same_size", "support", "alternative", "excluded_link"])
def test_changes_since_analysis_fail_closed(project, change):
    write, analyze, root = project
    scope, request, candidate = analyze(kind=ScopeKind.DIRECTORY)
    if change == "new_caller":
        write("app/new.py", "from voice import Speak\nSpeak()\n")
    elif change == "same_size":
        file = root / "app/run.py"
        before = file.stat()
        write("app/run.py", file.read_text().replace("Speak()", "Other()"))
        os.utime(file, ns=(before.st_atime_ns, before.st_mtime_ns))
    elif change == "support":
        write("voice.py", "def Speak():\n    return 1\n")
    elif change == "alternative":
        write("voice/__init__.py", "def Speak():\n    pass\n")
    else:
        try:
            (root / "app/link.py").symlink_to(root / "voice.py")
        except OSError:
            pytest.skip("Windows token cannot create symlinks")
    assert not check(scope, request, candidate).publication_eligible


def test_all_alternative_candidates_must_be_proven(project):
    write, analyze, _ = project
    write("voice/__init__.py", "def Speak():\n    pass\n")
    scope, request, candidate = analyze()
    assert not check(scope, request, candidate).publication_eligible
    scope, request, candidate = analyze(support=("voice.py", "voice/__init__.py"))
    assert not check(scope, request, candidate, claim=COMPLETE).publication_eligible


@pytest.mark.parametrize("change", ["revoke", "revision", "switch"])
def test_authorization_is_current(project, change):
    _, analyze, root = project
    scope, request, candidate = analyze()
    if change == "revoke":
        access.revoke_project("validation")
    elif change == "revision":
        access.register_project("validation", root)
    else:
        access.select_project("jarvis")
    result = check(scope, request, candidate)
    assert not result.publication_eligible and result.authorization_status == "refused"


@pytest.mark.parametrize("stage", ["cancel", "deadline", "reservation"])
def test_cancellation_and_original_deadline(project, stage):
    _, analyze, _ = project
    event = threading.Event()
    now = [0]
    scope, request, candidate = analyze(event=event, clock=lambda: now[0])
    if stage == "cancel":
        event.set()
    elif stage == "deadline":
        now[0] = 5
    else:
        now[0] = 4.99
    result = check(scope, request, candidate)
    assert not result.publication_eligible
    assert any(word in result.refusal_reasons[0] for word in ("cancelled", "seconds", "reservation"))


@pytest.mark.parametrize("resource,value", [("python_files", 3), ("source_bytes", 250), ("evidence_files", 1),
                                           ("evidence_excerpts", 1), ("payload_bytes", 50)])
def test_shared_resource_limits_fail_closed(project, resource, value):
    _, analyze, _ = project
    scope, request, candidate = analyze(limits=replace(AnalysisLimits(), **{resource: value}))
    result = check(scope, request, candidate)
    assert not result.publication_eligible
    assert result.refusal_reasons


def test_no_silent_evidence_truncation(project):
    write, analyze, _ = project
    code = "from voice import Speak\n" + "".join(f"def run{i}():\n    Speak()\n" for i in range(33))
    write("app/run.py", code)
    scope, request, candidate = analyze()
    assert len(candidate.verified_callers) == 33
    assert not check(scope, request, candidate).publication_eligible


def test_analysis_truncation_and_unsupported_claims(project):
    _, analyze, _ = project
    scope, request, candidate = analyze()
    forged = copy.deepcopy(candidate)
    object.__setattr__(forged.result, "evidence", EvidenceSelection.TRUNCATED)
    assert not check(scope, request, forged).publication_eligible
    for mode in (CompletenessClaim.NONE, "findings_only", CompletenessClaim.PROJECT_COMPLETE):
        assert not check(scope, request, candidate, claim=mode).publication_eligible


def test_empty_result_requires_independent_enumeration(project):
    write, analyze, _ = project
    write("app/run.py", "def run():\n    pass\n")
    scope, request, candidate = analyze()
    assert check(scope, request, candidate, claim=COMPLETE).publication_eligible
    assert not check(scope, request, candidate).publication_eligible
    write("app/new.py", "from voice import Speak\nSpeak()\n")
    assert not check(scope, request, candidate, claim=COMPLETE).publication_eligible


@pytest.mark.parametrize("change", ["source", "inventory", "authorization", "cancel", "deadline"])
def test_final_pass_detects_mid_validation_changes(project, monkeypatch, change):
    write, analyze, root = project
    event = threading.Event()
    now = [0]
    scope, request, candidate = analyze(event=event, clock=lambda: now[0])
    original = validation._select_evidence

    def select(*args):
        packet = original(*args)
        if change == "source":
            write("voice.py", "def Speak():\n    return 1\n")
        elif change == "inventory":
            write("voice/__init__.py", "def Speak():\n    pass\n")
        elif change == "authorization":
            access.register_project("validation", root)
        elif change == "cancel":
            event.set()
        else:
            now[0] = 5
        return packet

    monkeypatch.setattr(validation, "_select_evidence", select)
    assert not check(scope, request, candidate).publication_eligible


def test_project_complete_is_explicitly_scoped(project):
    write, analyze, _ = project
    write("app/run.py", "from voice import Speak\ndef run():\n    Speak()\n")
    scope, request, candidate = analyze(search=("app/run.py", "voice.py"), support=(), kind=ScopeKind.PROJECT_PYTHON)
    assert check(scope, request, candidate, claim=CompletenessClaim.PROJECT_COMPLETE).publication_eligible


def test_display_windows_are_not_full_proof_dependencies(project):
    write, analyze, _ = project
    write("app/run.py", "from voice import Speak\n" + "# padding\n" * 150 + "def run():\n    Speak()\n")
    scope, request, candidate = analyze()
    result = check(scope, request, candidate)
    assert result.publication_eligible
    assert any(excerpt.truncated for excerpt in result.evidence.excerpts)
    assert {f.path for f in result.evidence.proof_dependencies} == {"app/run.py", "voice.py"}
    assert sum(len(e.text) for e in result.evidence.excerpts) < 200


def test_omitted_verified_finding_is_refused_even_for_findings_only(project):
    write, analyze, _ = project
    write("app/run.py", "from voice import Speak\ndef first():\n    Speak()\ndef second():\n    Speak()\n")
    scope, request, candidate = analyze()
    forged = replace(candidate, result=replace(candidate.result, relationships=candidate.verified_callers[:1]))
    assert not check(scope, request, forged).publication_eligible


def test_undisplayed_proof_dependency_is_still_revalidated(project, monkeypatch):
    write, analyze, _ = project
    write("checks.py", "marker = 1\n")
    scope, request, candidate = analyze(support=("checks.py", "voice.py"))
    original = validation._select_evidence

    def select(*args):
        excerpts, supports = original(*args)
        assert "checks.py" not in {e.path for e in excerpts}
        write("checks.py", "marker = 2\n")
        return excerpts, supports

    monkeypatch.setattr(validation, "_select_evidence", select)
    result = check(scope, request, candidate)
    assert result.refusal_reasons == ("proof_dependency_changed:checks.py",)


def test_policy_excluded_python_prevents_complete_claim_but_not_proven_finding(project):
    write, analyze, _ = project
    write("app/secrets.py", "from voice import Speak\nSpeak()\n")
    scope, request, candidate = analyze(kind=ScopeKind.DIRECTORY)
    assert check(scope, request, candidate).publication_eligible
    assert not check(scope, request, candidate, claim=COMPLETE).publication_eligible


def test_fixture_source_is_never_executed(project):
    write, analyze, _ = project
    write("voice.py", "def Speak():\n    pass\nraise RuntimeError('source must not execute')\n")
    scope, request, candidate = analyze()
    assert check(scope, request, candidate).publication_eligible


def test_evidence_ranges_cannot_be_silently_cut(project):
    write, analyze, _ = project
    write("app/run.py", "from voice import Speak\ndef run():\n    Speak(\n" + "        0,\n" * 121 + "    )\n")
    scope, request, candidate = analyze()
    result = check(scope, request, candidate)
    assert not result.publication_eligible
    assert "evidence_range_limit" in result.refusal_reasons


def test_scope_cannot_be_replaced_by_search_support_role_change(project):
    _, analyze, _ = project
    scope, request, candidate = analyze()
    altered, _, _ = analyze(search=("app/run.py", "voice.py"), support=())
    assert not check(altered, request, candidate).publication_eligible


def test_actual_source_containment_is_checked_again(project, monkeypatch):
    _, analyze, _ = project
    scope, request, candidate = analyze()
    original = access._reject_links

    def changed(path):
        if str(path).endswith("voice.py"):
            raise access.ProjectAccessError("reparse point substituted")
        return original(path)

    monkeypatch.setattr(access, "_reject_links", changed)
    assert not check(scope, request, candidate).publication_eligible


@pytest.mark.parametrize("excluded_path", ["voice/__init__.py", "voice"])
def test_excluded_module_alternative_is_unknown_not_absent(project, monkeypatch, excluded_path):
    _, analyze, _ = project
    scope, request, candidate = analyze()
    excluded = ((excluded_path, "link_or_reparse_exclusion"),)
    forged = replace(candidate, inventory_exclusions=excluded)
    # Model a discovery-denied candidate without needing Windows link privileges.
    monkeypatch.setattr(validation, "_inventory", lambda *a: (candidate.source_inventory, excluded))
    result = check(scope, request, forged)
    assert not result.publication_eligible
    assert result.refusal_reasons == ("missing_module_candidate_dependency",)
