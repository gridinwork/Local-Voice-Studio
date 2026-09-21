"""Centralized logging setup writing to logs/app.log and stdout."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from src.utils.config import PROJECT_ROOT

LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "app.log"

_configured = False


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    global _configured
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger("lvs")
    if _configured:
        return root
    root.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(fmt)
    root.addHandler(stream_handler)

    _configured = True
    return root


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(f"lvs.{name}")
