import ast
import builtins
import inspect
from pathlib import Path

from models.project_relationships import RelationshipKind, RelationshipRecord, Resolution, SymbolKind


def resolve_source_calls(source, modules, import_bindings, request, *, tainted_paths=()):
    """Resolve C2 observations against extracted lexical definitions only.

    This is binding resolution, not a proof that a call executes. Receiver type
    inference, re-exports, inheritance and runtime binding changes are unsupported.
    """
    from services.project_dependencies import ImportObservation

    def lookup(scope, name):
        current = scope
        while current is not None:
            if name in current.blocked or current.wildcard:
                return [], "shadowed_reassigned_or_wildcard_binding", []
            bindings = current.bindings.get(name, [])
            if bindings:
                targets, supporting = [], []
                for binding in bindings:
                    if isinstance(binding, ImportObservation):
                        edge, target = import_bindings[id(binding)]
                        supporting.append(edge.location)
                        if target:
                            targets.append(target)
                        elif edge.resolution == Resolution.AMBIGUOUS:
                            for candidate in edge.candidates:
                                targets.extend(s for m in modules.values() for s in m.scopes
                                               if s.symbol == candidate)
                        else:
                            return [], edge.reason, supporting
                    else:
                        if binding.conditional:
                            return [], "conditional_definition", supporting
                        targets.append(binding)
                return targets, "lexical_or_imported_binding", supporting
            current = current.parent
            # Class namespaces do not form closures for methods/nested functions.
            while current is not None and current.symbol.kind == SymbolKind.CLASS:
                current = current.parent
        return [], "name_not_statically_bound", []

    def attribute(target, parts):
        owner = modules[target.symbol.definition.path]
        if target.symbol.kind == SymbolKind.MODULE:
            scopes = owner.scopes[0].bindings.get(parts[0], [])
            if any(isinstance(s, ImportObservation) for s in scopes):
                return [], "reexport_unsupported"
            if parts[0] in owner.scopes[0].blocked or owner.scopes[0].wildcard:
                return [], "reassigned_module_member"
            next_targets = scopes
        elif target.symbol.kind == SymbolKind.CLASS:
            next_targets = target.bindings.get(parts[0], [])
            if (parts[0] in target.blocked or target.node.decorator_list
                    or target.node.bases or target.node.keywords):
                return [], "reassigned_decorated_or_dynamic_class"
            if any(isinstance(s, ImportObservation) for s in next_targets):
                return [], "class_import_binding_unsupported"
        else:
            return [], "arbitrary_receiver_dispatch"
        if not next_targets:
            return [], "attribute_not_directly_defined_inheritance_unsupported"
        if any(s.conditional for s in next_targets):
            return [], "conditional_definition"
        if len(parts) == 1:
            return next_targets, "explicit_attribute_binding"
        found = []
        for candidate in next_targets:
            targets, reason = attribute(candidate, parts[1:])
            if not targets:
                return [], reason
            found.extend(targets)
        return found, "explicit_attribute_binding"

    for scope, node, dynamic_scope in source.calls:
        request.budget.check()
        expression = source.expression(node.func)
        parts, value = [], node.func
        while isinstance(value, ast.Attribute):
            parts.insert(0, value.attr)
            value = value.value
        targets, reason, supporting = [], "dynamic_callee_expression", []
        if isinstance(value, ast.Name):
            targets, reason, supporting = lookup(scope, value.id)
            if value.id in source.mutations:
                targets, reason = [], "monkey_patched_receiver"
            # `import pkg.module` binds pkg, whereas an alias binds pkg.module.
            if parts and targets:
                current = scope
                binding = None
                while current is not None and binding is None:
                    matches = current.bindings.get(value.id, [])
                    if len(matches) == 1 and isinstance(matches[0], ImportObservation):
                        binding = matches[0]
                    current = current.parent
                if binding is not None and isinstance(binding.node, ast.Import) and not binding.alias_node.asname:
                    prefix = binding.alias_node.name.split(".")[1:]
                    if parts[:len(prefix)] != prefix:
                        targets, reason = [], "module_prefix_not_supported"
                    else:
                        parts = parts[len(prefix):]
                resolved = []
                failed_receiver = False
                for target in targets:
                    found, reason = attribute(target, parts) if parts else ([target], reason)
                    failed_receiver = failed_receiver or not found
                    resolved.extend(found)
                targets = [] if failed_receiver else resolved
                if failed_receiver and len(resolved):
                    reason = "ambiguous_or_unsupported_receiver_binding"
        if dynamic_scope:
            targets, reason = [], "lambda_or_comprehension_scope_unsupported"
        unique = {target.symbol.symbol_id: target for target in targets}
        targets = list(unique.values())
        if len(targets) == 1:
            target = targets[0]
            owner = modules[target.symbol.definition.path]
            decorators = getattr(target.node, "decorator_list", [])
            if target.symbol.kind == SymbolKind.METHOD:
                static = (len(decorators) == 1 and isinstance(decorators[0], ast.Name)
                          and decorators[0].id in {"staticmethod", "classmethod"}
                          and decorators[0].id not in owner.scopes[0].bindings
                          and decorators[0].id not in owner.scopes[0].blocked
                          and target.parent is not None
                          and decorators[0].id not in target.parent.bindings
                          and decorators[0].id not in target.parent.blocked)
                if not parts or not static:
                    targets, reason = [], "instance_method_dispatch_unsupported"
            elif target.symbol.kind not in {SymbolKind.FUNCTION, SymbolKind.ASYNC_FUNCTION}:
                targets, reason = [], "target_is_not_a_supported_function"
            elif decorators:
                targets, reason = [], "decorated_function_binding_unsupported"
            if (target.conditional or target.symbol.qualified_name.split(".")[0] in owner.mutations
                    or target.symbol.definition.path in tainted_paths):
                targets, reason = [], "conditional_or_mutated_target"
        resolution = (Resolution.INCOMPLETE if reason in {"incomplete_inventory", "module_not_analyzed"} else
                      Resolution.CONFIRMED_STATIC if len(targets) == 1 else
                      Resolution.AMBIGUOUS if len(targets) > 1 else Resolution.UNRESOLVED)
        request.budget.consume(relationships=1)
        yield RelationshipRecord(RelationshipKind.CALLS, scope.symbol,
            targets[0].symbol if resolution == Resolution.CONFIRMED_STATIC else None,
            expression, source.location(node), resolution, reason,
            tuple(t.symbol for t in targets) if resolution == Resolution.AMBIGUOUS else (), tuple(supporting))

