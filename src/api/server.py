"""Local-only REST API (127.0.0.1) so other local tools can reuse the same Voice Engine."""
from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Optional

import soundfile as sf
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.audio.asr import transcribe as asr_transcribe
from src.engines.engine_factory import create_tts_engine
from src.engines.model_manager import get_model_manager
from src.profiles.voice_profile import VoiceProfile
from src.utils.config import get_config
from src.utils.gpu import get_gpu_status
from src.utils.logging_setup import get_logger
from src.audio.audio_preprocessing import configure_pydub_ffmpeg

log = get_logger("api")
configure_pydub_ffmpeg()
app = FastAPI(title="Local Voice Studio API", version="0.1.0")


class TTSRequest(BaseModel):
    text: str
    language: str = "auto"
    voice_profile: str
    quality_preset: Optional[str] = None


class VoiceCreateRequest(BaseModel):
    name: str


class VCRequest(BaseModel):
    voice_profile: str
    source_audio_b64: str
    preserve_timing: bool = True
    preserve_prosody: bool = True


class AnalyzeRequest(BaseModel):
    path_a: str
    path_b: str


def _audio_to_b64_wav(audio, sample_rate: int) -> str:
    buf = io.BytesIO()
    sf.write(buf, audio, sample_rate, format="WAV")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _ensure_prompt(engine, profile: VoiceProfile) -> str:
    cache_path = str(profile.cache_file(engine.cache_key))
    if not Path(cache_path).exists():
        ref_path = profile.best_reference_processed_path()
        if ref_path is None:
            raise HTTPException(400, f"Профиль '{profile.name}' не содержит обработанных референсов.")
        entry = next((r for r in profile.references
                      if (profile.processed_dir / f"{Path(r.filename).stem}_clean.wav") == ref_path), None)
        ref_text = entry.transcript if entry and entry.transcript else asr_transcribe(ref_path).text
        engine.build_voice_prompt(str(ref_path), ref_text, cache_path)
    return cache_path


@app.get("/status")
def status():
    return {"status": "ok", "local_only": True}


@app.get("/gpu")
def gpu():
    s = get_gpu_status()
    return {
        "available": s.available,
        "name": s.name,
        "cuda_version": s.cuda_version,
        "vram_total_mb": s.vram_total_mb,
        "vram_used_mb": s.vram_used_mb,
        "vram_free_mb": s.vram_free_mb,
        "error": s.error,
    }


@app.get("/voices")
def list_voices():
    return {"voices": VoiceProfile.list_all()}


@app.post("/voices")
def create_voice(req: VoiceCreateRequest):
    try:
        VoiceProfile.create(req.name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"created": req.name}


@app.post("/tts")
def tts(req: TTSRequest):
    try:
        profile = VoiceProfile.load(req.voice_profile)
    except FileNotFoundError:
        raise HTTPException(404, f"Профиль '{req.voice_profile}' не найден.")

    cfg = get_config()
    if req.quality_preset:
        cfg.set("active_preset", req.quality_preset)

    engine = create_tts_engine()
    cache_path = _ensure_prompt(engine, profile)
    result = engine.generate(req.text, req.language, cache_path, quality_preset=cfg.get("active_preset", "balanced"))

    ref_path = profile.best_reference_processed_path()
    if ref_path is not None:
        from src.audio.audio_preprocessing import match_loudness_to_reference
        result.audio = match_loudness_to_reference(result.audio, ref_path)

    return {
        "audio_b64": _audio_to_b64_wav(result.audio, result.sample_rate),
        "sample_rate": result.sample_rate,
        "generation_time_sec": result.generation_time_sec,
        "duration_sec": len(result.audio) / result.sample_rate,
        "peak_vram_mb": result.peak_vram_mb,
    }


@app.post("/voice-convert")
def voice_convert(req: VCRequest):
    try:
        profile = VoiceProfile.load(req.voice_profile)
    except FileNotFoundError:
        raise HTTPException(404, f"Профиль '{req.voice_profile}' не найден.")

    target_ref = profile.best_reference_processed_path()
    if target_ref is None:
        raise HTTPException(400, f"Профиль '{req.voice_profile}' не содержит обработанных референсов.")

    import tempfile
    raw = base64.b64decode(req.source_audio_b64)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(raw)
        source_path = f.name

    from src.engines.seed_vc_engine import SeedVCEngine
    manager = get_model_manager()
    engine = manager.get_vc("seed_vc", SeedVCEngine)
    result = engine.convert(
        source_path, str(target_ref),
        preserve_timing=req.preserve_timing, preserve_prosody=req.preserve_prosody,
    )

    return {
        "audio_b64": _audio_to_b64_wav(result.audio, result.sample_rate),
        "sample_rate": result.sample_rate,
        "generation_time_sec": result.generation_time_sec,
        "source_duration_sec": result.source_duration_sec,
        "output_duration_sec": result.output_duration_sec,
    }


@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    if not Path(req.path_a).exists():
        raise HTTPException(404, f"Файл не найден: {req.path_a}")
    if not Path(req.path_b).exists():
        raise HTTPException(404, f"Файл не найден: {req.path_b}")

    from src.audio.analysis import compare
    return compare(req.path_a, req.path_b)


def run():
    import uvicorn
    cfg = get_config()
    host = cfg.get("api_host", "127.0.0.1")
    port = cfg.get("api_port", 8722)
    log.info(f"Запуск Local API на {host}:{port} (только localhost)")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run()
