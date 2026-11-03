"""C3 scope declarations, not filesystem proofs or publication authorization.

Pure immutable contracts. Bind a scope through AnalysisRequest.validate_scope
before future analysis. Inventory, resolution, freshness, and evidence certificates
must eventually be independently verified; this checkpoint enables no publication.
"""
from dataclasses import asdict, dataclass
from enum import Enum

from models.project_relationships import (
    ProjectIdentity, SourceLocation, SymbolRecord, RelationshipRecord, RelationshipKind,
    Resolution, FileDiagnostic, stable_id, _path, _tuple,
)


C3_SCOPE_SCHEMA = "c3.scope.v1"
C3_ANALYSIS_POLICY = "python-static-scope-v1"
SUPPORT_MAX_FILES = 6
SUPPORT_MAX_DEPTH = 1


class ScopeKind(str, Enum):
    FILES = "files"
    DIRECTORY = "directory"
    PROJECT_PYTHON = "project_python"


class LanguagePolicy(str, Enum):
    PYTHON_ONLY = "python_only"


class QuerySemantics(str, Enum):
    DIRECT = "direct"
    TRANSITIVE = "transitive"


class CoverageStatus(str, Enum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    CANCELLED = "cancelled"


class CompletenessClaim(str, Enum):
    NONE = "none"
    FINDINGS_ONLY = "findings_only"
    SCOPED_COMPLETE = "scoped_complete"
    PROJECT_COMPLETE = "project_complete"


class EvidenceSelection(str, Enum):
    COMPLETE = "complete"
    TRUNCATED = "truncated"
    UNAVAILABLE = "unavailable"


class PublicationEligibility(str, Enum):
    DISABLED = "disabled"
    ELIGIBLE = "eligible"  # Reserved; rejected by this checkpoint's contract.


def _paths(record, field, *, python=False):
    paths = _tuple(record, field, str)
    for path in paths:
        _path(path)
        if any(char in path for char in '*?[]') or path != path.strip():
            raise ValueError("Scope paths must be explicit canonical paths, not patterns.")
        if python and not path.lower().endswith(".py"):
            raise ValueError("Expected a Python input path.")
    if len({path.casefold() for path in paths}) != len(paths):
        raise ValueError("Duplicate or Windows case-aliased scope paths.")
    object.__setattr__(record, field, tuple(sorted(paths)))
    return paths


def _within(path, root):
    path, root = path.casefold(), root.casefold()
    return path == root or path.startswith(root + "/")


@dataclass(frozen=True)
class SupportClosure:
    project: ProjectIdentity
    required_files: tuple[str, ...] = ()
    sources: tuple[SourceLocation, ...] = ()
    closed: bool = False
    depth: int = 0

    def __post_init__(self):
        if not isinstance(self.project, ProjectIdentity) or type(self.closed) is not bool:
            raise ValueError("Support needs a typed project and explicit closure state.")
        required = _paths(self, "required_files", python=True)
        sources = _tuple(self, "sources", SourceLocation)
        if (len(required) > SUPPORT_MAX_FILES or type(self.depth) is not int
                or not 0 <= self.depth <= SUPPORT_MAX_DEPTH):
            raise ValueError("Initial support closure exceeds its six-file, one-hop declaration bound.")
        paths = [source.path for source in sources]
        if (len({p.casefold() for p in paths}) != len(paths) or not set(paths) <= set(required)
                or any(source.project != self.project for source in sources)):
            raise ValueError("Support must be unique, declared, and from the same project/revision.")
        if self.closed and set(paths) != set(required):
            raise ValueError("A closed support set cannot have missing required files.")
        object.__setattr__(self, "sources", tuple(sorted(sources, key=lambda source: source.path)))

    @property
    def missing_files(self):
        return tuple(sorted(set(self.required_files) - {source.path for source in self.sources}))

    @property
    def complete(self):
        return self.closed and not self.missing_files


@dataclass(frozen=True)
class AnalysisScope:
    project: ProjectIdentity
    kind: ScopeKind
    roots: tuple[str, ...]
    search_files: tuple[str, ...]
    support: SupportClosure
    target: SymbolRecord
    operation: RelationshipKind
    direction: str
    semantics: QuerySemantics
    excluded_paths: tuple[str, ...] = ()
    language: LanguagePolicy = LanguagePolicy.PYTHON_ONLY
    analysis_policy: str = C3_ANALYSIS_POLICY
    schema_version: str = C3_SCOPE_SCHEMA

    def __post_init__(self):
        if (not isinstance(self.project, ProjectIdentity) or not isinstance(self.kind, ScopeKind)
                or not isinstance(self.support, SupportClosure) or not isinstance(self.target, SymbolRecord)
                or not isinstance(self.operation, RelationshipKind) or not isinstance(self.semantics, QuerySemantics)
                or self.direction not in {"forward", "reverse"}
                or self.language is not LanguagePolicy.PYTHON_ONLY
                or self.analysis_policy != C3_ANALYSIS_POLICY or self.schema_version != C3_SCOPE_SCHEMA):
            raise ValueError("Unsupported or unspecified C3 scope identity/query policy.")
        roots = _paths(self, "roots", python=self.kind == ScopeKind.FILES)
        search = _paths(self, "search_files", python=True)
        excluded = _paths(self, "excluded_paths")
        if self.kind == ScopeKind.PROJECT_PYTHON:
            if roots:
                raise ValueError("Project Python scope explicitly covers the authorized root, not subroots.")
        elif not roots:
            raise ValueError("File/directory scope requires explicit roots.")
        if any(_within(a, b) for a in roots for b in roots if a != b):
            raise ValueError("Overlapping scope roots are redundant declarations.")
        if any(not self.contains(path) for path in search):
            raise ValueError("Search membership expands beyond its declared roots/exclusions.")
        if self.kind == ScopeKind.FILES and set(roots) != set(search):
            raise ValueError("Explicit file scope must name exactly its caller-search files.")
        if any(not self._included(path) for path in excluded):
            raise ValueError("Exclusions must narrow the declared search domain.")
        required = set(self.support.required_files)
        if (self.support.project != self.project or self.target.definition.project != self.project
                or {path.casefold() for path in required} & {path.casefold() for path in search}
                or any(self.contains(path) for path in required)):
            raise ValueError("Search/support roles and project/revision must remain separate.")
        if self.target.definition.path not in set(search) | required:
            raise ValueError("Target definition must belong to the search or declared support domain.")

    def _included(self, path):
        if self.kind == ScopeKind.PROJECT_PYTHON:
            return True
        if self.kind == ScopeKind.FILES:
            return path in self.roots
        return any(_within(path, root) for root in self.roots)

    def contains(self, path):
        return (path.lower().endswith(".py") and self._included(path)
                and not any(_within(path, excluded) for excluded in self.excluded_paths))

    @property
    def scope_id(self):
        # Order is canonical; content freshness is separate from scope identity.
        value = asdict(self)
        value["target"] = self.target.symbol_id
        value["support"] = {"project": asdict(self.support.project),
                            "required_files": self.support.required_files,
                            "max_files": SUPPORT_MAX_FILES, "max_depth": SUPPORT_MAX_DEPTH}
        return stable_id("C3S", value)


@dataclass(frozen=True)
class ScopedCoverage:
    scope: AnalysisScope
    status: CoverageStatus = CoverageStatus.INCOMPLETE
    inventory_files: tuple[str, ...] = ()
    parsed_files: tuple[str, ...] = ()
    inventory_complete: bool = False
    extraction_truncated: bool = False
    limitations: tuple[FileDiagnostic, ...] = ()
    non_python_files: tuple[str, ...] = ()
    source_changed: bool = False

    def __post_init__(self):
        if (not isinstance(self.scope, AnalysisScope) or not isinstance(self.status, CoverageStatus)
                or type(self.inventory_complete) is not bool or type(self.extraction_truncated) is not bool
                or type(self.source_changed) is not bool):
            raise ValueError("Coverage requires typed scope/status and explicit flags.")
        inventory = _paths(self, "inventory_files", python=True)
        parsed = _paths(self, "parsed_files", python=True)
        other = _paths(self, "non_python_files")
        limits = _tuple(self, "limitations", FileDiagnostic)
        if (any(not self.scope.contains(path) for path in inventory)
                or not set(parsed) <= set(inventory) & set(self.scope.search_files)
                or any(path.lower().endswith(".py") or not self.scope._included(path) for path in other)):
            raise ValueError("Python coverage membership cannot be expanded or hidden as documentation.")
        if (len({d.path for d in limits}) != len(limits) or any(
                not d.path.lower().endswith(".py") or d.reason not in {
                    "unreadable_python", "excluded_required_python", "invalid_python", "unsupported_python"}
                or not (self.scope._included(d.path) or d.path in self.scope.support.required_files)
                for d in limits)):
            raise ValueError("Required Python failures need visible, scope-bound classifications.")
        if set(parsed) & {diagnostic.path for diagnostic in limits}:
            raise ValueError("A Python input cannot be both parsed and failed.")
        complete = (self.inventory_complete and not self.extraction_truncated and not self.source_changed and not limits
                    and self.scope.support.complete
                    and set(inventory) == set(parsed) == set(self.scope.search_files))
        if ((self.status == CoverageStatus.COMPLETE and not complete)
                or (self.status == CoverageStatus.INCOMPLETE and complete)):
            raise ValueError("Coverage status contradicts inventory, support, or extraction metadata.")


@dataclass(frozen=True)
class ScopedRelationshipResult:
    coverage: ScopedCoverage
    resolution: Resolution
    claim: CompletenessClaim
    evidence: EvidenceSelection
    relationships: tuple[RelationshipRecord, ...] = ()
    publication: PublicationEligibility = PublicationEligibility.DISABLED

    def __post_init__(self):
        if (not isinstance(self.coverage, ScopedCoverage) or not isinstance(self.resolution, Resolution)
                or not isinstance(self.claim, CompletenessClaim) or not isinstance(self.evidence, EvidenceSelection)
                or self.publication is not PublicationEligibility.DISABLED):
            raise ValueError("C3 metadata is typed; publication is disabled in this checkpoint.")
        edges = _tuple(self, "relationships", RelationshipRecord)
        scope = self.coverage.scope
        allowed = set(scope.search_files) | set(scope.support.required_files)
        provenance = {}
        def source_identity(source):
            identity = (source.source_id, source.digest)
            if source.path in provenance and provenance[source.path] != identity:
                raise ValueError("Conflicting source snapshots within the same scoped result.")
            provenance[source.path] = identity
        for source in (scope.target.definition,) + scope.support.sources:
            source_identity(source)
        if len({edge.relationship_id for edge in edges}) != len(edges):
            raise ValueError("Duplicate scoped relationship identities.")
        for edge in edges:
            endpoints = (edge.origin,) + edge.candidates + ((edge.target,) if edge.target else ())
            if (edge.kind != scope.operation or edge.origin.definition.path not in scope.search_files
                    or any(s.definition.project != scope.project or s.definition.path not in allowed for s in endpoints)
                    or any(s.project != scope.project or s.path not in allowed for s in edge.supporting_sources)):
                raise ValueError("Relationship provenance escapes its scope/project/revision.")
            for source in tuple(s.definition for s in endpoints) + (edge.location,) + edge.supporting_sources:
                source_identity(source)
            if scope.semantics == QuerySemantics.DIRECT and edge.target is not None:
                endpoint = edge.target if scope.direction == "reverse" else edge.origin
                if endpoint.symbol_id != scope.target.symbol_id:
                    raise ValueError("Direct relationship does not connect to the declared target.")
        exhaustive = self.claim in {CompletenessClaim.SCOPED_COMPLETE, CompletenessClaim.PROJECT_COMPLETE}
        if self.resolution == Resolution.CONFIRMED_STATIC and any(
                edge.resolution != Resolution.CONFIRMED_STATIC for edge in edges):
            raise ValueError("Unresolved records cannot be described as confirmed resolution.")
        if exhaustive and (self.coverage.status != CoverageStatus.COMPLETE
                or self.resolution != Resolution.CONFIRMED_STATIC or self.evidence != EvidenceSelection.COMPLETE
                or scope.semantics != QuerySemantics.DIRECT
                or scope.direction == "forward" and scope.target.definition.path not in scope.search_files
                or any(edge.resolution != Resolution.CONFIRMED_STATIC for edge in edges)):
            raise ValueError("Incomplete, uncertain, transitive, or evidence-truncated results cannot claim completeness.")
        if self.claim == CompletenessClaim.PROJECT_COMPLETE and (
                scope.kind != ScopeKind.PROJECT_PYTHON or scope.excluded_paths):
            raise ValueError("A narrowed domain cannot claim project-wide completeness.")
        if self.claim == CompletenessClaim.FINDINGS_ONLY and (
                not edges or scope.semantics != QuerySemantics.DIRECT
                or self.evidence == EvidenceSelection.UNAVAILABLE
                or not scope.support.complete
                or any(edge.resolution != Resolution.CONFIRMED_STATIC for edge in edges)):
            raise ValueError("Findings require selected confirmed direct records and evidence metadata.")
        if self.coverage.status == CoverageStatus.CANCELLED and self.claim != CompletenessClaim.NONE:
            raise ValueError("Cancelled work cannot carry a publishable claim.")

    @property
    def exhaustive(self):
        return self.claim in {CompletenessClaim.SCOPED_COMPLETE, CompletenessClaim.PROJECT_COMPLETE}

    @property
    def publication_ready(self):
        return False
