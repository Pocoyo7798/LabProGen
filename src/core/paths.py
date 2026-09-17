"""Resolve application directories in development, frozen and installed runtimes."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from platformdirs import user_config_dir

APP_NAME = "LabProGen"

_PACKAGE_DIR = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _PACKAGE_DIR.parent

# A checkout keeps the entry script and the build metadata next to the package.
# A copy installed into site-packages by pip/pipx/uv does not.
_CHECKOUT_MARKERS = ("main.py", "pyproject.toml")


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def is_source_checkout() -> bool:
    """True when the package is imported from the project tree or an editable install."""
    if is_frozen():
        return False
    return all((_PROJECT_ROOT / marker).exists() for marker in _CHECKOUT_MARKERS)


def get_package_dir() -> Path:
    """Directory of the installed application package."""
    return _PACKAGE_DIR


def get_app_dir() -> Path:
    """Application root: the executable's folder, the checkout, or the package."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    if is_source_checkout():
        return _PROJECT_ROOT
    return _PACKAGE_DIR


def get_bundle_dir() -> Path:
    """Root of the read-only assets shipped with the application."""
    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
    return _PACKAGE_DIR


def bundled_asset_candidates(name: str) -> list[Path]:
    """Return the locations to try for a read-only asset directory shipped with the app."""
    candidates: list[Path] = []
    if is_frozen():
        # PyInstaller exposes bundled data under _MEIPASS, which need not agree
        # with the __file__ the frozen package reports, so it wins there.
        bundle_dir = get_bundle_dir()
        candidates.extend([bundle_dir / "src" / name, bundle_dir / name])
    package_asset = _PACKAGE_DIR / name
    if package_asset not in candidates:
        candidates.append(package_asset)
    return candidates


def resolve_bundled_asset_dir(name: str) -> Path:
    """Return the first existing bundled asset directory, or the package-relative default."""
    for candidate in bundled_asset_candidates(name):
        if candidate.exists():
            return candidate
    return _PACKAGE_DIR / name


def get_config_dir() -> Path:
    """Writable config directory.

    A checkout and the portable frozen build keep their config next to the
    application. An installed copy must not write into site-packages, so it
    uses the per-user location the platform defines.
    """
    if is_frozen() or is_source_checkout():
        return get_app_dir() / "config"
    return Path(user_config_dir(APP_NAME, appauthor=False, roaming=True))


def get_project_root() -> Path:
    """Backward-compatible alias for :func:`get_app_dir`."""
    return get_app_dir()


def config_read_candidates(filename: str) -> list[Path]:
    """Return paths to try when reading a config file."""
    candidates = [get_config_dir() / filename]
    for asset_dir in bundled_asset_candidates("config"):
        bundled = asset_dir / filename
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

    source = next(
        (
            candidate
            for asset_dir in bundled_asset_candidates("config")
            if (candidate := asset_dir / filename).exists()
        ),
        None,
    )
    if source is None:
        return None
    try:
        if source.resolve() == target.resolve():
            return target
    except OSError:
        pass

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return target
