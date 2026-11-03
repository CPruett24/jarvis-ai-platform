from pathlib import Path
from functools import lru_cache


def analyze_project_relationships(request):
    """Context-aware C2 extraction, separate from the guarded legacy adapter.

    One inventory, safe reads only, no runtime imports of project source. Partial
    and cancelled operations retain typed coverage and already completed records.
    This does not publish a capability response or construct a traversal/impact graph.
    """
    import ast
    from dataclasses import replace
    from models.project_relationships import (AnalysisCoverage, AnalysisSnapshot, AnalysisResult,
                                             FileDiagnostic, SourceFingerprint)
    from models.source_evidence import RetrievalLimits, RetrievalStatus
    from services.project_analysis_request import AnalysisBudgetExceeded
    from services.project_analysis_cache import read_analysis_source
    from services.project_symbol_index import extract_scoped_symbols
    from services.project_dependencies import resolve_source_import
    from services.project_execution import resolve_source_calls
    from services.project_retrieval import discover
    from services.project_access import validate_project, get_project, ProjectAccessError
    from services.cancellation import OperationCancelled

    request.check_authorization()
    identity = request.identity
    modules, fingerprints, parsed, skipped, failures, unsupported = {}, [], [], [], [], []
    paths, edges, bindings, exhaustion = [], [], {}, []
    exclusions = []
    cancelled, complete_discovery, entries = False, False, 0
    try:
        listing = discover(request.context, analysis_request=request, exclusion_diagnostics=exclusions,
                           limits=replace(RetrievalLimits(), seconds=request.budget.limits.seconds))
        entries = listing.entries_visited
        paths = list(listing.paths)
        complete_discovery = listing.status == RetrievalStatus.SUCCESS
        exhaustion.extend(listing.limits_reached)
        if listing.status == RetrievalStatus.CANCELLED:
            raise OperationCancelled()
        if not listing.success:
            exhaustion.append(listing.error or listing.status.value)
        for path in paths:
            request.check_authorization()
            if not path.lower().endswith(".py"):
                unsupported.append(FileDiagnostic(path, "unsupported_source_language"))
                continue
            # Refuse to read another source when no parse slot remains.
            if dict(request.budget.usage.consumed)["python_files"] >= request.budget.limits.python_files:
                request.budget.consume(python_files=1)
            read = read_analysis_source(request, path)
            if read.status == RetrievalStatus.CANCELLED:
                raise OperationCancelled()
            if not read.success or not read.excerpts or read.excerpts[0].truncated:
                skipped.append(FileDiagnostic(path, read.error or ",".join(read.limits_reached) or read.status.value))
                exhaustion.extend(read.limits_reached)
                if any(reason.startswith("analysis:") for reason in read.limits_reached):
                    break
                continue
            excerpt = read.excerpts[0]
            fingerprints.append(SourceFingerprint(path, excerpt.digest))
            request.budget.consume(python_files=1)
            try:
                tree = ast.parse(excerpt.text, filename=path)
                count = 0
                for _ in ast.walk(tree):
                    count += 1
                    request.budget.consume(ast_nodes=1)
                    request.budget.check_file(read.bytes_read, count)
                module = extract_scoped_symbols(tree, excerpt, request)
            except (SyntaxError, RecursionError, ValueError) as exc:
                failures.append(FileDiagnostic(path, f"{type(exc).__name__}: {exc}"))
                continue
            modules[path] = module
            parsed.append(path)
        # Resolve only after the bounded parse pass so forward imports work.
        for module in modules.values():
            for observation in module.imports:
                request.budget.check()
                edge, target = resolve_source_import(observation, modules, set(paths),
                                                     inventory_complete=complete_discovery)
                request.budget.consume(relationships=1)
                bindings[id(observation)] = (edge, target)
                edges.append(edge)
        tainted = {target.symbol.definition.path for module in modules.values() for observation in module.imports
                   for _, target in [bindings[id(observation)]]
                   if target is not None and observation.bound_name in module.mutations}
        for module in modules.values():
            edges.extend(resolve_source_calls(module, modules, bindings, request, tainted_paths=tainted))
        request.budget.check()
    except OperationCancelled:
        cancelled = True
    except AnalysisBudgetExceeded as exc:
        exhaustion.append(exc.resource)
    # Budget checks can intentionally fail here, but authorization may never be
    # bypassed even when returning diagnostic-only partial/cancelled work.
    validate_project(request.context)
    if request.context != get_project():
        raise ProjectAccessError("Active project changed during analysis.")
    exhaustion.extend(request.budget.usage.exhausted)
    accounted = set(parsed) | {d.path for d in skipped + failures + unsupported}
    skipped.extend(FileDiagnostic(path, "analysis_stopped_before_parse") for path in paths if path not in accounted)
    coverage = AnalysisCoverage(tuple(sorted(paths + [p for p, _ in exclusions])), tuple(parsed),
        excluded=tuple(FileDiagnostic(p, reason) for p, reason in exclusions),
        skipped=tuple(skipped), parse_failures=tuple(failures),
        unsupported=tuple(unsupported), budget_exhausted=tuple(sorted(set(exhaustion))),
        cancelled=cancelled, discovery_complete=complete_discovery)
    usage = request.budget.usage
    options = (("language", "python"), ("discovery_entries", str(entries))) + tuple(
        ("consumed_" + name, str(value)) for name, value in usage.consumed)
    snapshot = AnalysisSnapshot(identity, coverage, tuple(fingerprints), options, schema_version="c2.2")
    return AnalysisResult(snapshot, tuple(scope.symbol for module in modules.values() for scope in module.scopes),
                          tuple(edges))

