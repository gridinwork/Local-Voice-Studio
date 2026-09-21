"""Builds concrete engine instances from config, keeping GUI/CLI/API decoupled
from which backend is actually active (Qwen3-TTS primary, XTTS-v2 fallback)."""
from __future__ import annotations

from src.engines.base_tts import BaseTTSEngine
from src.engines.model_manager import get_model_manager
from src.utils.config import get_config


def create_tts_engine(model_size: str | None = None) -> BaseTTSEngine:
    cfg = get_config()
    backend = cfg.get("tts_backend", "qwen3_tts")
    preset = cfg.get("active_preset", "balanced")
    size = model_size or cfg.get("quality_presets", {}).get(preset, {}).get("tts_model", "1.7B")

    manager = get_model_manager()
    key = f"{backend}:{size}"

    def factory():
        if backend == "qwen3_tts":
            from src.engines.qwen_tts import QwenTTSEngine
            return QwenTTSEngine(model_size=size)
        elif backend == "xtts_v2":
            from src.engines.xtts_engine import XTTSEngine
            return XTTSEngine()
        else:
            raise ValueError(f"Неизвестный TTS backend: {backend}")

    return manager.get_tts(key, factory)
