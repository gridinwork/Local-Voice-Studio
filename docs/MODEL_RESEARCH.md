# Model Research — Local Voice Studio

Дата исследования: 2026-09-21
Оборудование: NVIDIA RTX 3060 12 GB VRAM, Windows 11, Python 3.12.2, CUDA driver поддерживает до 13.x (nvcc 11.8 установлен локально, но не критично — PyTorch поставляется с собственным CUDA runtime).

Источники: официальные репозитории GitHub/Hugging Face моделей (см. ссылки в каждом разделе), состояние на сентябрь 2026.

## 1. Сводная таблица — TTS / Zero-shot Voice Cloning (MODE 1)

| Model | Task | License | VRAM (RTX-class) | Russian | English | Zero-shot | Voice cloning | Voice conversion | Prosody control | Streaming | Windows | Expected latency | Advantages | Disadvantages |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Qwen3-TTS-12Hz (0.6B/1.7B-Base)** | TTS | Apache-2.0 | 0.6B ≈ 2 GB; 1.7B ≈ 4-6 GB (fp16/bf16) | Да (нативно, 1 из 10 языков) | Да | Да | Да (ref audio + ref text) | Нет | Ограниченно (через emotion/voice-design controls) | Да, TTFA ~97 мс | Не документировано официально, но чистый PyTorch/HF — совместимо | 0.6B: RTF < 1 на RTX 3090 (быстрее на факто); 1.7B: RTF ~3x без FlashAttention (сообщения пользователей о низкой загрузке GPU) | Официальная модель от Alibaba Qwen team, свежий релиз (22.01.2026), нативная поддержка кэша voice-prompt (`create_voice_clone_prompt`), Apache-2.0 (свободная лицензия), явная поддержка RU | 1.7B модель существенно медленнее без FlashAttention 2, которая проблематично собирается под Windows; VRAM/Windows официально не задокументированы — требуется собственная проверка |
| **XTTS-v2 (через coqui-tts, форк idiap)** | TTS | CPML (некоммерч. свободная) | ≈ 4-6 GB | Да (есть проблемы с ударениями) | Да | Да | Да | Нет | Слабый (эмоции через референс) | Нет (chunked, не true streaming) | Да, зрелая поддержка Windows | RTF ~0.3-0.5 на RTX 3060 (типично для сообщества) | Очень зрелый проект, огромное community, простой Python API, стабильно работает на Windows, хорошо документирован | Оригинальная компания Coqui закрылась (01.2024), поддерживается community-форком; в русском нет контроля ударений; лицензия CPML ограничивает коммерческое использование |
| **CosyVoice2 / CosyVoice3 (FunAudioLLM)** | TTS | Apache-2.0 (репозиторий) | 0.5B модель ≈ 6-8 GB (CosyVoice3 ≈ 8-10 GB) | Да (в списке 9 языков) | Да | Да | Да | Частично (в составе pipeline) | Хороший (LM-based zero-shot emotion/speaker control) | Да (частично) | Не оптимизирован, есть сообщения о сложностях сборки под Windows (зависимости на Linux-специфичные пакеты) | Не измерялось локально | По бенчмаркам MOS 3.81 — лучшее качество среди сравнённых открытых моделей | Установка сложнее на Windows (зависимости, компиляция), выше VRAM |
| **Fish Speech / OpenAudio S1** | TTS | Веса: CC-BY-NC-SA-4.0 (некоммерческая!); код: Apache-2.0 | ≈ 4 GB | Не в основном списке (13 языков, RU не подтверждён явно) | Да | Да | Да | Нет | Хорошо (50+ emotion/tone маркеров) | Да | Поддерживается | Быстрая генерация (<1 мин для клонирования) | Гибкий emotion control, низкий VRAM | Лицензия весов некоммерческая — не подходит, если в будущем нужна коммерциализация; русский язык не гарантирован |

## 2. Сводная таблица — Voice Conversion / Prosody Transfer (MODE 2)

