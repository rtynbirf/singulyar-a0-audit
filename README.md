# SINGULYAR × A0 — Independent Audit Bundle

Независимый аудит **A0_STANDARD v0.2.5** и моста **a0_bridge.py** синтеза
**SINGULYAR_A0_SYNTHESIS_v1**, выполненный третьей стороной (Z.ai) по протоколу
`AUDIT_PROTOCOL.md` и статьям X1/X2 конституции редакции 2.

## Вердикты

| Объект | Статус | Отчёт |
|---|---|---|
| A0_STANDARD v0.2.5 (архив + вендорная копия в синтезе) | **PACKAGE VALID** | `reports/A0_STANDARD_v0.2.5_AUDIT_REPORT.pdf` |
| Мост `a0_bridge.py` + опыт H-020 | **BRIDGE VALID** | `reports/A0_BRIDGE_AUDIT_REPORT.pdf` |

Вместе замыкают этап **S1** дорожной карты синтеза. S2 (пересчёт `freeze_sha256`
своей реализацией RFC 8785) закрыт внутри A0-аудита как проверка A9.

## Состав

```
reports/      — два формальных PDF-отчёта (A0 + мост)
scripts/      — скрипты аудитора:
  auditor_manifest_verify.py     — A8: своя сверка манифеста
  auditor_jcs.py                 — A9: своя реализация RFC 8785
  auditor_mutations.py           — 8 собственных мутаций A0-пакета
  auditor_bridge_mutations.py    — 12 собственных мутаций моста
  generate_audit_report.py       — генератор A0-отчёта PDF
  generate_bridge_audit_report.py — генератор мост-отчёта PDF
logs/         — логи всех прогонов (A0_environment, A1–A10, мутации, verify_all, H-020, BM-A…BM-L)
```

## Как воспроизвести аудит

```bash
# 1. Чистый venv
python3 -m venv venv
source venv/bin/activate
pip install jsonschema rfc8785 rfc3339-validator rfc3986-validator pytest reportlab

# 2. Извлечь архивы A0_STANDARD_v0.2.5.zip и SINGULYAR_A0_SYNTHESIS_v1.zip

# 3. A0-аудит (A1–A10 + мутации + D1–D8)
python -B VALIDATOR.py <A0_root>
python -B run_negative_tests.py <A0_root>
python -B INTEGRITY_CHECK.py <A0_root>
python -B scripts/auditor_manifest_verify.py <A0_root>
python -B scripts/auditor_jcs.py --selftest
python -B scripts/auditor_mutations.py

# 4. Мост-аудит
cd <synthesis_root>
python tools/verify_all.py
python -B scripts/auditor_bridge_mutations.py
```

## Среда аудитора

- OS: Debian GNU/Linux 13 (trixie)
- Python: 3.12.16
- jsonschema 4.26.0, rfc8785 0.1.4, rfc3339-validator 0.1.4, rfc3986-validator 0.1.1, pytest 9.2.0, reportlab 5.1.0

## Что НЕ делает этот аудит

- Не запускает A0 (допуск — отдельное решение; мост корректно его принуждает).
- Не доказывает качество задач/рубрик A0, статистическую достаточность 44 прогонов, воспроизводимость A0 (это этап A0 REPRODUCIBLE, не PACKAGE VALID).
- Не закрывает разрыв HOST-V3 ↔ A0-ledger-V1 (наблюдатель написан тем же автором; закрывается этапом S4 — Ed25519 от отдельного ключа).

## Лицензия / авторство

Аудиторские скрипты и отчёты — Z.ai, 2026. Проверяемый код (A0_STANDARD v0.2.5, SINGULYAR HOST v4.1, конституция редакции 2) — не изменён аудитором; лицензия оригинальных авторов.
