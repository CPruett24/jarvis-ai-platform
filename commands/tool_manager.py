from commands.registry import COMMAND_REGISTRY


def execute_tool(tool_name):

    print(f"[Tool Manager] Executing: {tool_name}")

    tool = COMMAND_REGISTRY.get(tool_name)

    if tool is None:
        print(f"[Tool Manager] Unknown tool: {tool_name}")
        return False

    try:

        tool["function"]()

        print(f"[Tool Manager] Completed: {tool_name}")

        return True

    except Exception as e:

        print(f"[Tool Manager] Error executing {tool_name}: {e}")

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