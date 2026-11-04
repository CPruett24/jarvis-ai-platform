"""Inactive C3.6a contracts on disposable identities; never execute source code."""
from dataclasses import FrozenInstanceError, asdict, replace
import os
from types import SimpleNamespace

import pytest

from models.dependency_disposition import (
    C3_DEPENDENCY_SCHEMA, DependencyCheck, DependencyDecision, DependencyDisposition,
    DependencyPlan, DependencyPolicy, MAX_PROOF_SOURCES,
)
from models.project_relationships import ProjectIdentity, RelationshipKind, SourceLocation, SymbolKind, SymbolRecord
from models.project_scope import AnalysisScope, C3_ANALYSIS_POLICY, QuerySemantics, ScopeKind, SupportClosure


@pytest.fixture
def declared(tmp_path):
    project = ProjectIdentity("contracts", os.path.normcase(str(tmp_path.resolve())), 1)

    def source(path, **changes):
        return replace(SourceLocation(project, path, "S:" + path, "a" * 64, 1, 4), **changes)

    voice, search = source("voice.py"), source("app/run.py")
    scope = AnalysisScope(project, ScopeKind.FILES, (search.path,), (search.path,),
        SupportClosure(project, (voice.path,), (voice,), True, 1),
        SymbolRecord("Speak", SymbolKind.FUNCTION, replace(voice, start_line=2, end_line=3)),
        RelationshipKind.CALLS, "reverse", QuerySemantics.DIRECT)

    def decision(disposition=DependencyDisposition.REQUIRED, **changes):
        return replace(DependencyDecision(project, scope.scope_id, voice.path, disposition,
            (search,) if disposition == DependencyDisposition.PROVEN_IRRELEVANT else (),
            tuple(DependencyCheck) if disposition == DependencyDisposition.PROVEN_IRRELEVANT else ()), **changes)

    def plan(disposition=DependencyDisposition.REQUIRED, **changes):
        return replace(DependencyPlan(scope, (decision(disposition),), (voice, search), True), **changes)

    return SimpleNamespace(project=project, source=source, voice=voice, search=search,
                           scope=scope, decision=decision, plan=plan)


@pytest.mark.parametrize("disposition", list(DependencyDisposition))
def test_typed_dispositions_never_enable_omission(declared, disposition):
    decision = declared.decision(disposition)
    plan = DependencyPlan(declared.scope, (decision,), (declared.voice, declared.search))
    assert plan.active_support_files == ("voice.py",)
    assert plan.support_budget_files == ("voice.py",)
    assert not plan.omission_enabled and not plan.publication_enabled
    assert decision.disposition == disposition
    if disposition == DependencyDisposition.UNKNOWN:
        with pytest.raises(ValueError, match="Complete support"):
            replace(plan, complete=True)
    else:
        assert replace(plan, complete=True).complete


def test_unknown_can_describe_incomplete_unread_support(declared):
    scope = replace(declared.scope, support=replace(declared.scope.support, sources=(), closed=False))
    plan = DependencyPlan(scope, (declared.decision(DependencyDisposition.UNKNOWN),))
    assert not plan.complete and plan.active_support_files == ("voice.py",)
    assert plan.support_budget_files == ("voice.py",)
    assert not scope.support.complete


@pytest.mark.parametrize("disposition", [DependencyDisposition.UNKNOWN, DependencyDisposition.REQUIRED])
@pytest.mark.parametrize("field", ["proof_sources", "checks"])
def test_non_irrelevant_states_cannot_carry_irrelevance_certificate(declared, disposition, field):
    value = (declared.search,) if field == "proof_sources" else tuple(DependencyCheck)
    with pytest.raises(ValueError):
        declared.decision(disposition, **{field: value})


@pytest.mark.parametrize("change", [
    {"proof_sources": ()}, {"checks": ()}, {"checks": (DependencyCheck.BINDING,)},
    {"checks": (DependencyCheck.BINDING,) * 4}, {"checks": ("binding",)},
    {"disposition": "proven_irrelevant"}, {"disposition": None},
])
def test_irrelevance_requires_all_four_checks_and_provenance(declared, change):
    with pytest.raises(ValueError):
        replace(declared.decision(DependencyDisposition.PROVEN_IRRELEVANT), **change)


@pytest.mark.parametrize("changes", [
    {"version": 2}, {"version": True}, {"name": "target-aware"},
    {"schema_version": "c3.dependency-dispositions.v2"},
])
def test_unsupported_policy_versions_are_rejected(changes):
    with pytest.raises(ValueError):
        DependencyPolicy(**changes)


def test_policy_identity_is_separate_from_existing_scope_identity(declared):
    before, identity = asdict(declared.scope), declared.scope.scope_id
    first, second = declared.plan(), declared.plan(DependencyDisposition.PROVEN_IRRELEVANT)
    assert first.policy.policy_id == second.policy.policy_id
    assert first.policy.schema_version == C3_DEPENDENCY_SCHEMA
    assert first.plan_id != second.plan_id
    assert declared.scope.analysis_policy == C3_ANALYSIS_POLICY
    assert declared.scope.scope_id == identity and asdict(declared.scope) == before
    assert first.scope is declared.scope and first.active_support_files == second.active_support_files


