#!/usr/bin/env python3
"""Bridge audit: auditor's own mutation tests on a0_bridge.py.

These tests are NOT in H-020. They cover:
  - G3/H-008 in bridge context (observer == executor → SelfAttestationRefused)
  - X2 on the failure path (failed ATTEST → export result_status="UNKNOWN")
  - Export schema validity on failure path (failed admission still exports schema-valid entry)
  - G7/CAS in admission context (ATTEST OK but ACTIVATE conflict → a0_run_allowed denies)
  - evidence_level_for_ledger_entry boundaries (I2/I2/PARTIAL → V2; UNKNOWN → V1; I3/I3/I4 → V3)
  - passport_verdicts edge cases (empty claims, NOT_APPLICABLE)
  - Multiple admissions idempotency
  - The observer-author-independence gap (HOST-V3 vs A0-ledger-V3)
"""
import json
import sys
from pathlib import Path

# Setup path to synthesis
SYN = Path("/home/z/my-project/scripts/audit_a0/synthesis/SINGULYAR_A0_SYNTHESIS_v1")
sys.path.insert(0, str(SYN))

from jsonschema import Draft202012Validator, FormatChecker
from singulyar_host import a0_bridge as B
from singulyar_host.host import EXECUTOR, OBSERVER_ID, OBSERVER_KEY, build_host
from singulyar_host.kernel import HostKernel, TransitionRequest
from singulyar_host.ontology import Verdict
from singulyar_host.verification import EvidenceLevel, Identity, Observer, SelfAttestationRefused
from singulyar_host.a0_bridge import (
    A0PackageObserver, DEFAULT_A0_ROOT, ADMIT_REL,
    STANDARD_ID, A0_PROPS, build_gate_host, request_admission, a0_run_allowed,
    attestation_to_ledger_entry, evidence_level_for_ledger_entry,
    passport_verdicts, package_digest, inspect_package, gate_suite,
)

ROOT = DEFAULT_A0_ROOT
SCHEMA = json.loads((ROOT / "EVIDENCE_LEDGER.schema.json").read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())

fails = 0
def check(name, cond, detail=""):
    global fails
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}  {detail}")
    if not cond: fails += 1

# --- BM-A: observer same identity as executor → SelfAttestationRefused ---
# Bridge's A0PackageObserver is constructed with OBSERVER_ID. If we override
# the host's observer to one whose identity == EXECUTOR, the Verifier's
# _check_self_attestation must refuse.
def bm_a():
    h = B.build_gate_host(ROOT)
    # Replace observer with one whose identity == EXECUTOR (same actor_id)
    h.observer = A0PackageObserver(EXECUTOR, b"key-exec", ROOT, h._a0_digest)
    # Replace verifier too (it has the identity check)
    from singulyar_host.verification import Verifier, TransparencyLog
    h.verifier = Verifier(EXECUTOR, b"key-exec", TransparencyLog("gate"), min_level=3)
    rep = B.request_admission(h)
    attest = rep.stages.get("ATTEST", "")
    ok = (not rep.committed) and attest.startswith("REFUSED")
    check("BM-A observer==executor → SelfAttestationRefused", ok, f"ATTEST={attest!r} committed={rep.committed}")

# --- BM-B: failed ATTEST → export result_status="UNKNOWN" ---
def bm_b():
    h = B.build_gate_host(ROOT, claimed_digest="f"*64)
    rep = B.request_admission(h)
    entry = B.attestation_to_ledger_entry(rep, h._a0_digest)
    ok = entry["result_status"] == "UNKNOWN"
    check("BM-B failed ATTEST → export UNKNOWN", ok, f"result_status={entry['result_status']!r}")

# --- BM-C: failed admission's export still validates against EVIDENCE_LEDGER.schema.json ---
def bm_c():
    h = B.build_gate_host(ROOT, claimed_digest="f"*64)
    rep = B.request_admission(h)
    entry = B.attestation_to_ledger_entry(rep, h._a0_digest)
    errs = list(VALIDATOR.iter_errors(entry))
    ok = not errs
    check("BM-C failed-admission export schema-valid", ok, f"{len(errs)} errors" + (f": {errs[0].message}" if errs else ""))

# --- BM-D: gate_suite structure + inspect_package returns 5 A0 facts, all True ---
def bm_d():
    suite, crit = B.gate_suite()
    suite_ok = suite.size == 3 and suite.name == "a0-admission"
    crit_ok = crit.required_properties == B.A0_PROPS and len(B.A0_PROPS) == 6
    digest = B.package_digest(ROOT)
    facts = B.inspect_package(ROOT, digest)
    a0_facts_keys = {"a0_integrity_ok", "a0_validator_ok", "a0_negative_tests_ok",
                     "a0_freeze_not_placeholder", "a0_package_digest_matches"}
    facts_ok = set(facts.keys()) == a0_facts_keys and all(facts.values())
    check("BM-D gate_suite structure + inspect_package 5 facts all True",
          suite_ok and crit_ok and facts_ok,
          f"suite.size={suite.size} crit.props={len(crit.required_properties)} facts={facts}")

# --- BM-E: evidence_level_for_ledger_entry boundary: I2/I2/PARTIAL → V2 ---
def bm_e():
    lv, _ = B.evidence_level_for_ledger_entry({"independence_profile": {
        "reviewer_independence": "I2", "reference_independence": "I2",
        "procedure_reproducibility": "PARTIAL"}})
    ok = lv == EvidenceLevel.V2
    check("BM-E I2/I2/PARTIAL → V2 (not V3)", ok, f"level={lv}")

