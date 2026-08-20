# JARVIS Master Plan

**Project Name:** JARVIS (Just A Rather Very Intelligent System)

**Author:** Chandler Pruett

**Version:** 1.0 (Living Document)

**Last Updated:** August 2026

---

# 1. Vision

JARVIS is a local-first conversational AI assistant inspired by Iron Man's JARVIS.

The goal is **not** to build another chatbot.

The goal is to build a personal AI system capable of:

* Natural conversation
* Long-term memory
* Voice interaction
* Personal assistance
* Software engineering assistance
* Tool use
* Automation
* Planning
* Learning useful user preferences
* Multi-step workflows
* Proactive assistance

while remaining:

* Grounded in real information
* Modular
* Maintainable
* Local-first where practical
* Explicit about its capabilities
* Under user control

The experience should feel like collaborating with an intelligent assistant—not issuing commands to a computer.

---

# 2. Strategic Direction

The project has evolved beyond the original plan of building each capability independently from scratch.

The new strategy is:

> **Build the intelligence and orchestration that makes JARVIS unique. Integrate mature infrastructure for capabilities that are already solved well.**

This means JARVIS should not spend months recreating:

* Language models
* Speech recognition engines
* TTS engines
* Databases
* Browser engines
* Calendar infrastructure
* Email infrastructure
* Generic scheduling systems
* Mature AI perception systems

unless a specific JARVIS requirement makes owning that implementation worthwhile.

Instead, JARVIS should own the layer that connects these capabilities.

---

# 3. What Makes JARVIS Unique

JARVIS itself should own:

* Conversation orchestration
* Context management
* Memory behavior
* Intent resolution
* Capability awareness
* Tool selection
* Tool execution policy
* Conversation state
* Interruption behavior
* Planning
* Task orchestration
* Verification
* Permissions
* JARVIS personality
* User experience
* Integration between all subsystems

This is the actual product.

External libraries, models, and services are implementation components underneath it.

---

# 4. Core Philosophy

## 4.1 Conversation First

Conversation remains a primary interface.

The goal is not merely:

> "Explain router.py."

It is:

```text
Explain router.py.

Tell me more.

Why was it written that way?

What about tool_manager.py?

Compare them.

How does that affect the rest of the project?
```

JARVIS should preserve enough context to make this interaction natural.

---

## 4.2 Context Matters

JARVIS should understand the relevant combination of:

* Current conversation
* Current topic
* Current project
* Current workspace
* Current task
* Persistent memory
* Available tools
* Recent tool results

The user should rarely need to repeat information that JARVIS legitimately has available.

---

## 4.3 Modular Design

Every component should have a clear responsibility.

Avoid giant files and duplicated systems.

Prefer:

* Small services
* Explicit interfaces
* Replaceable providers
* Shared infrastructure
* Testable components

---

## 4.4 AI Is the Reasoning Layer

Traditional software should handle deterministic behavior:

* Routing
* Tool discovery
* Validation
* Database operations
* File operations
* OS interaction
* Permissions
* Execution
* Verification

AI should handle:

* Interpretation
* Reasoning
* Explanation
* Conversation
* Planning
* Synthesis
* Ambiguous requests

The two layers should cooperate rather than compete.

---

## 4.5 Build vs. Integrate

### Build

Build a component ourselves when:

* It is central to JARVIS.
* It contains JARVIS-specific state or behavior.
* Existing solutions do not provide the required behavior.
* Owning the component provides important control or reliability.

### Integrate

Use existing technology when:

* The problem is already solved well.
* Building it would distract from JARVIS's core.
* The component can be cleanly abstracted behind an interface.
* A mature local or external solution provides better quality.

This is an intentional engineering decision, not a shortcut.

---

# 5. Grounding and Capability Awareness

This is one of the most important architectural changes in the new plan.

JARVIS must understand the difference between:

### Available

A real capability exists and JARVIS can execute it.

### Unavailable

The capability does not exist or cannot currently be accessed.

### Planned

The capability is intended for a future phase but is not implemented.

### Observed

Information came directly from a real tool, system, source, or service.

### Remembered

Information came from persistent memory.

### Inferred

The model reasoned about the information but did not directly observe it.

JARVIS must not silently convert one category into another.

For example, if calendar integration does not exist, JARVIS should not say:

> "You have a meeting at 3 PM."

