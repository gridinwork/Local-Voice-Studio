# Итоговый отчёт — Local Voice Studio

Дата: 2026-09-21. Оборудование: NVIDIA RTX 3060 12 GB VRAM, Windows 11, Python 3.12.2.

## 1. Что реализовано

- **MODE 1 (Text → Cloned Voice)** — end-to-end pipeline: Voice Profile → reference → Russian/English synthesis → WAV/MP3.
- **Voice Profile system** — create/delete/rename, multiple references, rebuild, quality status, disk prompt cache and persistence.
- **Audio preprocessing** — decode, resample, silence trim, RMS normalization, reference quality checks.
- **Local ASR** — faster-whisper on CPU for reference transcription.
- **PySide6 GUI** — dark UI, three operating tabs, GPU/VRAM status, background workers and quality presets.
- **Local API** — FastAPI bound to 127.0.0.1 with status, GPU, voices, TTS, voice conversion and audio-analysis endpoints.
- **MODE 2 (Audio → Cloned Voice)** — Seed-VC integration through an isolated subprocess/venv.
- **MODE 3 (Live, EXPERIMENTAL)** — push-to-talk capture → conversion → playback.
- **Benchmark tooling** and objective audio comparison utilities.
- Documentation and Windows install/start scripts.

## 2. TTS backend

Primary: **Qwen3-TTS** (1.7B balanced/quality, 0.6B fast). The architecture also includes an XTTS-v2 fallback backend. See `docs/MODEL_RESEARCH.md`.

## 3. Voice Conversion backend

Primary: **Seed-VC**, isolated in `models/seed-vc/.venv-vc` to avoid dependency conflicts with the main Qwen TTS environment.

## 4. Runtime versions used during development

- Python 3.12.2
- PyTorch main environment: CUDA 12.4 build
- Qwen TTS / transformers stack in the main environment
- faster-whisper small, CPU/int8
- Seed-VC in its own environment

Exact installed package versions may differ on another machine and should be checked locally.

## 5. Measured performance on RTX 3060

Measured Qwen3-TTS results are preserved in `docs/BENCHMARK.md`. The observed RTF was around 4.3–4.6 without FlashAttention 2, with peak VRAM roughly 2.6–2.8 GB for 0.6B and 4.5–4.8 GB for 1.7B.

Seed-VC preserved output duration very closely to the source in the measured examples. The actual diffusion pass was much faster than the full wrapper call because the current subprocess integration reloads its models on each conversion.

## 6. Quality notes

Voice cloning quality depends heavily on clean reference material and an accurate reference transcript. The application therefore scores reference quality and supports multiple reference recordings per profile.

## 7. Known limitations

1. Qwen3-TTS generation without FlashAttention 2 is slower than real time on the tested RTX 3060.
2. XTTS-v2 is present as a fallback architecture but was not the main tested backend.
3. MODE 3 is push-to-talk, not continuous low-latency streaming.
4. Seed-VC currently reloads its model stack for each subprocess call, adding startup overhead.
5. Prosody/emotion preservation is backend-dependent and should be evaluated by listening as well as objective metrics.
6. Full realtime RU↔EN translation is a future layer, not part of v0.1.0.

## 8. Important fixes made during development

- fixed automatic profile restoration/selection on GUI restart;
- separated Qwen 0.6B and 1.7B voice-prompt cache keys;
- configured pydub to use the bundled imageio-ffmpeg binary when system FFmpeg is unavailable;
- removed a speculative Seed-VC parameter mapping and made unsupported preserve-options informational rather than pretending they are independent controls;
- added automatic reference transcript reuse and objective audio-comparison tooling.

## 9. Running

```text
install.bat
start.bat
```

See [INSTALL.md](INSTALL.md).

## 10. Adding a voice

1. Create a Voice Profile.
2. Add one or more clean 10–30 second speech references.
3. Check the reference-quality status.
4. Generate speech; the TTS prompt is built and cached automatically on first use.

## 11. Future realtime translation

See [docs/REALTIME_TRANSLATOR_PLAN.md](docs/REALTIME_TRANSLATOR_PLAN.md). The existing engine interfaces, prompt cache and local ASR were intentionally separated so VAD, translation and streaming orchestration can be added without rewriting the voice backends.
