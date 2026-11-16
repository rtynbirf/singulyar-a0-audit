"""Lex Naturae claim/evidence ledger v0.6.

Validation checks structure and locally verifiable artifacts. It does not prove truth,
authenticate a remote publisher, or semantically classify arbitrary claims.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse
import argparse
import csv
import hashlib
import json
import math
import re
import unicodedata


class Kind(str, Enum):
    OBSERVATION = "observation"
    EMPIRICAL_HYPOTHESIS = "empirical_hypothesis"
    PHILOSOPHICAL_PRINCIPLE = "philosophical_principle"
    INSTITUTIONAL_RULE = "institutional_rule"


class Status(str, Enum):
    UNKNOWN = "UNKNOWN"
    NOT_RUN = "NOT_RUN"
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    MIXED = "MIXED"


class EvidenceMethod(str, Enum):
    DIRECT_OBSERVATION = "direct_observation"
    MEASUREMENT = "measurement"
    REPEATABLE_EXPERIMENT = "repeatable_experiment"
    LOG_ANALYSIS = "log_analysis"
    DOCUMENT_CITATION = "document_citation"


class Relation(str, Enum):
    CONTRADICTS = "contradicts"
    VIOLATES = "violates"
    EXPLAINS = "explains"


# Deliberately finite and explicit. Add units only with tests and documented semantics.
ALLOWED_UNITS = frozenset({
    "1", "%", "count", "m", "cm", "mm", "km", "s", "ms", "min", "h",
    "kg", "g", "mg", "K", "degC", "degF", "Pa", "kPa", "bar", "m/s",
    "km/h", "L", "mL", "mol", "mol/L", "V", "A", "W", "J", "Hz",
})


def _nonempty(v: Any) -> bool:
    return isinstance(v, str) and bool(v.strip()) and any(ch.isalnum() for ch in v)


def _finite(v: Any) -> bool:
    """True only for real finite numbers (bool, NaN, inf and huge ints are not)."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return False
    try:
        return math.isfinite(v)
    except OverflowError:
        return False


def _require(errors: list[str], obj: Any, *fields: str) -> None:
    for field in fields:
        value = getattr(obj, field, None)
        valid = isinstance(value, str) and bool(value.strip()) if field == "unit" else _nonempty(value)
        if not valid:
            errors.append(f"{field} must be a non-empty string")


_CONFUSABLES = str.maketrans({
    "а":"a", "е":"e", "о":"o", "р":"p", "с":"c", "у":"y", "х":"x",
    "к":"k", "м":"m", "т":"t", "в":"b", "н":"h", "і":"i", "ј":"j",
})

_WORD = re.compile(r"[^\W_]+(?:[.,][^\W_]+)*", re.UNICODE)
_LETTER_DIGIT = re.compile(r"(?<=[^\W\d_])(?=\d)|(?<=\d)(?=[^\W\d_])", re.UNICODE)


def _tokens(value: Any, *, fold: bool = True) -> list[str]:
    """Word tokens. Decimal points between digits are kept ('1.5' != '15').

    fold=True also folds Latin/Cyrillic look-alike letters (for identity keys).
    """
    if not isinstance(value, str):
        return []
    value = unicodedata.normalize("NFKC", value).casefold()
    if fold:
        value = value.translate(_CONFUSABLES)
    value = _LETTER_DIGIT.sub(" ", value)
    return _WORD.findall(value)


def normalize_scope(value: Any) -> str:
    """Syntactic scope key: NFKC, case, look-alike letters, punctuation, spacing.

    Keeps digits and decimal points distinct ('room 1.5' != 'room 15').
    This is not semantic identity. New records should also use a controlled scope_id.
    """
    return " ".join(_tokens(value))


def _statement_key(value: Any) -> str:
    return " ".join(_tokens(value))


def _norm_text(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value)).strip()


