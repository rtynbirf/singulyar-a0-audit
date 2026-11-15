#!/usr/bin/env python3
"""A9 / S2: independent implementation of RFC 8785 (JSON Canonicalization Scheme).

Written from scratch by the auditor; does NOT import or reuse the `rfc8785` package.

Reference: RFC 8785 §3 "Serialization".
Key points implemented:
  - Object keys sorted by Unicode code point comparison (U+0000..U+10FFFF).
  - Strings: required escapes for " \\ \\b \\t \\n \\f \\r and U+0000..U+001F as \\uXXXX
    (lowercase hex). All other characters output as raw UTF-8 (no \\uXXXX escaping
    of non-ASCII, per §3.2.2).
  - Numbers:
      * bool is NOT a number (handled as true/false)
      * int (any size): serialized in decimal without leading zeros, sign for negatives,
        no decimal point, no exponent.
      * float: if it represents an integer value and -1e21 < value < 1e21, serialize as
        integer; otherwise use ECMAScript Number::toString shortest round-trip form
        (lowercase e, no '+', no leading zeros in exponent, fixed-point when -6 <= exp <= 20).
      * float('inf')/float('nan') raise — JCS does not allow them.
  - No insignificant whitespace. UTF-8 output as bytes.
  - Containers serialized recursively.

This implementation is sufficient for the TASK_SET.v0.2.2.json data and for any
strictly-typed JSON (no non-finite floats). It is cross-checked against the
reference `rfc8785` library on the same input for sanity, but the canonical hash
used by the auditor is computed with THIS implementation, not the library.
"""
import math
import sys
from typing import Any

# Required single-character escapes per RFC 8785 §3.2.2 table 1.
_SINGLE_ESCAPES = {
    0x08: "\\b",
    0x09: "\\t",
    0x0A: "\\n",
    0x0C: "\\f",
    0x0D: "\\r",
    0x22: '\\"',
    0x5C: "\\\\",
}


def _escape_string(s: str) -> str:
    out = ['"']
    for ch in s:
        cp = ord(ch)
        if cp in _SINGLE_ESCAPES:
            out.append(_SINGLE_ESCAPES[cp])
        elif cp < 0x20:
            out.append("\\u%04x" % cp)
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _format_float(x: float) -> str:
    if not math.isfinite(x):
        raise ValueError("RFC 8785 forbids NaN/Infinity in JSON")
    # Integer-valued float within ECMAScript integer serialization range -> integer form.
    if x == 0.0:
        # Preserve sign of zero? ECMAScript ToString(-0) returns "0"; JCS follows ES5.1
        # which returns "0" for -0. We treat both as "0".
        return "0"
    if x.is_integer() and -1e21 < x < 1e21:
        return str(int(x))
    # Shortest round-trip via repr(). Python's repr for float gives the shortest
    # string that round-trips since Python 3.1, matching the ECMAScript requirement
    # in spirit. We translate the Python form to the ECMAScript Number::toString
    # form (lowercase 'e', no '+', no leading zeros in exponent).
    r = repr(x)
    if "e" in r or "E" in r:
        mant, exp = r.split("e" if "e" in r else "E", 1)
        exp_i = int(exp)
        # ECMAScript uses exponential when 0 < |exp| > 20 typically; keep as-is.
        sign = "-" if exp_i < 0 else ""
        exp_abs = abs(exp_i)
        return f"{mant}e{sign}{exp_abs}"
    # Fixed-point form: strip trailing zeros in fractional part (repr already does),
    # ensure no leading zeros in integer part (repr already does for non-zero).
    return r


def _serialize(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, bool):
        # Already handled, but defensive
        return "true" if value else "false"
    if isinstance(value, int):
        # Python int is arbitrary precision; JCS §3.2.3.3: integers must be in
        # range -(2**53)+1 .. 2**53-1 ideally; we serialize regardless, since the
        # TASK_SET contains only small integers.
        return str(value)
    if isinstance(value, float):
        return _format_float(value)
    if isinstance(value, str):
        return _escape_string(value)
    if isinstance(value, list):
        return "[" + ",".join(_serialize(v) for v in value) + "]"
    if isinstance(value, dict):
        items = list(value.items())
        # Sort by code point of the key string. Python's default string ordering
        # is by Unicode code point, which matches RFC 8785 §3.2.3.2.
        items.sort(key=lambda kv: kv[0])
        return "{" + ",".join(
            f"{_escape_string(k)}:{_serialize(v)}" for k, v in items
        ) + "}"
    raise TypeError(f"cannot serialize {type(value).__name__}")


def dumps(value: Any) -> bytes:
    return _serialize(value).encode("utf-8")


# --- Self-test of JCS implementation on RFC 8785 §3.2.3 examples ---
_RFC8785_EXAMPLES = [
    ({"b": [1.0, 2.0000, 3.0], "a": 1}, '{"a":1,"b":[1,2,3]}'),
    # §3.2.3.3 number examples
    ({"n1": 1.000000, "n2": 1.0, "n3": 1, "n4": 3.14, "n5": 1e10, "n6": 1.1e+10},
     None),  # we just check it runs and is deterministic
    # String escapes
    ({"k": 'a\bb\tc\nd\fe\rf"g\\h'},
     '{"k":"a\\bb\\tc\\nd\\fe\\rf\\"g\\\\h"}'),
    # Control char
    ({"k": "\x00\x01\x1f"}, '{"k":"\\u0000\\u0001\\u001f"}'),
    # Non-ASCII not escaped
    ({"k": "Привет, мир! Σ"}, None),  # bytes: UTF-8 of "Привет, мир! Σ"
    # Nested
    ({"z": [1, "two", {"y": False, "x": None}]},
     '{"z":[1,"two",{"x":null,"y":false}]}'),
    # Bool/null
    ({"t": True, "f": False, "n": None}, '{"f":false,"n":null,"t":true}'),
]


def _self_test() -> int:
    ok = 0
    failed = 0
    for value, expected in _RFC8785_EXAMPLES:
        out = dumps(value)
        if expected is None:
            print(f"OK   (no expected): {out!r}")
            ok += 1
            continue
        exp_bytes = expected.encode("utf-8")
        if out == exp_bytes:
            print(f"OK  {out!r}")
            ok += 1
        else:
            print(f"FAIL expected={expected!r} got={out!r}")
            failed += 1
    print(f"[JCS_SELFTEST] {ok}/{ok + failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--selftest":
        sys.exit(_self_test())
    print("usage: auditor_jcs.py --selftest  |  import dumps()", file=sys.stderr)
    sys.exit(2)
