"""Abstract Voice Conversion engine interface (MODE 2: speech-to-speech)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterator

import numpy as np

from src.engines.base_tts import EngineStatus


@dataclass
class VCResult:
    audio: np.ndarray
    sample_rate: int
    generation_time_sec: float
    source_duration_sec: float
    output_duration_sec: float
    peak_vram_mb: float = 0.0


class BaseVCEngine(ABC):
    name: str = "base_vc"

    def __init__(self):
        self.status: EngineStatus = EngineStatus.UNLOADED
        self.last_error: str = ""

    @abstractmethod
    def load_model(self, precision: str = "float16", device: str = "cuda") -> None:
        raise NotImplementedError

    @abstractmethod
    def unload_model(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def convert(
        self,
        source_audio_path: str,
        target_ref_audio_path: str,
        preserve_timing: bool = True,
        preserve_prosody: bool = True,
        diffusion_steps: int = 25,
    ) -> VCResult:
        raise NotImplementedError

    def convert_stream(
        self,
        source_audio_path: str,
        target_ref_audio_path: str,
        **kwargs,
    ) -> Iterator[np.ndarray]:
        result = self.convert(source_audio_path, target_ref_audio_path, **kwargs)
        yield result.audio

    def get_status(self) -> dict:
        return {"name": self.name, "status": self.status.value, "error": self.last_error}
