# JARVIS AI Assistant

A voice-controlled AI assistant inspired by JARVIS from Iron Man.

JARVIS combines local AI, voice interaction, persistent memory, and natural language command execution into a fully local personal assistant built with Python.

## Features

### Voice Interaction

* Wake word activation ("Jarvis")
* Session-based conversations
* Faster-Whisper speech recognition
* Text-to-speech responses
* Standby and session management

### AI Intelligence

* Local LLM powered by Ollama
* Llama 3.1 integration
* Conversational context memory
* Personalized responses

### Memory System

* SQLite-backed persistent memory
* Remember information
* Recall stored memories
* Search memories by topic
* Forget stored memories

### Natural Language Commands

JARVIS can execute commands through natural language.

Examples:

* "Can you open GitHub for me?"
* "Launch Visual Studio Code."
* "Open ChatGPT."

AI intent recognition determines the requested action and routes it to the correct command handler.

## Example Conversation

User:
Jarvis

JARVIS:
Yes, Chandler?

User:
What do you know about my AWS plans?

JARVIS:
You told me your AWS Cloud Practitioner exam is August 15th.

User:
Can you open GitHub for me?

JARVIS:
Opening GitHub.

## Technology Stack

### AI

* Ollama
* Llama 3.1

### Speech

* Faster-Whisper
* PyAudio
* pyttsx3

### Data

* SQLite
* SQLAlchemy

### Development

* Python 3.12
* Git
* GitHub
* VS Code

## Current Architecture

JARVIS-AI/

├── commands/

│   ├── actions.py

│   └── router.py

├── models/

│   └── memory.py

├── services/

│   ├── ai_service.py

│   ├── conversation_service.py

│   ├── listener.py

│   ├── memory_service.py

│   ├── speaker.py

│   └── transcription_service.py

└── main.py

## Current Capabilities

* Voice-controlled assistant
* Local AI responses
* Persistent memory
* Memory-aware conversations
* Conversational context
* AI intent recognition
* Natural language command execution

## Roadmap

### Near Term

* Multi-action commands
* Windows startup integration
* Desktop dashboard

### Latest Milestone: Mk. VI

* Faster-Whisper Integration
* Local LLM (Ollama)
* Conversational Context
* Persistent Memory
* AI Intent Recognition

### Future

* Calendar and reminders
* Tool usage and automation
* Cloud synchronization
* Advanced memory retrieval
* Multi-device support

## Author

Chandler Pruett

Computer Science Student

Built as a personal project to explore AI assistants, local LLMs, voice interfaces, and software architecture.
