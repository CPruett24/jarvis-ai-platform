"""One utterance, one process, one engine-owning thread.

Parent termination also recovers hung native initialization/playback. Native
stop is not guaranteed on termination; per-utterance startup is the tradeoff.
"""
import json
import sys
from services.voice_diagnostics import voice_trace


def main():
    text = json.load(sys.stdin)
    import pyttsx3
    voice_trace("local_engine_init")
    engine = pyttsx3.init()
    try:
        voice_trace("local_engine_play")
        engine.say(text)
        engine.runAndWait()
    finally:
        voice_trace("local_engine_stop")
        engine.stop()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"[TTS] Local engine failed ({type(error).__name__}).")
        sys.exit(1)
