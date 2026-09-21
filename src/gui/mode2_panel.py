"""MODE 2: AUDIO -> CLONED VOICE (voice conversion) panel."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QVBoxLayout, QWidget,
)

from src.engines.model_manager import get_model_manager
from src.gui.audio_player import AudioPlayerWidget
from src.gui.workers import Worker
from src.profiles.voice_profile import VoiceProfile
from src.utils.benchmark import log_benchmark, make_record
from src.utils.config import get_config
from src.utils.logging_setup import get_logger

log = get_logger("mode2_panel")


class Mode2Panel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_profile: VoiceProfile | None = None
        self._source_path: str | None = None
        self._worker: Worker | None = None

        box = QGroupBox("AUDIO → CLONED VOICE (voice conversion)")
        layout = QVBoxLayout(box)

        self.source_label = QLabel("Source audio: не выбрано")
        layout.addWidget(self.source_label)
        self.btn_load_source = QPushButton("Load audio")
        layout.addWidget(self.btn_load_source)

        self.source_player = AudioPlayerWidget()
        layout.addWidget(self.source_player)

        self.chk_timing = QCheckBox("Preserve timing")
        self.chk_pauses = QCheckBox("Preserve pauses")
        self.chk_prosody = QCheckBox("Preserve prosody")
        self.chk_emotion = QCheckBox("Preserve emotion")
        for c in (self.chk_timing, self.chk_pauses, self.chk_prosody, self.chk_emotion):
            c.setChecked(True)
            c.setEnabled(False)
            layout.addWidget(c)
        preserve_note = QLabel(
            "Seed-VC сохраняет эти аспекты по умолчанию — независимого переключателя "
            "для каждого из них в текущей версии нет (см. docs/BENCHMARK.md)."
        )
        preserve_note.setWordWrap(True)
        preserve_note.setStyleSheet("color: #999999; font-size: 11px;")
        layout.addWidget(preserve_note)

        self.btn_convert = QPushButton("CONVERT")
        self.btn_convert.setStyleSheet("font-weight: bold; padding: 8px;")
        layout.addWidget(self.btn_convert)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        layout.addWidget(QLabel("OUTPUT:"))
        self.output_player = AudioPlayerWidget()
        layout.addWidget(self.output_player)

        save_row = QHBoxLayout()
        self.btn_save_wav = QPushButton("Save WAV")
        self.btn_save_mp3 = QPushButton("Save MP3")
        save_row.addWidget(self.btn_save_wav)
        save_row.addWidget(self.btn_save_mp3)
        layout.addLayout(save_row)

        self.stats_label = QLabel("Generation time: — | Source duration: — | Output duration: — | VRAM: —")
        layout.addWidget(self.stats_label)

        note = QLabel(
            "EXPERIMENTAL: сохранение интонации/эмоции зависит от возможностей Seed-VC "
            "(см. docs/MODEL_RESEARCH.md) — идеальное сохранение не гарантируется."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #ffb300;")
        layout.addWidget(note)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(box)

        self.btn_load_source.clicked.connect(self._load_source)
        self.btn_convert.clicked.connect(self._on_convert)
        self.btn_save_wav.clicked.connect(lambda: self._save_output("wav"))
        self.btn_save_mp3.clicked.connect(lambda: self._save_output("mp3"))

        self._last_output_path: Path | None = None
        self._set_enabled(True)

    def set_profile(self, profile: VoiceProfile | None):
        self.current_profile = profile

    def _set_enabled(self, enabled: bool):
        self.btn_convert.setEnabled(enabled)

    def _load_source(self):
        path, _ = QFileDialog.getOpenFileName(self, "Source audio", "", "Аудио (*.mp3 *.wav *.flac *.m4a)")
        if not path:
            return
        self._source_path = path
        self.source_label.setText(f"Source audio: {Path(path).name}")
        self.source_player.load_file(path)

    def _on_convert(self):
        if not self.current_profile:
            QMessageBox.information(self, "Нет профиля", "Сначала выберите Voice Profile.")
            return
        if not self._source_path:
            QMessageBox.information(self, "Нет исходного аудио", "Сначала загрузите source audio.")
            return
        target_ref = self.current_profile.best_reference_processed_path()
        if target_ref is None:
            QMessageBox.warning(self, "Нет референса", "В профиле нет обработанных референсов.")
            return

        cfg = get_config()
        preset = cfg.get("active_preset", "balanced")
        diffusion_steps = cfg.get("quality_presets", {}).get(preset, {}).get("vc_diffusion_steps", 25)

        self._set_enabled(False)
        self.status_label.setText("Конвертация...")

        source_path = self._source_path
        preserve_timing = self.chk_timing.isChecked()
        preserve_prosody = self.chk_prosody.isChecked()

        def task(progress_cb=None):
            from src.engines.seed_vc_engine import SeedVCEngine
            manager = get_model_manager()
            engine = manager.get_vc("seed_vc", SeedVCEngine)
            result = engine.convert(
                source_path, str(target_ref),
                preserve_timing=preserve_timing, preserve_prosody=preserve_prosody,
                diffusion_steps=diffusion_steps,
            )
            return engine, result

        self._worker = Worker(task)
        self._worker.signals.finished.connect(self._on_convert_done)
        self._worker.signals.error.connect(self._on_convert_error)
        self._worker.start()

    def _on_convert_done(self, payload):
        engine, result = payload
        self._set_enabled(True)
        self.status_label.setText("Готово.")

        cfg = get_config()
        out_dir = cfg.path_for("output_dir")
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        out_path = out_dir / f"{stamp}_{self.current_profile.name}_vc.wav"

        import soundfile as sf
        sf.write(str(out_path), result.audio, result.sample_rate)
        self.output_player.load_file(out_path, audio_array=result.audio, sample_rate=result.sample_rate)
        self._last_output_path = out_path

        self.stats_label.setText(
            f"Generation time: {result.generation_time_sec:.2f}s | "
            f"Source duration: {result.source_duration_sec:.2f}s | "
            f"Output duration: {result.output_duration_sec:.2f}s | VRAM: {result.peak_vram_mb:.0f} MB"
        )
        log_benchmark(make_record(
            op="vc_convert", engine=engine.name, quality_preset=cfg.get("active_preset"),
            audio_duration_sec=result.output_duration_sec, generation_time_sec=result.generation_time_sec,
            peak_vram_mb=result.peak_vram_mb,
        ))

    def _on_convert_error(self, error_text: str):
        self._set_enabled(True)
        self.status_label.setText("Ошибка конвертации.")
        log.error(error_text)
        QMessageBox.critical(self, "Ошибка Voice Conversion", error_text.splitlines()[-1] if error_text else "Неизвестная ошибка")

    def _save_output(self, fmt: str):
        if not self._last_output_path:
            QMessageBox.information(self, "Нет результата", "Сначала выполните конвертацию.")
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
