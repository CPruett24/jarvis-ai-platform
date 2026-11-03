from services.cancellation import OperationCancelled, check_cancelled
from dataclasses import dataclass
from services.ai_service import (
    ask_ai,
    detect_tool,
    stream_ai_response,
    explain_impact,
)
from services.speaker import speak
from services.speaker import stop_speaking
from services.conversation_lifecycle import (
    is_conversation_end,
    handle_conversation_boundary,
    CONVERSATION_ENDED,
)
from commands.static_commands import COMMANDS
from commands.dynamic_commands import process_dynamic_command
from commands.tool_manager import execute_tool
from services.command_parser import (
    parse_command,
    parse_workspace_command,
)

from services.conversation_manager import (
    has_pending_request,
    get_pending_request,
    clear_pending_request,
    complete_pending_request,
    is_follow_up,
    resolve_follow_up,
    is_explicit_file_target,
    get_topic,
    set_topic,
    set_pending_request,
    mark_conversation_discussion,
    mark_file_discussion,
)

from services.conversation_service import (
    add_message,
)

from services.code_intent import (
    should_use_file_context,
    is_clear_new_question,
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
    is_capability_explanation,
)

from services.capability_service import (
    explain_capability_availability,
    get_registered_capability,
    resolve_capability,
)

from services.capability_executor import (
    execute_capability,
    get_observed_information,
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
    get_agent_result_information,
)

from services.conversation_service import (
    save_message,
)

from services.grounding_service import (
    format_information_context,
)

from services.capability_registry import (
    get_capability_name_for_tool,
)

from models.tool_request import ToolRequest

import queue
import threading
import re
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

_conversation_producer_slot = threading.BoundedSemaphore(1)
MAX_VOICE_RESPONSE_SECONDS = 120
PLAYBACK_INACTIVITY_SECONDS = 120
INTERRUPTION_HANDOFF_SECONDS = 0.35


def _stream_with_interrupt(
    command,
    interrupt_controller,
    stream_factory=None,
):
    """
    Run the AI stream in a background thread so the
    router remains responsive to microphone interruptions.

    Returns normally when the stream completes.
    Stops yielding immediately when an interruption occurs.
    """

    cancellation_event = interrupt_controller.interrupted
    if cancellation_event.is_set():
        return
    if not _conversation_producer_slot.acquire(blocking=False):
        yield "The previous AI response is still cancelling. Please try again shortly."
        return
    chunks = queue.Queue(maxsize=32)
    finished = object()

    def enqueue(item):
        while not cancellation_event.is_set():
            try:
                chunks.put(item, timeout=0.05)
                return
            except queue.Full:
                continue

    def producer():

        try:

            stream = (stream_factory(cancellation_event) if stream_factory else
                      stream_ai_response(command, cancellation_event=cancellation_event))
            for chunk in stream:
                check_cancelled(cancellation_event)
                enqueue(chunk)

        except OperationCancelled as exc:
            if not cancellation_event.is_set():
                enqueue(exc)

        except Exception as exc:

            enqueue(exc)

        finally:

            _conversation_producer_slot.release()
            enqueue(finished)

    # Carry the operation's persistence receipt into its generation thread.
    from contextvars import copy_context
    generation_context = copy_context()
    thread = threading.Thread(
        target=lambda: generation_context.run(producer),
        daemon=True,
    )

    try:
        thread.start()
    except BaseException:
        _conversation_producer_slot.release()
        raise
    deadline = time.monotonic() + MAX_VOICE_RESPONSE_SECONDS

    while True:

        # Keep observing this operation's signal even if the controller resets.
        if cancellation_event.is_set():
            return
        if time.monotonic() >= deadline:
            cancellation_event.set()
            raise TimeoutError("Conversation stream timed out")

        try:

            item = chunks.get(
                timeout=0.05
            )

        except queue.Empty:

            continue

        if cancellation_event.is_set():
            return

        if item is finished:
            return

        if isinstance(item, Exception):
            raise item

        if isinstance(item, _RelationshipDelivery):
            try:
                item = present_relationship_result(item.result, item.arguments, cancellation_event)
            except OperationCancelled:
                if cancellation_event.is_set():
                    return
                raise
            if cancellation_event.is_set():
                return
        yield item

INTERRUPTION_PREFIX = "__JARVIS_INTERRUPTION__:"


