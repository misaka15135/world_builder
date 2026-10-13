"""Read-only credential/size check of staged files and unpublished Git objects.

Only paths/object IDs and rule names are printed, never matched secret values.
This is a scoped safety check, not a guarantee that all credential types are found.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RULES = {
    "provider_key": rb"\bsk-[A-Za-z0-9_-]{20,}\b",
    "github_token": rb"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b",
    "private_key": rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----",
}
# Reviewed 23-character synthetic token in the HTTP error-redaction unit test.
# Exact token digest and exact file only; known-key matching is never exempted.
TEST_TOKEN_DIGEST = "b85ff62d9b2787f5abf73a088d44e33f0122e6f4ee1c3d80cea0eca24bc8dfdb"


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--key-file", type=Path, help="Optional known key; first line only, never printed")
    args = parser.parse_args()
    patterns = {name: re.compile(pattern) for name, pattern in RULES.items()}
    known_key = None
    if args.key_file:
        with args.key_file.open("rb") as stream:
            encoding = "utf-16" if stream.read(2) in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig"
        with args.key_file.open(encoding=encoding) as stream:
            known_key = stream.readline().strip().encode("utf-8")
        if not known_key:
            parser.error("Known-key file is empty")
    findings: list[dict[str, str]] = []

    def scan(label: str, data: bytes, *, expand: bool = True) -> None:
        for name, pattern in patterns.items():
            matches = pattern.findall(data)
            if name == "provider_key" and label in {"tests/test_agent_pipeline.py", "history:tests/test_agent_pipeline.py"}:
                matches = [value for value in matches if hashlib.sha256(value).hexdigest() != TEST_TOKEN_DIGEST]
            if matches:
                findings.append({"file_or_object": label, "rule": name})
        if known_key and known_key in data:
            findings.append({"file_or_object": label, "rule": "known_key"})
        if expand and zipfile.is_zipfile(io.BytesIO(data)):
            with zipfile.ZipFile(io.BytesIO(data)) as package:
                for entry in package.infolist():
                    if entry.is_dir():
                        continue
                    if entry.file_size > 20 * 1024 * 1024:
                        findings.append({"file_or_object": label, "rule": "large_archive_entry"})
                    else:
                        scan(label + "::" + entry.filename, package.read(entry), expand=False)

    paths = git("diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR").split(b"\0")
    staged = [p.decode("utf-8") for p in paths if p]
    total = 0
    for path in staged:
        parts = Path(path).parts
        if any(part in {"Library", "Temp", "Logs", "UserSettings", ".venv", "__pycache__"} for part in parts) or Path(path).name.startswith(".env") or Path(path).name in {"api.txt", "agents.local.json"}:
            findings.append({"file_or_object": path, "rule": "local_only_path"})
        data = git("show", ":" + path)
        total += len(data)
        if len(data) > 20 * 1024 * 1024:
            findings.append({"file_or_object": path, "rule": "large_staged_file"})
        scan(path, data)
    objects = git("rev-list", "--objects", args.base + "..HEAD").splitlines()
    # Also inspect commit messages; Git batch protocol preserves binary blobs.
    if objects:
        proc = subprocess.Popen(["git", "cat-file", "--batch"], cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        assert proc.stdin is not None and proc.stdout is not None
        for record in objects:
            oid, _, name = record.partition(b" ")
            proc.stdin.write(oid + b"\n")
            proc.stdin.flush()
            header = proc.stdout.readline().split()
            size = int(header[2])
            data = proc.stdout.read(size)
            proc.stdout.read(1)
            if header[1] in {b"blob", b"commit"}:
                scan("history:" + (name.decode("utf-8") if name else oid.decode()), data)
        proc.stdin.close()
        if proc.wait() != 0:
            raise RuntimeError("Git object inspection failed")
    print(json.dumps({"staged_files": len(staged), "staged_bytes": total,
                      "unpublished_objects": len(objects), "findings": findings}, ensure_ascii=False, indent=2))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
