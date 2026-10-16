# Historical recall and playback outcomes

The fixed post-generation playback deadline cancelled healthy long responses.
Recall also received arbitrary neighboring topics and unchecked model prose,
without evidence of how much of a saved generated response was played.

## Playback

Providers now return `PlaybackOutcome`. Local TTS reports completion only after
the isolated worker exits successfully; cancellation, timeout, failures and
recovery skips are separate results. Legacy providers returning `None` remain
unknown. ElevenLabs reports completion only after nonempty audio writes and
normal stream exhaustion. Neither result proves human receipt.

`ConversationSpeech` records a monotonic timestamp only for successfully
completed utterances. Enqueueing, subprocess startup, failed/skipped work and
queue bookkeeping never reset it. The router's playback wait cancels after
120 seconds without successful progress (or without initial playback starting).
A healthy response can exceed 120 seconds overall. The separate generation
watchdog and local per-utterance initialization/playback bound remain 120 seconds.
Stop/reap/join bounds and iterative interruption handoff are unchanged.

Diagnostics include response-scoped utterance identifiers, pending work,
explicit outcomes, successful progress, watchdog reasons, final response status
and selected recall evidence IDs/statuses. No transcript text is added to these
diagnostics.

## Persistence

`conversations.playback_status VARCHAR NOT NULL DEFAULT 'unknown'` is additive.
Both startup initialization paths invoke an idempotent column migration.
Existing records remain unknown; the stored message and source are preserved.
A saved assistant row establishes generated/recorded text, not spoken content.
Statuses are `unknown`, `completed`, `interrupted`, `timed_out`, and `failed`.
An operation-scoped receipt follows the producer's copied context and updates
only its own saved assistant IDs, including a late save after cancellation.
The synchronous Ollama/recall routes use the same receipt. Persistence failures
are reported and cannot be converted into successful delivery claims.

## Historical evidence

Topic searches admit bounded direct lexical hits first. Only immediate
opposite-role physical neighbors can supply question/answer context. Another
user question, an excluded recap, the watermark or date boundary prevents a
pair. These are recorded adjacency relationships, not semantic proof that an
answer addressed every part of the question. Unanswered direct questions are
labeled. Direct hits get character-budget priority; presentation remains
chronological. Properly labeled historical recaps remain excluded throughout.

Recall requests and their responses are excluded from substantive discussion
selection without deleting audit/history rows. The live recall classifier also
recognizes legacy requests; immediate responses to those requests are excluded
even if their source label is missing. Explicit end controls and their immediate
responses do not become topics. Previous-session selection searches at most 400
candidates for the latest session with a recorded non-system answer, skipping
recall-only and unanswered-only sessions when an answered discussion exists.
Otherwise questions can still support a topic-only reply. Sessions are never merged.
If that bound prevents finding a discussion, recall reports incomplete history.

Summary and continuation instructions are distinct. The model selects at most
three exact sentences of at most 320 characters in JSON. Validation checks IDs, whole
source sentences, topic boundaries and direct relevance. A positive fragment
extracted from a negated sentence cannot validate. Fenced code is excluded.
Only narrowly defined grammatical transformations of descriptive sentences are
allowed: for example, "Inheritance is a way to reuse behavior" can become
"The saved explanation described inheritance as a way to reuse behavior."
Unchecked semantic paraphrases never reach speech. Repeated definition labels
and parenthesized acronyms are treated as formatting. Invalid or unhelpful model
selection falls back to source sentences passing the same deterministic checks,
so safe source details can still be summarized without another model call.

Rendering summarizes at most two recorded turns in sequence. General summaries
prefer supported explanations, completed playback and distinct topics over
trailing unanswered fragments. Topic summaries
prefer the latest explanation and latest subsequent question; continuation uses
the last supported explanatory topic, regardless of an older model-selected excerpt. A
repeated unanswered question never inherits an earlier answer. Missing evidence
in the character budget is distinguished from an unanswered question.

Spoken output contains no citation syntax, IDs, timestamps, provenance labels or
raw playback statuses. `GroundedRecap.anchors` retains source identifiers, dates,
delivery status and question/answer links internally; optional diagnostics expose
selected IDs and statuses. Saved-text attribution avoids claiming unknown playback
completed. Explicit questions about what JARVIS told the user get one delivery
qualification when needed; ordinary summaries omit playback boilerplate.
Invalid/unsafe output gets verified source details or a single topic-only fallback,
never raw records. Summaries contain no continuation suggestion. Continuation is
just the topic and a resume question, without recap limitations or delivery disclaimers.
Neither route restores archive state or old file context.

The renderer deliberately uses controlled templates rather than unrestricted
abstractive prose. Complex sentences, topics it cannot safely identify, code-heavy
answers, and unsupported grammatical forms get a short fallback. Lexical matching
can miss synonyms, and a supported sentence containing the requested term may
also mention another topic. A provider result does not identify exact words heard.
Abrupt process termination leaves delivery unknown. Legacy derived recaps without
a recognizable preceding recall request or source label cannot reliably be
identified. No production database was used to validate this patch.

## Safe disposable live test

Do not launch the main repository to test the migration. Synchronize changed
source into the existing disposable copy while preserving its isolated `.env`,
database module configuration, launcher, bootstrap and write/database guards.
In particular, merge the new migration function into its guarded
`models/database.py`; do not replace that file wholesale. Back up any wanted
disposable records, verify the configured database resolves inside the copy,
then apply the additive migration only there. No reset is required.

