#!/usr/bin/env python3
"""verify_witness.py — независимая верификация записи третьего наблюдателя.

Проверяет: (1) канонизованный корпус записи пересчитывается в заявленный
sha256; (2) подпись Ed25519 верна под открытым ключом из записи; (3) уровень
свидетельства по формуле моста совпадает с заявленным. Использует СВОЮ
канонизацию (jcs_third.py) и библиотеку cryptography — те же независимые
компоненты, что и при подписи; никакой связи с приватным ключом (он уничтожен).
"""
import base64
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from jcs_third import canonicalize  # своя канонизация
from build_witness import bridge_formula

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def main(path):
    signed = json.loads(Path(path).read_text(encoding="utf-8"))
    record = signed["record"]

    body = canonicalize(record)
    body_sha = hashlib.sha256(body).hexdigest()
    ok_body = body_sha == signed["canonical_body_sha256"]
    ok_len = len(body) == signed["canonical_body_bytes_len"]

    pub = Ed25519PublicKey.from_public_bytes(
        base64.b64decode(record["identity"]["public_key_ed25519_b64"]))
    sig = base64.b64decode(signed["signature_ed25519_b64"])
    try:
        pub.verify(sig, body)
        ok_sig = True
    except Exception:
        ok_sig = False

    level = bridge_formula(record["independence_profile"])
    claimed = {"V1": 1, "V2": 2, "V3": 3}[record["evidence_level_by_bridge_formula"]]
    ok_level = level == claimed

    print("корпус канонизуется байт-в-байт :", "PASS" if ok_body else "FAIL")
    print("длина корпуса                   :", "PASS" if ok_len else "FAIL")
    print("подпись Ed25519 верна           :", "PASS" if ok_sig else "FAIL")
    print("уровень по формуле моста        :", f"{record['evidence_level_by_bridge_formula']} (PASS)" if ok_level else "FAIL")
    verdict = ok_body and ok_len and ok_sig and ok_level
    print("\nИТОГ:", "VERIFIED" if verdict else "NOT_VERIFIED")
    return 0 if verdict else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else
                          "/home/z/my-project/download/volna22-tretiy-nablyudatel/witness_record.json"))
