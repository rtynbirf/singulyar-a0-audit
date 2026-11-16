#!/usr/bin/env python3
r"""jcs_third.py — независимая реализация RFC 8785 (JSON Canonicalization Scheme),
написанная с нуля третьим наблюдателем (волна-22). Не импортирует rfc8785 и код
соседа-аудитора: только stdlib.

Опорные точки RFC 8785:
  §3.2.2.2  сериализация строк: escapes \" \\ \b \t \n \f \r и U+0000..U+001F
            как \uXXXX в нижнем регистре; прочее — сырой UTF-8; одиночные
            суррогаты — ошибка.
  §3.2.2.3  сериализация чисел по ECMAScript ES6 Number::toString:
            * целые значения при |x| < 1e21 — десятичной записью без точки;
            * иначе — кратчайший round-trip; экспонента без ведущих нулей,
              со знаком '+'/'-'; fixed-notation при -6 <= n <= 20.
  §3.2.3    сортировка ключей объекта по UTF-16 code units (не по code points!) —
            сравнение big-endian UTF-16 последовательностей байт.
"""
import json
import math
from typing import Any

_SINGLE_ESCAPES = {
    0x08: "\\b", 0x09: "\\t", 0x0A: "\\n",
    0x0C: "\\f", 0x0D: "\\r", 0x22: '\\"', 0x5C: "\\\\",
}


class JCSNameError(ValueError):
    """Запрещённое по I-JSON/JCS значение (NaN/Inf, одиночный суррогат)."""


def _utf16_units(s: str) -> bytes:
    """Ключи сортируются по UTF-16 code units: big-endian UTF-16 байты
    лексикографически равны числовому порядку code units (RFC 8785 §3.2.3)."""
    try:
        return s.encode("utf-16-be", "strict")
    except UnicodeEncodeError as e:  # одиночный суррогат в ключе
        raise JCSNameError(f"lone surrogate in key: {s!r}") from e


def _serialize_string(s: str) -> bytes:
    out = bytearray(b'"')
    for ch in s:
        cp = ord(ch)
        if cp in _SINGLE_ESCAPES:
            out += _SINGLE_ESCAPES[cp].encode("ascii")
        elif cp < 0x20:
            out += f"\\u{cp:04x}".encode("ascii")
        elif 0xD800 <= cp <= 0xDFFF:
            raise JCSNameError(f"lone surrogate in string: U+{cp:04X}")
        else:
            out += ch.encode("utf-8")
    out += b'"'
    return bytes(out)


def _es6_number_to_string(f: float) -> str:
    """ES6 Number::toString для float: кратчайшие round-trip цифры те же, что у
    Python repr (оба строят кратчайший корректно-округлённый десятичный вид);
    различается только формат экспоненты/фиксированной записи."""
    if math.isnan(f) or math.isinf(f):
        raise JCSNameError(f"non-finite float is not JCS-serializable: {f!r}")
    if f == 0:
        return "0"  # ES6: и 0.0, и -0.0 печатаются как "0"
    if f.is_integer() and abs(f) < 1e21:
        return str(int(f))  # ES6 fixed notation для целых значений < 1e21
    r = repr(f)  # shortest round-trip: '4.5', '1.5e-07', '1e+30', '123.456'
    if "e" not in r and "E" not in r:
        return r  # Python fixed == ES6 fixed в этой зоне
    mant, exp_s = r.split("e")
    exp = int(exp_s)
    digits = mant.replace("-", "").replace(".", "").rstrip("0") or "0"
    lead = "-" if mant.startswith("-") else ""
    if -6 <= exp <= 20:
        # ES6 fixed: точка после exp+1 значащих цифр
        if exp >= 0:
            int_part = digits[: exp + 1].ljust(exp + 1, "0")
            frac = digits[exp + 1:]
            return lead + int_part + ("." + frac if frac else "")
        return lead + "0." + "0" * (-exp - 1) + digits
    # ES6 exponential: мантисса d[.ddd], экспонента без ведущих нулей
    e_sig = ("+" if exp > 0 else "-") + str(abs(exp))
    m = digits[0] + ("." + digits[1:] if len(digits) > 1 else "")
    return f"{lead}{m}e{e_sig}"


def _serialize(value: Any) -> bytes:
    if value is None:
        return b"null"
    if value is True:
        return b"true"
    if value is False:
        return b"false"
    if isinstance(value, int):
        return str(value).encode("ascii")
    if isinstance(value, float):
        return _es6_number_to_string(value).encode("ascii")
    if isinstance(value, str):
        return _serialize_string(value)
    if isinstance(value, (list, tuple)):
        return b"[" + b",".join(_serialize(v) for v in value) + b"]"
    if isinstance(value, dict):
        items = sorted(value.items(), key=lambda kv: _utf16_units(kv[0]))
        parts = [_serialize_string(k) + b":" + _serialize(v) for k, v in items]
        return b"{" + b",".join(parts) + b"}"
    raise JCSNameError(f"unsupported type: {type(value).__name__}")


def canonicalize(value: Any) -> bytes:
    """RFC 8785: значение → канонические байты UTF-8."""
    return _serialize(value)


def canonicalize_json(text: str) -> bytes:
    """Строка JSON → канонические байты (parse + canonicalize)."""
    return canonicalize(json.loads(text))


if __name__ == "__main__":
    # Самопроверка на канонических примерах RFC 8785 (§3.2.3, §4.2.2)
    cases = [
        ({"numbers": [1e30, 4.50, 2e-3]},
         b'{"numbers":[1e+30,4.5,0.002]}'),
    ]
    ok = True
    got = canonicalize(cases[0][0])
    print("numbers  :", got.decode("ascii"), "→", "PASS" if got == cases[0][1] else "FAIL")
    ok &= got == cases[0][1]
    # сортировка: UTF-16 code units; "\u20ac" (€) AFTER "\u00fc"?? — по UTF-16:
    # U+00FC < U+20AC; ASCII цифры/пробелы раньше букв; escapes по §3.2.2.2
    sample = {"\u20ac": "euro", "\u00fc": "u-uml", "0": "zero", "\u0080": "ctl",
              "\n": "nl", " ": "sp"}
    got2 = canonicalize(sample)
    print("sortings :", got2.decode("utf-8"))
    # строгие ожидания: "\n"(0x0A) < " "(0x20) < "0"(0x30) < "\u0080" < "\u00fc" < "\u20ac"
    expect2 = ('{"\\n":"nl"," ":"sp","0":"zero","\u0080":"ctl",'
               '"\u00fc":"u-uml","\u20ac":"euro"}').encode("utf-8")
    print("expect   :", expect2.decode("utf-8"), "→", "PASS" if got2 == expect2 else "FAIL")
    ok &= got2 == expect2
    # экспоненты: ES6 без ведущих нулей
    e1 = canonicalize([1.5e-7, 1e21, 1e20, -0.0, 1e-7])
    print("exponents:", e1.decode("ascii"))
    print("SELFTEST :", "PASS" if ok else "FAIL")
    raise SystemExit(0 if ok else 1)
