"""Reference audio decoding, cleanup and quality assessment.

Used both by the Voice Profile pipeline (MODE 1 reference audio) and by
MODE 2 source-audio loading. Never mutates the user's original files —
always writes a processed copy elsewhere.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import numpy as np
import soundfile as sf

from src.utils.logging_setup import get_logger

log = get_logger("audio_preprocessing")

TARGET_SR = 24000
MIN_DURATION_SEC = 3.0
RECOMMENDED_DURATION_SEC = 10.0
MAX_USEFUL_DURATION_SEC = 60.0
SILENCE_THRESHOLD_DB = -40.0
CLIPPING_THRESHOLD = 0.998
LOW_VOLUME_RMS_DB = -35.0
NOISE_FLOOR_ACCEPTABLE = 0.02
NOISE_FLOOR_BAD = 0.08


class Quality(str, Enum):
    GOOD = "GOOD"
    ACCEPTABLE = "ACCEPTABLE"
    BAD = "BAD"


@dataclass
class QualityReport:
    quality: Quality
    duration_sec: float
    reasons: list[str] = field(default_factory=list)
    rms_db: float = 0.0
    clipping_ratio: float = 0.0
    silence_ratio: float = 0.0
    sample_rate: int = 0


def _find_ffmpeg() -> str | None:
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _ffmpeg_available() -> bool:
    return _find_ffmpeg() is not None


def configure_pydub_ffmpeg() -> None:
    exe = _find_ffmpeg()
    if exe is None:
        return
    try:
        from pydub import AudioSegment
        AudioSegment.converter = exe
    except ImportError:
        pass


def decode_to_wav(src_path: Path, dst_path: Path, target_sr: int = TARGET_SR) -> Path:
    dst_path.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg_exe = _find_ffmpeg()
    if ffmpeg_exe:
        cmd = [
            ffmpeg_exe, "-y", "-i", str(src_path),
            "-ac", "1", "-ar", str(target_sr),
            "-sample_fmt", "s16",
            str(dst_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg не смог декодировать {src_path.name}: {result.stderr[-500:]}")
        return dst_path

    log.warning("ffmpeg не найден в PATH — используется резервный декодер (только WAV/FLAC/OGG).")
    data, sr = sf.read(str(src_path), always_2d=False)
    if data.ndim > 1:
        data = data.mean(axis=1)
    if sr != target_sr:
        data = _resample_linear(data, sr, target_sr)
    sf.write(str(dst_path), data, target_sr, subtype="PCM_16")
    return dst_path


def _resample_linear(data: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    duration = len(data) / orig_sr
    n_target = int(round(duration * target_sr))
    x_old = np.linspace(0.0, duration, num=len(data), endpoint=False)
    x_new = np.linspace(0.0, duration, num=n_target, endpoint=False)
    return np.interp(x_new, x_old, data).astype(np.float32)


def trim_silence(data: np.ndarray, sr: int, threshold_db: float = SILENCE_THRESHOLD_DB) -> np.ndarray:
    if len(data) == 0:
        return data
    amp = np.abs(data)
    threshold = 10 ** (threshold_db / 20.0)
    above = np.where(amp > threshold)[0]
    if len(above) == 0:
        return data
    start, end = above[0], above[-1] + 1
    pad = int(0.05 * sr)
    start = max(0, start - pad)
    end = min(len(data), end + pad)
    return data[start:end]


def normalize_loudness(data: np.ndarray, target_rms_db: float = -20.0) -> np.ndarray:
    rms = np.sqrt(np.mean(data.astype(np.float64) ** 2)) + 1e-9
    current_db = 20 * np.log10(rms)
    gain_db = target_rms_db - current_db
    gain_db = float(np.clip(gain_db, -12.0, 12.0))
    gain = 10 ** (gain_db / 20.0)
    out = data * gain
    return np.clip(out, -0.999, 0.999).astype(np.float32)


def assess_quality(data: np.ndarray, sr: int) -> QualityReport:
    duration = len(data) / sr
    reasons: list[str] = []

    rms = np.sqrt(np.mean(data.astype(np.float64) ** 2)) + 1e-9
    rms_db = 20 * np.log10(rms)
    clipping_ratio = float(np.mean(np.abs(data) > CLIPPING_THRESHOLD))

    amp = np.abs(data)
    threshold = 10 ** (SILENCE_THRESHOLD_DB / 20.0)
    silence_ratio = float(np.mean(amp < threshold))

    if duration < MIN_DURATION_SEC:
        reasons.append("too short")
    elif duration < RECOMMENDED_DURATION_SEC:
        reasons.append("short (рекомендуется > 10 сек)")

    if clipping_ratio > 0.001:
        reasons.append("clipping")
    if rms_db < LOW_VOLUME_RMS_DB:
        reasons.append("low volume")
    if silence_ratio > 0.6:
        reasons.append("too much silence")

    frame_len = int(0.02 * sr) or 1
    n_frames = max(1, len(data) // frame_len)
    frame_rms = np.array([
        np.sqrt(np.mean(data[i * frame_len:(i + 1) * frame_len].astype(np.float64) ** 2) + 1e-12)
        for i in range(n_frames)
    ])
    quiet_frames = frame_rms[frame_rms < np.percentile(frame_rms, 20)]
    noise_floor = float(np.mean(quiet_frames)) if len(quiet_frames) > 0 else 0.0
    if noise_floor > NOISE_FLOOR_BAD:
        reasons.append("too much noise")
    elif noise_floor > NOISE_FLOOR_ACCEPTABLE:
        reasons.append("elevated noise")

    if not reasons:
        quality = Quality.GOOD
    elif "too short" in reasons or clipping_ratio > 0.01 or "too much noise" in reasons:
        quality = Quality.BAD
    else:
        quality = Quality.ACCEPTABLE

    return QualityReport(
        quality=quality,
        duration_sec=duration,
        reasons=reasons,
        rms_db=rms_db,
        clipping_ratio=clipping_ratio,
        silence_ratio=silence_ratio,
        sample_rate=sr,
    )


def preprocess_reference(src_path: Path, processed_path: Path, denoise: bool = False) -> QualityReport:
    tmp_decoded = processed_path.with_suffix(".decoded.wav")
    decode_to_wav(src_path, tmp_decoded)

    data, sr = sf.read(str(tmp_decoded), always_2d=False)
    if data.ndim > 1:
        data = data.mean(axis=1)
    data = data.astype(np.float32)

    data = trim_silence(data, sr)
    data = normalize_loudness(data)

    if denoise:
        data = _light_denoise(data, sr)

    processed_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(processed_path), data, sr, subtype="PCM_16")
    tmp_decoded.unlink(missing_ok=True)

    report = assess_quality(data, sr)
    log.info(f"Reference '{src_path.name}' -> quality={report.quality.value} reasons={report.reasons}")
    return report


def _light_denoise(data: np.ndarray, sr: int) -> np.ndarray:
    try:
        import noisereduce as nr
        return nr.reduce_noise(y=data, sr=sr, prop_decrease=0.5).astype(np.float32)
    except ImportError:
        log.warning("noisereduce не установлен — шумоподавление пропущено.")
        return data


def match_loudness_to_reference(audio: np.ndarray, reference_path: Path, max_gain_db: float = 12.0) -> np.ndarray:
    ref_data, ref_sr = sf.read(str(reference_path), always_2d=False)
    if ref_data.ndim > 1:
        ref_data = ref_data.mean(axis=1)
    ref_rms = np.sqrt(np.mean(ref_data.astype(np.float64) ** 2)) + 1e-9
    ref_db = 20 * np.log10(ref_rms)

    audio_rms = np.sqrt(np.mean(audio.astype(np.float64) ** 2)) + 1e-9
    audio_db = 20 * np.log10(audio_rms)

    gain_db = float(np.clip(ref_db - audio_db, -max_gain_db, max_gain_db))
    gain = 10 ** (gain_db / 20.0)
    return np.clip(audio * gain, -0.999, 0.999).astype(np.float32)


def get_duration_sec(path: Path) -> float:
    info = sf.info(str(path))
    return info.frames / info.samplerate
