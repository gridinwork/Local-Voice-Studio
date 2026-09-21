"""Seed-VC backend — PRIMARY Voice Conversion engine for MODE 2."""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

import numpy as np
import soundfile as sf

from src.engines.base_tts import EngineStatus
from src.engines.base_vc import BaseVCEngine, VCResult
from src.utils.config import PROJECT_ROOT, get_config
from src.utils.gpu import get_process_vram_peak_mb
from src.utils.logging_setup import get_logger

log = get_logger("seed_vc_engine")

SEED_VC_DIR = PROJECT_ROOT / "models" / "seed-vc"
SEED_VC_VENV_PYTHON = SEED_VC_DIR / ".venv-vc" / "Scripts" / "python.exe"


class SeedVCEngine(BaseVCEngine):
    name = "seed_vc"

    def load_model(self, precision: str = "float16", device: str = "cuda") -> None:
        if not SEED_VC_DIR.exists():
            self.status = EngineStatus.ERROR
            self.last_error = (
                f"Seed-VC не установлен в {SEED_VC_DIR}. Запустите install.bat "
                f"или см. INSTALL.md, раздел Voice Conversion."
            )
            raise RuntimeError(self.last_error)
        if not SEED_VC_VENV_PYTHON.exists():
            self.status = EngineStatus.ERROR
            self.last_error = f"Отдельное окружение Seed-VC не найдено: {SEED_VC_VENV_PYTHON}"
            raise RuntimeError(self.last_error)
        self.status = EngineStatus.READY

    def unload_model(self) -> None:
        self.status = EngineStatus.UNLOADED

    def convert(
        self,
        source_audio_path: str,
        target_ref_audio_path: str,
        preserve_timing: bool = True,
        preserve_prosody: bool = True,
        diffusion_steps: int = 25,
    ) -> VCResult:
        if self.status != EngineStatus.READY:
            self.load_model()

        cfg = get_config()
        out_dir = Path(cfg.get("output_dir")) / "_vc_tmp"
        out_dir.mkdir(parents=True, exist_ok=True)
        source_duration = sf.info(source_audio_path).duration

        cmd = [
            str(SEED_VC_VENV_PYTHON), "inference.py",
            "--source", str(Path(source_audio_path).resolve()),
            "--target", str(Path(target_ref_audio_path).resolve()),
            "--output", str(out_dir.resolve()),
            "--diffusion-steps", str(diffusion_steps),
        ]
        del preserve_timing, preserve_prosody

        log.info(f"Запуск Seed-VC: {' '.join(cmd)}")
        t0 = time.time()
        result = subprocess.run(cmd, cwd=str(SEED_VC_DIR), capture_output=True, text=True)
        elapsed = time.time() - t0

        if result.returncode != 0:
            self.last_error = result.stderr[-2000:]
            log.error(f"Seed-VC завершился с ошибкой: {self.last_error}")
            raise RuntimeError(f"Voice Conversion не удался: {self.last_error}")

        produced = sorted(out_dir.glob("*.wav"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not produced:
            raise RuntimeError("Seed-VC не создал выходной файл.")
        out_path = produced[0]

        audio, sr = sf.read(str(out_path), always_2d=False)
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        audio = audio.astype(np.float32)

        return VCResult(
            audio=audio,
            sample_rate=sr,
            generation_time_sec=elapsed,
            source_duration_sec=source_duration,
            output_duration_sec=len(audio) / sr,
            peak_vram_mb=get_process_vram_peak_mb(),
        )
