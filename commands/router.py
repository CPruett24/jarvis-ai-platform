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

from services.capability_request import (
    detect_capability_request,
    detect_capability_management_request,
    detect_agent_request,
)

from services.capability_service import (
    explain_capability_availability,
    get_registered_capability,
    resolve_capability,
)

from services.capability_executor import (
    execute_capability,
)

from services.capability_response import (
    format_capability_result,
)

from services.capability_state import (
    is_capability_available,
)

from services.capability_manager import (
    get_capability_summary,
    get_capability_details,
    get_available_capability_names,
    get_disabled_capability_names,
    get_unavailable_capability_names,
)

from services.agents.agent_manager import (
    register_agent,
    get_agent,
    execute_agent,
)

from services.agents.hermes_agent import (
    HermesAgent,
)

from services.agent_response_service import (
    process_agent_response,
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

def try_basic_arithmetic(command):
    """
    Handle simple spoken arithmetic directly in JARVIS.

    Supports:
        2 plus 2
        two plus two
        what's 2 plus 2
        that's two plus two
        27 times 14
        twenty seven times fourteen
    """

    if not command:
        return None

    text = command.lower().strip()

    # Remove common spoken prefixes.
    prefixes = (
        "what is",
        "what's",
        "calculate",
        "how much is",
        "tell me",
        "it's",
        "it is",
        "that's",
        "that is",
    )

    changed = True

    while changed:

        changed = False

        for prefix in prefixes:

            if text.startswith(prefix + " "):

                text = text[len(prefix):].strip()

                changed = True
                break

    # Normalize common speech-recognition variations.
    text = text.replace("-", " ")

    # Spoken number vocabulary.
    number_words = {
        "zero": 0,
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "eleven": 11,
        "twelve": 12,
        "thirteen": 13,
        "fourteen": 14,
        "fifteen": 15,
        "sixteen": 16,
        "seventeen": 17,
        "eighteen": 18,
        "nineteen": 19,
        "twenty": 20,
        "thirty": 30,
        "forty": 40,
        "fifty": 50,
        "sixty": 60,
        "seventy": 70,
        "eighty": 80,
        "ninety": 90,
        "hundred": 100,
        "thousand": 1000,
    }

    def parse_number(value):

        value = value.strip()

        # Numeric input.
        try:
            return float(value)
        except ValueError:
            pass

        words = value.split()

        if not words:
            return None

        total = 0
        current = 0

        for word in words:

            if word not in number_words:
                return None

            number = number_words[word]

            if number == 100:

                if current == 0:
                    current = 1

                current *= 100

            elif number == 1000:

                if current == 0:
                    current = 1

                total += current * 1000
                current = 0

            else:

                current += number

        return float(total + current)

    # Supported arithmetic operators.
    operations = (
        ("multiplied by", "*"),
        ("divided by", "/"),
        ("plus", "+"),
        ("minus", "-"),
        ("times", "*"),
    )

    operator = None
    left_text = None
    right_text = None

    for phrase, symbol in operations:

        if phrase in text:

            parts = text.split(
                phrase,
                1,
            )

            if len(parts) != 2:
                return None

            left_text = parts[0].strip()
            right_text = parts[1].strip()

            operator = symbol
            break

    if operator is None:
        return None

    left = parse_number(left_text)
    right = parse_number(right_text)

    if left is None or right is None:
        return None

    if operator == "+":

        result = left + right

    elif operator == "-":

        result = left - right

    elif operator == "*":

        result = left * right

    elif operator == "/":

        if right == 0:
            return "I can't divide by zero."

        result = left / right

    else:
        return None

    if result.is_integer():

        return str(int(result))

    return str(result)

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

def format_capability_management_response(
    request,
):
    """
    Convert capability-management state into a natural
    language response suitable for JARVIS speech.
    """

    if request.action == "details":

        details = get_capability_details(
            request.capability_name
        )

        if details is None:

            return (
                "I couldn't find that capability."
            )

        name = details["name"]

        if not details["available"]:

            reason = details["reason"]

            if reason:

                return (
                    f"{name} isn't currently "
                    f"available. {reason}"
                )

            return (
                f"{name} isn't currently "
                "available."
            )

        if not details["enabled"]:

            return (
                f"{name} is currently "
                "disabled."
            )

        return (
            f"{name} is available and enabled."
        )

    if request.action == "list":

        summary = get_capability_summary()

        available = summary["available"]
        unavailable = summary["unavailable"]
        disabled = summary["disabled"]

        parts = []

        if available:

            parts.append(
                "Currently available: "
                + ", ".join(available)
                + "."
            )

        if unavailable:

            parts.append(
                "Registered but unavailable: "
                + ", ".join(unavailable)
                + "."
            )

        if disabled:

            parts.append(
                "Disabled: "
                + ", ".join(disabled)
                + "."
            )

        if not parts:

            return (
                "I don't currently have any "
                "registered capabilities."
            )

        return " ".join(parts)

    if request.action == "list_disabled":

        disabled = (
            get_disabled_capability_names()
        )

        if not disabled:

            return (
                "I don't currently have any "
                "disabled capabilities."
            )

        return (
            "The following capabilities are disabled: "
            + ", ".join(disabled)
            + "."
        )

    if request.action == "list_unavailable":

        unavailable = (
            get_unavailable_capability_names()
        )

        if not unavailable:

            return (
                "I don't currently have any "
                "unavailable capabilities."
            )

        return (
            "The following capabilities are "
            "currently unavailable: "
            + ", ".join(unavailable)
            + "."
        )

    if request.action == "status":

        summary = get_capability_summary()

        return (
            f"I have {summary['total']} registered "
            f"capabilities. "
            f"{len(summary['available'])} are available, "
            f"{len(summary['unavailable'])} are unavailable, "
            f"and {len(summary['disabled'])} are disabled."
        )

    return (
        "I don't know how to inspect that "
        "capability information yet."
    )

def ensure_agents_registered():
    """
    Ensure JARVIS' external agents are registered.

    Registration is idempotent so this can safely be called
    whenever the router processes a command.
    """

    if get_agent("hermes") is None:

        register_agent(
            HermesAgent()
        )

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

    arithmetic_result = try_basic_arithmetic(
        command
    )

    if arithmetic_result is not None:

        speak(
            arithmetic_result
        )

        return arithmetic_result
    
    # =========================================================
    # CAPABILITY MANAGEMENT
    # =========================================================
    #
    # Capability-management questions must be checked before
    # deterministic execution. For example:
    #
    # "Is current time available?"
    #
    # should inspect capability state rather than execute
    # the current-time tool.
    #

    capability_management = (
        detect_capability_management_request(
            normalized_command
        )
    )

    if capability_management.matched:

        print(
            "[Router] Capability management:",
            capability_management.action,
        )

        response = (
            format_capability_management_response(
                capability_management
            )
        )

        speak(response)

        return

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
    # GENERAL EXPLANATION
    # =========================================================
    #
    # Generic explanations should remain conversational.
    #
    # For example:
    #
    #     "Explain why 27 times 14 is important in programming."
    #
    # is not a file request simply because it starts with
    # "explain".
    #
    # Only treat an explanation as a file/code request when there
    # is an active file topic or the requested target is actually
    # a file in the project.
    #

    if normalized_command.startswith(
        "explain "
    ):

        explanation_target = (
            normalized_command[
                len("explain "):
            ].strip()
        )

        active_topic = get_topic()

        file_target_exists = False

        if active_topic:

            if active_topic.get(
                "type"
            ) == "file":

                file_target_exists = True

        if not file_target_exists:

            file_info = get_file_content(
                explanation_target
            )

            if file_info:

                file_target_exists = True

        if not file_target_exists:

            print(
                "[Router] General explanation detected."
            )

            result = process_streaming_conversation(
                normalized_command
            )

            if not result:

                return

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


    intent = resolve_intent(
        command
    )

    print(
        f"[Router] Intent: "
        f"{intent.type} "
        f"(confidence={intent.confidence:.2f})"
    )

    # =========================================================
    # HIGH-LEVEL CAPABILITY
    # =========================================================

    capability_request = (
        detect_capability_request(
            normalized_command
        )
    )

    if capability_request.matched:

        capability_name = (
            capability_request.capability_name
        )

        print(
            "[Router] High-level capability:",
            capability_name,
        )

        if not is_capability_available(
            capability_name
        ):

            print(
                "[Router] Capability unavailable or disabled:",
                capability_name,
            )

            speak(
                explain_capability_availability(
                    capability_name
                )
            )

            return

        result = execute_capability(
            capability_name
        )

        if result.success:

            print(
                "[Router] Capability completed:",
                capability_name,
            )

            response = format_capability_result(
                result
            )

            if response:

                speak(
                    response
                )

            return

        if result.error:

            print(
                "[Router] Capability failed:",
                result.error,
            )

            speak(
                format_capability_result(
                    result
                )
            )

            return

    # =========================================================
    # EXTERNAL AGENT
    # =========================================================
    #
    # Complex research, investigation, and multi-step requests
    # can be delegated to Hermes.
    #
    # This comes after deterministic capabilities so requests
    # such as "what time is it" or "what is my Git branch"
    # remain local and fast.
    #

    agent_request = detect_agent_request(
        normalized_command
    )

    if agent_request.matched:

        print(
            "[Router] External agent:",
            agent_request.agent_name,
        )

        ensure_agents_registered()

        agent = get_agent(
            agent_request.agent_name
        )

        if agent is None:

            speak(
                "I couldn't initialize the requested agent."
            )

            return

        if not agent.available:

            speak(
                "Hermes is currently unavailable."
            )

            return

        result = execute_agent(
            agent_request.agent_name,
            agent_request.task,
        )

        if result.success:

            print(
                "[Router] Agent completed:",
                agent_request.agent_name,
            )

            if result.message:

                agent_response = (
                    process_agent_response(
                        result.message
                    )
                )

                response = (
                    agent_response.speech_response
                )

                if response:

                    speak(
                        response
                    )

                return response

            return

        print(
            "[Router] Agent failed:",
            result.error,
        )

        if result.error:

            speak(
                "I couldn't complete that through Hermes. "
                + result.error
            )

        else:

            speak(
                "I couldn't complete that through Hermes."
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
    #
    # AI tool detection is intentionally conservative.
    #
    # A natural-language question such as:
    #
    #     "Explain why 27 times 14 is important in programming."
    #
    # must remain a conversation unless there is an actual
    # capability/tool request.
    #
    # File-related tools should only be selected when the request
    # has already been identified as a file/code operation.
    #

    tool = detect_tool(
        normalized_command
    )

    print(
        f"Selected tool: {tool}"
    )

    # ---------------------------------------------------------
    # Do not allow generic "explain" questions to become
    # explain_file requests.
    # ---------------------------------------------------------

    if tool == "explain_file":

        file_topic = get_topic()

        if not file_topic:

            print(
                "[Router] Ignoring explain_file detection "
                "because no file topic is active."
            )

            tool = "none"


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