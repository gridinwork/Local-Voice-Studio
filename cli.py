"""Phase-3 proof-of-concept CLI: reference.wav + text -> output.wav.

This must work end-to-end on the RTX 3060 before any GUI work begins
(see docs/ARCHITECTURE.md phased plan). Usage:

    .venv\\Scripts\\python.exe cli.py --ref reference.wav --ref-text "..." \
        --text "Hello, this is a test." --language en --out output.wav
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import soundfile as sf

from src.engines.qwen_tts import QwenTTSEngine
from src.utils.benchmark import log_benchmark, make_record
from src.utils.gpu import get_gpu_status
from src.utils.logging_setup import get_logger

log = get_logger("cli")


def main():
    parser = argparse.ArgumentParser(description="Local Voice Studio — CLI PoC (text -> cloned voice)")
    parser.add_argument("--ref", required=True, help="Path to reference audio (wav/mp3/flac)")
    parser.add_argument("--ref-text", required=True, help="Transcript of the reference audio")
    parser.add_argument("--text", required=True, help="Text to synthesize")
    parser.add_argument("--language", default="en", choices=["ru", "en", "auto"])
    parser.add_argument("--out", default="output.wav")
    parser.add_argument("--model-size", default="1.7B", choices=["0.6B", "1.7B"])
    parser.add_argument("--cache", default="cache/poc_voice_prompt.pt")
    args = parser.parse_args()

    gpu = get_gpu_status()
    log.info(f"GPU: {gpu.name if gpu.available else 'НЕДОСТУПНА'} | CUDA: {gpu.cuda_version} | "
              f"VRAM free: {gpu.vram_free_mb:.0f} MB")
    if not gpu.available:
        log.error(gpu.error)
        sys.exit(1)

    engine = QwenTTSEngine(model_size=args.model_size)

    t0 = time.time()
    engine.load_model()
    log.info(f"Модель загружена за {time.time() - t0:.2f} сек")

    Path(args.cache).parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    engine.build_voice_prompt(args.ref, args.ref_text, args.cache)
    log.info(f"Voice prompt построен за {time.time() - t0:.2f} сек")

    result = engine.generate(args.text, args.language, args.cache)
    sf.write(args.out, result.audio, result.sample_rate)

    duration = len(result.audio) / result.sample_rate
    rtf = result.generation_time_sec / duration if duration > 0 else float("nan")
    log.info(
        f"Готово: {args.out} | audio duration={duration:.2f}s | "
        f"gen time={result.generation_time_sec:.2f}s | RTF={rtf:.2f} | "
        f"peak VRAM={result.peak_vram_mb:.0f} MB"
    )
    log_benchmark(make_record(
        op="tts_generate", engine=f"qwen3_tts_{args.model_size}", language=args.language,
        text_len=len(args.text), audio_duration_sec=duration,
        generation_time_sec=result.generation_time_sec, rtf=rtf, peak_vram_mb=result.peak_vram_mb,
    ))


if __name__ == "__main__":
    main()
