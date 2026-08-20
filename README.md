# JARVIS AI Platform

> **JARVIS (Just A Rather Very Intelligent System)** is a local-first conversational AI platform inspired by Iron Man's JARVIS. Built with Python and powered primarily by local AI, JARVIS is evolving beyond a traditional voice assistant into an intelligent AI companion capable of conversation, reasoning, software engineering assistance, memory, tool use, automation, planning, and personal productivity.

---

# Vision

The goal of JARVIS is not simply to answer questions or execute commands.

The goal is to create an AI that feels like collaborating with an intelligent assistant—one that remembers context, understands ongoing conversations, reasons through problems, uses real capabilities when available, and can take meaningful action when appropriate.

JARVIS is built around five long-term capabilities:

* **Conversation** – Natural, context-aware dialogue that feels human.
* **Reasoning** – Intelligent problem solving and software engineering assistance.
* **Memory** – Long-term and conversational memory that reduces repetition.
* **Action** – The ability to use tools and automate real tasks.
* **Orchestration** – The intelligence layer that connects models, memory, tools, applications, and services into one assistant.

The long-term objective is for JARVIS to become a **personal AI operating layer**, while remaining local-first, modular, grounded, and under the user's control.

---

# Important Development Direction

JARVIS is **not** intended to recreate every piece of AI infrastructure from scratch.

The project will build the parts that make JARVIS uniquely JARVIS and integrate mature infrastructure where appropriate.

### Build ourselves

JARVIS should own:

* Conversation orchestration
* Context management
* Memory behavior
* Intent and capability resolution
* Tool selection
* Tool execution policy
* Conversation state
* Interruption behavior
* Planning and task orchestration
* JARVIS-specific safety and permissions
* Verification of important actions
* Integration between all of these systems

### Integrate existing technology

Where mature solutions already exist, JARVIS should prefer integrating them rather than unnecessarily recreating them.

Examples include:

* Language models
* Speech recognition
* Text-to-speech
* Databases
* Scheduling infrastructure
* Browser automation
* Operating-system APIs
* External service APIs
* Search/retrieval systems
* Specialized AI models

This gives JARVIS more time to focus on orchestration, intelligence, reliability, and user experience.

---

# Current Capabilities

## Conversation

