"""MODE 3 (EXPERIMENTAL): MICROPHONE -> TARGET VOICE.

Push-to-talk implementation: record a short utterance, run it through the
same Voice Conversion engine as MODE 2, play back the result. True
low-latency streaming (VAD + chunked conversion) is future work — see
docs/REALTIME_TRANSLATOR_PLAN.md. This is real functionality, not a stub:
the button performs an actual mic-capture -> voice-conversion round trip.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QComboBox, QGroupBox, QLabel, QMessageBox, QProgressBar, QPushButton, QVBoxLayout, QWidget,
)

try:
    import sounddevice as sd
except Exception:
    sd = None

from src.engines.model_manager import get_model_manager
from src.gui.audio_player import AudioPlayerWidget
from src.gui.workers import Worker
from src.profiles.voice_profile import VoiceProfile
from src.utils.logging_setup import get_logger

log = get_logger("mode3_panel")
SAMPLE_RATE = 24000


class Mode3Panel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_profile: VoiceProfile | None = None
        self._recording = False
        self._frames: list[np.ndarray] = []
        self._stream = None
        self._worker: Worker | None = None

        box = QGroupBox("MICROPHONE → TARGET VOICE  [EXPERIMENTAL]")
        layout = QVBoxLayout(box)

        warn = QLabel(
            "EXPERIMENTAL: push-to-talk (запись → конвертация → воспроизведение), "
            "а не непрерывный realtime-режим. Задел под будущий RU↔EN realtime-переводчик "
            "— см. docs/REALTIME_TRANSLATOR_PLAN.md."
        )
        warn.setWordWrap(True)
        warn.setStyleSheet("color: #ffb300;")
        layout.addWidget(warn)

        self.device_combo = QComboBox()
        self._populate_devices()
        layout.addWidget(QLabel("Микрофон:"))
        layout.addWidget(self.device_combo)

        self.level_bar = QProgressBar()
        self.level_bar.setRange(0, 100)
        layout.addWidget(self.level_bar)

        self.btn_talk = QPushButton("● Зажать и говорить (Push-to-talk)")
        self.btn_talk.pressed.connect(self._start_recording)
        self.btn_talk.released.connect(self._stop_recording_and_convert)
        layout.addWidget(self.btn_talk)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        layout.addWidget(QLabel("OUTPUT:"))
        self.player = AudioPlayerWidget()
        layout.addWidget(self.player)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(box)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll_level)

        if sd is None:
            self.btn_talk.setEnabled(False)
            self.status_label.setText("sounddevice не установлен — режим недоступен.")

    def set_profile(self, profile: VoiceProfile | None):
        self.current_profile = profile

    def _populate_devices(self):
        if sd is None:
            self.device_combo.addItem("sounddevice не установлен", None)
            return
        try:
            for idx, d in enumerate(sd.query_devices()):
                if d.get("max_input_channels", 0) > 0:
                    self.device_combo.addItem(d["name"], idx)
        except Exception as e:
            self.device_combo.addItem(f"Ошибка: {e}", None)

    def _start_recording(self):
        if sd is None or not self.current_profile:
            if not self.current_profile:
                QMessageBox.information(self, "Нет профиля", "Сначала выберите Voice Profile.")
            return
        self._frames = []
        self._recording = True
        device = self.device_combo.currentData()

        def callback(indata, frames, time_info, status):
            if self._recording:
                self._frames.append(indata.copy())

        self._stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, device=device, callback=callback)
        self._stream.start()
        self._timer.start(100)
        self.status_label.setText("Запись...")

    def _poll_level(self):
        if self._frames:
            level = float(np.abs(self._frames[-1]).mean()) * 400
            self.level_bar.setValue(int(min(100, level)))

    def _stop_recording_and_convert(self):
        self._recording = False
        self._timer.stop()
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        if not self._frames or not self.current_profile:
            self.status_label.setText("Нет записанного аудио.")
            return

        audio = np.concatenate(self._frames, axis=0).flatten()
        if len(audio) / SAMPLE_RATE < 0.5:
            self.status_label.setText("Слишком короткая запись.")
            return

        fd, tmp_path = tempfile.mkstemp(suffix=".wav")
        import os
        os.close(fd)
        sf.write(tmp_path, audio, SAMPLE_RATE)

        target_ref = self.current_profile.best_reference_processed_path()
        if target_ref is None:
            self.status_label.setText("В профиле нет обработанных референсов.")
            return

        self.status_label.setText("Конвертация...")
        self.btn_talk.setEnabled(False)

        def task(progress_cb=None):
            from src.engines.seed_vc_engine import SeedVCEngine
            manager = get_model_manager()
            engine = manager.get_vc("seed_vc", SeedVCEngine)
            return engine.convert(tmp_path, str(target_ref), diffusion_steps=10)

        self._worker = Worker(task)
        self._worker.signals.finished.connect(self._on_done)
        self._worker.signals.error.connect(self._on_error)
        self._worker.start()

    def _on_done(self, result):
        self.btn_talk.setEnabled(True)
        self.status_label.setText(f"Готово ({result.generation_time_sec:.2f} сек)")
        fd, tmp_path = tempfile.mkstemp(suffix=".wav")
        import os
        os.close(fd)
        sf.write(tmp_path, result.audio, result.sample_rate)
        self.player.load_file(tmp_path, audio_array=result.audio, sample_rate=result.sample_rate)

    def _on_error(self, error_text: str):
        self.btn_talk.setEnabled(True)
        self.status_label.setText("Ошибка конвертации.")
        log.error(error_text)
        QMessageBox.critical(self, "Ошибка", error_text.splitlines()[-1] if error_text else "Неизвестная ошибка")
