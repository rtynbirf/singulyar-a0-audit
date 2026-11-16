# lex-naturae 0.6

A local claim/evidence ledger. It records claims of four kinds (observation, empirical hypothesis, philosophical principle, institutional rule), attaches evidence, links claims (`contradicts`, `violates`, `explains`) and checks what a program *can* check. It does not prove natural law, truth, or the origin of any document.

## Run

```bash
python -m unittest -v                      # 68 tests
python lex_naturae.py example_claim.json   # exit 0
python lex_naturae.py example_collection.json   # exit 1: shows graph warnings
```

Python 3.10+, no dependencies. Exit codes: `0` clean, `1` valid but graph warnings need review, `2` invalid. Evidence paths are relative to the directory of the claim file.

## What is actually checked

| Evidence | The program verifies |
|---|---|
| `measurement` | file exists inside the package, SHA-256 recomputed, the CSV cell at `csv_row`/`csv_column` is a plain number equal to `measurement_value` within `tolerance` (<= 1% of the value), unit is in the catalog, in range, and matches `quantity` |
| `direct_observation`, `log_analysis`, `repeatable_experiment` | SHA-256 recomputed; `excerpt` (>= 12 chars, >= 3 words) occurs verbatim in the UTF-8 text file |
| `document_citation` | SHA-256 recomputed; `excerpt` occurs verbatim in the stored document; `retrieved_at` is a real ISO date between 1900 and now; `source` is an absolute http(s) URL |

Graph: unique ids and endpoints, allowed kind pairs per relation, duplicate statements (same normalized text and scope), `explains` cycles, and warnings for linked contradictions between assessed claims, narrow lexical negations, single-file support, reused files, document attribution, and `SUPPORTED` observations without any numerically checked measurement.

Scope comparison uses `scope_id` when both claims have one; otherwise a normalized `scope` (case, punctuation, spacing, look-alike letters; `1.5` stays different from `15`).

## What is NOT checked (stated limits)

- That an excerpt or number *means* what the claim says. Evidence text is tied to the file, not to the statement.
- That a document came from `source`. Reports mark this `UNVERIFIED_SUBMITTER_ASSERTION`.
- That a measurement was really taken, or that instrument/protocol text is true.
- That different files are independent sources.
- Semantic synonyms in scopes, or contradictions in free text beyond the narrow negation heuristic.
- That `kind` is classified correctly (it is declared by the submitter), or that `SUPPORTED`/`CONTRADICTED`/`MIXED` agrees with the evidence content.

`SUPPORTED` means: the submitter marked it so and the attached evidence passed the checks above. It is not a verdict.

## Library use

`Claim.validate(base_dir=...)`, `analyze_graph(claims, base_dir=...)`, `from_json(raw, base_dir=...)`. Without `base_dir`, any claim with evidence is reported invalid (artifacts cannot be verified). Assessments report `strongest_check`: `csv_cell_value`, `text_excerpt` or `none`.

## Files

`lex_naturae.py` module and CLI; `test_lex_naturae.py` tests; `testdata/` sample artifacts; `example_claim.json`, `example_collection.json`; `SHA256SUMS.txt` (run `sha256sum -c SHA256SUMS.txt`).
