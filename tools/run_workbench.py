#!/usr/bin/env python3
"""Launch from a source checkout without requiring package installation."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from world_builder.workbench.server import main

if __name__ == "__main__":
    raise SystemExit(main())
