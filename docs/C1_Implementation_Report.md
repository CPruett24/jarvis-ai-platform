# Milestone C1 implementation and acceptance report

Date: 2026-10-17

Status: **Milestone C1 accepted for its implemented scope on 2026-11-02.**
The user reported successful guarded real-Ollama acceptance and explicitly
authorized the approved 37-file manifest and one local commit. No push is authorized.

## User-run guarded real-Ollama acceptance (2026-11-02)

The user confirmed acceptance using **llama3.1:8b** in the guarded disposable
fixture environment:

- All four representative source requests succeeded: project file inventory,
  actions.py summary, router explanation, and project conversation-history explanation.
- All three previously failing project-question paraphrases subsequently succeeded
  with source citations: "Tell me how this project handles conversation history",
  "Explain how the router handles commands", and
  "Find out how this project handles conversation history".
- Missing, excluded, and outside-root requests failed safely.

This is user-reported acceptance of the implemented C1 scope. It does not establish
comprehensive real-project reasoning, live voice behavior, or complete resistance
to malicious source comments. Existing test skips and security limitations remain
documented below and are not waived by this acceptance. Historical verification
entries describe the checks performed at their respective checkpoints.

## Citation-generation acceptance correction (2026-11-02)

The user's real-Ollama run successfully retrieved source for the three reported
paraphrases but rejected the generated answers. Inspection identified a single-shot
generation pipeline: the prompt required `[source_id]`, while the strict validator
required a real retrieved ID or covered path/range in every paragraph. There was
no recovery for omitted citations, literal placeholder tokens, or an uncited
introduction beside otherwise valid citations. All reference failures shared one
generic error. The raw rejected model answers were not supplied or retained, so
the precise syntax defect in each live answer cannot be established retrospectively.
Missing tokens versus malformed tokens versus an uncited paragraph remain possible;
there is no evidence here of a reference-normalization or retrieval defect causing
these particular failures. The demonstrated engineering defect is relying on one
model attempt to satisfy the strict citation contract without bounded recovery.

`generate_source_answer` now lists exact allowed tokens and forbids uncited headings
and introductions. It validates the first answer and, only on rejection, regenerates
once with explicit citation instructions and the original evidence/question/limits.
Rejected prose is never supplied as evidence or repaired by attaching citations.
Both attempts are checked by the unchanged `validate_answer`; callers still reject
invalid output and revalidate current source/authorization before publishing success.
The capability reports a grounded limitation after two invalid attempts. Provider
exceptions preserve the existing generation-failure outcome; cancellation propagates.
The shared generator also covers the existing evidence-backed explanation callers.

Only four existing C1 files changed for this correction (addendum to the manifest):

```text
services/ai_service.py
services/source_answer.py
tests/test_c1_source_routing.py
docs/C1_Implementation_Report.md
```

Verification for this correction:

- Final focused routing/reference/acceptance-guard run: **144 passed**, 0 failed.
- Full guarded repository suite: **1118 passed, 3 skipped, 0 failed**, 44.49 seconds.
  The existing harness skip policy is unchanged. Warnings concern existing pytest
  configuration, datetime deprecation and the ONNX platform probe.
- Guarded noninteractive offline text acceptance: passed, including all three
  reported paraphrases and safe missing/excluded/outside-root failures.
- `git diff --check`: passed; final correction diff reviewed. Real Ollama was not run.

Deterministic regressions cover all three observed paraphrases crossed with omitted
citations, literal placeholders, unknown IDs, fabricated filenames, invalid ranges,
and reversed ranges; successful retry, failed retry capped at two calls, source edits
during retry, cancellation during retry, and interruption while retry is blocked.
The existing validator and authorization boundaries are unchanged. The full guarded
runner retains its watchdog, network/hardware/subprocess denial and production
SQLite/data protection. No separate sandbox source copy is used: the runner imports
this working tree and creates fresh disposable fixture roots. Existing disposable
records are preserved. No microphone, production SQLite, external service, staging,
commit, or push was used for this correction.

Repeat real-model acceptance from `C:\Projects\JARVIS-AI` with the existing local
Ollama server/model (this command was not executed during this correction):

```powershell
.venv\Scripts\python.exe tests/run_c1_regressions.py --acceptance --real-ollama --interactive
```

