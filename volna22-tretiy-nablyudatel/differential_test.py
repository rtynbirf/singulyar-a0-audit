#!/usr/bin/env python3
"""Дифференциальный стенд третьего наблюдателя (волна-22).

Три независимые реализации RFC 8785 на одном корпусе:
  1. jcs_third.py      — моя, с нуля (scripts/third_observer/jcs_third.py)
  2. auditor_jcs.py    — соседа-аудитора (район: singulyar-a0-audit/scripts)
  3. rfc8785 (pip)     — эталонная библиотека = ОРАКУЛ (только в тесте)

Вывод: по-байтовые расхождения per-кейс, классификация, вердикт.
Ключевой вопрос: сортировка ключей по UTF-16 code units vs code points
(астральные символы — зона известного расхождения).
"""
import importlib.util
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import jcs_third  # моя реализация

NEIGHBOR = Path("/home/z/my-project/w22_work/s0a/scripts/auditor_jcs.py")
spec = importlib.util.spec_from_file_location("auditor_jcs", NEIGHBOR)
neighbor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(neighbor)

import rfc8785 as oracle  # noqa: E402


def mine(v):
    return jcs_third.canonicalize(v)


def nb(v):
    return neighbor.dumps(v)


def orc(v):
    return oracle.dumps(v)


KEY_ALPHABET = [
    "a", "Z", "0", "1", " ", "\n", "\t", "\\", '"', "\u0080", "\u00fc",
    "\u20ac", "äöü", "Ж", "ЖЖ", "ж", "\u30a2", "\U0001f600",  # emoji: astral
    "\U0001f680", "\uffff", "\ufffd", "é", "e\u0301", "\u2f800",
    "\U0002f800",  # surrogate pair vs CJK ext-B
]


def gen_value(rng, depth):
    r = rng.random()
    if depth <= 0 or r < 0.28:
        kind = rng.randrange(8)
        if kind == 0:
            return rng.choice([True, False, None])
        if kind == 1:
            return rng.randrange(-2**53, 2**53)
        if kind == 2:
            return rng.choice([0, -0, 1, -1, 10**16, -(10**16), 2**53, 2**53 + 1])
        if kind == 3:
            return rng.choice([
                0.5, -0.5, 1.5e-7, 2e-3, 4.50, 1e-6, 9.999999999999999e-7,
                1e20, 1e21, 1.5e22, 1e30, 5e-324, 1.7976931348623157e308,
                3.141592653589793, 123.456, 1e16, 1e-5, 2.5, -1e21 + 1.0,
            ])
        if kind == 4:
            return rng.choice(["", "plain", "line\nbreak", "tab\there",
                               'q"uote', "back\\slash", "\u0000ctl" if False else "ctl",
                               "unicodé", "emoji \U0001f600!", "\u2028sep"])
        if kind == 5:
            return rng.random()
        if kind == 6:
            return float(rng.randrange(-10**6, 10**6))
        return rng.choice(["€uro", "ÀÉÎ", "жардыай"])
    if r < 0.62:
        return [gen_value(rng, depth - 1) for _ in range(rng.randrange(0, 5))]
    n = rng.randrange(1, 7)
    keys = rng.sample(KEY_ALPHABET, min(n, len(KEY_ALPHABET)))
    return {k: gen_value(rng, depth - 1) for k in keys}


def classify(a, b):
    """Первое расхождение между байтовыми выводами — человеческим языком."""
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            ctx_a = a[max(0, i - 30):i + 30].decode("utf-8", "replace")
            ctx_b = b[max(0, i - 30):i + 30].decode("utf-8", "replace")
            return f"pos {i}: …{ctx_a}… vs …{ctx_b}…"
    return f"len {len(a)} vs {len(b)}"


def main():
    rng = random.Random(20261116)
    N = 20000
    stats = {"mine_vs_oracle": 0, "neighbor_vs_oracle": 0,
             "neighbor_astral_only": 0}
    neighbor_diff_cases = []
    for i in range(N):
        case = gen_value(rng, rng.randrange(1, 5))
        try:
            m, o = mine(case), orc(case)
        except Exception as e:
            print(f"[{i}] ОШИБКА моей/оракула: {e!r} case={case!r:.120}")
            continue
        if m != o:
            stats["mine_vs_oracle"] += 1
            if stats["mine_vs_oracle"] <= 3:
                print(f"[{i}] МОЯ ≠ ОРАКУЛ: {classify(m, o)} case={json.dumps(case, ensure_ascii=False)[:100]}")
        try:
            nb_o = nb(case)
        except Exception as e:
            nb_o = None
        if nb_o != o:
            stats["neighbor_vs_oracle"] += 1
            has_astral = any(ord(ch) > 0xFFFF for ch in json.dumps(case, ensure_ascii=False))
            if has_astral:
                stats["neighbor_astral_only"] += 1
            if len(neighbor_diff_cases) < 5:
                diff = classify(nb_o, o) if nb_o is not None else f"exception"
                neighbor_diff_cases.append((i, has_astral, diff))
    print(f"\nкорпус: {N} кейсов")
    print(f"моя   vs оракул: расхождений {stats['mine_vs_oracle']}")
    print(f"сосед vs оракул: расхождений {stats['neighbor_vs_oracle']} "
          f"(из них с астральными символами: {stats['neighbor_astral_only']})")
    for i, ha, d in neighbor_diff_cases:
        print(f"  [{i}] astral={ha} → {d}")
    verdict = "PASS" if stats["mine_vs_oracle"] == 0 else "FAIL"
    print(f"\nВЕРДИКТ моей реализации против оракула: {verdict}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
