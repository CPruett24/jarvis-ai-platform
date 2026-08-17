from pathlib import Path


def build_symbol_index(
    file_path,
    tree,
    functions,
    imports,
):
    """
    Build a structured representation of symbols
    contained in a Python source file.
    """

    path = Path(file_path)

    function_symbols = []

    for name, node in functions.items():

        function_symbols.append(
            {
                "name": name,
                "line": node.lineno,
                "end_line": getattr(
                    node,
                    "end_lineno",
                    node.lineno,
                ),
            }
        )

    import_symbols = []

    for name, module in imports.items():

        if isinstance(module, dict):

            module_name = module.get(
                "module"
            )

        else:

            module_name = module

        import_symbols.append(
            {
                "name": name,
                "module": module_name,
            }
        )

    class_symbols = []

    for node in tree.body:

        if node.__class__.__name__ != "ClassDef":
            continue

        class_symbols.append(
            {
                "name": node.name,
                "line": node.lineno,
                "end_line": getattr(
                    node,
                    "end_lineno",
                    node.lineno,
                ),
            }
        )

    return {
        "file": str(
            path.resolve()
        ),
        "functions": function_symbols,
        "classes": class_symbols,
        "imports": import_symbols,
    }


def find_function(
    index,
    function_name,
):
    """
    Find a function in a symbol index.
    """

    for function in index["functions"]:

        if function["name"] == function_name:
            return function

    return None


def find_class(
    index,
    class_name,
):
    """
    Find a class in a symbol index.
    """

    for class_info in index["classes"]:

        if class_info["name"] == class_name:
            return class_info

    return None