# C3 checkpoint 5a: internal conversational caller answers

Baseline: `74cfcd10e405e50374609c2ef057236054e53173`.

This checkpoint introduces an internal deterministic conversational dispatcher,
scope admission and answer construction. It does **not** register a handler in
`commands/router.py`, a capability, a speech/UI consumer, or a history writer.
Existing C2 routing and its publication/response-receipt gates remain unchanged.

## Entry points

`parse_scoped_caller_request(command)` is syntax-only. It reuses the existing C2
target and project-qualifier grammar while preserving exact identifier/path case.
Recognized forms include:

- `What functions call speak in my Jarvis project?`
- `Which functions directly call speak?`
- `Show callers of services/speaker.py::speak`
- `Within commands, what calls speak?`
- `In this file, which functions call speak?`

The second and third examples require search-scope clarification. A target's
filename does not implicitly authorize narrowing caller search to that file.
Transitive/indirect caller and trace requests return explicit C2 deferral metadata;
they never execute direct analysis. Other C2/conversation requests remain outside
this path. No fallback handler or model is called by this dispatcher.

`prepare_scoped_caller_answer(command, request, current_file=None, claim=...)`
requires an existing captured `AnalysisRequest`. It never resets the request's
budget/deadline or selects/registers a project. Its data flow is:

```text
deterministic intent
  -> current authorization + explicit search domain
  -> bounded discovery and target/direct-support admission
  -> immutable AnalysisScope
  -> C3.3 scoped caller extraction
  -> C3.4 independent evidence/freshness/eligibility validation
  -> deterministic cited INTERNAL answer candidate
```

## Scope and target rules

Explicit `in file ...`, `within ...`, and `in directory/folder ...` domains are
resolved under the captured active authorized root and source policy. A bare
`in Jarvis` is ambiguous; it does not guess a directory or project. Project-wide
wording preserves all discovered permitted Python files, never a sample or a
single target file. A named project must uniquely match the already active
registration, case-insensitively; wording never grants or switches authorization.

`In this file` requires a caller-supplied `SourceLocation` from that same project
and revision. Its content fingerprint must still match. The dispatcher does not
consult or guess conversation topics or modify pending-clarification state.

Targets resolve by exact qualified name in admitted search/direct-support files.
Explicit target filenames disambiguate by exact project-relative path, or a
unique basename. Missing or duplicate identities produce clarification, with
bounded candidate options. No C3.3 caller analysis runs until scope and target
are resolved; bounded source/symbol inspection may be needed to resolve a target.
Unqualified names are not searched through unrelated project source outside the
declared domain and its direct imports. Supply `file.py::Qualified.name` when
additional target support must be named explicitly.

Support planning admits direct inventory-backed module/package alternatives,
bounded to the existing six-file, one-hop support contract. Support files never
become caller-search files. Binding validity remains C3.4's responsibility;
re-exports, unread alternatives and unsupported deeper closure cannot be repaired
by silently expanding scope.

## Result states and evidence

`ScopedCallerAnswerCandidate` is not a `CapabilityExecutionResult` and has no
`response` field or delivery handle. `publication_enabled` is always false.

- `clarification`: missing/ambiguous project, target or scope; no relationship facts.
- `refused`: explicit authorization, coverage, resolution, freshness, evidence or
  resource limitation; no relationship facts or citations escape.
- `findings_only`: opt-in `CompletenessClaim.FINDINGS_ONLY`; explicitly states
  that findings are verified direct static relationships and additional callers
  may exist. Complete claims never silently downgrade into this mode.
- `complete`: exact domain/project and static-only qualifications; requires C3.4
  completeness certification. Project-wide scopes use `PROJECT_COMPLETE`.
  Empty results are factual only after the same independent completeness checks.
- `not_applicable`: leave unsupported/other requests to their existing owner;
  the internal dispatcher does not itself invoke C2 or generic AI.

Every relationship sentence is derived from the independently validated records
and includes qualified caller/target identities and validated evidence references.
C2 label normalization and the existing C1 citation checker are reused. Structured
references preserve evidence IDs and displayed path/line ranges, and the answer
contract rejects substituted references. There is no model-written relationship
text. Full proof dependencies remain separate from display excerpts in C3.4.

## Bounds, cancellation and freshness

Planning, extraction, validation and rendering share one original request budget.
Existing C1/C2/C3 file, byte, AST, relationship, evidence and five-second deadline
limits are unchanged. Answer text is bounded by the existing 24 KiB payload limit;
input text and clarification lists are bounded to 4,096 characters and 32 options.
There is no new caching or silent selection truncation. Resource failure refuses.

Declaration fingerprints and Python inventory/exclusions must still match the
analyzer's result before C3.4 independently replays proof. Post-validation
cancellation/deadline/authorization checks prevent late internal factual results.
Cancellation propagates as `OperationCancelled` to its owner. Existing live C2
queue delivery, stale-response suppression and playback receipts are untouched.

Freshness remains check-time, not atomic against concurrent filesystem writes.
Any future delivery integration must perform its own final revalidation. Full
source parsing is repeated deliberately, so planning consumes part of the
existing limits and larger projects can refuse sooner. This initial version
supports explicit single-file/directory/project domains, not free-form multi-file
or exclusion syntax, semantic target guesses, transitive chains or live delivery.

## Offline verification

```powershell
.venv\Scripts\python.exe -B tests/run_c2_regressions.py -q tests/test_scoped_relationship_answer.py --tb=short
.venv\Scripts\python.exe -B tests/run_c2_regressions.py -q --tb=short -rs
git diff --check
```

Use the existing offline runner: fresh OS temporary fixtures and isolated SQLite,
production SQLite/network/subprocess guards, and stubbed voice/model startup.
Simulated listener input tests preserve qualified identifiers without publishing
C3 candidates. No live microphone, Ollama, Hermes or manual live command is
authorized or needed for this checkpoint. No `.c1-test-runs` synchronization is
performed; existing protected artifacts remain untouched.

Verified on November 3, 2026:

- C3.5a: 80 tests passed as part of the final focused C3 run.
- C3.2-C3.5a combined: 276 passed, one Windows symlink-privilege skip.
- Targeted C2/C1, simulated voice lifecycle and historical recall: 546 passed,
  one legacy child-process skip imposed by the guard.
- Full guarded suite, run once after code fixes: 1,741 passed, four skipped,
  zero failed, 158 existing warnings, 61.23 seconds. Skips: missing Hermes,
  two Windows symlink-privilege cases, and the forbidden legacy voice child.
- `git diff --check`, explicit new-file whitespace checks and Python syntax
  checks passed. The Git index remained empty and the baseline HEAD unchanged.
- Protected file SHA-256 values and metadata for 1,246 accessible
  `.c1-test-runs` entries matched the starting snapshot. Two known inaccessible
  children were excluded from traversal; their contents were not inspected.
