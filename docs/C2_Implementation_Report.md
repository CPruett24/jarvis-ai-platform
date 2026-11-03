# Milestone C2 implementation and Checkpoint 6 verification

Status: **Checkpoint 6A verification passed; GO recommendation pending user review. Not formally accepted or committed.**

Baseline: `b4db84c6b1c2d9664eb2f648e5e8391fc88fea9f` on `main`.
Checkpoints 1-5 supplied 32 approved, uncommitted files. Checkpoint 6 adds acceptance
infrastructure, adversarial tests, measurements, and this report. It makes no
runtime implementation changes and does not raise budgets or weaken validation.
Checkpoint 6A's subsequent minimal timeout correction and current results are
recorded in section 17; they supersede the original real-model blocker below.

## 1. Scope and architecture

C2 provides bounded, read-only Python source relationships through the existing
`multi_file_reasoning` capability and `project_relationships` registered tool.
The canonical path is captured authorization/request -> safe inventory and reads
-> AST symbols/imports/calls -> graph/traversal/impact -> selected source evidence
-> deterministic propositions -> validated answer -> consumer freshness gate.
Normal router answers are deterministic and require no model. Optional local AI
can order approved proposition IDs; it cannot supply claims or resolve targets.

C2 extends the existing services, capability registry, router, conversation topics,
response queue, speech lifecycle, and response receipts. Legacy approximate
analyzers remain available on their existing routes, restricted to their original
JARVIS project context; their output is never authoritative C2 evidence.

## 2. Contracts and identity

`models/project_relationships.py` contains immutable project, source, symbol,
relationship, coverage, snapshot, and analysis records. Project identity includes
registered project ID, canonical absolute root identity, and authorization revision.
Source provenance includes canonical relative path, digest, source ID, inclusive
line range, and zero-based columns. Stable symbol IDs include qualified identity
and definition location; relationship IDs include the actual endpoints and support.
Snapshots include inventory, exclusions, fingerprints, coverage, options, and schema.

`models/project_graph.py` defines canonical graph arcs, traversal steps, reverse
impact connections, and freshness outcomes. `models/relationship_answer.py` keeps
source windows/support mappings, approved propositions, and answer outcomes separate
from canonical records. Retained graphs never permanently assert publication readiness.

## 3. Extraction rules

`analyze_project_relationships` uses C1 discovery and `read_analysis_source`.
Python files are parsed as AST data, never imported or executed. Lexical function,
async function, class, method, nested scope, and module definitions retain source
locations. Imports resolve only against the authorized bounded inventory, including
relative imports, aliases, and directly defined members. Call resolution uses
lexical/import bindings and a deliberately limited explicit-attribute subset.

Conditional/reassigned/wildcard/re-export bindings, arbitrary receiver dispatch,
callbacks, inheritance, decorators, reflective mutation, and unsupported dynamic
constructs remain uncertain instead of becoming guessed edges. Resolutions distinguish
confirmed static, inferred, unresolved, ambiguous, and incomplete records. A confirmed
static relationship describes source binding, not observed runtime execution.

## 4. Traversal and impact

Call and import graph views preserve canonical relationship IDs. Import graphs project
file endpoints onto existing module symbols. Forward/reverse traversal uses the same
arcs, with explicit root, expanded, cycle, shared, revisited, and cutoff classifications.
Cycles are path-local; shared descendants are not mislabeled as recursion. Reverse
unknown-call boundaries prevent unsupported project-wide absence claims.

Function impact follows reverse calls. File impact supports distinct call/import
views internally; the current conversational impact adapter selects the call view.
Results say "Potentially affected" and explicitly do not establish runtime breakage.
Two-target connection questions return an explicit contract limitation, suggesting
a forward trace or reverse callers; they do not invent a connecting path.

## 5. Evidence and answer validation

Evidence selection preserves original edge IDs and maps call/import sites, binding
sites, and definition headers to bounded source windows. Validators recheck exact
canonical membership, direction, trace closure, completeness, support ranges,
fingerprints, actual source text, approved propositions, and strict C1 citations.
A valid citation beside a substituted false relationship is rejected.