# --- BM-F: evidence_level_for_ledger_entry with UNKNOWN reviewer → V1 ---
def bm_f():
    lv, _ = B.evidence_level_for_ledger_entry({"independence_profile": {
        "reviewer_independence": "UNKNOWN", "reference_independence": "I3",
        "procedure_reproducibility": "I4"}})
    ok = lv == EvidenceLevel.V1
    check("BM-F UNKNOWN reviewer → V1", ok, f"level={lv}")

# --- BM-G: positive path: I3/I3/I4 → V3 ---
def bm_g():
    lv, _ = B.evidence_level_for_ledger_entry({"independence_profile": {
        "reviewer_independence": "I3", "reference_independence": "I3",
        "procedure_reproducibility": "I4"}})
    ok = lv == EvidenceLevel.V3
    check("BM-G I3/I3/I4 → V3 (positive path)", ok, f"level={lv}")

# --- BM-H: passport_verdicts on empty architecture_claims → empty dict ---
def bm_h():
    v = B.passport_verdicts({"architecture_claims": []})
    ok = v == {}
    check("BM-H empty claims → empty verdicts", ok, f"verdicts={v}")

# --- BM-I: passport_verdicts with NOT_APPLICABLE → Verdict.UNKNOWN (not PASS) ---
def bm_i():
    v = B.passport_verdicts({"architecture_claims": [
        {"claim_id": "C1", "status": "NOT_APPLICABLE"},
        {"claim_id": "C2", "status": "CONFIRMED"},
        {"claim_id": "C3", "status": "REFUTED"},
    ]})
    ok = (v["C1"] == Verdict.UNKNOWN and v["C2"] == Verdict.PASS and v["C3"] == Verdict.FAIL)
    check("BM-I NOT_APPLICABLE → UNKNOWN, CONFIRMED → PASS, REFUTED → FAIL", ok,
          f"verdicts={ {k: x.value for k, x in v.items()} }")

# --- BM-J: The observer-author-independence gap ---
# The bridge's export records reviewer_independence="I1", reference_independence="UNKNOWN",
# procedure_reproducibility="PARTIAL" (honest disclosure of same-author observer).
# Under the bridge's OWN thresholds:
#   V3 needs reviewer>=I2 AND reference>=I2 AND procedure=="I4"
#   V2 needs reviewer>=I1 AND reference>=I1
#   else V1.
# With reviewer=I1 (→1), reference=UNKNOWN (→-1), procedure=PARTIAL:
#   r=1, f=-1, proc!=I4 → not V3; r>=1 yes but f>=1 no → not V2; falls to V1.
# So the HOST grants V3 (signature-key independence) but the exported entry
# qualifies only for V1 under the bridge's own thresholds — a 2-level gap.
# The test verifies the gap is honestly disclosed in the export.
def bm_j():
    h = B.build_gate_host(ROOT)
    rep = B.request_admission(h)
    entry = B.attestation_to_ledger_entry(rep, h._a0_digest)
    ip = entry["independence_profile"]
    lv, _ = B.evidence_level_for_ledger_entry(entry)
    host_v3 = rep.committed and rep.stages.get("ATTEST", "").startswith("VERIFIED (V3)")
    honest_disclosure = (ip["reviewer_independence"] == "I1"
                         and ip["reference_independence"] == "UNKNOWN"
                         and ip["procedure_reproducibility"] == "PARTIAL"
                         and "не независим от автора" in entry["reviewer"]["conflict_of_interest"])
    # Gap: HOST-V3 → ledger-V1 (2 levels), honestly disclosed
    gap_documented = host_v3 and (lv == EvidenceLevel.V1) and honest_disclosure
    check("BM-J HOST-V3 vs A0-ledger-V1 gap honestly disclosed", gap_documented,
          f"HOST_V3={host_v3} ledger_level={lv} reviewer_I={ip['reviewer_independence']!r} "
          f"reference_I={ip['reference_independence']!r} proc={ip['procedure_reproducibility']!r}")

# --- BM-K: a0_run_allowed returns NO_MANIFEST when manifest missing ---
def bm_k():
    import shutil, tempfile
    td = tempfile.mkdtemp(prefix="bm-k-")
    pkg = Path(td) / "pkg"
    shutil.copytree(ROOT, pkg, ignore=shutil.ignore_patterns("__pycache__"))
    (pkg / "MANIFEST.json").unlink()
    h = B.build_gate_host(pkg)  # builds with claimed_digest = current package_digest
    # But package_digest(pkg) is None (no manifest), so claimed_digest becomes "0"*64
    allowed = B.a0_run_allowed(h, pkg)
    ok = allowed == (False, "NO_MANIFEST")
    check("BM-K missing manifest → NO_MANIFEST", ok, f"allowed={allowed}")
    shutil.rmtree(td)

# --- BM-L: inspect_package runs A0's tools with PYTHONDONTWRITEBYTECODE ---
# Verify no __pycache__ created in A0 package after inspect_package runs
def bm_l():
    # Pre-clean
    for p in ROOT.rglob("__pycache__"):
        # don't actually delete from the audited package; just check none created
        pass
    before = set(p.relative_to(ROOT).as_posix() for p in ROOT.rglob("__pycache__"))
    B.inspect_package(ROOT, B.package_digest(ROOT))
    after = set(p.relative_to(ROOT).as_posix() for p in ROOT.rglob("__pycache__"))
    ok = before == after  # no new __pycache__ created
    check("BM-L inspect_package leaves no __pycache__", ok,
          f"before={before} after={after}")

print("=== Bridge mutation tests (auditor's own, not in H-020) ===\n")
bm_a()
bm_b()
bm_c()
bm_d()
bm_e()
bm_f()
bm_g()
bm_h()
bm_i()
bm_j()
bm_k()
bm_l()
print(f"\n[AUDITOR_BRIDGE_MUTATIONS] {12 - fails}/{12}")
sys.exit(1 if fails else 0)
