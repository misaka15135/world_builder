from __future__ import annotations

import copy
import hashlib
import json
import os
import sqlite3
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator

from world_builder.generation.spec import canonical, digest
from world_builder.wir.validator import validate_package


class StoreError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


class Repository:
    """Single local SQLite authority. All writes compare the expected head."""

    def __init__(self, directory: str | Path):
        self.root = Path(directory).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.database = self.root / "wir.sqlite3"
        with self.connect() as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE name='schema_migrations'").fetchone():
                migration = Path(__file__).resolve().parents[3] / "storage/migrations/0001_initial.sql"
                db.executescript("BEGIN IMMEDIATE;\n" + migration.read_text(encoding="utf-8"))
                db.execute("INSERT INTO schema_migrations VALUES (1, '0001_initial', datetime('now'))")
                db.commit()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.database, timeout=10)
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA synchronous=FULL")
        try:
            yield db
        finally:
            db.close()

    def head(self, world_id: str) -> str | None:
        with self.connect() as db:
            row = db.execute("SELECT head_revision_id FROM worlds WHERE world_id=?", (world_id,)).fetchone()
            return row[0] if row else None

    def publish(self, payload: bytes) -> tuple[str, str]:
        content_hash = "sha256:" + hashlib.sha256(payload).hexdigest()
        relative = "assets/sha256/" + content_hash[7:]
        destination = self.root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if destination.read_bytes() != payload:
                raise StoreError("resource.hash_mismatch", relative)
            return content_hash, relative
        fd, temporary = tempfile.mkstemp(prefix=".staged-", dir=destination.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return content_hash, relative

    def _resources(self, package: dict) -> list[tuple[dict, bytes]]:
        resources = []
        for asset in package["records"]:
            if asset["record_type"] != "asset":
                continue
            expected = "assets/sha256/" + asset["content_hash"][7:]
            if asset["uri"] != expected:
                raise StoreError("resource.unsupported_uri", "pilot repository accepts local content-addressed resources only")
            path = (self.root / expected).resolve()
            if not path.is_relative_to(self.root):
                raise StoreError("resource.path_escape", expected)
            if not path.is_file():
                raise StoreError("resource.missing", expected)
            payload = path.read_bytes()
            if "sha256:" + hashlib.sha256(payload).hexdigest() != asset["content_hash"]:
                raise StoreError("resource.hash_mismatch", expected)
            resources.append((asset, payload))
        return resources

    def commit(self, package: dict, expected_head: str | None,
               before_commit: Callable[[], None] | None = None) -> None:
        validate_package(package)
        manifest = package["manifest"]
        revision = next(r for r in package["records"] if r["id"] == manifest["revision_id"])
        if revision.get("extensions", {}).get("snapshot_manifest") != manifest:
            raise StoreError("contract.snapshot_manifest", "revision must contain the exact snapshot manifest")
        content = [r for r in package["records"] if r["record_type"] != "revision"]
        if revision["change_set_hash"] != digest(content):
            raise StoreError("resource.change_set_hash", revision["id"])
        if not revision["committed"] or any(revision["validation_summary"].values()):
            raise StoreError("constraint.unvalidated_revision", revision["id"])
        if revision["parent_revision_ids"] != ([expected_head] if expected_head else []):
            raise StoreError("conflict.parent_revision", revision["id"])
        resources = self._resources(package)
        world_id, revision_id = manifest["world_id"], manifest["revision_id"]
        with self.connect() as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                current = db.execute("SELECT head_revision_id FROM worlds WHERE world_id=?", (world_id,)).fetchone()
                if (current[0] if current else None) != expected_head:
                    raise StoreError("conflict.base_revision", "head changed before commit")
                if expected_head:
                    old = self._load(db, world_id, expected_head)
                    self._check_locks(old, package)
                if current is None:
                    db.execute("INSERT INTO worlds VALUES (?, ?, ?, NULL)", (world_id, "0.1.0", manifest["created_at"]))
                db.execute("INSERT INTO revisions VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (
                    revision_id, world_id, canonical(revision["parent_revision_ids"]).decode(),
                    revision["author"], revision["created_at"], revision["change_set_hash"],
                    canonical(revision["validation_summary"]).decode(), 1))
                for record in package["records"]:
                    cursor = db.execute("INSERT INTO records VALUES (?, ?, ?, ?, ?, ?, ?)", (
                        world_id, revision_id, record["id"], record["record_type"], record.get("parent_id"),
                        canonical(record).decode(), digest(record)))
                    if record["record_type"] == "entity":
                        bounds = record["bounds"]
                        db.execute("INSERT INTO record_bounds VALUES (?, ?, ?, ?, ?, ?, ?)", (
                            cursor.lastrowid, *[v for axis in range(3) for v in (bounds["min"][axis], bounds["max"][axis])]))
                for asset, payload in resources:
                    db.execute("INSERT OR IGNORE INTO resource_blobs VALUES (?, ?, ?, ?, 1)", (
                        asset["content_hash"], len(payload), asset["media_type"], asset["uri"]))
                    db.execute("INSERT INTO revision_resources VALUES (?, ?, ?)", (revision_id, asset["id"], asset["content_hash"]))
                db.execute("UPDATE worlds SET head_revision_id=? WHERE world_id=?", (revision_id, world_id))
                db.execute("INSERT INTO branches VALUES (?, 'main', ?) ON CONFLICT(world_id, branch_name) DO UPDATE SET head_revision_id=excluded.head_revision_id", (world_id, revision_id))
                if before_commit:
                    before_commit()
                db.commit()
            except BaseException:
                db.rollback()
                raise

    @staticmethod
    def _check_locks(old: dict, new: dict) -> None:
        records = {r["id"]: r for r in new["records"]}
        missing = object()

        def resolve(record: dict, pointer: str):
            value = record
            try:
                for token in pointer.lstrip("/").split("/"):
                    token = token.replace("~1", "/").replace("~0", "~")
                    value = value[int(token)] if isinstance(value, list) else value[token]
                return value
            except (KeyError, IndexError, ValueError, TypeError):
                return missing

        for record in old["records"]:
            for lock in record.get("locks", []):
                replacement = records.get(record["id"], {})
                if lock not in replacement.get("locks", []) or resolve(record, lock["json_pointer"]) != resolve(replacement, lock["json_pointer"]):
                    raise StoreError("conflict.locked_field", record["id"] + lock["json_pointer"])

    def _load(self, db: sqlite3.Connection, world_id: str, revision_id: str) -> dict:
        rows = db.execute("SELECT payload_json, payload_sha256 FROM records WHERE world_id=? AND revision_id=? ORDER BY rowid", (world_id, revision_id)).fetchall()
        if not rows:
            raise StoreError("reference.revision_missing", revision_id)
        records = []
        for payload, checksum in rows:
            record = json.loads(payload)
            if digest(record) != checksum:
                raise StoreError("resource.record_hash_mismatch", record["id"])
            records.append(record)
        revision = next(r for r in records if r["id"] == revision_id)
        manifest = copy.deepcopy(revision["extensions"]["snapshot_manifest"])
        package = {"manifest": manifest, "records": records}
        validate_package(package)
        self._resources(package)
        return package

    def load(self, world_id: str, revision_id: str | None = None) -> dict:
        with self.connect() as db:
            if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise StoreError("resource.database_corrupt", str(self.database))
            if revision_id is None:
                row = db.execute("SELECT head_revision_id FROM worlds WHERE world_id=?", (world_id,)).fetchone()
                revision_id = row[0] if row else None
            if revision_id is None:
                raise StoreError("reference.world_missing", world_id)
            return self._load(db, world_id, revision_id)