def _ask_and_speak(command):
    from services.conversation_service import ResponseDelivery, capture_response_delivery
    from services.tts.outcome import PlaybackOutcome
    receipt = ResponseDelivery()
    result = PlaybackOutcome.FAILED
    try:
        with capture_response_delivery(receipt):
            response = ask_ai(command)
        result = speak(response)
        return response
    finally:
        receipt.finish(result)


def process_streaming_conversation(command, stream_factory=None):
    from services.conversation_service import ResponseDelivery, capture_response_delivery
    from services.tts.outcome import PlaybackOutcome
    print("Streaming capability response..." if stream_factory is not None else "Calling streaming conversation AI...")
    speech = ConversationSpeech()
    controller = ConversationInterruptController(speech)
    monitor = None
    full_response = ""
    cancelled = False
    receipt = ResponseDelivery()
    outcome = PlaybackOutcome.UNKNOWN
    response_error = False
    interrupted_text = None
    try:
        monitor = SpeechInterruptMonitor(controller.handle_speech)
        monitor.start()
        speech.start_response()
        with capture_response_delivery(receipt):
            stream = (_stream_with_interrupt(command, controller, stream_factory) if stream_factory else
                      _stream_with_interrupt(command, controller))
            for chunk in stream:
                if controller.was_interrupted():
                    break
                if chunk:
                    full_response += chunk
                    speech.add_chunk(chunk)
        if not controller.was_interrupted():
            speech.finish()
            waiting_since = time.monotonic()
            while not controller.was_interrupted() and not speech.is_finished():
                progress = getattr(speech, "progress_timestamp", lambda: None)()
                if time.monotonic() - (progress if progress is not None else waiting_since) >= PLAYBACK_INACTIVITY_SECONDS:
                    outcome = PlaybackOutcome.TIMED_OUT
                    getattr(speech, "mark_timeout", speech.interrupt)()
                    print("[TTS] Playback timed out; returning to listening.")
                    break
                time.sleep(0.05)
        cancelled = controller.was_interrupted()
        if cancelled:
            outcome = PlaybackOutcome.INTERRUPTED
            speech.interrupt()  # One request; callback only records cancellation.
            begin_handoff = getattr(controller, "begin_handoff", None)
            if begin_handoff:
                begin_handoff()
            # Briefly retain following utterances while playback winds down.
            time.sleep(INTERRUPTION_HANDOFF_SECONDS)
        elif outcome != PlaybackOutcome.TIMED_OUT:
            outcome = getattr(speech, "playback_outcome", lambda: PlaybackOutcome.UNKNOWN)()
    except TimeoutError:
        outcome = PlaybackOutcome.TIMED_OUT
        speech.interrupt()
        print("[Voice] Response timed out; returning to listening.")
    except BaseException:
        outcome = PlaybackOutcome.FAILED
        response_error = True
        raise
    finally:
        # Dispose the speech worker even after successful playback or exceptions.
        try:
            close = getattr(speech, "stop", None)
            if close:
                close()
        finally:
            try:
                if monitor:
                    monitor.stop()
            finally:
                try:
                    # Seal the callback window after bounded cleanup, before
                    # persisting the result. The synthetic producer-stop event
                    # below is not evidence of a user interruption.
                    handoff = getattr(controller, "handoff", controller.get_interrupted_text)
                    interrupted_text = handoff()
                    if interrupted_text and not response_error and outcome != PlaybackOutcome.TIMED_OUT:
                        outcome = PlaybackOutcome.INTERRUPTED
                    receipt.finish(outcome)
                finally:
                    # Also release a producer waiting on a full queue after errors.
                    controller.interrupted.set()
    if interrupted_text:
        return INTERRUPTION_PREFIX + interrupted_text
    print("AI returned:", full_response)
    return full_response

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

    # Preserve qualified identifiers in C2 handoffs while retaining the legacy
    # normalization of other interrupted commands below.
    import re
    from services.code_intent import resolve_relationship_request
    original = re.sub(r"^(?:wait[,\s]+stop|wait|stop|hold on|hang on)[,\s]+", "",
                      command.strip(), flags=re.I)
    if resolve_relationship_request(original) is not None:
        return original
    pending = get_pending_request()
    if (isinstance(pending, dict) and pending.get("relationship_grounded")
            and original in pending.get("candidates", ())):
        return original

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