Expect cited interpretations for all three reported paraphrases, or an explicit
limitation after one regeneration; missing, excluded and outside-root requests must
still fail safely. Check claims against the displayed fixture excerpts. Citation
validation verifies reference membership/ranges and paragraph coverage, not semantic
entailment. Retrieval remains lexical and may include less relevant excerpts. Retry
can add one provider call; blocking calls still rely on the unchanged client timeout,
interruption mechanism and overall 120-second watchdog. The subsequent user-run
guarded real-model acceptance passed; C1 is accepted for its implemented scope.

## Implemented architecture

The existing router, capability registry/executor, project service, analysis cache,
and AI service remain the execution path. No additional agent framework, vector
database, external source index, or independent code-analysis engine was added.

1. `project_access` provides an explicit default `jarvis` project, trusted
   registration/revocation, deterministic authorized-project listing, and active
   selection. Registration is process-local and is not exposed as a model tool.
2. `source_evidence` defines retrieval outcomes, coverage limits, operation IDs,
   source IDs, project/revision identity, relative paths, one-based inclusive
   ranges, timestamps, signatures, whole-file digests, and truncation metadata.
3. `project_service` orchestrates deterministic discovery, filename resolution,
   lexical retrieval, and bounded excerpts. `project_retrieval` owns filesystem
   mechanics and the shared exclusion policy.
4. `source_answer` exposes the registered `project_source` capability and pure
   summary/explanation adapters. Availability of the relevant existing capability
   is checked as well as availability of `project_source`.
5. The existing AI service generates interpretations from retrieved excerpts only.
   Source IDs are validated and rendered into paths/ranges by JARVIS. Source text
   is untrusted data; source prompts contain no callable tools or external agents.
6. The existing router owns speech, observed-information retention, interpretation
   attribution, topics, clarification, interruption, and watchdog behavior.

Historical recall, lifecycle controls, and capability-management precedence are
preserved. Existing topic-transition and explicit file-command routes are retained;
their file execution now enters the C1 capability path. Failed retrieval does not
fall back to conversational generation. Ambiguity prompts require relative paths;
follow-ups recheck active project, authorization revision, and capability state.

Project topics carry project ID and authorization revision. Source follow-ups
retrieve again rather than treating old assistant messages as current source.
Stale-topic follow-ups explicitly request a new project question.

## Analyzer reuse and compatibility

Existing AST, symbol, dependency, graph, impact, execution-trace, and project-index
implementations remain in place. Their default-project source reads now use the
authorized reader, including module-path policy checks. AST/content cache keys
include project identity and authorization revision.

Additional projects support discovery, source reading, lexical excerpt retrieval,
and authorized AST reading. Legacy relationship/index analysis is explicitly
restricted to the default project until its root assumptions are migrated.
There is no claim that C1 provides verified cross-project relationships or full
multi-file reasoning. The existing unavailable capability remains unavailable.

Public source-reader interfaces retain their dictionary/None compatibility shape,
with evidence added to successful reads. Whole-file line counts are retained.
Duplicate filenames are no longer silently resolved to the first match. Invalid
UTF-8 and excluded/oversized files are rejected rather than silently decoded.
Top-level inventory remains top-level; recursive readable-file discovery is added.
Inventory and file search use the authorized project rather than the working
directory. Safe filtering intentionally omits runtime and sensitive entries.

No database schema migration or existing configuration change is required.
Additional root registration lasts for the process lifetime. Trusted setup can use:

```python
from services.project_access import register_project, select_project, list_projects

# Only after the user deliberately authorizes this exact local root:
register_project("demo", r"C:\Authorized\Demo")
select_project("demo")
```

Natural commands include `List authorized projects`, `Select project demo`,
`Show the file actions.py`, and `Show all files in this project`. A spoken path,
workspace name, memory, working directory, or model-generated path never registers
a root. Selecting an unknown project fails.

## Security boundaries

- Source access is read-only. It never imports or executes discovered code,
  starts project commands, installs dependencies, or writes an index to a project.
- Paths are relative to an authorized canonical root. Traversal, absolute paths,
  UNC/device paths, alternate data streams, and symlink/reparse traversal are denied.
- Windows directory handles are pinned against deletion/replacement while opening
  and reading. Actual handle attributes are checked for reparse points. Source
  handles disallow concurrent writes/deletion; hard-linked source files are denied.