Optional model input contains only the snapshot ID, approved proposition IDs, and
fixed categories: no source comments, paths, identifiers, or user question. Its only
accepted output is an exact JSON permutation of every approved ID with the original
snapshot ID. At most one regeneration is allowed; invalid output is discarded and
deterministic order is used if the original request budget remains available. Budget
expiry refuses publication instead of bypassing checks to render a fallback.

## 6. Routing and conversation

Explicit grammar supports forward calls, reverse callers, imports, reverse dependents,
traces, potential impact, connection limitations, and relationship follow-ups.
Termination, historical recall, capability management, C1 single-file requests, and
conceptual questions retain precedence. Explicit C2 failures do not delegate to
Hermes or generic AI. Identifier case and qualified paths are preserved. Basename
duplicates require clarification; `./leaf.py` explicitly identifies a root-level path.

Topics retain project/revision, operation, exact target, direction, depth, and relevant
comparison input. Follow-ups create fresh analysis; topics never authorize roots or
reuse retained graphs as current. Project switching/revocation/re-registration makes
old context stale. Capability disablement is checked at admission and delivery.

## 7. Authorization and publication safety / Phase A

Review covered the cumulative diff, added contracts/services/tests, C1 Windows safe
reads, capability registration, router precedence, and producer/consumer publication.
No unexpected changes to the approved 32-file foundation were found. The only
Checkpoint 6 change within that foundation is the test runner's explicit acceptance
dispatch; application code is unchanged.

Every C2 request validates its captured context against the active registry revision.
No source path, topic, model output, or analyzer registers a root implicitly. Reads
retain containment/exclusions and Windows ancestor-handle/reparse/hard-link defenses.
No project module execution, dynamic runtime module loading, unrestricted filesystem
tool, or external resolver is introduced. This remains a Windows implementation.

The unchanged CP3 gate requires complete declared coverage, no relevant unresolved
boundaries, no truncation, current authorization, and current inventory/fingerprints.
Freshness uses two inventory passes and digest re-reads under the same request budget.
Queued successes are checked again on the existing consumer before side effects.
Incomplete results do not release partial factual answers.

No security-boundary defect requiring a runtime correction was confirmed by this
review and deterministic acceptance. This is bounded verification, not a proof of
complete resistance to malicious source syntax/comments or concurrent filesystem change.

## 8. Budgets and Phase C measured workloads

Normal defaults are unchanged: 256 Python files; 8 MiB cumulative source reads;
512 KiB/file; 50,000 AST nodes/file and 200,000 total; 10,000 relationships;
maximum depth 4; 200 visited symbols; 500 charged traversed edges; 8 evidence
excerpts across 6 files; 32 selected relationships; 24 KiB organizer payload;
and a five-second cooperative request deadline. Router default depth is 2.
Evidence additionally caps windows at 120 lines and source text below 12 KiB.
Nested stages do not reset allowances; validation/re-reads also consume them.

The final offline acceptance run used disposable fixtures and a byte copy of Python
files from `services`, `commands`, and `models`. Copied code was only parsed as data.
No production data/configuration was copied or executed. All limits stayed at defaults.

| Workload | Discovered / parsed | Initial source bytes | AST nodes | Indexed relationships | Analysis seconds | Freshness seconds / state | Publishable |
|---|---:|---:|---:|---:|---:|---|---|
| 96-file independent callers | 96 / 96 | 5,143 | 859 | 190 | 0.250 | 0.141 / verified | Yes |
| Eight-file call chain | 8 / 8 | 395 | 67 | 14 | 0.032 | 0.000 / unverified | No: depth cutoff |
| Repository Python copy | 95 / 95 | 583,294 | 70,477 | 5,128 | 1.421 | 0.000 / unverified | No: depth cutoff and 63 relevant boundaries |
| File-budget overflow | 300 / 256 | 7,058 | 1,024 | 0 | 1.593 | 0.000 / unverified | No: Python-file budget exhausted, coverage incomplete |