* Wake word activation ("Jarvis")
* Session-based voice conversations
* Natural follow-up questions
* Topic switching
* Clarification handling
* Conversation context
* Persistent conversation history
* Streaming AI responses
* Sentence-buffered speech
* Interruptible speech output
* Speech interruption detection
* Interruption normalization and routing
* Cancellation of current speech when the user interrupts

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
(Switches topics naturally.)
```

The current voice architecture separates interruption capture from normal command routing so an interruption does not recursively invoke the router.

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
* Project context
* Project state inspection
* Dependency analysis
* Project graph analysis
* Project impact analysis
* Project target resolution
* Function/symbol analysis
* Git/project information
* Development workspace support

Examples:

* "Explain router.py"
* "Summarize project_service.py"
* "Search for execute_tool"
* "Find conversation_manager.py"
* "How does this function affect the rest of the project?"

The long-term goal is for JARVIS to understand entire software projects and act as an engineering partner rather than simply generating code.

---

## Memory System

JARVIS maintains persistent memory using SQLite.

Current features include:

* Remember information
* Recall stored memories
* Search memories
* Forget memories
* Memory-aware conversations
* Persistent conversation history

The next evolution is more selective memory: deciding what should be remembered, what belongs only to short-term context, and what project/task state should remain separate from personal memory.

---

## Voice Interface

Current voice capabilities include:

* Faster-Whisper speech recognition
* Wake word detection
* Session-based conversations
* Local text-to-speech
* Hands-free interaction
* Streaming speech responses
* Speech interruption
* Interruptible TTS

The voice layer is treated as an interface to JARVIS rather than the core intelligence itself.

---

## AI Intelligence

Current local AI stack:

* Ollama
* Llama 3.1 8B

Current uses include:

* General conversation
* Context-aware responses
* Developer assistance
* Code explanations
* Planning
* Conversational reasoning

The model is one component of JARVIS. JARVIS itself includes the router, tools, memory, context, state, voice, planning, and orchestration around the model.

---

## Tool and Command System

JARVIS has a modular command/tool architecture including:

* Static commands
* Dynamic commands
* Command aliases
* Tool registry
* Tool manager
* Deterministic actions
* Intent resolution
* Tool execution

A core design rule is:

> **If JARVIS has a real capability for a request, use that capability instead of asking the language model to guess the answer.**

For example, a current-time request should use the system clock rather than rely on the LLM to invent a time.

---

## Workspace Management

Quickly switch development environments.

Current workspaces include:

* Coding
* AWS
* School

The workspace system is intended to expand into broader environment and workflow automation.

---

## Planning

JARVIS now has planning infrastructure intended to plan work against the **existing project**, rather than treating JARVIS as a blank-slate system.

The planning architecture distinguishes between:

* What exists today
* What is planned
* What is missing
* What should be extended
* What should be integrated

Planning should favor extending existing services and capabilities rather than recreating them.

---

# Grounding and Capability Awareness

A major architectural priority is making JARVIS reliable about what it actually knows and can do.

JARVIS should distinguish between:

* **Available** – a real capability exists and can currently be executed.
* **Unavailable** – the capability does not exist or cannot currently be accessed.
* **Planned** – the capability is on the roadmap but is not implemented.
* **Observed** – information came from a real tool or source.
* **Remembered** – information came from persistent memory.
* **Inferred** – information was reasoned about rather than directly observed.

JARVIS should never claim that it:

* checked a calendar it cannot access
* read an email it cannot access
* performed an action it did not perform
* remembers information that is not stored
* observed current information that was never retrieved

This distinction is foundational to the future agentic system.

---

# Technology Stack

## AI

* Ollama
* Llama 3.1 8B

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

```text
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
├── conversation_interrupt.py
├── conversation_manager.py
├── conversation_service.py
├── conversation_speech.py
├── listener.py
├── memory_service.py
├── project_analysis_cache.py
├── project_analysis_index.py
├── project_context.py
├── project_dependencies.py
├── project_execution.py
├── project_graph.py
├── project_impact.py
├── project_service.py
├── project_state.py
├── project_symbol_index.py
├── project_target.py
├── prompt_builder.py
├── speaker.py
├── status_service.py
├── transcription_service.py
└── workspace_service.py

models/
│
├── conversation.py
├── memory.py
├── session.py
├── tool_request.py
└── planning_proposal.py

data/
│
├── jarvis.db
├── status.json
└── workspaces.json

tests/
│
└── ...

docs/
│
├── JARVIS_MASTER_PLAN.md
└── ROADMAP.md