UNIT_RANGES = {
    "1": (0, 1), "%": (0, 100), "count": (0, 1e12),
    "K": (0, 1e6), "degC": (-273.15, 1e6), "degF": (-459.67, 1e6),
    "m": (-1e9, 1e9), "cm": (-1e11, 1e11), "mm": (-1e12, 1e12), "km": (-1e6, 1e6),
    "s": (0, 1e12), "ms": (0, 1e15), "min": (0, 1e10), "h": (0, 1e9),
    "kg": (0, 1e12), "g": (0, 1e15), "mg": (0, 1e18),
    "Pa": (0, 1e15), "kPa": (0, 1e12), "bar": (0, 1e10),
    "m/s": (0, 1e9), "km/h": (0, 1e9), "L": (0, 1e12), "mL": (0, 1e15),
    "mol": (0, 1e12), "mol/L": (0, 1e12), "V": (-1e9, 1e9), "A": (-1e9, 1e9),
    "W": (-1e15, 1e15), "J": (-1e18, 1e18), "Hz": (0, 1e15),
}
UNIT_QUANTITIES = {
    "temperature": {"K", "degC", "degF"}, "length": {"m", "cm", "mm", "km"},
    "time": {"s", "ms", "min", "h"}, "mass": {"kg", "g", "mg"},
    "pressure": {"Pa", "kPa", "bar"}, "speed": {"m/s", "km/h"},
    "volume": {"L", "mL"}, "amount": {"mol", "mol/L"},
    "voltage": {"V"}, "current": {"A"}, "power": {"W"}, "energy": {"J"},
    "frequency": {"Hz"}, "percentage": {"%"}, "ratio": {"1"}, "count": {"count"},
}


MAX_ARTIFACT_BYTES = 20 * 1024 * 1024
_NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")


def _safe_artifact(base_dir: Path | None, ref: str, label: str, errors: list[str]) -> Path | None:
    if not _nonempty(ref):
        errors.append(f"{label} must reference a local artifact file")
        return None
    rel = Path(ref)
    if rel.is_absolute() or ".." in rel.parts:
        errors.append(f"{label} must be a relative path without '..'")
        return None
    if base_dir is None:
        errors.append(f"{label} cannot be verified without a package base directory")
        return None
    try:
        root = base_dir.resolve(strict=True)
        candidate = (root / rel).resolve(strict=True)
        if not candidate.is_relative_to(root):
            errors.append(f"{label} resolves outside the package directory")
            return None
        if not candidate.is_file():
            errors.append(f"{label} is not a regular file")
            return None
        return candidate
    except (OSError, RuntimeError):
        errors.append(f"{label} does not resolve to an existing local file")
        return None


def _verify_digest(base_dir: Path | None, ref: str, expected: str, label: str, errors: list[str]) -> None:
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected):
        errors.append(f"{label} must be a 64-character hexadecimal SHA-256 digest")
        return
    # Without a package root this is schema-only validation; CLI supplies base_dir
    # and performs the actual file existence, containment, and digest checks.
    if base_dir is None:
        errors.append(f"{label} cannot be verified without base_dir; library validation is not artifact-verified")
        return
    path = _safe_artifact(base_dir, ref, label, errors)
    if path is None:
        return
    try:
        if path.stat().st_size > MAX_ARTIFACT_BYTES:
            errors.append(f"{label} exceeds the {MAX_ARTIFACT_BYTES} byte limit")
            return
        artifact_bytes = path.read_bytes()
        if not artifact_bytes:
            errors.append(f"{label} must not be an empty file")
            return
        actual = hashlib.sha256(artifact_bytes).hexdigest()
    except OSError as ex:
        errors.append(f"{label} cannot be read for SHA-256 verification: {ex}")
        return
    if actual.lower() != expected.lower():
        errors.append(f"{label} SHA-256 mismatch: expected {expected.lower()}, calculated {actual}")


def _verify_excerpt(base_dir: Path | None, ref: str, excerpt: str, label: str, errors: list[str]) -> None:
    """The excerpt must occur verbatim (NFKC, whitespace-collapsed) in the UTF-8 text artifact."""
    if not _nonempty(excerpt):
        errors.append("excerpt must quote the artifact text that the evidence relies on")
        return
    norm = _norm_text(excerpt)
    if len(norm) < 12 or len(norm.split()) < 3:
        errors.append("excerpt must be at least 12 characters and 3 words")
        return
    if base_dir is None:
        return  # missing base_dir is already reported by the digest check
    scratch: list[str] = []
    path = _safe_artifact(base_dir, ref, label, scratch)
    if path is None:
        return  # path problems are already reported by the digest check
    try:
        if path.stat().st_size > MAX_ARTIFACT_BYTES:
            return
        text = path.read_bytes().decode("utf-8-sig")
    except (OSError, UnicodeError):
        errors.append(f"{label} is not a UTF-8 text file; excerpt cannot be verified (supply a text rendering)")
        return
    if norm not in _norm_text(text):
        errors.append(f"excerpt was not found verbatim in {label}")


