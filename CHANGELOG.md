# Changelog

## 0.1.0 — 2026-09-21 (MVP)

- Исследование моделей (`docs/MODEL_RESEARCH.md`): Qwen3-TTS выбран как PRIMARY TTS
  (MODE 1), Seed-VC как PRIMARY Voice Conversion (MODE 2), XTTS-v2 как FALLBACK TTS.
- Engine abstraction layer (`src/engines/base_tts.py`, `base_vc.py`, `model_manager.py`)
  — GUI/API не завязаны на конкретный backend.
- Voice Profile система (`src/profiles/voice_profile.py`) с оценкой качества
  референса, кэшированием voice-prompt, персистентностью между запусками.
- Audio preprocessing (`src/audio/audio_preprocessing.py`): decode/resample/
  trim silence/normalize/quality assessment, FFmpeg (системный или через
  `imageio-ffmpeg`).
- Локальный ASR (`src/audio/asr.py`, faster-whisper на CPU) для авто-транскрипции
  референсов и (в будущем) MODE 2.
- CLI proof-of-concept (`cli.py`) — подтверждён рабочий end-to-end пайплайн
  reference.wav + text → cloned voice output.wav на RTX 3060.
- PySide6 GUI (тёмная тема, русский интерфейс): Voice Profile панель, MODE 1
  (Text → Voice), MODE 2 (Audio → Voice), MODE 3 (Live, EXPERIMENTAL), live
  GPU/VRAM статус-бар, quality presets (fast/balanced/quality).
- Local API (FastAPI, 127.0.0.1): `/tts`, `/voice-convert`, `/voices`, `/status`, `/gpu`.
- Seed-VC интеграция (`src/engines/seed_vc_engine.py`) через subprocess в
  отдельном venv (`models/seed-vc/.venv-vc`) — изоляция несовместимых пинов
  зависимостей от основного окружения.
- Benchmark tooling (`tests/run_benchmark.py`, `logs/benchmark.jsonl`,
  `docs/BENCHMARK.md`) и A/B сравнение движков (`tests/ab_compare.py`).
- install.bat / start.bat, `tests/test_environment.py` аппаратный тест.
- Документация: README, INSTALL, ARCHITECTURE, MODEL_RESEARCH, BENCHMARK,
  TROUBLESHOOTING, REALTIME_TRANSLATOR_PLAN, FINAL_REPORT.

### Исправлено во время тестирования

- Профиль не выбирался автоматически при перезапуске GUI (Qt не эмитит
  `currentTextChanged`, когда целевой текст совпадает с уже выставленным) —
  ломало персистентность профиля между запусками. См. FINAL_REPORT.md §9.
- Кэш voice-prompt не различал размер модели Qwen3-TTS (0.6B/1.7B) —
  добавлен `cache_key`.
- MP3 export не находил FFmpeg без системной установки — `pydub` теперь
  явно настраивается на найденный движок (`configure_pydub_ffmpeg`).
- Убран непроверенный `--inference-cfg-rate` хак в Seed-VC-обёртке; чекбоксы
  Preserve timing/pauses/prosody/emotion в MODE 2 сделаны информационными,
  а не фальшивыми переключателями без эффекта.

### Добавлено по запросу пользователя (после MVP)

- Распознанный текст референса теперь автоматически появляется в поле
  генерации (MODE 1) сразу после загрузки/записи референса — можно сразу
  нажать GENERATE и получить пару "оригинал / клон" для сравнения. Кнопки
  "▶ Прослушать референс" и "Использовать текст референса" в панели профиля
  для повторного использования старых референсов.
- Автоматическая подгонка громкости (RMS) сгенерированной речи под референс
  профиля (`match_loudness_to_reference`, MODE 1, GUI и API).
- `src/audio/analysis.py` + `tests/compare_audio.py` + `POST /analyze` —
  объективное сравнение двух аудио (pitch, темп речи, паузы, громкость) без
  необходимости пересылать файлы — работает напрямую с файлами на диске.
