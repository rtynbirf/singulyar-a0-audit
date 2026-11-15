#!/usr/bin/env python3
"""Единая проверка синтеза. Каждый шаг — реальный запуск; код возврата != 0 при любом провале."""
import hashlib, json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
A0 = ROOT / "a0_standard" / "A0_STANDARD_v0.2.5"
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
EXCL = {"__pycache__", ".pytest_cache"}

def run(label, cmd, cwd, expect):
    p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, env=ENV)
    out = p.stdout + p.stderr
    ok = p.returncode == 0 and expect in out
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if not ok: print(out[-1500:])
    return ok

def synth_manifest_ok():
    m = json.loads((ROOT / "SYNTHESIS_MANIFEST.json").read_text(encoding="utf-8"))
    listed = {e["path"]: e["sha256"] for e in m["files"]}
    actual = {}
    for p in ROOT.rglob("*"):
        rel = p.relative_to(ROOT).as_posix()
        if p.is_file() and rel != "SYNTHESIS_MANIFEST.json" and not (set(p.relative_to(ROOT).parts) & EXCL) \
                and not rel.startswith("results/") and p.suffix not in (".pyc", ".pyo"):
            actual[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    bad = [k for k in listed if actual.get(k) != listed[k]]
    extra, missing = sorted(set(actual) - set(listed)), sorted(set(listed) - set(actual))
    ok = not bad and not extra and not missing
    print(f"[{'PASS' if ok else 'FAIL'}] SYNTHESIS_MANIFEST ({len(listed)} files)")
    if not ok: print("mismatch:", bad[:5], "extra:", extra[:5], "missing:", missing[:5])
    return ok

def main():
    py = sys.executable
    steps = [
        run("A0: INTEGRITY_CHECK (пакет A0 не изменён)", [py, "-B", "INTEGRITY_CHECK.py", "."], A0, "[INTEGRITY_OK]"),
        run("A0: самотесты 7/7", [py, "-B", "-m", "unittest", "discover", "-s", "tests/self"], A0, "OK"),
        run("A0: VALIDATOR", [py, "-B", "VALIDATOR.py", "."], A0, "[VALIDATOR_OK]"),
        run("A0: негативные тесты 11/11", [py, "-B", "run_negative_tests.py", "."], A0, "[NEGATIVE_TESTS] 11/11"),
        run("HOST: selftest (демо + 16 экспериментов)", [py, "-B", "-m", "singulyar_host", "selftest"], ROOT, "ИТОГО: 16/16 PASS"),
        run("HOST: pytest", [py, "-B", "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider"], ROOT, "passed"),
        synth_manifest_ok(),
    ]
    print("ИТОГО:", "ВСЁ PASS" if all(steps) else "ЕСТЬ FAIL")
    return 0 if all(steps) else 1

if __name__ == "__main__":
    sys.exit(main())
