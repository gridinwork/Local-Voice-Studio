"""Objective A/B acoustic comparison.

Usage:
    .venv\Scripts\python.exe tests\compare_audio.py --a reference.wav --b generated.wav
    .venv\Scripts\python.exe tests\compare_audio.py --profile Speaker1 --b output/generated.wav
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.audio.analysis import compare

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--a", help="Reference/source audio path")
    parser.add_argument("--profile", help="Voice Profile name (uses its best reference as --a)")
    parser.add_argument("--b", required=True, help="Generated/converted audio path")
    args = parser.parse_args()
    if args.profile:
        from src.profiles.voice_profile import VoiceProfile
        profile = VoiceProfile.load(args.profile)
        ref_path = profile.best_reference_processed_path()
        if ref_path is None:
            print(f"Профиль '{args.profile}' не содержит обработанных референсов."); sys.exit(1)
        path_a = str(ref_path)
    elif args.a:
        path_a = args.a
    else:
        print("Укажите --a <файл> или --profile <имя>"); sys.exit(1)
    result = compare(path_a, args.b)
    print(f"A (референс): {path_a}")
    print(f"B (результат): {args.b}\n")
    print(f"Длительность: A={result['a']['duration_sec']:.2f}s B={result['b']['duration_sec']:.2f}s (разница {result['duration_diff_pct']:.1f}%)")
    print(f"Громкость: A={result['a']['rms_db']:.1f}dB B={result['b']['rms_db']:.1f}dB (разница {result['loudness_diff_db']:+.1f}dB)")
    print(f"Pitch: A={result['a']['f0_mean_hz']:.0f}Hz B={result['b']['f0_mean_hz']:.0f}Hz (разница {result['pitch_mean_diff_pct']:.1f}%)")
    print(f"Темп: A={result['a']['speaking_rate_syllables_per_sec']:.2f}/s B={result['b']['speaking_rate_syllables_per_sec']:.2f}/s")
    print(f"Пауз: A={result['a']['pause_count']} B={result['b']['pause_count']} (разница {result['pause_count_diff']:+d})")
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__": main()
