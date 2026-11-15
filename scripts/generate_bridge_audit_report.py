#!/usr/bin/env python3
"""Generate formal bridge auditor report PDF for SINGULYAR_A0_SYNTHESIS_v1 a0_bridge.py.

Companion to A0_STANDARD_v0.2.5_AUDIT_REPORT.pdf. Closes S1 of the synthesis roadmap.
Output: /home/z/my-project/download/A0_BRIDGE_AUDIT_REPORT.pdf
"""
import hashlib
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.platypus import (
    Paragraph, Spacer, PageBreak, Table, TableStyle, HRFlowable,
)
from reportlab.platypus.doctemplate import PageTemplate, BaseDocTemplate, NextPageTemplate
from reportlab.platypus.frames import Frame

# --- font registration (Cyrillic-capable) ---
FD = "/usr/share/fonts/truetype/liberation"
pdfmetrics.registerFont(TTFont("LibSans", f"{FD}/LiberationSans-Regular.ttf"))
pdfmetrics.registerFont(TTFont("LibSans-Bold", f"{FD}/LiberationSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("LibSans-Italic", f"{FD}/LiberationSans-Italic.ttf"))
registerFontFamily("LibSans", normal="LibSans", bold="LibSans-Bold", italic="LibSans-Italic")
pdfmetrics.registerFont(TTFont("LibSerif", f"{FD}/LiberationSerif-Regular.ttf"))
pdfmetrics.registerFont(TTFont("LibSerif-Bold", f"{FD}/LiberationSerif-Bold.ttf"))
pdfmetrics.registerFont(TTFont("LibSerif-Italic", f"{FD}/LiberationSerif-Italic.ttf"))
registerFontFamily("LibSerif", normal="LibSerif", bold="LibSerif-Bold", italic="LibSerif-Italic")
pdfmetrics.registerFont(TTFont("LibMono", f"{FD}/LiberationMono-Regular.ttf"))
pdfmetrics.registerFont(TTFont("LibMono-Bold", f"{FD}/LiberationMono-Bold.ttf"))
registerFontFamily("LibMono", normal="LibMono", bold="LibMono-Bold")

# --- palette ---
C_TEXT = colors.HexColor("#111111")
C_MUTED = colors.HexColor("#555555")
C_BG_HEADER = colors.HexColor("#1f2937")
C_BG_SUB = colors.HexColor("#e5e7eb")
C_BG_ROW_ALT = colors.HexColor("#f5f5f5")
C_PASS = colors.HexColor("#1f7a3a")
C_FAIL = colors.HexColor("#a3160c")
C_UNKNOWN = colors.HexColor("#a16207")
C_RULE = colors.HexColor("#9ca3af")

# --- styles ---
H1 = ParagraphStyle("H1", fontName="LibSans-Bold", fontSize=15, leading=21,
                    textColor=C_TEXT, spaceBefore=10, spaceAfter=7)
H2 = ParagraphStyle("H2", fontName="LibSans-Bold", fontSize=12, leading=16,
                    textColor=C_BG_HEADER, spaceBefore=10, spaceAfter=4)
H3 = ParagraphStyle("H3", fontName="LibSans-Bold", fontSize=10.5, leading=14,
                    textColor=C_TEXT, spaceBefore=6, spaceAfter=3)
BODY = ParagraphStyle("BODY", fontName="LibSerif", fontSize=10, leading=14,
                      textColor=C_TEXT, spaceAfter=4)
BODY_TIGHT = ParagraphStyle("BT", fontName="LibSerif", fontSize=9.5, leading=13,
                            textColor=C_TEXT, spaceAfter=2)
CELL = ParagraphStyle("CELL", fontName="LibSerif", fontSize=8.8, leading=11.5,
                      textColor=C_TEXT)
CELL_MONO = ParagraphStyle("CELLM", fontName="LibMono", fontSize=7.8, leading=10.5,
                           textColor=C_TEXT)
CELL_CENTER = ParagraphStyle("CC", fontName="LibSerif", fontSize=9, leading=12,
                             textColor=C_TEXT, alignment=1)
CELL_PASS = ParagraphStyle("CP", fontName="LibSans-Bold", fontSize=9, leading=12,
                           textColor=C_PASS, alignment=1)
COVER_TITLE = ParagraphStyle("CT", fontName="LibSerif-Bold", fontSize=22, leading=28,
                             textColor=C_TEXT, alignment=0, spaceAfter=6)
COVER_SUB = ParagraphStyle("CS", fontName="LibSans", fontSize=12, leading=16,
                           textColor=C_MUTED, alignment=0, spaceAfter=4)
COVER_META = ParagraphStyle("CM", fontName="LibMono", fontSize=9.5, leading=13,
                            textColor=C_TEXT, alignment=0)
COVER_VERDICT = ParagraphStyle("CV", fontName="LibSans-Bold", fontSize=12.5, leading=16,
                               textColor=C_PASS, alignment=0, spaceBefore=8, spaceAfter=4)

# --- data ---
SYN_ARCHIVE = "SINGULYAR_A0_SYNTHESIS_v1.zip"
SYN_SHA256 = "e147fdb4e0c911ba7c4243cb9747412d3ac7440e474e57aa05d0eb89864fbb95"
AUDIT_DATE = "2026-11-15"
AUDITOR_OS = "Debian GNU/Linux 13 (trixie), Linux 5.10.134-013.15.kangaroo.al8.x86_64"
AUDITOR_PYTHON = "Python 3.12.16"
AUDITOR_PKGS = "jsonschema 4.26.0, rfc8785 0.1.4, rfc3339-validator 0.1.4, rfc3986-validator 0.1.1, pytest 9.2.0"
VENDORED_A0_DIGEST = "68b8343cde730eb44b21411baa59afe668ec1f2f1359dc3f89743c8f61d39d8d"
FREEZE_HASH = "6c4b312479cd49f04c93324d8eec06afd11e15dfff64903ccbb819ff22147924"
ARCHIVE_A0_SHA256 = "85f74444e3cc4fb6b63cf043937d4d9be5dc23a9124b2c4958b7735e6fd6fde4"

LOG_DIR = Path("/home/z/my-project/scripts/audit_a0/logs")
def log_hash(name):
    p = LOG_DIR / name
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16] if p.is_file() else "—"

# --- document setup ---
OUT_PDF = "/home/z/my-project/download/A0_BRIDGE_AUDIT_REPORT.pdf"
PAGE_W, PAGE_H = A4
MARGIN_L = 2.0 * cm
MARGIN_R = 2.0 * cm
MARGIN_T = 2.0 * cm
MARGIN_B = 2.0 * cm
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R


class BridgeDoc(BaseDocTemplate):
    def __init__(self, filename, **kw):
        super().__init__(filename, pagesize=A4,
                         leftMargin=MARGIN_L, rightMargin=MARGIN_R,
                         topMargin=MARGIN_T, bottomMargin=MARGIN_B,
                         title="SINGULYAR × A0 — Отчёт аудита моста a0_bridge.py",
                         author="Z.ai (независимый аудитор)",
                         subject="BRIDGE VALID audit per AUDIT_PROTOCOL.md + constitution X1/X2",
                         creator="Z.ai")
        frame = Frame(MARGIN_L, MARGIN_B, CONTENT_W,
                      PAGE_H - MARGIN_T - MARGIN_B, id="main",
                      leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates([
            PageTemplate(id="cover", frames=[frame], onPage=self._cover_page),
            PageTemplate(id="body", frames=[frame], onPage=self._body_page),
        ])

    def _cover_page(self, canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(C_RULE)
        canvas.setLineWidth(0.6)
        canvas.line(MARGIN_L, PAGE_H - MARGIN_T - 0.3*cm,
                    PAGE_W - MARGIN_R, PAGE_H - MARGIN_T - 0.3*cm)
        canvas.line(MARGIN_L, MARGIN_B + 0.3*cm,
                    PAGE_W - MARGIN_R, MARGIN_B + 0.3*cm)
        canvas.setFont("LibSans", 8)
        canvas.setFillColor(C_MUTED)
        canvas.drawString(MARGIN_L, MARGIN_B - 0.7*cm,
                          "Z.ai · Независимый аудитор · SINGULYAR × A0 synthesis")
        canvas.drawRightString(PAGE_W - MARGIN_R, MARGIN_B - 0.7*cm,
                               "Отчёт аудита моста · 2026-11-15")
        canvas.restoreState()

    def _body_page(self, canvas, doc):
        canvas.saveState()
        canvas.setFont("LibSans", 8)
        canvas.setFillColor(C_MUTED)
        canvas.drawString(MARGIN_L, MARGIN_B - 0.7*cm,
                          "SINGULYAR × A0 — Отчёт аудита моста a0_bridge.py")
        canvas.drawRightString(PAGE_W - MARGIN_R, MARGIN_B - 0.7*cm,
                               f"стр. {doc.page - 1}")
        canvas.setStrokeColor(C_RULE)
        canvas.setLineWidth(0.3)
        canvas.line(MARGIN_L, MARGIN_B - 0.2*cm,
                    PAGE_W - MARGIN_R, MARGIN_B - 0.2*cm)
        canvas.restoreState()


def hr():
    return HRFlowable(width="100%", thickness=0.4, color=C_RULE,
                      spaceBefore=4, spaceAfter=4)


def status_cell(label):
    s = label.upper()
    if s == "PASS": return Paragraph("PASS", CELL_PASS)
    if s == "FAIL":
        return Paragraph("FAIL", ParagraphStyle("CF", fontName="LibSans-Bold",
            fontSize=9, leading=12, textColor=C_FAIL, alignment=1))
    if s == "UNKNOWN":
        return Paragraph("UNKNOWN", ParagraphStyle("CU", fontName="LibSans-Bold",
            fontSize=9, leading=12, textColor=C_UNKNOWN, alignment=1))
    return Paragraph(label, CELL_CENTER)


# --- content ---
story = []

# === COVER ===
story.append(Spacer(1, 1.5*cm))
story.append(Paragraph("Отчёт независимого аудита моста", COVER_SUB))
story.append(Spacer(1, 0.2*cm))
story.append(Paragraph("SINGULYAR × A0 — a0_bridge.py", COVER_TITLE))
story.append(Paragraph("Проверка соответствия статьям X1/X2 конституции и замыкание S1 дорожной карты",
                       COVER_SUB))
story.append(Spacer(1, 0.6*cm))
story.append(hr())
story.append(Spacer(1, 0.3*cm))
story.append(Paragraph(f"<b>Архив синтеза:</b> {SYN_ARCHIVE}", COVER_META))
story.append(Paragraph(f"<b>SHA-256 архива синтеза:</b> {SYN_SHA256}", COVER_META))
story.append(Paragraph(f"<b>Вендорная копия A0 v0.2.5:</b> SHA-256 MANIFEST.json = {VENDORED_A0_DIGEST}", COVER_META))
story.append(Paragraph(f"<b>Дата аудита:</b> {AUDIT_DATE}", COVER_META))
story.append(Paragraph(f"<b>Аудитор:</b> Z.ai (третья сторона, не участвовала в сборке синтеза)", COVER_META))
story.append(Spacer(1, 0.4*cm))
story.append(Paragraph(f"<b>ОС:</b> {AUDITOR_OS}", COVER_META))
story.append(Paragraph(f"<b>Python:</b> {AUDITOR_PYTHON}", COVER_META))
story.append(Paragraph(f"<b>Версии:</b> {AUDITOR_PKGS}", COVER_META))
story.append(Spacer(1, 0.6*cm))
story.append(hr())
story.append(Spacer(1, 0.3*cm))
story.append(Paragraph("Вердикт (кратко):", COVER_SUB))
story.append(Paragraph(
    "BRIDGE VALID. Мост a0_bridge.py faithfully реализует статьи X1 (допуск к A0 как "
    "управляемый переход) и X2 (единая дисциплина статусов) конституции редакции 2. "
    "H-020: 9/9 PASS. Собственные мутации аудитора BM-A…BM-L: 12/12 PASS. "
    "Разрыв HOST-V3 ↔ A0-ledger-V1 (наблюдатель написан тем же автором) честно "
    "раскрыт в поле conflict_of_interest и задокументирован как открытое решение "
    "(06_INTEGRATION.md #2); закрывается этапом S4 (Ed25519 от отдельного ключа). "
    "FAIL не обнаружено. S1 дорожной карты синтеза закрыта.",
    COVER_VERDICT))
story.append(Spacer(1, 0.5*cm))
story.append(hr())
story.append(Spacer(1, 0.2*cm))
story.append(Paragraph(
    "Отчёт — компаньон к A0_STANDARD_v0.2.5_AUDIT_REPORT.pdf. Вместе они замыкают "
    "этап S1 дорожной карты синтеза: A0-аудит (PACKAGE VALID) + мост-аудит "
    "(BRIDGE VALID). Допуск к запуску A0 — отдельное решение и этим отчётом не "
    "выдаётся; мост корректно его принуждает (без V3 от независимого наблюдателя и "
    "совпадения хеша манифеста запуск невозможен).",
    BODY_TIGHT))

story.append(PageBreak())

# === SECTION 1 ===
story.append(Paragraph("1. Общие сведения", H1))
story.append(Paragraph(
    "Настоящий отчёт — компаньон к отчёту аудита A0_STANDARD v0.2.5. Аудит A0 "
    "установил статус PACKAGE VALID для вендорной копии A0 v0.2.5 в составе синтеза "
    "(SHA-256 MANIFEST.json = <font name='LibMono'>68b8343c…9d8d</font>). "
    "Настоящий отчёт проверяет <b>мост</b> между HOST и A0 — модуль "
    "<font name='LibMono'>singulyar_host/a0_bridge.py</font> — на соответствие "
    "статьям X1 (Допуск измерения) и X2 (Единая дисциплина статусов) конституции "
    "редакции 2, а также гарантиям G3 (EVIDENCE), G7 (ACTIVATION) и G2 "
    "(EXECUTION_BINDING), которые X1/X2 реализуют.", BODY))
story.append(Paragraph(
    "Аудит выполнен статически (чтение кода моста, кода опыта H-020, кода ядра и "
    "наблюдателя, текста конституции, схемы EVIDENCE_LEDGER, документа интеграции) "
    "и динамически (прогон verify_all.py, прогон H-020, 12 собственных мутаций "
    "аудитора на мосту). Логи сохранены и приложены (Приложение A).", BODY))

story.append(Paragraph("1.1. Идентификация синтеза", H3))
ident = [
    ("Архив синтеза", SYN_ARCHIVE),
    ("SHA-256 архива синтеза", SYN_SHA256),
    ("Вендорная копия A0", "a0_standard/A0_STANDARD_v0.2.5/"),
    ("SHA-256 MANIFEST.json вендорной копии", VENDORED_A0_DIGEST),
    ("freeze_sha256 TASK_SET вендорной копии", FREEZE_HASH),
    ("Совпадение с отдельным архивом A0", "ДА (отдельный A0_STANDARD_v0.2.5.zip прошёл аудит — см. A0_STANDARD_v0.2.5_AUDIT_REPORT.pdf)"),
    ("Архив A0 (отдельно, для перекрёстной ссылки)", f"SHA-256 {ARCHIVE_A0_SHA256}"),
    ("Объект аудита (модуль)", "singulyar_host/a0_bridge.py (243 строки)"),
    ("Объект аудита (опыт)", "singulyar_host/experiments/h020_a0_admission_gate.py (101 строка)"),
    ("Конституция", "CONSTITUTION.md, редакция 2 (7 гарантий G1–G7, мета M1–M4, мост X1/X2)"),
    ("Документ интеграции", "docs/06_INTEGRATION.md (5 открытых решений)"),
    ("Дорожная карта", "docs/02_ROADMAP.md (R0 готово; R1–R7 + S1–S4)"),
]
t = Table([[Paragraph(k, CELL), Paragraph(v, CELL_MONO)] for k, v in ident],
          colWidths=[6.0*cm, 11.0*cm])
t.setStyle(TableStyle([
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ("TOPPADDING", (0, 0), (-1, -1), 2),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ("GRID", (0, 0), (-1, -1), 0.25, C_RULE),
    ("BACKGROUND", (0, 0), (0, -1), C_BG_SUB),
    ("ROWBACKGROUNDS", (1, 0), (1, -1), [colors.white, C_BG_ROW_ALT]),
]))
story.append(t)

# === SECTION 2 ===
story.append(PageBreak())
story.append(Paragraph("2. Независимость аудитора и метод", H1))
story.append(Paragraph(
    "Аудитор — Z.ai, третья сторона, не участвовавшая в написании кода синтеза "
    "(включая <font name='LibMono'>a0_bridge.py</font>, <font name='LibMono'>h020</font>, "
    "конституцию, документ интеграции). Аудит выполнен в чистом виртуальном окружении "
    "Python 3.12.16, Debian 13 trixie (отличается от среды сборки дистрибутивом; "
    "минор Python совпадает). Зависимости установлены из "
    "<font name='LibMono'>requirements.txt</font> A0 + <font name='LibMono'>pytest</font> "
    "для тестов HOST.", BODY))
story.append(Paragraph(
    "<b>Метод:</b> статический аудит кода моста и его зависимостей + динамический "
    "прогон (verify_all, H-020) + 12 собственных мутаций аудитора, не входящих в "
    "H-020. Собственные мутации покрывают: отказ самоаттестации (G3/H-008 в контексте "
    "моста), путь отказа ATTEST → экспорт UNKNOWN, схема-валидность экспорта на пути "
    "отказа, структуру gate_suite, границы порогов V-уровней (I2/I2/PARTIAL → V2; "
    "UNKNOWN → V1; I3/I3/I4 → V3), кейсы passport_verdicts, разрыв HOST-V3 vs "
    "A0-ledger-V1 с проверкой честного раскрытия, отсутствие MANIFEST → NO_MANIFEST, "
    "инспекция пакета не оставляет __pycache__.", BODY))

# === SECTION 3: Что аудировалось ===
story.append(Paragraph("3. Объект аудита и зависимости", H1))
story.append(Paragraph(
    "Мост <font name='LibMono'>a0_bridge.py</font> зависит от: "
    "<font name='LibMono'>host.py</font> (EXECUTOR, OBSERVER_ID, OBSERVER_KEY, build_host), "
    "<font name='LibMono'>kernel.py</font> (HostKernel, TransitionRequest, TransitionReport, governed_transition), "
    "<font name='LibMono'>ontology.py</font> (Effect, Grammar, Instance, Space, Verdict, World), "
    "<font name='LibMono'>verification.py</font> (EvidenceLevel, ExecutionRecord, ExternalCriteria, Identity, Observer, TestSuite, Verifier). "
    "Все зависимости прочитаны аудитором; их поведение проверено динамически через "
    "прогоны H-020 и собственных мутаций.", BODY))
story.append(Paragraph(
    "Мост реализует следующие публичные функции:", BODY))
funcs = [
    ("package_digest(root)", "SHA-256 файла MANIFEST.json — отпечаток пакета"),
    ("inspect_package(root, claimed_digest)", "Запускает INTEGRITY/VALIDATOR/11 негативных; проверяет freeze ≠ placeholder; сверяет хеш манифеста. Возвращает 5 булевых фактов."),
    ("A0PackageObserver(Observer)", "Независимый свидетель: расширяет Observer.witness, добавляя 5 фактов A0 в артефакт."),
    ("gate_suite()", "TestSuite с 3 тестами + ExternalCriteria с 6 A0_PROPS"),
    ("build_gate_host(root, claimed_digest)", "Host с миром из одного пакета (под заявленным хешем) и стандарта; A0PackageObserver"),
    ("request_admission(host)", "governed_transition с эффектом ADD_RELATION(ADMITTED, pkg, standard)"),
    ("a0_run_allowed(host, root)", "Перед запуском A0: ADMITTED relation для текущего хеша + INTEGRITY_CHECK OK"),
    ("evidence_level_for_ledger_entry(entry)", "Профиль I0–I4 → V1/V2/V3 по конъюнкции осей (не лестница)"),
    ("STATUS_TO_VERDICT + passport_verdicts", "6 статусов A0 → 4 Verdict HOST; NOT_TESTED/NOT_APPLICABLE → UNKNOWN"),
    ("attestation_to_ledger_entry(report, digest)", "Экспорт TransitionReport в запись EVIDENCE_LEDGER.schema.json A0"),
]
data = [[Paragraph("Функция", ParagraphStyle("fh1", fontName="LibSans-Bold", fontSize=9,
                                              leading=11, textColor=colors.white)),
         Paragraph("Назначение", ParagraphStyle("fh2", fontName="LibSans-Bold", fontSize=9,
                                                leading=11, textColor=colors.white))]]
for n, d in funcs:
    data.append([Paragraph(n, CELL_MONO), Paragraph(d, CELL)])
ft = Table(data, colWidths=[5.5*cm, 11.5*cm], repeatRows=1)
ft.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), C_BG_HEADER),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ("TOPPADDING", (0, 0), (-1, -1), 3),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ("GRID", (0, 0), (-1, -1), 0.25, C_RULE),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, C_BG_ROW_ALT]),
]))
story.append(ft)