@dataclass(frozen=True)
class Evidence:
    description: str
    method: EvidenceMethod
    result: str
    source: str = ""
    protocol: str = ""
    instrument: str = ""
    unit: str = ""
    measurement_value: float | None = None
    raw_data_ref: str = ""
    raw_data_sha256: str = ""
    environment: str = ""
    document_title: str = ""
    issuer: str = ""
    locator: str = ""
    version: str = ""
    retrieved_at: str = ""
    content_sha256: str = ""
    csv_row: int = 0
    csv_column: str = ""
    tolerance: float | None = None
    quantity: str = ""
    excerpt: str = ""

    def check_kind(self) -> str:
        """What the program can verify for this record (valid only after validate(base_dir=...))."""
        return "csv_cell_value" if self.method == EvidenceMethod.MEASUREMENT else "text_excerpt"

    def validate(self, *, for_kind: Kind | None = None, base_dir: Path | None = None) -> list[str]:
        errors: list[str] = []
        _require(errors, self, "description", "result")
        if not isinstance(self.method, EvidenceMethod):
            errors.append("evidence.method must be a recognized EvidenceMethod")
            return errors

        if self.method == EvidenceMethod.DOCUMENT_CITATION:
            if for_kind not in (Kind.INSTITUTIONAL_RULE, Kind.PHILOSOPHICAL_PRINCIPLE):
                errors.append("document_citation is only accepted for institutional rules or philosophical references")
            _require(errors, self, "source", "document_title", "issuer", "locator", "version", "retrieved_at", "raw_data_ref")
            parsed = urlparse(self.source) if _nonempty(self.source) else None
            if parsed and (parsed.scheme not in ("http", "https") or not parsed.netloc):
                errors.append("evidence.source must be an absolute HTTP(S) URL")
            try:
                if not isinstance(self.retrieved_at, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?)?", self.retrieved_at): raise ValueError
                retrieved = datetime.fromisoformat(self.retrieved_at.replace("Z", "+00:00"))
                if retrieved.year < 1900: raise ValueError
                now = datetime.now(retrieved.tzinfo) if retrieved.tzinfo else datetime.now(timezone.utc).replace(tzinfo=None)
                if retrieved > now: raise ValueError
            except (ValueError, OverflowError):
                errors.append("evidence.retrieved_at must be a valid ISO-8601 date between 1900-01-01 and now")
            _verify_digest(base_dir, self.raw_data_ref, self.content_sha256, "document artifact", errors)
            _verify_excerpt(base_dir, self.raw_data_ref, self.excerpt, "document artifact", errors)
            if self.raw_data_sha256:
                errors.append("raw_data_sha256 is not used for document_citation; use content_sha256")
            if self.measurement_value is not None or self.unit or self.csv_row or self.csv_column or self.quantity or self.tolerance is not None:
                errors.append("measurement fields are reserved for method=measurement")
            return errors

        if for_kind == Kind.INSTITUTIONAL_RULE:
            errors.append("institutional_rule requires method=document_citation")
        if for_kind == Kind.PHILOSOPHICAL_PRINCIPLE:
            errors.append("philosophical_principle cannot be empirically assessed by this ledger")

        _require(errors, self, "protocol", "raw_data_ref")
        if self.method == EvidenceMethod.MEASUREMENT:
            _require(errors, self, "instrument", "unit", "raw_data_ref", "raw_data_sha256")
            if not isinstance(self.unit, str) or self.unit not in ALLOWED_UNITS:
                errors.append(f"measurement unit must be one of the supported units: {', '.join(sorted(ALLOWED_UNITS))}")
            if not _finite(self.measurement_value):
                errors.append("measurement_value must be a finite JSON number")
            else:
                lo, hi = UNIT_RANGES.get(self.unit, (0, 0)) if isinstance(self.unit, str) else (0, 0)
                if not lo <= self.measurement_value <= hi: errors.append(f"measurement_value outside plausible configured range for {self.unit}: [{lo}, {hi}]")
            quantity_ok = isinstance(self.quantity, str) and self.quantity in UNIT_QUANTITIES
            if isinstance(self.unit, str) and self.unit in ALLOWED_UNITS and not quantity_ok: errors.append("measurement quantity must be a recognized controlled quantity")
            elif quantity_ok and (not isinstance(self.unit, str) or self.unit not in UNIT_QUANTITIES[self.quantity]): errors.append(f"unit {self.unit!r} is incompatible with quantity {self.quantity!r}")
            if not isinstance(self.csv_row, int) or isinstance(self.csv_row, bool) or self.csv_row < 2: errors.append("csv_row must be a physical CSV line number >= 2")
            _require(errors, self, "csv_column")
            if not _finite(self.tolerance) or self.tolerance < 0: errors.append("tolerance must be a finite non-negative number")
            if self.excerpt: errors.append("excerpt is reserved for non-measurement evidence")
            if base_dir is not None and not errors:
                path = _safe_artifact(base_dir, self.raw_data_ref, "raw data artifact", errors)
                if path is not None:
                    try:
                        if path.stat().st_size > MAX_ARTIFACT_BYTES: raise ValueError("CSV file is too large")
                        with path.open("r", encoding="utf-8-sig", newline="") as fh:
                            reader = csv.DictReader(fh)
                            names = reader.fieldnames
                            if not names or self.csv_column not in names: raise ValueError("CSV column not found")
                            if len(set(names)) != len(names): raise ValueError("CSV header has duplicate column names")
                            row = None
                            for line_no, record in enumerate(reader, start=2):
                                if reader.line_num != line_no: raise ValueError("blank lines and multi-line CSV records are not supported")
                                if line_no == self.csv_row: row = record; break
                            if row is None: raise ValueError("CSV row not found")
                            cell = row[self.csv_column]
                            if not isinstance(cell, str) or not _NUMBER.fullmatch(cell.strip()): raise ValueError(f"CSV cell is not a plain decimal number: {cell!r}")
                            actual_value = float(cell.strip())
                            if not math.isfinite(actual_value): raise ValueError("CSV value is not finite")
                            limit = max(1e-6, 0.01 * max(abs(actual_value), abs(float(self.measurement_value))))
                            if float(self.tolerance) > limit: errors.append(f"tolerance {self.tolerance} exceeds the allowed bound {limit:g} (1% of the value, minimum 1e-6)")
                            if abs(actual_value - float(self.measurement_value)) > float(self.tolerance):
                                errors.append(f"measurement_value {self.measurement_value} does not match CSV {self.csv_column} line {self.csv_row}: {actual_value} (tolerance {self.tolerance})")
                    except (OSError, UnicodeError, csv.Error, TypeError, ValueError, OverflowError) as ex:
                        errors.append(f"measurement CSV extraction failed: {ex}")
        elif self.measurement_value is not None or self.unit or self.csv_row or self.csv_column or self.quantity or self.tolerance is not None:
            errors.append("measurement fields are reserved for method=measurement")
        if self.method == EvidenceMethod.REPEATABLE_EXPERIMENT:
            _require(errors, self, "environment", "raw_data_sha256")
        if self.method in (EvidenceMethod.DIRECT_OBSERVATION, EvidenceMethod.LOG_ANALYSIS):
            _require(errors, self, "raw_data_sha256")
        if self.raw_data_ref or self.raw_data_sha256:
            _verify_digest(base_dir, self.raw_data_ref, self.raw_data_sha256, "raw data artifact", errors)
        if self.method != EvidenceMethod.MEASUREMENT:
            _verify_excerpt(base_dir, self.raw_data_ref, self.excerpt, "raw data artifact", errors)
        return errors


