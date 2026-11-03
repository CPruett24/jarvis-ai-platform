import ast
from dataclasses import dataclass
from pathlib import Path

from models.project_relationships import RelationshipRecord, RelationshipKind, Resolution, SymbolKind

from services.project_service import find_matching_files
from services.project_analysis_cache import get_file_content


@dataclass
class ImportObservation:
    scope: object
    node: ast.AST
    alias_node: ast.alias
    conditional: bool
    source: object

    @property
    def bound_name(self):
        return self.alias_node.asname or (self.alias_node.name.split(".")[0]
            if isinstance(self.node, ast.Import) else self.alias_node.name)


@dataclass(frozen=True, kw_only=True)
class ImportRelationshipRecord(RelationshipRecord):
    """C2 import metadata; extends the unchanged Checkpoint 1 edge contract."""
    imported_module: str | None
    imported_member: str | None
    relative_level: int
    alias: str | None
    bound_name: str
    lexical_scope: str


def resolve_source_import(observation, modules, inventory, *, inventory_complete=True, require_all_candidates=False):
    """Resolve only inventory-backed modules and directly defined members.

    No runtime imports, installed-package lookup or re-export execution. Return
    the edge plus binding target (a lexical scope) for subsequent call resolution.
    """
    node, alias, source = observation.node, observation.alias_node, observation.source
    member = alias.name if isinstance(node, ast.ImportFrom) else None
    name = node.module if member is not None else alias.name
    level = node.level if member is not None else 0
    reason = "project_import"
    candidates = []
    if level:
        package = source.excerpt.path.split("/")[:-1]
        if level > len(package):
            reason = "relative_import_outside_package"
        else:
            name = ".".join(package[:len(package) - level + 1] + ([name] if name else []))
    if reason == "project_import":
        stem = (name or "").replace(".", "/")
        paths = [p for p in (stem + ".py", stem + "/__init__.py") if p in inventory]
        available = [modules[p] for p in paths if p in modules]
        if require_all_candidates and any(p not in modules for p in paths):
            # C3 subset analysis cannot disambiguate a module/package by failing
            # to read the other inventory-backed candidate. C2 keeps its default.
            available = []
        if not available:
            reason = "module_not_analyzed" if paths else "module_not_in_authorized_inventory"
        elif member is None:
            candidates = [m.scopes[0] for m in available]
        elif member == "*":
            reason = "wildcard_import_unsupported"
        else:
            bindings = [binding for m in available for binding in m.scopes[0].bindings.get(member, [])]
            if any(isinstance(binding, ImportObservation) for binding in bindings):
                reason = "reexport_unsupported"
            elif any(member in m.scopes[0].blocked or m.scopes[0].wildcard for m in available):
                reason = "reassigned_or_wildcard_module_member"
            else:
                candidates = [b for b in bindings if b.symbol.kind in {
                    SymbolKind.FUNCTION, SymbolKind.ASYNC_FUNCTION, SymbolKind.CLASS}]
                if not candidates:
                    child = stem + "/" + member
                    child_paths = [p for p in (child + ".py", child + "/__init__.py") if p in inventory]
                    candidates = [modules[p].scopes[0] for p in (child + ".py", child + "/__init__.py")
                                  if p in modules]
                    reason = "imported_member_not_defined" if not candidates else "project_submodule_import"
                    if require_all_candidates and any(p not in modules for p in child_paths):
                        candidates, reason = [], "module_not_analyzed"
        if require_all_candidates and len(paths) > 1 and all(p in modules for p in paths):
            # Even two parsed alternatives cannot be narrowed by which one
            # happens to define the requested member. No runtime import proof.
            candidates, reason = [], "ambiguous_module_path"
    target = candidates[0] if len(candidates) == 1 else None
    resolution = Resolution.CONFIRMED_STATIC if target else (
        Resolution.AMBIGUOUS if len(candidates) > 1 else Resolution.UNRESOLVED)
    if observation.conditional:
        target, resolution, reason = None, Resolution.UNRESOLVED, "conditional_import_binding"
        candidates = []
    if target and target.conditional:
        target, resolution, reason = None, Resolution.UNRESOLVED, "conditional_imported_definition"
        candidates = []
    if not inventory_complete or reason == "module_not_analyzed":
        target, candidates, resolution = None, [], Resolution.INCOMPLETE
        reason = "incomplete_inventory" if not inventory_complete else reason
    edge = ImportRelationshipRecord(kind=RelationshipKind.IMPORTS, origin=observation.scope.symbol,
        target=target.symbol if target else None, expression=source.expression(node),
        location=source.location(alias), resolution=resolution, reason=reason,
        candidates=tuple(c.symbol for c in candidates) if resolution == Resolution.AMBIGUOUS else (),
        supporting_sources=(source.location(node),),
        imported_module=node.module if member is not None else alias.name,
        imported_member=member, relative_level=level, alias=alias.asname,
        bound_name=observation.bound_name, lexical_scope=observation.scope.symbol.qualified_name)
    return edge, target


def _resolve_module_path(module_name):
    """
    Resolve a Python module name to a project file.

    Example:

        services.ai_service
        ->
        services/ai_service.py
    """

    parts = module_name.split(".")

    root = Path(__file__).resolve().parent.parent

    module_path = root.joinpath(
        *parts
    ).with_suffix(".py")

    from services.project_service import _is_project_file
    if _is_project_file(module_path):
        return module_path

    package_path = root.joinpath(
        *parts,
        "__init__.py",
    )

    if _is_project_file(package_path):
        return package_path

    return None


def _extract_imports(content):
    """
    Extract Python imports using the AST parser.

    Returns a list of module names.
    """

    try:
        tree = ast.parse(content)

    except SyntaxError:
        return []

    imports = []

    for node in ast.walk(tree):

        if isinstance(node, ast.Import):

            for alias in node.names:

                imports.append(
                    alias.name
                )

        elif isinstance(node, ast.ImportFrom):

            if node.module:

                imports.append(
                    node.module
                )

    return imports


def get_file_dependencies(filename):
    """
    Analyze a Python file and return its project dependencies.
    """

    matches = find_matching_files(
        filename
    )

    if not matches:
        return None

    file = matches[0]

    if file.suffix.lower() != ".py":
        return None

    try:

        content = get_file_content(file)
        if content is None:
            return None

    except Exception:
        return None

    imports = _extract_imports(
        content
    )

    dependencies = []

    external_imports = []

    for module_name in imports:

        module_path = _resolve_module_path(
            module_name
        )

        if module_path is None:

            external_imports.append(
                module_name
            )

            continue

        dependencies.append(
            {
                "module": module_name,
                "path": str(module_path),
            }
        )

    return {
        "file": str(file),
        "filename": file.name,
        "imports": imports,
        "dependencies": dependencies,
        "external_imports": external_imports,
    }
