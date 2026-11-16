import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from lex_naturae import (
    ALLOWED_UNITS, Claim, Evidence, EvidenceMethod, Kind, Link, Relation, Status,
    analyze_graph, claim_from_dict, from_json, load_claim_collection, main,
    normalize_scope, to_json,
)

ROOT = Path(__file__).resolve().parent
WATER = ROOT / "testdata" / "water.csv"
DOC = ROOT / "testdata" / "document.txt"
WATER_HASH = hashlib.sha256(WATER.read_bytes()).hexdigest()
DOC_HASH = hashlib.sha256(DOC.read_bytes()).hexdigest()


class ClaimTests(unittest.TestCase):
    def observation(self, **changes):
        values = dict(claim_id="O-1", statement="Water froze in sample A.",
                      kind=Kind.OBSERVATION, scope="sample A, test run 1")
        values.update(changes)
        return Claim(**values)

    def measurement(self, **changes):
        values = dict(description="Temperature reading", method=EvidenceMethod.MEASUREMENT,
                      result="Probe reading recorded", protocol="Place probe in sample for 60 seconds",
                      instrument="calibrated thermometer T-4", unit="degC", measurement_value=-2.0,
                      raw_data_ref="testdata/water.csv", raw_data_sha256=WATER_HASH,
                      csv_row=2, csv_column="temperature_c", tolerance=0.0, quantity="temperature")
        values.update(changes)
        return Evidence(**values)

    def hypothesis(self, **changes):
        values = dict(claim_id="H-1", statement="Cooling causes sample A to freeze.",
                      kind=Kind.EMPIRICAL_HYPOTHESIS, scope="sample A under protocol P",
                      testable_question="Does sample A freeze under protocol P?",
                      population="10 water samples from batch A", measure="phase state after 30 minutes",
                      decision_rule="At least 8 of 10 samples are solid")
        values.update(changes)
        return Claim(**values)

    def institutional_evidence(self, **changes):
        values = dict(description="Text of section 4", method=EvidenceMethod.DOCUMENT_CITATION,
                      result="Section 4 contains the quoted requirement", source="https://example.invalid/doc",
                      document_title="Example Act", issuer="Example issuer", locator="section 4",
                      version="2026-01-01 edition", retrieved_at="2026-11-16T10:00:00+03:00",
                      raw_data_ref="testdata/document.txt", content_sha256=DOC_HASH,
                      excerpt="document artifact for local integrity verification")
        values.update(changes)
        return Evidence(**values)

    def test_minimal_observation_is_valid_but_unknown(self):
        self.assertEqual(self.observation().validate(base_dir=ROOT), [])
        self.assertEqual(self.observation().assessment(base_dir=ROOT)["status"], "UNKNOWN")

    def test_punctuation_only_claim_fields_rejected(self):
        for field in ("claim_id", "statement", "scope"):
            self.assertTrue(self.observation(**{field: "..."}).validate())

    def test_measurement_requires_real_numeric_value_and_supported_unit(self):
        self.assertEqual(self.observation(status=Status.SUPPORTED, evidence=(self.measurement(),)).validate(base_dir=ROOT), [])
        for bad in ("a1", "x1", None, True, float("nan"), float("inf")):
            ev = self.measurement(measurement_value=bad)
            errors = self.observation(status=Status.SUPPORTED, evidence=(ev,)).validate(base_dir=ROOT)
            self.assertTrue(any("finite JSON number" in e for e in errors), repr(bad))
        self.assertTrue(any("supported units" in e for e in self.observation(
            status=Status.SUPPORTED, evidence=(self.measurement(unit="made-up-unit"),)).validate(base_dir=ROOT)))

    def test_unit_catalog_is_finite(self):
        self.assertIn("degC", ALLOWED_UNITS)
        self.assertNotIn("degree Celsius", ALLOWED_UNITS)

    def test_raw_data_hash_is_recomputed(self):
        bad = self.measurement(raw_data_sha256="0" * 64)
        errors = self.observation(status=Status.SUPPORTED, evidence=(bad,)).validate(base_dir=ROOT)
        self.assertTrue(any("SHA-256 mismatch" in e for e in errors))

    def test_missing_raw_data_file_rejected(self):
        bad = self.measurement(raw_data_ref="testdata/missing.csv")
        errors = self.observation(status=Status.SUPPORTED, evidence=(bad,)).validate(base_dir=ROOT)
        self.assertTrue(any("does not resolve" in e for e in errors))

    def test_path_traversal_and_absolute_paths_rejected(self):
        for ref in ("../outside.txt", str(WATER)):
            bad = self.measurement(raw_data_ref=ref)
            errors = self.observation(status=Status.SUPPORTED, evidence=(bad,)).validate(base_dir=ROOT)
            self.assertTrue(any("relative path" in e for e in errors), ref)

    def test_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            outside = Path(tmp) / "outside.txt"
            outside.write_text("outside", encoding="utf-8")
            (root / "escape.txt").symlink_to(outside)
            digest = hashlib.sha256(outside.read_bytes()).hexdigest()
            ev = self.measurement(raw_data_ref="escape.txt", raw_data_sha256=digest)
            errors = self.observation(status=Status.SUPPORTED, evidence=(ev,)).validate(base_dir=root)
            self.assertTrue(any("outside the package" in e for e in errors))

    def test_document_citation_requires_iso_date_and_actual_local_hash(self):
        valid = self.institutional_evidence()
        claim = Claim("R-1", "Section 4 says Y.", Kind.INSTITUTIONAL_RULE, "document X", Status.SUPPORTED, (valid,))
        self.assertEqual(claim.validate(base_dir=ROOT), [])
        for date in ("не дата", "2026-99-99", "yesterday", "2099-01-01", "0001-01-01", "20261116"):
            bad = self.institutional_evidence(retrieved_at=date)
            self.assertTrue(any("ISO-8601" in e for e in Claim("R-1", "Rule", Kind.INSTITUTIONAL_RULE,
                "document X", Status.SUPPORTED, (bad,)).validate(base_dir=ROOT)))
        bad_hash = self.institutional_evidence(content_sha256="0" * 64)
        self.assertTrue(any("SHA-256 mismatch" in e for e in Claim("R-1", "Rule", Kind.INSTITUTIONAL_RULE,
            "document X", Status.SUPPORTED, (bad_hash,)).validate(base_dir=ROOT)))

    def test_document_source_must_be_absolute_http_url(self):
        for source in ("asdf", "file:///tmp/doc", "https:///missing-host"):
            ev = self.institutional_evidence(source=source)
            errors = Claim("R-1", "Rule", Kind.INSTITUTIONAL_RULE, "doc", Status.SUPPORTED, (ev,)).validate(base_dir=ROOT)
            self.assertTrue(any("absolute HTTP(S)" in e for e in errors), source)

    def test_philosophical_claim_cannot_be_empirically_supported(self):
        ev = self.institutional_evidence()
        for status in (Status.SUPPORTED, Status.CONTRADICTED, Status.MIXED):
            c = Claim("P-1", "A person has a natural right to silence.", Kind.PHILOSOPHICAL_PRINCIPLE,
                      "conceptual", status, (ev,))
            self.assertTrue(any("cannot receive empirical" in e for e in c.validate(base_dir=ROOT)))

    def test_hypothesis_requires_operationalization_fields(self):
        for field in ("testable_question", "population", "measure", "decision_rule"):
            self.assertTrue(self.hypothesis(**{field: ""}).validate(), field)
        self.assertEqual(self.hypothesis().validate(), [])

    def test_hypothesis_field_presence_is_not_claimed_as_semantic_proof(self):
        # Explicitly records the known limit: schema validates presence, not scientific adequacy.
        self.assertEqual(self.hypothesis(testable_question="a1", population="a1", measure="a1",
                                         decision_rule="a1").validate(), [])

    def test_empty_claim_collection_rejected(self):
        for raw in ("[]", '{"claims": []}'):
            with self.assertRaisesRegex(ValueError, "must not be empty"):
                load_claim_collection(raw)

    def test_scope_normalizes_case_and_whitespace(self):
        self.assertEqual(normalize_scope("  ЛАБ   1 "), normalize_scope("лаб 1"))
        self.assertNotEqual(normalize_scope("лаб 1"), normalize_scope("лаборатория 1"))

    def test_contradiction_warning_uses_normalized_scope(self):
        a = self.observation(status=Status.SUPPORTED, evidence=(self.measurement(),),
                             scope="  ЛАБ   1 ", links=(Link("O-1", "O-2", Relation.CONTRADICTS),))
        b = self.observation(claim_id="O-2", statement="Water did not freeze.", scope="лаб 1",
                             status=Status.SUPPORTED, evidence=(self.measurement(),))
        self.assertTrue(any("linked as contradicts" in w for w in analyze_graph([a, b], base_dir=ROOT)["warnings"]))

    def test_contradiction_scope_synonyms_are_not_guessed(self):
        a = self.observation(status=Status.SUPPORTED, evidence=(self.measurement(),), scope="лаб 1",
                             links=(Link("O-1", "O-2", Relation.CONTRADICTS),))
        b = self.observation(claim_id="O-2", scope="лаборатория 1", status=Status.SUPPORTED,
                             evidence=(self.measurement(),))
        self.assertFalse(any("linked as contradicts" in w for w in analyze_graph([a, b], base_dir=ROOT)["warnings"]))

    def test_contradicts_matrix_rejects_observation_vs_philosophical(self):
        obs = self.observation(links=(Link("O-1", "P-1", Relation.CONTRADICTS),))
        principle = Claim("P-1", "A principle", Kind.PHILOSOPHICAL_PRINCIPLE, "conceptual")
        self.assertTrue(any("not allowed" in e for e in analyze_graph([obs, principle])["errors"]))

    def test_violates_allows_observation_to_rule_and_principle(self):
        obs_rule = self.observation(links=(Link("O-1", "R-1", Relation.VIOLATES),))
        rule = Claim("R-1", "Observed consequence of rule", Kind.INSTITUTIONAL_RULE, "rule")
        self.assertEqual(analyze_graph([obs_rule, rule])["errors"], [])
        obs_principle = self.observation(links=(Link("O-1", "P-1", Relation.VIOLATES),))
        principle = Claim("P-1", "Principle", Kind.PHILOSOPHICAL_PRINCIPLE, "concept")
        self.assertEqual(analyze_graph([obs_principle, principle])["errors"], [])

    def test_violates_rejects_invalid_direction(self):
        principle = Claim("P-1", "Principle", Kind.PHILOSOPHICAL_PRINCIPLE, "concept",
                          links=(Link("P-1", "O-1", Relation.VIOLATES),))
        self.assertTrue(any("not allowed" in e for e in analyze_graph([principle, self.observation()])["errors"]))

    def test_explains_type_pairs_checked(self):
        obs = self.observation(links=(Link("O-1", "O-2", Relation.EXPLAINS),))
        other = self.observation(claim_id="O-2")
        self.assertTrue(any("not allowed" in e for e in analyze_graph([obs, other])["errors"]))

    def test_explains_cycle_is_reported(self):
        a = self.hypothesis(claim_id="H-1", links=(Link("H-1", "H-2", Relation.EXPLAINS),))
        b = self.hypothesis(claim_id="H-2", links=(Link("H-2", "H-1", Relation.EXPLAINS),))
        self.assertTrue(any("circular explains" in w for w in analyze_graph([a, b], base_dir=ROOT)["warnings"]))

    def test_duplicate_ids_unknown_endpoints_and_wrong_owner_rejected(self):
        a = self.observation(links=(Link("O-2", "missing", Relation.CONTRADICTS),))
        b = self.observation(claim_id="O-2")
        errors = analyze_graph([a, b], base_dir=ROOT)["errors"]
        self.assertTrue(any("owning claim_id" in e for e in errors))
        self.assertTrue(any("unknown endpoint" in e for e in errors))
        self.assertTrue(analyze_graph([b, b])["errors"])

    def test_unknown_json_fields_rejected_at_every_level(self):
        base = {"claim_id": "x", "statement": "y", "kind": "observation", "scope": "z"}
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            claim_from_dict({**base, "extra": 1})
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            claim_from_dict({**base, "evidence": [{"description": "d", "method": "direct_observation",
                "result": "r", "extra": 1}]})
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            claim_from_dict({**base, "links": [{"a": "x", "b": "y", "relation": "explains", "extra": 1}]})

    def test_json_round_trip(self):
        original = self.observation(links=(Link("O-1", "O-2", Relation.CONTRADICTS),))
        self.assertEqual(from_json(to_json(original)), original)

    def test_cli_valid_collection_exit_zero(self):
        a = self.observation()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "claims.json"
            path.write_text(json.dumps({"claims": [json.loads(to_json(a, base_dir=ROOT))]}), encoding="utf-8")
            with mock.patch("builtins.print") as output:
                self.assertEqual(main([str(path)]), 0)
                self.assertTrue(json.loads(output.call_args.args[0])["valid"])

    def test_cli_warning_exit_one(self):
        a = self.observation(status=Status.SUPPORTED, evidence=(self.measurement(),),
                             links=(Link("O-1", "O-2", Relation.CONTRADICTS),))
        b = self.observation(claim_id="O-2", statement="Water did not freeze in sample A.", status=Status.SUPPORTED, evidence=(self.measurement(),))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT / "testdata", root / "testdata")
            path = root / "claims.json"
            path.write_text(json.dumps({"claims": [json.loads(to_json(a, base_dir=ROOT)), json.loads(to_json(b, base_dir=ROOT))]}), encoding="utf-8")
            with mock.patch("builtins.print") as output:
                self.assertEqual(main([str(path)]), 1)
                self.assertGreaterEqual(len(json.loads(output.call_args.args[0])["graph_warnings"]), 1)

    def test_cli_hash_mismatch_exit_two(self):
        a = self.observation(status=Status.SUPPORTED, evidence=(self.measurement(raw_data_sha256="0" * 64),))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT / "testdata", root / "testdata")
            path = root / "claims.json"
            data = json.loads(to_json(self.observation(status=Status.SUPPORTED, evidence=(self.measurement(),)), base_dir=ROOT))
            data["evidence"][0]["raw_data_sha256"] = "0" * 64
            path.write_text(json.dumps(data), encoding="utf-8")
            with mock.patch("builtins.print") as output:
                self.assertEqual(main([str(path)]), 2)
                self.assertFalse(json.loads(output.call_args.args[0])["valid"])

    def test_cli_empty_collection_exit_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "empty.json"
            path.write_text('{"claims": []}', encoding="utf-8")
            with mock.patch("builtins.print"):
                self.assertEqual(main([str(path)]), 2)

    def test_cli_malformed_input_no_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text('{"claim_id": 1}', encoding="utf-8")
            with mock.patch("builtins.print") as output:
                self.assertEqual(main([str(path)]), 2)
                report = json.loads(output.call_args.args[0])
                self.assertFalse(report["valid"])
                self.assertTrue(report["claims"][0]["errors"])
            path.write_text("not json at all", encoding="utf-8")
            with mock.patch("builtins.print") as output:
                self.assertEqual(main([str(path)]), 2)
                self.assertIn("error", json.loads(output.call_args.args[0]))

    def test_cli_document_hash_verification(self):
        claim = Claim("R-1", "Section 4 says Y.", Kind.INSTITUTIONAL_RULE, "document X",
                      Status.SUPPORTED, (self.institutional_evidence(),))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT / "testdata", root / "testdata")
            path = root / "claims.json"
            path.write_text(json.dumps(json.loads(to_json(claim, base_dir=ROOT))), encoding="utf-8")
            with mock.patch("builtins.print") as output:
                self.assertEqual(main([str(path)]), 1)
                self.assertTrue(json.loads(output.call_args.args[0])["valid"])
                self.assertTrue(any("URL-to-file attribution" in w for w in json.loads(output.call_args.args[0])["graph_warnings"]))

    def test_measurement_value_must_match_csv_cell(self):
        bad = self.measurement(measurement_value=9999)
        errors = self.observation(status=Status.SUPPORTED, evidence=(bad,)).validate(base_dir=ROOT)
        self.assertTrue(any("does not match CSV" in e for e in errors))

    def test_percent_is_usable_and_range_checked(self):
        ev = self.measurement(unit="%", quantity="percentage", measurement_value=50,
                              raw_data_ref="testdata/percent.csv", raw_data_sha256=hashlib.sha256((ROOT / "testdata/percent.csv").read_bytes()).hexdigest(),
                              csv_column="value", tolerance=0)
        # Unit validation is independent of the CSV's physical meaning; incompatible quantity is tested below.
        self.assertFalse(any("supported units" in e for e in ev.validate(for_kind=Kind.OBSERVATION, base_dir=ROOT)))
        bad = self.measurement(unit="%", quantity="percentage", measurement_value=1e9)
        self.assertTrue(any("plausible configured range" in e for e in bad.validate(for_kind=Kind.OBSERVATION, base_dir=ROOT)))

    def test_measurement_requires_explicit_tolerance(self):
        ev = self.measurement(tolerance=None)
        self.assertTrue(any("tolerance must be a finite non-negative" in e for e in ev.validate(for_kind=Kind.OBSERVATION, base_dir=ROOT)))

    def test_absolute_temperature_below_zero_kelvin_rejected(self):
        bad = self.measurement(unit="K", quantity="temperature", measurement_value=-5000)
        self.assertTrue(any("plausible configured range" in e for e in bad.validate(for_kind=Kind.OBSERVATION, base_dir=ROOT)))

    def test_controlled_scope_id_overrides_display_label_variants(self):
        a = self.observation(status=Status.SUPPORTED, evidence=(self.measurement(),), scope="Lab One",
                             scope_id="lab.one", links=(Link("O-1", "O-2", Relation.CONTRADICTS),))
        b = self.observation(claim_id="O-2", statement="Water did not freeze in sample A.", status=Status.MIXED,
                             evidence=(self.measurement(),), scope="Laboratory 1", scope_id="lab.one")
        self.assertTrue(any("linked as contradicts" in w for w in analyze_graph([a, b], base_dir=ROOT)["warnings"]))

    def test_unit_must_match_quantity(self):
        bad = self.measurement(unit="degC", quantity="length")
        self.assertTrue(any("incompatible with quantity" in e for e in bad.validate(for_kind=Kind.OBSERVATION, base_dir=ROOT)))

    def test_retrieved_at_future_and_out_of_range_rejected(self):
        for date in ("2099-01-01", "0001-01-01", "20261116"):
            ev = self.institutional_evidence(retrieved_at=date)
            claim = Claim("R-1", "Rule", Kind.INSTITUTIONAL_RULE, "rule", Status.SUPPORTED, (ev,))
            self.assertTrue(claim.validate(base_dir=ROOT), date)

    def test_scope_punctuation_homoglyph_normalization(self):
        self.assertEqual(normalize_scope("lab. 1"), normalize_scope("lab-1"))
        self.assertEqual(normalize_scope("lab a"), normalize_scope("lab а"))

    def test_invisible_claim_id_rejected(self):
        self.assertTrue(self.observation(claim_id="B\u200b").validate())

    def test_library_mode_marks_artifact_unverified_and_invalid(self):
        with self.assertRaisesRegex(ValueError, "cannot be verified without base_dir"):
            from_json(to_json(self.observation(status=Status.SUPPORTED, evidence=(self.measurement(),)), base_dir=ROOT))

    def test_duplicate_file_does_not_inflate_evidence_count(self):
        claim = self.observation(status=Status.SUPPORTED, evidence=(self.measurement(), self.measurement()))
        report = claim.assessment(base_dir=ROOT)
        self.assertEqual(report["evidence_count"], 1)
        self.assertEqual(report["evidence_verification"], "CHECKED_AGAINST_LOCAL_ARTIFACTS")

    def test_duplicate_document_digest_does_not_inflate_evidence_count(self):
        ev = self.institutional_evidence()
        claim = Claim("R-1", "Rule", Kind.INSTITUTIONAL_RULE, "rule", Status.SUPPORTED, (ev, ev))
        report = claim.assessment(base_dir=ROOT)
        self.assertEqual(report["evidence_count"], 1)
        warnings = analyze_graph([claim], base_dir=ROOT)["warnings"]
        self.assertTrue(any("reuses the same evidence file" in w for w in warnings))

    def test_supported_single_file_warns(self):
        claim = self.observation(status=Status.SUPPORTED, evidence=(self.measurement(),))
        warnings = analyze_graph([claim], base_dir=ROOT)["warnings"]
        self.assertTrue(any("one unique evidence file" in w for w in warnings))

    def test_duplicate_normalized_statements_rejected(self):
        a = self.observation()
        b = self.observation(claim_id="O-2", statement="Water froze in sample A!")
        self.assertTrue(any("duplicate normalized claim statements" in e for e in analyze_graph([a, b], base_dir=ROOT)["errors"]))

    def test_possible_contradiction_without_manual_link_warns(self):
        a = self.observation(statement="Water freezes", status=Status.SUPPORTED, evidence=(self.measurement(),))
        b = self.observation(claim_id="O-2", statement="Water does not freezes", status=Status.MIXED, evidence=(self.measurement(),))
        self.assertTrue(any("possible lexical contradiction" in w for w in analyze_graph([a, b], base_dir=ROOT)["warnings"]))

    def test_arbitrary_non_csv_artifacts_do_not_count_as_measurements(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, payload in (("one.txt", b"x"), ("empty.csv", b""), ("source.py", (ROOT / "lex_naturae.py").read_bytes())):
                (root / name).write_bytes(payload)
                ev = self.measurement(raw_data_ref=name, raw_data_sha256=hashlib.sha256(payload).hexdigest())
                errors = self.observation(status=Status.SUPPORTED, evidence=(ev,)).validate(base_dir=root)
                self.assertTrue(any("measurement CSV extraction failed" in e for e in errors), name)

    def test_document_source_is_explicitly_unverified(self):
        claim = Claim("R-1", "Rule", Kind.INSTITUTIONAL_RULE, "rule", Status.SUPPORTED, (self.institutional_evidence(),))
        report = claim.assessment(base_dir=ROOT)
        self.assertEqual(report["document_source_attribution"], "UNVERIFIED_SUBMITTER_ASSERTION")


class AuditRegressionTests(unittest.TestCase):
    """Each test reproduces an attack that passed in v0.5 (or earlier) and must now fail or warn."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        (self.dir / "testdata").mkdir()
        for name in ("water.csv", "document.txt", "log.txt"):
            shutil.copy(ROOT / "testdata" / name, self.dir / "testdata" / name)

    def put(self, name, data):
        path = self.dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def measurement(self, **changes):
        values = dict(description="Temperature reading", method=EvidenceMethod.MEASUREMENT,
                      result="Probe reading recorded", protocol="Place probe in sample for 60 seconds",
                      instrument="calibrated thermometer T-4", unit="degC", measurement_value=-2.0,
                      raw_data_ref="testdata/water.csv", raw_data_sha256=WATER_HASH,
                      csv_row=2, csv_column="temperature_c", tolerance=0.0, quantity="temperature")
        values.update(changes)
        return Evidence(**values)

    def text_evidence(self, method=EvidenceMethod.LOG_ANALYSIS, **changes):
        data = (ROOT / "testdata" / "log.txt").read_bytes()
        values = dict(description="Cooler log", method=method, result="Surface froze at -2.0 degC",
                      protocol="Read the cooler log", raw_data_ref="testdata/log.txt",
                      raw_data_sha256=hashlib.sha256(data).hexdigest(), environment="cooler at 5 degC",
                      excerpt="sample A surface frozen, probe reads -2.0 degC")
        values.update(changes)
        return Evidence(**values)

    def claim(self, evidence, status=Status.SUPPORTED, **changes):
        values = dict(claim_id="O-1", statement="Water froze in sample A.", kind=Kind.OBSERVATION,
                      scope="sample A, run 1", status=status, evidence=tuple(evidence))
        values.update(changes)
        return Claim(**values)

    def errors(self, evidence, **changes):
        return self.claim(evidence, **changes).validate(base_dir=self.dir)

    # --- measurement binding -------------------------------------------------
    def test_huge_tolerance_cannot_launder_a_wrong_value(self):
        errs = self.errors([self.measurement(measurement_value=100, tolerance=1e300)])
        self.assertTrue(any("exceeds the allowed bound" in e for e in errs))

    def test_tolerance_is_bounded_to_one_percent(self):
        self.put("t.csv", "v\n100.5\n")
        ok = self.measurement(raw_data_ref="t.csv", raw_data_sha256=hashlib.sha256((self.dir / "t.csv").read_bytes()).hexdigest(),
                              csv_column="v", unit="m", quantity="length", measurement_value=100.0, tolerance=1.0)
        self.assertEqual(self.errors([ok]), [])
        bad = Evidence(**{**ok.__dict__, "tolerance": 2.0})
        self.assertTrue(any("exceeds the allowed bound" in e for e in self.errors([bad])))

    def test_underscore_and_text_numbers_in_csv_rejected(self):
        for cell in ("1_0", "ten", "0x10", "1,0", ""):
            digest = self.put("c.csv", f"v\n{cell}\n")
            ev = self.measurement(raw_data_ref="c.csv", raw_data_sha256=digest, csv_column="v",
                                  unit="m", quantity="length", measurement_value=10)
            self.assertTrue(self.errors([ev]), repr(cell))

    def test_csv_duplicate_headers_blank_lines_and_multiline_rejected(self):
        for body in ("v,v\n1,2\n", "v\n\n1\n", 'v\n"1\n"\n'):
            digest = self.put("c.csv", body)
            ev = self.measurement(raw_data_ref="c.csv", raw_data_sha256=digest, csv_column="v",
                                  unit="1", quantity="ratio", measurement_value=1, csv_row=2)
            self.assertTrue(self.errors([ev]), repr(body))

    def test_measurement_value_must_match_cell_and_other_columns_do_not_count(self):
        self.assertTrue(any("does not match" in e for e in self.errors([self.measurement(measurement_value=9999)])))
        self.assertTrue(any("not found" in e for e in self.errors([self.measurement(csv_column="phase_x")])))

    # --- excerpt binding for non-measurement evidence ----------------------------
    def test_junk_file_cannot_support_observation_methods(self):
        digest = self.put("junk.bin", "x")
        for method in (EvidenceMethod.DIRECT_OBSERVATION, EvidenceMethod.LOG_ANALYSIS, EvidenceMethod.REPEATABLE_EXPERIMENT):
            ev = self.text_evidence(method, raw_data_ref="junk.bin", raw_data_sha256=digest, excerpt="a1")
            self.assertTrue(self.errors([ev]), method)
            ev = self.text_evidence(method, raw_data_ref="junk.bin", raw_data_sha256=digest)
            self.assertTrue(any("not found verbatim" in e for e in self.errors([ev])), method)

    def test_real_excerpt_is_accepted_and_whitespace_insensitive(self):
        for method in (EvidenceMethod.DIRECT_OBSERVATION, EvidenceMethod.LOG_ANALYSIS, EvidenceMethod.REPEATABLE_EXPERIMENT):
            self.assertEqual(self.errors([self.text_evidence(method)]), [], method)
        spaced = self.text_evidence(excerpt="sample A   surface frozen,\n probe reads -2.0 degC")
        self.assertEqual(self.errors([spaced]), [])

    def test_excerpt_must_exist_be_long_enough_and_artifact_must_be_text(self):
        self.assertTrue(any("excerpt must quote" in e for e in self.errors([self.text_evidence(excerpt="")])))
        self.assertTrue(any("at least 12" in e for e in self.errors([self.text_evidence(excerpt="frozen -2.0")])))
        digest = self.put("blob.bin", bytes(range(128, 256)) * 4)
        ev = self.text_evidence(raw_data_ref="blob.bin", raw_data_sha256=digest)
        self.assertTrue(any("not a UTF-8 text file" in e for e in self.errors([ev])))

    def test_excerpt_and_measurement_fields_stay_in_their_lanes(self):
        self.assertTrue(any("reserved for non-measurement" in e for e in self.errors([self.measurement(excerpt="some quoted words here")])))
        self.assertTrue(any("reserved for method=measurement" in e for e in self.errors([self.text_evidence(unit="m")])))

    def test_document_excerpt_must_be_in_the_document(self):
        ev = Evidence(description="Rule text", method=EvidenceMethod.DOCUMENT_CITATION, result="Rule quoted",
                      source="https://example.invalid/doc", document_title="Act", issuer="Issuer", locator="s.4",
                      version="v1", retrieved_at="2026-01-01", raw_data_ref="testdata/document.txt", content_sha256=DOC_HASH,
                      excerpt="Article 51 grants the right to silence")
        claim = Claim("R-1", "Rule grants silence", Kind.INSTITUTIONAL_RULE, "rule", Status.SUPPORTED, (ev,))
        self.assertTrue(any("not found verbatim" in e for e in claim.validate(base_dir=self.dir)))
        good = Evidence(**{**ev.__dict__, "excerpt": "Example document artifact for local integrity verification"})
        self.assertEqual(Claim("R-1", "Rule grants silence", Kind.INSTITUTIONAL_RULE, "rule", Status.SUPPORTED, (good,)).validate(base_dir=self.dir), [])
        none = Evidence(**{**ev.__dict__, "excerpt": ""})
        self.assertTrue(Claim("R-1", "Rule", Kind.INSTITUTIONAL_RULE, "rule", Status.SUPPORTED, (none,)).validate(base_dir=self.dir))

    def test_oversized_artifact_rejected(self):
        import lex_naturae
        with mock.patch.object(lex_naturae, "MAX_ARTIFACT_BYTES", 10):
            self.assertTrue(any("byte limit" in e for e in self.errors([self.measurement()])))

    # --- normalization --------------------------------------------------------
    def test_decimal_points_are_not_merged_by_normalization(self):
        self.assertNotEqual(normalize_scope("room 1.5"), normalize_scope("room 15"))
        a = self.claim([], Status.UNKNOWN, claim_id="A", statement="T is 1.5")
        b = self.claim([], Status.UNKNOWN, claim_id="B", statement="T is 15")
        self.assertEqual(analyze_graph([a, b])["errors"], [])
        c = self.claim([], Status.UNKNOWN, claim_id="C", statement="T is 1.5")
        self.assertTrue(any("duplicate" in e for e in analyze_graph([a, c])["errors"]))

    def test_scope_variants_still_normalize(self):
        self.assertEqual(normalize_scope("лаб. 1"), normalize_scope("лаб 1"))
        self.assertEqual(normalize_scope("lab 1"), normalize_scope("lab-1"))
        self.assertEqual(normalize_scope("lab1"), normalize_scope("LAB 1"))
        self.assertEqual(normalize_scope("lab a"), normalize_scope("lab \u0430"))

    def test_lexical_negation_is_narrow(self):
        a = self.claim([], Status.UNKNOWN, claim_id="A", statement="Sample A is frozen", scope="s1")
        b = self.claim([], Status.UNKNOWN, claim_id="B", statement="Sample A is not frozen", scope="s1")
        c = self.claim([], Status.UNKNOWN, claim_id="C", statement="Sample 2 is not frozen", scope="s1")
        self.assertTrue(any("lexical contradiction" in w for w in analyze_graph([a, b])["warnings"]))
        self.assertFalse(any("lexical" in w for w in analyze_graph([a, c])["warnings"]))

    # --- graph honesty ---------------------------------------------------------
    def test_supported_without_numeric_check_warns(self):
        text_only = self.claim([self.text_evidence()])
        self.assertTrue(any("no numerically checked measurement" in w for w in analyze_graph([text_only], base_dir=self.dir)["warnings"]))
        numeric = self.claim([self.measurement()])
        self.assertFalse(any("no numerically checked" in w for w in analyze_graph([numeric], base_dir=self.dir)["warnings"]))

    def test_assessment_reports_strongest_check(self):
        self.assertEqual(self.claim([self.text_evidence()]).assessment(base_dir=self.dir)["strongest_check"], "text_excerpt")
        self.assertEqual(self.claim([self.measurement()]).assessment(base_dir=self.dir)["strongest_check"], "csv_cell_value")
        self.assertEqual(self.claim([], Status.UNKNOWN).assessment()["strongest_check"], "none")

    # --- robustness --------------------------------------------------------------
    def test_weird_json_types_never_raise_from_validate(self):
        weird = [None, 0, 1.5, True, [], {}, "", "x", ["a"], {"a": 1}, 10 ** 400, float("inf"), float("nan"), -1]
        bases = [self.measurement(), self.text_evidence()]
        from dataclasses import fields
        for base in bases:
            for f in fields(Evidence):
                if f.name == "method":
                    continue
                for value in weird:
                    ev = Evidence(**{**base.__dict__, f.name: value})
                    try:
                        self.claim([ev]).validate(base_dir=self.dir)
                    except Exception as ex:
                        self.fail(f"{f.name}={value!r} raised {type(ex).__name__}: {ex}")
        for f in ("claim_id", "statement", "scope", "scope_id", "testable_question"):
            for value in weird:
                try:
                    self.claim([], Status.UNKNOWN, **{f: value}).validate(base_dir=self.dir)
                    analyze_graph([self.claim([], Status.UNKNOWN, **{f: value})])
                except Exception as ex:
                    self.fail(f"claim.{f}={value!r} raised {type(ex).__name__}: {ex}")

    def run_cli(self, payload):
        path = self.dir / "claims.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        with mock.patch("builtins.print") as output:
            code = main([str(path)])
        return code, json.loads(output.call_args.args[0])

    def test_cli_reports_every_claim_not_only_the_first_bad_one(self):
        good = {"claim_id": "A", "statement": "Water froze", "kind": "observation", "scope": "s1"}
        code, out = self.run_cli([good, {"claim_id": 1}, {**good, "claim_id": "C", "statement": "Other"}])
        self.assertEqual(code, 2)
        self.assertEqual(len(out["claims"]), 3)
        self.assertEqual([r["valid"] for r in sorted(out["claims"], key=lambda r: r["claim_index"])], [True, False, True])

    def test_cli_rejects_evidence_that_is_the_claim_file(self):
        digest = None
        payload = {"claim_id": "A", "statement": "Water froze", "kind": "observation", "scope": "s1", "status": "SUPPORTED",
                   "evidence": [{"description": "d", "method": "log_analysis", "result": "r", "protocol": "p",
                                 "raw_data_ref": "claims.json", "raw_data_sha256": "0" * 64,
                                 "excerpt": "Water froze in the sample"}]}
        code, out = self.run_cli(payload)
        self.assertEqual(code, 2)
        self.assertFalse(out["valid"])

    def test_shipped_examples_behave_as_documented(self):
        for name, expected in (("example_claim.json", 0), ("example_collection.json", 1)):
            with mock.patch("builtins.print") as output:
                code = main([str(ROOT / name)])
            self.assertEqual(code, expected, name)
            self.assertTrue(json.loads(output.call_args.args[0])["valid"], name)


if __name__ == "__main__":
    unittest.main(verbosity=2)

class TestBomTolerance(unittest.TestCase):
    """v0.7: JSON with UTF-8 BOM must parse correctly."""
    def test_bom_single_claim(self):
        bom_json = '﻿{"claim_id":"BOM","statement":"x","kind":"observation","scope":"s","status":"UNKNOWN"}'
        c = from_json(bom_json)
        self.assertEqual(c.claim_id, "BOM")

    def test_bom_collection(self):
        bom_json = '﻿{"claims":[{"claim_id":"B1","statement":"x","kind":"observation","scope":"s","status":"UNKNOWN"}]}'
        claims = load_claim_collection(bom_json)
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0].claim_id, "B1")
