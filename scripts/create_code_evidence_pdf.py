"""Build the team report from real execution evidence and repository source."""
import hashlib
import json
import math
import textwrap
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image as PILImage, ImageDraw, ImageFont
from pypdf import PdfReader
from pdf2image import convert_from_path
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Table, TableStyle,
                               Spacer, PageBreak, Image, Preformatted)

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "artifacts/healing-report"
OUT = ROOT / "output/pdf/Self_Correcting_Data_Pipeline_Code_and_Healing_Evidence.pdf"
QA = EVIDENCE / "pdf-pages"
QA.mkdir(parents=True, exist_ok=True)
OUT.parent.mkdir(parents=True, exist_ok=True)
safe = json.loads((EVIDENCE / "safe.json").read_text(encoding="utf-8"))
unsafe = json.loads((EVIDENCE / "unsafe.json").read_text(encoding="utf-8"))
tests = json.loads((EVIDENCE / "tests.json").read_text(encoding="utf-8"))
assert safe["automatic_passes"] == unsafe["automatic_passes"] == 1
assert safe["validation_calls"] == unsafe["validation_calls"] == 2
assert not safe["final_issues"] and len(unsafe["final_issues"]) == 5
assert sum(a["applied"] for a in safe["attempts"]) == 7
assert tests["exit_code"] == 0

for name, filename in [("Calibri", "calibri.ttf"), ("CalibriBold", "calibrib.ttf"),
                       ("Consolas", "consola.ttf")]:
    pdfmetrics.registerFont(TTFont(name, "C:/Windows/Fonts/" + filename))
pdfmetrics.registerFontFamily("Calibri", normal="Calibri", bold="CalibriBold", italic="Calibri", boldItalic="CalibriBold")
WIDTH = A4[0] - 104
body = ParagraphStyle("Body", fontName="Calibri", fontSize=11, leading=14, spaceAfter=9)
title = ParagraphStyle("Title", parent=body, fontName="CalibriBold", fontSize=26, leading=29, spaceAfter=14)
h1 = ParagraphStyle("Heading", parent=body, fontName="CalibriBold", fontSize=19, leading=23, spaceAfter=11, keepWithNext=True)
h2 = ParagraphStyle("Subheading", parent=body, fontName="CalibriBold", fontSize=12.5, leading=16, spaceBefore=9, spaceAfter=7, keepWithNext=True)
small = ParagraphStyle("Small", parent=body, fontSize=9, leading=11, spaceAfter=8)
cell = ParagraphStyle("Cell", parent=body, fontSize=9.3, leading=12, spaceAfter=0)
cell_head = ParagraphStyle("CellHead", parent=cell, fontName="CalibriBold", textColor=colors.white)
mono = ParagraphStyle("Code", fontName="Consolas", fontSize=8.2, leading=10, spaceAfter=0)
commands = ParagraphStyle("Commands", parent=mono, fontSize=9, leading=12, spaceAfter=10)
story = []


def p(value, style=body):
    story.append(Paragraph(value, style))


def heading(value):
    p(value, h2)


def page(value):
    story.append(PageBreak())
    p(value, h1)