from services.project_analysis_cache import (
    get_source_tree,
    get_file_content,
)

from services.project_symbol_index import (
    build_symbol_index,
)

from services.project_service import (
    find_matching_files,
    _project_files,
)


def _normalize_path(path):
    """
    Normalize a filesystem path for consistent output.
    """

    return str(path).replace("\\", "/")


def _project_root():
    return Path(__file__).resolve().parent.parent


def _module_to_path(module_name):
    """
    Convert a project module name into a Python file path.

    Example:

        services.ai_service

    becomes:

        services/ai_service.py
    """

    parts = module_name.split(".")

    module_path = _project_root().joinpath(
        *parts
    ).with_suffix(".py")

    from services.project_service import _is_project_file
    if _is_project_file(module_path):
        return module_path

    package_path = _project_root().joinpath(
        *parts,
        "__init__.py",
    )

    if _is_project_file(package_path):
        return package_path

    return None


def _get_source_tree(path):
    """
    Return a cached AST for a Python file.
    """

    return get_source_tree(path)


def _extract_functions(tree):
    """
    Return function definitions from an AST.
    """

    functions = {}

    if tree is None:
        return functions

    for node in ast.walk(tree):

        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):

            functions[node.name] = node

    return functions


def _extract_imports(tree):
    """
    Build a mapping of imported names to modules.
    """

    imports = {}

    if tree is None:
        return imports

    for node in ast.walk(tree):

        if isinstance(node, ast.Import):

            for alias in node.names:

                local_name = (
                    alias.asname
                    or alias.name.split(".")[0]
                )

                imports[local_name] = {
                    "module": alias.name,
                    "name": None,
                }

        elif isinstance(node, ast.ImportFrom):

            if node.module is None:
                continue

            for alias in node.names:

                local_name = (
                    alias.asname
                    or alias.name
                )

                imports[local_name] = {
                    "module": node.module,
                    "name": alias.name,
                }

    return imports


