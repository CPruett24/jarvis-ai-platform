"""Immutable C2 graph views and traversal results over canonical source records."""
from dataclasses import dataclass

from models.project_relationships import (
    AnalysisResult, RelationshipKind, Resolution, SymbolKind, _tuple,
)


@dataclass(frozen=True)
class GraphArc:
    relationship_id: str
    origin_id: str
    target_id: str


@dataclass(frozen=True)
class RelationshipGraph:
    analysis: AnalysisResult
    kind: RelationshipKind
    node_ids: tuple[str, ...]
    arcs: tuple[GraphArc, ...]
    boundary_ids: tuple[str, ...]

    def __post_init__(self):
        if not isinstance(self.analysis, AnalysisResult) or not isinstance(self.kind, RelationshipKind):
            raise ValueError("A graph requires a canonical analysis and relationship kind.")
        nodes = _tuple(self, "node_ids", str)
        arcs = _tuple(self, "arcs", GraphArc)
        boundaries = _tuple(self, "boundary_ids", str)
        symbols = {s.symbol_id: s for s in self.analysis.symbols}
        records = {r.relationship_id: r for r in self.analysis.relationships if r.kind == self.kind}
        modules = {s.definition.path: s.symbol_id for s in self.analysis.symbols if s.kind == SymbolKind.MODULE}
        expected_nodes = set(modules.values()) if self.kind == RelationshipKind.IMPORTS else set(symbols)
        if len(set(nodes)) != len(nodes) or set(nodes) != expected_nodes:
            raise ValueError("Graph nodes must be the canonical symbols for its view.")
        expected = {}
        for identity, record in records.items():
            if record.resolution != Resolution.CONFIRMED_STATIC:
                continue
            origin, target = record.origin.symbol_id, record.target.symbol_id
            if self.kind == RelationshipKind.IMPORTS:
                origin = modules.get(record.origin.definition.path)
                target = modules.get(record.target.definition.path)
            if origin not in expected_nodes or target not in expected_nodes:
                raise ValueError("Import graphs require canonical module records for both files.")
            expected[identity] = GraphArc(identity, origin, target)
        if len({a.relationship_id for a in arcs}) != len(arcs) or {a.relationship_id: a for a in arcs} != expected:
            raise ValueError("Graph arcs must exactly preserve the confirmed canonical relationships.")
        uncertain = {identity for identity, r in records.items() if r.resolution != Resolution.CONFIRMED_STATIC}
        if len(set(boundaries)) != len(boundaries) or set(boundaries) != uncertain:
            raise ValueError("Uncertain relationships must remain explicit graph boundaries.")

    @property
    def snapshot_id(self):
        return self.analysis.snapshot.snapshot_id

    @property
    def publication_ready(self):
        # A retained snapshot is never a durable freshness guarantee. Future
        # callers must use the explicit publication gate at the delivery boundary.
        return False


@dataclass(frozen=True)
class TraversalStep:
    node_id: str
    path: tuple[str, ...]
    relationship_path: tuple[str, ...]
    classification: str
    back_reference_path: tuple[str, ...] = ()

    def __post_init__(self):
        _tuple(self, "path", str)
        _tuple(self, "relationship_path", str)
        _tuple(self, "back_reference_path", str)
        if (self.classification not in {"root", "expanded", "cycle", "shared", "revisited", "depth_cutoff",
                                        "node_cutoff", "edge_cutoff"}
                or not self.path or self.path[-1] != self.node_id
                or len(self.relationship_path) != len(self.path) - 1):
            raise ValueError("Invalid traversal path or classification.")


