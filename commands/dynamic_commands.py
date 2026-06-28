from commands.actions import (
    remember_command,
    search_memory_command,
    forget_memory_command,
)


def process_dynamic_command(command):

    if command.startswith("remember"):
        remember_command(command)
        return True

    if command.startswith("what do you remember about"):
        search_memory_command(command)
        return True

    if command.startswith("forget"):
        forget_memory_command(command)
        return True

    return False