- Hidden files/directories, VCS internals, dependencies, generated output, runtime
  data, logs, databases, credentials, keys, and common sensitive configuration
  names are excluded. Explicit paths cannot override policy.
- Default limits: 10,000 visited entries, 512 KiB per file, 16 MiB per search,
  eight excerpts, 120 lines per excerpt, 64 KiB total answer evidence, and a
  three-second cooperative retrieval deadline. Limits are checked during traversal
  and chunked reads. Partial coverage is returned explicitly. Filename resolution
  refuses to choose a basename when discovery was incomplete.
- Whole-file summaries refuse partial evidence rather than presenting partial
  counts as whole-file facts. Plain source display requires no model call.
- Source is re-read and its digest checked after interpretation generation.
  Changed source/authorization rejects the answer. Subsequent turns retrieve fresh
  evidence. Valid generated source IDs are rendered from retrieval records;
  invented IDs, unsupported paths/ranges, and uncited paragraphs are rejected.
  Explicit references are admitted only when a retrieved excerpt covers the path
  and complete range; source-ID rendering still uses the actual retrieval record.
- C1 source requests never delegate filesystem access to Hermes. Unrelated Hermes
  requests retain the existing adapter, state checks, and agent-result attribution.
- New interactive project-question responses reuse the existing producer slot,
  interruption controller, response receipt, and watchdog. Generation is buffered
  until citations are validated. Cancellation prevents a delayed provider response
  from committing evidence or a completed interpretation.

## Verification by checkpoint

Focused verification was run after each implementation boundary, followed by a
full guarded repository run after the final implementation changes.

| Checkpoint | Verification performed | Result |
| --- | --- | --- |
| 1: authorization/contracts | Registration, selection, revocation, unsafe paths, topic revision, evidence validation | Initial 14 passed |
| 2: safe retrieval | Windows handle reads, exclusions, duplicate names, ranges, missing/oversized/invalid-encoding files, traversal and cancellation | Initial 29 passed, 1 skipped including checkpoint 1; later expanded with hard links, reparse flags, budgets and blank lines |
| 3: analyzers | Existing project index, execution, dependencies, context, state inventory, graph and impact regressions | 85 passed; additional-project/cache boundary test also passed |
| 4: routing | Existing authority, summary parser and file-transition regressions | 98 passed |
| 4-5: source answers | Four representative requests, missing evidence, fabricated citations, edits, ambiguity, capability/authorization changes, conceptual conversation | Passed with deterministic fake provider |
| 5-6: cancellation/compatibility | Source cancellation, streaming/interruption, watchdog and mocked Hermes regression group | 43 passed, 1 intentionally skipped at that checkpoint |
| 6: original C1 repository suite | Original implementation before acceptance-review remediation | 994 passed, 3 skipped in 39.94 seconds |
| Remediation: final repository suite | All collected repository tests through the strict C1 harness | **1096 passed, 3 skipped, 0 failed** in 40.02 seconds |

The remediated final suite collected 1099 tests. Skips:

1. `tests/test_hermes_acp_integration.py::test_real_hermes_acp_connection`:
   Hermes executable is not installed. The integration marker alone is not an
   opt-in gate; this test's existing availability-based behavior is preserved.
2. `tests/test_project_retrieval.py::test_reparse_point_is_denied`:
   physical symlink creation unavailable to this Windows account. Deterministic
   reparse-policy rejection is separately tested without that privilege. New
   physical NTFS junction tests passed for inside-root and outside-root targets,
   including direct native-handle rejection, without launching a subprocess.
3. `tests/test_voice_reliability.py::test_local_cancellation_reaps_blocked_child_and_recovers`, which
   intentionally launches real child processes. The C1 harness explicitly skips
   it because the requested subprocess guard forbids those launches. Other fake
   child-process, cancellation, timeout, and cleanup tests passed.

Initial full-suite failures were corrected: topic snapshot assertions needed the
new identity fields; old temporary-file fixtures needed explicit authorization;
and explicit summary routing was restored to its existing deterministic entry
point. The real-child-process conflict is reported as a skip, not a passing test.

Observed warnings include SQLAlchemy datetime deprecations, the existing unknown
integration marker, plugin import rewriting, and an ONNX platform warning caused
by the test harness's subprocess-free Windows platform probe.

