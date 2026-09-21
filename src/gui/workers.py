"""QThread workers so model load/generate/convert never block the GUI thread."""
from __future__ import annotations

import traceback

from PySide6.QtCore import QObject, QThread, Signal


class WorkerSignals(QObject):
    finished = Signal(object)
    error = Signal(str)
    progress = Signal(str)


class Worker(QThread):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    def run(self):
        try:
            def progress_cb(msg: str):
                self.signals.progress.emit(msg)

            result = self.fn(*self.args, progress_cb=progress_cb, **self.kwargs)
            self.signals.finished.emit(result)
        except TypeError:
            try:
                result = self.fn(*self.args, **self.kwargs)
                self.signals.finished.emit(result)
            except Exception:
                self.signals.error.emit(traceback.format_exc())
        except Exception:
            self.signals.error.emit(traceback.format_exc())