# === SECTION 4: Соответствие конституции ===
story.append(PageBreak())
story.append(Paragraph("4. Соответствие статьям конституции (статический аудит)", H1))
story.append(Paragraph(
    "Конституция редакции 2 (CONSTITUTION.md) определяет в части VII (Мост с A0) "
    "две статьи X1 и X2, реализующие гарантии G3, G7, G2 в применении к A0. Ниже — "
    "проверка каждой статьи и гарантии по коду моста.", BODY))

conf_rows = [
    ("X1", "Допуск измерения: запуск A0 — управляемый переход; V3 от независимого наблюдателя, который сам прогоняет INTEGRITY/VALIDATOR/11 тестов и сверяет хеш манифеста; CAS по HEAD закрепляет допуск за хешем; правка пакета гасит допуск.",
     "request_admission → governed_transition; A0PackageObserver.witness → inspect_package; gate_suite → Verifier.verify → V3; ACTIVATE стадия CAS; a0_run_allowed сверяет текущий хеш с ADMITTED relation",
     "PASS"),
    ("X2", "Единая дисциплина статусов: CONFIRMED/REFUTED/DISPUTED/UNKNOWN/NOT_TESTED/NOT_APPLICABLE ↔ PASS/FAIL/CONTESTED/UNKNOWN; NOT_TESTED и NOT_APPLICABLE не становятся PASS; I0–I4 — профиль, не лестница.",
     "STATUS_TO_VERDICT (6→4, NOT_TESTED/NOT_APPLICABLE→UNKNOWN); passport_verdicts; evidence_level_for_ledger_entry (конъюнкция осей, не сумма)",
     "PASS"),
    ("G3", "V3 только при: независимый наблюдатель со своим ключом, детерминированные тесты, внешние критерии; исполнитель себя не подтверждает.",
     "Verifier.verify проверяет record.signature_key_id ≠ executor.signing_key_id; _check_self_attestation (H-008); TestSuite.run; ExternalCriteria.check; min_level=3",
     "PASS"),
    ("G7", "ACTIVATION: ровно один HEAD на линию; CAS; при разделе — никого.",
     "kernel.py governed_transition стадия ACTIVATE — CAS по HEAD; ActivationRegistry",
     "PASS"),
    ("G2", "EXECUTION_BINDING: применённый эффект обязан совпасть с разрешённым (по хешу).",
     "Observer.witness считает delta_hash от observed effects; Verifier.verify сверяет delta_hash == effects_digest(authorized); delta_matches_intent в A0_PROPS",
     "PASS"),
    ("M2", "Жизненный путь: PROPOSE→AUTHORIZE→RESERVE→ADMIT→(SCHEMA_ADMIT)→EXECUTE→ATTEST→ACTIVATE→SETTLE. ADMIT ≠ ACTIVATE.",
     "kernel.py governed_transition реализует все стадии; ATTEST и ACTIVATE разделены; эффект в кандидате, не в действующем мире до ACTIVATE",
     "PASS"),
    ("M4", "Честный статус: PASS/FAIL/UNKNOWN/CONTESTED/REFUSED. Корректный отказ — успех. Не доказанное не объявляется доказанным.",
     "TransitionReport.stages содержит DENIED:* / REFUSED:* / NOT_VERIFIED* / BLOCKED_NO_EVIDENCE; committed=False при отказе; export result_status='UNKNOWN' при не-V3",
     "PASS"),
]
header = [
    Paragraph("№", ParagraphStyle("ch1", fontName="LibSans-Bold", fontSize=9,
                                  leading=11, textColor=colors.white, alignment=1)),
    Paragraph("Требование конституции", ParagraphStyle("ch2", fontName="LibSans-Bold",
                                                       fontSize=9, leading=11, textColor=colors.white)),
    Paragraph("Реализация в коде моста", ParagraphStyle("ch3", fontName="LibSans-Bold",
                                                        fontSize=9, leading=11, textColor=colors.white)),
    Paragraph("Статус", ParagraphStyle("ch4", fontName="LibSans-Bold", fontSize=9,
                                       leading=11, textColor=colors.white, alignment=1)),
]
data = [header]
for r in conf_rows:
    data.append([
        Paragraph(r[0], CELL_CENTER),
        Paragraph(r[1], CELL),
        Paragraph(r[2], CELL_MONO),
        status_cell(r[3]),
    ])
