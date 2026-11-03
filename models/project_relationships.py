"""C2 data contracts only. Records describe static source, never runtime execution.

No filesystem access, extraction, resolution, persistence or model calls live here.
Completeness is relative to the recorded Python scope and exclusion policy.
"""
from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
import os
import re


ANALYZER_SCHEMA_VERSION = "c2.1"


def stable_id(kind, value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return kind + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _text(value):
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ValueError("Expected nonempty text without NUL.")


def _path(value):
    _text(value)
    if (value.startswith("/") or "\\" in value or ":" in value
            or any(part in {"", ".", ".."} for part in value.split("/"))):
        raise ValueError("Expected a canonical project-relative POSIX path.")


def _positive(value):
    if type(value) is not int or value < 1:
        raise ValueError("Expected a positive integer.")


def _digest(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("Expected a lowercase SHA-256 digest.")


def _tuple(record, name, item_type):
    value = getattr(record, name)
    if isinstance(value, (str, bytes, dict)):
        raise ValueError(f"Expected a collection for {name}.")
    items = tuple(value)
    if any(not isinstance(item, item_type) for item in items):
        raise ValueError(f"Invalid {name} item.")
    object.__setattr__(record, name, items)
    return items


@dataclass(frozen=True)
class ProjectIdentity:
    project_id: str
    root_identity: str
    authorization_revision: int

    def __post_init__(self):
        _text(self.project_id)
        _text(self.root_identity)
        if (not os.path.isabs(self.root_identity)
                or os.path.normcase(os.path.normpath(self.root_identity)) != self.root_identity):
            raise ValueError("Root identity must be a canonical absolute path.")
        _positive(self.authorization_revision)


@dataclass(frozen=True)
class SourceLocation:
    project: ProjectIdentity
    path: str
    source_id: str
    digest: str
    start_line: int
    end_line: int
    start_column: int = 0
    end_column: int = 0

    def __post_init__(self):
        if not isinstance(self.project, ProjectIdentity):
            raise ValueError("Source requires a project identity.")
        _path(self.path)
        _text(self.source_id)
        _digest(self.digest)
        _positive(self.start_line)
        _positive(self.end_line)
        if (self.end_line < self.start_line
                or any(type(v) is not int or v < 0 for v in (self.start_column, self.end_column))
                or (self.start_line == self.end_line and self.end_column < self.start_column)):
            raise ValueError("Invalid inclusive lines or zero-based column offsets.")

    @classmethod
    def from_excerpt(cls, project, excerpt):
        if (excerpt.project_id, excerpt.revision) != (project.project_id, project.authorization_revision):
            raise ValueError("Excerpt belongs to another project/revision.")
        return cls(project, excerpt.path, excerpt.source_id, excerpt.digest,
                   excerpt.start_line, excerpt.end_line)


class SymbolKind(str, Enum):
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    ASYNC_FUNCTION = "async_function"
    METHOD = "method"


@dataclass(frozen=True)
class SymbolRecord:
    qualified_name: str
    kind: SymbolKind
    definition: SourceLocation

    def __post_init__(self):
        _text(self.qualified_name)
        if not isinstance(self.kind, SymbolKind) or not isinstance(self.definition, SourceLocation):
            raise ValueError("Symbol requires a typed kind and definition.")

    @property
    def symbol_id(self):
        source = asdict(self.definition)
        # Definition identity is stable across unrelated edits to the file.
        del source["source_id"], source["digest"]
        return stable_id("Y", [source, self.qualified_name, self.kind.value])


class RelationshipKind(str, Enum):
    IMPORTS = "imports"
    CALLS = "calls"


class Resolution(str, Enum):
    CONFIRMED_STATIC = "confirmed_static"
    INFERRED = "inferred"
    UNRESOLVED = "unresolved"
    AMBIGUOUS = "ambiguous"
    INCOMPLETE = "incomplete"


@dataclass(frozen=True)
class RelationshipRecord:
    kind: RelationshipKind
    origin: SymbolRecord
    target: SymbolRecord | None
    expression: str
    location: SourceLocation
    resolution: Resolution
    reason: str
    candidates: tuple[SymbolRecord, ...] = ()
    supporting_sources: tuple[SourceLocation, ...] = ()

    def __post_init__(self):
        if (not isinstance(self.kind, RelationshipKind) or not isinstance(self.resolution, Resolution)
                or not isinstance(self.origin, SymbolRecord) or not isinstance(self.location, SourceLocation)
                or (self.target is not None and not isinstance(self.target, SymbolRecord))):
            raise ValueError("Relationship requires typed endpoints, location and classification.")
        _text(self.expression)
        _text(self.reason)
        candidates = _tuple(self, "candidates", SymbolRecord)
        sources = _tuple(self, "supporting_sources", SourceLocation)
        if (self.resolution == Resolution.CONFIRMED_STATIC and (self.target is None or candidates)
                or self.resolution in {Resolution.UNRESOLVED, Resolution.AMBIGUOUS, Resolution.INCOMPLETE}
                and self.target is not None
                or self.resolution == Resolution.AMBIGUOUS and len({s.symbol_id for s in candidates}) < 2
                or self.resolution == Resolution.UNRESOLVED and candidates):
            raise ValueError("Resolution does not match target/candidates.")
        origin = self.origin.definition
        if (self.location.project != origin.project or self.location.path != origin.path
                or self.location.digest != origin.digest
                or not origin.start_line <= self.location.start_line <= self.location.end_line <= origin.end_line):
            raise ValueError("Relationship site must belong to its origin definition snapshot.")
        endpoints = candidates + ((self.target,) if self.target else ())
        if any(s.definition.project != origin.project for s in endpoints) or any(
                s.project != origin.project for s in sources):
            raise ValueError("Cross-project or cross-revision relationship denied.")

    @property
    def relationship_id(self):
        value = asdict(self)
        for name in ("candidates", "supporting_sources"):
            value[name] = sorted(value[name], key=lambda item: json.dumps(item, sort_keys=True))
        return stable_id("R", value)


@dataclass(frozen=True)
class FileDiagnostic:
    path: str
    reason: str

    def __post_init__(self):
        _path(self.path)
        _text(self.reason)


@dataclass(frozen=True)
class AnalysisCoverage:
    discovered: tuple[str, ...] = ()
    parsed: tuple[str, ...] = ()
    excluded: tuple[FileDiagnostic, ...] = ()
    skipped: tuple[FileDiagnostic, ...] = ()
    parse_failures: tuple[FileDiagnostic, ...] = ()
    unsupported: tuple[FileDiagnostic, ...] = ()
    budget_exhausted: tuple[str, ...] = ()
    cancelled: bool = False
    discovery_complete: bool = False

    def __post_init__(self):
        for name in ("discovered", "parsed", "budget_exhausted"):
            for value in _tuple(self, name, str):
                _text(value)
        for path in self.discovered + self.parsed:
            _path(path)
        if any(not path.lower().endswith(".py") for path in self.parsed):
            raise ValueError("C2 currently parses Python source only.")
        outcomes = list(self.parsed)
        for name in ("excluded", "skipped", "parse_failures", "unsupported"):
            outcomes.extend(item.path for item in _tuple(self, name, FileDiagnostic))
        if (len(set(self.discovered)) != len(self.discovered) or len(set(outcomes)) != len(outcomes)
                or not set(outcomes) <= set(self.discovered)
                or type(self.cancelled) is not bool or type(self.discovery_complete) is not bool):
            raise ValueError("Coverage outcomes must be disjoint and belong to discovery.")

    @property
    def complete(self):
        # Explicit policy exclusions are outside the declared analysis scope.
        accounted = set(self.parsed) | {item.path for item in self.excluded}
        return (self.discovery_complete and not self.cancelled and not self.budget_exhausted
                and not self.skipped and not self.parse_failures and not self.unsupported
                and accounted == set(self.discovered))


@dataclass(frozen=True)
class SourceFingerprint:
    path: str
    digest: str

    def __post_init__(self):
        _path(self.path)
        _digest(self.digest)


@dataclass(frozen=True)
class AnalysisSnapshot:
    project: ProjectIdentity
    coverage: AnalysisCoverage
    fingerprints: tuple[SourceFingerprint, ...] = ()
    # Scope/options are canonical string pairs, never caller-owned nested dicts.
    options: tuple[tuple[str, str], ...] = ()
    schema_version: str = ANALYZER_SCHEMA_VERSION

    def __post_init__(self):
        if not isinstance(self.project, ProjectIdentity) or not isinstance(self.coverage, AnalysisCoverage):
            raise ValueError("Snapshot requires typed project and coverage.")
        _text(self.schema_version)
        fingerprints = _tuple(self, "fingerprints", SourceFingerprint)
        if (len({f.path for f in fingerprints}) != len(fingerprints)
                or not set(self.coverage.parsed) <= {f.path for f in fingerprints}
                or not {f.path for f in fingerprints} <= set(self.coverage.discovered)):
            raise ValueError("Parsed files require unique inventory fingerprints.")
        options = tuple(tuple(pair) for pair in self.options)
        if any(len(pair) != 2 or any(not isinstance(v, str) or not v for v in pair) for pair in options):
            raise ValueError("Options must be string key/value pairs.")
        if len({pair[0] for pair in options}) != len(options):
            raise ValueError("Duplicate scope option.")
        object.__setattr__(self, "options", tuple(sorted(options)))
        object.__setattr__(self, "fingerprints", tuple(sorted(fingerprints, key=lambda f: f.path)))

    @property
    def snapshot_id(self):
        value = asdict(self)
        # Discovery order is not part of snapshot identity.
        coverage = value["coverage"]
        for key in coverage:
            if isinstance(coverage[key], tuple):
                coverage[key] = sorted(coverage[key], key=lambda item: json.dumps(item, sort_keys=True))
        return stable_id("A", value)


@dataclass(frozen=True)
class AnalysisResult:
    snapshot: AnalysisSnapshot
    symbols: tuple[SymbolRecord, ...] = ()
    relationships: tuple[RelationshipRecord, ...] = ()

    def __post_init__(self):
        if not isinstance(self.snapshot, AnalysisSnapshot):
            raise ValueError("Analysis requires a snapshot.")
        symbols = _tuple(self, "symbols", SymbolRecord)
        relationships = _tuple(self, "relationships", RelationshipRecord)
        identities = {s.symbol_id: s for s in symbols}
        fingerprints = {f.path: f.digest for f in self.snapshot.fingerprints}
        if len(identities) != len(symbols) or len({r.relationship_id for r in relationships}) != len(relationships):
            raise ValueError("Duplicate symbol or relationship identity.")
        def validate_source(source):
            if (source.project != self.snapshot.project or source.path not in self.snapshot.coverage.parsed
                    or fingerprints.get(source.path) != source.digest):
                raise ValueError("Record source is outside the parsed snapshot.")
        for symbol in symbols:
            validate_source(symbol.definition)
        for relationship in relationships:
            endpoints = (relationship.origin,) + relationship.candidates
            if relationship.target:
                endpoints += (relationship.target,)
            if any(identities.get(s.symbol_id) != s for s in endpoints):
                raise ValueError("Unknown relationship endpoint.")
            for source in (relationship.location,) + relationship.supporting_sources:
                validate_source(source)


@dataclass(frozen=True)
class TraceResult:
    analysis: AnalysisResult
    root_symbol_id: str
    direction: str
    relationship_ids: tuple[str, ...] = ()
    cycle_relationship_ids: tuple[str, ...] = ()
    frontier_symbol_ids: tuple[str, ...] = ()
    cutoff_reasons: tuple[str, ...] = ()

    def __post_init__(self):
        if not isinstance(self.analysis, AnalysisResult) or self.direction not in {"forward", "reverse"}:
            raise ValueError("Trace requires an analysis and forward/reverse direction.")
        for name in ("relationship_ids", "cycle_relationship_ids", "frontier_symbol_ids", "cutoff_reasons"):
            for item in _tuple(self, name, str):
                _text(item)
        symbols = {s.symbol_id for s in self.analysis.symbols}
        edges = {r.relationship_id for r in self.analysis.relationships}
        if (self.root_symbol_id not in symbols or not set(self.frontier_symbol_ids) <= symbols
                or not set(self.relationship_ids) <= edges
                or not set(self.cycle_relationship_ids) <= set(self.relationship_ids)):
            raise ValueError("Trace references unknown records.")

    @property
    def complete(self):
        return self.analysis.snapshot.coverage.complete and not self.cutoff_reasons and not self.frontier_symbol_ids


@dataclass(frozen=True)
class RelationshipAnswerEvidence:
    analysis: AnalysisResult
    relationship_ids: tuple[str, ...]
    excerpts: tuple  # Existing frozen C1 SourceExcerpt records.

    def __post_init__(self):
        from models.source_evidence import SourceExcerpt
        if not isinstance(self.analysis, AnalysisResult):
            raise ValueError("Evidence requires an analysis result.")
        ids = _tuple(self, "relationship_ids", str)
        excerpts = _tuple(self, "excerpts", SourceExcerpt)
        records = {r.relationship_id: r for r in self.analysis.relationships}
        if len(set(ids)) != len(ids) or not set(ids) <= records.keys():
            raise ValueError("Unknown or duplicate selected relationship.")
        project = self.analysis.snapshot.project
        fingerprints = {f.path: f.digest for f in self.analysis.snapshot.fingerprints}
        source_ids = set()
        for excerpt in excerpts:
            if (excerpt.source_id in source_ids or excerpt.project_id != project.project_id
                    or excerpt.revision != project.authorization_revision
                    or fingerprints.get(excerpt.path) != excerpt.digest):
                raise ValueError("Evidence must use unique current snapshot source IDs.")
            source_ids.add(excerpt.source_id)
            if any(not isinstance(getattr(excerpt, name), str) for name in (
                    "path", "source_id", "digest", "text", "retrieved_at", "kind", "project_id")):
                raise ValueError("Excerpt text metadata must be immutable strings.")
            if type(excerpt.truncated) is not bool or type(excerpt.total_lines) is not int:
                raise ValueError("Excerpt coverage metadata must be immutable scalars.")
            SourceLocation.from_excerpt(project, excerpt)
            if not isinstance(excerpt.signature, tuple) or any(type(v) is not int for v in excerpt.signature):
                raise ValueError("Excerpt signature must be an immutable integer tuple.")
        def covered(source):
            return any(e.source_id == source.source_id and e.path == source.path and e.digest == source.digest
                       and e.start_line <= source.start_line <= source.end_line <= e.end_line for e in excerpts)
        for identity in ids:
            record = records[identity]
            required = (record.location,) + record.supporting_sources
            if record.target:
                required += (record.target.definition,)
            if not all(covered(source) for source in required):
                raise ValueError("Selected relationship lacks supporting source excerpts.")