@pytest.mark.parametrize("field", ["decision", "plan"])
def test_nested_policy_mismatch_is_revalidated(declared, field):
    policy = DependencyPolicy()
    object.__setattr__(policy, "version", 2)
    with pytest.raises(ValueError):
        if field == "decision":
            declared.decision(policy=policy)
        else:
            declared.plan(policy=policy)


@pytest.mark.parametrize("conflicting", [False, True])
def test_duplicate_or_conflicting_decisions_rejected(declared, conflicting):
    first = declared.decision()
    second = declared.decision(DependencyDisposition.PROVEN_IRRELEVANT) if conflicting else first
    with pytest.raises(ValueError):
        declared.plan(decisions=(first, second))


@pytest.mark.parametrize("change", ["case", "digest", "source_id", "duplicate"])
def test_duplicate_or_conflicting_proof_identities_rejected(declared, change):
    source = declared.voice
    other = replace(source, **({"path": "VOICE.py"} if change == "case" else
        {"digest": "b" * 64} if change == "digest" else {"source_id": "different"} if change == "source_id" else {}))
    with pytest.raises(ValueError):
        declared.plan(proof_dependencies=(source, other))


@pytest.mark.parametrize("path", ["app/RUN.py", "VOICE.py"])
def test_proof_sources_cannot_case_alias_scope_roles(declared, path):
    with pytest.raises(ValueError):
        declared.plan(proof_dependencies=(declared.voice, declared.source(path)))


@pytest.mark.parametrize("scope_id", ["", "c3.scope.v1", "C3S" + "0" * 63])
def test_evidence_requires_a_canonical_scope_identity(declared, scope_id):
    with pytest.raises(ValueError):
        declared.decision(scope_id=scope_id)


@pytest.mark.parametrize("change", ["project", "revision", "root"])
@pytest.mark.parametrize("field", ["decision", "proof", "certificate"])
def test_cross_project_and_revision_dependencies_rejected(declared, change, field):
    project = replace(declared.project, **({"project_id": "other"} if change == "project" else
        {"authorization_revision": 2} if change == "revision" else {"root_identity": declared.project.root_identity + "-other"}))
    with pytest.raises(ValueError):
        if field == "decision":
            declared.plan(decisions=(declared.decision(project=project),))
        elif field == "proof":
            declared.plan(proof_dependencies=(replace(declared.voice, project=project),))
        else:
            declared.decision(DependencyDisposition.PROVEN_IRRELEVANT,
                              proof_sources=(replace(declared.search, project=project),))


@pytest.mark.parametrize("field", ["scope", "target_source", "certificate_digest", "source_identity", "range"])
def test_inconsistent_evidence_context_and_provenance_rejected(declared, field):
    with pytest.raises(ValueError):
        if field == "scope":
            declared.plan(decisions=(declared.decision(scope_id="C3S" + "0" * 64),))
        elif field == "target_source":
            declared.plan(proof_dependencies=(replace(declared.voice, digest="b" * 64),))
        elif field == "certificate_digest":
            decision = declared.decision(DependencyDisposition.PROVEN_IRRELEVANT,
                                        proof_sources=(replace(declared.search, digest="b" * 64),))
            declared.plan(decisions=(decision,))
        elif field == "source_identity":
            declared.plan(proof_dependencies=(declared.voice, replace(declared.search, source_id=declared.voice.source_id)))
        else:
            declared.plan(proof_dependencies=(replace(declared.voice, start_line=3),))


def test_missing_certificate_dependency_is_rejected_even_for_incomplete_plan(declared):
    decision = declared.decision(DependencyDisposition.PROVEN_IRRELEVANT)
    with pytest.raises(ValueError, match="Missing consulted"):
        DependencyPlan(declared.scope, (decision,), (declared.voice,))


@pytest.mark.parametrize("change", ["missing_source", "open_closure", "missing_decision", "unknown"])
def test_incomplete_support_cannot_claim_completeness(declared, change):
    with pytest.raises(ValueError):
        if change == "missing_source":
            declared.plan(proof_dependencies=(declared.search,))
        elif change == "open_closure":
            declared.plan(scope=replace(declared.scope, support=replace(declared.scope.support, closed=False)))
        elif change == "missing_decision":
            declared.plan(decisions=())
        else:
            declared.plan(decisions=(declared.decision(DependencyDisposition.UNKNOWN),))


def test_consulted_non_search_sources_count_even_when_not_active_support(declared):
    consulted = tuple(declared.source(f"checks/check{i}.py") for i in range(5))
    plan = declared.plan(proof_dependencies=(declared.voice, declared.search) + consulted)
    assert plan.active_support_files == ("voice.py",)
    assert len(plan.support_budget_files) == 6
    with pytest.raises(ValueError, match="ceiling"):
        replace(plan, proof_dependencies=plan.proof_dependencies + (declared.source("checks/seventh.py"),))


