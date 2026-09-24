import os
import tempfile
import wave
from pathlib import Path


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
            temp_path
        )

        text = " ".join(
            segment.text
            for segment in segments
        )

        return text.strip()

    finally:

        if os.path.exists(
            temp_path
        ):
            os.remove(temp_path)