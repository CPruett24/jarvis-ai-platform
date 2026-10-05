import os
import tempfile
import wave
from pathlib import Path
from services.configuration import load_environment


PROJECT_ROOT = Path(__file__).resolve().parents[1]

CUDA_DLL_DIRECTORIES = [
    PROJECT_ROOT
    / ".venv"
    / "Lib"
    / "site-packages"
    / "nvidia"
    / "cublas"
    / "bin",

    PROJECT_ROOT
    / ".venv"
    / "Lib"
    / "site-packages"
    / "nvidia"
    / "cudnn"
    / "bin",
]


for directory in CUDA_DLL_DIRECTORIES:

    if directory.exists():

        os.add_dll_directory(
            str(directory)
        )

        os.environ["PATH"] = (
            str(directory)
            + os.pathsep
            + os.environ["PATH"]
        )


from faster_whisper import WhisperModel
from faster_whisper.audio import decode_audio
from faster_whisper.vad import get_speech_timestamps

load_environment()
SPEECH_DIAGNOSTICS = os.getenv("JARVIS_SPEECH_DIAGNOSTICS", "0").lower() in {
    "1", "true", "yes", "on",
}


model = WhisperModel(
    "small",
    device="cuda",
    compute_type="float16",
)

def warm_up_transcription():
    """
    Warm up Faster-Whisper and the CUDA inference path so the
    first real user utterance does not pay the cold-start cost.
    """

    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".wav",
    ) as temp_audio:

        temp_path = temp_audio.name

    try:

        with wave.open(
            temp_path,
            "wb",
        ) as wav_file:

            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)

            # 0.5 seconds of 16-bit mono silence.
            wav_file.writeframes(
                b"\x00\x00" * 8000
            )

        segments, _ = model.transcribe(
            temp_path,
            language="en",
            beam_size=1,
        )

        # Faster-Whisper inference is lazy.
        list(segments)

        # Exercise Silero initialization/inference without filtering away the
        # silence needed by the existing Whisper/CUDA warm-up above.
        get_speech_timestamps(decode_audio(temp_path, sampling_rate=16000))

    finally:

        if os.path.exists(
            temp_path
        ):
            os.remove(temp_path)

def transcribe_audio(audio):

    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".wav",
    ) as temp_audio:

        temp_audio.write(
            audio.get_wav_data()
        )

        temp_path = temp_audio.name

    try:

        segments, info = model.transcribe(
            temp_path,
            vad_filter=True,
        )

        # In Faster-Whisper 1.2.1 an empty VAD chunk list becomes a zero-length
        # audio array and duration_after_vad=0. Do not decode its lazy iterator.
        no_speech = info.duration_after_vad == 0
        returned_segments = [] if no_speech else list(segments)
        if SPEECH_DIAGNOSTICS:
            print(
                "[Speech diagnostics] "
                f"audio={info.duration:.2f}s vad={info.duration_after_vad:.2f}s "
                f"segments={len(returned_segments)} no_retained_speech={no_speech}"
            )
            for index, segment in enumerate(returned_segments):
                print(
                    f"[Speech diagnostics] segment={index} "
                    f"no_speech_prob={segment.no_speech_prob:.3f} "
                    f"avg_logprob={segment.avg_logprob:.3f} "
                    f"temperature={segment.temperature:g}"
                )

        text = " ".join(
            segment.text
            for segment in returned_segments
        )

        return text.strip()

    finally:

        if os.path.exists(
            temp_path
        ):
            os.remove(temp_path)