The strict harness:

- uses fresh workspace-local temporary fixtures and in-memory default SQLite;
- denies production SQLite opens/connections and writes to production data,
  AGENTS.md, Codex_Rules.md, and .env;
- blocks network connections/resolution, subprocesses, OS launch actions and
  physical microphone access; disables actual speech;
- retains the existing 120-second regression watchdog;
- does not overwrite existing disposable historical-recall databases.

## Disposable text acceptance

Run from `C:\Projects\JARVIS-AI`:

```powershell
.venv\Scripts\python.exe tests/run_c1_regressions.py --acceptance
```

For a guarded interactive text session:

```powershell
.venv\Scripts\python.exe tests/run_c1_regressions.py --acceptance --interactive
```

The default script uses the actual router, temporary fixture projects, an explicitly fake
AI provider, printed speech, fresh memory-only storage, and no external integration.
It does not start a microphone. Each run gets a new isolated directory beneath
`.c1-test-runs`; it does not reset existing historical-recall data. The scripted
fixture is deleted on exit. Regression fixture directories can remain for inspection.

Demonstrated offline behavior:

| Request | Actual behavior |
| --- | --- |
| What files are in this project? | Lists the three readable fixture files through `project_tree`; .env omitted |
| Summarize the file actions.py. | Two lines, one function, zero classes; reference to actions.py lines 1-2; no model call |
| What does the router do? | Retrieved router.py lines 1-6, including untrusted test comments; fake interpretation with rendered source reference |
| Explain how this project handles conversation history. | Retrieved conversation_history.py lines 1-4; source-referenced fake interpretation |
| What does missing.py do? | Explicit missing-source failure; no conversational or Hermes fallback |
| Explain .env | Explicit excluded-file failure |
| Explain ../outside.py | Explicit unsafe-path failure |

For full guarded regression verification:

```powershell
.venv\Scripts\python.exe tests/run_c1_regressions.py -q --tb=short
git diff --check
```

## Exact changed-file manifest

Implementation:

```text
commands/actions.py
commands/registry.py
commands/router.py
commands/tool_manager.py
models/source_evidence.py                     (new)
services/ai_service.py
services/capability_executor.py
services/capability_registry.py
services/code_assistant.py
services/code_intent.py
services/command_parser.py
services/conversation_manager.py
services/project_access.py                    (new)
services/project_analysis_cache.py
services/project_context.py
services/project_dependencies.py
services/project_execution.py
services/project_retrieval.py                 (new)
services/project_service.py
services/source_answer.py                    (new)
```

Verification/documentation:

```text
scripts/accept_c1.py                          (new)
scripts/c1_acceptance_guard.py                (new, remediation)
tests/run_c1_regressions.py                   (new)
tests/test_c1_acceptance_guards.py            (new, remediation)
tests/test_c1_analysis_boundary.py            (new)
tests/test_c1_source_references.py            (new, remediation)
tests/test_c1_source_routing.py               (new)
tests/test_conversation_manager.py
tests/test_live_followup_corrections.py
tests/test_project_access.py                  (new)
tests/test_project_retrieval.py               (new)
tests/test_router_file_transitions.py
tests/test_router_capability.py               (remediation)
tests/test_router_topic.py
tests/test_source_evidence.py                 (new)
tests/test_summary_filename_parser.py
docs/C1_Implementation_Report.md              (new)
```

The pre-existing modified `data/status.json` and untracked `AGENTS.md` and
`Codex_Rules.md` are outside the C1 change set and were preserved. Existing local
configuration was not edited. Nothing was staged, committed, or pushed.

## Remaining limitations and manual checks

- Safe filesystem mechanics currently support Windows; other platforms fail
  closed. Roots requiring permissions the process lacks also fail closed.
- Root registration is a trusted process-local API, not a persistent settings UI.
- Retrieval is bounded lexical selection; it can miss relevant code and does not
  establish complete execution flow. Partial excerpts must not be interpreted as
  a complete project analysis. Empty files have no readable source range.
- Exclusion rules identify filenames/types, not every secret embedded in otherwise
  allowed source. Authorized project selection is still a meaningful trust boundary.
- Citation validation proves references correspond to retrieved text, not that
  every model interpretation follows from it. Real-model adherence, usefulness,
  insufficient-evidence phrasing, and voice naturalness require manual review.
