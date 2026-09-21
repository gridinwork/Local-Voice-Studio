"""Play/Pause/Stop/Seek/Volume audio player widget using QtMultimedia."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl, Qt
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QSlider, QVBoxLayout, QWidget

from src.gui.waveform_widget import WaveformWidget


class AudioPlayerWidget(QWidget):
    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)
        self._audio_output.setVolume(0.8)

        self.waveform = WaveformWidget()

        self.btn_play = QPushButton("▶ Play")
        self.btn_pause = QPushButton("⏸ Pause")
        self.btn_stop = QPushButton("⏹ Stop")
        self.seek_slider = QSlider(Qt.Horizontal)
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)

        controls = QHBoxLayout()
        controls.addWidget(self.btn_play)
        controls.addWidget(self.btn_pause)
        controls.addWidget(self.btn_stop)
        controls.addWidget(self.seek_slider, stretch=1)
        controls.addWidget(self.volume_slider)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.waveform)
        layout.addLayout(controls)

        self.btn_play.clicked.connect(self.play)
        self.btn_pause.clicked.connect(self._player.pause)
        self.btn_stop.clicked.connect(self.stop)
        self.volume_slider.valueChanged.connect(lambda v: self._audio_output.setVolume(v / 100))
        self.seek_slider.sliderMoved.connect(self._on_seek)
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(lambda d: self.seek_slider.setRange(0, max(d, 1)))

        self._current_path: Path | None = None

    def load_file(self, path: str | Path, audio_array=None, sample_rate: int = 24000):
        self._current_path = Path(path)
        self._player.setSource(QUrl.fromLocalFile(str(self._current_path)))
        if audio_array is not None:
            self.waveform.set_audio(audio_array, sample_rate)
        else:
            self._load_waveform_from_file(self._current_path)

    def _load_waveform_from_file(self, path: Path):
        try:
            import soundfile as sf
            data, sr = sf.read(str(path), always_2d=False)
            if data.ndim > 1:
                data = data.mean(axis=1)
            self.waveform.set_audio(data, sr)
        except Exception:
            self.waveform.set_audio(None)

    def play(self):
        self._player.play()

    def stop(self):
        self._player.stop()
        self.waveform.set_playhead(0.0)

    def _on_seek(self, position: int):
        self._player.setPosition(position)

    def _on_position_changed(self, position: int):
        self.seek_slider.blockSignals(True)
        self.seek_slider.setValue(position)
        self.seek_slider.blockSignals(False)
        duration = self._player.duration()
        if duration > 0:
            self.waveform.set_playhead(position / duration)