It should say that it cannot currently access the calendar.

This principle will become increasingly important as JARVIS gains autonomy.

---

# 6. Deterministic Tool-First Architecture

If a real tool exists for a request, the tool should normally be preferred over LLM generation.

Example:

```text
User:
What time is it?

        ↓

Intent resolution

        ↓

current_time tool

        ↓

System clock

        ↓

Actual result
```

The LLM can then turn the result into natural language.

This pattern should eventually apply to:

* Time
* File operations
* Git
* Project information
* Tasks
* Calendar
* Email
* Browser actions
* OS operations
* Notifications
* External APIs

The model should reason over tool results rather than fabricate them.

---

# 7. Current Architecture

```text
                         JARVIS CORE
                              │
             ┌────────────────┼────────────────┐
             │                │                │
             ▼                ▼                ▼
       Conversation         Memory           Tools
       & Context            & State        & Actions
             │                │                │
             └────────────────┼────────────────┘
                              │
                         Orchestrator
                              │
             ┌────────────────┼────────────────┐
             │                │                │
             ▼                ▼                ▼
            LLM             Planner          Router
             │                │                │
             └────────────────┼────────────────┘
                              │
                         Verification
                              │
             ┌────────────────┼────────────────┐
             ▼                ▼                ▼
           Voice             OS             External
         Interface          Tools            Services
```

---

# 8. Voice Architecture

Voice is an interface into JARVIS.

Current flow:

```text
Microphone
    ↓
Speech recognition
    ↓
Router
    ↓
Conversation / Tool / Project / AI
    ↓
Streaming response
    ↓
Sentence buffer
    ↓
TTS
```

Interruption behavior:

```text
JARVIS speaking
       │
       ├───────────────┐
       │               │
       ▼               ▼
TTS worker       interruption monitor
                       │
                 user speaks
                       ↓
              capture interruption
                       ↓
                 stop TTS
                       ↓
             normalize interruption
                       ↓
                normal routing
```

The interruption controller should capture and coordinate interruption state rather than recursively invoking the main router from a microphone callback.

This keeps voice interruption behavior modular and prevents recursive command-processing loops.

---

# 9. Memory Architecture

JARVIS already has persistent memory and conversation storage.

The target architecture separates:

## Short-term context

* Current conversation
* Current topic
* Pending request
* Immediate task state

## Persistent memory

* User facts
* Useful preferences
* Explicitly remembered information

## Project knowledge

* Source code
* Project architecture
* Dependencies
* Project state
* Analysis results

## Operational state

* Tasks
* Goals
* Plans
* Execution history

These should not all be injected into every prompt.

The next stage is selective retrieval and better classification.

---

# 10. Developer Assistant

The developer-assistant system has become one of JARVIS's strongest existing capability areas.

Current infrastructure includes:

* Project search
* File search
* File summaries
* Code explanations
* Project context
* Project state
* Dependency analysis
* Dependency graphs
* Impact analysis
* Symbol/function analysis
* Target resolution
* Project execution infrastructure
* AI planning infrastructure

The long-term engineering workflow is:

```text
User describes goal
        ↓
Understand project
        ↓
Inspect relevant code
        ↓
Analyze dependencies / impact
        ↓
Create implementation plan
        ↓
Make controlled changes
        ↓
Run tests
        ↓
Inspect diff
        ↓
Verify result
        ↓
Explain result
```

The assistant should become increasingly capable without blindly modifying code based only on model output.

---

# 11. Planning System

JARVIS now includes planning infrastructure designed around the existing codebase.

The planner should:

1. Understand the user's goal.
2. Inspect current project context.
3. Determine what already exists.
4. Determine what is missing.
5. Avoid recreating existing capabilities.
6. Prefer extending existing services.
7. Break work into concrete tasks.
8. Keep tasks independently testable.
9. Distinguish current state from roadmap plans.

Planning is therefore an orchestration layer, not a separate "AI project manager" disconnected from the actual codebase.

---

# 12. Tool Architecture

The tool system should eventually expose:

```text
Tool
 ├── Name
 ├── Description
 ├── Input schema
 ├── Permission level
 ├── Execution
 ├── Result
 ├── Verification
 └── Execution trace
```

Tools should be:

* Explicit
* Discoverable
* Validated
* Testable
* Observable
* Permission-aware
* Replaceable

