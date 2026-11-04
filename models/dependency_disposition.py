"""Inactive C3 dependency declarations, not independent proof or authorization.

No planner or consumer imports this module. Evidence here is untrusted input for
future independent replay. Even a structurally complete plan cannot omit imports
or enable publication. Existing AnalysisScope/SupportClosure identities are intact.
"""
from dataclasses import asdict, dataclass, replace
from enum import Enum
import json
import re

from models.project_relationships import ProjectIdentity, SourceLocation, _path, stable_id
from models.project_scope import AnalysisScope, SUPPORT_MAX_DEPTH, SUPPORT_MAX_FILES


C3_DEPENDENCY_SCHEMA = "c3.dependency-dispositions.v1"
# Declaration ceilings only; future consumers must also apply the request's
# smaller limits and charge the original shared budget for all actual work.
MAX_PROOF_SOURCES = 256
MAX_PLAN_BYTES = 24 * 1024


class DependencyDisposition(str, Enum):
    REQUIRED = "required"
    PROVEN_IRRELEVANT = "proven_irrelevant"
    UNKNOWN = "unknown"


class DependencyCheck(str, Enum):
    BINDING = "binding"
    AMBIGUITY = "ambiguity"
    MUTATION = "mutation"
    CALLS = "calls"


@dataclass(frozen=True)
class DependencyPolicy:
    name: str = "unconditional-one-hop"
    version: int = 1
    schema_version: str = C3_DEPENDENCY_SCHEMA

    def __post_init__(self):
        if (self.name != "unconditional-one-hop" or type(self.version) is not int
                or self.version != 1 or self.schema_version != C3_DEPENDENCY_SCHEMA):
            raise ValueError("Unsupported dependency planning policy or schema version.")

    @property
    def policy_id(self):
        return stable_id("C3DP", {**asdict(self), "max_support_files": SUPPORT_MAX_FILES,
                                  "max_support_depth": SUPPORT_MAX_DEPTH})


def _bounded(value, item_type, maximum):
    if (type(value) not in {tuple, list} or len(value) > maximum
            or any(not isinstance(item, item_type) for item in value)):
        raise ValueError("Expected a bounded typed dependency collection.")
    return tuple(value)


def _python_path(path):
    _path(path)
    if path != path.strip() or any(c in path for c in "*?[]") or not path.lower().endswith(".py"):
        raise ValueError("Dependency paths must be canonical explicit Python paths.")


def _sources(value, project):
    sources = _bounded(value, SourceLocation, MAX_PROOF_SOURCES)
    paths, identities = set(), set()
    for source in sources:
        replace(source)
        _python_path(source.path)
        if (source.project != project or source.path.casefold() in paths
                or source.source_id in identities):
            raise ValueError("Duplicate, conflicting or cross-project proof source.")
        paths.add(source.path.casefold())
        identities.add(source.source_id)
    return tuple(sorted(sources, key=lambda source: source.path))


@dataclass(frozen=True)
class DependencyDecision:
    project: ProjectIdentity
    scope_id: str
    path: str
    disposition: DependencyDisposition
    proof_sources: tuple[SourceLocation, ...] = ()
    checks: tuple[DependencyCheck, ...] = ()
    policy: DependencyPolicy = DependencyPolicy()

    def __post_init__(self):
        if not isinstance(self.project, ProjectIdentity) or not isinstance(self.policy, DependencyPolicy):
            raise ValueError("Dependency decisions require typed project and policy identities.")
        replace(self.project)
        replace(self.policy)
        _python_path(self.path)
        if not isinstance(self.scope_id, str) or not re.fullmatch(r"C3S[0-9a-f]{64}", self.scope_id):
            raise ValueError("Dependency evidence must be bound to an existing C3 scope identity.")
        if not isinstance(self.disposition, DependencyDisposition):
            raise ValueError("Unknown dependency disposition.")
        sources = _sources(self.proof_sources, self.project)
        checks = _bounded(self.checks, DependencyCheck, len(DependencyCheck))
        if len(set(checks)) != len(checks):
            raise ValueError("Duplicate irrelevance checks.")
        if self.disposition == DependencyDisposition.PROVEN_IRRELEVANT:
            if not sources or set(checks) != set(DependencyCheck):
                raise ValueError("Irrelevance requires evidence for binding, ambiguity, mutation and calls.")
        elif sources or checks:
            raise ValueError("Required or unknown relevance cannot carry an irrelevance certificate.")
        object.__setattr__(self, "proof_sources", sources)
        object.__setattr__(self, "checks", tuple(sorted(checks, key=lambda check: check.value)))


