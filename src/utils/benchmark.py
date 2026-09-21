"""Appends structured benchmark records to logs/benchmark.jsonl (see spec §17/§35)."""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from src.utils.config import PROJECT_ROOT

BENCHMARK_FILE = PROJECT_ROOT / "logs" / "benchmark.jsonl"


@dataclass
class BenchmarkRecord:
    timestamp: str
    op: str
    engine: str
    quality_preset: str = ""
    language: str = ""
    text_len: int = 0
    audio_duration_sec: float = 0.0
    generation_time_sec: float = 0.0
    rtf: float = 0.0
    peak_vram_mb: float = 0.0
    ttfa_sec: float = 0.0
    extra: dict = field(default_factory=dict)


def log_benchmark(record: BenchmarkRecord) -> None:
    BENCHMARK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(BENCHMARK_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")


def make_record(op: str, engine: str, **kwargs) -> BenchmarkRecord:
    return BenchmarkRecord(
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
        op=op,
        engine=engine,
        **kwargs,
    )