def table(headers, rows, fractions):
    data = [[Paragraph(escape(str(value)), cell_head if i == 0 else cell) for value in row]
            for i, row in enumerate([headers] + list(rows))]
    result = Table(data, colWidths=[WIDTH * x for x in fractions], repeatRows=1, hAlign="LEFT")
    result.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#24445B")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#F1F5F7"), colors.white]),
        ("GRID", (0, 0), (-1, -1), .4, colors.HexColor("#D9D9D9")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.extend([result, Spacer(1, 11)])


def screenshot(filename, max_height=535):
    path = EVIDENCE / filename
    with PILImage.open(path) as im:
        w, h = im.size
    scale = min(WIDTH / w, max_height / h)
    story.extend([Image(str(path), width=w * scale, height=h * scale, hAlign="LEFT"), Spacer(1, 9)])


def code(value):
    story.append(Preformatted(value, commands))


# Keep the teammate block at the very start, with identifiers exactly as supplied.
p("LY AIDS B2 Batch", h1)
heading("Teammates")
table(["Name", "Roll number"], [
    ("Soham Redkar", "160142233081"),
    ("Soumya Patil", "16014223081"),
    ("Tanish Shetty", "16014223088"),
], [.55, .45])
p("Names and roll numbers are reproduced exactly as supplied.", small)
story.append(Spacer(1, 12))
p("Self Correcting Data Pipeline", title)
p("Source code and self healing execution evidence", h1)
p("The project detects quality errors in sales CSV data, applies explicit deterministic repairs, revalidates the result, and sends unresolved records to quarantine. This report contains live execution screenshots and a complete appendix of the application source, configuration, deployment files, tests, and demonstration scripts.")
heading("Observed correction count")
p("<b>The safe example heals in one automatic correction pass.</b> That pass applies seven field changes and performs two validation calls. The unsafe example also stops after one pass; it remains invalid rather than repeatedly guessing values.")
table(["Observed result", "Safe example", "Unsafe example"], [
    ("Automatic correction passes", "1", "1"),
    ("Validation calls", "2", "2"),
    ("Applied field changes", "7", "1"),
    ("Unresolved issue entries", "0", "5 across 3 fields"),
    ("Quality decision", "Ready for duplicate checks", "Quarantine required"),
], [.44, .28, .28])
p("Evidence captured on 29 October 2026 using the real pipeline/quality.py engine, us_sales profile, and ruleset 1.0.0. PostgreSQL was unavailable during this capture, so the diagnostic screenshots do not claim that these demonstration rows were persisted.", small)

page("What one iteration means")
p("Self healing here means repairing input data; the program does not rewrite its Python source. An iteration means one ordered traversal of the correction rules inside correct(). It does not mean one field edit, one validation call, a database retry, or a manual review submission.")
table(["Stage", "Action", "Pass count"], [
    ("Before execution", "Show original values; no correction has run", "0"),
    ("Initial validation", "Pandera checks the current record", "Still part of the same call"),
    ("Automatic correction", "Visit configured rules once, then apply the total policy", "1"),
    ("Revalidation", "Validate the corrected record and retain failed parsing reasons", "Remains 1"),
    ("Downstream processing", "Accept, quarantine, or exclude duplicates in the service", "No additional correction loop"),
], [.25, .53, .22])
heading("Why seven changes are still one pass")
p("The safe example triggers trim, country_alias, currency_alias, date_format, quantity_format, money_format, and authoritative_total. These are sequential rule applications within one pass. The code has no loop that restarts the rules until success. Unsafe values therefore remain unresolved after the bounded pass.")
table(["Field", "Original input", "After pass 1"], [
    ("customer_id", repr(safe["raw"]["customer_id"]), repr(safe["corrected"]["customer_id"])),
    *[(f, safe["raw"][f], safe["corrected"][f]) for f in
      ("transaction_date", "quantity", "unit_price", "currency", "country", "total_amount")],
], [.29, .33, .38])
p("The quoted customer ID above makes the removed surrounding spaces visible. total_amount changes from 20.00 to 20.50 because us_sales explicitly declares quantity and unit price authoritative, and both fields are valid after parsing. Amounts use Decimal with ROUND_HALF_UP at two decimal places.")
heading("How the count was observed")
p("The diagnostic view invokes correct() exactly once per example. A wrapper counts calls to the original validate() function while delegating to its real implementation. It does not substitute validation outcomes. The observed count is two calls: initial validation and revalidation. The screenshots and JSON results are generated by that execution.")

page("Screenshot 1 Before correction")
p("The safe demonstration record is still in its original form. The automatic pass counter is zero, and no corrected result is shown. Clicking Run one correction pass executes the real engine.")
screenshot("01-before.png")
p("Figure 1. Actual browser capture of the local diagnostic Streamlit view before running the correction function. The original customer ID contains surrounding spaces, which the grid does not visually emphasize.", small)
p("Source view: scripts/healing_evidence_app.py. Engine: pipeline/quality.py. This diagnostic view was added to capture reproducible evidence; it does not replace the main application's upload, persistence, or duplicate checks.")

page("Screenshot 2 Safe values after one pass")
p("The same record passes all data checks after one ordered correction pass. The counters show one pass, two validation calls, seven applied field changes, and zero remaining issues.")
screenshot("02-safe-pass-one.png")
p("Figure 2. Actual execution after pass 1. The date, quantity, price, currency, country, total, and customer ID now have their configured canonical forms.", small)
p("Ready for downstream duplicate checks means that the data is valid. It does not assert database acceptance: the full service must still check transaction IDs and duplicate content before storing a sale.")

page("Screenshot 3 The applied rule audit")
p("The engine returns a structured attempt for every changed field. All seven applied changes in this safe example have a true whole-record revalidation result.")
screenshot("02b-safe-audit.png", max_height=230)
p("Figure 3. Browser capture of the actual audit grid returned by the safe execution. No success states or values were drawn into this image.", small)
heading("What the audit explains")
table(["Audit attribute", "Meaning"], [
    ("Rule and field", "Which explicit rule acted on which field"),
    ("Before and proposed value", "What the engine received and proposed to replace"),
    ("Applied", "Whether the proposed correction was applied"),
    ("Revalidation OK", "Whether the whole record passed validation after the correction pass"),
], [.31, .69])
p("The returned attempts also contain the rule version and reason. In the full database service, correction_attempts records these details with the batch, raw record, optional review ID, and timestamp. Failed correction attempts are retained too.")
heading("The bounded pass in the source")
source = (ROOT / "pipeline/quality.py").read_text(encoding="utf-8")
start = source.index("    # Each rule visits each field once.")
end = source.index("    if (profile.authoritative_totals", start)
snippet = source[start:end].rstrip()
story.append(Preformatted(snippet, mono))
p("This is an exact excerpt from pipeline/quality.py. The conditional total policy and revalidation follow it. The complete function appears in the source appendix.", small)

page("Screenshot 4 Unsafe values after one pass")
p("The unsafe case also executes one automatic correction pass. The country alias changes safely, but the date, currency-symbol conflict, and email remain unresolved. The row requires quarantine.")
screenshot("03-unsafe-pass-one.png")
p("Figure 4. Actual result for DEMO-UNSAFE. One applied country correction is not counted as successful healing of the whole record. The counters show one pass and five unresolved issue entries.", small)
p("There is no automatic pass 2. A verified manual edit would be a separate review submission, validated through the same rules; it is not an automatic iteration of this run.")

page("Screenshot 5 Why quarantine is required")
screenshot("03b-unsafe-reasons.png", max_height=190)
p("Figure 5. Actual unresolved validation reasons from the unsafe execution. Five issue entries refer to three distinct fields because the date and price each receive both a schema-validation reason and a failed-correction reason.", small)
table(["Field", "Unresolved value", "Why the code refuses to guess"], [
    ("transaction_date", "01/02/03", "It does not match the declared date formats."),
    ("unit_price", "€10.25 with USD", "The recognized symbol conflicts with the declared currency."),
    ("email", "bad@@mail", "The address fails syntax validation; it is not rewritten."),
], [.22, .29, .49])
heading("A correction is not an acceptance decision")
p("The country_alias attempt is applied, but its revalidation_ok value is false because the full record remains invalid. The failed date_format and money_format attempts are not applied. The engine preserves those values and appends actionable reasons rather than repeatedly attempting new interpretations.")
heading("What the main service would do next")
p("Pipeline.process() in pipeline/service.py takes the validation result. If issues remain, it creates a quarantine snapshot instead of an accepted sale. Otherwise, it performs duplicate checks. Conflicting transaction IDs are quarantined, identical accepted content is excluded as a duplicate, and only an eligible new sale is written to PostgreSQL.")
p("A completed batch can therefore contain accepted rows, corrected accepted rows, quarantined rows, and excluded duplicates. These final outcomes are mutually exclusive. A row is not accepted simply because one field was repaired.")

page("Screenshot 6 Fresh tests and reproduction")
screenshot("04-tests.png", max_height=350)
p("Figure 6. Browser capture displaying the actual pytest subprocess result and exit code. The output is read from artifacts/healing-report/tests.json.", small)
p("<b>Current verification:</b> 32 tests passed, 12 PostgreSQL-dependent tests were deselected, and the test process exited with code 0. PostgreSQL persistence and duplicate integration behavior were not re-run for this report because the local database was unreachable.")
heading("Reproduce these screenshots")
code("python scripts/run_healing_report_tests.py\nstreamlit run scripts/healing_evidence_app.py --server.port 8502")
p("Open http://127.0.0.1:8502, choose Safe corrections, and run one pass. Inspect its audit. Choose Unsafe values and run one pass again for that separate case. The capture script in the appendix automates the browser actions using the available local Playwright runtime.")
heading("Start the full application when Docker is available")
code("docker compose up --build -d\ndocker compose exec app python -m pytest -q")
p("Then use http://localhost:8501 for the main six-view interface. The source appendix contains the persistence, duplicate, and manual-review implementations even though this report's live screenshots cover the isolated quality engine.", small)

# Source listings include all application modules, tests, deployment and evidence code.
FILES = [
    "pipeline/__init__.py", "pipeline/config.py", "pipeline/profiles.json",
    "pipeline/input.py", "pipeline/quality.py", "pipeline/service.py", "pipeline/db.py",
    "pipeline/export.py", "pipeline/cli.py", "streamlit_app.py",
    "pyproject.toml", "Dockerfile", "compose.yaml", ".env.example",
    "scripts/generate_samples.py", "tests/conftest.py", "tests/test_quality.py",
    "tests/test_input_export.py", "tests/test_persistence.py", "tests/test_ui.py",
    "scripts/healing_evidence_app.py", "scripts/run_healing_report_tests.py",
    "scripts/capture_healing_evidence.cjs",
]
manifest = []
code_chunks = []


def displayed_source_lines(content):
    output = []
    for number, line in enumerate(content.splitlines(), 1):
        # Display non-BMP symbols as explicit Unicode escapes for embedded mono fonts.
        line = "".join(c if ord(c) <= 0xFFFF else f"\\U{ord(c):08x}" for c in line).expandtabs(4)
        parts = textwrap.wrap(line, width=94, expand_tabs=False, replace_whitespace=False,
                              drop_whitespace=False, break_long_words=True, break_on_hyphens=False) or [""]
        output.append(f"{number:4d}  {parts[0]}")
        output.extend("   |  " + part for part in parts[1:])
    return output


next_page = 10  # Eight evidence pages plus the source index.
for name in FILES:
    data = (ROOT / name).read_bytes()
    content = data.decode("utf-8")
    lines = displayed_source_lines(content)
    # Balance continuation pages so a long listing does not end with a lone line.
    page_count = max(1, math.ceil(len(lines) / 66))
    chunk_size = max(1, math.ceil(len(lines) / page_count))
    chunks = [lines[i:i + chunk_size] for i in range(0, len(lines), chunk_size)] or [["    (empty file)"]]
    item = {"file": name, "lines": len(content.splitlines()), "sha256": hashlib.sha256(data).hexdigest(),
            "first_page": next_page, "pages": len(chunks)}
    manifest.append(item)
    for index, chunk in enumerate(chunks, 1):
        code_chunks.append((item, index, chunk))
    next_page += len(chunks)

page("Source code appendix index")
p("The following listings reproduce the complete application source, configuration, deployment files, tests, sample generator, and evidence scripts used by this report. Generated datasets, virtual-environment packages, private .env values, and PDF authoring utilities are excluded.", small)
table(["File", "Lines", "PDF page"], [(x["file"], x["lines"], x["first_page"]) for x in manifest], [.75, .11, .14])
p("Source line numbers are shown at the left. A vertical bar marks a display continuation of the preceding source line. Non-BMP symbols such as the magnifying-glass page icon are displayed as Python-style Unicode escapes so the monospaced font remains readable. Hashes refer to original file bytes.", small)

for item, part, chunk in code_chunks:
    page(item["file"])
    p(f"Complete source listing - part {part} of {item['pages']}", small)
    p("SHA-256  " + item["sha256"], ParagraphStyle("Hash", parent=small, fontName="Consolas", fontSize=7.2, leading=9))
    story.append(Preformatted("\n".join(chunk), mono))


def furniture(canvas, document):
    canvas.saveState()
    canvas.setFillColor(colors.black)
    canvas.setFont("Calibri", 8)
    canvas.drawString(52, A4[1] - 27, "SELF CORRECTING DATA PIPELINE  |  CODE AND EXECUTION EVIDENCE")
    canvas.drawString(52, 25, "LY AIDS B2 Batch  |  29 October 2026")
    canvas.drawRightString(A4[0] - 52, 25, str(document.page))
    canvas.restoreState()


SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=52, rightMargin=52,
                  topMargin=51, bottomMargin=48, title="Self Correcting Data Pipeline Code and Healing Evidence",
                  author="Soham Redkar, Soumya Patil, Tanish Shetty").build(story, onFirstPage=furniture, onLaterPages=furniture)
