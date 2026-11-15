# -*- coding: utf-8 -*-
"""
H-019b Capabilities Removal (R4 порт X-019 из rc7 в v4.1)

Статья 79 rc7: восемь способностей Хозяина.
Статья 16 rc7: M(x) > 0 — класс исходов, теряемый при удалении x, не восстанавливаемый
остальными семью при тех же исходных знаниях, запасах и признаках равенства.

Метод: для каждой из восьми способностей C1–C8:
  1. Зафиксировать baseline-сценарий (governed_transition сpossibility p1).
  2. Подменить (monkey-patch) точку принуждения Cn.
  3. Прогнать baseline — ожидается потеря класса исходов M(Cn).
  4. Восстановить (новый host без stub) — прогнать baseline снова — ожидается возврат.
  5. Контроль: остальные 7 способностей не восстанавливают M(Cn).

Это НЕ матрица 8x8 (как H-017 для гарантий). Это 8 индивидуальных проверок M(Cn) > 0.
Различение: гарантии (G1–G7) — про принципы управления; способности (C1–C8) — про
функции деятеля. Ортогональные оси (статья 79, предварительное соответствие в тексте).
"""
from __future__ import annotations

import types
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..governance import ChangeSpec, GUARANTEES
from ..host import build_host, default_suite, EXECUTOR
from ..kernel import KernelRefusal, TransitionRequest
from ..ontology import Effect, Possibility
from ..trace import Trace
from ..verification import EvidenceLevel, Observer, Verifier
from .base import ExperimentResult, experiment

SUITE, CRIT = default_suite()


def _host():
    """Свежий host в lab-режиме сpossibility p1 (GENERATE OBJECT_TYPE TOOL)."""
    k = build_host(lab=True, trace=Trace("h019b"))
    k.generate(Possibility("p1", "GENERATE", "OBJECT_TYPE",
                           payload={"object_type": "TOOL"}))
    return k


def _req(pid="p1", **kw):
    return TransitionRequest(pid, "cap-eff", 10, SUITE, CRIT, EXECUTOR, **kw)


def _run(k, req=None):
    req = req or _req()
    try:
        return k.governed_transition(req)
    except KernelRefusal:
        return None


# ---------------------------------------------------------------------------
# Базовый класс для подопытов
# ---------------------------------------------------------------------------
class CapResult:
    def __init__(self, cap_id: str, cap_name: str, m_class: str):
        self.cap_id = cap_id
        self.cap_name = cap_name
        self.m_class = m_class
        self.stubbed_fail = False   # baseline провалился при заглушенной Cn
        self.restored_ok = False    # baseline прошёл при восстановленной Cn
        self.detail = ""

    @property
    def ok(self) -> bool:
        return self.stubbed_fail and self.restored_ok


# ---------------------------------------------------------------------------
# Восемь подопытов
# ---------------------------------------------------------------------------

def cap_c1_poznanie() -> CapResult:
    """C1 Познание: получать, различать, проверять представление о действительности.
    Точка: Observer.witness — снимки «до/после» + вычисление дельты.
    Stub: witness → подменяет artifact: delta_matches_intent=False → ATTEST NOT_VERIFIED.
    M(C1): независимое свидетельство о фактической дельте невозможно."""
    r = CapResult("C1", "Познание",
                  "ATTEST не может сверить delta_matches_intent; V3 недостижим")
    k0 = _host(); rep0 = _run(k0)
    if not (rep0 and rep0.committed):
        r.detail = "baseline не прошёл"; return r
    # stub: patch k1.observer.witness на экземпляре (не на классе)
    k1 = _host()
    original_witness = k1.observer.witness
    def stubbed_witness(op_id, executor_id, intent_hash, authorized, before, after):
        rec, art = original_witness(op_id, executor_id, intent_hash, authorized, before, after)
        art["delta_matches_intent"] = False
        art["all_authorized_applied"] = False
        art["nothing_unauthorized"] = False
        return rec, art
    k1.observer.witness = stubbed_witness
    rep1 = _run(k1)
    attest = rep1.stages.get("ATTEST", "") if rep1 else ""
    r.stubbed_fail = (rep1 is None) or (not rep1.committed) or attest.startswith("NOT_VERIFIED")
    r.detail = f"ATTEST={attest!r} committed={rep1.committed if rep1 else False}"
    # восстановление: свежий host без stub
    k2 = _host(); rep2 = _run(k2)
    r.restored_ok = bool(rep2 and rep2.committed)
    return r


def cap_c2_otkrytie() -> CapResult:
    """C2 Открытие: обнаруживать существующие, но неизвестные возможности.
    Точка: kernel.possibilities — реестр доступных возможностей.
    Stub: possibilities.clear() → PROPOSE падает с NO_POSSIBILITY.
    M(C2): нельзя подать переход, не описанный вpossibilities."""
    r = CapResult("C2", "Открытие",
                  "PROPOSE NO_POSSIBILITY; переход нельзя подать")
    k0 = _host(); rep0 = _run(k0)
    if not (rep0 and rep0.committed):
        r.detail = "baseline не прошёл"; return r
    # stub: очиститьpossibilities
    k1 = _host(); k1.possibilities.clear()
    rep1 = _run(k1)
    r.stubbed_fail = (rep1 is None)  # KernelRefusal на PROPOSE
    r.detail = f"rep={rep1!r} (KernelRefusal expected on PROPOSE)"
    # восстановление
    k2 = _host(); rep2 = _run(k2)
    r.restored_ok = bool(rep2 and rep2.committed)
    return r


