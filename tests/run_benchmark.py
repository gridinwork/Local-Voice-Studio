"""Automated Qwen3-TTS benchmark."""
from __future__ import annotations
import argparse, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.engines.qwen_tts import QwenTTSEngine
from src.utils.benchmark import log_benchmark, make_record
from src.utils.gpu import get_gpu_status, reset_peak_stats

CASES = {
    "short_en": ("en", "Hello, this is a short test."),
    "long_en": ("en", "Hello. Today I would like to demonstrate our new robotic system. It combines advanced sensors, real-time control, and a locally running voice engine so that everything works completely offline."),
    "short_ru": ("ru", "Привет, это короткий тест."),
    "long_ru": ("ru", "Привет. Сегодня я хочу показать вам нашу новую роботизированную систему. Она сочетает современные датчики, управление в реальном времени и локальный голосовой движок, который работает полностью автономно."),
}

def run(ref_audio, ref_text, model_size, out_dir):
    import soundfile as sf
    engine = QwenTTSEngine(model_size=model_size); t0=time.time(); engine.load_model(); load_time=time.time()-t0
    cache_path=out_dir/f"bench_prompt_{model_size}.pt"; engine.build_voice_prompt(ref_audio,ref_text,str(cache_path))
    rows=[]
    for case_name,(lang,text) in CASES.items():
        reset_peak_stats(); result=engine.generate(text,lang,str(cache_path))
        duration=len(result.audio)/result.sample_rate; rtf=result.generation_time_sec/duration if duration>0 else float("nan")
        sf.write(str(out_dir/f"bench_{model_size}_{case_name}.wav"),result.audio,result.sample_rate)
        row={"case":case_name,"model":model_size,"language":lang,"audio_duration_sec":duration,"generation_time_sec":result.generation_time_sec,"rtf":rtf,"peak_vram_mb":result.peak_vram_mb,"load_time_sec":load_time}
        rows.append(row); log_benchmark(make_record(op="benchmark",engine=f"qwen3_tts_{model_size}",language=lang,text_len=len(text),audio_duration_sec=duration,generation_time_sec=result.generation_time_sec,rtf=rtf,peak_vram_mb=result.peak_vram_mb,extra={"case":case_name}))
        print(row)
    engine.unload_model(); return rows

def main():
    p=argparse.ArgumentParser(); p.add_argument("--ref",required=True); p.add_argument("--ref-text",required=True); p.add_argument("--out-dir",default="cache/benchmark"); a=p.parse_args()
    out=Path(a.out_dir); out.mkdir(parents=True,exist_ok=True); gpu=get_gpu_status(); print(f"GPU: {gpu.name}")
    run(a.ref,a.ref_text,"0.6B",out); run(a.ref,a.ref_text,"1.7B",out)

if __name__=="__main__": main()
