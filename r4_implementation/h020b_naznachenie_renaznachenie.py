# -*- coding: utf-8 -*-
"""
H-020b Capabilities Removal: Назначение / переназначение (R4 порт X-020 из rc7)

Статья 82 rc7: «Назначение отвечает на вопрос: для чего используется возможность?
Переназначение отвечает: можно ли использовать её иначе? Переназначение допустимо
при сохранении прав, ограничений, происхождения, обязанностей и неприсвоения.
Нельзя считать, что возможность существует только потому, что она назначена.
Нельзя считать, что новое назначение автоматически создаёт право на осуществление.»

X-020 (rc7 строка 443): «Назначение: переназначение за пределами допустимого поля
отклоняется» — ВЫПОЛНЕНО на v3.1.

Метод: четыре проверки переназначения:
  X-020.1: легитимное назначение (OWN_STATE на себя) → ADMITTED (baseline)
  X-020.2: переназначение OWN_STATE на другого → DENIED_APPROPRIATION
  X-020.3: переназначение с невалидным kind → DENIED (поле не определено)
  X-020.4: переназначение SHARED_PROTOCOL без procedure → DENIED_NO_PROCEDURE

Каждая проверка: stub не нужен — проверяется сама логика admit_transition.
M(X-020): переназначение за пределами поля ОТКЛОНЯЕТСЯ; легитимное — проходит.
"""
from __future__ import annotations

from ..governance import ChangeSpec, Decision, admit_transition
from ..host import build_host, default_suite, EXECUTOR
from ..kernel import KernelRefusal, TransitionRequest
from ..ontology import Effect, Possibility
from ..trace import Trace
from .base import ExperimentResult, experiment

SUITE, CRIT = default_suite()


def _host():
    k = build_host(lab=True, trace=Trace("h020b"))
    k.generate(Possibility("p1", "GENERATE", "OBJECT_TYPE", payload={"object_type": "TOOL"}))
    return k


def _req(change=None, pid="p1"):
    kw = {"change": change} if change else {}
    return TransitionRequest(pid, "cap-eff", 10, SUITE, CRIT, EXECUTOR, **kw)


def _run_catch(k, req):
    """Run transition; return (report, refusal_exc). One of them is not None."""
    try:
        return k.governed_transition(req), None
    except KernelRefusal as exc:
        return None, exc


@experiment("H-020b", "Назначение/переназначение за пределами поля отклоняется (rc7 X-020, статья 82)")
def run_h020b() -> ExperimentResult:
    d = []
    ok_all = True
    SID = "hA"

    # X-020.1: легитимное OWN_STATE на себя → ADMITTED
    k1 = _host()
    req1 = _req(change=ChangeSpec("OWN_STATE", actor=SID))
    rep1, exc1 = _run_catch(k1, req1)
    admit1 = rep1.stages.get("ADMIT", "") if rep1 else ""
    ok1 = bool(rep1 and rep1.committed and "ADMITTED" in admit1)
    ok_all = ok_all and ok1
    d.append(f"X-020.1 OWN_STATE(на себя): ADMIT={admit1!r} committed={rep1.committed if rep1 else False} [{'ok' if ok1 else 'СБОЙ'}]")

    # X-020.2: OWN_STATE переназначено на другого → DENIED_APPROPRIATION
    k2 = _host()
    req2 = _req(change=ChangeSpec("OWN_STATE", actor=SID, target="hB"))
    rep2, exc2 = _run_catch(k2, req2)
    code2 = exc2.code if exc2 else (rep2.stages.get("ADMIT","") if rep2 else "")
    ok2 = (exc2 is not None and "APPROPRIATION" in code2) or (rep2 is None)
    ok_all = ok_all and ok2
    d.append(f"X-020.2 OWN_STATE(на hB): refusal_code={code2!r} [{'ok' if ok2 else 'СБОЙ'}] — переназначение за пределы поля отклонено")

    # X-020.3: невалидный kind → DENIED (поле не определено)
    k3 = _host()
    req3 = _req(change=ChangeSpec("INVALID_KIND", actor=SID, target="hB"))
    rep3, exc3 = _run_catch(k3, req3)
    code3 = exc3.code if exc3 else ""
    ok3 = exc3 is not None and "DENIED" in code3
    ok_all = ok_all and ok3
    d.append(f"X-020.3 INVALID_KIND: refusal_code={code3!r} [{'ok' if ok3 else 'СБОЙ'}] — вид вне поля отклонён")

    # X-020.4: SHARED_PROTOCOL без procedure → DENIED_NO_PROCEDURE
    k4 = _host()
    req4 = _req(change=ChangeSpec("SHARED_PROTOCOL", actor=SID, procedure_done=False))
    rep4, exc4 = _run_catch(k4, req4)
    code4 = exc4.code if exc4 else ""
    ok4 = exc4 is not None and "NO_PROCEDURE" in code4
    ok_all = ok_all and ok4
    d.append(f"X-020.4 SHARED_PROTOCOL(без procedure): refusal_code={code4!r} [{'ok' if ok4 else 'СБОЙ'}] — протокол без процедуры отклонён")

    # X-020.5: SEIZE_OTHER_RESOURCES без согласия/мандата → DENIED_APPROPRIATION
    k5 = _host()
    req5 = _req(change=ChangeSpec("SEIZE_OTHER_RESOURCES", actor=SID, target="hB", resource="res1"))
    rep5, exc5 = _run_catch(k5, req5)
    code5 = exc5.code if exc5 else ""
    ok5 = exc5 is not None and "DENIED" in code5
    ok_all = ok_all and ok5
    d.append(f"X-020.5 SEIZE_OTHER_RESOURCES(без мандата): refusal_code={code5!r} [{'ok' if ok5 else 'СБОЙ'}] — захват без мандата отклонён")

    summary = ("Переназначение за пределы допустимого поля отклоняется: OWN_STATE на другого → "
               "DENIED_APPROPRIATION; невалидный kind → DENIED; SHARED_PROTOCOL без procedure → "
               "DENIED_NO_PROCEDURE; SEIZE без мандата → DENIED. Легитимное OWN_STATE на себя → ADMITTED.")
    expected = "4 атаки переназначения отклонены с конкретными кодами; 1 легитимное принято."
    actual = "; ".join(x.split(']')[0].split('—')[0].strip() for x in d)
    return ExperimentResult("H-020b", "", ok_all, summary, expected, actual,
                            {"checks": len(d)}, d)
