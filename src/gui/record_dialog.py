"""RECORD REFERENCE dialog: mic level meter, record/stop/preview/save."""
from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout,
)

try:
    import sounddevice as sd
except Exception:
    sd = None

SAMPLE_RATE = 24000


class RecordDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Записать референс")
        self.saved_path: str | None = None
        self._recording = False
        self._frames: list[np.ndarray] = []
        self._stream = None
        self._elapsed_ms = 0

        layout = QVBoxLayout(self)

        self.device_combo = QComboBox()
        self._populate_devices()
        layout.addWidget(QLabel("Устройство ввода:"))
        layout.addWidget(self.device_combo)

        self.level_bar = QProgressBar()
        self.level_bar.setRange(0, 100)
        layout.addWidget(QLabel("Уровень сигнала:"))
        layout.addWidget(self.level_bar)

        self.duration_label = QLabel("Длительность: 0.0 сек")
        layout.addWidget(self.duration_label)

        btn_row = QHBoxLayout()
        self.btn_record = QPushButton("● Записать")
        self.btn_stop = QPushButton("■ Стоп")
        self.btn_preview = QPushButton("▶ Прослушать")
        self.btn_save = QPushButton("Сохранить в профиль")
        self.btn_stop.setEnabled(False)
        self.btn_preview.setEnabled(False)
        self.btn_save.setEnabled(False)
        for b in (self.btn_record, self.btn_stop, self.btn_preview, self.btn_save):
            btn_row.addWidget(b)
        layout.addLayout(btn_row)

        self.btn_record.clicked.connect(self.start_recording)
        self.btn_stop.clicked.connect(self.stop_recording)
        self.btn_preview.clicked.connect(self.preview)
        self.btn_save.clicked.connect(self.save_and_accept)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll_level)

        self._tmp_wav: Path | None = None

    def _populate_devices(self):
        if sd is None:
            self.device_combo.addItem("sounddevice не установлен", None)
            return
        try:
            devices = sd.query_devices()
            for idx, d in enumerate(devices):
                if d.get("max_input_channels", 0) > 0:
                    self.device_combo.addItem(d["name"], idx)
        except Exception as e:
            self.device_combo.addItem(f"Ошибка получения устройств: {e}", None)

    def start_recording(self):
        if sd is None:
            self.duration_label.setText("Ошибка: sounddevice не установлен.")
            return
        device = self.device_combo.currentData()
        self._frames = []
        self._recording = True
        self.btn_record.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_save.setEnabled(False)
        self.btn_preview.setEnabled(False)

        def callback(indata, frames, time_info, status):
            if self._recording:
                self._frames.append(indata.copy())

        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, device=device, callback=callback,
        )
        self._stream.start()
        self._timer.start(100)

    def _poll_level(self):
        if self._frames:
            last = self._frames[-1]
            level = float(np.abs(last).mean()) * 400
            self.level_bar.setValue(int(min(100, level)))
        total_samples = sum(len(f) for f in self._frames)
        self.duration_label.setText(f"Длительность: {total_samples / SAMPLE_RATE:.1f} сек")

    def stop_recording(self):
        self._recording = False
        self._timer.stop()
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        self.btn_record.setEnabled(True)
        self.btn_stop.setEnabled(False)

        if self._frames:
            audio = np.concatenate(self._frames, axis=0).flatten()
            fd, tmp_path = tempfile.mkstemp(suffix=".wav")
            import os
            os.close(fd)
            sf.write(tmp_path, audio, SAMPLE_RATE)
            self._tmp_wav = Path(tmp_path)
            self.btn_preview.setEnabled(True)
            self.btn_save.setEnabled(True)

    def preview(self):
        if self._tmp_wav and sd is not None:
            data, sr = sf.read(str(self._tmp_wav))
            sd.play(data, sr)

    def save_and_accept(self):
        if self._tmp_wav:
            self.saved_path = str(self._tmp_wav)
            self.accept()
