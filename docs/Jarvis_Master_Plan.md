# JARVIS Master Plan

**Project Name:** JARVIS (Just A Rather Very Intelligent System)

**Author:** Chandler Pruett

**Version:** 0.3 (Living Document)

**Last Updated:** July 31, 2026

---

# Vision

JARVIS is a conversational AI assistant inspired by Iron Man's JARVIS.

The goal is **not** to build another chatbot.

The goal is to build an AI companion capable of:

* Natural conversation
* Long-term memory
* Voice interaction
* Personal assistance
* Software engineering assistance
* Automation
* Planning
* Learning user preferences
* Becoming increasingly autonomous while remaining under user control

The experience should feel like talking to another engineer—not issuing commands to a computer.

---

# Core Philosophy

Every feature should improve one or more of these pillars.

## 1. Conversation First

Conversation always takes priority over commands.

Instead of:

> Explain router.py

> Explain tool_manager.py

The goal is:

> Explain router.py

> Tell me more

> Why was it written that way?

> What about tool_manager.py?

> Compare them.

---

## 2. Context Matters

JARVIS should always understand:

* current conversation
* current project
* current workspace
* current task
* user memories

The user should rarely need to repeat themselves.

---

## 3. Modular Design

Every component should have a single responsibility.

Avoid giant files.

Prefer many small services over one large service.

---

## 4. AI Is the Brain

Traditional programming handles:

* routing
* tools
* validation
* automation

AI handles:

* reasoning
* explanation
* conversation
* planning
* engineering discussions

---

# Long-Term Vision

JARVIS should eventually be capable of:

### Personal Assistant

* Calendar management
* Reminders
* Email drafting
* Task management
* Scheduling
* Daily briefings

### Software Engineering Assistant

* Understand entire repositories
* Explain architecture
* Review code
* Suggest improvements
* Debug issues
* Generate tests
* Generate documentation
* Understand execution flow

### Computer Automation

* Open applications
* Control workspaces
* Run scripts
* Manage files
* Launch development environments
* Perform repetitive tasks

### Intelligent Conversation

* Hold long conversations
* Remember previous discussions
* Switch topics naturally
* Ask clarification questions
* Learn preferences
* Answer follow-up questions

---

# Current Architecture

```
Voice Input
      │
      ▼
Speech Recognition
      │
      ▼
Router
      │
      ├─────────────► Static Commands
      │
      ├─────────────► Dynamic Commands
      │
      ├─────────────► Tool Detection
      │
      ├─────────────► Conversation Manager
      │
      └─────────────► AI
                        │
                        ▼
                 Ollama (Llama 3.1)
                        │
                        ▼
                Text-to-Speech
```

---

# Current Project Structure

```
JARVIS-AI/

commands/
    actions.py
    dynamic_commands.py
    registry.py
    router.py
    static_commands.py
    tool_manager.py

models/
    tool_request.py

services/
    ai_service.py
    conversation_manager.py
    memory_service.py
    project_service.py
    workspace_service.py
    speaker.py
    listener.py

data/

tools/

main.py
```

---

# Completed Features

## Foundation

* ✅ Voice interaction
* ✅ Wake word
* ✅ Continuous conversation session
* ✅ Text-to-speech
* ✅ Speech-to-text
* ✅ Local AI using Ollama
* ✅ Persistent memory
* ✅ Dashboard

---

## Conversation

* ✅ Command parser
* ✅ Alias system
* ✅ Pending requests
* ✅ Clarification questions
* ✅ Follow-up detection
* ✅ Topic switching
* ✅ Topic tracking
* ✅ Context-aware AI (topic)
* ✅ Context-aware AI (current source code)

---

## Developer Assistant

* ✅ Project search
* ✅ File search
* ✅ File summaries
* ✅ Code explanations
* ✅ Explain follow-ups
* ✅ Project-wide keyword search

---

## Workspace

* ✅ Coding workspace
* ✅ AWS workspace
* ✅ School workspace

---

# Current Limitations

JARVIS currently cannot:

* Answer engineering questions about code naturally
* Understand relationships between multiple files
* Compare files
* Understand full execution flow
* Review architecture
* Plan large refactors
* Remember topic history
* Execute multi-step plans autonomously

---

# Current Roadmap

## Phase 1 — Foundation ✅

* Voice
* Memory
* Dashboard
* Router
* Tools

Completed.

---

## Phase 2 — Conversational Assistant 🚧

### Completed

* Command parser
* Pending requests
* Clarification
* Follow-up detection
* Topic switching
* Context-aware prompts

### Remaining

* Topic history
* Go back to previous topic
* Compare topics
* Conversation planning

---

## Phase 3 — AI Code Assistant (Current Focus)

### Goal

Transform JARVIS from a command executor into an engineering partner.

### Features

* AI code questions
* Architectural reasoning
* Explain functions
* Explain classes
* Trace execution
* Detect bugs
* Explain imports
* Explain variables
* Explain design decisions

Example:

> Why is ALIASES here?

Instead of summarizing the file, JARVIS should answer the specific question.

---

## Phase 4 — Multi-File Understanding

Goals:

* Trace execution between files
* Understand imports
* Build dependency graphs
* Compare files
* Explain architecture
* Explain data flow

Example:

> How does main.py reach execute_tool()?

---

## Phase 5 — Code Review

JARVIS should identify:

* Bugs
* Code smells
* Duplication
* Large functions
* Poor naming
* Dead code
* Suggested refactors
* Performance improvements

---

## Phase 6 — Planning

JARVIS becomes capable of:

* Breaking projects into milestones
* Planning implementations
* Creating TODO lists
* Tracking progress
* Estimating effort
* Suggesting next tasks

---

## Phase 7 — Automation

Examples:

* Git helper
* Build helper
* Test runner
* Documentation generator
* Workspace setup
* Deployment helper

---

## Phase 8 — Personal Assistant

* Email
* Calendar
* Notifications
* Smart reminders
* Daily briefing
* Weather
* News
* Task management

---

# Engineering Principles

When adding new features:

1. Prefer composition over duplication.
2. Every service should have one responsibility.
3. Avoid giant files.
4. Test after every implementation.
5. Refactor before adding major new capabilities.
6. Reuse existing logic whenever possible.
7. Keep conversational behavior natural.
8. Favor maintainability over shortcuts.

---

# Coding Standards

* Meaningful function names
* Small functions
* Clear separation of concerns
* Minimal global state
* Strong typing where practical
* Consistent formatting
* Helpful debug logging during development
* Remove temporary debug statements before release

---

# Session Workflow

Each development session should follow this process:

1. Review the current milestone.
2. Define one implementation goal.
3. Design before coding.
4. Implement incrementally.
5. Test immediately.
6. Refactor if necessary.
7. Update this document.
8. Commit changes.
9. Push to GitHub.

---

# Current Priority

**Current Milestone:** AI Code Assistant

Immediate objectives:

1. Create `code_assistant.py`.
2. Differentiate "explain file" from "answer code question."
3. Route conversational engineering questions to the code assistant.
4. Improve responses using current code context.
5. Prepare for multi-file reasoning.

---

# Future Vision (Version 1.0)

By version 1.0, JARVIS should be able to:

* Hold natural spoken conversations.
* Remember long-term information.
* Understand ongoing conversations.
* Understand entire software projects.
* Help write, debug, and review code.
* Manage workspaces.
* Plan implementations.
* Automate repetitive tasks.
* Act as a daily personal productivity assistant.

The end goal is for interacting with JARVIS to feel like collaborating with an experienced software engineer and personal assistant—someone who understands your projects, remembers previous discussions, and helps you think through problems rather than simply responding to commands.
