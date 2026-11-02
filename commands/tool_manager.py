from commands.registry import COMMAND_REGISTRY
from models.tool_request import ToolRequest


def execute_tool(request):

    if isinstance(request, str):

        request = ToolRequest(
            tool=request
        )

    tool_name = request.tool

    if tool_name in {"summarize_file", "explain_file"}:
        # Preserve legacy routing entry points while enforcing capability state
        # and returning evidence through the same C1 presentation path.
        from services.project_access import get_project
        from commands.router import execute_registered_capability
        context = get_project()
        operation = "summary" if tool_name == "summarize_file" else "read"
        filename = request.arguments.get("filename")
        question = f"Explain {filename} at detail level {request.arguments.get('depth', 1)}."
        result = execute_registered_capability("project_source", arguments={
            "filename": filename, "question": question, "operation": operation,
            "project_id": context.project_id, "authorization_revision": context.revision,
            "detail_depth": request.arguments.get("depth", 1)})
        return result.success

    print(f"[Tool Manager] Executing: {tool_name}")

    tool = COMMAND_REGISTRY.get(tool_name)

    if tool is None:

        print(f"[Tool Manager] Unknown tool: {tool_name}")

        return False

    try:

        arguments = request.arguments

        print(f"[Tool Manager] Arguments: {arguments}")

        if arguments:
            tool["function"](**arguments)
        else:
            tool["function"]()

        print(f"[Tool Manager] Completed: {tool_name}")

        return True

    except Exception as e:

        print(
            f"[Tool Manager] Error executing {tool_name}: {e}"
        )

        return False
    
def get_tool(tool_name):

    return COMMAND_REGISTRY.get(tool_name)


def get_available_tools():

    return COMMAND_REGISTRY


def tool_exists(tool_name):

    return tool_name in COMMAND_REGISTRY

def get_tool_descriptions():

    descriptions = []

    for tool_name, tool in COMMAND_REGISTRY.items():

        descriptions.append(
            f"{tool_name}: {tool['description']}"
        )

    return "\n".join(descriptions)
