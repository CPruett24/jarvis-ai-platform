# JARVIS Roadmap

**Status:** Living Document  
**Last Updated:** August 2026

---

# Development Strategy

The roadmap has been revised to reflect a major change in approach:

> **JARVIS should build its unique intelligence/orchestration layer while integrating mature technology for specialized capabilities.**

We do not need to build every subsystem from scratch.

The roadmap therefore measures progress by **capability maturity**, not by the number of components independently reinvented.

---

# Phase 1 — Foundation ✅

## Completed

- [x] Python project structure
- [x] Virtual environment
- [x] Local LLM integration
- [x] Voice interaction
- [x] Wake word detection
- [x] Speech-to-text
- [x] Text-to-speech
- [x] Persistent memory
- [x] Conversation persistence
- [x] Dashboard
- [x] Workspace management
- [x] Command parser
- [x] Router
- [x] Command aliases
- [x] Static/dynamic command architecture
- [x] Tool registry/manager
- [x] Core testing infrastructure

## Exit Criteria

- [x] JARVIS runs locally
- [x] Core services are modular
- [x] Major subsystems can be tested independently
- [x] Development can be checkpointed safely with Git

---

# Phase 2 — Conversational Intelligence 🚧

## Completed

- [x] Follow-up detection
- [x] Clarification handling
- [x] Pending requests
- [x] Topic switching
- [x] Topic tracking
- [x] Context-aware conversations
- [x] Context-aware source-code discussions
- [x] Streaming AI responses
- [x] Sentence buffering
- [x] Interruptible speech
- [x] Speech interruption monitoring
- [x] Interruption normalization
- [x] Deterministic routing after interruption

## Current Priorities

- [ ] Capability-aware prompting
- [ ] Tool-first routing
- [ ] Stronger grounding
- [ ] Explicit unavailable-capability behavior
- [ ] Better separation of memory vs. tool results vs. inference
- [ ] Improved conversational state
- [ ] Better cancellation for long-running operations

## Target Outcome

JARVIS should be able to converse naturally while reliably understanding what it actually knows, remembers, can access, and can do.

---

# Phase 3 — Software Engineering Assistant 🚧

## Existing Foundation

- [x] Project-wide search
- [x] File search
- [x] File summaries
- [x] Code explanations
- [x] Conversational code navigation
- [x] Project context
- [x] Project state
- [x] Dependency analysis
- [x] Dependency graph
- [x] Impact analysis
- [x] Project target resolution
- [x] Symbol/function analysis
- [x] Project execution infrastructure
- [x] AI planning infrastructure

## Next

- [ ] Multi-file reasoning
- [ ] Execution-flow explanations
- [ ] Architecture analysis
- [ ] Code review
- [ ] Bug analysis
- [ ] Code-smell detection
- [ ] Refactoring suggestions
- [ ] Test generation
- [ ] Documentation generation
- [ ] Controlled code modifications
- [ ] Test-aware code changes
- [ ] Change verification

## Target Outcome

JARVIS should be able to inspect a project, understand relationships between components, reason about a change, make controlled modifications, run verification, and explain the result.

---

# Phase 4 — Planning, Tasks, and Goals

## Goal

Turn the existing planning infrastructure into persistent user-facing execution.

## Planned

- [ ] Natural-language task creation
- [ ] Persistent tasks
- [ ] Task priorities
- [ ] Due dates
- [ ] Recurring tasks
- [ ] Task completion
- [ ] Goals
- [ ] Goal/task relationships
- [ ] Plan tracking
- [ ] Progress updates
- [ ] Follow-up tasks
- [ ] Verification after execution
- [ ] Reminders

## Example

```text
User:
Remind me tomorrow at 3 PM to work on JARVIS.

JARVIS:
Create persistent reminder.

Later:
Reminder fires.

JARVIS:
You asked me to remind you to work on JARVIS.
```

---

# Phase 5 — Tool and Integration Platform

## Goal

Make tools the reliable capability layer underneath JARVIS.

## Planned

- [ ] Unified tool contracts
- [ ] Tool schemas
- [ ] Capability discovery
- [ ] Argument validation
- [ ] Permission levels
- [ ] Tool execution traces
- [ ] Standardized tool results
- [ ] Tool failure handling
- [ ] Verification strategies
- [ ] Cancellation
- [ ] Approval policies