The zero freshness timings mean the graph gate refused incomplete work before a
fingerprint pass; they are not claims of instantaneous full-source validation.
On overflow, extraction stops before relationship resolution; zero indexed edges
does not mean the project has no relationships.

| Workload | Traversal steps | Charged visited symbols / edges | Selected excerpts | Total charged excerpts / files | Total source bytes | Total seconds |
|---|---:|---:|---:|---:|---:|---:|
| 96-file independent callers | 2 | 2 / 7 | 2 | 4 / 4 | 15,657 | 0.687 |
| Eight-file call chain | 3 | 3 / 2 | 0 | 0 / 0 | 395 | 0.032 |
| Repository Python copy | 30 | 20 / 112 | 0 | 0 / 0 | 583,294 | 1.828 |
| File-budget overflow | 1 | 1 / 0 | 0 | 0 / 0 | 7,058 | 1.609 |

Measurement explicitly selects evidence before invoking the actual answer pipeline;
the successful case therefore charges two selections. Edge charges include validation
work, not just distinct graph arcs. These are single local runs, not latency guarantees.
The three refusals are expected conservative limitations, not routing or freshness
defects. The real-model deadline failures below are a separate performance limitation.

## 9. Deterministic acceptance / Phase B

All C2 focused tests: **283 passed, 0 skipped, 0 failed, 1 warning**, 6.16 seconds.
This includes **21 new Checkpoint 6 tests** and all previous checkpoint tests.
The final standalone guarded acceptance session passed **10/10 scenarios** using
the real router/capability and a fake organizer, with eight provider calls total.

New independent oracles construct expected call records from fixture bytes, manually
specified definition/call/import ranges, endpoints, classifications, and context-bound
source IDs; exact resulting relationship IDs and ordered trace steps must match.
Import endpoint/column/direction expectations are independently enumerated.

Coverage includes forward/reverse calls and imports, traces, impact, qualified/case-
sensitive targets, duplicate filenames/symbols and exact clarification, relative paths,
follow-up depth/direction, missing/unsupported connection requests, cycles/shared
descendants, limits, accurate source references, added/removed/edited sources,
revocation/switching, excluded/outside paths, incomplete refusal, and no fallback.

Adversarial checks reject fabricated IDs, valid citations beside false claims, wrong
trace direction, partial graphs labeled complete, stale snapshots, and foreign project
records. Malicious source comments do not appear in organizer payloads or final claims.
Invalid ordering retries once against identical approved evidence, then falls back
deterministically when time remains. Cancellation inside the provider causes no
history, speech, or topic publication. Initial oracle development corrected an expected
support column to the actual import-alias site; no application code was changed.

## 10. Guarded real Ollama / Phase D

**Executed, not fully passed: 5/10 scenarios passed; 5/10 failed.**
The existing guard verified installed local GGUF `llama3.1:8b` through the pinned
loopback client. External networking, subprocesses, production SQLite, real microphone,
speech playback, and Hermes remained blocked. Client timeout was 30 seconds, outer
guard watchdog 120 seconds; each analysis retained its five-second shared deadline.

Normal C2 router responses do not use an LLM. The acceptance harness explicitly opted
the existing adapter into optional model ordering through the existing registry; it
did not change runtime defaults. Model prose never became source claims.

| Scenario | Result | Model calls | Seconds |
|---|---|---:|---:|
| Forward calls | Failed safely: request deadline | 1 | 11.047 |
| Reverse callers | Passed with source citations | 1 | 4.500 |
| Import dependencies | Failed safely: request deadline | 1 | 5.031 |
| Potential impact | Failed safely: request deadline | 1 | 6.375 |
| Relationship follow-up | Failed safely: request deadline | 1 | 7.016 |
| Ambiguous target | Passed: deterministic clarification | 0 | 0.015 |
| Qualified clarification | Passed with source citation | 1 | 1.579 |
| Missing target | Passed: grounded not-found | 0 | 0.000 |
| Invalid ordering / fallback | Failed safely: deadline during two attempts | 2 | 6.812 |
| Incomplete analysis | Passed: no partial facts | 0 | 0.016 |