from services.project_service import _project_files
from services.project_analysis_cache import get_source_tree
from services.project_execution import (
    _extract_functions,
    _extract_imports,
    _extract_calls,
    _resolve_call,
    _normalize_path,
)


def build_project_analysis_index():
    """
    Build a project-wide static analysis index.

    Each Python file is analyzed once.

    The resulting index contains:
    - functions
    - classes
    - imports
    - resolved calls
    - reverse call relationships
    """

    index = {
        "files": {},
        "symbols": {},
        "calls": {},
        "reverse_calls": {},
    }

    for file_path in _project_files():

        if file_path.suffix.lower() != ".py":
            continue

        tree = get_source_tree(file_path)

        if tree is None:
            continue

        functions = _extract_functions(tree)
        imports = _extract_imports(tree)

        module_calls = _extract_calls(tree)

        resolved_module_calls = []

        for call in module_calls:

            resolved = _resolve_call(
                call,
                functions,
                imports,
            )

            if resolved is None:
                continue

            resolved_module_calls.append(
                {
                    "call": call,
                    "target": resolved,
                }
            )

        normalized_file = _normalize_path(file_path)

        file_data = {
            "path": normalized_file,
            "functions": {},
            "imports": imports,
        }

        module_key = (
            normalized_file,
            "<module>",
        )

        index["symbols"][
            module_key
        ] = {
            "file": normalized_file,
            "function": "<module>",
        }

        index["calls"][
            module_key
        ] = resolved_module_calls

        for resolved in resolved_module_calls:

            target = resolved["target"]

            if target["kind"] == "local":

                target_file = normalized_file

            elif target["kind"] == "project_function":

                target_file = _normalize_path(
                    target["path"]
                )

            else:
                continue

            target_key = (
                target_file,
                target["function"],
            )

            index["reverse_calls"].setdefault(
                target_key,
                [],
            )

            caller = {
                "file": normalized_file,
                "function": "<module>",
                "call": resolved["call"],
            }

            if caller not in index[
                "reverse_calls"
            ][target_key]:

                index[
                    "reverse_calls"
                ][target_key].append(
                    caller
                )

        for function_name, function_node in functions.items():

            calls = _extract_calls(function_node)

            resolved_calls = []

            for call in calls:

                resolved = _resolve_call(
                    call,
                    functions,
                    imports,
                )

                if resolved is None:
                    continue

                resolved_calls.append(
                    {
                        "call": call,
                        "target": resolved,
                    }
                )

            file_data["functions"][
                function_name
            ] = {
                "name": function_name,
                "calls": calls,
                "resolved_calls": resolved_calls,
            }

            symbol_key = (
                normalized_file,
                function_name,
            )

            index["symbols"][
                symbol_key
            ] = {
                "file": normalized_file,
                "function": function_name,
            }

            caller_key = symbol_key

            index["calls"][
                caller_key
            ] = resolved_calls

            for resolved in resolved_calls:

                target = resolved["target"]

                if target["kind"] == "local":

                    target_file = normalized_file

                elif target["kind"] == "project_function":

                    target_file = _normalize_path(
                        target["path"]
                    )

                else:
                    continue

                target_key = (
                    target_file,
                    target["function"],
                )

                index["reverse_calls"].setdefault(
                    target_key,
                    [],
                )

                caller = {
                    "file": normalized_file,
                    "function": function_name,
                    "call": resolved["call"],
                }

                if caller not in index[
                    "reverse_calls"
                ][target_key]:

                    index[
                        "reverse_calls"
                    ][target_key].append(
                        caller
                    )

        index["files"][
            normalized_file
        ] = file_data

    return index

def _project_signature():
    """
    Build a signature for the current Python project files.

    The signature changes when a Python file is added, removed,
    modified, or resized.
    """

    files = []

    for path in _project_files():

        if path.suffix.lower() != ".py":
            continue

        try:
            stat = path.stat()

        except OSError:
            continue

        files.append(
            (
                str(path.resolve()),
                stat.st_mtime_ns,
                stat.st_size,
            )
        )

    return tuple(
        sorted(files)
    )


@lru_cache(maxsize=4)
def _get_cached_project_analysis_index(
    signature,
):
    """
    Return a cached project-wide analysis index.
    """

    return build_project_analysis_index()


def get_project_analysis_index():
    """
    Return the current project analysis index.

    The index is rebuilt automatically when Python project
    files change.
    """

    signature = _project_signature()

    return _get_cached_project_analysis_index(
        signature
    )


def clear_project_analysis_index_cache():
    """
    Clear the cached project analysis index.
    """

    _get_cached_project_analysis_index.cache_clear()


def get_project_analysis_index_cache_info():
    """
    Return cache statistics for the project analysis index.
    """

    return (
        _get_cached_project_analysis_index.cache_info()
    )

def find_indexed_function_callers(
    index,
    filename,
    function_name,
):
    """
    Find callers using a previously-built project index.
    """

    matches = [
        path
        for path in index["files"]
        if Path(path).name.lower()
        == filename.lower()
    ]

    if not matches:
        return None

    target_file = matches[0]

    target_key = (
        target_file,
        function_name,
    )

    callers = index[
        "reverse_calls"
    ].get(
        target_key,
        [],
    )

    return {
        "file": target_file,
        "function": function_name,
        "callers": callers,
    }