MIGRATED_DETERMINISTIC_CAPABILITIES = {
    "current_time",
    "git_status",
    "git_branch",
    "git_remote",
    "project_tree",
    "project_search",
    "file_search",
    "coding_workspace",
    "aws_workspace",
    "school_workspace",
}


def execute_registered_capability(
    capability_name,
    arguments=None,
    speak_result=True,
    cancellation_event=None,
):
    """Execute and present a registered deterministic capability.

    Successful results are retained as observed information so
    future AI turns receive evidence rather than an unlabelled
    assistant statement.
    """

    if cancellation_event is not None and capability_name in {"project_source", "multi_file_reasoning"}:
        arguments = {**(arguments or {}), "cancellation_event": cancellation_event}
    if arguments is None:

        result = execute_capability(
            capability_name
        )

    else:

        result = execute_capability(
            capability_name,
            arguments=arguments,
        )

    check_cancelled(cancellation_event)
    if capability_name == "multi_file_reasoning":
        if speak_result:
            from services.conversation_service import ResponseDelivery, capture_response_delivery
            from services.tts.outcome import PlaybackOutcome
            receipt = ResponseDelivery()
            outcome = PlaybackOutcome.FAILED
            try:
                with capture_response_delivery(receipt):
                    response = present_relationship_result(result, arguments or {}, cancellation_event)
                check_cancelled(cancellation_event)
                if response:
                    outcome = speak(response)
            finally:
                receipt.finish(outcome)
        else:
            present_relationship_result(result, arguments or {}, cancellation_event)
        return result
    if result.success:

        observations = get_observed_information(
            result
        )

        if observations:

            add_message(
                "assistant",
                format_information_context(
                    observations
                ),
                source="observed",
            )

    response = format_capability_result(
        result
    )

    if capability_name == "project_source" and response:
        add_message("assistant", response, source="inferred" if result.success else "router")
        if result.success and result.data.get("topic"):
            topic = result.data["topic"]
            topic["query"] = (arguments or {}).get("question", "")
            set_topic(topic)
        elif result.data.get("candidates") or result.data.get("needs_filename"):
            from services.project_access import get_project
            context = get_project()
            set_pending_request({"source_grounded": True, "candidates": result.data["candidates"],
                "project_id": context.project_id, "authorization_revision": context.revision,
                "question": (arguments or {}).get("question", ""),
                "operation": (arguments or {}).get("operation", "read"), "missing": "filename"})

    if response and speak_result:

        speak(response)

    return result


@dataclass(frozen=True)
class _RelationshipDelivery:
    result: object
    arguments: dict


def present_relationship_result(result, arguments, cancellation_event=None):
    """Consumer-only C2 effects: producer completion alone never publishes a turn."""
    from services.project_relationship_capability import validate_relationship_delivery, relationship_speech
    from services.project_access import get_project, ProjectAccessError
    check_cancelled(cancellation_event)
    if not is_capability_available("multi_file_reasoning"):
        result.success, result.error, result.data = False, "Capability is currently disabled.", {}
    result = validate_relationship_delivery(result, cancellation_event)
    context = arguments.get("context")
    try:
        current = get_project()
        if context != current:
            raise ProjectAccessError("Project changed before delivery.")
    except ProjectAccessError:
        result.success, result.error, result.data = False, "The project context or authorization changed. Please repeat the question.", {}
    response = format_capability_result(result)
    check_cancelled(cancellation_event)
    if arguments.get("question"):
        add_message("user", arguments["question"], source="user")
    check_cancelled(cancellation_event)
    if result.success:
        observations = get_observed_information(result)
        if observations:
            add_message("assistant", format_information_context(observations), source="observed")
    check_cancelled(cancellation_event)
    add_message("assistant", response, source="observed" if result.success else "router")
    check_cancelled(cancellation_event)
    if result.success and result.data.get("topic"):
        clear_pending_request()
        set_topic(result.data["topic"])
    elif result.data.get("pending"):
        set_pending_request(result.data["pending"])
    if result.data.get("candidates"):
        return "The target is ambiguous. Please specify a project-relative file and qualified symbol name."
    return relationship_speech(response)


def stream_relationship_response(arguments, cancellation_event):
    """Use the existing bounded queue; all publication effects stay on its consumer."""
    check_cancelled(cancellation_event)
    result = execute_capability("multi_file_reasoning", {**arguments, "cancellation_event": cancellation_event})
    check_cancelled(cancellation_event)
    yield _RelationshipDelivery(result, arguments)


