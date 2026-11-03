"""Bounded source windows and deterministic propositions for canonical C2 results.

Selection does not discover edges. Source windows have their own snapshot/range
IDs; explicit support mappings preserve the original canonical relationship IDs.
The earlier full-definition RelationshipAnswerEvidence contract stays unchanged.
"""
from dataclasses import asdict, replace
import io
import json
import tokenize

from models.project_graph import RelationshipGraph, GraphTraversal, PotentialImpact
from models.project_relationships import RelationshipKind, Resolution, SymbolKind, stable_id
from models.relationship_answer import (
    ApprovedProposition, EvidenceSupport, RelationshipEvidence, excerpt_identity,
)
from services.project_analysis_cache import read_analysis_source
from services.project_graph import _validate_analysis_owner


class RelationshipEvidenceError(ValueError):
    """Cannot safely support the requested claim set; never publish partial prose."""


def graph_value(value):
    if isinstance(value, PotentialImpact):
        return value.traversal.graph
    if isinstance(value, GraphTraversal):
        return value.graph
    if isinstance(value, RelationshipGraph):
        return value
    raise RelationshipEvidenceError("Unsupported relationship result.")


def validate_relationship_value(analysis, value, request):
    """Revalidate canonical membership, projection, direction, paths and certainty."""
    _validate_analysis_owner(analysis, request)
    graph = graph_value(value)
    if graph.analysis != analysis or graph.snapshot_id != analysis.snapshot.snapshot_id:
        raise RelationshipEvidenceError("Result is not from the supplied canonical analysis.")
    replace(graph)  # Re-run the existing strict canonical graph contract.
    trace = value.traversal if isinstance(value, PotentialImpact) else value if isinstance(value, GraphTraversal) else None
    if trace is not None:
        replace(trace)
        previous = set()
        for step in trace.steps:
            request.budget.check()
            repeated = step.node_id in step.path[:-1]
            if repeated != (step.classification == "cycle") or len(set(step.path[:-1])) != len(step.path[:-1]):
                raise RelationshipEvidenceError("Cycle classification is inconsistent with the path.")
            if step.classification == "cycle" and step.back_reference_path != step.path[:step.path.index(step.node_id) + 1]:
                raise RelationshipEvidenceError("Cycle does not reference its path-local ancestor.")
            if step.classification == "root" and len(step.path) != 1:
                raise RelationshipEvidenceError("A root cannot have an incoming path.")
            cutoff = {"depth_cutoff": "depth", "node_cutoff": "visited_symbols", "edge_cutoff": "traversed_edges"}.get(step.classification)
            if cutoff is not None and cutoff not in trace.cutoff_reasons:
                raise RelationshipEvidenceError("A traversal cutoff cannot be described as complete.")
            if step.classification in {"shared", "revisited"}:
                if step.back_reference_path not in previous or step.back_reference_path[-1] != step.node_id:
                    raise RelationshipEvidenceError("Invalid shared-node back-reference.")
                if (step.classification == "shared" and len(step.path) < len(step.back_reference_path)
                        or step.classification == "revisited" and len(step.path) >= len(step.back_reference_path)):
                    raise RelationshipEvidenceError("Shared/revisited depth qualification changed.")
            previous.add(step.path)
        if trace.status == "resolved" and not trace.cutoff_reasons:
            # A valid path prefix alone is not a complete trace. Check closure
            # independently so omitted callers/edges cannot become absence claims.
            adjacency = {node: [] for node in graph.node_ids}
            for arc in graph.arcs:
                origin, target = (arc.origin_id, arc.target_id) if trace.direction == "forward" else (arc.target_id, arc.origin_id)
                adjacency[origin].append((target, arc.relationship_id))
            pending, reachable, expected_edges = list(trace.root_ids), set(), set()
            while pending:
                request.budget.check()
                node = pending.pop()
                if node in reachable:
                    continue
                reachable.add(node)
                for target, identity in adjacency[node]:
                    request.budget.consume(traversed_edges=1)
                    expected_edges.add(identity)
                    pending.append(target)
            actual_edges = {identity for step in trace.steps for identity in step.relationship_path}
            if actual_edges != expected_edges or {step.node_id for step in trace.steps} != reachable:
                raise RelationshipEvidenceError("A trace omitted reachable confirmed relationships.")
            modules = {s.definition.path: s.symbol_id for s in analysis.symbols if s.kind == SymbolKind.MODULE}
            expected_boundaries = set()
            boundary_ids = set(graph.boundary_ids)
            for record in analysis.relationships:
                request.budget.check()
                if record.relationship_id not in boundary_ids:
                    continue
                origin = modules[record.origin.definition.path] if graph.kind == RelationshipKind.IMPORTS else record.origin.symbol_id
                if trace.direction == "reverse" or origin in reachable:
                    expected_boundaries.add(record.relationship_id)
            if set(trace.boundary_ids) != expected_boundaries:
                raise RelationshipEvidenceError("Uncertain boundaries were omitted from a traversal.")
    if isinstance(value, PotentialImpact):
        # Use the existing deterministic impact adapter, not supplied impact prose.
        from services.project_impact import _potential_impact
        if value != _potential_impact(value.traversal, request):
            raise RelationshipEvidenceError("Potential-impact conclusions were substituted.")
    return graph


