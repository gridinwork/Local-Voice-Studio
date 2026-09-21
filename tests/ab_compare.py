"""A/B comparison: generate the same text with Qwen3-TTS 0.6B and 1.7B."""
from __future__ import annotations
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import soundfile as sf
from src.engines.qwen_tts import QwenTTSEngine

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ref", required=True)
    parser.add_argument("--ref-text", required=True)
    parser.add_argument("--text", required=True)
    parser.add_argument("--language", default="en")
    parser.add_argument("--out-dir", default="output/ab_compare")
    args = parser.parse_args()
    out_dir = Path(args.out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    results = {}
    for size in ("0.6B", "1.7B"):
        engine = QwenTTSEngine(model_size=size); engine.load_model()
        cache_path = out_dir / f"prompt_{size}.pt"
        engine.build_voice_prompt(args.ref, args.ref_text, str(cache_path))
        result = engine.generate(args.text, args.language, str(cache_path))
        out_path = out_dir / f"engine_{'A' if size == '0.6B' else 'B'}_{size}.wav"
        sf.write(str(out_path), result.audio, result.sample_rate)
        duration = len(result.audio) / result.sample_rate
        rtf = result.generation_time_sec / duration if duration > 0 else float("nan")
        results[size] = (out_path, result.generation_time_sec, duration, rtf, result.peak_vram_mb)
        engine.unload_model()
        print(f"[{size}] -> {out_path} | gen={result.generation_time_sec:.2f}s | duration={duration:.2f}s | RTF={rtf:.2f} | VRAM={result.peak_vram_mb:.0f}MB")
    print("\nA =", results["0.6B"][0]); print("B =", results["1.7B"][0])

if __name__ == "__main__": main()
