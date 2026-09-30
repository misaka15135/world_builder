"""Source and frozen executable entry point."""
from pathlib import Path
import sys
import multiprocessing

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

if __name__ == "__main__":
    multiprocessing.freeze_support()
    from world_builder.desktop.app import main
    raise SystemExit(main())