reader = PdfReader(OUT)
assert len(reader.pages) == next_page - 1, (len(reader.pages), next_page - 1)
first = reader.pages[0].extract_text()
for value in ["LY AIDS B2 Batch", "Soham Redkar", "160142233081", "Soumya Patil", "16014223081", "Tanish Shetty", "16014223088"]:
    assert value in first, value
for item in manifest:
    assert item["file"] in reader.pages[item["first_page"] - 1].extract_text(), item["file"]
metadata = {"pdf": str(OUT), "pages": len(reader.pages), "source_files": manifest,
            "screenshots": {name: hashlib.sha256((EVIDENCE/name).read_bytes()).hexdigest() for name in
              ["01-before.png", "02-safe-pass-one.png", "02b-safe-audit.png", "03-unsafe-pass-one.png", "03b-unsafe-reasons.png", "04-tests.png"]}}
(EVIDENCE / "report-manifest.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

images = convert_from_path(str(OUT), dpi=100,
    poppler_path=r"C:\Users\tanis\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin")
for i, im in enumerate(images, 1):
    im.save(QA / f"page-{i:02}.png")
font = ImageFont.truetype("C:/Windows/Fonts/calibri.ttf", 22)
for start in range(0, len(images), 6):
    sheet = PILImage.new("RGB", (1200, 2640), "#D9D9D9")
    draw = ImageDraw.Draw(sheet)
    for offset, im in enumerate(images[start:start + 6]):
        thumb = im.copy()
        thumb.thumbnail((584, 824))
        x, y = (offset % 2) * 600 + 8, (offset // 2) * 880 + 34
        sheet.paste(thumb, (x, y))
        draw.text((x + 5, y - 29), f"PDF page {start + offset + 1}", fill="black", font=font)
    sheet.save(QA / f"contact-{start//6 + 1}.png")
print(f"Created {OUT}\nPages: {len(reader.pages)}\nSource files: {len(manifest)}\nScreenshots: 6")