def _extract_calls(function_node):
    """
    Extract function names called inside a function.
    """

    calls = []

    for node in ast.walk(function_node):

        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        function = node.func

        if isinstance(
            function,
            ast.Name,
        ):

            calls.append(
                {
                    "name": function.id,
                    "type": "name",
                }
            )

        elif isinstance(
            function,
            ast.Attribute,
        ):

            calls.append(
                {
                    "name": function.attr,
                    "type": "attribute",
                }
            )

        else:

            calls.append(
                {
                    "name": ast.unparse(function),
                    "type": "dynamic",
                }
            )

    return calls

def _is_standard_library(module_name):
    """
    Return True when a module belongs to Python's
    standard library.
    """

    if not module_name:
        return False

    top_level = module_name.split(
        ".",
        1,
    )[0]

    standard_library = {
        "abc",
        "argparse",
        "ast",
        "asyncio",
        "builtins",
        "collections",
        "contextlib",
        "csv",
        "dataclasses",
        "datetime",
        "enum",
        "functools",
        "glob",
        "hashlib",
        "inspect",
        "io",
        "itertools",
        "json",
        "logging",
        "math",
        "os",
        "pathlib",
        "re",
        "shutil",
        "sqlite3",
        "subprocess",
        "sys",
        "tempfile",
        "threading",
        "time",
        "traceback",
        "typing",
        "unittest",
        "urllib",
        "uuid",
        "warnings",
        "weakref",
    }

    return top_level in standard_library

def _get_imported_modules(
    file_path,
):
    """
    Return a mapping of local names to imported modules.

    Example:

        from ollama import chat

    becomes:

        {
            "chat": "ollama"
        }
    """

    path = Path(
        file_path
    )

    try:

        content = get_file_content(path)
        if content is None:
            return {}

    except Exception:
        return {}

    try:

        tree = ast.parse(
            content
        )

    except SyntaxError:
        return {}

    imports = {}

    for node in ast.walk(tree):

        if isinstance(
            node,
            ast.Import,
        ):

            for alias in node.names:

                local_name = (
                    alias.asname
                    or alias.name.split(
                        ".",
                        1,
                    )[0]
                )

                imports[
                    local_name
                ] = alias.name

        elif isinstance(
            node,
            ast.ImportFrom,
        ):

            if node.module is None:
                continue

            for alias in node.names:

                local_name = (
                    alias.asname
                    or alias.name
                )

                imports[
                    local_name
                ] = node.module

    return imports

def _classify_imported_module(
    module_name,
):
    """
    Classify an imported module.
    """

    if _is_standard_library(
        module_name
    ):

        return "standard_library"

    return "third_party"

def _is_builtin(name):
    """
    Return True when a call refers to a Python builtin.
    """

    return hasattr(
        builtins,
        name,
    )


def _classify_unresolved_call(
    call,
    imported_modules=None,
):
    """
    Classify a call that could not be resolved
    to a project function.
    """

    if imported_modules is None:
        imported_modules = {}

    name = call["name"]

    if (
        call["type"] == "name"
        and _is_builtin(name)
    ):

        return {
            "name": name,
            "type": "builtin",
        }

    root_name = name.split(
        ".",
        1,
    )[0]

    module_name = imported_modules.get(
        root_name
    )

    if module_name:

        category = _classify_imported_module(
            module_name
        )

        return {
            "name": name,
            "type": category,
            "module": module_name,
        }

    if call["type"] == "attribute":

        return {
            "name": name,
            "type": "external_or_runtime",
        }

    return {
        "name": name,
        "type": "dynamic",
    }

