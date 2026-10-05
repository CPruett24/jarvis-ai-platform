"""Shared microphone selection for foreground and interruption capture."""

import os

import speech_recognition as sr

from services.configuration import load_environment


def create_microphone():
    load_environment()
    preferred = os.getenv("JARVIS_MICROPHONE_NAME", "").strip()
    if not preferred:
        return sr.Microphone()

    try:
        names = sr.Microphone.list_microphone_names()
    except Exception as exc:
        print(
            f"Warning: Could not list microphones ({type(exc).__name__}); "
            "using the default microphone."
        )
        return sr.Microphone()

    # Exact names avoid accidentally selecting similarly named devices.
    # Enumeration order makes duplicate-name selection deterministic.
    for index, name in enumerate(names):
        if name.strip().casefold() == preferred.casefold():
            return sr.Microphone(device_index=index)

    print(
        f"Warning: Configured microphone {preferred!r} was not found; "
        "using the default microphone."
    )
    return sr.Microphone()