All fixtures included an adversarial comment requesting fabricated paths/runtime
claims; no returned answer included it. This verifies the fixture's isolation and
deterministic rendering, not comprehensive injection resistance. The invalid-order
scenario deliberately replaced actual local responses with invalid IDs at the trusted
harness seam; two real calls occurred, but no fallback could publish after expiry.
Successful deterministic fallback is established separately by fake-provider tests.

Root cause: local ID ordering plus validation can exceed five seconds, including
the initial model load. Checks correctly refuse late results. There was no observed
citation fabrication, invented edge, authorization bypass, or ungrounded fallback.
No larger budget, shortened validation, hidden warm-up, or substitute fake result
was used to turn these failures into a pass. Optional-model performance remains a
blocker for claiming complete requested real-Ollama acceptance.

## 11. Cancellation and delivery

Deterministic tests cover cancellation before/during/after generation, graph/evidence
stages, organizer calls/retry, freshness, queued publication, and late producer output.
The adapter is side-effect free. The consumer owns observations, history, topics,
and speech. Cancellation checks guard these effects and discarded late results.
The existing producer semaphore, bounded queue, watchdog, interrupt controller,
handoff, response receipt, and cleanup remain in use. Receipt tests cover completed,
interrupted, timed-out, and failed playback outcomes with fake speech engines.
Full text retains source citations; speech omits citation metadata while preserving
static-analysis and potential-impact qualifications.

Cancellation is cooperative. A synchronous local provider call may continue until
its existing transport timeout; checks prevent publication when it returns late.
Real microphone, audible playback, and real-model cancellation were **NOT TESTED**.

## 12. C1 / Milestone B / legacy compatibility and Phase E

Focused compatibility selection: **563 passed, 2 skipped, 0 failed, 156 warnings**,
38.14 seconds. It explicitly covered C1 source/authorization/routing/citations,
Milestone B historical recall and playback attribution, voice/interruption/cancellation,
and legacy analysis/dependency/execution/graph/impact/target services.

Final full guarded suite: **1,401 passed, 3 skipped, 0 failed, 158 warnings**,
50.00 seconds. All previous tests plus the 21 new acceptance tests ran. No runtime
or test code changed after this run began; only this report was added/finalized.

The three skips are the unavailable Hermes executable (no invocation), unavailable
Windows symlink privilege, and the legacy real-child-process test prohibited by
the guard. Warnings comprise the already imported `anyio` rewrite warning, the
unregistered legacy `integration` marker, 155 SQLAlchemy `datetime.utcnow()`
deprecations, and the existing ONNX Windows-version warning. The focused C2
selection has just the `anyio` warning; the compatibility selection has that warning
plus the 155 deprecations. No test failure remains in the final guarded run.

Existing compatibility changes from CP5 remain documented: `./` exact target syntax,
and moving the legacy refresh regression onto "what would break" wording because
"what would be affected" now intentionally selects canonical C2. No legacy analyzer
implementation was removed. C1's citation validator/retry and source guards remain.

## 13. Known limitations and untested behavior

- Python static subset only; arbitrary runtime dispatch, re-exports, inheritance,
  dynamic imports/callbacks, and external dependency bodies are not proven.
- Complete-result policy deliberately refuses many realistic project-wide questions;
  the copied repository trace was not publishable despite complete parsing.
- Depth/evidence limits can refuse long or broad paths; no partial facts are released.
- Two-target connection queries have an explicit limitation, not a path-finding feature.
- Grammar is deterministic and bounded; conversational file impact currently uses calls.
- Optional real-model ordering may not complete within the five-second budget;
  Checkpoint 6A now bounds/skips it and preserves validated deterministic fallback.
