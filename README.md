# JARVIS AI Platform

> **JARVIS (Just A Rather Very Intelligent System)** is a local-first conversational AI platform inspired by Iron Man's JARVIS. Built with Python and powered by local language models, JARVIS is designed to evolve beyond a voice assistant into an intelligent AI companion capable of conversation, reasoning, software engineering assistance, automation, and personal productivity.

---

# Vision

The goal of JARVIS is not simply to answer questions or execute commands.

The goal is to create an AI that feels like collaborating with an intelligent assistant—one that remembers context, understands ongoing conversations, reasons through problems, and can take meaningful action when appropriate.

JARVIS is built around four long-term capabilities:

* **Conversation** – Natural, context-aware dialogue that feels human.
* **Reasoning** – Intelligent problem solving and software engineering assistance.
* **Memory** – Long-term and conversational memory that reduces repetition.
* **Action** – The ability to automate tasks, control tools, and assist with real work.

---

# Current Capabilities

## Conversation

* Wake word activation ("Jarvis")
* Session-based voice conversations
* Natural follow-up questions
* Topic switching during conversations
* Clarification questions for incomplete requests
* Context-aware conversations
* Persistent conversational memory

Example:

```text
You:
Explain router.py

JARVIS:
(Explains the file.)

You:
Tell me more.

JARVIS:
(Continues discussing the same file.)

You:
What about tool_manager.py?

JARVIS:
(Switches topics naturally and begins explaining tool_manager.py.)
```

---

## Developer Assistant

JARVIS can actively assist with software development.

Current capabilities include:

* Project-wide keyword search
* File search
* File summaries
* AI-powered code explanations
* Context-aware code discussions
* Conversational navigation through source code

Examples:

* "Explain router.py"
* "Summarize project_service.py"
* "Search for execute_tool"
* "Find conversation_manager.py"

The long-term vision is for JARVIS to understand entire software projects and act as an engineering partner rather than simply generating code.

---

## Memory System

JARVIS maintains persistent memory using SQLite.

Current features include:

* Remember information
* Recall stored memories
* Search memories
* Forget memories
* Memory-aware conversations

This allows conversations to become increasingly personalized over time.

---

## Voice Interface

* Faster-Whisper speech recognition
* Wake word detection
* Session-based conversations
* Local text-to-speech
* Hands-free interaction

---

## AI Intelligence

Powered entirely by local AI.

Current stack:

* Ollama
* Llama 3.1

Current capabilities:

* General conversation
* Context-aware responses
* Developer assistance
* Code explanations
* Conversational context awareness

---

## Workspace Management

Quickly switch development environments.

Current workspaces include:

* Coding
* AWS
* School

Designed to expand into complete workspace automation.

---

# Technology Stack

## AI

* Ollama
* Llama 3.1

## Speech

* Faster-Whisper
* PyAudio
* pyttsx3

## Data

* SQLite
* SQLAlchemy

## Development

* Python 3.12
* Git
* GitHub
* Visual Studio Code

---

# Project Architecture

JARVIS follows a modular, service-oriented architecture.

```
JARVIS-AI/

commands/
│
├── actions.py
├── dynamic_commands.py
├── registry.py
├── router.py
├── static_commands.py
└── tool_manager.py

services/
│
├── ai_service.py
├── code_assistant.py
├── command_parser.py
├── conversation_db.py
├── conversation_manager.py
├── conversation_service.py
├── listener.py
├── memory_service.py
├── project_service.py
├── speaker.py
├── status_service.py
├── transcription_service.py
└── workspace_service.py

models/
│
├── conversation.py
├── memory.py
├── session.py
└── tool_request.py

data/
│
├── jarvis.db
├── status.json
└── workspaces.json

tests/
│
└── test_intent.py

docs/
│
├── JARVIS_MASTER_PLAN.md
└── ROADMAP.md

main.py
dashboard.py
```

The architecture emphasizes:

* Separation of concerns
* Modular services
* Extensibility
* Maintainability
* Reusable components

---

# Current Development Status

## Foundation ✅

* Voice interaction
* Wake word detection
* Persistent memory
* Local AI
* Dashboard
* Workspace management

## Conversation ✅

* Command parser
* Follow-up detection
* Clarification handling
* Pending requests
* Topic switching
* Context-aware AI

## Developer Assistant ✅

* Project search
* File search
* File summaries
* Code explanations
* Conversational code navigation

---

# Roadmap

## Phase 1 — Foundation ✅

Completed:

* Wake word detection
* Faster-Whisper integration
* Local LLM integration
* Persistent memory
* Dashboard
* Workspace management
* Context-aware conversations

---

## Phase 2 — Conversational Intelligence 🚧

Current focus:

* AI code assistant
* Engineering discussions
* Topic history
* Improved reasoning
* Code-aware conversations

---

## Phase 3 — Software Engineering Assistant

Planned:

* Multi-file understanding
* Execution tracing
* Code review
* Architectural analysis
* Refactoring suggestions
* Documentation generation
* Project planning

Example:

> "How does main.py eventually call execute_tool()?"

---

## Phase 4 — Intelligent Automation

Planned:

* Desktop automation
* Browser automation
* Git integration
* Build automation
* Testing automation
* Plugin framework

---

## Phase 5 — Personal AI Assistant

Planned:

* Calendar integration
* Email drafting
* Task management
* Daily briefings
* Smart reminders
* Productivity assistance

---

## Phase 6 — AI Operating Layer

Long-term vision:

JARVIS becomes a conversational operating layer capable of managing projects, workflows, automation, and intelligent decision support while remaining local-first and user-controlled.

---

# Design Philosophy

Every implementation should strengthen at least one of these pillars:

* **Conversation** – Make interactions feel more natural.
* **Reasoning** – Improve understanding and problem solving.
* **Memory** – Reduce repetition and maintain context.
* **Action** – Help users accomplish real tasks.

Features are only added when they move JARVIS closer to its long-term vision rather than simply increasing the feature list.

---

# Documentation

Project documentation is maintained in the `docs` directory.

* **JARVIS_MASTER_PLAN.md** — Long-term vision, architecture, engineering principles, and roadmap.
* **ROADMAP.md** — Development milestones and current priorities.

---

# Author

**Chandler Pruett**

Computer Science student and software developer building JARVIS as a long-term exploration of conversational AI, local language models, software architecture, and intelligent automation.

The project is developed incrementally with an emphasis on thoughtful architecture, maintainability, and creating an AI assistant that feels natural to interact with rather than simply responding to commands.