@dataclass(frozen=True)
class DependencyPlan:
    """Structurally checked metadata; complete is NOT semantic verification.

    All unconditional support remains active regardless of disposition. Additional
    consulted proof sources are explicit and consume the same six-file allowance.
    Unknown decisions and missing required provenance cannot declare completeness.
    """
    scope: AnalysisScope
    decisions: tuple[DependencyDecision, ...]
    proof_dependencies: tuple[SourceLocation, ...] = ()
    complete: bool = False
    policy: DependencyPolicy = DependencyPolicy()

    def __post_init__(self):
        if (not isinstance(self.scope, AnalysisScope) or not isinstance(self.policy, DependencyPolicy)
                or type(self.complete) is not bool):
            raise ValueError("Dependency plans need an existing scope, typed policy and explicit completeness.")
        replace(self.scope)
        replace(self.scope.support)
        replace(self.scope.project)
        replace(self.policy)
        decisions = _bounded(self.decisions, DependencyDecision, SUPPORT_MAX_FILES)
        paths = set()
        for decision in decisions:
            replace(decision)
            if (decision.project != self.scope.project or decision.scope_id != self.scope.scope_id
                    or decision.policy != self.policy or decision.path.casefold() in paths):
                raise ValueError("Conflicting dependency identity, scope, project/revision or policy.")
            paths.add(decision.path.casefold())
        if {d.path for d in decisions} != set(self.scope.support.required_files):
            raise ValueError("The unconditional policy must retain every declared support dependency.")
        sources = _sources(self.proof_dependencies, self.scope.project)
        catalog = {source.path: source for source in sources}
        provenance, identities = {}, {}
        references = (self.scope.target.definition,) + self.scope.support.sources + sources + tuple(
            source for decision in decisions for source in decision.proof_sources)
        for source in references:
            replace(source)
            key = source.path.casefold()
            identity = (source.path, source.project, source.source_id, source.digest)
            if (source.project != self.scope.project
                    or key in provenance and provenance[key] != identity
                    or source.source_id in identities and identities[source.source_id] != key):
                raise ValueError("Inconsistent source provenance.")
            provenance[key], identities[source.source_id] = identity, key
            if source.path in catalog:
                whole = catalog[source.path]
                if not whole.start_line <= source.start_line <= source.end_line <= whole.end_line:
                    raise ValueError("Proof reference escapes its declared source range.")
        for decision in decisions:
            if any(source.path not in catalog for source in decision.proof_sources):
                raise ValueError("Missing consulted proof dependency.")
        search = set(self.scope.search_files)
        declared_paths = {path.casefold(): path for path in search | set(self.scope.support.required_files)}
        if any(path.casefold() in declared_paths and declared_paths[path.casefold()] != path for path in catalog):
            raise ValueError("Proof sources cannot case-alias declared search or support identities.")
        if any(self.scope.contains(path) and path not in search for path in catalog):
            raise ValueError("Proof dependencies cannot expand declared caller-search membership.")
        support = set(self.scope.support.required_files) | (set(catalog) - search)
        if len(support) > SUPPORT_MAX_FILES or len(search | support) > MAX_PROOF_SOURCES:
            raise ValueError("Dependency proof exceeds the existing support or source-file ceiling.")
        if self.complete and (not self.scope.support.complete
                or any(d.disposition == DependencyDisposition.UNKNOWN for d in decisions)
                or not set(self.scope.support.required_files) <= set(catalog)
                or self.scope.target.definition.path not in catalog):
            raise ValueError("Complete support requires resolved dispositions and all required provenance.")
        object.__setattr__(self, "decisions", tuple(sorted(decisions, key=lambda d: d.path)))
        object.__setattr__(self, "proof_dependencies", sources)
        if len(json.dumps(asdict(self), separators=(",", ":")).encode("utf-8")) > MAX_PLAN_BYTES:
            raise ValueError("Dependency plan exceeds the existing payload ceiling.")

    @property
    def active_support_files(self):
        return self.scope.support.required_files

    @property
    def support_budget_files(self):
        return tuple(sorted(set(self.active_support_files) | {
            source.path for source in self.proof_dependencies if source.path not in self.scope.search_files}))

    @property
    def plan_id(self):
        return stable_id("C3DPlan", {"policy_id": self.policy.policy_id, "declaration": asdict(self)})

    @property
    def omission_enabled(self):
        return False

    @property
    def publication_enabled(self):
        return False