- Freshness is a check-time guarantee, not an atomic snapshot of a concurrently edited
  project. No claim of complete malicious-source resistance or runtime execution proof.
- Windows safe reads are required. One symlink test could not run on this account;
  a real child-process voice test remains forbidden by the guard.
- No live voice acceptance, production-data exercise, external integration acceptance,
  unrestricted project execution, or exhaustive real-project reasoning acceptance.

## 14. Exact cumulative changed-file manifest

**36 files**, excluding all protected/pre-existing entries. CP6 modifies only the
existing C2 runner and adds the acceptance script, acceptance tests, and this report.
The prior report's accidental `commands/actions.py` row is not part of C2.

```text
commands/registry.py
commands/router.py
docs/C2_Implementation_Report.md
models/project_graph.py
models/project_relationships.py
models/relationship_answer.py
scripts/accept_c2.py
services/ai_service.py
services/capability_executor.py
services/capability_registry.py
services/code_intent.py
services/conversation_manager.py
services/project_analysis_cache.py
services/project_analysis_freshness.py
services/project_analysis_index.py
services/project_analysis_request.py
services/project_dependencies.py
services/project_execution.py
services/project_graph.py
services/project_impact.py
services/project_relationship_answer.py
services/project_relationship_capability.py
services/project_relationship_evidence.py
services/project_retrieval.py
services/project_symbol_index.py
services/project_target.py
tests/run_c2_regressions.py
tests/test_c2_acceptance.py
tests/test_c2_capability_routing.py
tests/test_c2_graph_traversal.py
tests/test_c2_ordering_timeout.py
tests/test_c2_relationship_answers.py
tests/test_c2_relationship_extraction.py
tests/test_project_analysis_request.py
tests/test_project_impact.py
tests/test_project_relationships.py
```

## 15. Reproduction, artifacts, and worktree safety

Run from `C:\Projects\JARVIS-AI`:

```powershell
.venv\Scripts\python.exe -B tests/run_c2_regressions.py --acceptance
.venv\Scripts\python.exe -B tests/run_c2_regressions.py --acceptance --real-ollama
.venv\Scripts\python.exe -B tests/run_c2_regressions.py -q --tb=short -rs
```

The first command uses a fake organizer and measures four workloads. The second
requires the already installed configured `llama3.1:8b`; it neither downloads a
model nor starts Ollama. It is text-only; after Checkpoint 6A the scenarios pass
with bounded ordering and deterministic fallback. Regression mode never enables loopback.
Unsupported arguments are rejected. The C2 runner reuses the C1 audit admission,
voice/bootstrap isolation, and watchdog with fresh OS temp storage, not `.c1-test-runs/`.

Executed final offline artifact:
`C:\Users\pruet\AppData\Local\Temp\jarvis-c2-3jjtjsp_\c2-acceptance-4k16inky\results.json`.
Executed real-model artifact:
`C:\Users\pruet\AppData\Local\Temp\jarvis-c2-81j65rnq\c2-acceptance-vzeo8aih\results.json`.
These artifacts and all fixture sources are outside the working tree and manifest.

Protected baseline SHA-256 values:

```text
AGENTS.md       CB5D4D2CD99FFC5F7E6B7DDA2DC4DDA3E48D56674530DD0E13B43D3DD7F1BA20
Codex_Rules.md  584761876D2885B379DA5C1441B6BB7458245871259B640DBF2D8E62A7B69EBC
data/status.json E5E0DF1BDA27A741D1C9749168C859C1D0629C80242995CC4F6C58C868152080
```

`.c1-test-runs/` was not used or modified; its baseline directory timestamp is
2026-11-02 22:45:13 UTC. Its existing inaccessible child remains untouched.
The preserved modified `data/status.json` and untracked `AGENTS.md`, `Codex_Rules.md`,
and `.c1-test-runs/` are explicitly excluded from C2. No Git index/commit/branch
mutation, package installation, production SQLite, microphone startup, external
service use, Hermes invocation, or analyzed-code execution was authorized or performed.

