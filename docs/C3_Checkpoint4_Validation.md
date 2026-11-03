# C3 checkpoint 4: internal caller eligibility

This checkpoint adds independent evidence, freshness and eligibility checks for
reverse direct static Python callers. It does not register a capability, route a
request, render an answer, speak, write conversation history, or deliver results.
Existing C2 publication, traversal and caching contracts are unchanged.

## Entry points and ownership

`services.scoped_relationship_validation.validate_scoped_callers(candidate,
expected_scope, request, claim=..., evidence=None)` returns an immutable
`ScopedValidationOutcome`. The trusted caller supplies its original scope
declaration separately; the validator never derives authorization from the
candidate's scope. Supported claim modes are `FINDINGS_ONLY`, `SCOPED_COMPLETE`
and `PROJECT_COMPLETE`. Project completeness requires an unnarrowed project
Python scope.

The outcome records scope identity, claim mode, evidence/freshness/authorization/
completeness status, refusal reasons, and internal publication eligibility.
`publication_enabled` is always false. Candidate publication flags also remain
disabled. An outcome is check-time metadata, not a delivery capability or a
cacheable promise of future freshness.

`collect_scoped_caller_evidence` optionally constructs a bounded evidence packet
after proof replay. Collection is not an eligibility grant. A supplied packet is
reconstructed and compared during validation; this repeats work on the original
request budget. Call validation directly to avoid unnecessary duplicate work.

## Independent proof

The validator does not call `analyze_scoped_callers` or trust a verified label.
It safely rereads full declared search/support sources, checks their SHA-256
fingerprints, parses them, and uses the existing C2 lexical symbol, import and
call primitives to reconstruct candidate relationships. Exact records must
match, including caller definition, qualified target, call expression, source
lines/columns, import locations, and binding support. Missing findings and
omitted unresolved boundaries are rejected, including in findings-only mode.

The shared primitives enforce alias, lexical shadowing, reassignment,
conditional-definition, wildcard, receiver, decorator and mutation safeguards.
All declared source files remain proof dependencies, even if not displayed.
Undeclared module/package alternatives prevent proof. Policy-denied or linked
module alternatives are unknown rather than absent and cannot disambiguate an
import by exclusion. Source is parsed as data and never imported or executed.

C3.3 now retains the permitted Python inventory and exclusion diagnostics from
discovery. These are comparison inputs, not proof certificates. C3.4 independently
enumerates and checks them. Older candidates lacking these dependencies fail
closed rather than receiving implicit freshness.

## Findings and completeness

Findings-only mode needs at least one independently proven relationship and
explicitly qualifies the claim: additional callers may exist. Unresolved calls
or excluded search boundaries may prevent a complete list while leaving a
verified finding eligible.

A complete scoped list additionally requires exact search membership, parsed
coverage, closed support, no relevant excluded/uncertain boundaries, no analysis
or selection truncation, and all reconstructed required findings. An empty
verified list proves nothing by itself; an empty complete result needs the same
enumeration, target, proof and freshness checks as a nonempty result.

Initial validation conservatively refuses all claims if a declared proof input
cannot be read/parsed or support closure is incomplete. It does not attempt to
prove that an unread source is irrelevant to binding or mutation safety.

## Display evidence and limits

Display windows reuse C2 definition-header selection, source-range identities
and `EvidenceSupport` mappings. They do not establish the relationship proof.
Collected packets carry proof fingerprints and discovery membership separately.
Supplied citations, source text, ranges, identities, support mappings and claim
mode must match independently reconstructed evidence. Retrieval time alone is
descriptive and excluded from packet equality.

All stages share the caller's original `AnalysisBudget`; no budget or deadline
is reset. Existing C2 defaults remain unchanged. Limits include:

- 256 Python files, 8 MiB cumulative source reads, 512 KiB per file;
- 200,000 AST nodes total and 50,000 per file;
- 10,000 relationships and the original five-second cooperative deadline;
- at most 32 selected relationships, six displayed files, eight excerpts;
- at most 120 lines per excerpt, less than 12 KiB displayed UTF-8 source,
  and at most 24 KiB serialized evidence payload;
- at most 256 display-support mappings and bounded untrusted collections;
- 10,000 discovery entries per pass under the existing retrieval ceiling.

Smaller request limits apply. Exhaustion, truncation, missing support and malformed
metadata produce refusal, never a silently shortened eligible result.

## Freshness and safety

After proof/evidence checks, a final pass reserves at least 50 ms on the original
deadline, checks discovery membership, rereads every proof fingerprint, checks
discovery again, and verifies authorization/cancellation/deadline before granting
eligibility. Failure to finish that pass refuses eligibility. The reservation
does not extend time or guarantee completion.

Project registration/revision, active-project identity, canonical root identity,
safe containment, reparse/hard-link guards and source policy use existing C1/C2
authorization/read machinery. Same-size edits are detected by content hashes.
New callers and module alternatives invalidate inventory comparisons.

As with C2 freshness, this is not an atomic filesystem transaction: files can
change after their final read or after return. Future delivery must revalidate;
there is deliberately no delivery path in this checkpoint. Static confirmation
does not prove runtime execution or arbitrary Python dynamic behavior. Both
analyzer and validator rely on the existing conservative C2 resolution semantics.

## Guarded verification

Run from the repository root using the existing offline runner:

```powershell
.venv\Scripts\python.exe -B tests/run_c2_regressions.py -q tests/test_project_scope.py tests/test_scoped_relationship_analysis.py tests/test_scoped_relationship_validation.py --tb=short
.venv\Scripts\python.exe -B tests/run_c2_regressions.py -q --tb=short -rs
git diff --check
```

The runner uses fresh OS temporary fixtures/storage, blocks production SQLite,
network and subprocess access, and stubs hardware/model startup. It does not
write `.c1-test-runs`. Actual Windows symlink creation tests may skip when the
token lacks privilege; deterministic denied-alternative and containment tests
also exercise refusal without needing that privilege. No live voice/model test
is required or authorized for this internal checkpoint.

Verified on November 3, 2026:

- C3.2/C3.3/C3.4: 196 passed, one Windows symlink privilege skip.
- Targeted C2/C1, authorization/budget, voice lifecycle and historical recall:
  501 passed, one guarded child-process skip.
- Full guarded suite, run once after code fixes: 1,661 passed, four skipped,
  zero failed, 158 warnings, 57.98 seconds. Skips: missing Hermes executable,
  two Windows symlink privilege cases, and the forbidden legacy voice child.
- `git diff --check` and explicit new-file whitespace checks passed.

The protected `AGENTS.md`, `Codex_Rules.md` and `data/status.json` SHA-256 hashes
matched the initial inspection. No checkpoint artifacts were written into
`.c1-test-runs`; all 1,246 accessible entries had modification times preceding
this work. Two existing permission-denied subdirectories could not be inspected,
so a complete content-integrity claim for that tree is not made.
