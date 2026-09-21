"""Local Voice Studio — application entry point (PySide6 GUI)."""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtWidgets import QApplication, QMessageBox

from src.audio.audio_preprocessing import configure_pydub_ffmpeg
from src.utils.logging_setup import get_logger

log = get_logger("app")


def main():
    configure_pydub_ffmpeg()
    app = QApplication(sys.argv)
    app.setApplicationName("Local Voice Studio")

    try:
        from src.gui.main_window import MainWindow
        window = MainWindow()
        window.show()
    except Exception:
        tb = traceback.format_exc()
        log.error(f"Не удалось запустить GUI: {tb}")
        QMessageBox.critical(None, "Ошибка запуска", f"Не удалось запустить Local Voice Studio.\n\nСм. logs/app.log.\n\n{tb[-800:]}")
        sys.exit(1)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