---

# 13. Safety and Permissions

As JARVIS gains the ability to act, actions should be classified.

## Read-only

Examples:

* Current time
* File search
* Project inspection
* Git status

## Reversible

Examples:

* Opening an application
* Creating a draft
* Creating a task

## Consequential

Examples:

* Sending a message
* Deleting files
* Modifying important data
* Executing destructive commands
* Making external commitments

Consequential actions should eventually require explicit user approval according to configurable policy.

---

# 14. Task and Goal System

The planning system should eventually connect to persistent tasks and goals.

A natural-language request such as:

> "Remind me tomorrow at 3 PM to work on JARVIS."

should eventually become a real persistent task/reminder.

The system should support:

* Task creation
* Priorities
* Due dates
* Recurrence
* Completion
* Goals
* Goal/task relationships
* Progress
* Follow-up
* Verification

---

# 15. Intelligent Automation

Once individual tools are reliable, JARVIS can begin coordinating multiple tools.

Target workflow:

```text
Goal
 ↓
Understand
 ↓
Plan
 ↓
Execute tool 1
 ↓
Inspect result
 ↓
Execute tool 2
 ↓
Verify
 ↓
Recover if necessary
 ↓
Report
```

Future capabilities include:

* Git workflows
* Build workflows
* Testing workflows
* Documentation workflows
* Workspace automation
* Browser automation
* OS automation
* Multi-step development tasks

Automation should remain controlled rather than unrestricted.

---

# 16. Personal Assistant

Future capabilities include:

* Calendar
* Email
* Notifications
* Reminders
* Task management
* Daily briefings
* Weather
* News
* Productivity assistance

These should be implemented through real integrations and tools.

JARVIS should never imply access to an external system before that integration actually exists.

---

# 17. Multimodal and Environmental Awareness

Long-term capabilities may include:

* Screen understanding
* OCR
* Image understanding
* Browser awareness
* Application state
* Device awareness
* Optional camera/environment awareness

Mature models and libraries should be integrated where appropriate.

The project does not need to build perception models from scratch to achieve these goals.

---

# 18. Multi-Interface Strategy

The long-term system should support multiple interfaces:

```text
                JARVIS CORE
                     │
       ┌─────────────┼─────────────┐
       │             │             │
     Voice        Desktop       Terminal
       │             │             │
       └─────────────┼─────────────┘
                     │
              Web / Mobile
```

The intelligence should live in the shared JARVIS core rather than being duplicated for each interface.

---

# 19. What We Will Not Build From Scratch

Unless a specific requirement justifies it, JARVIS will not build custom replacements for:

* Large language models
* Speech recognition engines
* TTS engines
* Database engines
* Browser engines
* Calendar infrastructure
* Email infrastructure
* Generic scheduling systems
* Mature perception models
* Generic automation infrastructure

Instead, JARVIS will integrate these capabilities behind its own interfaces.

---

# 20. What We Must Build

JARVIS must own:

* Orchestration
* Context
* Memory behavior
* Capability awareness
* Tool selection
* Tool policy
* Conversation state
* Interruption behavior
* Planning
* Task orchestration
* Verification
* Permissions
* User experience
* JARVIS-specific integrations

These are what transform a collection of libraries and models into JARVIS.

---

# 21. Roadmap

## Phase 1 — Foundation

**Status: Complete**

* Voice
* Wake word
* Local AI
* Persistent memory
* Dashboard
* Workspace management
* Core router
* Tool architecture
* Conversation persistence

---

## Phase 2 — Conversational Intelligence

**Status: Active**

Completed:

* Command parsing
* Follow-up detection
* Clarification
* Pending requests
* Topic switching
* Context-aware conversations
* Streaming responses
* Sentence buffering
* Interruptible speech
* Interruption handling

Current priorities:

* Tool-first routing
* Capability awareness
* Grounded responses
* Stronger conversation state
* Better distinction between memory, tool results, and inference

---

## Phase 3 — Software Engineering Intelligence

**Status: Active / foundation built**

Existing:

* Project search
* File search
* Code explanations
* Project context
* Dependency analysis
* Graph analysis
* Impact analysis
* Target resolution
* Symbol/function analysis
* Execution infrastructure
* Planning infrastructure

Next:

