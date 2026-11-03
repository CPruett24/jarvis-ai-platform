from pathlib import Path
import ast
from dataclasses import dataclass, field

from models.project_relationships import SourceLocation, SymbolKind, SymbolRecord


@dataclass
class LexicalScope:
    """Operation-local extraction state, never a published/cached contract."""
    symbol: SymbolRecord
    node: ast.AST
    parent: object = None
    bindings: dict = field(default_factory=dict)
    blocked: set = field(default_factory=set)
    wildcard: bool = False
    conditional: bool = False


@dataclass
class ScopedModule:
    excerpt: object
    project: object
    scopes: list = field(default_factory=list)
    calls: list = field(default_factory=list)
    imports: list = field(default_factory=list)
    mutations: set = field(default_factory=set)

    def location(self, node):
        return SourceLocation(self.project, self.excerpt.path, self.excerpt.source_id,
            self.excerpt.digest, node.lineno, node.end_lineno, node.col_offset, node.end_col_offset)

    def expression(self, node):
        return ast.get_source_segment(self.excerpt.text, node) or ast.unparse(node)


def extract_scoped_symbols(tree, excerpt, request):
    """Extract Python lexical scopes and observations without executing source.

    Names are qualified by their lexical owners. Definitions have their own
    bodies; defaults/decorators/bases are evaluated in the enclosing scope.
    Unsupported binding constructs are retained conservatively, never guessed.
    """
    from services.project_dependencies import ImportObservation
    module = ScopedModule(excerpt, request.identity)
    definition = SourceLocation.from_excerpt(request.identity, excerpt)
    module.scopes.append(LexicalScope(SymbolRecord("<module>", SymbolKind.MODULE, definition), tree))

    class Visitor(ast.NodeVisitor):
        scope = module.scopes[0]
        conditional = 0
        dynamic = 0

        def visit(self, node):
            request.budget.check()
            return super().visit(node)

        def define(self, node, kind):
            parent = self.scope
            prefix = "" if parent.symbol.kind == SymbolKind.MODULE else parent.symbol.qualified_name + (
                "." if parent.symbol.kind == SymbolKind.CLASS else ".<locals>.")
            record = SymbolRecord(prefix + node.name, kind, module.location(node))
            child = LexicalScope(record, node, parent, conditional=bool(self.conditional))
            module.scopes.append(child)
            parent.bindings.setdefault(node.name, []).append(child)
            # Defaults, annotations, decorators and bases belong to the defining
            # environment, not the new function's runtime body.
            for decorator in node.decorator_list:
                self.visit(decorator)
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    self.visit(base)
                for keyword in node.keywords:
                    self.visit(keyword.value)
            else:
                for value in node.args.defaults + [v for v in node.args.kw_defaults if v is not None]:
                    self.visit(value)
                args = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
                args += [arg for arg in (node.args.vararg, node.args.kwarg) if arg is not None]
                child.blocked.update(arg.arg for arg in args)
                for annotation in [arg.annotation for arg in args] + [node.returns]:
                    if annotation is not None:
                        self.visit(annotation)
            previous_conditional = self.conditional
            self.scope, self.conditional = child, 0
            for statement in node.body:
                self.visit(statement)
            self.scope, self.conditional = parent, previous_conditional

        def visit_FunctionDef(self, node):
            kind = SymbolKind.METHOD if self.scope.symbol.kind == SymbolKind.CLASS else SymbolKind.FUNCTION
            self.define(node, kind)

        def visit_AsyncFunctionDef(self, node):
            kind = SymbolKind.METHOD if self.scope.symbol.kind == SymbolKind.CLASS else SymbolKind.ASYNC_FUNCTION
            self.define(node, kind)

        def visit_ClassDef(self, node):
            self.define(node, SymbolKind.CLASS)

        def import_statement(self, node):
            for alias in node.names:
                observation = ImportObservation(self.scope, node, alias, bool(self.conditional), module)
                module.imports.append(observation)
                if alias.name == "*":
                    self.scope.wildcard = True
                else:
                    self.scope.bindings.setdefault(observation.bound_name, []).append(observation)

        visit_Import = import_statement
        visit_ImportFrom = import_statement

        def visit_Call(self, node):
            if ((isinstance(node.func, ast.Name) and node.func.id in {"setattr", "delattr", "vars"}
                 or isinstance(node.func, ast.Attribute) and node.func.attr in {"__setattr__", "__delattr__"})
                    and node.args):
                if isinstance(node.args[0], ast.Name):
                    module.mutations.add(node.args[0].id)
            if isinstance(node.func, ast.Name) and node.func.id in {"exec", "eval", "globals", "locals"}:
                module.scopes[0].wildcard = True
            module.calls.append((self.scope, node, bool(self.dynamic)))
            self.generic_visit(node)

        def visit_Name(self, node):
            if isinstance(node.ctx, (ast.Store, ast.Del)):
                self.scope.blocked.add(node.id)

        def visit_Attribute(self, node):
            if isinstance(node.ctx, (ast.Store, ast.Del)):
                root = node.value
                while isinstance(root, (ast.Attribute, ast.Subscript)):
                    root = root.value
                if isinstance(root, ast.Name):
                    module.mutations.add(root.id)
            self.generic_visit(node)

        visit_Subscript = visit_Attribute

        def visit_Global(self, node):
            self.scope.blocked.update(node.names)
            module.scopes[0].blocked.update(node.names)

        visit_Nonlocal = visit_Global

        def visit_MatchAs(self, node):
            if node.name:
                self.scope.blocked.add(node.name)
            self.generic_visit(node)

        visit_MatchStar = visit_MatchAs

        def visit_MatchMapping(self, node):
            if node.rest:
                self.scope.blocked.add(node.rest)
            self.generic_visit(node)

        def visit_ExceptHandler(self, node):
            if node.name:
                self.scope.blocked.add(node.name)
            self.conditional += 1
            self.generic_visit(node)
            self.conditional -= 1

        def conditional_block(self, node):
            self.conditional += 1
            self.generic_visit(node)
            self.conditional -= 1

        visit_If = conditional_block
        visit_For = conditional_block
        visit_AsyncFor = conditional_block
        visit_While = conditional_block
        visit_Try = conditional_block
        visit_TryStar = conditional_block
        visit_With = conditional_block
        visit_AsyncWith = conditional_block
        visit_Match = conditional_block

        def dynamic_scope(self, node):
            self.dynamic += 1
            self.generic_visit(node)
            self.dynamic -= 1

        visit_Lambda = dynamic_scope
        visit_ListComp = dynamic_scope
        visit_SetComp = dynamic_scope
        visit_DictComp = dynamic_scope
        visit_GeneratorExp = dynamic_scope

    Visitor().visit(tree)
    return module


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
