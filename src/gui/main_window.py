"""Main window: Voice Profile panel + tabbed MODE 1/2/3 + status bar (GPU/VRAM/LOCAL MODE)."""
from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QMainWindow, QSplitter, QTabWidget, QVBoxLayout, QWidget,
)

from src.gui.mode1_panel import Mode1Panel
from src.gui.mode2_panel import Mode2Panel
from src.gui.mode3_panel import Mode3Panel
from src.gui.profile_panel import ProfilePanel
from src.utils.config import get_config
from src.utils.gpu import get_gpu_status, get_process_vram_mb

DARK_STYLESHEET = """
QWidget { background-color: #1e1e1e; color: #e0e0e0; font-size: 13px; }
QGroupBox { border: 1px solid #3a3a3a; border-radius: 6px; margin-top: 8px; padding-top: 10px; font-weight: bold; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QPushButton { background-color: #2d2d2d; border: 1px solid #444; border-radius: 4px; padding: 6px 10px; }
QPushButton:hover { background-color: #3a3a3a; }
QPushButton:disabled { color: #777; }
QPlainTextEdit, QListWidget, QComboBox { background-color: #252526; border: 1px solid #3a3a3a; border-radius: 4px; }
QTabWidget::pane { border: 1px solid #3a3a3a; }
QTabBar::tab { background: #2d2d2d; padding: 8px 16px; }
QTabBar::tab:selected { background: #3a3a3a; }
QProgressBar { border: 1px solid #3a3a3a; border-radius: 4px; text-align: center; }
QProgressBar::chunk { background-color: #4fc3f7; }
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LOCAL VOICE STUDIO")
        self.resize(1100, 800)
        self.setStyleSheet(DARK_STYLESHEET)

        self.profile_panel = ProfilePanel()
        self.mode1 = Mode1Panel()
        self.mode2 = Mode2Panel()
        self.mode3 = Mode3Panel()

        tabs = QTabWidget()
        tabs.addTab(self.mode1, "TEXT → VOICE")
        tabs.addTab(self.mode2, "AUDIO → VOICE")
        tabs.addTab(self.mode3, "LIVE [EXPERIMENTAL]")

        splitter = QSplitter()
        splitter.addWidget(self.profile_panel)
        splitter.addWidget(tabs)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 800])

        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.addWidget(self._build_preset_bar())
        central_layout.addWidget(splitter)
        self.setCentralWidget(central)

        self.profile_panel.profile_changed.connect(self.mode1.set_profile)
        self.profile_panel.profile_changed.connect(self.mode2.set_profile)
        self.profile_panel.profile_changed.connect(self.mode3.set_profile)
        self.profile_panel.reference_text_ready.connect(self._on_reference_text_ready)
        self._tabs = tabs
        self.mode1.set_profile(self.profile_panel.current_profile)
        self.mode2.set_profile(self.profile_panel.current_profile)
        self.mode3.set_profile(self.profile_panel.current_profile)

        self._build_status_bar()
        self._gpu_timer = QTimer(self)
        self._gpu_timer.timeout.connect(self._update_gpu_status)
        self._gpu_timer.start(2000)
        self._update_gpu_status()

    def _build_preset_bar(self) -> QWidget:
        cfg = get_config()
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)

        local_badge = QLabel("🔒 LOCAL MODE — данные не отправляются в облако")
        local_badge.setStyleSheet("color: #4caf50; font-weight: bold; padding: 4px;")
        layout.addWidget(local_badge)
        layout.addStretch()

        layout.addWidget(QLabel("Preset:"))
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(["fast", "balanced", "quality"])
        self.preset_combo.setCurrentText(cfg.get("active_preset", "balanced"))
        self.preset_combo.currentTextChanged.connect(self._on_preset_changed)
        layout.addWidget(self.preset_combo)
        return bar

    def _on_reference_text_ready(self, text: str):
        self.mode1.set_text(text)
        self._tabs.setCurrentWidget(self.mode1)

    def _on_preset_changed(self, preset: str):
        cfg = get_config()
        cfg.set("active_preset", preset)
        cfg.save()

    def _build_status_bar(self):
        self.gpu_label = QLabel("GPU: —")
        self.statusBar().addPermanentWidget(self.gpu_label)

    def _update_gpu_status(self):
        status = get_gpu_status()
        if not status.available:
            self.gpu_label.setText(f"GPU: недоступна ({status.error})")
            self.gpu_label.setStyleSheet("color: #e53935;")
            return
        process_vram = get_process_vram_mb()
        self.gpu_label.setText(
            f"GPU: {status.name} | VRAM: {status.vram_used_mb:.0f}/{status.vram_total_mb:.0f} MB "
            f"(процесс: {process_vram:.0f} MB) | CUDA {status.cuda_version}"
        )
        self.gpu_label.setStyleSheet("color: #4fc3f7;")