def stream_source_response(arguments, cancellation_event):
    """Validate a complete source answer before speech; reuse voice watchdogs."""
    result = execute_registered_capability("project_source", arguments=arguments,
        speak_result=False, cancellation_event=cancellation_event)
    check_cancelled(cancellation_event)
    yield format_capability_result(result)


def execute_migrated_tool_request(
    request,
):
    """Use the capability path for the scoped read-only tools."""

    capability_name = get_capability_name_for_tool(
        request.tool
    )

    if capability_name not in MIGRATED_DETERMINISTIC_CAPABILITIES:

        return False

    execute_registered_capability(
        capability_name,
        arguments=request.arguments,
    )

    return True

def process(command, allow_interruption=True):
    """Route handoffs iteratively, preserving barge-in and end control results."""
    while command:
        if command.lower().startswith(INTERRUPTION_PREFIX.lower()):
            command = normalize_interruption(command[len(INTERRUPTION_PREFIX):].strip())
            allow_interruption = True
            if not command:
                return
        result = _process_once(command, allow_interruption=allow_interruption)
        if isinstance(result, str) and result.startswith(INTERRUPTION_PREFIX):
            command = result
            continue
        return result


def _process_once(command, allow_interruption=True):
    if not command:
        return
    original_command = command.strip()
    command = command.lower().strip()
    command = command.strip(".,!?")

    if is_conversation_end(command):
        stop_speaking()
        handle_conversation_boundary("explicit_end")
        return CONVERSATION_ENDED

    command = ALIASES.get(
        command,
        command,
    )

    normalized_command = command.strip(".,!")

    # Explicit archive recall precedes broad code, agent, clarification, and
    # memory routes. The AI service selects its isolated prompt while the
    # existing streaming/speech machinery retains ownership of interruption.
    from services.historical_recall import classify_historical_recall
    if classify_historical_recall(normalized_command) is not None:
        clear_pending_request()
        mark_conversation_discussion()
        if not allow_interruption:
            return _ask_and_speak(normalized_command)
        result = process_streaming_conversation(normalized_command)
        return result

    from services.code_intent import is_conversation_summary_phrase
    if is_conversation_summary_phrase(normalized_command):
        clear_pending_request()
        mark_conversation_discussion()
        response = "Did you mean summarize our last conversation?"
        speak(response)
        return response

    arithmetic_result = try_basic_arithmetic(
        command
    )

    if arithmetic_result is not None:

        clear_pending_request()

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

        clear_pending_request()

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

    if capability.source == "static_command":

        clear_pending_request()

        print(
            "[Router] Deterministic capability:",
            capability.tool_name,
        )

        execute_registered_capability(
            capability.capability_name
        )

        return

    # Explicit C2 grammar precedes broad C1 project search, after recall/management.
    from services.code_intent import resolve_relationship_request, relationship_target
    from services.conversation_manager import resolve_relationship_follow_up
    from services.project_access import get_project, ProjectAccessError
    relationship_request = resolve_relationship_request(original_command)
    if relationship_request is None:
        relationship_request = resolve_relationship_follow_up(original_command)
    pending = get_pending_request()
    if relationship_request is None and isinstance(pending, dict) and pending.get("relationship_grounded"):
        candidate = original_command.strip().strip("`\"'")
        if candidate in pending["candidates"]:
            try:
                current = get_project()
                if current.project_id != pending["project_id"] or current.revision != pending["authorization_revision"]:
                    raise ProjectAccessError("Stale clarification")
                relationship_request = {key: pending[key] for key in (
                    "operation", "direction", "depth", "comparison") if key in pending}
                relationship_request.update(relationship_target(candidate))
            except ProjectAccessError:
                relationship_request = {"stale_context": True}
    if relationship_request is not None:
        clear_pending_request()
        try:
            if relationship_request.pop("stale_context", False):
                raise ProjectAccessError("Stale relationship topic")
            target_error = relationship_request.pop("target_error", None)
            if target_error:
                from services.capability_executor import CapabilityExecutionResult
                result = CapabilityExecutionResult(False, "multi_file_reasoning", error=target_error)
                response = present_relationship_result(result, {"context": get_project(), "question": original_command})
                speak(response)
                return result
            qualifier = relationship_request.pop("project_qualifier", None)
            if qualifier:
                from services.project_access import list_projects
                matches = [project for project in list_projects() if project.project_id.casefold() == qualifier.casefold()]
                if len(matches) != 1 or matches[0] != get_project():
                    response = "That named project is not the active authorized project. Select an authorized project explicitly, then repeat the relationship question."
                    speak(response)
                    return response
            relationship_request.update(context=get_project(), question=original_command)
        except ProjectAccessError:
            response = "The project context or authorization changed. Please repeat the project question."
            speak(response)
            return response
        if allow_interruption:
            return process_streaming_conversation(original_command,
                stream_factory=lambda event: stream_relationship_response(relationship_request, event))
        return execute_registered_capability("multi_file_reasoning", relationship_request)

    # C1 resolves project-source requests before generic explanations/agents.
    # Archive recall and capability management retain precedence above.
    from services.code_intent import resolve_source_request
    from services.project_access import get_project
    source_request = resolve_source_request(normalized_command)
    from services.conversation_manager import get_stale_source_topic
    if source_request is None and get_stale_source_topic() and normalized_command in {
            "tell me more", "explain that", "explain it", "continue", "why", "go on"}:
        speak("The project context or authorization changed. Please repeat the project question.")
        return
    source_topic = get_topic()
    if source_request is None and source_topic and source_topic.get("source_grounded"):
        if should_use_file_context(normalized_command, source_topic):
            source_request = {"question": normalized_command, "operation": "read",
                              "filename": source_topic["filename"], "detail_depth": source_topic["depth"] + 1}
        elif source_topic.get("type") == "project" and normalized_command in {
                "tell me more", "explain that", "explain it", "continue"}:
            source_request = {"question": normalized_command + " " + source_topic.get("query", ""),
                              "operation": "search"}
    source_pending = get_pending_request()
    if source_request is None and source_pending and source_pending.get("source_grounded"):
        context = get_project()
        if (context.project_id != source_pending["project_id"] or
                context.revision != source_pending["authorization_revision"]):
            clear_pending_request()
            speak("Project authorization changed; please repeat the request.")
            return
        choices = source_pending["candidates"]
        reply = normalized_command.replace("\\", "/")
        matches = [path for path in choices if reply == path.lower() or reply == path.lower().rsplit("/", 1)[-1]]
        if not choices and re.fullmatch(r"[\w./\\:-]+", reply) and not is_clear_new_question(reply):
            matches = [reply]
        if len(matches) == 1:
            source_request = {"question": source_pending["question"], "filename": matches[0],
                              "operation": source_pending["operation"]}
        elif not is_clear_new_question(normalized_command):
            speak("Please specify one of these project-relative paths: " + ", ".join(choices))
            return
        else:
            clear_pending_request()
    if source_request is not None:
        clear_pending_request()
        context = get_project()
        source_request.update(project_id=context.project_id, authorization_revision=context.revision)
        add_message("user", normalized_command, source="user")
        if allow_interruption:
            return process_streaming_conversation(normalized_command,
                stream_factory=lambda event: stream_source_response(source_request, event))
        execute_registered_capability("project_source", arguments=source_request)
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
    # Explicit filename/path targets remain file requests even when missing.
    # Other explanations require a file topic or a resolvable project target.
    #

    conceptual_capability = is_capability_explanation(normalized_command)

    if conceptual_capability or normalized_command.startswith(
        "explain "
    ):

        clear_pending_request()

        explanation_target = (
            normalized_command[
                len("explain "):
            ].strip()
        )

        active_topic = get_topic()

        file_target_exists = is_explicit_file_target(explanation_target)

        if active_topic and not conceptual_capability and should_use_file_context(normalized_command, active_topic):

            if active_topic.get(
                "type"
            ) == "file":

                file_target_exists = True

        if not file_target_exists and not conceptual_capability:

            file_info = get_file_content(
                explanation_target
            )

            if file_info:

                file_target_exists = True

        if not file_target_exists:
            mark_conversation_discussion()

            if not allow_interruption:
                _ask_and_speak(normalized_command)
                return

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

                return result

            return


    intent = resolve_intent(
        command
    )

    # Explicit tools, topic switches, and contextual follow-ups supersede
    # clarification. The fallback conversation intent alone is not evidence.
    if intent.type != "conversation":
        clear_pending_request()

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

        clear_pending_request()

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

        result = execute_registered_capability(
            capability_name
        )

        if result.success:

            print(
                "[Router] Capability completed:",
                capability_name,
            )

        elif result.error:

            print(
                "[Router] Capability failed:",
                result.error,
            )

        return

    # =========================================================
    # WORKSPACE
    # =========================================================
    #
    # Workspace opening is a deterministic local capability.
    # It must be resolved before external-agent detection so
    # Hermes cannot intercept requests that JARVIS can execute
    # directly.
    #

    workspace_request = parse_workspace_command(
        normalized_command
    )

    if workspace_request:
        clear_pending_request()
        print(
            "[Router] Workspace capability:",
            workspace_request.tool,
        )

        if execute_migrated_tool_request(
            workspace_request
        ):
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

        clear_pending_request()

        print(
            "[Router] External agent:",
            agent_request.agent_name,
        )

        add_message(
            "user",
            normalized_command,
            source="user",
        )

        ensure_agents_registered()

        agent = get_agent(
            agent_request.agent_name
        )

        if agent is None:

            response = (
                "I couldn't initialize the requested agent."
            )

            add_message(
                "assistant",
                response,
                source="router",
            )

            speak(response)

            return response

        if not agent.available:

            response = (
                "Hermes is currently unavailable."
            )

            add_message(
                "assistant",
                response,
                source="router",
            )

            speak(response)

            return response

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
                agent_response = process_agent_response(
                    result.message
                )

                response = agent_response.speech_response

                agent_information = get_agent_result_information(
                    result
                )

                if agent_information:
                    add_message(
                        "assistant",
                        format_information_context(
                            agent_information
                        ),
                        source="hermes",
                    )

                if response:
                    add_message(
                        "assistant",
                        response,
                        source="hermes",
                    )

                    speak(response)

                return response

            return

        print(
            "[Router] Agent failed:",
            result.error,
        )

        if result.error:

            response = (
                "I couldn't complete that through Hermes. "
                + result.error
            )

        else:

            response = (
                "I couldn't complete that through Hermes."
            )

        add_message(
            "assistant",
            response,
            source="router",
        )

        speak(response)

        return response

    # =========================================================
    # PENDING REQUEST
    # =========================================================

    if has_pending_request() and intent.type == "conversation" and is_clear_new_question(normalized_command):
        clear_pending_request()

    if has_pending_request():

        pending_state = get_pending_request()
        pending = complete_pending_request(response=normalized_command)

        if pending:
            execute_tool(pending)
        else:
            speak(
                pending_state.get("prompt")
                or "I couldn't resolve that clarification. Please try again."
            )

        return

    # =========================================================
    # DYNAMIC MEMORY COMMAND
    # =========================================================
    #
    # Explicit memory actions must be resolved before the
    # conversational fallback so they cannot be consumed as
    # ordinary conversation.
    #

    if process_dynamic_command(
        normalized_command
    ):
        clear_pending_request()
        return

    # =========================================================
    # CONVERSATION
    # =========================================================

    if intent.type == "conversation":
        mark_conversation_discussion()

        if not allow_interruption:

            response = _ask_and_speak(normalized_command)

            print(
                "AI returned:",
                response,
            )

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

            return result

            return

        return

    # =========================================================
    # IMPACT ANALYSIS
    # =========================================================

    if intent.type == "impact_analysis":

        if get_project().project_id != "jarvis":
            speak("Relationship analysis is unavailable for additional projects; source reading is available.")
            return

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
    # TOPIC SWITCH
    # =========================================================

    if intent.type == "topic_switch":
        execute_tool(intent.tool_request)
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

    if intent.type == "code_question" and should_use_file_context(normalized_command, topic):

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

            mark_file_discussion()
            speak(response)

            return

        speak("I couldn't retrieve the current file. Please specify a readable project file.")
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

        if execute_migrated_tool_request(
            parsed
        ):

            return

        execute_tool(parsed)

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

            request = ToolRequest(
                tool=tool_name
            )

            if execute_migrated_tool_request(
                request
            ):

                continue

            execute_tool(
                request
            )

        return

    # =========================================================
    # FALLBACK AI
    # =========================================================

    print(
        "Calling ask_ai..."
    )

    response = _ask_and_speak(normalized_command)

    print(
        "AI returned:",
        response,
    )

    print(
        "Speaking..."
    )
