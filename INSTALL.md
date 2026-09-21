# Установка — Local Voice Studio

## 1. Базовая установка (MODE 1 — Text → Voice, GUI, API)

```bash
install.bat
```

Шаги, которые выполняет скрипт:
1. Проверяет наличие Python в PATH.
2. Создаёт `.venv` (если ещё не существует).
3. Обновляет pip.
4. Ставит PyTorch с CUDA 12.4 (`torch`, `torchaudio`), с откатом на CPU-версию,
   если сборка с CUDA не подошла (см. `nvidia-smi` для проверки версии драйвера).
5. Ставит остальные зависимости из `requirements.txt` (qwen-tts, faster-whisper,
   PySide6, FastAPI, аудио-библиотеки).
6. Проверяет FFmpeg (системный или резервный из `imageio-ffmpeg`).
7. Создаёт каталоги `models/`, `voices/`, `output/`, `cache/`, `logs/`.
8. Запускает `tests/test_environment.py` — аппаратный тест (Python, CUDA, GPU,
   VRAM, FFmpeg, аудио-устройства, наличие qwen-tts).

Модели Qwen3-TTS (0.6B/1.7B) скачиваются автоматически с Hugging Face **при
первом запуске генерации**, не во время install.bat — это происходит один раз
и кэшируется (обычно в `%USERPROFILE%\.cache\huggingface`, если не переопределено
переменной `HF_HOME`).

## 2. Voice Conversion setup (MODE 2 — Audio → Voice, Seed-VC)

Seed-VC ставится в **отдельное окружение**, потому что его зависимости
(Python 3.10-совместимые пины: `torch==2.4.0`, `numpy==1.26.4`, `transformers==4.46.3`)
не гарантированно совместимы с зависимостями `qwen-tts` в основном `.venv`
(см. `docs/ARCHITECTURE.md`, раздел 2).

```bash
cd models
git clone --depth 1 https://github.com/Plachtaa/seed-vc.git
cd seed-vc
python -m venv .venv-vc
.venv-vc\Scripts\python.exe -m pip install --upgrade pip
.venv-vc\Scripts\python.exe -m pip install torch==2.4.0 torchvision==0.19.0 torchaudio==2.4.0 --index-url https://download.pytorch.org/whl/cu124
.venv-vc\Scripts\python.exe -m pip install -r requirements_minimal.txt
```

Две особенности, обнаруженные при реальной установке на этой машине (Windows,
без Visual Studio Build Tools):

1. Оригинальный `requirements.txt` из репозитория Seed-VC содержит битые строки
   с nightly-сборками PyTorch вперемешку с пинами стабильной версии — они не
   нужны (мы уже поставили `torch==2.4.0` явно строкой выше).
2. Полный `requirements.txt` тянет `funasr`/`modelscope`, которые транзитивно
   требуют `webrtcvad` — а `webrtcvad` не публикует Windows-колёса и требует
   компиляции через MSVC ("Unable to find a compatible Visual Studio
   installation"). Мы проверили: **`inference.py` (наш единственный путь
   вызова MODE 2) не импортирует ни `funasr`, ни `modelscope`, ни `webrtcvad`
   напрямую** — это лишние зависимости для train.py/eval.py/gradio-демо, не
   для CLI-инференса. Поэтому используется `requirements_minimal.txt`
   (создан нами в этом репозитории) — тот же набор пакетов, но без
   funasr/modelscope/webrtcvad/gradio/jiwer/resemblyzer/FreeSimpleGUI/hydra-core.
   Если вам всё же нужны train.py/real-time-gui.py — поставьте Visual Studio
   Build Tools (компонент "Desktop development with C++") и используйте
   полный `requirements.txt`.

Модель Seed-VC скачивается автоматически при первом запуске `inference.py`
(с Hugging Face). После этого MODE 2 в GUI/API становится доступен —
`SeedVCEngine` (src/engines/seed_vc_engine.py) обнаруживает `models/seed-vc/.venv-vc`
и вызывает `inference.py` как subprocess.

Лицензия Seed-VC — **GPL-3.0** (в отличие от Apache-2.0 у Qwen3-TTS), учитывайте
это при дистрибуции сборки, включающей код Seed-VC.

## 3. Проверка

```bash
start.bat
```

В статус-баре должно появиться `GPU: NVIDIA GeForce RTX 3060 | VRAM: ... | CUDA 12.4`.
Если написано "GPU: недоступна" — см. [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## 4. Ручной CLI-тест (без GUI)

```bash
.venv\Scripts\python.exe cli.py --ref reference.wav --ref-text "Текст референса" --text "Текст для синтеза" --language ru --out output.wav
```
