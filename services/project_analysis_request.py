"""Request-owned C2 context and budgets; not connected to live analyzers yet."""
from dataclasses import dataclass, fields
import math
import os
from threading import RLock
import time

from models.project_relationships import ProjectIdentity
from services.cancellation import check_cancelled
from services.project_access import AuthorizedProject, ProjectAccessError, get_project, validate_project


@dataclass(frozen=True)
class AnalysisLimits:
    python_files: int = 256
    source_bytes: int = 8 * 1024 * 1024
    file_bytes: int = 512 * 1024
    ast_nodes_per_file: int = 50000
    ast_nodes: int = 200000
    relationships: int = 10000
    depth: int = 4
    visited_symbols: int = 200
    traversed_edges: int = 500
    evidence_excerpts: int = 8
    evidence_files: int = 6
    payload_bytes: int = 24 * 1024
    selected_relationships: int = 32
    seconds: float = 5.0

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            if field.name == "seconds":
                if type(value) not in {int, float} or not math.isfinite(value) or value <= 0:
                    raise ValueError("Deadline must be finite and positive.")
            elif type(value) is not int or value <= 0:
                raise ValueError("Analysis limits must be positive integers.")
        if self.file_bytes > 512 * 1024:
            raise ValueError("C1 per-file ceiling cannot be raised.")


class AnalysisBudgetExceeded(Exception):
    def __init__(self, resource):
        self.resource = resource
        super().__init__(f"Analysis budget exhausted: {resource}")


@dataclass(frozen=True)
class BudgetUsage:
    consumed: tuple[tuple[str, int], ...]
    exhausted: tuple[str, ...]
    elapsed_seconds: float


class AnalysisBudget:
    """Pass the same instance through every nested stage. No implicit resets.

    consume() charges additive work; check_file() and check_depth() validate local
    ceilings. Failed multi-resource charges are atomic. Cancellation propagates as
    OperationCancelled, separate from resource exhaustion. Deadlines are cooperative.
    """
    def __init__(self, limits=None, cancellation_event=None, *, clock=time.monotonic):
        self._limits = AnalysisLimits() if limits is None else limits
        if not isinstance(self._limits, AnalysisLimits):
            raise ValueError("Expected AnalysisLimits.")
        self._event = cancellation_event
        self._clock = clock
        self._started = clock()
        self._deadline = self._started + self._limits.seconds
        self._consumed = {f.name: 0 for f in fields(self._limits)
                          if f.name not in {"seconds", "depth", "file_bytes", "ast_nodes_per_file"}}
        self._exhausted = set()
        self._lock = RLock()

    @property
    def limits(self):
        return self._limits

    def _fail(self, resource):
        self._exhausted.add(resource)
        raise AnalysisBudgetExceeded(resource)

    def check(self):
        with self._lock:
            check_cancelled(self._event)
            if self._clock() >= self._deadline:
                self._fail("seconds")

    def consume(self, **amounts):
        with self._lock:
            self.check()
            for name, amount in amounts.items():
                if name not in self._consumed or type(amount) is not int or amount < 0:
                    raise ValueError("Expected a known additive resource and nonnegative integer.")
            for name, amount in amounts.items():
                if self._consumed[name] + amount > getattr(self._limits, name):
                    self._fail(name)
            for name, amount in amounts.items():
                self._consumed[name] += amount

    def _ceiling(self, name, value):
        with self._lock:
            self.check()
            if type(value) is not int or value < 0:
                raise ValueError("Expected a nonnegative integer.")
            if value > getattr(self._limits, name):
                self._fail(name)

    def check_file(self, byte_count, ast_node_count=0):
        self._ceiling("file_bytes", byte_count)
        self._ceiling("ast_nodes_per_file", ast_node_count)

    def check_depth(self, depth):
        self._ceiling("depth", depth)

    @property
    def remaining_seconds(self):
        """Time left on the original deadline; reading this never renews it."""
        with self._lock:
            self.check()
            return max(0.0, self._deadline - self._clock())

    @property
    def usage(self):
        with self._lock:
            return BudgetUsage(tuple(sorted(self._consumed.items())), tuple(sorted(self._exhausted)),
                               max(0.0, self._clock() - self._started))


@dataclass(frozen=True)
class AnalysisRequest:
    context: AuthorizedProject
    budget: AnalysisBudget

    def __post_init__(self):
        if not isinstance(self.context, AuthorizedProject) or not isinstance(self.budget, AnalysisBudget):
            raise ValueError("Request requires captured authorization and one shared budget.")
        self.check_authorization()

    @classmethod
    def capture(cls, project_id=None, *, limits=None, cancellation_event=None, clock=time.monotonic):
        # Existing registry only: this never registers or infers a project root.
        return cls(get_project(project_id), AnalysisBudget(limits, cancellation_event, clock=clock))

    @property
    def identity(self):
        return ProjectIdentity(self.context.project_id,
                               os.path.normcase(str(self.context.root.resolve(strict=True))),
                               self.context.revision)

    def check_authorization(self):
        self.budget.check()
        validate_project(self.context)
        if self.context != get_project():
            raise ProjectAccessError("Active project changed during analysis.")

    def validate_for_publication(self, result):
        from models.project_relationships import AnalysisResult
        self.check_authorization()
        if not isinstance(result, AnalysisResult) or result.snapshot.project != self.identity:
            raise ProjectAccessError("Result does not belong to the captured project context.")
        # Source/inventory freshness must be checked by the future analyzer.
        return result
