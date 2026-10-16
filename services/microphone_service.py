"""Shared microphone selection for foreground and interruption capture."""

import os

import speech_recognition as sr

from services.configuration import load_environment
from services.voice_diagnostics import voice_trace


def create_microphone():
    load_environment()
    preferred = os.getenv("JARVIS_MICROPHONE_NAME", "").strip()
    if not preferred:
        voice_trace("microphone_selected", endpoint="system_default")
        return sr.Microphone()

    try:
        names = sr.Microphone.list_microphone_names()
    except Exception as exc:
        voice_trace("microphone_selected", endpoint="system_default", reason="enumeration_failed")
        print(
            f"Warning: Could not list microphones ({type(exc).__name__}); "
            "using the default microphone."
        )
        return sr.Microphone()

    # Exact names avoid accidentally selecting similarly named devices.
    # Enumeration order makes duplicate-name selection deterministic.
    for index, name in enumerate(names):
        if name.strip().casefold() == preferred.casefold():
            voice_trace("microphone_selected", endpoint=name, index=index)
            return sr.Microphone(device_index=index)

    print(
        f"Warning: Configured microphone {preferred!r} was not found; "
        "using the default microphone."
    )
    voice_trace("microphone_selected", endpoint="system_default", reason="configured_endpoint_missing")
    return sr.Microphone()
