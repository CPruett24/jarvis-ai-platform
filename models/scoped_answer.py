"""C3.5a internal request/answer contracts, deliberately not capability responses."""
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.scoped_relationship_analysis import ScopedCallerAnalysis

from models.project_scope import AnalysisScope, ScopeKind, CompletenessClaim
from models.project_relationships import RelationshipRecord
from models.scoped_validation import ScopedValidationOutcome


@dataclass(frozen=True)
class ScopedCallerIntent:
    qualified_name: str | None = None
    filename: str | None = None
    project_qualifier: str | None = None
    scope_kind: ScopeKind | None = None
    scope_path: str | None = None
    current_file: bool = False
    direct: bool = True
    error: str = ""
    findings_only: bool = False


@dataclass(frozen=True)
class CallerSourceReference:
    relationship_id: str
    source_id: str
    path: str
    start_line: int
    end_line: int


@dataclass(frozen=True)
class ScopedCallerAnswerCandidate:
    status: str
    text: str
    intent: ScopedCallerIntent | None = None
    scope: AnalysisScope | None = None
    validation: ScopedValidationOutcome | None = None
    relationships: tuple[RelationshipRecord, ...] = ()
    references: tuple[CallerSourceReference, ...] = ()
    reasons: tuple[str, ...] = ()
    target_options: tuple[str, ...] = ()
    analysis: "ScopedCallerAnalysis | None" = None

    def __post_init__(self):
        if self.status not in {"not_applicable", "clarification", "refused", "findings_only", "complete"}:
            raise ValueError("Unknown internal C3 answer state.")
        if self.status in {"findings_only", "complete"}:
            if (self.scope is None or self.validation is None or not self.validation.publication_eligible
                    or self.validation.scope_id != self.scope.scope_id or not self.text
                    or {edge.relationship_id for edge in self.relationships} !=
                       set(self.validation.evidence.relationship_ids)):
                raise ValueError("Factual candidates require matching validated scope/evidence.")
            findings = self.validation.claim == CompletenessClaim.FINDINGS_ONLY
            if findings != (self.status == "findings_only") or findings and not self.relationships:
                raise ValueError("Answer status must preserve validated claim mode.")
            if {ref.relationship_id for ref in self.references} != {r.relationship_id for r in self.relationships}:
                raise ValueError("Each relationship requires source references.")
            excerpts = {e.source_id: e for e in self.validation.evidence.excerpts}
            for ref in self.references:
                source = excerpts.get(ref.source_id)
                if source is None or (ref.path, ref.start_line, ref.end_line) != (
                        source.path, source.start_line, source.end_line):
                    raise ValueError("Answer references must match validated source windows.")
        elif self.relationships or self.references:
            raise ValueError("Clarifications/refusals cannot contain relationship facts.")

    @property
    def publication_enabled(self):
        return False

    @property
    def defer_to_c2(self):
        return self.status == "not_applicable"
