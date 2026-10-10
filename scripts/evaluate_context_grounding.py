"""Optional local Ollama smoke evaluation; no DB reads/writes or saved turns.

Run from the repository root with the project Python interpreter.
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv

load_dotenv()
from services import ai_service
from services.grounding_service import create_memory_information


def main():
    oop = [{"role": "user", "content": "What is object-oriented programming?"},
           {"role": "assistant", "content": "OOP organizes code into objects with data and behavior."}]
    cases = [
        ("repeated_oop", "What is object-oriented programming?", oop, []),
        ("unsupported_claim", "What is REST?", [
            {"role": "assistant", "content": "You've built several web applications."}], []),
        ("followup", "What about inheritance?", oop, []),
        ("personal_memory", "What programming projects have I worked on?", [], [
            create_memory_information("You told me you worked on a Python weather application project."),
            create_memory_information("Your favorite food is sushi.")]),
    ]
    model = os.getenv("JARVIS_OLLAMA_MODEL", ai_service.OLLAMA_MODEL)
    print(json.dumps({"model": model}), flush=True)
    for name, question, history, memories in cases:
        with patch.object(ai_service, "get_memory_information", return_value=memories), \
             patch.object(ai_service, "get_source_aware_history", return_value=history), \
             patch.object(ai_service, "get_topic", return_value=None), \
             patch.object(ai_service, "get_pending_request", return_value=None), \
             patch.object(ai_service, "get_capability_context", return_value=""):
            messages = ai_service._build_conversation_messages(question)
        messages.append({"role": "user", "content": question})
        response = ai_service.chat(model=model, messages=messages, stream=False,
                                   options={"temperature": 0, "num_predict": 250},
                                   keep_alive=ai_service.OLLAMA_KEEP_ALIVE)
        print(json.dumps({"case": name, "answer": response["message"]["content"]}), flush=True)


if __name__ == "__main__":
    main()
