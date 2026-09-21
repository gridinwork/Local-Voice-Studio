# План подключения к будущему Realtime RU↔EN переводчику

Этот документ описывает, как Voice Engine из Local Voice Studio будет
использован как последнее звено realtime-переводчика, без переписывания ядра.

## Целевой pipeline

```
RU микрофон
   │
   ▼
VAD (webrtcvad / silero-vad) — определяет границы фраз
   │
   ▼
Streaming ASR (faster-whisper, RU) — уже есть в src/audio/asr.py
   │
   ▼
Russian text
   │
   ▼
RU → EN перевод (отдельный модуль, не часть Voice Engine — например,
   локальная LLM или NLLB/M2M100)
   │
   ▼
English text
   │
   ▼
Voice Engine.generate_stream(text, language="en", cache_path=<профиль пользователя>)
   │
   ▼
English audio chunks (тем же голосом, что и у пользователя)
   │
   ▼
Динамик / виртуальный аудио-кабель (например, VB-Cable) для звонков
```

И симметрично для EN → RU.

## Почему текущая архитектура уже готова

1. **`BaseTTSEngine.generate_stream()`** (src/engines/base_tts.py) уже
   определён как генератор audio chunks, не привязанный к GUI. Realtime
   pipeline просто вызывает его напрямую или через Local API.
2. **Voice Profile + cache** (src/profiles/voice_profile.py) уже разделяет
   "построить голос один раз" (`build_voice_prompt`) и "сгенерировать текст"
   (`generate`) — critical для low-latency: голосовой prompt пользователя
   строится один раз при настройке, а не на каждую фразу.
3. **ASR уже локальный и не занимает VRAM** (faster-whisper на CPU,
   src/audio/asr.py) — освобождает всю RTX 3060 под TTS-модель, что и
   потребуется в реальном времени.
4. **ModelManager** гарантирует, что в момент realtime-перевода в VRAM
   резидентна только TTS-модель (VC выгружается) — важно для стабильной
   задержки.

## Что нужно добавить (не в текущем MVP)

1. **VAD-модуль** (`src/audio/vad.py`) — определение границ речи из
   микрофонного потока, чтобы не гонять ASR на тишине.
2. **Streaming ASR loop** — обёртка над faster-whisper с потоковым буфером.
3. **Модуль перевода** (`src/translation/`) — отдельный слой, не связанный
   с Voice Engine. Наиболее вероятный кандидат — локальная LLM или
   специализированная MT-модель (NLLB-200, M2M100).
4. **Live GUI режим (MODE 3, сейчас EXPERIMENTAL)** — уже присутствует как
   push-to-talk прототип, будет расширен до полного pipeline выше.
5. **Аудио-роутинг** — направление синтезированной речи в виртуальное
   аудио-устройство (VB-Cable/VoiceMeeter), конфигурируется через
   `audio_output_device` в config.json.

## Важно

Ни TTS, ни VC движок НЕ нужно переписывать для realtime-переводчика —
только добавить слои ASR-streaming/VAD/перевода поверх существующего
`generate_stream()`. Это было заложено в интерфейс с самого начала
(см. `docs/ARCHITECTURE.md`, раздел 6).