def selected_relationship_ids(value):
    graph = graph_value(value)
    trace = value.traversal if isinstance(value, PotentialImpact) else value if isinstance(value, GraphTraversal) else None
    ids = ([a.relationship_id for a in graph.arcs] + list(graph.boundary_ids) if trace is None else
           [identity for step in trace.steps for identity in step.relationship_path] + list(trace.boundary_ids))
    return tuple(dict.fromkeys(ids))


def _support_specs(analysis, value, identities):
    records = {r.relationship_id: r for r in analysis.relationships}
    symbols = {s.symbol_id: s for s in analysis.symbols}
    specs = []
    def header(symbol, relationship_id=None):
        specs.append((relationship_id, symbol.symbol_id, "header", symbol.definition))
    for identity in identities:
        if identity not in records:
            raise RelationshipEvidenceError("Unknown relationship ID.")
        record = records[identity]
        specs.append((identity, None, "site", record.location))
        specs.extend((identity, None, "binding", source) for source in record.supporting_sources)
        header(record.origin, identity)
        if record.target is not None:
            header(record.target, identity)
        for candidate in record.candidates:
            header(candidate, identity)
    trace = value.traversal if isinstance(value, PotentialImpact) else value if isinstance(value, GraphTraversal) else None
    extra = trace.root_ids + trace.candidates if trace else (() if identities else graph_value(value).node_ids)
    for identity in extra:
        header(symbols[identity])
    return tuple(dict.fromkeys(specs))


def _header_end(text, start, maximum_end, kind):
    if kind == SymbolKind.MODULE:
        return start
    # Tokenize only to the first logical newline, including multiline signatures.
    # No importing, evaluation or execution of project code.
    try:
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type == tokenize.NEWLINE:
                return min(maximum_end, start + token.end[0] - 1)
    except (tokenize.TokenError, IndentationError):
        pass
    raise RelationshipEvidenceError("Definition header is incomplete.")


def _range_for(spec, source_text, text_start, symbols):
    _, symbol_id, role, source = spec
    end = source.end_line
    if role == "header":
        lines = source_text.split("\n")
        offset = source.start_line - text_start
        if offset < 0 or offset >= len(lines):
            raise RelationshipEvidenceError("Definition header is not covered.")
        end = _header_end("\n".join(lines[offset:]), source.start_line, source.end_line, symbols[symbol_id].kind)
    return source.start_line, end


def _label(symbol):
    from services.source_answer import _reference_text
    name = "module" if symbol.kind == SymbolKind.MODULE else symbol.qualified_name
    label = name + " in " + json.dumps(symbol.definition.path, ensure_ascii=False)
    if _reference_text(label) != label:
        raise RelationshipEvidenceError("Source label cannot survive strict citation normalization unchanged.")
    return label


