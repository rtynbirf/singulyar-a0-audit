# -*- coding: utf-8 -*-
"""python -m singulyar_host [demo|experiments|constitution|selftest] """
from __future__ import annotations

import json
import sys

from .constitution import Constitution


def _load_experiments():
    from .experiments import (h007_orthogonality, h008_attestation, h009_partition,  # noqa
                              h010_h011_continuity, h012_space, h013_non_appropriation,
                              h014_authority_possibility, h015_meta_capture,
                              h016_evidence_failure, h017_guarantee_independence,
                              h018_hidden_complexity, h019_staged_activation,
                              h019b_capabilities_removal, h020b_naznachenie_renaznachenie, h020_a0_admission_gate)
    from .experiments.base import run_all
    return run_all()


def cmd_experiments(export: str = "") -> int:
    res = _load_experiments()
    print(f"{'ID':<7}{'Эксперимент':<78}Вердикт")
    for r in res:
        print(f"{r.experiment_id:<7}{r.title[:76]:<78}{'PASS' if r.passed else 'FAIL'}")
    ok = all(r.passed for r in res)
    print(f"ИТОГО: {sum(r.passed for r in res)}/{len(res)} PASS")
    if export:
        with open(export, "w", encoding="utf-8") as f:
            json.dump([r.__dict__ for r in res], f, ensure_ascii=False, indent=2)
    return 0 if ok else 1


def cmd_constitution() -> int:
    c = Constitution.load()
    print(f"{c.name} v{c.version}\n{c.formula}\n")
    for a in c.articles.values():
        print(f"[{a.id}] {a.title}{' (неотменяемая)' if a.non_derogable else ''}\n    {a.statement}")
    print("\nРазличения:", "; ".join(c.distinctions))
    print("Открытые вопросы:", *["- " + q for q in c.open_questions], sep="\n")
    return 0


def main(argv=None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    cmd = a[0] if a else "selftest"
    if cmd == "demo":
        from .demo import run_demo
        return 0 if run_demo() else 1
    if cmd == "experiments":
        return cmd_experiments(a[1] if len(a) > 1 else "")
    if cmd == "constitution":
        return cmd_constitution()
    if cmd == "selftest":
        from .demo import run_demo
        d = run_demo(False)
        e = cmd_experiments()
        print("демо:", "OK" if d else "FAIL")
        return 0 if d and e == 0 else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