def _resolve_call(
    call,
    functions,
    imports,
):
    """
    Resolve a function call to a project function when possible.
    """

    name = call["name"]

    if call["type"] == "name":

        if name in functions:

            return {
                "kind": "local",
                "function": name,
                "module": None,
            }

        if name in imports:

            imported = imports[name]

            return _resolve_import(
                imported
            )

    return None


def _resolve_import(import_info):
    """
    Resolve an imported symbol to a project file.
    """

    module = import_info["module"]

    path = _module_to_path(
        module
    )

    if path is None:
        return None

    imported_name = import_info["name"]

    if imported_name is None:

        return {
            "kind": "module",
            "function": None,
            "module": module,
            "path": _normalize_path(path),
        }

    return {
        "kind": "project_function",
        "function": imported_name,
        "module": module,
        "path": _normalize_path(path),
    }

def _resolve_registry_tool(tool_name):
    """
    Resolve a JARVIS tool through COMMAND_REGISTRY.

    Returns the actual registered function and its
    source file when available.
    """

    try:

        from commands.registry import (
            COMMAND_REGISTRY,
        )

    except Exception:
        return None

    tool = COMMAND_REGISTRY.get(
        tool_name
    )

    if tool is None:
        return None

    function = tool.get(
        "function"
    )

    if function is None:
        return None

    try:

        source_file = inspect.getsourcefile(
            function
        )

    except (
        OSError,
        TypeError,
    ):

        source_file = None

    if source_file is None:
        return {
            "tool": tool_name,
            "function": function.__name__,
            "module": function.__module__,
            "path": None,
        }

    return {
        "tool": tool_name,
        "function": function.__name__,
        "module": function.__module__,
        "path": _normalize_path(
            source_file
        ),
    }

def resolve_registered_tool(
    tool_name,
):
    """
    Resolve a JARVIS tool to its actual
    registered implementation.
    """

    return _resolve_registry_tool(
        tool_name
    )

def trace_tool_execution(
    tool_name,
    max_depth=5,
):
    """
    Trace execution starting from a registered JARVIS tool.
    """

    resolved = resolve_registered_tool(
        tool_name
    )

    if resolved is None:
        return None

    if resolved["path"] is None:
        return {
            "tool": tool_name,
            "function": resolved["function"],
            "module": resolved["module"],
            "path": None,
            "trace": None,
        }

    path = Path(
        resolved["path"]
    )

    trace = trace_execution(
        path.name,
        resolved["function"],
        max_depth=max_depth,
    )

    return {
        "tool": tool_name,
        "function": resolved["function"],
        "module": resolved["module"],
        "path": resolved["path"],
        "trace": trace,
    }

def format_tool_execution_trace(
    result,
):
    """
    Format a registered tool execution trace.
    """

    if result is None:
        return None

    lines = [
        f"Tool: {result['tool']}",
        (
            f"Implementation: "
            f"{result['module']}."
            f"{result['function']}()"
        ),
    ]

    if result["path"] is not None:

        lines.append(
            f"Source: {result['path']}"
        )

    lines.append("")
    lines.append(
        "Execution path:"
    )

    if result["trace"] is None:

        lines.append(
            "  Unable to statically trace implementation."
        )

    else:

        trace = format_execution_trace(
            result["trace"]
        )

        for line in trace.splitlines():

            lines.append(
                f"  {line}"
            )

    return "\n".join(lines)

