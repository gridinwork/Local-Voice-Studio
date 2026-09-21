# Архитектура — Local Voice Studio

## 1. Слои системы

```
┌─────────────────────────────────────────────────────────┐
│  GUI (PySide6)         │  Local API (FastAPI, 127.0.0.1) │
└───────────┬─────────────────────────┬────────────────────┘
            │                         │
            ▼                         ▼
┌─────────────────────────────────────────────────────────┐
│                    Engine Abstraction                    │
│   BaseTTSEngine (src/engines/base_tts.py)                │
│   BaseVCEngine  (src/engines/base_vc.py)                 │
│   ModelManager  (src/engines/model_manager.py)           │
└───────────┬─────────────────────────┬────────────────────┘
            │                         │
            ▼                         ▼
┌────────────────────────┐  ┌──────────────────────────────┐
│ QwenTTSEngine (primary) │  │ SeedVCEngine (primary)       │
│ XTTSEngine (fallback)   │  │ (subprocess into models/     │
│                         │  │  seed-vc, own .venv-vc)      │
└────────────────────────┘  └──────────────────────────────┘
            │                         │
            ▼                         ▼
┌─────────────────────────────────────────────────────────┐
│  VoiceProfile (src/profiles/voice_profile.py)             │
│  voices/<Name>/{profile.json, reference/, processed/,     │
│                 cache/<engine>_speaker_prompt.*}           │
└─────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────┐
│  audio_preprocessing.py / asr.py (faster-whisper, CPU)    │
└─────────────────────────────────────────────────────────┘
```

GUI and API never import a concrete engine class directly — only
`src/engines/engine_factory.py`, which reads `config/config.json` to decide
which backend/model-size to instantiate, and `ModelManager`, which makes
sure only one heavy model (TTS *or* VC) is resident in VRAM at a time.

## 2. Почему разные backend'ы для MODE 1 и MODE 2

TTS (text→voice) и VC (audio→voice, полное сохранение prosody/timing) —
разные инженерные задачи (см. `docs/MODEL_RESEARCH.md`). Ни одна открытая
модель на сентябрь 2026 не решает обе одинаково хорошо, поэтому:

- **MODE 1** использует Qwen3-TTS (LM-based zero-shot cloning, есть встроенный
  кэш voice-prompt, streaming).
- **MODE 2** использует Seed-VC (diffusion-based speech-to-speech conversion,
  явно спроектирован для сохранения content/timing/prosody исходной записи
  и замены только voice identity).

Seed-VC живёт в отдельном venv (`models/seed-vc/.venv-vc`) и вызывается как
subprocess, потому что его зависимости (Python 3.10, конкретные версии
torch) не гарантированно совместимы с зависимостями `qwen-tts` в одном
окружении. `SeedVCEngine` (src/engines/seed_vc_engine.py) прячет это за
тем же `BaseVCEngine` интерфейсом — вызывающий код не знает о subprocess.

## 3. Voice Profile — единственный источник данных о голосе пользователя

`voices/<Name>/`:
- `reference/` — оригиналы, как загрузил пользователь (никогда не изменяются).
- `processed/` — очищенные копии (trim silence, RMS-нормализация; без
  агрессивного шумоподавления по умолчанию — оно может разрушить speaker identity).
- `cache/<engine>_speaker_prompt.*` — сериализованный voice-prompt/conditioning
  latents конкретного TTS-движка. Инвалидируется при добавлении/удалении
  референса или Rebuild Profile. Вычисляется один раз (`build_voice_prompt`),
  переиспользуется при каждой генерации (`generate`/`generate_stream`).
- `profile.json` — метаданные, список референсов, их качество и транскрипт.

## 4. VRAM management

`ModelManager.get_tts()` / `get_vc()` выгружает противоположный тип движка
перед загрузкой нужного — на 12 GB VRAM одновременное присутствие TTS и VC
моделей избыточно. Explicit `unload_model()` на каждом движке + `torch.cuda.empty_cache()`.
GUI показывает live VRAM (см. `src/utils/gpu.py`) в статус-баре.

## 5. Почему GUI не блокируется

Все операции с моделью (load/generate/convert) выполняются в QThread worker'ах
(`src/gui/workers.py`). GUI поток только отправляет задачи и получает Qt-сигналы
с результатом/прогрессом/ошибкой.

## 6. Готовность к realtime-переводчику

`generate_stream()` в `BaseTTSEngine` и `convert_stream()` в `BaseVCEngine`
уже часть интерфейса (реализованы либо через нативный streaming API движка,
либо через fallback "один chunk = весь буфер"). Это единственная точка,
которую должен дёргать будущий realtime pipeline — см.
`docs/REALTIME_TRANSLATOR_PLAN.md`.
