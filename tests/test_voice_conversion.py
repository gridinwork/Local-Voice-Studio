"""Voice Conversion timing/pause preservation check."""
from __future__ import annotations
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, soundfile as sf
from src.audio.audio_preprocessing import trim_silence

def detect_pauses(audio,sr,threshold_db=-35.0,min_pause_sec=0.15):
    amp=np.abs(audio); threshold=10**(threshold_db/20.0); silent=amp<threshold; pauses=[]; start=None
    for i,s in enumerate(silent):
        if s and start is None: start=i
        elif not s and start is not None:
            d=(i-start)/sr
            if d>=min_pause_sec: pauses.append((start/sr,i/sr))
            start=None
    return pauses

def compare(source_path,output_path):
    src,sr_src=sf.read(source_path,always_2d=False); out,sr_out=sf.read(output_path,always_2d=False)
    if src.ndim>1: src=src.mean(axis=1)
    if out.ndim>1: out=out.mean(axis=1)
    src_t=trim_silence(src,sr_src); out_t=trim_silence(out,sr_out)
    sd=len(src_t)/sr_src; od=len(out_t)/sr_out; diff=abs(od-sd)/sd*100 if sd>0 else float("nan")
    print(f"Source {sd:.2f}s | Output {od:.2f}s | Difference {diff:.1f}%")
    print(f"Pauses source={len(detect_pauses(src,sr_src))}, output={len(detect_pauses(out,sr_out))}")

def main():
    p=argparse.ArgumentParser(); p.add_argument("--source",nargs="+",required=True); p.add_argument("--target-ref",required=True); a=p.parse_args()
    from src.engines.model_manager import get_model_manager
    from src.engines.seed_vc_engine import SeedVCEngine
    engine=get_model_manager().get_vc("seed_vc",SeedVCEngine)
    for source in a.source:
        result=engine.convert(source,a.target_ref); out_path=Path(source).with_name(Path(source).stem+"_converted.wav")
        sf.write(str(out_path),result.audio,result.sample_rate); print(f"-> {out_path}"); compare(source,str(out_path))

if __name__=="__main__": main()
