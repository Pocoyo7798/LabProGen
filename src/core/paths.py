"""Resolve application directories in development and frozen runtimes."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def get_app_dir() -> Path:
    """Writable application root (project checkout or folder containing the executable)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return _PROJECT_ROOT


def get_bundle_dir() -> Path:
    """Read-only directory for packaged assets bundled with the executable."""
    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
    return _PROJECT_ROOT


def get_config_dir() -> Path:
    """Writable config directory next to the app / project root."""
    return get_app_dir() / "config"


def get_project_root() -> Path:
    """Backward-compatible alias for :func:`get_app_dir`."""
    return get_app_dir()


def config_read_candidates(filename: str) -> list[Path]:
    """Return paths to try when reading a config file."""
    candidates = [get_config_dir() / filename]
    bundled = get_bundle_dir() / "config" / filename
    if bundled not in candidates:
        candidates.append(bundled)
    return candidates


def resolve_config_read_path(filename: str) -> Path | None:
    """Return the first existing config path for ``filename``, if any."""
    for path in config_read_candidates(filename):
        if path.exists():
            return path
    return None


def writable_config_path(filename: str) -> Path:
    """Return the writable config path for ``filename``."""
    return get_config_dir() / filename


def seed_writable_config_from_bundle(filename: str) -> Path | None:
    """Copy a bundled config template into the writable config directory."""
    target = writable_config_path(filename)
    if target.exists():
        return target

    source = get_bundle_dir() / "config" / filename
    if not source.exists():
        return None
    try:
        if source.resolve() == target.resolve():
            return target
    except OSError:
        pass

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return target
