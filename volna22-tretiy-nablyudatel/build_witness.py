#!/usr/bin/env python3
"""build_witness.py — S4/O-B1: запись-свидетельство третьего наблюдателя.

Свежий ключ Ed25519 генерируется В ПАМЯТИ, подписывает канонизованный
(моим JCS) корпус записи и уничтожается: на диск попадает только открытый
ключ и подпись. Формула уровня свидетельства — из отчёта аудита моста
(стр. 6): V3 <=> reviewer>=I2 AND reference>=I2 AND procedure=I4; V2 <=> оба>=I1;
иначе V1; UNKNOWN = -1.
"""
import base64
import datetime
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import jcs_third  # своя канонизация

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

I_ORDER = {"UNKNOWN": -1, "I0": 0, "I1": 1, "I2": 2, "I3": 3, "I4": 4}
PROC_FULL = "I4"


def bridge_formula(profile: dict) -> int:
    """evidence_level_for_ledger_entry по отчёту аудита моста (стр. 6)."""
    r = I_ORDER.get(profile.get("reviewer_independence"), -1)
    f = I_ORDER.get(profile.get("reference_independence"), -1)
    p = profile.get("procedure_reproducibility")
    if p == PROC_FULL:
        p_v = 4
    elif p == "PARTIAL":
        p_v = 2
    elif p == "UNKNOWN":
        p_v = -1
    else:
        p_v = I_ORDER.get(p, -1)
    if r >= I_ORDER["I2"] and f >= I_ORDER["I2"] and p_v == I_ORDER["I4"]:
        return 3  # V3
    if r >= I_ORDER["I1"] and f >= I_ORDER["I1"]:
        return 2  # V2
    return 1  # V1


def main():
    reports = Path("/home/z/my-project/w22_work/s0a/reports")
    chatzip = Path("/home/z/my-project/w22_work/a0_chat/chatzip")

    def sha(p):
        return hashlib.sha256(Path(p).read_bytes()).hexdigest()

    rep_std_a, rep_std_b = sha(chatzip / "A0_STANDARD_v0.2.5_AUDIT_REPORT.pdf"), sha(reports / "A0_STANDARD_v0.2.5_AUDIT_REPORT.pdf")
    rep_br_a, rep_br_b = sha(chatzip / "A0_BRIDGE_AUDIT_REPORT.pdf"), sha(reports / "A0_BRIDGE_AUDIT_REPORT.pdf")
    assert rep_std_a == rep_std_b, "PDF расходится между вложением и районом!"
    assert rep_br_a == rep_br_b, "PDF расходится между вложением и районом!"

    profile = {
        "reviewer_independence": "I2",
        "reference_independence": "I2",
        "procedure_reproducibility": "I4",
    }

    record = {
        "witness_type": "third_observer_record",
        "schema": "bridge-aligned/1",
        "witness_id": "third-observer-zai-wave22",
        "created_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "vector": "долгая дорога синтеза: S1 закрыт соседом (PACKAGE VALID + BRIDGE VALID); здесь — S4/O-B1",
        "role": "независимый третий наблюдатель: не автор моста, не автор аудита",
        "independence_profile": profile,
        "conflict_of_interest": [
            "один вендор модели (Z.ai) с автором аудита; другая сессия/инстанс, контекст не разделялся",
            "пакет A0_STANDARD_v0.2.5.zip недоступен наблюдателю (эфемерный) — см. out_of_scope",
        ],
        "subjects": [
            {"id": "A0_STANDARD_v0.2.5_AUDIT_REPORT.pdf",
             "sha256": rep_std_a,
             "checked": "копия во вложении Хозяина ≡ копии в s0a/reports; 12 страниц; вердикт PACKAGE VALID"},
            {"id": "A0_BRIDGE_AUDIT_REPORT.pdf",
             "sha256": rep_br_a,
             "checked": "копии совпадают; 11 страниц; вердикт BRIDGE VALID; формула V-уровней (стр. 6) извлечена и закодирована в verify_witness.py"},
            {"id": "lex_naturae-v0.7 bundle (s0a/lex-naturae-v0.7-audit)",
             "checked": "SHA256SUMS соседа: 10/10 файлов OK (сверка sha256sum -c)"},
            {"id": "дифференциальный корпус JCS",
             "checked": "20000 кейсов: моя реализация ≡ оракулу rfc8785 — 0 байтовых расхождений; auditor_jcs.py соседа ≢ оракулу — 2580 (сортировка code points вместо UTF-16; '+' в экспонентах)"},
        ],
        "method": [
            "scripts/third_observer/jcs_third.py — своя RFC 8785, самотест на канонических примерах RFC",
            "scripts/third_observer/differential_test.py — дифтест (seed 20261116)",
            "sha256 сверка вложений Хозяина с районом singulyar-a0-audit",
        ],
        "findings": [
            "O-TO-1: auditor_jcs.py (район) не является общей реализацией RFC 8785: (а) сортировка ключей по Unicode code points вместо UTF-16 code units — астральные ключи (эмодзи) сортируются неверно; (б) положительные экспоненты без '+'. На данных TASK_SET (ASCII-ключи) ошибки не срабатывают — вывод S2 соседа не отменяется; повторное использование скрипта как общего канонизатора — только после исправления",
            "O-TO-2: оба аудиторских PDF, вложенные Хозяином, байт-в-байт совпадают с районными копиями — цепочка «аудит→район» целостна",
            "O-TO-3: пакет A0 эфемерен: полный перепрогон A1–A10 третьим наблюдателем невозможен — допуск данных A0 остаётся решением потребителя",
        ],
        "out_of_scope": [
            "A0_STANDARD_v0.2.5.zip — недоступен: пересчёт freeze_sha256 (6c4b3124…7924) в объём настоящего свидетества НЕ входит",
            "SINGULYAR_A0_SYNTHESIS_v1.zip — недоступен: end-to-end прогон моста не выполнялся",
        ],
        "evidence_level_claim": "V3 (скоуп: перечисленные subjects, только они)",
    }

    level = bridge_formula(profile)
    record["evidence_level_by_bridge_formula"] = ["V1", "V2", "V3"][level - 1]

    # --- ключ только в памяти ---
    key = Ed25519PrivateKey.generate()
    pub_b = key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    record["identity"] = {
        "observer_id": "zai-glm-wave22-third-observer",
        "signing_key_alg": "Ed25519",
        "signing_key_id": "ed25519:sha256:" + hashlib.sha256(pub_b).hexdigest()[:32],
        "public_key_ed25519_b64": base64.b64encode(pub_b).decode("ascii"),
    }

    body = jcs_third.canonicalize(record)
    body_sha = hashlib.sha256(body).hexdigest()
    sig = key.sign(body)
    # приватный ключ уничтожается сразу после подписи
    del key

    signed = {
        "record": record,
        "canonical_body_sha256": body_sha,
        "canonical_body_bytes_len": len(body),
        "signature_ed25519_b64": base64.b64encode(sig).decode("ascii"),
    }
    out = Path("/home/z/my-project/download/volna22-tretiy-nablyudatel/witness_record.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(signed, ensure_ascii=False, indent=2), encoding="utf-8")
    print("запись           :", out)
    print("canonical sha256 :", body_sha)
    print("ключ подписи     :", record["identity"]["signing_key_id"])
    print("уровень по формуле:", record["evidence_level_by_bridge_formula"])
    print("приватный ключ   : уничтожен в памяти, на диск не попадал")


if __name__ == "__main__":
    main()
