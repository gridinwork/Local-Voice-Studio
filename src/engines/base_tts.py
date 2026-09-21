"""Abstract TTS engine interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Iterator

import numpy as np


class EngineStatus(str, Enum):
    UNLOADED = "unloaded"
    LOADING = "loading"
    READY = "ready"
    ERROR = "error"


@dataclass
class TTSResult:
    audio: np.ndarray
    sample_rate: int
    generation_time_sec: float
    peak_vram_mb: float = 0.0


class BaseTTSEngine(ABC):
    name: str = "base"

    def __init__(self):
        self.status: EngineStatus = EngineStatus.UNLOADED
        self.last_error: str = ""

    @abstractmethod
    def load_model(self, precision: str = "bfloat16", device: str = "cuda") -> None:
        raise NotImplementedError

    @abstractmethod
    def unload_model(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def build_voice_prompt(self, ref_audio_path: str, ref_text: str, cache_path: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def generate(
        self,
        text: str,
        language: str,
        cache_path: str,
        quality_preset: str = "balanced",
    ) -> TTSResult:
        raise NotImplementedError

    def generate_stream(
        self,
        text: str,
        language: str,
        cache_path: str,
        quality_preset: str = "balanced",
    ) -> Iterator[np.ndarray]:
        result = self.generate(text, language, cache_path, quality_preset)
        yield result.audio

    def get_status(self) -> dict:
        return {"name": self.name, "status": self.status.value, "error": self.last_error}

    @property
    def cache_key(self) -> str:
        return self.name
