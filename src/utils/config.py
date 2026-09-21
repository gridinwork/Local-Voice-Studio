"""Loading and access to config/config.json."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config" / "config.json"


class Config:
    def __init__(self, path: Path = CONFIG_PATH):
        self._path = path
        self._data: dict[str, Any] = {}
        self.reload()

    def reload(self) -> None:
        with open(self._path, "r", encoding="utf-8") as f:
            self._data = json.load(f)

    def save(self) -> None:
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def path_for(self, key: str) -> Path:
        """Resolve a *_dir config key to an absolute Path under PROJECT_ROOT, creating it."""
        rel = self._data[key]
        p = (PROJECT_ROOT / rel).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def data(self) -> dict[str, Any]:
        return self._data


_config: Config | None = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
    return _config