Final checks confirmed all three protected hashes above still match, and the C1
artifact directory timestamp is unchanged. The exact C2 working-tree set matches
the cumulative manifest; no unexpected implementation/configuration paths appeared.
`git diff --check` and cumulative new-file whitespace checks passed.
Git remains on the baseline `main` with an empty index and all C2 work uncommitted.
The pre-existing protected working-tree entries remain as originally found.

## 16. Original Checkpoint 6 recommendation (superseded by 6A)

**NO-GO for committing C2 as fully accepted.** Deterministic security/correctness
acceptance passes, but optional real-Ollama ordering failed five requested scenarios
under the preserved deadline. Review must resolve that acceptance scope/performance
issue before a milestone acceptance or commit claim. The safe default deterministic
path and conservative realistic-workload refusals are separately verified.
No additional feature work, staging, commit, or push has been performed. Await review.

## 17. Checkpoint 6A: optional ordering timeout correction

### Confirmed root cause

Ordering starts after canonical relationship validation and evidence selection in
`answer_relationships`, before deterministic rendering and final source/inventory
freshness. Previously the organizer called the normal synchronous `chat` interface
without a remaining-time allowance. The acceptance client allowed 30 seconds;
the installed Ollama `chat` method has no per-call timeout argument. Cancellation
and deadline checks occurred only after the blocking call returned. The optional
invalid-output retry could spend the remaining request time as well.

Thus a valid deterministic answer was not recoverable after the shared five-second
deadline expired: rendering and publication must still validate current evidence.
No bypass was appropriate. Original pre-order remaining times were not logged, so
their precise values cannot be reconstructed from the old total-duration records.
The correction now reads the original clock/deadline directly at admission and
before each attempt. Tests explicitly exercise one second remaining and verify
that ordering is skipped without renewing the deadline.

The harness intentionally enables optional ordering. Ordinary C2 routing still
uses deterministic rendering and does not require the model.

### Exact changes

Checkpoint 6A changes these seven paths:

```text
docs/C2_Implementation_Report.md
scripts/accept_c2.py
services/ai_service.py
services/project_analysis_request.py
tests/test_c2_acceptance.py
tests/test_c2_ordering_timeout.py
tests/test_c2_relationship_answers.py
```

`AnalysisBudget.remaining_seconds` exposes the existing request deadline under
the same lock, observing cancellation and expiry without resetting it.
`bounded_relationship_chat` creates and closes a request-local Ollama client with
an explicit timeout, redirects/environment proxy use disabled, and the configured
endpoint (localhost pinned numerically). No shared client timeout is mutated and
no local worker/background generation thread is introduced. The ordinary `chat`
interface and all C1 callers remain unchanged.

The organizer reserves `max(1 second, remaining / 2)` for final validation and
admits optional work against `min(1 second, remaining - reserve)`. It skips ordering
if less than 0.1 seconds is available or the timeout-capable callable is unavailable.
Before each of at most two attempts it subtracts elapsed time from that SAME optional
allowance; less than 0.05 seconds remaining prevents another call. Each transport
timeout is at most 0.4 seconds and is further reduced by the remaining optional
allowance divided between remaining attempts. Payload/relationship/source limits
and the proposition-ID-only validator remain unchanged.

Invalid/failed/timed-out ordering falls back to deterministic order only through
the existing rendering, authorization, citation, relationship, and freshness path.
Expired deadlines, cancelled operations, stale sources, revoked authorization,
incomplete coverage, and genuine analysis failures still refuse publication.
No analysis semantics or CP3/CP4 gate checks were changed.

The acceptance harness was adapted explicitly to the new timeout-capable seam and
counts attempted calls before invocation (a timeout is an attempted provider call).
No scenario, expected success, or two-attempt invalid-order assertion was removed
or relaxed. Existing fake-provider tests now patch the same timeout-capable seam.

### Corrected guarded real-Ollama results

The unchanged command was executed:

```powershell
.venv\Scripts\python.exe -B tests/run_c2_regressions.py --acceptance --real-ollama
```

