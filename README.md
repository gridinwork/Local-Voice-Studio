# Local Voice Studio — Offline Voice Cloning & Voice Conversion

![Local Voice Studio interface](IMG/interface.png)

**Local Voice Studio** is a Windows desktop application for fully local voice cloning, text-to-speech, voice conversion and experimental live voice processing. Reference recordings, generated audio, cached voice prompts and logs stay on the local computer; the Internet is only required when models or Python packages need to be downloaded during setup.

> **Privacy-first design:** voice profiles and user audio are intentionally excluded from this repository and are ignored by Git.

## What the application does

Local Voice Studio combines several voice-processing workflows behind one PySide6 desktop interface.

### 1. Text → Cloned Voice

Type text in Russian or English and synthesize it using the selected voice profile.

The primary backend is **Qwen3-TTS**, used for zero-shot voice cloning from reference recordings. The application can cache a reusable voice prompt so repeated generations do not need to rebuild the profile representation each time.

Main functions:

- Russian and English text-to-speech;
- zero-shot voice cloning from a reference recording;
- reusable voice profiles;
- reference transcript support;
- quality presets: `fast`, `balanced`, `quality`;
- asynchronous generation so the GUI remains responsive;
- WAV and MP3 export;
- generation-time, duration, RTF and VRAM reporting.

### 2. Audio → Cloned Voice

Convert an existing speech recording to the selected target voice while keeping the original spoken content and timing as closely as the backend allows.

The planned/default conversion backend is **Seed-VC**. This mode is separated from TTS because voice conversion and text synthesis solve different problems and use different model pipelines.

Typical workflow:

1. Select a target Voice Profile.
2. Load a source speech file.
3. Run voice conversion.
4. Preview the result.
5. Save the converted audio.

### 3. Live Voice Conversion — Experimental

The **LIVE** tab provides an experimental push-to-talk / microphone-oriented workflow intended as a foundation for future low-latency voice conversion and real-time RU↔EN translation.

The long-term architecture for this mode is documented in `docs/REALTIME_TRANSLATOR_PLAN.md`.

## Voice Profiles

A Voice Profile groups one or more reference recordings for one speaker.

The profile manager supports:

- create profile;
- delete profile;
- rename profile;
- add MP3/WAV/FLAC references;
- record a reference directly from the microphone;
- store multiple references per profile;
- remove individual references;
- preview a selected reference;
- reuse reference transcripts;
- rebuild cached profile data;
- automatic reference-quality analysis.

Reference recordings and profile-generated data are stored under `voices/` and are ignored by Git.

## Reference Quality Analysis

The application analyzes imported reference recordings before they are used for cloning. The analysis pipeline checks properties such as duration, signal level and other audio-quality indicators and reports a human-readable quality status in the interface.

This is useful because voice cloning quality depends heavily on the cleanliness and duration of the reference material.

## Local ASR

The project includes local speech-recognition support through **faster-whisper**. ASR can be used where a transcript is required or useful for voice-reference processing and future translation workflows.

Default configuration:

- backend: `faster_whisper`;
- model: `small`;
- ASR device: CPU by default.

These values are configurable in `config/config.json`.

## Audio Playback and Recording

The GUI includes local audio utilities for:

- microphone recording;
- waveform display;
- play / pause / stop;
- output-volume control;
- listening to reference files;
- listening to generated results;
- saving WAV;
- saving MP3.

## GPU and Runtime Monitoring

Local Voice Studio is designed primarily for CUDA-capable NVIDIA GPUs.

The main window can display:

- detected GPU name;
- VRAM usage;
- CUDA version;
- generation duration;
- generated-audio duration;
- real-time factor (RTF);
- peak VRAM where available.

The development configuration was tested around an NVIDIA RTX 3060 12 GB environment. Other CUDA GPUs may work depending on the selected models and available VRAM.

## Quality Presets

The default configuration contains three operating presets:

| Preset | TTS model | VC diffusion steps | Precision |
|---|---:|---:|---|
| `fast` | 0.6B | 10 | float16 |
| `balanced` | 1.7B | 25 | bfloat16 |
| `quality` | 1.7B | 50 | bfloat16 |

The active preset is configurable in `config/config.json`.

## Local API

An optional **FastAPI** server is included for integration with other local tools and applications.

Default binding:

```text
127.0.0.1:8722
```

The default loopback binding means the API is intended for local-machine integrations rather than public network exposure.

The API layer can be used to connect Local Voice Studio to local assistants, automation software, robotics interfaces, or other desktop applications.

Available endpoints include status/GPU information, voice-profile listing/creation, text-to-speech, voice conversion, and objective audio comparison.

## Architecture

The project is divided into several subsystems:

