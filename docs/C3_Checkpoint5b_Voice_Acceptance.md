# C3 checkpoint 5b: receipt-gated conversational delivery

Baseline: `b774669442a819dba4f983f1f8123e8a5f625635`.

C3 now joins the existing `multi_file_reasoning` capability, relationship-result
consumer, bounded producer queue, `ConversationSpeech` worker and
`ResponseDelivery` receipt. It introduces no new capability registration,
speaker/provider, queue, cache, dependency, database schema or analysis allowance.
Verification is offline only; no live microphone, Ollama or Hermes acceptance is
authorized by this checkpoint.

## Routing ownership

The deterministic branch in `commands/router.py` precedes the existing C2/C1
relationship/source fallbacks, after recall, control and capability management.

- Explicit file/directory/project direct-caller questions use C3, preserving
  exact qualified names, path case and project qualifiers.
- Explicit direct-only phrasing and `show/list callers of ...` use C3 even when
  missing scope, producing clarification rather than assuming a narrower search.
- `show verified direct callers of ...` opts into findings-only mode. A failed
  complete request never silently becomes findings-only.
- Legacy unscoped questions such as `What calls Speak?` retain C2 behavior.
  Supported C2 traces remain C2 requests even with an explicit project qualifier.
  Unsupported caller-chain wording asks for an explicit reverse trace rather
  than using generic AI or silently running direct analysis.
- C3-topic follow-ups cannot manufacture a new scope, reuse a proof as authority,
  or fall through to generic AI. They request explicit scope/target or trace.

Missing scope, ambiguous target and unresolved `this file` context produce
deterministic clarification without caller facts. Explicit scope replies or
displayed qualified target choices can complete clarification. Project names
never register or switch roots. Registration/revision changes invalidate the
captured clarification context. The actual user utterance is persisted, separately
from any reconstructed command used to resolve a clarification.

## Capability and publication flow

```text
router + existing response receipt
  -> existing multi_file_reasoning capability, scoped_command argument
  -> C3.5a construction + C3.3 + C3.4 (same AnalysisRequest/budget)
  -> producer-bound private ScopedPublication handle
  -> existing _RelationshipDelivery queue item
  -> existing consumer: present_relationship_result
  -> independent C3.4 delivery replay + canonical answer/citation comparison
  -> one-use receipt claim + guarded history/text publication
  -> existing speech worker: dependency/owner check before each utterance
  -> existing playback receipt finalization
```

The synchronous/text path creates its receipt before capability execution, then
uses the same consumer and playback finalization. C3 without a current receipt
cannot return a factual capability result. Producer completion alone performs no
history, UI or speech effects. No factual token is streamed before consumer
publication eligibility. C2's complete-result gate and private publication tuple
continue to use their existing implementation.

`ScopedCallerAnswerCandidate` remains internal and retains the analysis required
for fresh independent validation. Its internal publication flag stays false;
only the explicit capability consumer can admit delivery. Analysis objects,
requests, handles and receipts never enter history or model context.

## Ownership and replay protections

The existing receipt now supports guarded ownership: cancellation event, consumer
thread, active receipt, process-local conversation generation and persisted-session
object identity. A producer reserves exactly one handle and immutable identity
metadata. The consumer requires that exact reservation and the original request,
question, analysis command, scope, claim and proof fingerprints. It consumes the
publication once. Substitution, wrong consumer, replay and closed receipts are
discarded rather than delivering an old response under another request.

New routed commands or response receipts supersede an active C3 response.
Conversation resets and existing session start/end paths cancel guarded delivery.
Existing cancellation/stop callbacks discard queued speech. Old producers cannot
publish late history; finishing an old receipt cannot clear a newer owner.
Guarded history publication uses the receipt's existing ownership lock so a new
request/session boundary cannot interleave its records with those effects.

C3 persists one user row and one assistant row through existing `add_message`.
Validated factual text is `observed`; refusals/clarifications are `router`.
Playback status remains unknown until the receipt records actual completion,
failure, interruption or timeout. Completion still does not prove human receipt.
Named-project authorization failures preserve the existing no-history behavior.

## Delivery proof, evidence and speech

Immediately before publication, C3.4 independently replays full source/binding
proof, verifies the supplied evidence packet, and checks inventory/fingerprints,
authorization, scope identity, cancellation and the original deadline. Canonical
rendering must match the prepared text, relationships and source references.
Untrusted result-dictionary response/topic/pending fields are rebuilt rather
than used as factual authority.

Findings-only responses retain their static-only and additional-callers warning.
Complete answers identify exactly the declared domain/project; empty answers
need the same completeness proof. Refusal uses limitation categories and emits
no rejected caller facts. Only citation metadata is removed for speech by the
existing C2 formatter; qualifications remain intact. History/text keep citations.

Before each existing speech-worker utterance, a guarded C3 response rechecks its
receipt, capability availability, scope, full proof fingerprints and inventory,
authorization and deadline. It reuses the already independently validated proof
only while those dependencies remain unchanged; it does not collect a new
evidence packet per sentence. Failure cancels remaining speech, marks the receipt
interrupted and suppresses stale returned text. C1/C2/general speech has no C3
guard and retains its established playback behavior.

## Bounds and limitations

All admission, analysis, validation, delivery replay and playback checks share
the original budget. No default was increased or deadline renewed. Repeated
checks can exhaust remaining source/evidence limits, and the original five-second
deadline can interrupt a long spoken response. Fail-closed delivery takes
precedence over completing an answer. This conservative behavior needs future
live acceptance before any budget-policy change is considered.

Filesystem freshness is check-time and not atomic against external writes.
Changes discovered before a later utterance stop subsequent playback; already
spoken audio cannot be recalled. Cooperative cancellation uses the existing
bounded provider stop behavior and cannot guarantee instantaneous native-provider
termination. Arbitrary dynamic Python remains outside the static proof contract.

## Guarded acceptance commands

```powershell
.venv\Scripts\python.exe -B tests/run_c2_regressions.py -q tests/test_scoped_relationship_voice.py --tb=short
.venv\Scripts\python.exe -B tests/run_c2_regressions.py -q --tb=short -rs
git diff --check
```

The existing guard blocks production SQLite, network and subprocess access,
stubs microphone/model startup, and uses fresh OS temporary fixtures. Tests use
simulated utterances with the actual queue, worker, capability and receipt paths.
No `.c1-test-runs` synchronization or live voice session is performed. Known
inaccessible protected children are excluded from metadata traversal.

## Verification results (November 3, 2026)

- Focused C3.5b: 59 passed. All C3 contracts/analysis/validation/construction plus
  C3.5b: 335 passed, one Windows symlink-privilege skip.
- Targeted C1/C2, simulated voice, receipt and historical-recall compatibility:
  550 passed, one guarded legacy child-process skip.
- An initial full run found one generic streaming test-double compatibility
  failure: the double did not implement `interrupt`. Optional callback binding
  fixed it without weakening guarded C3 playback. Post-fix targeted checks:
  168 passed.
- Final full guarded run, once after that fix: 1,800 passed, four skipped,
  zero failed, 158 existing warnings, 63.64 seconds. Skips: unavailable Hermes,
  two Windows symlink-privilege tests and the forbidden legacy voice child.
- `git diff --check`, changed Python syntax and new-file whitespace checks pass.
  No staging, commit or push was performed; HEAD remains the stated baseline.
- All three protected file hashes and metadata for 1,246 accessible
  `.c1-test-runs` entries match the initial snapshot. Two known inaccessible
  children were skipped without entering them. Disposable fixtures used OS temp
  directories; no production SQLite or live voice/model session was accessed.
