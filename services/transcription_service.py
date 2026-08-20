import os
import tempfile
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