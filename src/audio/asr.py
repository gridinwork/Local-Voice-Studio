"""Lightweight local ASR (faster-whisper) for MODE 2 source-audio transcription
and for auto-filling ref_text when creating a Voice Profile.

Runs on CPU by default (see config.json: asr_device) so the RTX 3060 stays
free for the TTS/VC model — small model is real-time-or-better on any modern CPU.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from src.utils.config import get_config
from src.utils.logging_setup import get_logger

log = get_logger("asr")

_model = None
_model_key = None


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass
class TranscriptResult:
    text: str
    language: str
    segments: list[TranscriptSegment] = field(default_factory=list)


def _get_model():
    global _model, _model_key
    cfg = get_config()
    model_size = cfg.get("asr_model", "small")
    device = cfg.get("asr_device", "cpu")
    key = f"{model_size}:{device}"
    if _model is None or _model_key != key:
        from faster_whisper import WhisperModel
        compute_type = "int8" if device == "cpu" else "float16"
        log.info(f"Загрузка ASR модели faster-whisper '{model_size}' на {device} ({compute_type})")
        _model = WhisperModel(model_size, device=device, compute_type=compute_type)
        _model_key = key
    return _model


def transcribe(audio_path: str | Path, language: str | None = None) -> TranscriptResult:
    """language: 'ru', 'en' or None for auto-detect."""
    model = _get_model()
    segments_iter, info = model.transcribe(str(audio_path), language=language, vad_filter=True)
    segments = [TranscriptSegment(start=s.start, end=s.end, text=s.text.strip()) for s in segments_iter]
    text = " ".join(s.text for s in segments).strip()
    return TranscriptResult(text=text, language=info.language, segments=segments)


def unload() -> None:
    global _model, _model_key
    _model = None
    _model_key = None