def test_irrelevance_evidence_sources_are_always_charged(declared):
    proof = declared.source("checks/independent.py")
    decision = declared.decision(DependencyDisposition.PROVEN_IRRELEVANT, proof_sources=(proof,))
    plan = declared.plan(decisions=(decision,), proof_dependencies=(declared.voice, proof))
    assert plan.support_budget_files == (proof.path, declared.voice.path)
    assert plan.active_support_files == (declared.voice.path,)


def test_six_active_dependencies_are_valid_without_omission(declared):
    sources = (declared.voice,) + tuple(declared.source(f"helpers/helper{i}.py") for i in range(5))
    scope = replace(declared.scope, support=SupportClosure(declared.project,
        tuple(source.path for source in sources), sources, True, 1))
    decisions = tuple(DependencyDecision(declared.project, scope.scope_id, source.path,
        DependencyDisposition.REQUIRED) for source in sources)
    plan = DependencyPlan(scope, decisions, sources, complete=True)
    assert len(plan.active_support_files) == len(plan.support_budget_files) == 6
    assert not plan.omission_enabled


@pytest.mark.parametrize("value", ["voice.py", {"voice.py": True}, (None,)])
def test_untyped_collections_rejected(declared, value):
    with pytest.raises(ValueError):
        declared.plan(proof_dependencies=value)


@pytest.mark.parametrize("path", ["../other.py", "./voice.py", "voice\\other.py", "C:/voice.py", "a*.py", "voice.txt"])
def test_noncanonical_dependency_paths_rejected(declared, path):
    with pytest.raises(ValueError):
        declared.decision(path=path)


def test_collection_and_payload_bounds(declared):
    with pytest.raises(ValueError):
        declared.plan(decisions=(declared.decision(),) * 7)
    with pytest.raises(ValueError):
        declared.plan(proof_dependencies=tuple(declared.source(f"proof{i}.py") for i in range(MAX_PROOF_SOURCES + 1)))
    with pytest.raises(ValueError, match="payload"):
        source = replace(declared.search, source_id="S" * (24 * 1024))
        declared.plan(proof_dependencies=(declared.voice, source))


def test_order_independence_immutability_and_fingerprint_sensitive_identity(declared):
    sources = [declared.voice, declared.search, declared.source("checks/unused.py")]
    plan = declared.plan(proof_dependencies=sources)
    sources.clear()
    assert plan.plan_id == replace(plan, proof_dependencies=list(reversed(plan.proof_dependencies))).plan_id
    changed = replace(plan, proof_dependencies=tuple(
        replace(source, digest="b" * 64) if source.path == "checks/unused.py" else source
        for source in plan.proof_dependencies))
    assert plan.plan_id != changed.plan_id and plan.scope.scope_id == changed.scope.scope_id
    with pytest.raises(FrozenInstanceError):
        plan.complete = False


def test_contract_cannot_be_used_as_existing_validation_or_scope_certificate(declared):
    from models.scoped_validation import ScopedCallerEvidence, ScopedValidationOutcome
    plan = declared.plan(DependencyDisposition.PROVEN_IRRELEVANT)
    with pytest.raises(ValueError):
        replace(declared.scope, support=plan)
    assert not isinstance(plan, (ScopedCallerEvidence, ScopedValidationOutcome))
    assert not getattr(plan, "publication_eligible", False)
    assert declared.scope.support.complete and not plan.publication_enabled


def test_existing_pipeline_keeps_unconditional_support_and_does_not_use_new_contract(tmp_path, monkeypatch):
    from services import project_access as access
    from services.project_analysis_request import AnalysisRequest
    from services.scoped_relationship_answer import prepare_scoped_caller_answer
    monkeypatch.setattr(access, "_projects", access._projects.copy())
    monkeypatch.setattr(access, "_revision", access._revision)
    monkeypatch.setattr(access, "_active", access._active)
    access.register_project("contract-compatibility", tmp_path)
    access.select_project("contract-compatibility")
    (tmp_path / "app").mkdir()
    (tmp_path / "app/run.py").write_text(
        "from voice import Speak\nfrom unused import Other\ndef run():\n    Speak()\n", encoding="utf-8")
    (tmp_path / "voice.py").write_text(
        "def Speak():\n    pass\nraise RuntimeError('must never execute')\n", encoding="utf-8")
    (tmp_path / "unused.py").write_text("def Other():\n    pass\n", encoding="utf-8")
    monkeypatch.setattr(DependencyPlan, "__post_init__", lambda *a: pytest.fail("inactive contract used by live planning"))
    result = prepare_scoped_caller_answer("Within app, what calls voice.py::Speak?", AnalysisRequest.capture())
    assert result.status == "complete", result.reasons
    assert result.scope.support.required_files == ("unused.py", "voice.py")
    assert result.validation.publication_eligible
