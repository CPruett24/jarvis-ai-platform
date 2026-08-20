from services.ai_service import (
    ask_ai,
    detect_tool,
    stream_ai_response,
    explain_impact,
)
from services.speaker import speak
from commands.static_commands import COMMANDS
from commands.dynamic_commands import process_dynamic_command
from commands.tool_manager import execute_tool
from services.command_parser import parse_command

from services.conversation_manager import (
    has_pending_request,
    complete_pending_request,
    is_follow_up,
    resolve_follow_up,
    is_topic_switch,
    resolve_topic_switch,
    get_topic,
)

from services.code_intent import (
    is_code_question,
    is_contextual_code_question,
)

from services.project_service import get_file_content
from services.code_assistant import answer_question
from services.intent_resolver import resolve_intent

from services.conversation_speech import (
    ConversationSpeech,
)

from services.conversation_interrupt import (
    ConversationInterruptController,
)

from services.listener import (
    SpeechInterruptMonitor,
)

from services.project_impact import (
    explain_function_impact,
)

from services.project_state import (
    refresh_project_analysis_if_changed,
)

from services.capability_service import resolve_capability

from services.capability_request import (
    detect_capability_request,
)

from services.capability_service import (
    explain_capability_availability,
    get_registered_capability,
)

import queue
import threading
import time

ALIASES = {
    "open chat gpt": "open chatgpt",
    "open chat g p t": "open chatgpt",

    "what's the time": "what time is it",
    "tell me the time": "what time is it",
    "what time is it right now": "what time is it",
    "can you tell me the time": "what time is it",

    "hi": "hello",
    "hey": "hello",

    "where are we": "where am i",
    "what folder am i in": "where am i",

    "show files": "list files",
    "show me the files": "list files",

    "computer information": "tell me about this computer",
    "system information": "tell me about this computer",

    "current branch": "what branch am i on",

    "repository status": "git status",
    "repo status": "git status",

    "python version": "what version of python am i running",

    "current project": "what project am i in",
}

def _stream_with_interrupt(
    command,
    interrupt_controller,
):
    """
    Run the Ollama stream in a background thread so the
    router remains responsive to microphone interruptions.

    Returns normally when the stream completes.
    Stops yielding immediately when an interruption occurs.
    """

    chunks = queue.Queue()
    finished = object()

    def producer():

        try:

            for chunk in stream_ai_response(command):

                chunks.put(chunk)

        except Exception as exc:

            chunks.put(exc)

        finally:

            chunks.put(finished)

    thread = threading.Thread(
        target=producer,
        daemon=True,
    )

    thread.start()

    while True:

        # Check the interruption BEFORE waiting for another
        # Ollama chunk.
        if interrupt_controller.was_interrupted():
            return

        try:

            item = chunks.get(
                timeout=0.05
            )

        except queue.Empty:

            continue

        if item is finished:
            return

        if isinstance(item, Exception):
            raise item

        yield item

INTERRUPTION_PREFIX = "__JARVIS_INTERRUPTION__:"


def process_streaming_conversation(command):

    print("Calling streaming conversation AI...")

    speech = ConversationSpeech()

    interrupt_controller = (
        ConversationInterruptController(
            speech
        )
    )

    interrupt_monitor = SpeechInterruptMonitor(
        interrupt_controller.handle_speech
    )

    full_response = ""

    try:

        interrupt_monitor.start()

        for chunk in _stream_with_interrupt(
            command,
            interrupt_controller,
        ):

            if interrupt_controller.was_interrupted():

                print(
                    "[Router] Conversation interrupted."
                )

                break

            if not chunk:
                continue

            full_response += chunk

            speech.add_chunk(chunk)

        # Critical race check after streaming.
        if interrupt_controller.was_interrupted():

            interrupted_text = (
                interrupt_controller
                .get_interrupted_text()
            )

            print(
                "[Router] Interrupted command:",
                interrupted_text,
            )

            speech.interrupt()

            return (
                INTERRUPTION_PREFIX
                + interrupted_text
            )

        speech.finish()

        while True:

            if interrupt_controller.was_interrupted():

                interrupted_text = (
                    interrupt_controller
                    .get_interrupted_text()
                )

                print(
                    "[Router] Interrupted while speaking:",
                    interrupted_text,
                )

                speech.interrupt()

                return (
                    INTERRUPTION_PREFIX
                    + interrupted_text
                )

            if speech.is_finished():

                break

            time.sleep(0.05)

        print(
            "AI returned:",
            full_response,
        )

        return full_response

    finally:

        interrupt_monitor.stop()