ct = Table(data, colWidths=[0.8*cm, 6.0*cm, 8.5*cm, 1.7*cm], repeatRows=1)
ct.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), C_BG_HEADER),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ("TOPPADDING", (0, 0), (-1, -1), 3),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ("GRID", (0, 0), (-1, -1), 0.25, C_RULE),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, C_BG_ROW_ALT]),
]))
story.append(ct)
story.append(Spacer(1, 0.3*cm))
story.append(Paragraph(
    "<b>Итог по разделу 4:</b> все семь проверенных статей/гарантий реализованы в "
    "коде моста и соответствуют тексту конституции. Статических расхождений между "
    "текстом CONSTITUTION.md и кодом a0_bridge.py не обнаружено.", BODY))

# === SECTION 5: Dynamic checks ===
story.append(PageBreak())
story.append(Paragraph("5. Динамические проверки", H1))
story.append(Paragraph("5.1. Прогон verify_all.py (синтез целиком)", H3))
story.append(Paragraph(
    '<font name="LibMono">$ python tools/verify_all.py</font><br/>'
    '<font name="LibMono">[PASS] A0: INTEGRITY_CHECK (пакет A0 не изменён)</font><br/>'
    '<font name="LibMono">[PASS] A0: самотесты 7/7</font><br/>'
    '<font name="LibMono">[PASS] A0: VALIDATOR</font><br/>'
    '<font name="LibMono">[PASS] A0: негативные тесты 11/11</font><br/>'
    '<font name="LibMono">[PASS] HOST: selftest (демо + 14 экспериментов)</font><br/>'
    '<font name="LibMono">[PASS] HOST: pytest</font><br/>'
    '<font name="LibMono">[PASS] SYNTHESIS_MANIFEST (109 files)</font><br/>'
    '<font name="LibMono">ИТОГО: ВСЁ PASS</font> '
    f'(log={log_hash("SYN_verify_all.log")})',
    BODY_TIGHT))

