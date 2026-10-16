"""Opt-in voice lifecycle metadata; never include credentials or utterances."""
import os
import threading


def voice_trace(event, **fields):
    if os.getenv("JARVIS_SPEECH_DIAGNOSTICS", "0").lower() in {"1", "true", "yes", "on"}:
        details = " ".join(f"{key}={value}" for key, value in fields.items())
        print(f"[Voice diagnostics] {event} pid={os.getpid()} thread={threading.get_ident()} {details}")