def get_function_calls(
    filename,
    function_name,
):
    """
    Analyze calls made by a specific function.
    """

    matches = find_matching_files(
        filename
    )

    if not matches:
        return None

    file = matches[0]

    if file.suffix.lower() != ".py":
        return None

    imported_modules = _get_imported_modules(
        file
    )

    tree = _get_source_tree(
        file
    )

    if tree is None:
        return None

    functions = _extract_functions(
        tree
    )

    function = functions.get(
        function_name
    )

    if function is None:
        return None

    imports = _extract_imports(
        tree
    )

    symbol_index = build_symbol_index(
        file,
        tree,
        functions,
        imports,
    )

    calls = _extract_calls(
        function
    )

    resolved_calls = []
    unresolved_calls = []

    for call in calls:

        resolved = _resolve_call(
            call,
            functions,
            imports,
        )

        if resolved is not None:

            resolved_calls.append(
                {
                    "call": call,
                    "target": resolved,
                }
            )

        else:

            unresolved_calls.append(
                _classify_unresolved_call(
                    call,
                    imported_modules,
                )
            )

    return {
        "file": _normalize_path(file),
        "function": function_name,
        "calls": calls,
        "resolved_calls": resolved_calls,
        "unresolved_calls": unresolved_calls,
        "symbol_index": symbol_index,
    }

def find_function_callers(
    filename,
    function_name,
):
    """
    Find project functions that call the specified function.

    Uses the cached project analysis index.
    """

    from services.project_analysis_index import (
        get_project_analysis_index,
        find_indexed_function_callers,
    )

    index = get_project_analysis_index()

    return find_indexed_function_callers(
        index,
        filename,
        function_name,
    )


def trace_execution(
    filename,
    function_name,
    max_depth=5,
):
    """
    Trace statically resolvable project function calls.

    Dynamic calls are recorded but are not guessed.
    """

    visited = set()

    def walk(
        current_file,
        current_function,
        depth,
    ):

        node = {
            "file": _normalize_path(
                current_file
            ),
            "function": current_function,
            "depth": depth,
            "category": "project",
            "calls": [],
            "unresolved_calls": [],
            "symbol_index": None,
        }

        if depth >= max_depth:
            return node

        key = (
            _normalize_path(current_file),
            current_function,
        )

        if key in visited:
            return node

        visited.add(key)

        result = get_function_calls(
            current_file.name,
            current_function,
        )

        if result is None:
            return node

        node["symbol_index"] = result[
            "symbol_index"
        ]

        node["unresolved_calls"] = (
            result["unresolved_calls"]
        )

        for resolved in result[
            "resolved_calls"
        ]:

            target = resolved["target"]

            if target["kind"] == "local":

                child_file = current_file
                child_function = target[
                    "function"
                ]

            elif target["kind"] == "project_function":

                child_path = Path(
                    target["path"]
                )

                child_file = child_path
                child_function = target[
                    "function"
                ]

            else:

                continue

            child = walk(
                child_file,
                child_function,
                depth + 1,
            )

            node["calls"].append(
                child
            )

        return node

    matches = find_matching_files(
        filename
    )

    if not matches:
        return None

    return walk(
        matches[0],
        function_name,
        0,
    )


def format_execution_trace(
    trace,
):
    """
    Convert an execution trace into readable
    architectural output.
    """

    if trace is None:
        return None

    lines = []

    def walk(node):

        indentation = (
            "  " * node["depth"]
        )

        lines.append(
            f"{indentation}- "
            f"[PROJECT] "
            f"{node['file']}::"
            f"{node['function']}()"
        )

        for unresolved in node[
            "unresolved_calls"
        ]:

            call_type = unresolved["type"]

            if call_type == "builtin":

                category = "PYTHON_BUILTIN"

            elif call_type == "standard_library":

                category = "STANDARD_LIBRARY"

            elif call_type == "third_party":

                category = "THIRD_PARTY"

            elif call_type == "external_or_runtime":

                category = "EXTERNAL/RUNTIME"

            else:

                category = "DYNAMIC"

            lines.append(
                f"{indentation}  "
                f"[{category}] "
                f"{unresolved['name']}"
            )

        for child in node["calls"]:

            walk(child)

    walk(trace)

    return "\n".join(lines)