story.append(Paragraph("5.2. Опыт H-020 (9 случаев)", H3))
h020_rows = [
    ("1", "до допуска", "запуск A0 запрещён (DIGEST_NOT_ADMITTED)", "PASS"),
    ("2", "допуск", "наблюдатель прогнал INTEGRITY/VALIDATOR/11; CAS закрепил; ADMITTED", "PASS"),
    ("3", "ложный хеш", "NOT_VERIFIED; a0_run_allowed=False", "PASS"),
    ("4", "испорченный пакет", "INTEGRITY провалена → нет V3 → нет ACTIVATE", "PASS"),
    ("5", "правка после допуска", "INTEGRITY_FAILED; после пересборки манифеста — DIGEST_NOT_ADMITTED", "PASS"),
    ("6", "профиль → уровень", "I3/I0 → V1 (оси не складываются)", "PASS"),
    ("7", "статусы", "NOT_TESTED/NOT_APPLICABLE → UNKNOWN", "PASS"),
    ("8", "экспорт", "запись HOST валидна по EVIDENCE_LEDGER.schema.json", "PASS"),
    ("9", "трасса", "хеш-цепочка допуска цела", "PASS"),
]
header = [
    Paragraph("№", ParagraphStyle("h1", fontName="LibSans-Bold", fontSize=9,
                                  leading=11, textColor=colors.white, alignment=1)),
    Paragraph("Случай", ParagraphStyle("h2", fontName="LibSans-Bold", fontSize=9,
                                       leading=11, textColor=colors.white)),
    Paragraph("Ожидание и результат", ParagraphStyle("h3", fontName="LibSans-Bold",
                                                     fontSize=9, leading=11, textColor=colors.white)),
    Paragraph("Статус", ParagraphStyle("h4", fontName="LibSans-Bold", fontSize=9,
                                       leading=11, textColor=colors.white, alignment=1)),
]
data = [header]
for r in h020_rows:
    data.append([Paragraph(r[0], CELL_CENTER), Paragraph(r[1], CELL),
                 Paragraph(r[2], CELL_MONO), status_cell(r[3])])
