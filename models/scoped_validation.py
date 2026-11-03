"""Internal C3 eligibility certificates. These never authorize delivery."""
from dataclasses import dataclass

from models.project_scope import CompletenessClaim
from models.project_relationships import SourceFingerprint
from models.relationship_answer import EvidenceSupport
from models.source_evidence import SourceExcerpt


@dataclass(frozen=True)
class ScopedCallerEvidence:
    scope_id: str
    claim: CompletenessClaim
    relationship_ids: tuple[str, ...]
    # All source dependencies, including sources not selected for display.
    proof_dependencies: tuple[SourceFingerprint, ...]
    source_inventory: tuple[str, ...]
    inventory_exclusions: tuple[tuple[str, str], ...]
    excerpts: tuple[SourceExcerpt, ...]
    supports: tuple[EvidenceSupport, ...]


@dataclass(frozen=True)
class ScopedValidationOutcome:
    scope_id: str
    claim: CompletenessClaim | None
    evidence_status: str = "unverified"
    freshness_status: str = "unverified"
    authorization_status: str = "unverified"
    completeness_status: str = "unverified"
    refusal_reasons: tuple[str, ...] = ()
    publication_eligible: bool = False
    evidence: ScopedCallerEvidence | None = None

    def __post_init__(self):
        if self.publication_eligible and (
                self.claim not in {CompletenessClaim.FINDINGS_ONLY, CompletenessClaim.SCOPED_COMPLETE,
                                   CompletenessClaim.PROJECT_COMPLETE}
                or self.evidence_status != "verified" or self.freshness_status != "verified"
                or self.authorization_status != "verified" or self.refusal_reasons
                or self.evidence is None or self.evidence.scope_id != self.scope_id
                or self.evidence.claim != self.claim
                or self.completeness_status != ("not_claimed" if self.claim == CompletenessClaim.FINDINGS_ONLY
                                                else "complete")):
            raise ValueError("Eligibility requires separate evidence, freshness and authorization checks.")

    @property
    def publication_enabled(self):
        return False

    @property
    def claim_qualification(self):
        if not self.publication_eligible:
            return "No validated claim."
        if self.claim == CompletenessClaim.FINDINGS_ONLY:
            return "Verified direct static findings only; additional callers may exist."
        return "Complete direct static caller list within the declared Python scope and policy."