- An OS read or provider call can outlast cooperative cancellation. The existing
  voice watchdog returns control and prevents overlapping producers; it cannot
  forcibly terminate an arbitrary Python/provider call. Legacy explicit file-tool
  execution remains synchronous, as before C1.
- Source freshness is checked immediately before presentation; files may naturally
  change afterward. References describe the retrieved snapshot and timestamp.
- Physical symlink and real-child cleanup acceptance remain to be checked in a
  suitable explicitly authorized environment. Physical junction rejection is now
  verified. Live Hermes was not invoked.
- Review and explicit approval are required before committing. No additional
  architecture expansion or security-policy relaxation has been assumed.

## Acceptance-review remediation

The final read-only review identified two high-severity defects. Both were
reproduced before editing and verified after remediation without a real provider.

### Project-specific intent bypass

Root cause: the C1 classifier used a small set of request prefixes and a narrow
module-question pattern. Unrecognized project requests could reach the existing
general-explanation, conversational, or Hermes routes.

`services/code_intent.py` now separates request framing from project/component
subjects. Shared inquiry rules cover tell/show/find-out/research/walk-through
phrasing and definite code-component behavior, while indefinite/network-router,
project-management, file-format, and tax-filing questions remain conceptual.
The existing C1 routing point precedes all those fallback paths; no competing
classifier or orchestration path was introduced.

| Exact request | Before | After |
| --- | --- | --- |
| Tell me how this project handles conversation history | No C1 classification; conversational fallback | C1 bounded project search |
| Explain how the router handles commands | No C1 classification; general-explanation fallback | C1 authorized router read |
| Find out how this project handles conversation history | No C1 classification; Hermes match | C1 bounded project search |

All three were exercised through the actual router with fixture files and a fake
provider. Empty-project variants return a grounded limitation with zero provider
or Hermes calls. Generalizations cover other request wrappers/components.
Conceptual controls include inheritance, a router, Python decorators, project
management, network packets, file formats, and filing taxes.

An older negative-control test expected `tell me about my project` to bypass
capabilities. That expectation conflicts with project grounding: it now has an
explicit source-routing regression, and the conceptual control uses `tell me
about a project management technique` instead.

### Fabricated source references

Root cause: the raw path/line rejection regex was case-sensitive and omitted
supported extensions. A valid source ID elsewhere did not validate another
reference appearing in the same paragraph.

`services/source_answer.py` now audits all source-looking references, including
unknown extensions. Unicode, HTML/URL encoding, Markdown emphasis, slash variants,
colon/hash line syntax and line ranges are normalized for validation. References
must match a project-relative retrieved path and fit within one retrieved excerpt;
inventory membership alone is insufficient. Unsupported/ambiguous references fail
closed without unrestricted generation or delivery. Valid IDs and legitimate
covered references remain supported. Citation validity is separate from semantic
correctness.

Using evidence limited to `router.py` lines 1-2 and source ID `Sreal`:

| Provider output | Before | After |
| --- | --- | --- |
| See invented.yaml:999 for the implementation. [Sreal] | Accepted; invented reference remained | Rejected |
| See ROUTER.PY:999 for the implementation. [Sreal] | Accepted; invented range remained | Rejected |

New tests cover every supported extension, casing, separators, Unicode digits and
dashes, zero-width characters, encoding, Markdown wrappers/links, hidden files,
drive prefixes, reverse ranges, zero lines, unknown IDs, wrong paths, outside
ranges, and uncited paragraphs. Valid source-ID rendering and covered subranges
are retained.

### Guarded real-Ollama mode (not run automatically)

Default acceptance remains deterministic and offline. The real provider is used
only with the explicit `--acceptance --real-ollama` combination:

```powershell
.venv\Scripts\python.exe tests/run_c1_regressions.py --acceptance --real-ollama --interactive
```

Prerequisites: an already-running local Ollama service and the already-installed
model currently selected by JARVIS. The harness does not start a server, pull a
model, change model selection, edit `.env`, or switch to a substitute provider.