main.py
dashboard.py
```

The exact file structure will evolve as the project grows. The architectural goal is stable separation of concerns, not preserving a fixed list of files forever.

---

# Current Development Status

## Foundation ✅

* Voice interaction
* Wake word detection
* Persistent memory
* Local AI
* Dashboard
* Workspace management
* Modular command architecture
* Tool registry/manager
* Persistent conversation infrastructure

## Conversation ✅ / 🚧

* Command parser
* Follow-up detection
* Clarification handling
* Pending requests
* Topic switching
* Context-aware AI
* Streaming responses
* Sentence-buffered speech
* Interruptible TTS
* Conversation interruption monitoring
* Interruption routing and normalization

The next conversation priority is improving grounding, capability awareness, and reliable tool-first behavior.

## Developer Assistant ✅ / 🚧

* Project search
* File search
* File summaries
* Code explanations
* Conversational code navigation
* Project context
* Dependency analysis
* Project graph analysis
* Project impact analysis
* Project target resolution
* Symbol/function analysis
* Execution tracing infrastructure
* AI planning infrastructure

The next goal is turning these building blocks into a more complete engineering workflow.

---

# Roadmap

## Phase 1 — Foundation ✅

Completed:

* Wake word detection
* Speech recognition integration
* Local LLM integration
* Persistent memory
* Dashboard
* Workspace management
* Core router
* Tool registry/manager
* Conversation persistence
* Context-aware conversations

---

## Phase 2 — Conversational Intelligence 🚧

Completed/implemented:

* Follow-up detection
* Clarification handling
* Topic switching
* Conversation context
* Streaming responses
* Sentence buffering
* Interruptible speech
* Speech interruption handling
* Deterministic interruption routing

Current focus:

* Capability-aware AI
* Tool-first routing
* Grounded responses
* Better conversation state
* Stronger distinction between memory, tool results, and inference
* Better handling of unavailable capabilities

---

## Phase 3 — Software Engineering Assistant 🚧

Existing foundation:

* Project understanding
* Project context
* Dependency analysis
* Dependency graph
* Impact analysis
* Symbol/function analysis
* Project target resolution
* Project execution infrastructure
* AI planning

Planned progression:

* Multi-file reasoning
* Execution-flow explanations
* Architecture analysis
* Code review
* Bug analysis
* Refactoring suggestions
* Documentation generation
* Test-aware code changes
* Controlled code modification
* Change verification

Example:

> "How does main.py eventually reach execute_tool()?"

---

## Phase 4 — Planning, Tasks, and Goals

Planned:

* Natural-language task creation
* Persistent reminders
* Due dates
* Recurring tasks
* Task completion
* Goals
* Goal/task relationships
* Planning execution
* Progress tracking
* Verification after execution

---

## Phase 5 — Tool and Integration Platform

Planned:

* Unified tool contracts
* Capability discovery
* Argument validation
* Permission levels
* Tool execution tracing
* Tool failure handling
* Result normalization
* Verification strategies

Potential integrations:

* Git
* Browser
* Operating system
* Calendar
* Email
* Notifications
* Web research
* External APIs

These should be integrated behind JARVIS's tool layer rather than built as unrelated subsystems.

---

## Phase 6 — Intelligent Automation

Planned:

* Multi-step workflows
* Tool chaining
* Conditional execution
* Retry/recovery
* Human approval gates
* Progress reporting
* Cancellation
* Execution history
* Build/test automation
* Documentation workflows
* Workspace automation

---

## Phase 7 — Personal AI Assistant

Planned:

* Calendar integration
* Email drafting
* Task management
* Daily briefings
* Smart reminders
* Notifications
* Productivity assistance
* Proactive follow-ups

---

## Phase 8 — Multimodal and Environmental Awareness

Long-term:

* Screen understanding
* OCR
* Image understanding
* Browser awareness
* Application state
* Device awareness
* Optional camera/environment awareness

Where mature technology already exists, JARVIS should integrate it rather than recreate perception models from scratch.

---

## Phase 9 — Multi-Interface JARVIS

Long-term:

* Voice
* Desktop
* Terminal
* Web dashboard
* Mobile/remote interface
* Messaging/notification interfaces

The JARVIS core should remain shared across interfaces.

---

## Phase 10 — AI Operating Layer

Long-term vision:

JARVIS becomes a conversational operating layer capable of managing projects, workflows, automation, personal productivity, software engineering, and intelligent decision support while remaining grounded, modular, local-first where practical, and user-controlled.

---

# Design Philosophy

Every implementation should strengthen one or more of these pillars:

* **Conversation** – Make interactions more natural.
* **Reasoning** – Improve understanding and problem solving.
* **Memory** – Maintain useful context without unnecessary repetition.
* **Action** – Help accomplish real tasks.
* **Orchestration** – Connect intelligence, tools, memory, and external capabilities reliably.

Additional principles:

* Build JARVIS-specific intelligence; integrate mature infrastructure.
* Prefer deterministic tools over LLM guesses.
* Never fabricate capabilities or observations.
* Extend existing services before creating duplicate systems.
* Keep components modular and replaceable.
* Test major behavior independently.
* Keep the user in control of consequential actions.
* Favor maintainability over unnecessary complexity.

Features should move JARVIS toward its long-term vision rather than simply increase the feature count.

---

# Documentation

Project documentation is maintained in the `docs` directory.

* **`JARVIS_MASTER_PLAN.md`** — Long-term vision, architecture, engineering principles, capability model, and strategic direction.
* **`ROADMAP.md`** — Development phases, completed work, current priorities, and future milestones.

These documents are living documents and should be updated when the architecture or development strategy materially changes.

---

# Author

**Chandler Pruett**

Computer Science student and software developer building JARVIS as a long-term exploration of conversational AI, local language models, software architecture, intelligent automation, and personal AI systems.

The project is developed incrementally with an emphasis on thoughtful architecture, maintainability, grounded behavior, and creating an AI assistant that feels natural to interact with rather than simply responding to commands.
