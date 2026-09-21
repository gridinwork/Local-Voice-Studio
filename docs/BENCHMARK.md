# Benchmark — Local Voice Studio

GPU: NVIDIA GeForce RTX 3060. Модель: Qwen3-TTS. Precision: bfloat16. FlashAttention: не установлен (sdpa fallback).

| Model | Case | Language | Audio duration (s) | Gen time (s) | RTF | Peak VRAM (MB) |
|---|---|---|---|---|---|---|
| 0.6B | short_en | en | 2.48 | 11.05 | 4.46 | 2626 |
| 0.6B | long_en | en | 13.76 | 60.49 | 4.40 | 2818 |
| 0.6B | short_ru | ru | 2.40 | 10.32 | 4.30 | 2624 |
| 0.6B | long_ru | ru | 15.36 | 66.54 | 4.33 | 2818 |
| 1.7B | short_en | en | 2.64 | 11.96 | 4.53 | 4565 |
| 1.7B | long_en | en | 13.84 | 61.40 | 4.44 | 4752 |
| 1.7B | short_ru | ru | 1.84 | 8.46 | 4.60 | 4541 |
| 1.7B | long_ru | ru | 14.72 | 64.21 | 4.36 | 4752 |

Примечание: RTF > 1 означает, что генерация медленнее реального времени (на RTX 3060 без FlashAttention 2 это ожидаемо для обеих моделей — см. docs/MODEL_RESEARCH.md, раздел «Риски»). Для сценария MODE 1 (не realtime) это приемлемо; для будущего realtime-переводчика потребуется FlashAttention или альтернативный backend.

## Voice Conversion (MODE 2, Seed-VC)

| Case | Source duration (s) | Output duration (s) | Diffusion loop time (s) | Full call time (s)* | Diffusion steps |
|---|---|---|---|---|---|
| s2_a.wav → cloned target | 13.32 | 13.31 | ~2.0 (RTF 0.33) | — | 25 |
| s1_b.wav → cloned target (через `SeedVCEngine`) | 12.63 | 12.62 | — | 20.49 | 25 |

* "Full call time" — время нашей обёртки `SeedVCEngine.convert()`, которая
запускает `inference.py` отдельным subprocess'ом при каждом вызове. Это время
включает загрузку модели (диффузионная модель + BigVGAN vocoder + CAMPPlus +
Whisper feature extractor) заново на каждый вызов — сама диффузия
(RTF 0.33, быстрее реального времени) занимает лишь малую часть этого
времени. **Известное ограничение**: в отличие от `QwenTTSEngine` (модель
остаётся резидентной в процессе между вызовами), `SeedVCEngine` сейчас
перезагружает модель при каждой конвертации, потому что Seed-VC интегрирован
через subprocess в отдельном venv, а не как персистентный сервис. Для
повторяющихся конвертаций это расточительно; естественное улучшение —
превратить subprocess в постоянно работающий процесс (например, через
небольшой локальный сервер внутри `.venv-vc`, к которому `SeedVCEngine`
обращался бы по IPC/HTTP вместо запуска заново). Не реализовано в этом MVP
из-за ограничения по времени — см. FINAL_REPORT.md, раздел «Что осталось улучшить».

Длительность выхода в обоих случаях практически идентична источнику —
timing преобразования сохраняется корректно. VRAM во время конвертации:
~6-7 GB (диффузионная модель, vocoder BigVGAN, CAMPPlus speaker encoder и
Whisper feature extractor загружены одновременно).
