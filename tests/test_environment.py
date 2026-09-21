"""Hardware/software environment smoke test."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def main():
    print("=== Local Voice Studio — проверка окружения ===")
    print(f"[OK] Python {sys.version.split()[0]}")
    import torch
    print(f"[OK] PyTorch {torch.__version__}")
    if not torch.cuda.is_available():
        print("[FAIL] CUDA недоступна."); sys.exit(1)
    name = torch.cuda.get_device_name(0)
    free_b, total_b = torch.cuda.mem_get_info(0)
    print(f"[OK] GPU: {name}, VRAM всего: {total_b/(1024**2):.0f} MB, свободно: {free_b/(1024**2):.0f} MB")
    from src.audio.audio_preprocessing import _find_ffmpeg
    exe = _find_ffmpeg()
    if not exe:
        print("[FAIL] FFmpeg не найден."); sys.exit(1)
    print(f"[OK] FFmpeg: {exe}")
    import soundfile, sounddevice as sd
    print(f"[OK] Аудио-устройства: {len(sd.query_devices())}")
    try:
        import qwen_tts
        print("[OK] qwen-tts установлен")
    except ImportError:
        print("[WARN] qwen-tts не установлен")
    from src.utils.config import get_config
    cfg = get_config()
    for key in ("output_dir","cache_dir","voices_dir","logs_dir"):
        print(f"[OK] {key}: {cfg.path_for(key)}")
    print("=== Проверка завершена успешно ===")

if __name__ == "__main__": main()
