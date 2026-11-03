"""C2 answer contracts: canonical records stay separate from selected source windows."""
from dataclasses import dataclass

from models.project_relationships import AnalysisResult, SourceLocation, _tuple, stable_id
from models.project_graph import RelationshipGraph, GraphTraversal, PotentialImpact
from models.source_evidence import SourceExcerpt


def excerpt_identity(snapshot_id, path, start, end, digest):
    return stable_id("S", [snapshot_id, path, start, end, digest])


@dataclass(frozen=True)
class EvidenceSupport:
    relationship_id: str | None
    symbol_id: str | None
    role: str
    canonical: SourceLocation
    start_line: int
    end_line: int
    excerpt_id: str

    def __post_init__(self):
        if (not isinstance(self.canonical, SourceLocation) or self.role not in {"site", "binding", "header"}
                or type(self.start_line) is not int or type(self.end_line) is not int
                or not self.canonical.start_line <= self.start_line <= self.end_line <= self.canonical.end_line):
            raise ValueError("Invalid source-support range or role.")
        if self.role != "header" and (self.start_line, self.end_line) != (
                self.canonical.start_line, self.canonical.end_line):
            raise ValueError("Call/import sites and bindings cannot be narrowed.")
        if self.role == "header" and self.start_line != self.canonical.start_line:
            raise ValueError("Definition headers must start at their canonical definition.")


@dataclass(frozen=True)
class ApprovedProposition:
    proposition_id: str
    kind: str
    relationship_ids: tuple[str, ...]
    symbol_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    text: str

    def __post_init__(self):
        for name in ("relationship_ids", "symbol_ids", "source_ids"):
            _tuple(self, name, str)


@dataclass(frozen=True)
class RelationshipEvidence:
    analysis: AnalysisResult
    value: RelationshipGraph | GraphTraversal | PotentialImpact
    snapshot_id: str
    relationship_ids: tuple[str, ...]
    excerpts: tuple[SourceExcerpt, ...]
    supports: tuple[EvidenceSupport, ...]
    propositions: tuple[ApprovedProposition, ...]

    def __post_init__(self):
        if not isinstance(self.analysis, AnalysisResult) or self.snapshot_id != self.analysis.snapshot.snapshot_id:
            raise ValueError("Evidence must retain its canonical snapshot identity.")
        if not isinstance(self.value, (RelationshipGraph, GraphTraversal, PotentialImpact)):
            raise ValueError("Expected a canonical graph result.")
        for name, kind in (("relationship_ids", str), ("excerpts", SourceExcerpt),
                           ("supports", EvidenceSupport), ("propositions", ApprovedProposition)):
            _tuple(self, name, kind)
        if len({p.proposition_id for p in self.propositions}) != len(self.propositions):
            raise ValueError("Approved proposition identities must be unique.")
        for excerpt in self.excerpts:
            if (not isinstance(excerpt.signature, tuple) or any(type(v) is not int for v in excerpt.signature)
                    or any(not isinstance(getattr(excerpt, name), str) for name in (
                        "text", "path", "source_id", "digest", "project_id", "retrieved_at", "kind"))):
                raise ValueError("Source metadata must remain immutable typed values.")


@dataclass(frozen=True)
class RelationshipAnswer:
    success: bool
    text: str
    status: str
    snapshot_id: str
    used_model_order: bool = False
