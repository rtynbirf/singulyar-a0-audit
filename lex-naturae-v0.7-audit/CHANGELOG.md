# Changelog

## v0.7 — BOM tolerance (independent audit fix)

Independent audit of v0.6 by Z.ai (не автор v0.6). 10+10 атак; v0.6 отбил 19/20.
Единственный реальный gap: JSON с UTF-8 BOM (U+FEFF) вызывал ValueError в
`from_json()` и `_split_collection()` — `json.loads()` не толерирует BOM.

### Исправлено
- `from_json()`: strip BOM (U+FEFF) перед `json.loads()`.
- `_split_collection()`: то же для коллекций.
- 2 новых теста: `test_bom_single_claim`, `test_bom_collection`.

### Не исправлено (осознанные границы, как в v0.6)
- Excerpt cherry-picking: цитата найдена, но контекст может быть negation.
  Семантическая граница — программа не понимает смысл.
- URL ↔ файл: программа не доказывает, что файл получен с указанного URL.
  Маркируется `UNVERIFIED_SUBMITTER_ASSERTION`.
- Единицы — программные диапазоны, не физические законы.
- Противоречия — ограниченная эвристика отрицания, не семантический анализ.
- Независимость источников — дедупликация по хешу, не по происхождению.

### Атаки, которые v0.6 уже отбил (подтверждено независимым прогоном)
- Hardlink/symlink вне пакета → rejected (resolve + is_relative_to)
- Excerpt cherry-pick из negation → accepted (semantic gap, acknowledged)
- Duplicate file → deduplicated by hash
- value=0 tolerance=0 → accepted (correct)
- Tolerance over 1% → rejected
- Opposite claims no Link → warning (single-evidence)
- Same statement different claim_id → warning
- Unit m with quantity temperature → rejected (incompatible)
- CSV scientific notation 1e5 → accepted (correct)
- Empty file as artifact → rejected
- Duplicate claim_id → detected (normalization collision)
- Huge value 1e308 → rejected by range
- Invalid timezone +25:00 → rejected
- Zero-width space in claim_id → rejected
- CLI invalid claim → exit 2
- CLI one bad claim → GOOD processed, BAD flagged, exit 2

### Проверка
- 70/70 тестов PASS (68 v0.6 + 2 BOM)
- py_compile: OK
- SHA256SUMS: 10/10 OK (после обновления)
- CLI: example_collection.json → valid=true, exit=0

## v0.6 — excerpt verification, tolerance cap, CSV hardening, crash resistance
## v0.5 — measurement↔CSV cell link, unit ranges, date validation, deduplication
## v0.4 — SHA-256 file verification, controlled units, scope normalization
## v0.3 — structured evidence methods, link matrix, graph validation
## v0.2 — Link relations, method blacklist, MIXED for philosophy
## v0.1 — initial prototype: 4 claim kinds, status validation, 11 tests