def _propositions(analysis, value, identities, supports):
    records = {r.relationship_id: r for r in analysis.relationships}
    symbols = {s.symbol_id: s for s in analysis.symbols}
    propositions = []
    def add(kind, edge_ids, symbol_ids, text):
        source_ids = tuple(dict.fromkeys(s.excerpt_id for s in supports if
            s.relationship_id in edge_ids or s.relationship_id is None and s.symbol_id in symbol_ids))
        if not source_ids:
            raise RelationshipEvidenceError("Proposition lacks supporting source evidence.")
        identity = stable_id("P", [analysis.snapshot.snapshot_id, kind, edge_ids, symbol_ids, source_ids, text])
        propositions.append(ApprovedProposition(identity, kind, tuple(edge_ids), tuple(symbol_ids), source_ids, text))
    for identity in identities:
        record = records[identity]
        source, target = _label(record.origin), _label(record.target) if record.target else None
        noun = "call" if record.kind == RelationshipKind.CALLS else "import dependency"
        if record.resolution == Resolution.CONFIRMED_STATIC:
            verb = "calls" if record.kind == RelationshipKind.CALLS else "imports"
            text = f"Confirmed static {noun}: {source} {verb} {target}."
        elif record.resolution == Resolution.INFERRED:
            text = f"Inferred {noun} from {source}; a target is possible, not confirmed."
        elif record.resolution == Resolution.AMBIGUOUS:
            text = f"Ambiguous {noun} from {source}; no unique target was established."
        elif record.resolution == Resolution.INCOMPLETE:
            text = f"Incomplete {noun} resolution at {source}; the relationship is not established."
        else:
            text = f"Unresolved {noun} at {source}; dynamic or unsupported binding prevents a confirmed target."
        add("relationship", (identity,), (record.origin.symbol_id,) + ((record.target.symbol_id,) if record.target else ()), text)
    trace = value.traversal if isinstance(value, PotentialImpact) else value if isinstance(value, GraphTraversal) else None
    if trace is not None:
        relation = "call" if trace.graph.kind == RelationshipKind.CALLS else "import dependency"
        for step in trace.steps:
            if len(step.path) == 1:
                continue
            arrow = " -> " if trace.direction == "forward" else " <- "
            path = arrow.join(_label(symbols[node]) for node in step.path)
            qualification = {"cycle": " Cycle back-reference to an ancestor.",
                             "shared": " Shared descendant; refers to an earlier expansion.",
                             "revisited": " Shallower revisit of a previously reached symbol.",
                             "depth_cutoff": " Depth limit reached.", "node_cutoff": " Node limit reached.",
                             "edge_cutoff": " Edge limit reached."}.get(step.classification, "")
            add("trace", step.relationship_path, step.path,
                f"Static {trace.direction} {relation} path: {path}.{qualification}")
        for identity in trace.candidates:
            add("candidate", (), (identity,), f"Ambiguous target candidate: {_label(symbols[identity])}; no target was chosen.")
    if isinstance(value, PotentialImpact):
        for affected in value.affected:
            add("impact", affected.relationship_path, (affected.root_id, affected.symbol_id),
                f"Potentially affected: {_label(symbols[affected.symbol_id])}, through a confirmed reverse "
                f"{value.kind.value} connection to {_label(symbols[affected.root_id])}. Runtime breakage is not established.")
    if not propositions:
        roots = trace.root_ids if trace else graph_value(value).node_ids
        for identity in roots:
            text = f"Static analysis target: {_label(symbols[identity])}."
            if trace and trace.complete:
                text += " No confirmed relationships were found within this traversal scope."
            add("target", (), (identity,), text)
    return tuple(propositions)


