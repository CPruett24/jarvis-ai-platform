"""Pure C3 conversational admission grammar; not registered in live routing."""
import re

from models.project_scope import ScopeKind
from models.scoped_answer import ScopedCallerIntent
from services.code_intent import _relationship_project_qualifier, relationship_target


def parse_scoped_caller_request(command):
    """Recognize direct caller requests without lowercasing identifiers or paths.

    None leaves other C2/conversation requests untouched. A non-direct intent
    marks an explicit deferral; it is never downgraded to a direct query.
    """
    if not isinstance(command, str):
        return None
    if len(command) > 4096:
        return ScopedCallerIntent(error="request_too_long")
    original = re.sub(r"^(?:can you |could you |please )", "", command.strip().rstrip(".!?"), flags=re.I)
    text, project = _relationship_project_qualifier(original)
    project_scope = text != original
    scope_kind = ScopeKind.PROJECT_PYTHON if project_scope else None
    scope_path, current_file, scope_error = None, False, ""

    def scope(value):
        value = value.strip().strip("`\"'")
        if value.casefold() == "this file":
            return ScopeKind.FILES, None, True
        file = re.fullmatch(r"(?:the )?file (.+)", value, re.I)
        directory = re.fullmatch(r"(?:the )?(?:directory|folder) (.+)", value, re.I)
        if file:
            return ScopeKind.FILES, file[1].strip().strip("`\"'"), False
        if directory:
            return ScopeKind.DIRECTORY, directory[1].strip().strip("`\"'"), False
        return (ScopeKind.FILES if value.lower().endswith(".py") else ScopeKind.DIRECTORY), value, False

    prefix = re.match(r"^(within|in) (.+?),\s*(.+)$", text, re.I)
    if prefix:
        if prefix[1].lower() == "in" and not re.match(r"^(?:this file$|(?:the )?(?:file|directory|folder) )", prefix[2], re.I):
            scope_error = "scope_type_required"
        scope_kind, scope_path, current_file = scope(prefix[2])
        text = prefix[3]
    suffix = re.search(r"\s+(within|in) ((?:this file|(?:the )?(?:file|directory|folder) .+)|[^\s,]+)$", text, re.I)
    if suffix:
        if prefix:
            scope_error = "multiple_scope_declarations"
        if suffix[1].lower() == "in" and not re.match(r"^(?:this file$|(?:the )?(?:file|directory|folder) )", suffix[2], re.I):
            scope_error = scope_error or "scope_type_required"
        scope_kind, scope_path, current_file = scope(suffix[2])
        text = text[:suffix.start()]
    metadata = dict(project_qualifier=project.get("project_qualifier"), scope_kind=scope_kind,
                    scope_path=scope_path, current_file=current_file)
    transitive = (r"^(?:trace\b|(?:show|list)(?: me)? (?:the )?(?:caller chains?|"
                  r"(?:transitive|recursive|indirect|upstream) callers?)\b|"
                  r"(?:what|which) (?:functions|methods) (?:directly or indirectly|transitively|indirectly|recursively) call\b|"
                  r"(?:what|who) (?:directly or indirectly|transitively|indirectly|recursively) calls\b)")
    if re.search(transitive, text, re.I):
        return ScopedCallerIntent(direct=False, **metadata)
    pattern = (r"(?:(?:what|which) (?:functions|methods) (?:directly )?call|"
               r"(?:what|who) (?:directly )?calls|(?:show|list)(?: me)? (?:direct )?callers of)(?:\s+(.*))?")
    match = re.fullmatch(pattern, text, re.I)
    if not match:
        return None
    target = relationship_target(match[1] or "")
    return ScopedCallerIntent(qualified_name=target.get("qualified_name"), filename=target.get("filename"),
        error=scope_error or ("target_required" if target.get("target_error") or not target.get("qualified_name") else ""),
        **metadata)