@dataclass(frozen=True)
class Link:
    a: str
    b: str
    relation: Relation

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not _nonempty(self.a): errors.append("link.a must be a non-empty claim id")
        if not _nonempty(self.b): errors.append("link.b must be a non-empty claim id")
        if self.a == self.b and _nonempty(self.a): errors.append("link cannot connect a claim to itself")
        if not isinstance(self.relation, Relation): errors.append("link.relation must be contradicts, violates, or explains")
        return errors


@dataclass(frozen=True)
class Claim:
    claim_id: str
    statement: str
    kind: Kind
    scope: str
    status: Status = Status.UNKNOWN
    evidence: tuple[Evidence, ...] = ()
    testable_question: str = ""
    population: str = ""
    measure: str = ""
    decision_rule: str = ""
    links: tuple[Link, ...] = ()
    scope_id: str = ""

    def validate(self, *, base_dir: Path | None = None) -> list[str]:
        errors: list[str] = []
        _require(errors, self, "claim_id", "statement", "scope")
        if not isinstance(self.claim_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", self.claim_id):
            errors.append("claim_id must be an ASCII identifier without invisible/control characters")
        if self.scope_id and (not isinstance(self.scope_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._:-]{0,127}", self.scope_id)): errors.append("scope_id must be a controlled lowercase ASCII identifier")
        if not isinstance(self.kind, Kind): errors.append("kind must be a recognized claim kind")
        if not isinstance(self.status, Status): errors.append("status must be a recognized status")
        if not isinstance(self.evidence, tuple):
            errors.append("evidence must be a tuple of Evidence records")
        else:
            for i, item in enumerate(self.evidence):
                if not isinstance(item, Evidence): errors.append(f"evidence[{i}] must be an Evidence record")
                else:
                    errors.extend(f"evidence[{i}].{err}" for err in item.validate(for_kind=self.kind if isinstance(self.kind, Kind) else None, base_dir=base_dir))
        if not isinstance(self.links, tuple):
            errors.append("links must be a tuple of Link records")
        else:
            for i, item in enumerate(self.links):
                if not isinstance(item, Link): errors.append(f"links[{i}] must be a Link record")
                else: errors.extend(f"links[{i}].{err}" for err in item.validate())
        if self.kind == Kind.EMPIRICAL_HYPOTHESIS:
            _require(errors, self, "testable_question", "population", "measure", "decision_rule")
        elif any(_nonempty(getattr(self, f, "")) for f in ("testable_question", "population", "measure", "decision_rule")):
            errors.append("hypothesis operationalization fields are reserved for empirical_hypothesis")
        if self.status in (Status.SUPPORTED, Status.CONTRADICTED, Status.MIXED) and not self.evidence:
            errors.append(f"{self.status.value} requires evidence; use UNKNOWN or NOT_RUN without evidence")
        if self.kind == Kind.PHILOSOPHICAL_PRINCIPLE and self.status in (Status.SUPPORTED, Status.CONTRADICTED, Status.MIXED):
            errors.append("philosophical principles cannot receive empirical evidence statuses in this ledger")
        return errors

    def assessment(self, *, base_dir: Path | None = None) -> dict[str, Any]:
        errors = self.validate(base_dir=base_dir)
        if errors:
            return {"valid": False, "errors": errors, "claim_id": self.claim_id if _nonempty(self.claim_id) else None}
        unique_digests = {(e.raw_data_sha256 or e.content_sha256).lower() for e in self.evidence if (e.raw_data_sha256 or e.content_sha256)}
        checks = sorted({e.check_kind() for e in self.evidence})
        strongest = "csv_cell_value" if "csv_cell_value" in checks else ("text_excerpt" if checks else "none")
        return {"valid": True, "claim_id": self.claim_id, "kind": self.kind.value, "status": self.status.value,
                "evidence_count": len(unique_digests) if unique_digests else len(self.evidence),
                "evidence_verification": ("NOT_APPLICABLE" if not self.evidence else ("CHECKED_AGAINST_LOCAL_ARTIFACTS" if base_dir is not None else "NOT_VERIFIED")),
                "evidence_checks": checks, "strongest_check": strongest,
                "document_source_attribution": "UNVERIFIED_SUBMITTER_ASSERTION" if any(e.method == EvidenceMethod.DOCUMENT_CITATION for e in self.evidence) else "NOT_APPLICABLE", "link_count": len(self.links),
                "meaning": status_meaning(self.status), "scope": self.scope}


CLAIM_KEYS = {"claim_id", "statement", "kind", "scope", "scope_id", "status", "evidence", "testable_question", "population", "measure", "decision_rule", "links"}
EVIDENCE_KEYS = {"description", "method", "result", "source", "protocol", "instrument", "unit", "measurement_value", "raw_data_ref", "raw_data_sha256", "environment", "document_title", "issuer", "locator", "version", "retrieved_at", "content_sha256", "csv_row", "csv_column", "tolerance", "quantity", "excerpt"}
LINK_KEYS = {"a", "b", "relation"}


def _strict_obj(data: Any, allowed: set[str], label: str) -> dict:
    if not isinstance(data, dict): raise ValueError(f"{label} must be a JSON object")
    extra = set(data) - allowed
    if extra: raise ValueError(f"{label} contains unknown fields: {', '.join(sorted(extra))}")
    return data


def _evidence(data: Any) -> Evidence:
    d = dict(_strict_obj(data, EVIDENCE_KEYS, "evidence item"))
    try:
        if "method" not in d: raise ValueError("missing method")
        d["method"] = EvidenceMethod(d["method"])
        return Evidence(**d)
    except (KeyError, TypeError, ValueError) as ex:
        raise ValueError(f"invalid evidence structure: {ex}") from ex


def _link(data: Any) -> Link:
    d = _strict_obj(data, LINK_KEYS, "link item")
    try: return Link(d["a"], d["b"], Relation(d["relation"]))
    except (KeyError, TypeError, ValueError) as ex: raise ValueError(f"invalid link structure: {ex}") from ex


def claim_from_dict(data: Any, *, base_dir: Path | None = None, validate: bool = True) -> Claim:
    d = dict(_strict_obj(data, CLAIM_KEYS, "claim"))
    try:
        d["kind"] = Kind(d["kind"])
        d["status"] = Status(d.get("status", "UNKNOWN"))
        ev, links = d.get("evidence", []), d.get("links", [])
        if not isinstance(ev, list) or not isinstance(links, list): raise ValueError("evidence and links must be JSON arrays")
        d["evidence"] = tuple(_evidence(x) for x in ev)
        d["links"] = tuple(_link(x) for x in links)
        claim = Claim(**d)
    except (KeyError, TypeError, ValueError) as ex:
        raise ValueError(f"invalid claim structure: {ex}") from ex
    if validate:
        errors = claim.validate(base_dir=base_dir)
        if errors: raise ValueError("Invalid claim: " + "; ".join(errors))
    return claim


def from_json(raw: str, *, base_dir: Path | None = None) -> Claim:
    if isinstance(raw, str): raw = raw.lstrip("﻿")  # BOM tolerance
    try: data = json.loads(raw)
    except json.JSONDecodeError as ex: raise ValueError(f"invalid JSON: {ex}") from ex
    return claim_from_dict(data, base_dir=base_dir)


CONTRADICTS_PAIRS = {
    (Kind.OBSERVATION, Kind.OBSERVATION),
    (Kind.EMPIRICAL_HYPOTHESIS, Kind.EMPIRICAL_HYPOTHESIS),
    (Kind.OBSERVATION, Kind.EMPIRICAL_HYPOTHESIS),
    (Kind.EMPIRICAL_HYPOTHESIS, Kind.OBSERVATION),
    (Kind.PHILOSOPHICAL_PRINCIPLE, Kind.PHILOSOPHICAL_PRINCIPLE),
    (Kind.INSTITUTIONAL_RULE, Kind.INSTITUTIONAL_RULE),
    (Kind.INSTITUTIONAL_RULE, Kind.PHILOSOPHICAL_PRINCIPLE),
    (Kind.PHILOSOPHICAL_PRINCIPLE, Kind.INSTITUTIONAL_RULE),
}
VIOLATES_PAIRS = {
    (Kind.INSTITUTIONAL_RULE, Kind.PHILOSOPHICAL_PRINCIPLE),
    (Kind.OBSERVATION, Kind.INSTITUTIONAL_RULE),
    (Kind.OBSERVATION, Kind.PHILOSOPHICAL_PRINCIPLE),
}
EXPLAINS_PAIRS = {
    (Kind.OBSERVATION, Kind.EMPIRICAL_HYPOTHESIS),
    (Kind.EMPIRICAL_HYPOTHESIS, Kind.OBSERVATION),
    (Kind.EMPIRICAL_HYPOTHESIS, Kind.EMPIRICAL_HYPOTHESIS),
    (Kind.PHILOSOPHICAL_PRINCIPLE, Kind.PHILOSOPHICAL_PRINCIPLE),
    (Kind.INSTITUTIONAL_RULE, Kind.INSTITUTIONAL_RULE),
}
ALLOWED_PAIRS = {Relation.CONTRADICTS: CONTRADICTS_PAIRS, Relation.VIOLATES: VIOLATES_PAIRS, Relation.EXPLAINS: EXPLAINS_PAIRS}


_NEGATIONS = frozenset({"not", "no", "never", "не", "нет", "никогда"})
_AUXILIARY = frozenset({"does", "do", "did", "is", "are", "was", "were"})


def _polarity(text: Any) -> tuple[tuple[str, ...], bool]:
    words = _tokens(text, fold=False)
    negated = any(w in _NEGATIONS for w in words)
    core = tuple(w for w in words if w not in _NEGATIONS and w not in _AUXILIARY)
    return core, negated


def analyze_graph(claims: Iterable[Claim], *, base_dir: Path | None = None, check_claims: bool = True) -> dict[str, list[str]]:
    items = list(claims)
    errors: list[str] = []
    warnings: list[str] = []
    if not items: return {"errors": ["claim collection must not be empty"], "warnings": []}
    ids = [c.claim_id for c in items if isinstance(c, Claim) and _nonempty(c.claim_id)]
    normalized_ids = [unicodedata.normalize("NFKC", x).casefold() for x in ids]
    if len(normalized_ids) != len(set(normalized_ids)): errors.append("claim_id values collide after normalization")
    statement_keys = [(_statement_key(c.statement), c.scope_id if isinstance(c.scope_id, str) and c.scope_id else normalize_scope(c.scope)) for c in items if isinstance(c, Claim)]
    if len(statement_keys) != len(set(statement_keys)): errors.append("duplicate normalized claim statements are not allowed")
    if len(ids) != len(set(ids)): errors.append("claim_id values must be unique in a graph")
    by_id = {c.claim_id: c for c in items if isinstance(c, Claim) and _nonempty(c.claim_id)}
    seen: set[tuple[str, str, Relation]] = set()
    explain: dict[str, list[str]] = {}
    for i, claim in enumerate(items):
        if not isinstance(claim, Claim): errors.append(f"claims[{i}] must be a Claim record"); continue
        if check_claims: errors.extend(f"claims[{i}].{err}" for err in claim.validate(base_dir=base_dir))
        if not isinstance(claim.links, tuple): continue
        for j, link in enumerate(claim.links):
            if not isinstance(link, Link): continue
            label = f"claims[{i}].links[{j}]"
            for endpoint, value in (("a", link.a), ("b", link.b)):
                if not _nonempty(value): errors.append(f"{label}.{endpoint}: invalid endpoint {value!r}")
                elif value not in by_id: errors.append(f"{label}.{endpoint}: unknown endpoint {value!r}")
            if link.a != claim.claim_id: errors.append(f"{label}.a must equal the owning claim_id")
            if not _nonempty(link.a) or not _nonempty(link.b) or link.a not in by_id or link.b not in by_id or not isinstance(link.relation, Relation): continue
            target = by_id[link.b]
            edge = (link.a, link.b, link.relation)
            if edge in seen: errors.append(f"{label}: duplicate graph edge")
            seen.add(edge)
            pair = (claim.kind, target.kind)
            if not isinstance(claim.kind, Kind) or not isinstance(target.kind, Kind):
                errors.append(f"{label}: relation endpoints must have recognized claim kinds")
            elif pair not in ALLOWED_PAIRS[link.relation]:
                errors.append(f"{label}: relation {link.relation.value} is not allowed for {claim.kind.value} -> {target.kind.value}")
            if link.relation == Relation.CONTRADICTS:
                same_scope = (claim.scope_id == target.scope_id) if claim.scope_id and target.scope_id else normalize_scope(claim.scope) == normalize_scope(target.scope)
                assessed = claim.status in (Status.SUPPORTED, Status.CONTRADICTED, Status.MIXED) and target.status in (Status.SUPPORTED, Status.CONTRADICTED, Status.MIXED)
                if same_scope and assessed:
                    warnings.append(f"assessed claims {link.a!r} and {link.b!r} are linked as contradicts in scope {claim.scope_id or normalize_scope(claim.scope)!r}")
            if link.relation == Relation.EXPLAINS: explain.setdefault(link.a, []).append(link.b)
    # Conservative lexical detector: flags direct negation pairs; never claims full semantic inference.
    for i, left in enumerate(items):
        if not isinstance(left, Claim): continue
        for right in items[i+1:]:
            if not isinstance(right, Claim) or left.kind != right.kind: continue
            same = (left.scope_id == right.scope_id) if left.scope_id and right.scope_id else normalize_scope(left.scope) == normalize_scope(right.scope)
            if not same: continue
            lp, ln = _polarity(left.statement); rp, rn = _polarity(right.statement)
            if lp and lp == rp and ln != rn:
                warnings.append(f"possible lexical contradiction between {left.claim_id!r} and {right.claim_id!r}; review manually")
    # One evidence digest is one artifact, not independent corroboration.
    for claim in items:
        if isinstance(claim, Claim) and claim.status == Status.SUPPORTED and isinstance(claim.evidence, tuple):
            if any(e.method == EvidenceMethod.DOCUMENT_CITATION for e in claim.evidence):
                warnings.append(f"SUPPORTED claim {claim.claim_id!r} has unverified document URL-to-file attribution")
            digests = [(e.raw_data_sha256 or e.content_sha256).lower() for e in claim.evidence if (e.raw_data_sha256 or e.content_sha256)]
            if len(set(digests)) == 1:
                warnings.append(f"SUPPORTED claim {claim.claim_id!r} relies on one unique evidence file only")
            if claim.kind in (Kind.OBSERVATION, Kind.EMPIRICAL_HYPOTHESIS) and not any(e.method == EvidenceMethod.MEASUREMENT for e in claim.evidence):
                warnings.append(f"SUPPORTED claim {claim.claim_id!r} has no numerically checked measurement; only quoted text excerpts were verified")
            if len(digests) != len(set(digests)):
                warnings.append(f"claim {claim.claim_id!r} reuses the same evidence file; duplicates are not independent")
    visiting: set[str] = set()
    visited: set[str] = set()
    def visit(node: str, path: list[str]) -> None:
        if node in visiting:
            start = path.index(node) if node in path else 0
            warnings.append("circular explains relation: " + " -> ".join(path[start:] + [node]))
            return
        if node in visited: return
        visiting.add(node)
        for nxt in explain.get(node, []): visit(nxt, path + [nxt])
        visiting.remove(node)
        visited.add(node)
    for node in explain:
        if node not in visited: visit(node, [node])
    return {"errors": errors, "warnings": warnings}


def validate_graph(claims: Iterable[Claim]) -> list[str]:
    return analyze_graph(claims)["errors"]


def status_meaning(status: Status) -> str:
    return {
        Status.UNKNOWN: "No assessment has been established.",
        Status.NOT_RUN: "The proposed check has not been performed.",
        Status.SUPPORTED: "The submitter marked this supported; evidence is not independently authenticated.",
        Status.CONTRADICTED: "The submitter marked this contradicted; evidence is not independently authenticated.",
        Status.MIXED: "The submitter marked the evidence mixed; evidence is not independently authenticated.",
    }[status]


def to_json(claim: Claim, *, base_dir: Path | None = None) -> str:
    errors = claim.validate(base_dir=base_dir)
    if errors: raise ValueError("Invalid claim: " + "; ".join(errors))
    data = asdict(claim)
    data["kind"] = claim.kind.value
    data["status"] = claim.status.value
    data["evidence"] = [{**asdict(item), "method": item.method.value} for item in claim.evidence]
    data["links"] = [{"a": item.a, "b": item.b, "relation": item.relation.value} for item in claim.links]
    return json.dumps(data, ensure_ascii=False, indent=2)


def _split_collection(raw: str) -> list[Any]:
    if isinstance(raw, str): raw = raw.lstrip("﻿")  # BOM tolerance
    try: data = json.loads(raw)
    except json.JSONDecodeError as ex: raise ValueError(f"invalid JSON: {ex}") from ex
    if isinstance(data, list): items = data
    elif isinstance(data, dict) and set(data) == {"claims"} and isinstance(data["claims"], list): items = data["claims"]
    elif isinstance(data, dict) and "claims" in data: raise ValueError("claims collection must contain only a JSON array in 'claims'")
    else: items = [data]
    if not items: raise ValueError("claim collection must not be empty")
    return items


def load_claim_collection(raw: str, *, base_dir: Path | None = None) -> list[Claim]:
    return [claim_from_dict(item, base_dir=base_dir) for item in _split_collection(raw)]


def _self_reference_errors(claim: Claim, base_dir: Path, claim_file: Path) -> list[str]:
    errors = []
    for i, ev in enumerate(claim.evidence):
        ref = ev.raw_data_ref
        if _nonempty(ref):
            try:
                if (base_dir / ref).resolve() == claim_file:
                    errors.append(f"evidence[{i}].raw_data_ref must not be the claim file itself")
            except (OSError, RuntimeError, ValueError):
                pass
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate claims and analyze their relationship graph")
    parser.add_argument("claim_file")
    args = parser.parse_args(argv)
    try:
        file_path = Path(args.claim_file).resolve(strict=True)
        base = file_path.parent
        items = _split_collection(file_path.read_text(encoding="utf-8"))
        reports: list[dict[str, Any]] = []
        claims: list[Claim] = []
        for index, item in enumerate(items):
            try:
                claim = claim_from_dict(item, base_dir=base, validate=False)
            except ValueError as ex:
                reports.append({"valid": False, "claim_index": index, "errors": [str(ex)]})
                continue
            claims.append(claim)
            report = claim.assessment(base_dir=base)
            extra = _self_reference_errors(claim, base, file_path)
            if extra:
                report = {"valid": False, "claim_id": report.get("claim_id"), "errors": report.get("errors", []) + extra}
            report["claim_index"] = index
            reports.append(report)
        graph = analyze_graph(claims, base_dir=base, check_claims=False)
        valid = all(r["valid"] for r in reports) and not graph["errors"]
        code = 2 if not valid else (1 if graph["warnings"] else 0)
        output = {"valid": valid, "claim_count": len(items), "claims": reports,
                  "graph_errors": graph["errors"], "graph_warnings": graph["warnings"], "exit_code": code}
    except Exception as ex:
        output = {"valid": False, "error": f"{type(ex).__name__}: {ex}", "exit_code": 2}
        code = 2
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