h0 = Table(data, colWidths=[0.8*cm, 3.5*cm, 10.5*cm, 1.7*cm], repeatRows=1)
h0.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), C_BG_HEADER),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ("TOPPADDING", (0, 0), (-1, -1), 3),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ("GRID", (0, 0), (-1, -1), 0.25, C_RULE),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, C_BG_ROW_ALT]),
]))
story.append(h0)
story.append(Spacer(1, 0.2*cm))
story.append(Paragraph(f"Прогон H-020: 9/9 PASS (log={log_hash('SYN_H020_detail.log')})", BODY_TIGHT))

story.append(Paragraph("5.3. Собственные мутации аудитора BM-A…BM-L (12 случаев, не в H-020)", H3))
bm_rows = [
    ("BM-A", "observer==executor → SelfAttestationRefused (G3/H-008)", "ATTEST='REFUSED: H-008…'; committed=False", "PASS"),
    ("BM-B", "failed ATTEST → export result_status='UNKNOWN'", "result_status='UNKNOWN'", "PASS"),
    ("BM-C", "failed-admission export schema-valid", "0 schema errors", "PASS"),
    ("BM-D", "gate_suite structure + inspect_package 5 facts all True", "suite.size=3; crit.props=6; facts={5×True}", "PASS"),
    ("BM-E", "I2/I2/PARTIAL → V2 (не V3)", "level=V2", "PASS"),
    ("BM-F", "UNKNOWN reviewer → V1", "level=V1", "PASS"),
    ("BM-G", "I3/I3/I4 → V3 (positive path)", "level=V3", "PASS"),
    ("BM-H", "empty claims → empty verdicts", "{}", "PASS"),
    ("BM-I", "NOT_APPLICABLE→UNKNOWN, CONFIRMED→PASS, REFUTED→FAIL", "verdicts={'C1':'UNKNOWN','C2':'PASS','C3':'FAIL'}", "PASS"),
    ("BM-J", "HOST-V3 vs A0-ledger-V1 gap honestly disclosed", "HOST_V3=True; ledger_level=V1; CoI disclosure present", "PASS"),
    ("BM-K", "missing manifest → NO_MANIFEST", "(False, 'NO_MANIFEST')", "PASS"),
    ("BM-L", "inspect_package leaves no __pycache__", "before==after", "PASS"),
]
data = [header]
for r in bm_rows:
    data.append([Paragraph(r[0], CELL_CENTER), Paragraph(r[1], CELL),
                 Paragraph(r[2], CELL_MONO), status_cell(r[3])])