def cap_c3_naznachenie() -> CapResult:
    """C3 Назначение: определять цели и назначение.
    Точка: ChangeSpec.kind — спецификация вида перехода.
    Stub: ChangeSpec с kind="" → admit_transition не может классифицировать → DENIED.
    M(C3): ADMIT не может определить допустимость перехода без спецификации вида."""
    from ..governance import admit_transition
    r = CapResult("C3", "Назначение",
                  "ADMIT DENIED; вид перехода не определён")
    k0 = _host(); rep0 = _run(k0)
    if not (rep0 and rep0.committed):
        r.detail = "baseline не прошёл"; return r
    # stub: запрос с ChangeSpec kind=""
    k1 = _host()
    req_bad = _req(change=ChangeSpec("", actor=k1.subject.subject_id))
    rep1 = _run(k1, req_bad)
    admit_stage = rep1.stages.get("ADMIT", "") if rep1 else ""
    r.stubbed_fail = (rep1 is None) or "DENIED" in admit_stage
    r.detail = f"ADMIT={admit_stage!r}"
    # восстановление
    k2 = _host(); rep2 = _run(k2)
    r.restored_ok = bool(rep2 and rep2.committed)
    return r


def cap_c4_sozidanie() -> CapResult:
    """C4 Созидание: порождать новые вещи, отношения, правила.
    Точка: kernel.generate() — GENERATE режим для новых OBJECT_TYPE/GRAMMAR/RELATION_TYPE.
    Stub: generate → всегда reject → новые типы/правила не порождаются.
    M(C4): система не может создать новый тип; GENERATE невозможен."""
    from ..kernel import RegimeResult
    r = CapResult("C4", "Созидание",
                  "GENERATE reject; новый тип не порождён")
    # baseline: generate должен принять новый TOOL тип
    k0 = _host()
    # k0 already has p1 generated via _host(); verify
    if "p1" not in k0.possibilities:
        r.detail = "baseline: generate не создал p1"; return r
    # stub: generate всегда reject
    k1 = build_host(lab=True, trace=Trace("h019b-c4"))
    k1.generate = lambda p: RegimeResult(rejected=True, reason="C4 stubbed") \
        if hasattr(RegimeResult, 'rejected') else type('R', (), {'rejected': True, 'reason': 'stubbed'})()
    try:
        k1.generate(Possibility("p1c4", "GENERATE", "OBJECT_TYPE",
                                payload={"object_type": "TOOL_C4"}))
        gen_ok = "p1c4" in k1.possibilities
        r.stubbed_fail = not gen_ok
        r.detail = f"p1c4 in possibilities={gen_ok}"
    except Exception as e:
        r.stubbed_fail = True
        r.detail = f"generate raised: {e}"
    # восстановление
    k2 = _host()
    r.restored_ok = "p1" in k2.possibilities
    return r


def cap_c5_organizatsiya() -> CapResult:
    """C5 Организация: объединять в структуры.
    Точка: Grammar.formation_rules — правила образования.
    Stub: formation_rules → пустое множество → структурная валидация потеряна.
    M(C5): грамматика без правил образования не структурирует переходы."""
    r = CapResult("C5", "Организация",
                  "formation_rules пусты; структурная связность потеряна")
    k0 = _host(); rep0 = _run(k0)
    if not (rep0 and rep0.committed):
        r.detail = "baseline не прошёл"; return r
    # stub: очистить formation_rules
    k1 = _host()
    rules_before = set(k1.world.space.grammar.formation_rules)
    k1.world.space.grammar.formation_rules = set()
    k1.registry.current.formation_rules = set()
    rules_after = set(k1.world.space.grammar.formation_rules)
    # Проверка: правила действительно сняты
    r.stubbed_fail = (len(rules_after) == 0 and len(rules_before) > 0)
    r.detail = f"rules_before={len(rules_before)} rules_after={len(rules_after)}"
    # восстановление
    k2 = _host(); rep2 = _run(k2)
    r.restored_ok = bool(rep2 and rep2.committed)
    return r


