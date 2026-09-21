"""Ensures only the engines actually needed are resident in VRAM at once."""
from __future__ import annotations

from typing import Optional

from src.engines.base_tts import BaseTTSEngine
from src.engines.base_vc import BaseVCEngine
from src.utils.gpu import empty_cache
from src.utils.logging_setup import get_logger

log = get_logger("model_manager")


class ModelManager:
    def __init__(self):
        self._tts: Optional[BaseTTSEngine] = None
        self._vc: Optional[BaseVCEngine] = None
        self._active_tts_key: Optional[str] = None
        self._active_vc_key: Optional[str] = None

    def get_tts(self, factory_key: str, factory) -> BaseTTSEngine:
        if self._active_tts_key != factory_key:
            self.unload_vc()
            if self._tts is not None:
                self._tts.unload_model()
                self._tts = None
            self._tts = factory()
            self._active_tts_key = factory_key
        return self._tts

    def get_vc(self, factory_key: str, factory) -> BaseVCEngine:
        if self._active_vc_key != factory_key:
            self.unload_tts()
            if self._vc is not None:
                self._vc.unload_model()
                self._vc = None
            self._vc = factory()
            self._active_vc_key = factory_key
        return self._vc

    def unload_tts(self) -> None:
        if self._tts is not None:
            log.info(f"Выгрузка TTS engine '{self._active_tts_key}' для освобождения VRAM")
            self._tts.unload_model()
            self._tts = None
            self._active_tts_key = None
            empty_cache()

    def unload_vc(self) -> None:
        if self._vc is not None:
            log.info(f"Выгрузка VC engine '{self._active_vc_key}' для освобождения VRAM")
            self._vc.unload_model()
            self._vc = None
            self._active_vc_key = None
            empty_cache()

    def unload_all(self) -> None:
        self.unload_tts()
        self.unload_vc()


_manager: Optional[ModelManager] = None


def get_model_manager() -> ModelManager:
    global _manager
    if _manager is None:
        _manager = ModelManager()
    return _manager
