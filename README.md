# JARVIS AI Platform

A local-first AI assistant and agent platform inspired by JARVIS from Iron Man.

JARVIS combines local AI, voice interaction, persistent memory, automation, workspaces, and agent-oriented architecture into an extensible personal AI platform built with Python.

The long-term goal is to evolve JARVIS from a personal voice assistant into a business-capable AI operating layer capable of managing projects, workflows, automation, analytics, and autonomous agents.


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
Remember that my project deadline is Friday.

JARVIS:
Got it stored.

User:
What do you remember about my project?

JARVIS:
You told me your project deadline is Friday.

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

# Roadmap

## Phase 1 — Foundation (Current)

### Completed

* Wake word detection
* Faster-Whisper speech recognition
* Ollama integration
* Text-to-speech responses
* Conversational context
* SQLite memory system
* Intent recognition
* Dynamic workspaces
* Streamlit dashboard
* Windows startup integration
* Live status system

### Planned

* Persistent conversation database
* Interruptible speech
* Dashboard improvements
* Enhanced memory retrieval

---

## Phase 2 — Platform

### Planned

* Tool framework
* Browser automation
* Desktop automation
* Workflow engine
* Task management system
* Plugin architecture

---

## Phase 3 — Agent System

### Planned

* Planner agent
* Executor agent
* Goal tracking
* Multi-step task execution
* Tool orchestration
* Long-running task support

---

## Phase 4 — Business Operations Layer

### Planned

* Email integration
* GitHub integration
* Calendar integration
* Analytics integrations
* Customer support workflows
* Revenue and KPI reporting

Example:

"How is the business doing this week?"

JARVIS can summarize:

* Revenue
* User growth
* Support requests
* Development progress
* Marketing performance
* Recommended actions

---

## Phase 5 — AI Operating Layer

### Planned

* Multi-agent architecture
* Developer agents
* Research agents
* Marketing agents
* Autonomous workflows
* Continuous monitoring
* Business intelligence and recommendations

Example:

"Launch the new feature."

JARVIS could:

1. Create development tasks
2. Implement changes
3. Run tests
4. Deploy updates
5. Monitor results
6. Report outcomes

---

## Vision

JARVIS is being built as a local-first AI platform that evolves from a personal assistant into a system capable of helping manage applications, projects, workflows, customers, analytics, and businesses.

## Author

Chandler Pruett

Computer Science Student

Built as a personal project to explore AI assistants, local LLMs, voice interfaces, and software architecture.