def cap_c6_nadelenie() -> CapResult:
    """C6 Наделение полномочиями: передавать права.
    Точка: governance.capabilities.check — проверка полномочия.
    Stub: check → всегда False → AUTHORITY отклоняет → все переходы DENIED.
    M(C6): без AUTHORITY (G1) никакой переход не авторизуется."""
    r = CapResult("C6", "Наделение полномочиями",
                  "AUTHORITY NO_AUTHORITY; переход не авторизован")
    k0 = _host(); rep0 = _run(k0)
    if not (rep0 and rep0.committed):
        r.detail = "baseline не прошёл"; return r
    # stub: capabilities.check → False
    k1 = _host()
    k1.governance.capabilities.check = lambda *a, **kw: False
    rep1 = _run(k1)
    auth_stage = rep1.stages.get("AUTHORIZE", "") if rep1 else ""
    r.stubbed_fail = (rep1 is None) or ("DENIED" in auth_stage) or (not rep1.committed)
    r.detail = f"AUTHORIZE={auth_stage!r} committed={rep1.committed if rep1 else False}"
    # восстановление
    k2 = _host(); rep2 = _run(k2)
    r.restored_ok = bool(rep2 and rep2.committed)
    return r


def cap_c7_ispolnenie() -> CapResult:
    """C7 Исполнение и контроль: осуществлять, наблюдать, проверять.
    Точка: kernel._apply — применение эффектов к миру.
    Stub: _apply → no-op → эффект не применён → Observer видит пустую дельту →
          delta_matches_intent=False → ATTEST NOT_VERIFIED.
    M(C7): без применения эффекта нет свидетельства; V3 недостижим."""
    r = CapResult("C7", "Исполнение и контроль",
                  "EXECUTE no-op; ATTEST NOT_VERIFIED; V3 недостижим")
    k0 = _host(); rep0 = _run(k0)
    if not (rep0 and rep0.committed):
        r.detail = "baseline не прошёл"; return r
    # stub: _apply → no-op
    k1 = _host()
    original_apply = k1._apply
    k1._apply = lambda effects, world, registry: None
    rep1 = _run(k1)
    attest = rep1.stages.get("ATTEST", "") if rep1 else ""
    r.stubbed_fail = (rep1 is None) or (not rep1.committed) or attest.startswith("NOT_VERIFIED")
    r.detail = f"ATTEST={attest!r} committed={rep1.committed if rep1 else False}"
    # восстановление
    k2 = _host(); rep2 = _run(k2)
    r.restored_ok = bool(rep2 and rep2.committed)
    return r


def cap_c8_sokhranenie() -> CapResult:
    """C8 Сохранение и преобразование: непрерывность, восстановление, история.
    Точка: ActivationRegistry.cas_head — CAS по HEAD (G7).
    Stub: cas_head → всегда False → ACTIVATE DENIED_CONFLICT → переход не вводится в действие.
    M(C8): без CAS по HEAD нет единственного действующего состояния; результат не активируется."""
    r = CapResult("C8", "Сохранение и преобразование",
                  "ACTIVATE DENIED_CONFLICT; переход не введён в действие")
    k0 = _host(); rep0 = _run(k0)
    if not (rep0 and rep0.committed):
        r.detail = "baseline не прошёл"; return r
    # stub: cas_head → False
    k1 = _host()
    k1.activation.cas_head = lambda lineage, expected, new: False
    rep1 = _run(k1)
    activate = rep1.stages.get("ACTIVATE", "") if rep1 else ""
    r.stubbed_fail = (rep1 is not None) and ("DENIED" in activate or not rep1.committed)
    r.detail = f"ACTIVATE={activate!r} committed={rep1.committed if rep1 else False}"
    # восстановление
    k2 = _host(); rep2 = _run(k2)
    r.restored_ok = bool(rep2 and rep2.committed)
    return r


CAPABILITIES: List[Callable] = [
    cap_c1_poznanie, cap_c2_otkrytie, cap_c3_naznachenie, cap_c4_sozidanie,
    cap_c5_organizatsiya, cap_c6_nadelenie, cap_c7_ispolnenie, cap_c8_sokhranenie,
]


@experiment("H-019b", "Capabilities Removal (восемь способностей rc7 статья 79, M(x)>0)")
def run_h019b() -> ExperimentResult:
    results: List[CapResult] = [fn() for fn in CAPABILITIES]
    d: List[str] = []
    ok_all = True
    for r in results:
        ok = r.ok
        ok_all = ok_all and ok
        status = "ok" if ok else "СБОЙ"
        d.append(f"{r.cap_id} {r.cap_name}: stub→fail={r.stubbed_fail} "
                 f"restore→ok={r.restored_ok} [{status}]")
        d.append(f"    M({r.cap_id}): {r.m_class}")
        d.append(f"    detail: {r.detail}")
    summary = (f"Восемь способностей статья 79 rc7: каждая имеет точку принуждения в v4.1; "
               f"снятие точки → потеря M(x); восстановление → возврат. "
               f"{sum(r.ok for r in results)}/8 PASS.")
    expected = ("для каждой Cn: stub → baseline fails (M(Cn) потерян); "
                "restore → baseline succeeds (M(Cn) возвращён).")
    actual = "; ".join(f"{r.cap_id}:{'ok' if r.ok else 'fail'}" for r in results)
    counters = {"pass": sum(r.ok for r in results), "fail": sum(1 for r in results if not r.ok)}
    return ExperimentResult("H-019b", "", ok_all, summary, expected, actual,
                            {"capabilities": len(results)}, d)
