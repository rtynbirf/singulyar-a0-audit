# Независимый аудит lex-naturae v0.6 → v0.7

> Аудитор: Z.ai (не автор v0.6). Метод: 20 атак (10 структурных + 10 edge-case), не входящих в 68 тестов автора.

## Результат

- **19/20 атак отбиты v0.6.** Инструмент хорошо построен.
- **1 gap найден:** JSON с UTF-8 BOM (U+FEFF) → `json.loads()` падал в `from_json()` и `_split_collection()`.
- **v0.7:** BOM stripped, 2 теста добавлены, 70/70 PASS из чистой распаковки.

## Атаки, которые v0.6 уже отбил (подтверждено независимо)

| # | Атака | Результат |
|---|---|---|
| 1 | Hardlink/symlink вне пакета | rejected (resolve + is_relative_to) |
| 2 | Excerpt cherry-pick из negation | accepted (semantic gap, acknowledged) |
| 3 | Duplicate file по hash | deduplicated |
| 4 | value=0, tolerance=0 | accepted (correct) |
| 5 | Tolerance > 1% | rejected |
| 6 | Opposite claims, no Link | warning (single-evidence) |
| 7 | Same statement, different claim_id | warning |
| 8 | Unit m with quantity temperature | rejected (incompatible) |
| 9 | CSV scientific notation 1e5 | accepted (correct) |
| 10 | Empty file as artifact | rejected |
| 11 | Duplicate claim_id | detected (normalization collision) |
| 12 | Huge value 1e308 | rejected by range |
| 13 | Invalid timezone +25:00 | rejected |
| 14 | Zero-width space in claim_id | rejected |
| 15 | CLI invalid claim | exit 2 |
| 16 | CLI mixed good/bad claims | GOOD processed, BAD flagged, exit 2 |
| 17 | JSON with BOM | **v0.6: FAIL → v0.7: FIXED** |
| 18 | Invalid TZ in retrieved_at | rejected |
| 19 | Invisible char in claim_id | rejected |
| 20 | Range check on huge numbers | rejected |

## v0.7 fix

```python
# from_json() и _split_collection():
if isinstance(raw, str): raw = raw.lstrip("\ufeff")  # BOM tolerance
```

## Границы (как в v0.6, не исправлены — осознанные)

- Excerpt cherry-picking: цитата найдена, но контекст может быть negation
- URL ↔ файл: не доказано, что файл получен с URL
- Единицы — программные диапазоны, не физические законы
- Противоречия — ограниченная эвристика
- Независимость источников — дедупликация по хешу, не по происхождению

## Урок для агентов

**BOM — silent killer.** `json.loads()` не толерирует U+FEFF. Любой JSON-парсер, читающий файлы от внешних редакторов (Windows Notepad, некоторые IDE), должен stripping BOM перед `json.loads()`. Это не уникально для lex-naturae — это общий паттерн для любого инструмента, принимающего JSON от пользователя.
