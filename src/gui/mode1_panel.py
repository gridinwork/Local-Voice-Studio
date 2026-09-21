"""MODE 1: TEXT -> CLONED VOICE panel."""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel, QMessageBox,
    QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)

from src.audio.asr import transcribe as asr_transcribe
from src.engines.engine_factory import create_tts_engine
from src.gui.audio_player import AudioPlayerWidget
from src.gui.workers import Worker
from src.profiles.voice_profile import VoiceProfile
from src.utils.benchmark import log_benchmark, make_record
from src.utils.config import get_config
from src.utils.logging_setup import get_logger

log = get_logger("mode1_panel")

TEST_PHRASES = {
    "ru": "Привет. Это тест моего локального синтезатора речи.",
    "en": "Hello. This is a test of my local voice synthesis system.",
}


class Mode1Panel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_profile: VoiceProfile | None = None
        self._worker: Worker | None = None

        box = QGroupBox("TEXT → CLONED VOICE")
        layout = QVBoxLayout(box)

        layout.addWidget(QLabel("Текст:"))
        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("Введите текст для озвучивания...")
        layout.addWidget(self.text_edit)

        row = QHBoxLayout()
        row.addWidget(QLabel("Язык:"))
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("Русский", "ru")
        self.lang_combo.addItem("English", "en")
        self.lang_combo.addItem("Auto", "auto")
        row.addWidget(self.lang_combo)

        self.btn_test_phrase = QPushButton("Тестовая фраза")
        row.addWidget(self.btn_test_phrase)
        layout.addLayout(row)

        gen_row = QHBoxLayout()
        self.btn_generate = QPushButton("GENERATE")
        self.btn_generate.setStyleSheet("font-weight: bold; padding: 8px;")
        self.btn_test_voice = QPushButton("TEST VOICE")
        gen_row.addWidget(self.btn_generate)
        gen_row.addWidget(self.btn_test_voice)
        layout.addLayout(gen_row)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        layout.addWidget(QLabel("OUTPUT:"))
        self.player = AudioPlayerWidget()
        layout.addWidget(self.player)

        save_row = QHBoxLayout()
        self.btn_save_wav = QPushButton("Save WAV")
        self.btn_save_mp3 = QPushButton("Save MP3")
        save_row.addWidget(self.btn_save_wav)
        save_row.addWidget(self.btn_save_mp3)
        layout.addLayout(save_row)

        self.stats_label = QLabel("Generation time: — | Duration: — | RTF: — | VRAM: —")
        layout.addWidget(self.stats_label)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(box)

        self.btn_generate.clicked.connect(self._on_generate)
        self.btn_test_voice.clicked.connect(self._on_test_voice)
        self.btn_test_phrase.clicked.connect(self._fill_test_phrase)
        self.btn_save_wav.clicked.connect(lambda: self._save_output("wav"))
        self.btn_save_mp3.clicked.connect(lambda: self._save_output("mp3"))

        self._last_result = None
        self._set_generation_enabled(True)

    def set_profile(self, profile: VoiceProfile | None):
        self.current_profile = profile

    def set_text(self, text: str):
        self.text_edit.setPlainText(text)

    def _fill_test_phrase(self):
        lang = self.lang_combo.currentData()
        phrase = TEST_PHRASES.get(lang, TEST_PHRASES["en"])
        self.text_edit.setPlainText(phrase)

    def _on_test_voice(self):
        self._fill_test_phrase()
        self._on_generate()

    def _set_generation_enabled(self, enabled: bool):
        self.btn_generate.setEnabled(enabled)
        self.btn_test_voice.setEnabled(enabled)

    def _ensure_voice_prompt_cached(self, engine, profile: VoiceProfile) -> str:
        cache_path = str(profile.cache_file(engine.cache_key))
        if not Path(cache_path).exists():
            ref_path = profile.best_reference_processed_path()
            if ref_path is None:
                raise RuntimeError("В профиле нет обработанных референсов.")
            entry = next((r for r in profile.references
                          if (profile.processed_dir / f"{Path(r.filename).stem}_clean.wav") == ref_path), None)
            ref_text = entry.transcript if entry and entry.transcript else asr_transcribe(ref_path).text
            engine.build_voice_prompt(str(ref_path), ref_text, cache_path)
        return cache_path

    def _on_generate(self):
        if not self.current_profile:
            QMessageBox.information(self, "Нет профиля", "Сначала создайте или выберите Voice Profile.")
            return
        text = self.text_edit.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "Пустой текст", "Введите текст для озвучивания.")
            return

        language = self.lang_combo.currentData()
        profile = self.current_profile
        cfg = get_config()
        preset = cfg.get("active_preset", "balanced")

        self._set_generation_enabled(False)
        self.status_label.setText("Генерация... (модель может загружаться в первый раз)")

        def task(progress_cb=None):
            engine = create_tts_engine()
            cache_path = self._ensure_voice_prompt_cached(engine, profile)
            t0 = time.time()
            result = engine.generate(text, language, cache_path, quality_preset=preset)
            total_time = time.time() - t0

            ref_path = profile.best_reference_processed_path()
            if ref_path is not None:
                from src.audio.audio_preprocessing import match_loudness_to_reference
                result.audio = match_loudness_to_reference(result.audio, ref_path)

            return engine, result, total_time

        self._worker = Worker(task)
        self._worker.signals.finished.connect(self._on_generate_done)
        self._worker.signals.error.connect(self._on_generate_error)
        self._worker.start()

    def _on_generate_done(self, payload):
        engine, result, total_time = payload
        self._set_generation_enabled(True)
        self.status_label.setText("Готово.")
        self._last_result = result

        cfg = get_config()
        out_dir = cfg.path_for("output_dir")
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        lang = self.lang_combo.currentData()
        out_path = out_dir / f"{stamp}_{self.current_profile.name}_{lang}.wav"

        import soundfile as sf
        sf.write(str(out_path), result.audio, result.sample_rate)
        self.player.load_file(out_path, audio_array=result.audio, sample_rate=result.sample_rate)

        duration = len(result.audio) / result.sample_rate
        rtf = result.generation_time_sec / duration if duration > 0 else float("nan")
        self.stats_label.setText(
            f"Generation time: {result.generation_time_sec:.2f}s | Duration: {duration:.2f}s | "
            f"RTF: {rtf:.2f} | VRAM: {result.peak_vram_mb:.0f} MB"
        )
        log_benchmark(make_record(
            op="tts_generate", engine=engine.name, quality_preset=cfg.get("active_preset"),
            language=lang, text_len=len(self.text_edit.toPlainText()),
            audio_duration_sec=duration, generation_time_sec=result.generation_time_sec,
            rtf=rtf, peak_vram_mb=result.peak_vram_mb,
        ))
        self._last_output_path = out_path

    def _on_generate_error(self, error_text: str):
        self._set_generation_enabled(True)
        self.status_label.setText("Ошибка генерации.")
        log.error(error_text)
        QMessageBox.critical(self, "Ошибка генерации", error_text.splitlines()[-1] if error_text else "Неизвестная ошибка")

    def _save_output(self, fmt: str):
        if not hasattr(self, "_last_output_path") or self._last_output_path is None:
            QMessageBox.information(self, "Нет результата", "Сначала сгенерируйте аудио.")
            return
        default_name = self._last_output_path.with_suffix(f".{fmt}").name
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить как", default_name, f"*.{fmt}")
        if not path:
            return
        if fmt == "mp3":
            from pydub import AudioSegment
            seg = AudioSegment.from_wav(str(self._last_output_path))
            seg.export(path, format="mp3")
        else:
            import shutil
            shutil.copy2(self._last_output_path, path)
