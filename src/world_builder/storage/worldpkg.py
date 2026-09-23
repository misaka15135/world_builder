"""Bounded ZIP64 WIR 0.1 exchange; SQLite remains the only writable authority."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import stat
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from world_builder.generation.spec import canonical, digest
from world_builder.wir.validator import validate_package

from .repository import Repository, StoreError

FORMAT = "worldpkg-zip64-0.1"
MAX_MEMBERS = 512
MAX_TOTAL_BYTES = 128 * 1024 * 1024
MAX_MEMBER_BYTES = 64 * 1024 * 1024
MAX_RATIO = 1000


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _safe_name(name: str) -> bool:
    return (bool(name) and len(name) <= 240 and not name.startswith("/") and "\\" not in name
            and ":" not in name and "\x00" not in name
            and all(part not in {"", ".", ".."} for part in name.split("/")))


def _member(data: bytes, path: str, role: str) -> dict:
    return {"path": path, "bytes": len(data), "sha256": _sha(data), "role": role}


def _info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    return info


def read_worldpkg(path: str | Path) -> tuple[dict, dict[str, bytes]]:
    """Verify all archive members before returning any WIR records or resources."""
    try:
        with zipfile.ZipFile(path, "r", allowZip64=True) as archive:
            infos = archive.infolist()
            if not 2 <= len(infos) <= MAX_MEMBERS:
                raise StoreError("resource.package_count", "archive member count is out of bounds")
            names = [info.filename for info in infos]
            if len(names) != len(set(names)) or "manifest.json" not in names or "snapshot/records.jsonl" not in names:
                raise StoreError("resource.package_members", "duplicate or missing required archive member")
            total = 0
            for info in infos:
                name = info.filename
                mode = info.external_attr >> 16
                if not _safe_name(name) or info.is_dir() or (stat.S_IFMT(mode) not in {0, stat.S_IFREG}):
                    raise StoreError("resource.package_path", name)
                if info.flag_bits & 0x1:
                    raise StoreError("resource.package_encrypted", name)
                total += info.file_size
                if info.file_size > MAX_MEMBER_BYTES or total > MAX_TOTAL_BYTES:
                    raise StoreError("resource.package_size", name)
                if info.file_size and (not info.compress_size or info.file_size / info.compress_size > MAX_RATIO):
                    raise StoreError("resource.package_ratio", name)
            blobs = {info.filename: archive.read(info) for info in infos}
    except (zipfile.BadZipFile, OSError, EOFError) as exc:
        raise StoreError("resource.package_corrupt", str(exc)) from exc
    try:
        raw_manifest = blobs.pop("manifest.json")
        wrapper = json.loads(raw_manifest)
        if raw_manifest != canonical(wrapper):
            raise ValueError("manifest is not canonical JSON")
        if not isinstance(wrapper, dict) or set(wrapper) != {"package_format", "wir_manifest", "members"} or wrapper["package_format"] != FORMAT:
            raise ValueError("unsupported manifest format")
        entries = wrapper["members"]
        if not isinstance(entries, list) or len(entries) != len(blobs):
            raise ValueError("manifest member count mismatch")
        listed = {}
        for item in entries:
            if not isinstance(item, dict) or set(item) != {"path", "bytes", "sha256", "role"}:
                raise ValueError("invalid member description")
            name = item["path"]
            if not isinstance(name, str) or not _safe_name(name) or name in listed or name not in blobs:
                raise ValueError("manifest contains missing or duplicate member")
            role = "snapshot" if name == "snapshot/records.jsonl" else "asset" if name.startswith("assets/sha256/") else None
            if role is None or item != _member(blobs[name], name, role):
                raise ValueError("member size, role or checksum mismatch")
            listed[name] = True
        if set(listed) != set(blobs):
            raise ValueError("manifest omits an archive member")
        snapshot = blobs.pop("snapshot/records.jsonl")
        lines = snapshot.splitlines(keepends=True)
        if not lines or any(not line.endswith(b"\n") for line in lines):
            raise ValueError("records must be nonempty newline-terminated JSONL")
        records = []
        for line in lines:
            record = json.loads(line)
            if line != canonical(record) + b"\n":
                raise ValueError("noncanonical record")
            records.append(record)
        package = {"manifest": wrapper["wir_manifest"], "records": records}
        validate_package(package)
        assets = [r for r in records if r["record_type"] == "asset"]
        if package["manifest"]["package_mode"] != "self_contained" or len({r["uri"] for r in assets}) != len(blobs):
            raise ValueError("only self-contained archives with all referenced assets are supported")
        for asset in assets:
            expected = "assets/sha256/" + asset["content_hash"][7:]
            if asset["uri"] != expected or expected not in blobs or _sha(blobs[expected]) != asset["content_hash"]:
                raise ValueError("resource URI or content hash mismatch")
        revisions = [r for r in records if r["record_type"] == "revision"]
        if len(revisions) != 1 or not revisions[0]["committed"]:
            raise ValueError("snapshot must contain exactly one committed revision")
        return package, blobs
    except (UnicodeError, ValueError, KeyError, TypeError) as exc:
        raise StoreError("resource.package_invalid", str(exc)) from exc


def export_worldpkg(repository: Repository, world_id: str, destination: str | Path,
                    revision_id: str | None = None) -> str:
    package = repository.load(world_id, revision_id)
    assets = repository._resources(package)
    members: dict[str, bytes] = {
        "snapshot/records.jsonl": b"".join(canonical(record) + b"\n" for record in package["records"]),
    }
    for asset, data in assets:
        members[asset["uri"]] = data
    if len(members) + 1 > MAX_MEMBERS or sum(map(len, members.values())) > MAX_TOTAL_BYTES:
        raise StoreError("resource.package_size", "source exceeds exchange limits")
    wrapper = {"package_format": FORMAT, "wir_manifest": package["manifest"],
               "members": [_member(members[name], name, "snapshot" if name.startswith("snapshot/") else "asset") for name in sorted(members)]}
    members["manifest.json"] = canonical(wrapper)
    output = Path(destination).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise StoreError("resource.package_exists", "choose a new archive path; existing output is preserved")
    fd, temporary = tempfile.mkstemp(prefix=".worldpkg-", suffix=".staged", dir=output.parent)
    os.close(fd)
    try:
        with zipfile.ZipFile(temporary, "w", allowZip64=True) as archive:
            for name in sorted(members):
                with archive.open(_info(name), "w", force_zip64=True) as member:
                    member.write(members[name])
        checked, _ = read_worldpkg(temporary)
        if checked != package:
            raise StoreError("resource.package_roundtrip", "published archive differs from source snapshot")
        with open(temporary, "r+b") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return _sha(output.read_bytes())


def import_worldpkg(repository: Repository, path: str | Path) -> tuple[str, str]:
    """Import a verified snapshot as a new revision; never move the head on failure."""
    package, blobs = read_worldpkg(path)
    package = copy.deepcopy(package)
    world_id = package["manifest"]["world_id"]
    source_revision_id = package["manifest"]["revision_id"]
    parent = repository.head(world_id)
    package_hash = _sha(Path(path).read_bytes())
    new_revision_id = "revision_import_" + digest([package_hash, parent])[7:31]
    package["manifest"]["revision_id"] = new_revision_id
    package["manifest"]["package_id"] = "package_" + new_revision_id[9:]
    package["manifest"]["created_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    package["manifest"].setdefault("extensions", {})["import_source"] = {
        "revision_id": source_revision_id, "package_hash": package_hash, "source_schema_version": "0.1.0"}
    records = [r for r in package["records"] if r["record_type"] != "revision"]
    for record in records:
        if record["record_type"] == "constraint" and record["validation"]["checked_revision_id"] == source_revision_id:
            record["validation"]["checked_revision_id"] = new_revision_id
        if record["record_type"] == "export_report" and record["revision_id"] == source_revision_id:
            record["revision_id"] = new_revision_id
    hard_failures = sum(r["record_type"] == "constraint" and r["severity"] == "hard" and r["validation"]["state"] == "fail" for r in records)
    unknown = sum(r["record_type"] == "constraint" and r["validation"]["state"] == "unknown" for r in records)
    if hard_failures or unknown:
        raise StoreError("constraint.import_invalid", "only checked, valid source revisions can be imported")
    records.append({"record_type": "revision", "id": new_revision_id, "world_id": world_id,
        "parent_revision_ids": [parent] if parent else [], "created_at": package["manifest"]["created_at"],
        "author": "worldpkg-import/0.1", "change_set_hash": digest(records),
        "validation_summary": {"hard_failures": 0, "unknown_checks": 0}, "committed": True,
        "extensions": {"snapshot_manifest": copy.deepcopy(package["manifest"]),
                       "import_source_revision_id": source_revision_id, "source_package_hash": package_hash}})
    package["records"] = records
    validate_package(package)
    for content in blobs.values():
        repository.publish(content)
    repository.commit(package, parent)
    return world_id, new_revision_id
