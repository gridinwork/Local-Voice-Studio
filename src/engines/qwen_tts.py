"""Qwen3-TTS backend — PRIMARY TTS engine for MODE 1."""
from __future__ import annotations

import pickle
import time
from pathlib import Path
from typing import Iterator

import numpy as np

from src.engines.base_tts import BaseTTSEngine, EngineStatus, TTSResult
from src.utils.gpu import get_process_vram_peak_mb, reset_peak_stats
from src.utils.logging_setup import get_logger

log = get_logger("qwen_tts")

MODEL_IDS = {
    "0.6B": "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
    "1.7B": "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
}

LANGUAGE_MAP = {"ru": "Russian", "en": "English", "auto": "Auto"}


class QwenTTSEngine(BaseTTSEngine):
    name = "qwen3_tts"

    def __init__(self, model_size: str = "1.7B"):
        super().__init__()
        self.model_size = model_size
        self._model = None
        self._device = "cuda"

    @property
    def cache_key(self) -> str:
        return f"{self.name}_{self.model_size}"

    def load_model(self, precision: str = "bfloat16", device: str = "cuda") -> None:
        if self.status == EngineStatus.READY:
            return
        self.status = EngineStatus.LOADING
        self._device = device
        try:
            import torch
            from qwen_tts import Qwen3TTSModel
            dtype = {"bfloat16": torch.bfloat16, "float16": torch.float16, "float32": torch.float32}[precision]
            model_id = MODEL_IDS[self.model_size]
            try:
                self._model = Qwen3TTSModel.from_pretrained(
                    model_id, device_map=device, dtype=dtype, attn_implementation="sdpa",
                )
            except TypeError:
                self._model = Qwen3TTSModel.from_pretrained(model_id, device_map=device, dtype=dtype)
            self.status = EngineStatus.READY
            log.info(f"Qwen3-TTS ({self.model_size}) загружена на {device} ({precision})")
        except Exception as e:
            self.status = EngineStatus.ERROR
            self.last_error = str(e)
            log.error(f"Не удалось загрузить Qwen3-TTS: {e}")
            raise

    def unload_model(self) -> None:
        if self._model is not None:
            del self._model
            self._model = None
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
        self.status = EngineStatus.UNLOADED

    def build_voice_prompt(self, ref_audio_path: str, ref_text: str, cache_path: str) -> None:
        if self.status != EngineStatus.READY:
            self.load_model()
        prompt_items = self._model.create_voice_clone_prompt(ref_audio_path, ref_text)
        Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "wb") as f:
            pickle.dump(prompt_items, f)
        log.info(f"Voice-clone prompt сохранён в {cache_path}")

    def _load_cached_prompt(self, cache_path: str):
        with open(cache_path, "rb") as f:
            return pickle.load(f)

    def generate(self, text: str, language: str, cache_path: str, quality_preset: str = "balanced") -> TTSResult:
        if self.status != EngineStatus.READY:
            self.load_model()
        if not Path(cache_path).exists():
            raise FileNotFoundError(
                f"Кэш голосового профиля не найден ({cache_path}). Сначала создайте/пересоздайте Voice Profile."
            )
        prompt_items = self._load_cached_prompt(cache_path)
        lang = LANGUAGE_MAP.get(language, language)
        reset_peak_stats()
        t0 = time.time()
        wavs, sr = self._model.generate_voice_clone(
            text=text, language=lang, voice_clone_prompt=prompt_items,
        )
        elapsed = time.time() - t0
        peak_vram = get_process_vram_peak_mb()
        audio = np.asarray(wavs[0], dtype=np.float32)
        return TTSResult(audio=audio, sample_rate=sr, generation_time_sec=elapsed, peak_vram_mb=peak_vram)

    def generate_stream(self, text: str, language: str, cache_path: str, quality_preset: str = "balanced") -> Iterator[np.ndarray]:
        if self.status != EngineStatus.READY:
            self.load_model()
        if not hasattr(self._model, "stream_generate_voice_clone"):
            yield from super().generate_stream(text, language, cache_path, quality_preset)
            return
        prompt_items = self._load_cached_prompt(cache_path)
        lang = LANGUAGE_MAP.get(language, language)
        for chunk, _sr in self._model.stream_generate_voice_clone(
            text=text, language=lang, voice_clone_prompt=prompt_items,
        ):
            yield np.asarray(chunk, dtype=np.float32)
