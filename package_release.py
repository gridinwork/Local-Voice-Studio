"""Builds a clean, shareable ZIP of Local Voice Studio for GitHub — source
code, docs and configs only. Excludes everything personal or environment-
specific: venvs, downloaded/cloned models, voice profiles, generated audio,
caches, logs. Safe to re-run any time a release snapshot is needed.

Usage:
    .venv\\Scripts\\python.exe package_release.py [--version 0.1.0] [--out dist]
"""
from __future__ import annotations

import argparse
import shutil
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

# Directories excluded entirely (personal data, environments, or fetched-not-authored content).
EXCLUDE_DIRS = {
    ".venv", ".git", "__pycache__",
    "models",   # downloaded TTS weights + cloned seed-vc repo/venv — fetched by INSTALL.md, not source
    "voices",   # personal voice profiles
    "output",   # generated audio
    "cache",    # voice-prompt caches, benchmark scratch files
}

# Top-level files never shipped.
EXCLUDE_FILES = {
    ".gitkeep",  # regenerated per-directory below instead of copied verbatim
}

EXCLUDE_SUFFIXES = {".pyc", ".pyo"}

# Directories that should exist in the archive, but empty (with just a .gitkeep
# so git/zip tooling preserves them) — matches the runtime layout install.bat expects.
EMPTY_DIRS_WITH_GITKEEP = ["models", "voices", "output", "cache", "logs"]


def should_skip_dir(path: Path) -> bool:
    return path.name in EXCLUDE_DIRS


def should_skip_file(path: Path) -> bool:
    if path.name in EXCLUDE_FILES:
        return True
    if path.suffix in EXCLUDE_SUFFIXES:
        return True
    return False


def copy_source_tree(staging: Path) -> None:
    for item in PROJECT_ROOT.iterdir():
        if item.name in EXCLUDE_DIRS or item.name == "dist" or item.name == staging.name:
            continue
        if item.is_dir():
            if item.name == "logs":
                continue  # recreated empty below (may contain personal log lines)
            shutil.copytree(
                item, staging / item.name,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".gitkeep"),
            )
        else:
            if should_skip_file(item):
                continue
            shutil.copy2(item, staging / item.name)

    for d in EMPTY_DIRS_WITH_GITKEEP:
        target = staging / d
        target.mkdir(parents=True, exist_ok=True)
        (target / ".gitkeep").touch()


def zip_staging(staging: Path, out_zip: Path) -> None:
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in staging.rglob("*"):
            if path.is_file():
                zf.write(path, arcname=path.relative_to(staging.parent))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="0.1.0")
    parser.add_argument("--out", default="dist")
    args = parser.parse_args()

    out_dir = PROJECT_ROOT / args.out
    out_dir.mkdir(exist_ok=True)

    staging_name = "LocalVoiceStudio"
    staging = out_dir / staging_name
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    print(f"Собираю чистое дерево проекта в {staging} ...")
    copy_source_tree(staging)

    zip_path = out_dir / f"LocalVoiceStudio_v{args.version}.zip"
    if zip_path.exists():
        zip_path.unlink()
    print(f"Упаковываю в {zip_path} ...")
    zip_staging(staging, zip_path)

    shutil.rmtree(staging)

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"Готово: {zip_path} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    main()
