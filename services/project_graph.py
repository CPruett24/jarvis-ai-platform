from services.project_dependencies import (
    get_file_dependencies,
)

from services.project_service import (
    _project_files,
    classify_project_file,
)


def _validate_analysis_owner(analysis, request, *, check_budget=True):
    """C2 admission; do not relax the separate legacy project restriction."""
    from services.project_access import validate_project, get_project, ProjectAccessError
    if check_budget:
        request.budget.check()
    validate_project(request.context)
    if request.context != get_project() or analysis.snapshot.project != request.identity:
        raise ProjectAccessError("Analysis does not belong to the captured active authorization.")


def build_relationship_graph(analysis, request, kind):
    """Canonical C2 view only: no legacy graph facts or name-based edge guesses.

    Imports project exact file endpoints onto existing module symbols, retaining
    original relationship IDs and records. Reverse adjacency uses those same arcs.
    Construction deadline/cancellation failures propagate without returning a graph.
    """
    from models.project_graph import GraphArc, RelationshipGraph
    from models.project_relationships import RelationshipKind, Resolution, SymbolKind
    from services.project_analysis_request import AnalysisBudgetExceeded
    if not isinstance(kind, RelationshipKind):
        raise ValueError("Expected a relationship kind.")
    _validate_analysis_owner(analysis, request)
    if len(analysis.relationships) > request.budget.limits.relationships:
        raise AnalysisBudgetExceeded("relationships")
    symbols = {s.symbol_id: s for s in analysis.symbols}
    modules = {s.definition.path: s.symbol_id for s in analysis.symbols if s.kind == SymbolKind.MODULE}
    if len(modules) != sum(s.kind == SymbolKind.MODULE for s in analysis.symbols):
        raise ValueError("Duplicate module records cannot define canonical file vertices.")
    arcs, boundaries = [], []
    for edge in analysis.relationships:
        request.budget.check()
        if edge.kind != kind:
            continue
        if edge.resolution != Resolution.CONFIRMED_STATIC:
            boundaries.append(edge.relationship_id)
            continue
        origin, target = edge.origin.symbol_id, edge.target.symbol_id
        if kind == RelationshipKind.IMPORTS:
            origin, target = modules.get(edge.origin.definition.path), modules.get(edge.target.definition.path)
        if origin is None or target is None:
            raise ValueError("Canonical import endpoints need module symbols.")
        arcs.append(GraphArc(edge.relationship_id, origin, target))
    def node_key(identity):
        symbol = symbols[identity]
        return symbol.definition.path, symbol.qualified_name, symbol.definition.start_line, identity
    nodes = modules.values() if kind == RelationshipKind.IMPORTS else symbols.keys()
    graph = RelationshipGraph(analysis, kind, tuple(sorted(nodes, key=node_key)),
        tuple(sorted(arcs, key=lambda a: (node_key(a.origin_id), node_key(a.target_id), a.relationship_id))),
        tuple(sorted(boundaries)))
    _validate_analysis_owner(analysis, request)
    return graph


def traverse_relationships(graph, request, *, symbol_id=None, filename=None, qualified_name=None,
                           direction="forward", max_depth=None):
    """Resolve an exact C2 target, returning ambiguity instead of choosing one."""
    from models.project_graph import GraphTraversal
    from services.project_target import resolve_analysis_target
    _validate_analysis_owner(graph.analysis, request)
    if symbol_id is not None:
        if filename is not None or qualified_name is not None:
            raise ValueError("Use an exact ID or a file/qualified-name target.")
        roots = (symbol_id,) if symbol_id in graph.node_ids else ()
        status, candidates = ("resolved" if roots else "not_found"), ()
    else:
        result = resolve_analysis_target(graph.analysis, filename, qualified_name)
        candidates = tuple(s.symbol_id for s in result["candidates"] if s.symbol_id in graph.node_ids)
        status = "resolved" if len(candidates) == 1 else "ambiguous" if candidates else "not_found"
        roots = candidates if status == "resolved" else ()
    if status != "resolved":
        result = GraphTraversal(graph, direction, status, candidates=candidates)
        _validate_analysis_owner(graph.analysis, request)
        return result
    return _traverse_roots(graph, request, roots, direction=direction, max_depth=max_depth)


