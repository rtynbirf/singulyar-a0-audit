# R4 X-019 Implementation — Changes to SINGULYAR_A0_SYNTHESIS_v1

## New file
- `singulyar_host/experiments/h019b_capabilities_removal.py` — X-019 experiment:
  8 sub-experiments (C1–C8) testing M(x) > 0 for each capability of статья 79 rc7.

## Modified files (2-line changes each)

### `singulyar_host/__main__.py`
Added `h019b_capabilities_removal` to the experiment import list in `_load_experiments()`:
```python
from .experiments import (..., h019_staged_activation,
                          h019b_capabilities_removal,  # NEW
                          h020_a0_admission_gate)
```

### `tools/verify_all.py`
Updated expected experiment count from 14 to 15:
```python
run("HOST: selftest (демо + 15 экспериментов)", ..., "ИТОГО: 15/15 PASS"),  # was 14/14
```

### `SYNTHESIS_MANIFEST.json`
Regenerated via `python tools/make_synthesis_manifest.py` — now 110 files (was 109).

## Verification
```
$ python tools/verify_all.py
[PASS] A0: INTEGRITY_CHECK
[PASS] A0: самотесты 7/7
[PASS] A0: VALIDATOR
[PASS] A0: негативные тесты 11/11
[PASS] HOST: selftest (демо + 15 экспериментов)   ← H-019b included
[PASS] HOST: pytest
[PASS] SYNTHESIS_MANIFEST (110 files)
ИТОГО: ВСЁ PASS
```

## H-019b details (8/8 PASS)
- C1 Познание: stub Observer.witness → ATTEST NOT_VERIFIED ✓
- C2 Открытие: clear possibilities → PROPOSE NO_POSSIBILITY ✓
- C3 Назначение: ChangeSpec kind="" → ADMIT DENIED ✓
- C4 Созидание: stub generate → reject → new type not created ✓
- C5 Организация: clear formation_rules → structural rules lost ✓
- C6 Наделение полномочиями: stub capabilities.check → False → AUTHORITY fails ✓
- C7 Исполнение и контроль: stub _apply → no-op → ATTEST NOT_VERIFIED ✓
- C8 Сохранение и преобразование: stub cas_head → False → ACTIVATE DENIED_CONFLICT ✓

Each: stub → baseline fails (M(x) lost); restore → baseline succeeds (M(x) returned).