@dataclass(frozen=True)
class GraphTraversal:
    graph: RelationshipGraph
    direction: str
    status: str
    root_ids: tuple[str, ...] = ()
    candidates: tuple[str, ...] = ()
    steps: tuple[TraversalStep, ...] = ()
    boundary_ids: tuple[str, ...] = ()
    cutoff_reasons: tuple[str, ...] = ()

    def __post_init__(self):
        if (not isinstance(self.graph, RelationshipGraph) or self.direction not in {"forward", "reverse"}
                or self.status not in {"resolved", "ambiguous", "not_found"}):
            raise ValueError("Invalid graph traversal outcome.")
        for name in ("root_ids", "candidates", "boundary_ids", "cutoff_reasons"):
            _tuple(self, name, str)
        _tuple(self, "steps", TraversalStep)
        nodes, arcs = set(self.graph.node_ids), {a.relationship_id: a for a in self.graph.arcs}
        if not set(self.root_ids + self.candidates) <= nodes or not set(self.boundary_ids) <= set(self.graph.boundary_ids):
            raise ValueError("Traversal references unknown graph records.")
        if (self.status == "resolved" and not self.root_ids or self.status != "resolved" and self.root_ids
                or self.status == "ambiguous" and len(set(self.candidates)) < 2):
            raise ValueError("Target outcome is inconsistent.")
        previous_paths = set()
        for step in self.steps:
            if step.path[0] not in self.root_ids or not set(step.path) <= nodes:
                raise ValueError("Path is outside the selected roots/graph.")
            for index, identity in enumerate(step.relationship_path):
                arc = arcs.get(identity)
                if arc is None:
                    raise ValueError("Path includes a nonconfirmed edge.")
                pair = (arc.origin_id, arc.target_id) if self.direction == "forward" else (arc.target_id, arc.origin_id)
                if pair != step.path[index:index + 2]:
                    raise ValueError("Path direction or edge endpoints do not match.")
            if step.classification == "cycle" and step.node_id not in step.path[:-1]:
                raise ValueError("A shared descendant is not a path-local cycle.")
            if step.classification in {"cycle", "shared", "revisited"}:
                if (step.back_reference_path not in previous_paths
                        or step.back_reference_path[-1] != step.node_id):
                    raise ValueError("A back-reference must identify a previously recorded path to this node.")
            if step.classification == "shared" and step.node_id in step.path[:-1]:
                raise ValueError("A cycle cannot be classified as a shared descendant.")
            previous_paths.add(step.path)

    @property
    def complete(self):
        return (self.status == "resolved" and self.graph.analysis.snapshot.coverage.complete
                and not self.cutoff_reasons and not self.boundary_ids)

    @property
    def publication_ready(self):
        return False


@dataclass(frozen=True)
class ImpactConnection:
    symbol_id: str
    root_id: str
    relationship_path: tuple[str, ...]

    def __post_init__(self):
        _tuple(self, "relationship_path", str)


@dataclass(frozen=True)
class PotentialImpact:
    traversal: GraphTraversal
    affected: tuple[ImpactConnection, ...]
    interpretation: str = "Potentially affected through confirmed static relationships; runtime breakage is not established."

    def __post_init__(self):
        if not isinstance(self.traversal, GraphTraversal) or self.traversal.direction != "reverse":
            raise ValueError("Potential impact requires a reverse traversal.")
        _tuple(self, "affected", ImpactConnection)
        paths = {(s.node_id, s.path[0], s.relationship_path) for s in self.traversal.steps}
        if any((a.symbol_id, a.root_id, a.relationship_path) not in paths
               or a.symbol_id in self.traversal.root_ids for a in self.affected):
            raise ValueError("Affected symbols require a confirmed supporting reverse path.")

    @property
    def kind(self):
        return self.traversal.graph.kind

    @property
    def complete(self):
        return self.traversal.complete

    @property
    def publication_ready(self):
        return False


@dataclass(frozen=True)
class FreshnessCheck:
    snapshot_id: str
    state: str
    reasons: tuple[str, ...] = ()

    def __post_init__(self):
        _tuple(self, "reasons", str)
        if self.state not in {"verified", "stale", "unverified", "cancelled"}:
            raise ValueError("Unknown freshness state.")
        if self.state == "verified" and self.reasons:
            raise ValueError("Verified freshness cannot carry failures.")

    @property
    def verified(self):
        return self.state == "verified"