def _traverse_roots(graph, request, roots, *, direction, max_depth=None):
    """Depth-first bounded walk, with path-local cycles and shared-node references.

    Unique nodes are charged once per traversal; every inspected outgoing edge
    (including repeated expansions/boundaries) consumes traversal allowance. The
    request's existing counters/deadline are never reset. Cancellation propagates.
    """
    from models.project_graph import GraphTraversal, TraversalStep
    from models.project_relationships import RelationshipKind, SymbolKind
    from services.project_analysis_request import AnalysisBudgetExceeded
    if direction not in {"forward", "reverse"}:
        raise ValueError("Expected forward or reverse traversal.")
    depth_limit = request.budget.limits.depth if max_depth is None else max_depth
    if type(depth_limit) is not int or not 0 <= depth_limit <= request.budget.limits.depth:
        raise ValueError("Requested depth exceeds the request allowance.")
    _validate_analysis_owner(graph.analysis, request)
    roots = tuple(sorted(set(roots)))
    if not roots or not set(roots) <= set(graph.node_ids):
        raise ValueError("Unknown graph roots.")
    adjacency = {node: [] for node in graph.node_ids}
    for arc in graph.arcs:
        request.budget.check()
        origin, target = (arc.origin_id, arc.target_id) if direction == "forward" else (arc.target_id, arc.origin_id)
        adjacency[origin].append((target, arc.relationship_id))
    uncertain = {node: [] for node in graph.node_ids}
    modules = {s.definition.path: s.symbol_id for s in graph.analysis.symbols if s.kind == SymbolKind.MODULE}
    boundary_set = set(graph.boundary_ids)
    boundary_records = {}
    for record in graph.analysis.relationships:
        request.budget.check()
        identity = record.relationship_id
        if identity in boundary_set:
            boundary_records[identity] = record
    for identity, edge in boundary_records.items():
        request.budget.check()
        origin = modules[edge.origin.definition.path] if graph.kind == RelationshipKind.IMPORTS else edge.origin.symbol_id
        uncertain[origin].append(identity)
    steps, boundaries, cutoffs, charged, expanded, first_paths = [], set(), set(), set(), {}, {}

    def step(node, path, edges, kind, reference=()):
        steps.append(TraversalStep(node, path, edges, kind, reference))

    def walk(node, path, edges):
        request.budget.check()
        depth = len(edges)
        if node in path[:-1]:
            step(node, path, edges, "cycle", path[:path.index(node) + 1])
            return
        if node not in charged:
            try:
                request.budget.consume(visited_symbols=1)
            except AnalysisBudgetExceeded:
                step(node, path, edges, "node_cutoff")
                raise
            charged.add(node)
            first_paths[node] = path
        if direction == "forward":
            for identity in sorted(uncertain[node]):
                request.budget.consume(traversed_edges=1)
                boundaries.add(identity)
        if depth >= depth_limit and adjacency[node]:
            step(node, path, edges, "depth_cutoff")
            cutoffs.add("depth")
            return
        previous = expanded.get(node)
        if previous is not None and depth >= previous[0]:
            step(node, path, edges, "shared", previous[1])
            return
        revisited = first_paths[node] != path
        step(node, path, edges, "revisited" if previous or revisited else "root" if depth == 0 else "expanded",
             previous[1] if previous else first_paths[node] if revisited else ())
        expanded[node] = (depth, path)
        for target, identity in adjacency[node]:
            try:
                request.budget.consume(traversed_edges=1)
            except AnalysisBudgetExceeded:
                step(node, path, edges, "edge_cutoff")
                raise
            walk(target, path + (target,), edges + (identity,))

    try:
        for root in roots:
            walk(root, (root,), ())
        if direction == "reverse":
            # An unresolved call elsewhere may target any selected symbol. Keep
            # every uncertain edge in this graph as an explicit absence boundary.
            for identity in graph.boundary_ids:
                request.budget.consume(traversed_edges=1)
                boundaries.add(identity)
        request.budget.check()
    except AnalysisBudgetExceeded as exc:
        cutoffs.add(exc.resource)
    try:
        request.budget.check()  # cancellation is never swallowed by a budget outcome
    except AnalysisBudgetExceeded as exc:
        cutoffs.add(exc.resource)
    _validate_analysis_owner(graph.analysis, request, check_budget=False)
    return GraphTraversal(graph, direction, "resolved", roots, steps=tuple(steps),
                          boundary_ids=tuple(sorted(boundaries)), cutoff_reasons=tuple(sorted(cutoffs)))