def select_relationship_evidence(analysis, value, request):
    """All required claims must fit, otherwise fail closed instead of dropping support."""
    validate_relationship_value(analysis, value, request)
    identities = selected_relationship_ids(value)
    if len(identities) > min(32, request.budget.limits.selected_relationships):
        raise RelationshipEvidenceError("Required evidence exceeds 32 relationships.")
    request.budget.consume(selected_relationships=len(identities))
    specs = _support_specs(analysis, value, identities)
    paths = sorted({source.path for _, _, _, source in specs})
    if len(paths) > min(6, request.budget.limits.evidence_files):
        raise RelationshipEvidenceError("Required evidence exceeds the source-file allowance.")
    fingerprints = {f.path: f.digest for f in analysis.snapshot.fingerprints}
    files, ranges = {}, {}
    symbols = {s.symbol_id: s for s in analysis.symbols}
    for path in paths:
        request.check_authorization()
        request.budget.consume(evidence_files=1)
        fresh = read_analysis_source(request, path)
        if not fresh.success or not fresh.excerpts or fresh.excerpts[0].truncated:
            request.budget.check()
            raise RelationshipEvidenceError("Required source evidence is unavailable.")
        excerpt = fresh.excerpts[0]
        if excerpt.digest != fingerprints.get(path) or excerpt.total_lines == 0:
            raise RelationshipEvidenceError("Required source evidence changed or has no physical source lines.")
        files[path] = excerpt
        ranges[path] = []
    planned = []
    for spec in specs:
        request.budget.check()
        source = spec[3]
        start, end = _range_for(spec, files[source.path].text, 1, symbols)
        if end - start + 1 > 120:
            raise RelationshipEvidenceError("A required source range exceeds 120 lines.")
        ranges[source.path].append((start, end))
        planned.append((spec, start, end))
    excerpts = []
    for path in paths:
        merged = []
        for start, end in sorted(set(ranges[path])):
            if merged and start <= merged[-1][1] + 1 and max(end, merged[-1][1]) - merged[-1][0] + 1 <= 120:
                merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
            else:
                merged.append((start, end))
        for start, end in merged:
            source = files[path]
            excerpts.append(replace(source, source_id=excerpt_identity(analysis.snapshot.snapshot_id, path, start, end, source.digest),
                start_line=start, end_line=end, text="\n".join(source.text.split("\n")[start - 1:end]),
                truncated=start > 1 or end < source.total_lines))
    if len(excerpts) > min(8, request.budget.limits.evidence_excerpts):
        raise RelationshipEvidenceError("Required evidence exceeds eight excerpts.")
    if sum(len(e.text.encode("utf-8")) for e in excerpts) >= 12 * 1024:
        raise RelationshipEvidenceError("Required source text exceeds the 12 KiB target.")
    request.budget.consume(evidence_excerpts=len(excerpts))
    supports = []
    for spec, start, end in planned:
        identity, symbol_id, role, source = spec
        covering = next(e for e in excerpts if e.path == source.path and e.start_line <= start <= end <= e.end_line)
        supports.append(EvidenceSupport(identity, symbol_id, role, source, start, end, covering.source_id))
    propositions = _propositions(analysis, value, identities, supports)
    packet = RelationshipEvidence(analysis, value, analysis.snapshot.snapshot_id, identities,
                                  tuple(excerpts), tuple(supports), propositions)
    if len(json.dumps(organization_payload(packet), separators=(",", ":")).encode("utf-8")) > min(24 * 1024, request.budget.limits.payload_bytes):
        raise RelationshipEvidenceError("Approved proposition payload exceeds 24 KiB.")
    _validate_relationship_evidence(packet, request)
    return packet


