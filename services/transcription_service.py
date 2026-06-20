from faster_whisper import WhisperModel
import tempfile
import os

model = WhisperModel(
    "base",
    device="cpu",
    compute_type="int8"
)


def transcribe_audio(audio):

    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".wav"
    ) as temp_audio:

        temp_audio.write(audio.get_wav_data())

        temp_path = temp_audio.name

    segments, info = model.transcribe(
        temp_path
    )

    text = " ".join(
        segment.text
        for segment in segments
    )

    os.remove(temp_path)

    return text.strip()