Keep local TTS, the Samson microphone and diagnostics enabled. Ensure the
bootstrap still routes `services.tts.local_worker` through the guarded child
entry point. Launch manually:

```powershell
Set-Location -LiteralPath 'C:\Users\pruet\AppData\Local\Temp\JARVIS-MilestoneB-b800bc16c1'
& .\Launch-LiveTest.ps1
```

Test a long response, repeated interruptions, an explicit end phrase, then topic
recall in a later session. Inspect only the disposable records: full generated
text should remain while playback status reflects the outcome. Confirm recall
does not claim that unknown or interrupted text was fully spoken. This patch
does not synchronize or launch that environment automatically.

For the latest correction, synchronize only `commands/router.py`,
`services/code_intent.py`, `services/command_parser.py`,
`services/conversation_db.py`, `services/historical_recall.py`,
`tests/test_historical_recall.py`, and this document. Preserve all disposable
guards, configuration and recorded conversations; this refinement adds no schema
change. Test inheritance recall, a summary, and continuation after a recall-only
session. Confirm concise topic wording, natural playback uncertainty, no spoken
metadata, and correct handling of repeated unanswered questions. The validated
playback watchdog, delivery metadata and interruption code are unchanged.

## Latest live-test findings

Read-only inspection of the disposable records confirmed that session 3's
completed OOP answer (28) was crowded out by the last-two-turn renderer:
question 31 ("inherent") and question/answer 32–33 ("inheritance"). Numbered
definition headings, parenthesized acronyms and longer sentences also defeated
the narrow renderer. These remain distinct topics; no phonetic correction is
applied. Session 4's "did we discuss about inheritance" (34) bypassed recall
because that phrasing was missing from the deterministic classifier. Its ordinary
Ollama answer (35) was therefore not validated against historical evidence.

The classifier now covers "Did we discuss X?", "Have we talked about X before?",
"Do you remember our discussion about X?" and related shared-history forms.
Conceptual questions and tool requests retain their existing routes. The expanded
classifier also excludes newly recognizable legacy recall exchanges from later
evidence, without deleting records.

The cancellation test assumed the worker could not start between enqueue and
interrupt. It now gates worker admission with events and asserts all definitely
queued work is discarded. A second event-driven case starts one utterance and
checks active cancellation plus discard of all waiting sentences. Both cases
repeat ten times without sleeps or production cancellation changes. Run disposable
regressions without the old `--exclude-timing-test` option after copying the test.

## Final retrieval and partial-transcription correction

Read-only replay of the next disposable test confirmed that session 5 contained
only the truncated "we discuss inheritance" (40) and an ordinary ungrounded
assistant reply (41). The reply had no supported descriptive sentence, but
previous-session selection counted any nonempty answer as substantive. Topic
recall also preferred the newest paired answer without checking its usability.
This displaced the completed OOP explanation (28) and usable inheritance
explanation (33) in session 3. The former was present in the archive; the latter
has interrupted playback, which remains preserved and never becomes a receipt claim.

Session selection now first prefers sessions with an answer passing the existing
deterministic definition checks, then retains the conservative older fallbacks.
Topic rendering likewise prefers supported answers over newer unusable replies.
The evidence budget prioritizes direct supported explanations before unhelpful
direct rows, while final presentation remains chronological. No session is merged
or restored, and no phonetic equivalence is introduced.

The generic summarize parser previously accepted every suffix as a filename.
A shared conversation-summary phrase guard now prevents complete or truncated
conversation requests from becoming file targets. The router clarifies incomplete
phrases such as "Summarize our last"; explicit file targets such as "our last.py"
retain file-summary routing. Polite complete conversation-summary requests still
enter historical recall. Truncated summary requests also remain excluded from
substantive archive topics. The watchdog, delivery schema and interruption
implementation are unchanged.

## Final targeted routing and finalization pass

The conversation-summary guard also recognizes explicit cutoff markers on
prefixes of `last`, `previous`, `conversation`, and `discussion`, such as
"Summarize our la-". Only full conversational phrases qualify; filenames and
paths such as `our la-.py` retain their file-summary route.

Playback status used to be persisted before bounded speech cleanup and monitor
draining. An accepted end control in that window could therefore reach handoff
after a stale final status was already saved. Finalization now follows bounded
cleanup and an atomic handoff seal, and uses the accepted user control rather
than the synthetic producer-stop event. Late worker acknowledgement need not
delay finalization: accepted user cancellation is recorded as interrupted.
Watchdog timeouts and genuine response exceptions retain their distinct outcomes;
per-utterance failure diagnostics remain available. No cancellation or watchdog
bounds were extended. The failed legacy record is not retrospectively rewritten.

For this targeted pass, synchronize only `services/code_intent.py`,
`commands/router.py`, `tests/test_historical_recall.py`,
`tests/test_recall_playback_grounding.py`, and this document. Preserve the existing
database and all guards/configuration; no reset or migration is required. Minimal
live checks are a cut-off conversation summary, an explicit file summary, and an
inheritance explanation ended intentionally with "That's all". The last case
should return to standby with final playback status interrupted, even if the
active utterance acknowledges cancellation later.
