"""Voice Profile management: voices/<Name>/{profile.json, reference/, processed/, cache/}."""
from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from src.audio.audio_preprocessing import QualityReport, Quality, preprocess_reference
from src.utils.config import get_config
from src.utils.logging_setup import get_logger

log = get_logger("voice_profile")


def _profiles_root() -> Path:
    return get_config().path_for("voices_dir")


@dataclass
class ReferenceEntry:
    filename: str
    original_name: str
    added_at: str
    duration_sec: float
    quality: str
    quality_reasons: list[str] = field(default_factory=list)
    transcript: str = ""


@dataclass
class VoiceProfile:
    name: str
    created_at: str
    references: list[ReferenceEntry] = field(default_factory=list)
    settings: dict = field(default_factory=dict)

    @property
    def root(self) -> Path:
        return _profiles_root() / self.name

    @property
    def reference_dir(self) -> Path:
        return self.root / "reference"

    @property
    def processed_dir(self) -> Path:
        return self.root / "processed"

    @property
    def cache_dir(self) -> Path:
        return self.root / "cache"

    @property
    def profile_json_path(self) -> Path:
        return self.root / "profile.json"

    @staticmethod
    def create(name: str) -> "VoiceProfile":
        name = name.strip()
        if not name:
            raise ValueError("Имя профиля не может быть пустым.")
        invalid = set('<>:"/\\|?*')
        if any(c in invalid for c in name):
            raise ValueError("Имя профиля содержит недопустимые символы.")
        root = _profiles_root() / name
        if root.exists():
            raise ValueError(f"Профиль '{name}' уже существует.")

        profile = VoiceProfile(name=name, created_at=datetime.now().isoformat())
        for d in (profile.reference_dir, profile.processed_dir, profile.cache_dir):
            d.mkdir(parents=True, exist_ok=True)
        profile.save()
        log.info(f"Создан Voice Profile '{name}'")
        return profile

    @staticmethod
    def load(name: str) -> "VoiceProfile":
        root = _profiles_root() / name
        path = root / "profile.json"
        if not path.exists():
            raise FileNotFoundError(f"Профиль '{name}' не найден.")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        refs = [ReferenceEntry(**r) for r in data.get("references", [])]
        return VoiceProfile(
            name=data["name"],
            created_at=data["created_at"],
            references=refs,
            settings=data.get("settings", {}),
        )

    @staticmethod
    def list_all() -> list[str]:
        root = _profiles_root()
        if not root.exists():
            return []
        return sorted([p.name for p in root.iterdir() if p.is_dir() and (p / "profile.json").exists()])

    @staticmethod
    def delete(name: str) -> None:
        root = _profiles_root() / name
        if root.exists():
            shutil.rmtree(root)
            log.info(f"Профиль '{name}' удалён.")

    def rename(self, new_name: str) -> "VoiceProfile":
        new_root = _profiles_root() / new_name
        if new_root.exists():
            raise ValueError(f"Профиль '{new_name}' уже существует.")
        self.root.rename(new_root)
        self.name = new_name
        self.save()
        return self

    def save(self) -> None:
        data = {
            "name": self.name,
            "created_at": self.created_at,
            "references": [asdict(r) for r in self.references],
            "settings": self.settings,
        }
        self.root.mkdir(parents=True, exist_ok=True)
        with open(self.profile_json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add_reference(
        self, src_path: Path, denoise: bool = False, transcript: str | None = None, auto_transcribe: bool = True
    ) -> ReferenceEntry:
        src_path = Path(src_path)
        if not src_path.exists():
            raise FileNotFoundError(src_path)

        dest_name = src_path.name
        dest_path = self.reference_dir / dest_name
        counter = 1
        while dest_path.exists():
            dest_path = self.reference_dir / f"{src_path.stem}_{counter}{src_path.suffix}"
            counter += 1
        shutil.copy2(src_path, dest_path)

        processed_path = self.processed_dir / f"{dest_path.stem}_clean.wav"
        report: QualityReport = preprocess_reference(dest_path, processed_path, denoise=denoise)

        if transcript is None and auto_transcribe:
            try:
                from src.audio.asr import transcribe as asr_transcribe
                transcript = asr_transcribe(processed_path).text
            except Exception as e:
                log.warning(f"Автоматическая транскрипция референса не удалась: {e}")
                transcript = ""

        entry = ReferenceEntry(
            filename=dest_path.name,
            original_name=src_path.name,
            added_at=datetime.now().isoformat(),
            duration_sec=report.duration_sec,
            quality=report.quality.value,
            quality_reasons=report.reasons,
            transcript=transcript or "",
        )
        self.references.append(entry)
        self._invalidate_cache()
        self.save()
        return entry

    def remove_reference(self, filename: str) -> None:
        self.references = [r for r in self.references if r.filename != filename]
        ref_path = self.reference_dir / filename
        ref_path.unlink(missing_ok=True)
        stem = Path(filename).stem
        for p in self.processed_dir.glob(f"{stem}*_clean.wav"):
            p.unlink(missing_ok=True)
        self._invalidate_cache()
        self.save()

    def _invalidate_cache(self) -> None:
        if self.cache_dir.exists():
            for f in self.cache_dir.iterdir():
                f.unlink(missing_ok=True)

    def rebuild(self, denoise: bool = False) -> None:
        for entry in list(self.references):
            src = self.reference_dir / entry.filename
            if not src.exists():
                continue
            processed_path = self.processed_dir / f"{src.stem}_clean.wav"
            report = preprocess_reference(src, processed_path, denoise=denoise)
            entry.duration_sec = report.duration_sec
            entry.quality = report.quality.value
            entry.quality_reasons = report.reasons
        self._invalidate_cache()
        self.save()

    def best_reference_processed_path(self) -> Path | None:
        if not self.references:
            return None

        def sort_key(r: ReferenceEntry):
            quality_rank = {Quality.GOOD.value: 2, Quality.ACCEPTABLE.value: 1, Quality.BAD.value: 0}
            return (quality_rank.get(r.quality, 0), r.duration_sec)

        best = max(self.references, key=sort_key)
        path = self.processed_dir / f"{Path(best.filename).stem}_clean.wav"
        return path if path.exists() else None

    def overall_quality(self) -> str:
        if not self.references:
            return "NO_DATA"
        ranks = {Quality.GOOD.value: 2, Quality.ACCEPTABLE.value: 1, Quality.BAD.value: 0}
        best = max(self.references, key=lambda r: ranks.get(r.quality, 0))
        return best.quality

    def cache_file(self, engine_name: str, ext: str = "pt") -> Path:
        return self.cache_dir / f"{engine_name}_speaker_prompt.{ext}"