bm = Table(data, colWidths=[1.2*cm, 6.5*cm, 7.3*cm, 1.5*cm], repeatRows=1)
bm.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), C_BG_HEADER),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ("TOPPADDING", (0, 0), (-1, -1), 3),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ("GRID", (0, 0), (-1, -1), 0.25, C_RULE),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, C_BG_ROW_ALT]),
]))
story.append(bm)
story.append(Spacer(1, 0.2*cm))
story.append(Paragraph(
    f"[AUDITOR_BRIDGE_MUTATIONS] 12/12 PASS (log={log_hash('SYN_bridge_mutations.log')}). "
    "Динамических дефектов не обнаружено.", BODY_TIGHT))

# === SECTION 6: Observations ===
story.append(PageBreak())
story.append(Paragraph("6. Наблюдения", H1))

story.append(Paragraph(
    "<b>O-B1 (главное): разрыв HOST-V3 ↔ A0-ledger-V1.</b> HOST даёт V3 при допуске "
    "по независимости ключа подписи (G3: <font name='LibMono'>record.signature_key_id "
    "≠ executor.signing_key_id</font>). Но в экспортируемой записи "
    "<font name='LibMono'>independence_profile</font> = {reviewer_independence: 'I1', "
    "reference_independence: 'UNKNOWN', procedure_reproducibility: 'PARTIAL'} — "
    "честная саморазметка того, что наблюдатель написан тем же автором, что и мост. "
    "По <b>собственным порогам моста</b> "
    "(<font name='LibMono'>evidence_level_for_ledger_entry</font>: V3 требует reviewer≥I2 "
    "И reference≥I2 И procedure=I4; V2 — оба ≥I1; иначе V1) эта запись квалифицируется "
    "только как V1: reviewer=I1 даёт r=1 (≥1), но reference=UNKNOWN даёт f=-1 (<1) → "
    "падает в V1. Разрыв в <b>два уровня</b>, не в один. Мост честно раскрывает это в "
    "поле <font name='LibMono'>reviewer.conflict_of_interest</font>: "
    "«Наблюдатель написан тем же автором, что и мост; независим от исполнителя по ключу, "
    "не независим от автора». Задокументировано как открытое решение #2 в "
    "<font name='LibMono'>docs/06_INTEGRATION.md</font>. Не дефект; закрывается этапом "
    "S4 дорожной карты (Ed25519 от отдельного ключа, который не контролирует автор "
    "моста). До S4 любая запись из моста, потребляемая A0, должна трактоваться как V1, "
    "не как V3 — это решение за потребителем A0, мост его не навязывает.", BODY))

story.append(Paragraph(
    "<b>O-B2: a0_run_allowed перезапускает только INTEGRITY_CHECK.</b> После допуска, "
    "перед каждым запуском A0, мост проверяет: (1) текущий хеш манифеста "
    "соответствует ADMITTED relation в мире; (2) INTEGRITY_CHECK проходит. VALIDATOR "
    "и 11 негативных тестов не перезапускаются. Это корректно: хеш манифеста — "
    "криптографическое обязательство на весь пакет (MAKE_MANIFEST детерминирован); "
    "INTEGRITY_CHECK сверяет файлы с манифестом; любое изменение файла → либо "
    "INTEGRITY_FAILED, либо (при пересборке манифеста) DIGEST_NOT_ADMITTED. "
    "Перезапуск VALIDATOR/негативных был бы избыточен.", BODY))

story.append(Paragraph(
    "<b>O-B3: package_digest — SHA-256 от байтов MANIFEST.json, не канонический "
    "хеш контента.</b> Звучит как уязвимость (пересериализация манифеста изменила бы "
    "хеш), но MAKE_MANIFEST.py пишет детерминированно: <font name='LibMono'>sort_keys=True, "
    "indent=2, trailing newline, os.replace</font>. Байт-стабильно для данного контента. "
    "Любая сторона, пересобирающая манифест, получает идентичные байты. Корректно.", BODY))