def _normalize_path(path):
    """
    Normalize a filesystem path for consistent graph keys.
    """

    return path.replace("\\", "/")


def build_dependency_graph(
    include_tests=False,
):
    """
    Build a project-wide dependency graph.

    Each project file is represented as a graph node.
    Each import between project files becomes a directed edge.
    """

    from services.project_service import _project_files

    graph = {}

    project_files = [
    path
    for path in _project_files()
    if include_tests
    or classify_project_file(path) != "test"
    ]

    for file in project_files:

        normalized_file = _normalize_path(
            str(file)
        )

        graph[normalized_file] = {
            "dependencies": [],
            "dependents": [],
        }

    for file in project_files:

        normalized_file = _normalize_path(
            str(file)
        )

        result = get_file_dependencies(
            file.name
        )

        if result is None:
            continue

        for dependency in result["dependencies"]:

            dependency_path = _normalize_path(
                dependency["path"]
            )

            if dependency_path not in graph:
                continue

            if dependency_path not in graph[normalized_file]["dependencies"]:

                graph[normalized_file]["dependencies"].append(
                    dependency_path
                )

            if normalized_file not in graph[dependency_path]["dependents"]:

                graph[dependency_path]["dependents"].append(
                    normalized_file
                )

    return graph


def get_dependency_tree(
    filename,
    max_depth=3,
):
    """
    Return the dependency tree for a specific file.

    The traversal is depth-limited and cycle-safe.
    """

    from services.project_service import find_matching_files

    matches = find_matching_files(
        filename
    )

    if not matches:
        return None

    root = _normalize_path(
        str(matches[0])
    )

    graph = build_dependency_graph()

    if root not in graph:
        return None

    def walk(
        current,
        depth,
        visited,
    ):

        node = {
            "file": current,
            "depth": depth,
            "dependencies": [],
        }

        if depth >= max_depth:
            return node

        if current in visited:
            return node

        visited.add(current)

        for dependency in graph[current]["dependencies"]:

            child = walk(
                dependency,
                depth + 1,
                visited.copy(),
            )

            node["dependencies"].append(
                child
            )

        return node

    return walk(
        root,
        0,
        set(),
    )


def get_file_dependents(filename):
    """
    Return files that directly depend on the supplied file.
    """

    from services.project_service import find_matching_files

    matches = find_matching_files(
        filename
    )

    if not matches:
        return None

    file_path = _normalize_path(
        str(matches[0])
    )

    graph = build_dependency_graph()

    if file_path not in graph:
        return None

    return graph[file_path]["dependents"]


def format_dependency_tree(
    tree,
):
    """
    Convert a dependency tree into readable text.
    """

    if tree is None:
        return None

    lines = []

    def walk(node):

        indentation = "  " * node["depth"]

        lines.append(
            f"{indentation}- {node['file']}"
        )

        for dependency in node["dependencies"]:

            walk(dependency)

    walk(tree)

    return "\n".join(lines)
