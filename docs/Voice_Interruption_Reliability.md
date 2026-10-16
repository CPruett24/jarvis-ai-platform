# Voice interruption recovery

The original failure combined an accepted nonempty false transcript, a
first-transcript latch, duplicate synchronous stop calls, and local engine calls
from different threads. The exact source of the silent `You` transcription and
the exact native blocked call remain unproven without captured audio/stack data.
Headphones do not establish either acoustic feedback or electronic loopback.

## Local playback ownership

Each local utterance runs in one hidden child process. That child's main thread
creates, plays, and normally stops its pyttsx3 engine. No parent thread calls
engine methods. Text is supplied through an automatically removed temporary file
as stdin, avoiding pipe writes that could hang behind native initialization.

An operation-scoped event propagates through the speaker, fallback, and local
provider. Stop sets that event promptly, including before provider registration.
The playback owner checks it every 50 ms, then terminates the child, waits at most
500 ms, escalates to kill, and waits another 500 ms. An unreaped child retains its
handle and prevents additional local children. Each utterance also has a 120 s
watchdog. Repeated stop requests do not create cancellation workers or queues in
the local provider.

This is bounded recovery rather than guaranteed graceful SAPI cancellation.
Termination can cut off sound abruptly; Windows audio buffering can briefly
outlive the process. Per-utterance interpreter/engine startup adds latency and
needs live measurement. The native Windows backend has not been live validated
by the mocked regression suite.

The shared speaker permits only one provider playback and one stop worker at a
time. Stop waits at most 20 ms. If a non-local provider's native call remains
blocked, new playback is refused with text still shown, rather than creating
additional blocked operations. The voice router can continue processing commands.

## Handoff and cleanup

Controller states are `listening`, `cancelling`, `handoff_pending`, and
`handed_off`. The callback records text and signals streaming cancellation; it
does not stop playback or invoke routing. The router requests cancellation once.

The handoff stores the initial transcript, at most one following complete
utterance, and one priority end control. The following utterance supersedes the
initial transcript; further ordinary utterances are discarded. An explicit end
phrase overrides both and cannot be superseded by an ordinary command. No
fragments are concatenated, and only one selected command executes. Handoff
closes after monitor shutdown, and late results are discarded.

After cancellation the monitor has a 350 ms collection interval. Shutdown stops
new capture and drains an already captured/in-progress utterance for at most
4 s. This is not an indefinite command backlog: speech after the window belongs
to the next listener. The main router handles selected commands iteratively and
starts a fresh interruption-capable response, preserving the end control result
without recursive stack growth.

Monitor capture releases its input stream before transcription. A shared capture
lock prevents simultaneous foreground/background input streams. If a timed-out
capture is still releasing, foreground acquisition retries without treating that
contention as a conversation timeout. A still-alive old monitor prevents spawning
another monitor; late transcription cannot route commands after shutdown. Model
inference is serialized with bounded lock acquisition. A permanently hung native
input/decoder still needs device/process recovery; Python cannot terminate such
a thread safely, and diagnostics report the pending recovery.

Speech cleanup runs on successful turns, cancellation, and exceptions. Queued
speech is cleared, one sentinel closes the worker, and joining waits at most
250 ms. Production stop requests use the shared bounded speaker; custom injected
stop callbacks are isolated with at most one stop worker per speech instance.
Blocked native provider calls can retain one daemon playback/stop worker until
they return, but the shared speaker prevents accumulating further blocked calls.

AI generation remains cooperative. One producer slot and a 32-item chunk queue
bound outstanding generation. If cancellation cannot yet reach a blocked AI
iterator, new generation returns a recovery message rather than spawning more
producers. Streaming and post-stream playback each have a 120 s watchdog. No AI
producer join blocks cleanup, and cleanup signals cancellation even on errors.

## Recognition and diagnostics

Only interruption recognition applies an additional confidence gate: no retained
VAD speech, segment no-speech probability above 0.6, or average log probability
below -1.0 rejects the utterance. These confidence limits reuse Faster-Whisper's
defaults; unlike its combined skip condition, barge-in requires both confidence
checks to pass. There is no word blacklist or transcript-length filter. Confident
`You`, `stop`, `wait`, and `That's all` remain valid. This cannot guarantee that a
confident hallucination or electronically routed playback will be rejected.
Foreground decoding keeps its original acceptance behavior.

`JARVIS_SPEECH_DIAGNOSTICS=1` enables confidence/rejection reasons, state
transitions, stop request/completion, process/thread identities, shutdown results,
and selected microphone endpoint/index. No keys or complete environment values
are logged. Existing normal voice logs still print recognized utterances.

## Validation and safe live testing

Focused validation: 240 tests passed across voice reliability, interruption,
speech, fallback/factory/ElevenLabs mocks, microphone selection, speech validation,
AI cancellation, router authority, active conversation boundaries, live follow-up
corrections, and historical recall. `git diff --check` passed. The warnings were
pytest import rewriting and existing SQLAlchemy datetime deprecations.

Run selected tests with `tests/run_voice_regressions.py`. The runner uses an
in-memory replacement for the production database URL, disables status writes,
blocks outbound socket connections and unmocked speech, stubs initial microphone
and Whisper construction, and uses a 120 s overall watchdog. Archive tests use
their own temporary databases. Real child termination tests run sleeping Python
children, not audio engines.

For live validation:

1. Use a disposable checkout and a new test database; do not copy the production
   SQLite database. Force `JARVIS_TTS_PROVIDER=local` before startup to avoid cloud
   TTS requests. Use the existing local Ollama model.
2. Enable speech diagnostics and verify both listeners select the Samson endpoint
   and index. Record Windows input/output endpoints and Samson channel/monitor
   settings; do not assume the headphone monitor mix is USB recording input.
3. Stay silent during several answers, then test `stop`, a replacement question,
   repeated interruptions of replacement answers, and `That's all` during both
   generation and speech. Confirm standby and a fresh wake cycle work.
4. Repeat the inheritance question, including separate follow-up utterances during
   cancellation. Confirm one selected question or priority end control executes,
   and fragments do not replay later.
5. Test active-discussion timeout versus explicit end and historical recall in
   the disposable database. Verify old cancelled responses do not appear as
   completed recall answers.
6. Measure local first-audio latency and cancellation-to-silence. If false speech
   recurs, retain confidence/endpoint diagnostics and a thread dump. Capture raw
   input audio only with explicit consent; that is needed to distinguish noise,
   decoding hallucination, and Windows/hardware routing.

## Files changed for this fix

- `commands/router.py`
- `services/conversation_interrupt.py`
- `services/conversation_speech.py`
- `services/listener.py`
- `services/microphone_service.py`
- `services/speaker.py`
- `services/transcription_service.py`
- `services/voice_diagnostics.py` (new)
- `services/tts/base.py`
- `services/tts/fallback_provider.py`
- `services/tts/local_provider.py`
- `services/tts/local_worker.py` (new)
- `tests/test_conversation_interrupt.py`
- `tests/test_conversation_speech.py`
- `tests/test_speech_validation.py`
- `tests/test_voice_reliability.py` (new)
- `tests/run_voice_regressions.py` (new)
- `docs/Voice_Interruption_Reliability.md` (new)

Pre-existing Milestone B files and the original working-tree status changes were
preserved. No commit, push, external API call, or production SQLite use was part
of implementation validation.
