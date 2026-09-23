from __future__ import annotations

import os
import uuid
from pathlib import Path

from .spec import canonical


class RunJournal:
    """Append-only events; a killed process leaves a readable completed prefix."""

    def __init__(self, root: Path):
        self.run_id = "run_" + uuid.uuid4().hex
        folder = root / "runs"
        folder.mkdir(parents=True, exist_ok=True)
        self.path = folder / (self.run_id + ".jsonl")
        # Exclusive creation prevents an accidental overwrite of earlier evidence.
        with self.path.open("xb"):
            pass

    def append(self, event: dict) -> None:
        with self.path.open("ab") as handle:
            handle.write(canonical(event) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
