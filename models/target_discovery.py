"""Inactive C3 identity-discovery snapshots, never caller/publication evidence."""
from dataclasses import asdict, dataclass, replace
from enum import Enum
import json

from models.dependency_disposition import (
    DependencyPolicy, MAX_PLAN_BYTES, MAX_PROOF_SOURCES, _bounded, _sources,
)
from models.project_relationships import ProjectIdentity, SourceLocation, SymbolKind, SymbolRecord, _path, stable_id
from models.project_scope import ScopeKind, SUPPORT_MAX_FILES, _paths
from models.scoped_answer import ScopedCallerIntent


C3_TARGET_DISCOVERY_SCHEMA = "c3.target-discovery.v1"


class TargetIdentityStatus(str, Enum):
    EXACT = "exact"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"
    REFUSED = "refused"


@dataclass(frozen=True)
class TargetIdentityResult:
    project: ProjectIdentity
    intent: ScopedCallerIntent | None
    status: TargetIdentityStatus
    roots: tuple[str, ...] = ()
    search_files: tuple[str, ...] = ()
    lookup_files: tuple[str, ...] = ()
    source_inventory: tuple[str, ...] = ()
    inventory_exclusions: tuple[tuple[str, str], ...] = ()
    proof_dependencies: tuple[SourceLocation, ...] = ()
    candidates: tuple[SymbolRecord, ...] = ()
    file_options: tuple[str, ...] = ()
    target: SymbolRecord | None = None
    reasons: tuple[str, ...] = ()
    policy: DependencyPolicy = DependencyPolicy()
    schema_version: str = C3_TARGET_DISCOVERY_SCHEMA

    def __post_init__(self):
        if (not isinstance(self.project, ProjectIdentity) or not isinstance(self.status, TargetIdentityStatus)
                or self.intent is not None and not isinstance(self.intent, ScopedCallerIntent)
                or not isinstance(self.policy, DependencyPolicy) or self.schema_version != C3_TARGET_DISCOVERY_SCHEMA):
            raise ValueError("Invalid target-discovery identity, state or policy.")
        replace(self.project)
        replace(self.policy)
        for field, maximum in (("roots", MAX_PROOF_SOURCES), ("search_files", MAX_PROOF_SOURCES),
                               ("lookup_files", MAX_PROOF_SOURCES), ("source_inventory", 10000), ("file_options", 32)):
            _bounded(getattr(self, field), str, maximum)
            _paths(self, field, python=field != "roots")
        excluded = _bounded(self.inventory_exclusions, tuple, 10000)
        for pair in excluded:
            if len(pair) != 2 or not all(isinstance(value, str) and value for value in pair):
                raise ValueError("Malformed discovery exclusion.")
            _path(pair[0])
        if len(set(excluded)) != len(excluded):
            raise ValueError("Duplicate discovery exclusions.")
        object.__setattr__(self, "inventory_exclusions", tuple(sorted(excluded)))
        sources = _sources(self.proof_dependencies, self.project)
        catalog = {source.path: source for source in sources}
        if (set(catalog) != set(self.lookup_files)
                or not set(self.lookup_files + self.search_files + self.file_options) <= set(self.source_inventory)
                or len(set(self.lookup_files) - set(self.search_files)) > SUPPORT_MAX_FILES):
            raise ValueError("Discovery sources must match the bounded authorized lookup domain.")
        candidates = _bounded(self.candidates, SymbolRecord, 32)
        if len({candidate.symbol_id for candidate in candidates}) != len(candidates):
            raise ValueError("Duplicate target identities.")
        for candidate in candidates:
            replace(candidate)
            source = candidate.definition
            whole = catalog.get(source.path)
            if (source.project != self.project or whole is None
                    or (source.source_id, source.digest) != (whole.source_id, whole.digest)
                    or not whole.start_line <= source.start_line <= source.end_line <= whole.end_line):
                raise ValueError("Target identity lacks matching source provenance.")
        reasons = _bounded(self.reasons, str, 8)
        if any(not reason or len(reason) > 512 for reason in reasons):
            raise ValueError("Invalid discovery diagnostics.")
        if self.status == TargetIdentityStatus.EXACT:
            if (self.target is None or candidates != (self.target,) or reasons or self.file_options
                    or self.intent is None or not self.intent.direct or self.intent.error
                    or not isinstance(self.intent.scope_kind, ScopeKind)
                    or self.target.qualified_name != self.intent.qualified_name
                    or self.target.kind not in {SymbolKind.FUNCTION, SymbolKind.ASYNC_FUNCTION, SymbolKind.METHOD}):
                raise ValueError("Exact discovery needs one source-backed callable definition.")
        elif self.target is not None or not reasons:
            raise ValueError("Non-exact discovery cannot grant a target identity.")
        if self.status == TargetIdentityStatus.AMBIGUOUS and len(candidates) < 2 and len(self.file_options) < 2:
            raise ValueError("Ambiguity needs distinct candidate identities or target files.")
        if self.status == TargetIdentityStatus.REFUSED and (candidates or self.file_options):
            raise ValueError("Refusal cannot carry rejected target options.")
        object.__setattr__(self, "proof_dependencies", sources)
        object.__setattr__(self, "candidates", tuple(sorted(candidates,
            key=lambda s: (s.definition.path, s.qualified_name, s.definition.start_line, s.definition.start_column))))
        object.__setattr__(self, "reasons", reasons)
        if len(json.dumps(asdict(self), separators=(",", ":")).encode("utf-8")) > MAX_PLAN_BYTES:
            raise ValueError("Target discovery exceeds the existing payload ceiling.")

    @property
    def discovery_id(self):
        return stable_id("C3Target", {"policy_id": self.policy.policy_id, "snapshot": asdict(self)})

    @property
    def support_budget_files(self):
        return tuple(path for path in self.lookup_files if path not in self.search_files)

    @property
    def publication_enabled(self):
        return False

    @property
    def omission_enabled(self):
        return False