Installed local GGUF `llama3.1:8b`, pinned loopback guard, disposable fixture/storage,
no microphone, no audible playback, no Hermes, no external service, no model install.
**10/10 scenarios passed**, versus the original **5/10**. Fourteen bounded provider
attempts were recorded; successful answer delivery may use deterministic fallback
and is not a claim that the model itself returned a valid ordering each time.

| Scenario | Original result / seconds | Corrected result / seconds | Corrected attempts |
|---|---|---|---:|
| Forward calls | Refused / 11.047 | Passed / 1.140 | 2 |
| Reverse callers | Passed / 4.500 | Passed / 1.110 | 2 |
| Imports | Refused / 5.031 | Passed / 1.156 | 2 |
| Potential impact | Refused / 6.375 | Passed / 1.125 | 2 |
| Follow-up | Refused / 7.016 | Passed / 1.141 | 2 |
| Ambiguity | Safe clarification / 0.015 | Safe clarification / 0.000 | 0 |
| Qualified clarification | Passed / 1.579 | Passed / 1.140 | 2 |
| Missing target | Safe not-found / 0.000 | Safe not-found / 0.016 | 0 |
| Invalid ordering / fallback | Refused / 6.812 | Passed / 1.141 | 2 |
| Incomplete analysis | Safe refusal / 0.016 | Safe refusal / 0.015 | 0 |

Artifact:
`C:\Users\pruet\AppData\Local\Temp\jarvis-c2-d59xrk6w\c2-acceptance-xs084h01\results.json`.
The forced-invalid scenario retains its original fault injection; timeouts can also
cause deterministic fallback. Invalid-ID rejection and retry are independently
proven by deterministic fake-provider tests, not inferred from real-model timings.

### Regression and safety results

- Focused ordering/acceptance/shared-budget selection: **121 passed**, one warning.
- All C2 tests, including 12 new correction tests: **295 passed**, no skips/failures,
  one existing warning, 6.31 seconds.
- C1/Milestone B/voice/cancellation compatibility selection: **409 passed, 2 skipped**,
  no failures, 156 existing warnings, 7.09 seconds.
- Full guarded suite: **1,413 passed, 3 skipped, 0 failed, 158 existing warnings**,
  51.30 seconds. Skip reasons remain those listed in section 12.

New tests cover slow/timeout/invalid providers, one bounded retry, reserve protection,
insufficient time, unavailable bounded interface, deterministic fallback, exhausted
deadline, cancellation, stale source, revocation, and actual-router history/speech/topic
effects. Existing C2 strict completeness and no-fallback tests also pass.

Protected hashes and `.c1-test-runs/` timestamp remain unchanged. The cumulative
manifest now contains 36 paths; all remain uncommitted, with an empty index.
Diff and new-file whitespace checks pass. Only report documentation was finalized
after the full regression run; no functional code changed afterward.

### Remaining limits and recommendation

HTTPX timeouts bound individual connect/read/write/pool waits, not an absolute
wall-clock duration for every network/OS operation. The one-second optional allowance
is a cooperative admission target, not a hard real-time guarantee. Checks against the
original five-second deadline remain authoritative after calls and at publication.
Slow OS work or a provider failing its timeout contract can still cause safe refusal;
fallback never resurrects an expired request. Closing the local transport does not
claim to stop all computation inside the external Ollama server. No returned late
model output can mutate application history, speech, or topics.

The fixed reserve is conservative admission policy, not a guarantee that every
project's validation fits it. Ordinary C2 remains model-free; incomplete and broad
project analyses and two-target connections retain their original limitations.
Live voice and real-model cancellation remain untested. No comprehensive malicious
source resistance or runtime reasoning proof is claimed.

**GO recommendation for review/commit readiness of the implemented C2 scope.**
The observed optional-model deadline blocker is resolved under guarded acceptance.
Formal milestone acceptance and any staging/commit still require explicit user
review and authorization. No Git mutation has been performed. Stop after Checkpoint 6A.
