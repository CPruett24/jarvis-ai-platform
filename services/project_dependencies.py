import ast
from pathlib import Path

from services.project_service import find_matching_files


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

    if module_path.exists():
        return module_path

    package_path = root.joinpath(
        *parts,
        "__init__.py",
    )

    if package_path.exists():
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

        content = file.read_text(
            encoding="utf-8",
            errors="ignore",
        )

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