```text
LocalVoiceStudio/
├── app.py                      # PySide6 GUI entry point
├── cli.py                      # Text-to-cloned-voice CLI proof of concept
├── config/
│   └── config.json
├── src/
│   ├── api/
│   │   └── server.py
│   ├── audio/
│   │   ├── analysis.py
│   │   ├── asr.py
│   │   └── audio_preprocessing.py
│   ├── engines/
│   │   ├── base_tts.py
│   │   ├── base_vc.py
│   │   ├── engine_factory.py
│   │   ├── model_manager.py
│   │   ├── qwen_tts.py
│   │   ├── seed_vc_engine.py
│   │   └── xtts_engine.py
│   ├── gui/
│   │   ├── audio_player.py
│   │   ├── main_window.py
│   │   ├── mode1_panel.py
│   │   ├── mode2_panel.py
│   │   ├── mode3_panel.py
│   │   ├── profile_panel.py
│   │   ├── record_dialog.py
│   │   ├── waveform_widget.py
│   │   └── workers.py
│   ├── profiles/
│   │   └── voice_profile.py
│   └── utils/
│       ├── benchmark.py
│       ├── config.py
│       ├── gpu.py
│       └── logging_setup.py
├── tests/
├── docs/
├── voices/                    # personal voice profiles — ignored
├── output/                    # generated audio — ignored
├── cache/                     # cached prompts/embeddings — ignored
├── logs/                      # local logs — ignored
└── models/                    # downloaded models — ignored
```

## Engine Design

The project intentionally uses separate engines for separate tasks:

- **Qwen3-TTS** — primary text-to-cloned-voice backend;
- **XTTS v2** — optional/fallback TTS backend in the project architecture;
- **Seed-VC** — voice-conversion backend;
- **faster-whisper** — local ASR.

The engine factory and model manager isolate model-specific code from the GUI so individual backends can be replaced or extended later.

## Installation

### Requirements

- Windows 11 recommended;
- Python 3.11 or 3.12;
- NVIDIA GPU with CUDA recommended for TTS/VC;
- approximately 15 GB free disk space depending on installed models and environments.

Run:

```text
install.bat
```

Then launch:

```text
start.bat
```

See [INSTALL.md](INSTALL.md) for the full installation procedure, including the separate Seed-VC environment when required.

## Command-line TTS

A proof-of-concept command-line workflow is included:

```text
.venv\Scripts\python.exe cli.py \
  --ref reference.wav \
  --ref-text "Reference transcript" \
  --text "Hello, this is a test." \
  --language en \
  --out output.wav
```

## Privacy and Repository Hygiene

This public repository contains **source code and documentation only**. It does not include personal voice recordings or generated user data.

The `.gitignore` explicitly excludes:

- `voices/*` — voice profiles and reference recordings;
- `output/*` — generated audio;
- `cache/*` — cached voice prompts / embeddings;
- `logs/*` — runtime logs;
- `models/*` — downloaded model weights;
- `.venv/` and Seed-VC virtual environments;
- Python caches and editor/OS files.

The repository keeps only `.gitkeep` placeholders for these runtime directories.

## Documentation

- [Installation guide](INSTALL.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Model research](docs/MODEL_RESEARCH.md)
- [Benchmark notes](docs/BENCHMARK.md)
- [Troubleshooting](TROUBLESHOOTING.md)
- [Realtime translator plan](docs/REALTIME_TRANSLATOR_PLAN.md)
- [Implementation report](FINAL_REPORT.md)
- [Changelog](CHANGELOG.md)

## Testing and Benchmarks

The project contains environment, conversion and benchmark utilities under `tests/`, including:

- environment validation;
- voice-conversion testing;
- benchmark execution;
- A/B audio comparison helpers.

No personal voice profile is hard-coded in the published tests; examples use generic placeholder profile names.

## Third-party Models and Licenses

The project integrates third-party model backends. Their own licenses continue to apply to those components and model weights.

At the time of this project documentation:

- Qwen3-TTS — Apache-2.0;
- Seed-VC — GPL-3.0;
- faster-whisper — MIT.

Model files are not redistributed in this repository.

## Security Note

The optional API is configured for `127.0.0.1` by default. If you change the binding to a LAN or public interface, add appropriate authentication and network controls before exposing it to other machines.

## Project Status

This repository represents **Local Voice Studio v0.1.0**. Text-to-voice and the desktop profile workflow are the main implemented focus, while live voice conversion is explicitly marked experimental and the realtime translator remains a future-development plan.

## Responsible Use

Voice cloning and voice conversion should only be used with voices and recordings you are authorized to use. Do not use the software to impersonate people deceptively, bypass consent, or misrepresent generated speech as authentic recordings.
