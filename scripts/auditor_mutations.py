#!/usr/bin/env python3
"""Section 3 of AUDIT_PROTOCOL.md: auditor's own mutation tests.

The auditor adds mutations of his own invention (not present among the 11
negative tests in run_negative_tests.py) and runs the package tools against
mutated copies, recording the actual code returned.

Each mutation runs on a fresh copy of the package; tools are run with `python -B`
via the auditor venv. Each test records PASS/FAIL based on whether the expected
error code appears in the tool output AND exit code is non-zero.

Min required by protocol: 5. Provided here: 8.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

AUD = Path("/home/z/my-project/scripts/audit_a0")
PKG_SRC = AUD / "pkg" / "A0_STANDARD_v0.2.5"
VENV_PY = AUD / "venv" / "bin" / "python"
LOG_DIR = AUD / "logs" / "mutations"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def fresh_copy() -> Path:
    td = tempfile.mkdtemp(prefix="a0-mut-")
    dst = Path(td) / "package"
    shutil.copytree(PKG_SRC, dst, dirs_exist_ok=False)
    # remove any pycache that copy may have produced
    for p in list(dst.rglob("__pycache__")):
        shutil.rmtree(p)
    return dst


def run_validator(pkg: Path) -> tuple[int, str]:
    p = subprocess.run(
        [str(VENV_PY), "-B", str(pkg / "VALIDATOR.py"), str(pkg)],
        capture_output=True, text=True, cwd=str(pkg),
    )
    return p.returncode, (p.stdout + "\n" + p.stderr)


def run_integrity(pkg: Path) -> tuple[int, str]:
    p = subprocess.run(
        [str(VENV_PY), "-B", str(pkg / "INTEGRITY_CHECK.py"), str(pkg)],
        capture_output=True, text=True, cwd=str(pkg),
    )
    return p.returncode, (p.stdout + "\n" + p.stderr)


def check(name: str, expected: str, actual_out: str, rc: int, log_path: Path) -> bool:
    log_path.write_text(f"expected: {expected}\nexit: {rc}\n--- output ---\n{actual_out}\n",
                        encoding="utf-8")
    ok = (rc != 0) and (expected in actual_out)
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name} expected={expected} exit={rc}")
    if not ok:
        print("  actual output (first 500 chars):")
        print("  " + actual_out[:500].replace("\n", "\n  "))
    return ok


# --- mutation functions ---

def mut_rubric_text_no_rehash(pkg: Path):
    """§3.1: change rubric text without recomputing freeze_sha256.
    Expected: [HASH_MISMATCH] from VALIDATOR.py"""
    ts_path = pkg / "TASK_SET.v0.2.2.json"
    ts = json.loads(ts_path.read_text(encoding="utf-8"))
    # Modify a rubric text field on T01 (any task)
    for t in ts["tasks"]:
        if t["task_id"] == "T01":
            t["quality_rubric"]["full"] = (
                t["quality_rubric"]["full"] + " АУДИТОР_ВМЕШАЛСЯ"
            )
            break
    ts_path.write_text(json.dumps(ts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def mut_delete_sample(pkg: Path):
    """§3.2: delete one sample file.
    Expected: [FILE_MISSING] from VALIDATOR.py"""
    (pkg / "SAMPLE_PASSPORT.json").unlink()


def mut_plant_symlink(pkg: Path):
    """§3.3: plant a symlink in the package.
    Expected: [PACKAGE_SYMLINK] from INTEGRITY_CHECK.py"""
    target = pkg / "VALIDATOR.py"
    link = pkg / "evil_link.py"
    os.symlink(str(target), str(link))


def mut_extra_file(pkg: Path):
    """§3.4: add an extra file after manifest was built.
    Expected: [MANIFEST_OMITS_FILES] from INTEGRITY_CHECK.py"""
    (pkg / "auditor_injected.txt").write_text("hello from auditor\n", encoding="utf-8")


def mut_corrupt_datetime(pkg: Path):
    """§3.5: corrupt a date-time in a sample.
    Expected: [SCHEMA_VIOLATION] from VALIDATOR.py"""
    p = pkg / "SAMPLE_PASSPORT.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    data["created_at"] = "2026-11-15 12:00:00"  # space instead of 'T' → not RFC 3339
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def mut_zero_freeze_hash(pkg: Path):
    """§4 checklist: validator must reject 64-zero freeze_sha256.
    Expected: [HASH_MISMATCH] from VALIDATOR.py"""
    ts_path = pkg / "TASK_SET.v0.2.2.json"
    ts = json.loads(ts_path.read_text(encoding="utf-8"))
    ts["freeze_sha256"] = "0" * 64
    ts_path.write_text(json.dumps(ts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def mut_manifest_corrupt_hash(pkg: Path):
    """Auditor's extra: corrupt one sha256 in MANIFEST.json.
    Expected: [HASH_MISMATCH] from INTEGRITY_CHECK.py"""
    mp = pkg / "MANIFEST.json"
    m = json.loads(mp.read_text(encoding="utf-8"))
    m["files"][0]["sha256"] = "0" * 64
    mp.write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def mut_manifest_list_pycache(pkg: Path):
    """Auditor's extra: add a __pycache__ entry to MANIFEST.json.
    Expected: [MANIFEST_LISTS_EXCLUDED] from INTEGRITY_CHECK.py"""
    mp = pkg / "MANIFEST.json"
    m = json.loads(mp.read_text(encoding="utf-8"))
    m["files"].append({"path": "__pycache__/x.pyc", "sha256": "0" * 64})
    mp.write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# (name, mutator, runner, expected_code)
CASES = [
    ("rubric_text_no_rehash",   mut_rubric_text_no_rehash,    run_validator, "[HASH_MISMATCH]"),
    ("delete_sample_passport",  mut_delete_sample,            run_validator, "[FILE_MISSING]"),
    ("plant_symlink",           mut_plant_symlink,            run_integrity, "[PACKAGE_SYMLINK]"),
    ("extra_file_after_manifest", mut_extra_file,             run_integrity, "[MANIFEST_OMITS_FILES]"),
    ("corrupt_datetime_sample", mut_corrupt_datetime,         run_validator, "[SCHEMA_VIOLATION]"),
    ("zero_freeze_hash",        mut_zero_freeze_hash,         run_validator, "[HASH_MISMATCH]"),
    ("manifest_corrupt_hash",   mut_manifest_corrupt_hash,    run_integrity, "[HASH_MISMATCH]"),
    ("manifest_lists_pycache",  mut_manifest_list_pycache,    run_integrity, "[MANIFEST_LISTS_EXCLUDED]"),
]


def main() -> int:
    fails = 0
    for name, mutator, runner, expected in CASES:
        pkg = fresh_copy()
        try:
            mutator(pkg)
            rc, out = runner(pkg)
            log_path = LOG_DIR / f"{name}.log"
            ok = check(name, expected, out, rc, log_path)
            if not ok:
                fails += 1
        finally:
            shutil.rmtree(pkg.parent, ignore_errors=True)
    print(f"[AUDITOR_MUTATIONS] {len(CASES) - fails}/{len(CASES)}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
