"""XTTS-v2 backend — FALLBACK TTS engine."""
from __future__ import annotations

import pickle
import time
from pathlib import Path

import numpy as np

from src.engines.base_tts import BaseTTSEngine, EngineStatus, TTSResult
from src.utils.gpu import get_process_vram_peak_mb, reset_peak_stats
from src.utils.logging_setup import get_logger

log = get_logger("xtts_engine")

MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"
LANGUAGE_MAP = {"ru": "ru", "en": "en", "auto": "en"}


class XTTSEngine(BaseTTSEngine):
    name = "xtts_v2"

    def __init__(self):
        super().__init__()
        self._tts = None

    def load_model(self, precision: str = "float16", device: str = "cuda") -> None:
        if self.status == EngineStatus.READY:
            return
        self.status = EngineStatus.LOADING
        try:
            from TTS.api import TTS
            self._tts = TTS(MODEL_NAME).to(device)
            self.status = EngineStatus.READY
            log.info(f"XTTS-v2 загружена на {device}")
        except Exception as e:
            self.status = EngineStatus.ERROR
            self.last_error = str(e)
            log.error(f"Не удалось загрузить XTTS-v2: {e}")
            raise

    def unload_model(self) -> None:
        if self._tts is not None:
            del self._tts
            self._tts = None
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
        model = self._tts.synthesizer.tts_model
        gpt_cond_latent, speaker_embedding = model.get_conditioning_latents(audio_path=[ref_audio_path])
        Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "wb") as f:
            pickle.dump({"gpt_cond_latent": gpt_cond_latent, "speaker_embedding": speaker_embedding}, f)

    def generate(self, text: str, language: str, cache_path: str, quality_preset: str = "balanced") -> TTSResult:
        if self.status != EngineStatus.READY:
            self.load_model()
        if not Path(cache_path).exists():
            raise FileNotFoundError(
                f"Кэш голосового профиля не найден ({cache_path}). Сначала создайте/пересоздайте Voice Profile."
            )
        with open(cache_path, "rb") as f:
            cached = pickle.load(f)

        lang = LANGUAGE_MAP.get(language, language)
        model = self._tts.synthesizer.tts_model
        reset_peak_stats()
        t0 = time.time()
        out = model.inference(
            text=text,
            language=lang,
            gpt_cond_latent=cached["gpt_cond_latent"],
            speaker_embedding=cached["speaker_embedding"],
        )
        elapsed = time.time() - t0
        peak_vram = get_process_vram_peak_mb()
        audio = np.asarray(out["wav"], dtype=np.float32)
        sr = self._tts.synthesizer.output_sample_rate
        return TTSResult(audio=audio, sample_rate=sr, generation_time_sec=elapsed, peak_vram_mb=peak_vram)
