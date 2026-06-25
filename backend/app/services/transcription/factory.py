# SPDX-License-Identifier: Apache-2.0
from app.services.transcription.interface import Transcriber
from app.services.transcription.whisper_adapter import WhisperTranscriber


def get_transcriber() -> Transcriber:
    return WhisperTranscriber()
