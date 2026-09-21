"""Objective acoustic comparison between two audio files (e.g. a reference
recording and its cloned/converted counterpart): pitch, speaking rate, pauses,
loudness. This is what stands in for "listening" when there's no ear
available — it turns "does this sound right?" into numbers that can be
checked without a human replaying every file, and is what backs the local
`/analyze` API endpoint and `tests/compare_audio.py`.

Not a substitute for actually listening — a duration/pitch/loudness match
doesn't guarantee naturalness. It catches gross mismatches (wrong speed,
wrong loudness, pitch far outside the speaker's range) that ARE measurable.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf


@dataclass
class AudioStats:
    path: str
    duration_sec: float
    sample_rate: int
    rms_db: float
    f0_mean_hz: float
    f0_std_hz: float
    f0_min_hz: float
    f0_max_hz: float
    voiced_ratio: float
    speaking_rate_syllables_per_sec: float
    pause_count: int
    total_pause_sec: float


def _load_mono(path: str | Path, target_sr: int | None = None) -> tuple[np.ndarray, int]:
    data, sr = sf.read(str(path), always_2d=False)
    if data.ndim > 1:
        data = data.mean(axis=1)
    data = data.astype(np.float32)
    if target_sr and sr != target_sr:
        data = librosa.resample(data, orig_sr=sr, target_sr=target_sr)
        sr = target_sr
    return data, sr


def _detect_pauses(audio: np.ndarray, sr: int, threshold_db: float = -35.0, min_pause_sec: float = 0.15):
    amp = np.abs(audio)
    threshold = 10 ** (threshold_db / 20.0)
    is_silent = amp < threshold
    pauses = []
    start = None
    for i, silent in enumerate(is_silent):
        if silent and start is None:
            start = i
        elif not silent and start is not None:
            dur = (i - start) / sr
            if dur >= min_pause_sec:
                pauses.append(dur)
            start = None
    return pauses


def _estimate_speaking_rate(audio: np.ndarray, sr: int) -> float:
    hop = 512
    rms = librosa.feature.rms(y=audio, hop_length=hop)[0]
    if len(rms) < 3:
        return 0.0
    from scipy.signal import find_peaks
    peaks, _ = find_peaks(rms, distance=max(1, int(0.1 * sr / hop)), prominence=np.std(rms) * 0.3)
    duration = len(audio) / sr
    return len(peaks) / duration if duration > 0 else 0.0


def analyze(path: str | Path) -> AudioStats:
    audio, sr = _load_mono(path)
    duration = len(audio) / sr

    rms = np.sqrt(np.mean(audio.astype(np.float64) ** 2)) + 1e-9
    rms_db = 20 * np.log10(rms)

    f0, voiced_flag, _ = librosa.pyin(
        audio, fmin=librosa.note_to_hz("C2"), fmax=librosa.note_to_hz("C7"), sr=sr
    )
    voiced = f0[~np.isnan(f0)] if f0 is not None else np.array([])
    voiced_ratio = float(np.mean(voiced_flag)) if voiced_flag is not None and len(voiced_flag) else 0.0

    pauses = _detect_pauses(audio, sr)
    speaking_rate = _estimate_speaking_rate(audio, sr)

    return AudioStats(
        path=str(path),
        duration_sec=duration,
        sample_rate=sr,
        rms_db=float(rms_db),
        f0_mean_hz=float(np.mean(voiced)) if len(voiced) else 0.0,
        f0_std_hz=float(np.std(voiced)) if len(voiced) else 0.0,
        f0_min_hz=float(np.min(voiced)) if len(voiced) else 0.0,
        f0_max_hz=float(np.max(voiced)) if len(voiced) else 0.0,
        voiced_ratio=voiced_ratio,
        speaking_rate_syllables_per_sec=speaking_rate,
        pause_count=len(pauses),
        total_pause_sec=float(sum(pauses)),
    )


def compare(path_a: str | Path, path_b: str | Path) -> dict:
    a = analyze(path_a)
    b = analyze(path_b)

    def pct_diff(x, y):
        if x == 0:
            return float("nan")
        return (y - x) / x * 100

    return {
        "a": asdict(a),
        "b": asdict(b),
        "duration_diff_pct": pct_diff(a.duration_sec, b.duration_sec),
        "loudness_diff_db": b.rms_db - a.rms_db,
        "pitch_mean_diff_hz": b.f0_mean_hz - a.f0_mean_hz,
        "pitch_mean_diff_pct": pct_diff(a.f0_mean_hz, b.f0_mean_hz),
        "speaking_rate_diff_pct": pct_diff(a.speaking_rate_syllables_per_sec, b.speaking_rate_syllables_per_sec),
        "pause_count_diff": b.pause_count - a.pause_count,
    }


def suggest_loudness_gain_db(reference_path: str | Path, target_path: str | Path) -> float:
    ref = analyze(reference_path)
    tgt = analyze(target_path)
    return ref.rms_db - tgt.rms_db