story.append(Paragraph(
    "<b>O-B4: мост использует sys.executable для запуска инструментов A0.</b> "
    "Это тот же Python, под которым работает HOST. Если версия Python у потребителя "
    "отличается от версии, на которой собирался A0, инструменты A0 могут вести себя "
    "по-другому. Не дефект (инструменты A0 pure-Python с явными зависимостями); "
    "замечание для эксплуатации.", BODY))

story.append(Paragraph(
    "<b>O-B5: hash.value в экспорте не проверяется схемой на соответствие "
    "каноническому хешу записи.</b> Поле <font name='LibMono'>hash.value</font> = "
    "SHA-256 от <font name='LibMono'>{stages, package}</font>, но "
    "EVIDENCE_LEDGER.schema.json требует только <font name='LibMono'>pattern "
    "'^[A-Fa-f0-9]+$'</font> — не сверяет с хешем записи. Подделанная запись с "
    "устаревшим hash.value пройдёт схему. Это ограничение схемы A0 (не моста); "
    "потребитель A0 должен перепроверять hash.value независимо.", BODY))

story.append(Paragraph(
    "<b>O-B6: inspect_package без таймаута.</b> Инструменты A0 запускаются "
    "синхронно через subprocess.run. Если они зависнут, мост зависнет. Для прототипа "
    "допустимо; R3 (распределённый стенд) потребует таймаутов.", BODY))

story.append(Paragraph(
    "<b>O-B7: evidence_level_for_ledger_entry корректно обрабатывает UNKNOWN.</b> "
    "<font name='LibMono'>_I.get('UNKNOWN', -1) = -1</font>, что ниже I0=0 → V1. "
    "Профиль с любым UNKNOWN полем квалифицируется как V1. Корректно: 'неизвестная "
    "независимость' ≠ 'I0 (нулевая независимость)'; UNKNOWN строго хуже I0.", BODY))

# === SECTION 7: Verdict ===
story.append(PageBreak())
story.append(Paragraph("7. Вердикт", H1))
story.append(Paragraph(
    "Мост <font name='LibMono'>a0_bridge.py</font> в составе SINGULYAR_A0_SYNTHESIS_v1 "
    "прошёл независимый аудит:", BODY))
story.append(Paragraph(
    "• <b>Статически:</b> все семь проверенных статей/гарантий (X1, X2, G3, G7, G2, "
    "M2, M4) реализованы в коде и соответствуют тексту CONSTITUTION.md редакции 2.<br/>"
    "• <b>Динамически — verify_all:</b> ВСЁ PASS (7 пунктов).<br/>"
    "• <b>Динамически — H-020:</b> 9/9 PASS.<br/>"
    "• <b>Динамически — собственные мутации аудитора BM-A…BM-L:</b> 12/12 PASS.",
    BODY))
story.append(Paragraph(
    "FAIL не обнаружено. Разрыв HOST-V3 ↔ A0-ledger-V1 (O-B1) честно раскрыт в коде "
    "и экспорте, задокументирован как открытое решение #2 в docs/06_INTEGRATION.md, "
    "и закрывается этапом S4 дорожной карты (Ed25519 от отдельного ключа).", BODY))
story.append(Paragraph(
    "<b>Вердикт: BRIDGE VALID.</b> Мост корректно реализует принуждение «A0 не "
    "запускать до V3 от независимого наблюдателя и совпадения хеша манифеста» "
    "(статья X1) и единую дисциплину статусов (статья X2).", BODY))
story.append(Paragraph(
    "<b>Замыкание S1 дорожной карты синтеза.</b> A0-аудит (PACKAGE VALID, см. "
    "A0_STANDARD_v0.2.5_AUDIT_REPORT.pdf) + мост-аудит (BRIDGE VALID, настоящий "
    "отчёт) = S1 закрыта. Допуск к A0 через мост работает корректно в пределах "
    "прототипа: HOST не запускает A0 без V3 и совпадения хеша; правка пакета гасит "
    "допуск; ложный хеш не проходит; профиль независимости не сворачивается в число. "
    "Оставшиеся этапы дорожной карты: S2 (пересчёт freeze_sha256 независимой "
    "реализацией — закрыта мной в A0-аудите как A9), S3 (допуск результатов A0 как "
    "переходы V3), S4 (Ed25519 для допуска и экспорта).", BODY))

# === Appendix A ===
story.append(PageBreak())
story.append(Paragraph("Приложение A. Перечень логов с хешами", H1))
log_files = [
    ("SYN_verify_all.log", "Прогон tools/verify_all.py на синтезе целиком (7 PASS)"),
    ("SYN_H020_detail.log", "Прогон H-020 напрямую: 9/9 PASS с детализацией случаев"),
    ("SYN_bridge_mutations.log", "Прогон 12 собственных мутаций аудитора BM-A…BM-L: 12/12 PASS"),
]
appx_header = [
    Paragraph("Файл лога", ParagraphStyle("ah1", fontName="LibSans-Bold", fontSize=9,
                                          leading=11, textColor=colors.white)),
    Paragraph("Описание", ParagraphStyle("ah2", fontName="LibSans-Bold", fontSize=9,
                                         leading=11, textColor=colors.white)),
    Paragraph("SHA-256 (префикс)", ParagraphStyle("ah3", fontName="LibSans-Bold",
                  fontSize=9, leading=11, textColor=colors.white, alignment=1)),
]
data = [appx_header]
for name, desc in log_files:
    data.append([Paragraph(name, CELL_MONO), Paragraph(desc, CELL),
                 Paragraph(log_hash(name), CELL_MONO)])
at = Table(data, colWidths=[7.2*cm, 6.8*cm, 3.0*cm], repeatRows=1)
at.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), C_BG_HEADER),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ("TOPPADDING", (0, 0), (-1, -1), 3),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ("GRID", (0, 0), (-1, -1), 0.25, C_RULE),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, C_BG_ROW_ALT]),
]))
story.append(at)

