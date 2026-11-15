#!/usr/bin/env python3
"""A8: independent manifest verifier, written by the auditor.
Does NOT reuse INTEGRITY_CHECK.py from the package. Implements its own walk, hash,
path safety, and excluded-file rules; compares against MANIFEST.json.
"""
import hashlib, json, os, sys
from pathlib import Path, PurePosixPath

MANIFEST = "MANIFEST.json"
EXCLUDED_DIRS = {"__pycache__"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def is_excluded(rel_posix: str) -> bool:
    parts = rel_posix.split("/")
    if any(p in EXCLUDED_DIRS for p in parts[:-1]):
        return True
    return Path(rel_posix).suffix.lower() in EXCLUDED_SUFFIXES


def safe_relpath(raw: str) -> bool:
    """Reject absolute, drive, traversal, empty, NUL."""
    if not isinstance(raw, str) or not raw or "\x00" in raw:
        return False
    p = PurePosixPath(raw)
    if p.is_absolute():
        return False
    if any(part in ("", "..", ".") for part in p.parts):
        # '.' is technically harmless but the auditor rejects it as suspicious
        return False
    return True


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(root: str) -> int:
    root = Path(root).resolve()
    mp = root / MANIFEST
    errors = []

    if not mp.is_file():
        print(f"[MANIFEST_MISSING] {mp}", file=sys.stderr)
        return 1
    try:
        m = json.loads(mp.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[MANIFEST_INVALID] {e}", file=sys.stderr)
        return 1
    if not isinstance(m, dict) or not isinstance(m.get("files"), list):
        print("[MANIFEST_SCHEMA] files must be an array", file=sys.stderr)
        return 1

    listed = []
    listed_set = set()
    for i, entry in enumerate(m["files"]):
        if not isinstance(entry, dict) or {"path", "sha256"} - set(entry):
            errors.append(f"[MANIFEST_ENTRY_INVALID] index={i}")
            continue
        rel = entry["path"]
        digest = entry["sha256"]
        if not safe_relpath(rel):
            errors.append(f"[MANIFEST_UNSAFE_PATH] {rel!r}")
            continue
        if rel == MANIFEST:
            errors.append(f"[MANIFEST_SELF_REFERENCE] {rel}")
            continue
        if is_excluded(rel):
            errors.append(f"[MANIFEST_LISTS_EXCLUDED] {rel}")
            continue
        if not isinstance(digest, str) or len(digest) != 64 or any(
            c not in "0123456789abcdef" for c in digest.lower()
        ):
            errors.append(f"[MANIFEST_HASH_FORMAT] {rel}")
            continue
        if rel in listed_set:
            errors.append(f"[MANIFEST_DUPLICATE_PATH] {rel}")
            continue
        listed.append(rel)
        listed_set.add(rel)

        target = root.joinpath(*rel.split("/"))
        try:
            resolved = target.resolve(strict=True)
        except FileNotFoundError:
            errors.append(f"[FILE_MISSING] {rel}")
            continue
        except (OSError, ValueError) as e:
            errors.append(f"[FILE_READ_ERROR] {rel}: {e}")
            continue
        if os.path.commonpath((str(root), str(resolved))) != str(root):
            errors.append(f"[MANIFEST_PATH_ESCAPE] {rel}")
            continue
        if target.is_symlink() or not resolved.is_file():
            errors.append(f"[MANIFEST_NOT_REGULAR_FILE] {rel}")
            continue
        actual = sha256_file(resolved)
        if actual != digest.lower():
            errors.append(f"[HASH_MISMATCH] {rel} actual={actual}")

    # Independent walk for actual files
    actual_files = set()
    for p in root.rglob("*"):
        rel_posix = p.relative_to(root).as_posix()
        if p.is_symlink():
            errors.append(f"[PACKAGE_SYMLINK] {rel_posix}")
            continue
        if is_excluded(rel_posix):
            continue
        if p.is_file() and rel_posix != MANIFEST:
            actual_files.add(rel_posix)

    missing = actual_files - listed_set
    extra = listed_set - actual_files
    if missing:
        errors.append(f"[MANIFEST_OMITS_FILES] {sorted(missing)}")
    if extra:
        errors.append(f"[MANIFEST_REFERENCES_UNKNOWN_FILES] {sorted(extra)}")

    if errors:
        print("\n".join(errors))
        return 1
    print(f"[AUDITOR_MANIFEST_OK] {len(listed)} files verified")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: auditor_manifest_verify.py PACKAGE_ROOT", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