| Model | Task | License | VRAM | Timing preservation | Prosody/emotion transfer | Real-time | Windows | Expected latency | Advantages | Disadvantages |
|---|---|---|---|---|---|---|---|---|---|---|
| **Seed-VC (Plachtaa/seed-vc)** | Voice Conversion (speech-to-speech, zero-shot) | GPL-3.0 | ≈ 4-6 GB (V2 с AR-компонентом больше) | Да, конверсия 1:1 по контенту source | V2: accent & emotion conversion через AR-компонент; V1: pitch conditioning (f0-condition) | Да, официально протестировано на RTX 3060 Laptop: ~150 мс/chunk, ~430 мс общая задержка | Да, официально поддерживается (Windows/macOS/Linux), опционально `triton-windows` | ~430 мс (real-time режим), для оффлайн конвертации быстрее | Единственный из рассмотренных VC-проектов с явным бенчмарком на RTX 3060, реальный real-time режим, активная поддержка | GPL-3.0 (copyleft — учитывать при дистрибуции), не TTS — не заменяет MODE 1 |
| **OpenVoice / OpenVoice V2** | Voice cloning + tone color conversion | MIT | ≈ 2-4 GB | Частично (base speaker TTS определяет тайминг) | Ограниченно (tone color, не полный prosody transfer) | Нет | Да | Не измерялось | MIT-лицензия, лёгкий | Слабее в сохранении оригинального timing/emotion исходной речи по сравнению с Seed-VC, менее активная поддержка в 2026 |
| **RVC-подобные решения (Retrieval-based VC)** | Singing/speech voice conversion | MIT (большинство форков) | ≈ 2-4 GB | Хорошо (frame-level conversion, timing 1:1 по построению) | Pitch сохраняется явно (F0), эмоция — ограниченно | Да (некоторые форки) | Да | Низкая (RTF << 1) | Отличное сохранение timing/pitch по архитектуре (frame-to-frame), много готовых Windows GUI (RVC WebUI) | Изначально заточен под пение, для разговорной речи с полным prosody/emotion transfer уступает Seed-VC v2; требует отдельного индекса на голос |

## 3. ASR для MODE 2 (нужна транскрипция source audio)

| Model | License | Device | Russian | English | RTF (CPU) | Примечание |
|---|---|---|---|---|---|---|
| **faster-whisper (small/medium)** | MIT | CPU или GPU | Да | Да | < 1 на современном CPU (small, int8) | Основан на CTranslate2, не занимает VRAM если запущен на CPU — освобождает RTX 3060 для TTS/VC |

## 4. Итоговый выбор

**PRIMARY TTS ENGINE (MODE 1): Qwen3-TTS-12Hz-1.7B-Base**, с возможностью переключения на **0.6B-Base** как FAST-preset.
Обоснование: официальная, свежая (2026), Apache-2.0, нативная русская локализация, встроенное кэширование voice-prompt (что прямо требуется в ТЗ п.11), streaming API "из коробки". Риск медленной работы 1.7B без FlashAttention компенсируется quality-пресетами (0.6B для FAST).

**FALLBACK TTS ENGINE: XTTS-v2 (пакет `coqui-tts`)**.
Используется, если Qwen3-TTS не устанавливается/не запускается на конкретной машине (например, проблемы с `qwen-tts` под Windows) — как проверенный резерв с огромным community и стабильной Windows-поддержкой.

**PRIMARY VOICE CONVERSION ENGINE (MODE 2): Seed-VC (Plachtaa/seed-vc), модель v2**.
Обоснование: единственный из рассмотренных VC-проектов с прямым официальным бенчмарком на RTX 3060, реальная поддержка timing/prosody/emotion transfer через AR-компонент, официальная поддержка Windows.

**ASR (для транскрипции source audio в MODE 2): faster-whisper, модель `small`, CPU, int8**.
Не занимает VRAM, оставляя всю RTX 3060 для VC/TTS модели.

## 5. Риски и что проверить на этапе PoC

1. Установится ли `qwen-tts` и его зависимости (torch/transformers) в Windows-venv без ошибок сборки.
2. Реальная скорость 1.7B-Base на RTX 3060 (слабее 3090 из отчётов) — если RTF > 2-3, использовать 0.6B как основной, либо переключиться на XTTS-v2.
3. Реальное качество голоса на русском/английском референсе пользователя — оценивается только на реальных сэмплах, не по бенчмаркам сторонних авторов.
4. Совместимость Seed-VC c той же venv (может требовать отдельного окружения из-за конфликтов зависимостей — в таком случае использовать отдельный `.venv-vc` или subprocess-изоляцию через model manager).

Эта таблица будет уточнена по итогам PoC (Phase 3) в [BENCHMARK.md](BENCHMARK.md).
