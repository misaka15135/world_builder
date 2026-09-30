"""Read-only resources in a source checkout or a PyInstaller bundle."""
from pathlib import Path
import sys


def resource_root():
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[2]