## Potential Integrations

- [ ] Git
- [ ] Browser
- [ ] Operating system
- [ ] Calendar
- [ ] Email
- [ ] Notifications
- [ ] Web research
- [ ] External APIs

These should be integrations behind the JARVIS tool layer rather than separate assistant architectures.

---

# Phase 6 — Controlled Intelligent Automation

## Goal

Move from individual actions to reliable multi-step workflows.

```text
Request
   ↓
Understand
   ↓
Plan
   ↓
Execute
   ↓
Verify
   ↓
Recover if necessary
   ↓
Report
```

## Planned

- [ ] Multi-step plans
- [ ] Tool chaining
- [ ] Conditional execution
- [ ] Retry/recovery
- [ ] Progress reporting
- [ ] Cancellation
- [ ] Human approval gates
- [ ] Execution history
- [ ] Build automation
- [ ] Test automation
- [ ] Documentation workflows
- [ ] Workspace automation
- [ ] Browser automation
- [ ] OS automation

## Important Rule

Automation should be **controlled orchestration**, not unrestricted autonomy.

---

# Phase 7 — Personal AI Assistant

## Planned

- [ ] Calendar integration
- [ ] Email integration
- [ ] Email drafting
- [ ] Task management
- [ ] Smart reminders
- [ ] Daily briefings
- [ ] Notifications
- [ ] Weather
- [ ] News
- [ ] Productivity assistance
- [ ] Proactive follow-ups

Every external capability must be backed by a real integration before JARVIS claims access to it.

---

# Phase 8 — Multimodal and Environmental Awareness

## Long-Term

- [ ] Screen understanding
- [ ] OCR
- [ ] Image understanding
- [ ] Browser awareness
- [ ] Application state
- [ ] Device awareness
- [ ] Optional camera/environment awareness

Where mature models or libraries already exist, integrate them rather than rebuilding perception systems from scratch.

---

# Phase 9 — Multi-Interface JARVIS

## Long-Term

- [x] Voice
- [x] Terminal/developer workflow
- [ ] Desktop interface expansion
- [ ] Web interface expansion
- [ ] Mobile/remote interface
- [ ] Messaging/notification interfaces

The shared JARVIS core should provide the intelligence across all interfaces.

---

# Phase 10 — AI Operating Layer

## Vision

JARVIS becomes a conversational operating layer capable of coordinating:

- Conversation
- Memory
- Tasks
- Goals
- Software engineering
- Computer interaction
- Research
- Automation
- External services
- Proactive assistance

while remaining:

- Grounded
- Modular
- Local-first where practical
- Permission-aware
- User-controlled
- Maintainable

---

# Build vs. Integrate Policy

## Build

Build a component ourselves when it is:

- central to JARVIS
- JARVIS-specific
- an orchestration layer
- difficult to replace without losing important behavior
- not already solved adequately by mature infrastructure

## Integrate

Integrate existing technology when it is:

- mature
- specialized
- replaceable behind an interface
- not a core differentiator for JARVIS

Examples:

- LLMs
- Speech recognition
- TTS
- Database engines
- Browser engines
- Scheduling infrastructure
- External APIs
- Perception models

---

# Current Priority Queue

## 1. Grounding

Prevent JARVIS from inventing capabilities, observations, or actions.

## 2. Tool-First Routing

Use deterministic capabilities whenever a real tool exists.

## 3. Capability Awareness

Make JARVIS explicitly understand available, unavailable, planned, remembered, observed, and inferred information.

## 4. Conversational State

Improve context and multi-turn reasoning.

## 5. Tasks and Reminders

Turn planning infrastructure into persistent real-world functionality.

## 6. Developer Workflows

Use the growing project-analysis infrastructure for stronger engineering assistance.

## 7. Tool Platform

Add validation, permissions, traces, failures, and verification.

## 8. Controlled Automation

Only after individual capabilities are reliable.

---

# Milestone Policy

Each major stable milestone should:

1. Have appropriate tests.
2. Pass the relevant test suite.
3. Pass `git diff --check`.
4. Be reviewed for architectural consistency.
5. Be committed.
6. Be pushed to GitHub.
7. Update this roadmap if the project direction materially changed.

The roadmap is a living engineering document. Future phases are directional and may change as JARVIS develops.