def _validate_relationship_evidence(packet, request):
    """Validate canonical facts and exact source mappings, not arbitrary generated prose."""
    replace(packet)
    validate_relationship_value(packet.analysis, packet.value, request)
    if packet.relationship_ids != selected_relationship_ids(packet.value):
        raise RelationshipEvidenceError("Selected relationships were omitted or substituted.")
    if len(packet.relationship_ids) > 32:
        raise RelationshipEvidenceError("Selected relationship ceiling exceeded.")
    expected = _support_specs(packet.analysis, packet.value, packet.relationship_ids)
    fingerprints = {f.path: f.digest for f in packet.analysis.snapshot.fingerprints}
    symbols = {s.symbol_id: s for s in packet.analysis.symbols}
    sources = {e.source_id: e for e in packet.excerpts}
    if len(sources) != len(packet.excerpts) or len(packet.excerpts) > 8 or len({e.path for e in packet.excerpts}) > 6:
        raise RelationshipEvidenceError("Invalid excerpt identities or limits.")
    if sum(len(e.text.encode("utf-8")) for e in packet.excerpts) >= 12 * 1024:
        raise RelationshipEvidenceError("Source text allowance exceeded.")
    for excerpt in packet.excerpts:
        replace(excerpt)
        project = packet.analysis.snapshot.project
        if (excerpt.project_id != project.project_id or excerpt.revision != project.authorization_revision
                or excerpt.digest != fingerprints.get(excerpt.path) or excerpt.end_line - excerpt.start_line + 1 > 120
                or type(excerpt.truncated) is not bool
                or excerpt.truncated != (excerpt.start_line > 1 or excerpt.end_line < excerpt.total_lines)
                or excerpt.total_lines < excerpt.end_line or excerpt.source_id != excerpt_identity(
                    packet.snapshot_id, excerpt.path, excerpt.start_line, excerpt.end_line, excerpt.digest)):
            raise RelationshipEvidenceError("Source range, fingerprint or snapshot identity does not match.")
    actual = []
    for support in packet.supports:
        request.budget.check()
        replace(support)
        excerpt = sources.get(support.excerpt_id)
        if (excerpt is None or support.canonical.project != packet.analysis.snapshot.project
                or excerpt.path != support.canonical.path or excerpt.digest != support.canonical.digest
                or not excerpt.start_line <= support.start_line <= support.end_line <= excerpt.end_line):
            raise RelationshipEvidenceError("Support does not match its source excerpt.")
        spec = (support.relationship_id, support.symbol_id, support.role, support.canonical)
        if spec not in expected or (support.start_line, support.end_line) != _range_for(
                spec, excerpt.text, excerpt.start_line, symbols):
            raise RelationshipEvidenceError("Canonical support or header range was substituted.")
        actual.append(spec)
    if len(actual) != len(expected) or set(actual) != set(expected):
        raise RelationshipEvidenceError("Required relationship evidence is missing.")
    if packet.propositions != _propositions(packet.analysis, packet.value, packet.relationship_ids, packet.supports):
        raise RelationshipEvidenceError("Approved factual propositions were changed.")
    if not packet.propositions:
        raise RelationshipEvidenceError("No source-backed propositions are available.")
    request.check_authorization()


def validate_relationship_evidence(packet, request):
    """Public validation also checks actual source text, not just declared digests."""
    _validate_relationship_evidence(packet, request)
    fresh_files = {}
    for excerpt in packet.excerpts:
        request.check_authorization()
        if excerpt.path not in fresh_files:
            fresh = read_analysis_source(request, excerpt.path)
            if not fresh.success or not fresh.excerpts or fresh.excerpts[0].truncated:
                request.budget.check()
                raise RelationshipEvidenceError("Required source evidence is unavailable.")
            fresh_files[excerpt.path] = fresh.excerpts[0]
        actual = fresh_files[excerpt.path]
        text = "\n".join(actual.text.split("\n")[excerpt.start_line - 1:excerpt.end_line])
        if (actual.digest != excerpt.digest or text != excerpt.text or actual.total_lines != excerpt.total_lines
                or actual.kind != excerpt.kind):
            raise RelationshipEvidenceError("Selected source text or digest is stale or substituted.")
    request.check_authorization()


def organization_payload(packet):
    """The organizer sees IDs and fixed categories, never source text or identifiers."""
    return {"snapshot_id": packet.snapshot_id, "approved_propositions": [
        {"id": p.proposition_id, "kind": p.kind} for p in packet.propositions]}