`OLLAMA_HOST` is read from the existing process/configuration. An unset value uses
the SDK's normal `http://127.0.0.1:11434` default. Localhost is pinned to numeric
IPv4; explicit IPv6 loopback is supported. Remote hosts, wildcard addresses,
credentials, URL paths, and ambiguous endpoint forms fail closed. A dedicated
Ollama SDK client disables environment proxies and redirects and has a 30-second
request timeout. Only that exact numeric TCP address and port pass the audit
guard; other destinations, DNS names, UDP, subprocesses, and OS launch actions
remain forbidden. `--real-ollama` without acceptance is rejected.

Before generation, a read-only model metadata request verifies local GGUF format
and architecture and rejects known cloud/remote stubs. Missing/unrecognized models
or an unavailable server stop acceptance; no automatic download or fake fallback
occurs. Tests use stubs for this wiring, never a live server.

Storage, microphone, protected-file, and production-SQLite guards are unchanged.
The acceptance registry is restricted to disposable fixture roots; even selecting
`jarvis` cannot expose production project source in this session. Hermes is
explicitly disabled. Source-policy checks, current-evidence validation, cancellation
checks, and the existing 120-second overall harness watchdog remain active.
The text session does not start voice/microphone monitoring. An interrupt exits
the session; provider requests also have the bounded client timeout.

The loopback guard constrains this acceptance process, not the independent
Ollama server's own network behavior. It assumes a trusted local Ollama service;
local-model metadata preflight rejects recognizable remote-model configurations.
This is not a claim of an OS firewall or sandbox around an existing server.

Manual checks after launching the command above:

1. Verify the banner says REAL Ollama and shows the unchanged model and pinned
   loopback endpoint. The offline banner is not real-model acceptance.
2. Inspect all four original requests and the three remediated requests. Open the
   displayed fixture excerpts with `Show the file router.py` or the corresponding
   file command; compare every claim and citation to those lines.
3. Verify missing files, `.env`, traversal, and `Select project jarvis` are refused
   without guessing, delegation, or successful-access claims.
4. The router fixture contains deliberately malicious comments asking for an
   invented reference and expanded authorization. Verify the model treats them as
   source data, and the authorized-project list still contains only `acceptance`.
5. Enter inheritance, generic router, and Python-decorator questions; verify they
   remain conceptual. Repeat a source question afterward to verify topic routing.
6. Report failures, rejected citations, timeouts, and interpretation errors. Exit
   using `:quit`; the entire session is limited to 120 seconds. Exit code zero
   alone does not establish that the printed answers meet acceptance criteria.

No real-Ollama session was launched by Codex during remediation. The user subsequently
ran and passed guarded acceptance as recorded above; broader interpretation quality
and complete prompt-injection resistance remain outside that acceptance claim.

### Remediation verification and scope

- Broad focused routing/citation/retrieval/capability/grounding/history/interruption
  regressions: 369 passed, 1 skipped at that checkpoint.
- Final citation/guard focus: 75 passed; subsequent routing/capability/citation/
  guard checks: 133 passed.
- Final physical retrieval/acceptance-guard checks: 45 passed, 1 symlink skip.
- Final full guarded suite: **1096 passed, 3 skipped, 0 failed**, 40.02 seconds.
- The initial full remediation run had one outdated conceptual-control failure;
  it was corrected as described above. There are no unresolved test failures.
- Offline fake-provider acceptance exercised the actual router successfully.
  Real-client wiring was verified only with deterministic stubs.
- `git diff --check` and changed-file scope review passed. Protected-file hashes
  are checked against the remediation baseline; no production SQLite was opened.

The original 33-file C1 manifest matched the pre-remediation Git state exactly.
The manifest above is now 37 files. Four additional paths are in scope:

```text
scripts/c1_acceptance_guard.py                (new)
tests/test_c1_acceptance_guards.py            (new)
tests/test_c1_source_references.py            (new)
tests/test_router_capability.py               (existing file, newly modified)
```

Within the original C1 scope, remediation changed `services/code_intent.py`,
`services/source_answer.py`, `scripts/accept_c1.py`, `tests/run_c1_regressions.py`,
`tests/test_c1_source_routing.py`, `tests/test_project_retrieval.py`, and this report.
Only the first two are production behavior changes; the rest prepare/verify
acceptance. No architecture, authorization policy, retrieval limit, production
configuration, or database migration was relaxed.

Final disposition: **C1 accepted for its implemented scope** following successful
user-run guarded real-Ollama acceptance. The approved 37-file manifest is authorized
for one local commit; existing skips and limitations remain. No push is authorized.