* Multi-file reasoning
* Execution-flow explanations
* Architecture analysis
* Code review
* Bug analysis
* Refactoring suggestions
* Test-aware code modification
* Documentation generation
* Change verification

---

## Phase 4 — Planning, Tasks, and Goals

**Status: Next major capability**

* Persistent tasks
* Reminders
* Due dates
* Recurring tasks
* Goals
* Task/goal relationships
* Plan execution
* Progress tracking
* Verification

---

## Phase 5 — Tool and Integration Platform

* Capability discovery
* Tool schemas
* Validation
* Permissions
* Execution traces
* Failure handling
* Result normalization
* Verification
* Git
* Browser
* OS
* Calendar
* Email
* Notifications
* Web research
* External APIs

---

## Phase 6 — Controlled Agentic Workflows

* Multi-step planning
* Tool chaining
* Conditional execution
* Retry/recovery
* Approval gates
* Progress
* Cancellation
* Execution history

---

## Phase 7 — Proactive Personal Assistant

* Reminders
* Daily briefings
* Scheduled summaries
* Notifications
* Calendar
* Email
* Productivity workflows

---

## Phase 8 — Multimodal Awareness

* Screen
* OCR
* Images
* Browser state
* Application state
* Device awareness

---

## Phase 9 — Multi-Interface JARVIS

* Voice
* Desktop
* Terminal
* Web
* Mobile
* Messaging

---

## Phase 10 — AI Operating Layer

The mature JARVIS system becomes a personal AI operating layer capable of coordinating:

* Conversation
* Memory
* Tasks
* Goals
* Software engineering
* Computer interaction
* Research
* Automation
* External services
* Proactive assistance

while remaining grounded and user-controlled.

---

# 22. Engineering Principles

When adding new features:

1. Prefer composition over duplication.
2. Extend existing capabilities before creating duplicates.
3. Build JARVIS-specific logic; integrate mature infrastructure.
4. Every service should have a clear responsibility.
5. Avoid giant files.
6. Test after every meaningful implementation.
7. Refactor before major capability expansion when needed.
8. Prefer deterministic tools over LLM guesses.
9. Never claim an action or observation that did not occur.
10. Keep providers replaceable.
11. Keep consequential actions under explicit user control.
12. Favor maintainability over unnecessary complexity.

---

# 23. Coding Standards

* Meaningful function names
* Small functions
* Clear separation of concerns
* Minimal global state
* Strong typing where practical
* Consistent formatting
* Helpful debug logging during development
* Remove temporary debug statements before release
* Tests for new behavior
* Clear tool contracts

---

# 24. Session Workflow

Each development session should follow this process:

1. Review the current milestone.
2. Review the actual project state.
3. Define one implementation goal.
4. Determine whether the capability already exists.
5. Decide whether to extend, integrate, or build.
6. Design before coding.
7. Implement incrementally.
8. Test immediately.
9. Refactor if necessary.
10. Run the relevant test suite.
11. Check the Git diff.
12. Commit a stable milestone.
13. Push to GitHub.
14. Update roadmap/master plan when the direction changes.

---

# 25. Current Priority

The immediate strategic priority is:

> **Make JARVIS grounded and reliable before making it substantially more autonomous.**

The next sequence is:

1. Strengthen tool-first routing.
2. Add capability-aware AI behavior.
3. Prevent fabricated capabilities and observations.
4. Improve conversational state.
5. Strengthen tool result handling and verification.
6. Turn planning infrastructure into persistent tasks/reminders.
7. Continue expanding developer-assistant workflows.
8. Build multi-step automation only after individual capabilities are reliable.

---

# 26. Success Definition

JARVIS succeeds when it becomes a reliable personal system rather than merely an impressive demo.

It should:

* Remember what matters.
* Understand current context.
* Know its capabilities.
* Use real tools.
* Avoid hallucinating actions or observations.
* Interrupt naturally.
* Handle follow-ups.
* Understand software projects.
* Execute useful workflows.
* Verify important actions.
* Remain modular.
* Remain maintainable.
* Remain under the user's control.

---

# 27. Future Vision

By the mature version of JARVIS, interacting with it should feel like collaborating with an experienced software engineer and personal assistant—one that understands projects, remembers useful information, reasons through problems, uses real tools, and helps accomplish meaningful work.

The objective is not to build the largest AI system.

The objective is to build **your JARVIS**.