# === Appendix B ===
story.append(PageBreak())
story.append(Paragraph("Приложение B. Ключевые фрагменты вывода", H1))
story.append(Paragraph("B.1. verify_all.py — итог", H3))
story.append(Paragraph(
    '<font name="LibMono">[PASS] A0: INTEGRITY_CHECK (пакет A0 не изменён)</font><br/>'
    '<font name="LibMono">[PASS] A0: самотесты 7/7</font><br/>'
    '<font name="LibMono">[PASS] A0: VALIDATOR</font><br/>'
    '<font name="LibMono">[PASS] A0: негативные тесты 11/11</font><br/>'
    '<font name="LibMono">[PASS] HOST: selftest (демо + 14 экспериментов)</font><br/>'
    '<font name="LibMono">[PASS] HOST: pytest</font><br/>'
    '<font name="LibMono">[PASS] SYNTHESIS_MANIFEST (109 files)</font><br/>'
    '<font name="LibMono">ИТОГО: ВСЁ PASS</font>',
    BODY_TIGHT))
story.append(Paragraph("B.2. H-020 — детали 9 случаев", H3))
story.append(Paragraph(
    '<font name="LibMono">1 до допуска: запуск A0 запрещён [ok]</font><br/>'
    '<font name="LibMono">2 допуск: наблюдатель прогнал INTEGRITY/VALIDATOR/11 тестов; допуск закреплён за хешем манифеста [ok]</font><br/>'
    '<font name="LibMono">3 ложный хеш: заявленный хеш не совпал с фактическим [ok]</font><br/>'
    '<font name="LibMono">4 испорченный пакет: INTEGRITY_CHECK наблюдателя провален → нет V3 → нет ACTIVATE [ok]</font><br/>'
    '<font name="LibMono">5 правка после допуска: правка файла ломает целостность; пересборка манифеста меняет хеш — допуск не переносится [ok]</font><br/>'
    '<font name="LibMono">6 профиль → уровень: I3-проверяющий при I0-эталоне не даёт V3: оси не складываются [ok]</font><br/>'
    '<font name="LibMono">7 статусы: {CLM-ARCH-001: UNKNOWN, CLM-ARCH-002: UNKNOWN} [ok]</font><br/>'
    '<font name="LibMono">8 экспорт: запись HOST валидна по EVIDENCE_LEDGER.schema.json A0 [ok]</font><br/>'
    '<font name="LibMono">9 трасса: хеш-цепочка допуска цела [ok]</font>',
    BODY_TIGHT))
story.append(Paragraph("B.3. BM-J — разрыв HOST-V3 vs A0-ledger-V1 (деталь)", H3))
story.append(Paragraph(
    '<font name="LibMono">[PASS] BM-J HOST-V3 vs A0-ledger-V1 gap honestly disclosed</font><br/>'
    '<font name="LibMono">  HOST_V3=True  ledger_level=1  reviewer_I=\'I1\'  reference_I=\'UNKNOWN\'  proc=\'PARTIAL\'</font><br/>'
    '<font name="LibMono">  → HOST даёт V3 (по независимости ключа), но та же запись</font><br/>'
    '<font name="LibMono">    по собственным порогам моста квалифицируется как V1.</font><br/>'
    '<font name="LibMono">  conflict_of_interest = "Наблюдатель написан тем же автором,</font><br/>'
    '<font name="LibMono">    что и мост; независим от исполнителя по ключу, не независим от автора."</font>',
    BODY_TIGHT))

# === Appendix C ===
story.append(PageBreak())
story.append(Paragraph("Приложение C. Скрипт аудитора", H1))
story.append(Paragraph(
    "Аудитор разработал драйвер 12 собственных мутаций моста "
    "<font name='LibMono'>auditor_bridge_mutations.py</font>, не использующий "
    "инструменты пакета кроме как через публичный API моста. Скрипт сохранён в "
    "<font name='LibMono'>/home/z/my-project/scripts/audit_a0/</font> и может быть "
    "предоставлен для ревизии.", BODY))
scripts = [
    ("auditor_bridge_mutations.py",
     "Драйвер 12 мутаций BM-A…BM-L: самоаттестация (G3/H-008), путь отказа ATTEST → "
     "экспорт UNKNOWN, схема-валидность на пути отказа, структура gate_suite, "
     "границы порогов V-уровней, passport_verdicts edge cases, разрыв HOST-V3 vs "
     "A0-ledger-V1 с проверкой раскрытия, missing manifest, no __pycache__."),
]
data = [[
    Paragraph("Скрипт", ParagraphStyle("cth1", fontName="LibSans-Bold", fontSize=9,
                                       leading=11, textColor=colors.white)),
    Paragraph("Назначение", ParagraphStyle("cth2", fontName="LibSans-Bold", fontSize=9,
                                           leading=11, textColor=colors.white)),
]]
for name, desc in scripts:
    data.append([Paragraph(name, ParagraphStyle("cn", fontName="LibMono-Bold",
                                                fontSize=8.5, leading=11, textColor=C_TEXT)),
                 Paragraph(desc, CELL)])
ctbl = Table(data, colWidths=[5.0*cm, 12.0*cm], repeatRows=1)
ctbl.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), C_BG_HEADER),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ("TOPPADDING", (0, 0), (-1, -1), 3),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ("GRID", (0, 0), (-1, -1), 0.25, C_RULE),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, C_BG_ROW_ALT]),
]))
story.append(ctbl)
story.append(Spacer(1, 0.4*cm))
story.append(hr())
story.append(Paragraph("Итог одной строкой", H3))
story.append(Paragraph(
    "BRIDGE VALID. a0_bridge.py faithfully реализует X1/X2/G3/G7/G2; verify_all ВСЁ "
    "PASS; H-020 9/9 PASS; BM-A…BM-L 12/12 PASS; разрыв HOST-V3 vs A0-ledger-V1 "
    "честно раскрыт и закрывается S4 (Ed25519). S1 дорожной карты закрыта.", BODY))

# --- build ---
doc = BridgeDoc(OUT_PDF)
story.insert(0, NextPageTemplate("body"))
doc.multiBuild(story)
import os
print(f"OK: {OUT_PDF}")
print(f"size: {os.path.getsize(OUT_PDF)} bytes")
