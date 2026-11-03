"""Importing the source launcher must not start the application."""

import subprocess
import sys
from pathlib import Path


def test_import_launcher_does_not_create_application():
    result = subprocess.run(
        [sys.executable, "-c", "import main; from PySide6.QtWidgets import QApplication; assert QApplication.instance() is None"],
        cwd=Path(__file__).resolve().parent.parent,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