def normalize_interruption(command):
    """
    Normalize natural interruption phrases into the actual
    command the router should execute.

    Examples:
        "Wait, stop, what time is it?"
            -> "what time is it"

        "Wait stop what time is it"
            -> "what time is it"

        "Stop, open VS Code"
            -> "open vscode"
    """

    if not command:
        return ""

    command = command.lower().strip()

    # Normalize punctuation to spaces.
    command = command.replace(",", " ")
    command = command.replace(".", " ")
    command = command.replace("!", " ")
    command = command.replace("?", " ")

    # Collapse repeated whitespace.
    command = " ".join(
        command.split()
    )

    prefixes = [
        "wait stop",
        "wait",
        "stop",
        "hold on",
        "hang on",
    ]

    for prefix in prefixes:

        if command.startswith(prefix + " "):

            command = command[
                len(prefix):
            ].strip()

            break

        if command == prefix:

            return ""

    return command

def process(
    command,
    allow_interruption=True,
):
    """
    Main JARVIS command router.

    allow_interruption=False is used when processing a command
    that was captured by the interruption monitor. This prevents
    an interrupted command from starting another interruption
    monitor and creating a recursive conversation loop.
    """

    if not command:
        return

    command = command.lower().strip()

    # =========================================================
    # INTERRUPTION
    # =========================================================
    #
    # Interruption commands must be handled BEFORE intent
    # resolution. Otherwise the interruption wrapper gets sent
    # through the normal AI/conversation routing path.
    #
    if command.startswith(
        INTERRUPTION_PREFIX.lower()
    ):

        interrupted_command = command[
            len(INTERRUPTION_PREFIX):
        ].strip()

        print(
            "[Router] Processing interruption:",
            interrupted_command,
        )

        interrupted_command = (
            normalize_interruption(
                interrupted_command
            )
        )

        print(
            "[Router] Normalized interruption:",
            interrupted_command,
        )

        if interrupted_command:

            process(
                interrupted_command,
                allow_interruption=False,
            )

        return

    command = command.strip(".,!?")

    command = ALIASES.get(
        command,
        command,
    )

    normalized_command = command.strip(".,!")

    capability = resolve_capability(
        normalized_command
    )

    if capability.available:

        print(
            "[Router] Deterministic capability:",
            capability.tool_name,
        )

        execute_tool(
            capability.tool_name
        )

        return

    intent = resolve_intent(command)

    print(
        f"[Router] Intent: "
        f"{intent.type} "
        f"(confidence={intent.confidence:.2f})"
    )

    # =========================================================
    # DETERMINISTIC CAPABILITY
    # =========================================================

    capability = resolve_capability(
        normalized_command
    )

    if capability.available:

        print(
            "[Router] Deterministic capability:",
            capability.tool_name,
        )

        execute_tool(
            capability.tool_name
        )

        return


    # =========================================================
    # HIGH-LEVEL CAPABILITY
    # =========================================================

    capability_request = (
        detect_capability_request(
            normalized_command
        )
    )

    if capability_request.matched:

        capability = (
            get_registered_capability(
                capability_request.capability_name
            )
        )

        if capability and not capability.available:

            print(
                "[Router] Registered capability unavailable:",
                capability_request.capability_name,
            )

            speak(
                explain_capability_availability(
                    capability_request.capability_name
                )
            )

            return

    # =========================================================
    # CONVERSATION
    # =========================================================

    if intent.type == "conversation":

        if not allow_interruption:

            response = ask_ai(
                normalized_command
            )

            print(
                "AI returned:",
                response,
            )

            speak(response)

            return

        result = process_streaming_conversation(
            normalized_command
        )

        if not result:
            return

        # -----------------------------------------------------
        # The streaming conversation may return an interruption
        # wrapped in INTERRUPTION_PREFIX.
        #
        # IMPORTANT:
        # Check `result`, NOT `command`.
        # -----------------------------------------------------

        if result.startswith(
            INTERRUPTION_PREFIX
        ):

            interrupted_command = result[
                len(INTERRUPTION_PREFIX):
            ].strip()

            print(
                "[Router] Processing interruption:",
                interrupted_command,
            )

            interrupted_command = (
                normalize_interruption(
                    interrupted_command
                )
            )

            print(
                "[Router] Normalized interruption:",
                interrupted_command,
            )

            if interrupted_command:

                process(
                    interrupted_command,
                    allow_interruption=False,
                )

            return

        return

    # =========================================================
    # IMPACT ANALYSIS
    # =========================================================

    if intent.type == "impact_analysis":

        refresh_project_analysis_if_changed()

        result = explain_function_impact(
            normalized_command
        )

        if result["status"] == "not_found":

            speak(
                result["message"]
            )

            return

        if result["status"] == "ambiguous":

            candidates = result["candidates"]

            response = (
                "I found multiple possible targets. "
                "Please specify which one you mean:\n\n"
            )

            for candidate in candidates:

                if candidate["type"] == "function":

                    response += (
                        f"- {candidate['file']}::"
                        f"{candidate['function']}()\n"
                    )

                else:

                    response += (
                        f"- {candidate['file']}\n"
                    )

            speak(response)

            return

        response = explain_impact(
            normalized_command,
            result,
        )

        speak(response)

        return

    # =========================================================
    # PENDING REQUEST
    # =========================================================

    if has_pending_request():

        pending = complete_pending_request(
            filename=normalized_command
        )

        if pending:

            execute_tool(pending)

            return

    # =========================================================
    # TOPIC SWITCH
    # =========================================================

    if is_topic_switch(
        normalized_command
    ):

        switch = resolve_topic_switch(
            normalized_command
        )

        if switch:

            execute_tool(switch)

            return

    # =========================================================
    # COMMAND PARSER
    # =========================================================

    parsed = parse_command(
        normalized_command
    )

    # =========================================================
    # CODE CONVERSATION
    # =========================================================

    topic = get_topic()

    if topic and (
        is_code_question(
            normalized_command
        )
        or is_contextual_code_question(
            normalized_command
        )
    ):

        file_info = get_file_content(
            topic["filename"]
        )

        if file_info:

            print(
                "[Router] Code discussion detected."
            )

            response = answer_question(
                normalized_command,
                file_info,
            )

            speak(response)

            return

    # =========================================================
    # FOLLOW-UP COMMAND
    # =========================================================

    if is_follow_up(
        normalized_command
    ):

        follow_up = resolve_follow_up(
            normalized_command
        )

        if follow_up:

            execute_tool(follow_up)

            return

    # =========================================================
    # STATIC/PARSED COMMAND
    # =========================================================

    if parsed:

        execute_tool(parsed)

        return

    # =========================================================
    # DYNAMIC COMMAND
    # =========================================================

    if process_dynamic_command(
        normalized_command
    ):

        return

    # =========================================================
    # WORKSPACE
    # =========================================================

    if "workspace" in normalized_command:

        workspace_name = None

        if "coding" in normalized_command:
            workspace_name = "coding"

        elif "aws" in normalized_command:
            workspace_name = "aws"

        elif "school" in normalized_command:
            workspace_name = "school"

        if workspace_name:

            print(
                f"Workspace requested: "
                f"{workspace_name}"
            )

            execute_tool(
                f"open_{workspace_name}_workspace"
            )

            return

    # =========================================================
    # STATIC COMMAND LOOKUP
    # =========================================================

    tool_name = COMMANDS.get(
        normalized_command
    )

    if tool_name:

        execute_tool(
            tool_name
        )

        return

    # =========================================================
    # AI TOOL DETECTION
    # =========================================================

    tool = detect_tool(
        normalized_command
    )

    print(
        f"Selected tool: {tool}"
    )

    if tool != "none":

        tool_names = [
            tool_name.strip()
            for tool_name in tool.split(",")
        ]

        for tool_name in tool_names:

            execute_tool(
                tool_name
            )

        return

    # =========================================================
    # FALLBACK AI
    # =========================================================

    print(
        "Calling ask_ai..."
    )

    response = ask_ai(
        normalized_command
    )

    print(
        "AI returned:",
        response,
    )

    print(
        "Speaking..."
    )

    speak(response)