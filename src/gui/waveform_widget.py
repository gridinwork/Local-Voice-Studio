"""Lightweight waveform display (QPainter, no extra plotting dependency)."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget


class WaveformWidget(QWidget):
    def __init__(self, color: str = "#4fc3f7", parent=None):
        super().__init__(parent)
        self.setMinimumHeight(80)
        self._peaks: np.ndarray | None = None
        self._color = QColor(color)
        self._playhead_ratio: float = 0.0

    def set_audio(self, audio: np.ndarray | None, sr: int = 24000):
        if audio is None or len(audio) == 0:
            self._peaks = None
            self.update()
            return
        n_buckets = max(1, self.width() or 400)
        bucket_size = max(1, len(audio) // n_buckets)
        trimmed = audio[: bucket_size * n_buckets]
        if len(trimmed) == 0:
            self._peaks = np.abs(audio).reshape(1)
        else:
            self._peaks = np.abs(trimmed).reshape(-1, bucket_size).max(axis=1)
        self.update()

    def set_playhead(self, ratio: float):
        self._playhead_ratio = max(0.0, min(1.0, ratio))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#1e1e1e"))

        if self._peaks is None or len(self._peaks) == 0:
            painter.setPen(QColor("#666666"))
            painter.drawText(self.rect(), Qt.AlignCenter, "Нет аудио")
            return

        w, h = self.width(), self.height()
        mid = h / 2
        n = len(self._peaks)
        pen = QPen(self._color)
        pen.setWidth(1)
        painter.setPen(pen)

        for i, peak in enumerate(self._peaks):
            x = int(i / n * w)
            bar_h = float(peak) * mid
            painter.drawLine(x, int(mid - bar_h), x, int(mid + bar_h))

        if self._playhead_ratio > 0:
            painter.setPen(QColor("#ffffff"))
            x = int(self._playhead_ratio * w)
            painter.drawLine(x, 0, x, h)
