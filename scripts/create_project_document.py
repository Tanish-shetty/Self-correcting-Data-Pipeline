"""Build the project explanation using the managed document runtime."""
from pathlib import Path

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs"
QA = ROOT / "artifacts" / "project-document"
OUT.mkdir(exist_ok=True)
QA.mkdir(parents=True, exist_ok=True)

doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Inches(8.27), Inches(11.69)
sec.top_margin = sec.bottom_margin = Inches(.72)
sec.left_margin = sec.right_margin = Inches(.75)
sec.header_distance = sec.footer_distance = Inches(.3)

for name in ("Normal", "Title", "Subtitle", "Heading 1", "Heading 2", "Caption"):
    s = doc.styles[name]
    s.font.name = "Calibri"
    s.font.color.rgb = RGBColor(0, 0, 0)
    s.paragraph_format.widow_control = True
normal = doc.styles["Normal"]
normal.font.size = Pt(11)
normal.paragraph_format.line_spacing = 1.10
normal.paragraph_format.space_after = Pt(7)
for name, size in (("Title", 27), ("Heading 1", 20), ("Heading 2", 12.5)):
    doc.styles[name].font.size = Pt(size)
    doc.styles[name].paragraph_format.space_before = Pt(10)
    doc.styles[name].paragraph_format.space_after = Pt(8)
    doc.styles[name].paragraph_format.keep_with_next = True
doc.styles["Title"].paragraph_format.space_before = Pt(0)
doc.styles["Subtitle"].font.size = Pt(12)
doc.styles["Caption"].font.size = Pt(9)
doc.styles["Caption"].font.italic = False
header = sec.header.paragraphs[0]
header.text = "SELF CORRECTING DATA PIPELINE   |   PROJECT EXPLANATION"
header.style = doc.styles["Normal"]
header.runs[0].font.size = Pt(8)
header.paragraph_format.space_after = Pt(0)
footer = sec.footer.paragraphs[0]
footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
run = footer.add_run("Project version 1.0.0  •  ")
run.font.size = Pt(8)
field = OxmlElement("w:fldSimple")
field.set(qn("w:instr"), "PAGE")
footer._p.append(field)


def p(text, bold_lead=None):
    para = doc.add_paragraph()
    if bold_lead:
        para.add_run(bold_lead).bold = True
        para.add_run(text)
    else:
        para.add_run(text)
    return para


def h(text, level=2):
    return doc.add_heading(text, level)


def page(title):
    doc.add_page_break()
    h(title, 1)


def table(headers, rows, widths):
    t = doc.add_table(rows=1, cols=len(headers))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    borders = OxmlElement("w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        item = OxmlElement("w:" + side)
        for key, val in (("val", "single"), ("sz", "5"), ("color", "D9D9D9")):
            item.set(qn("w:" + key), val)
        borders.append(item)
    t._tbl.tblPr.append(borders)
    for col, width in zip(t.columns, widths):
        col.width = Inches(width)
    repeat = OxmlElement("w:tblHeader")
    t.rows[0]._tr.get_or_add_trPr().append(repeat)
    for idx, values in enumerate([headers] + rows):
        cells = t.rows[0].cells if idx == 0 else t.add_row().cells
        row_pr = cells[0]._tc.getparent().get_or_add_trPr()
        no_split = OxmlElement("w:cantSplit")
        row_pr.append(no_split)
        for j, (cell, value) in enumerate(zip(cells, values)):
            cell.width = Inches(widths[j])
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            props = cell._tc.get_or_add_tcPr()
            margin = OxmlElement("w:tcMar")
            for edge, amount in (("top", "80"), ("left", "100"), ("bottom", "80"), ("right", "100")):
                node = OxmlElement("w:" + edge)
                node.set(qn("w:w"), amount)
                node.set(qn("w:type"), "dxa")
                margin.append(node)
            props.append(margin)
            shade = OxmlElement("w:shd")
            shade.set(qn("w:fill"), "24445B" if idx == 0 else ("F1F5F7" if idx % 2 else "FFFFFF"))
            props.append(shade)
            para = cell.paragraphs[0]
            para.paragraph_format.space_after = Pt(0)
            para.paragraph_format.line_spacing = 1.05
            run = para.add_run(str(value))
            run.font.size = Pt(9.5)
            if idx == 0:
                run.bold = True
                run.font.color.rgb = RGBColor(255, 255, 255)
    doc.add_paragraph().paragraph_format.space_after = Pt(0)
    return t


def code(lines):
    para = doc.add_paragraph()
    para.paragraph_format.space_after = Pt(9)
    para.paragraph_format.line_spacing = 1.12
    for i, line in enumerate(lines.split("\n")):
        run = para.add_run(("\n" if i else "") + line)
        run.font.name = "Consolas"
        run.font.size = Pt(9)


# A code-drawn architecture figure keeps labels sharp in Word.
im = Image.new("RGB", (1680, 490), "white")
d = ImageDraw.Draw(im)
font = ImageFont.truetype("C:/Windows/Fonts/calibri.ttf", 31)
small = ImageFont.truetype("C:/Windows/Fonts/calibri.ttf", 26)
boxes = [(10, 80, 345, 245), (450, 80, 1010, 245), (1115, 80, 1670, 245)]
labels = [("CSV input", "Streamlit or CLI"), ("Shared Python service", "Validate → correct → revalidate"), ("PostgreSQL", "Sales • quarantine • audit")]
for rect, (main, sub) in zip(boxes, labels):
    d.rounded_rectangle(rect, radius=14, fill="#F1F5F7", outline="#24445B", width=3)
    mid = (rect[0] + rect[2]) / 2
    d.text((mid, 130), main, font=font, fill="black", anchor="mm")
    d.text((mid, 190), sub, font=small, fill="black", anchor="mm")
for x1, x2 in ((345, 450), (1010, 1115)):
    d.line((x1 + 8, 163, x2 - 12, 163), fill="#24445B", width=5)
    d.polygon([(x2-12, 163), (x2-31, 151), (x2-31, 175)], fill="#24445B")
d.line([(1390, 255), (1390, 358), (730, 358), (730, 255)], fill="#24445B", width=4)
d.polygon([(730,255),(718,274),(742,274)],fill="#24445B")
d.text((1065, 410), "Explicit review edits return through validation", font=small, fill="black", anchor="mm")
figure = QA / "architecture.png"
im.save(figure)

doc.add_heading("Self Correcting Data Pipeline", 0)
doc.add_paragraph("Project explanation and demonstration guide", "Subtitle")
p("This project turns sales CSV files into validated database records. It repairs only issues that can be resolved by explicit rules, explains every attempted correction, and keeps unsafe records in quarantine for human review. The original input remains available throughout the process.")
p("This document explains the implemented version 1.0.0 for readers reviewing, demonstrating, or extending the project. It covers the design, rules, persistence, interface, and verified demo behavior. Prepared on 29 October 2026.")
h("The problem the project solves")
p("Sales files often contain extra whitespace, inconsistent country names, different date formats, numeric formatting differences, missing values, and duplicate transaction IDs. Loading these directly into a database can distort reporting or overwrite trustworthy data. The pipeline makes the acceptance decision visible and repeatable.")
h("How the application is organized")
pic = doc.add_paragraph()
pic.add_run().add_picture(str(figure), width=Inches(6.7))
doc.add_paragraph("Figure 1  Both entry points use the same validation and persistence service", "Caption")
p("Python 3.11 or later provides the service layer. Pandera checks dataframes against the sales contract. SQLAlchemy and psycopg write to PostgreSQL. Streamlit provides the interface, pytest verifies behavior, and Docker Compose starts the local application and database.")
h("What self correction means here")
p("The correction engine is deterministic: the same file, source profile, and rule configuration lead to the same processing decisions. Source profiles declare the expected formats. The MVP uses no AI model, statistical outlier replacement, or automatic inference of missing business values.")

page("Sales data and source profiles")
p("Each CSV row represents one sales transaction. A transaction ID is the business key used to distinguish a new sale from a repeated or conflicting submission.")
table(["Field", "Validation requirement"], [
    ("transaction_id", "Required text and unique accepted business key"),
    ("customer_id", "Required text"),
    ("transaction_date", "Required real calendar date"),
    ("product", "Required free text rather than a predefined catalog"),
    ("quantity", "Positive integer within the 32 bit range"),
    ("unit_price", "Nonnegative decimal with at most two fractional digits"),
    ("currency", "USD, EUR, GBP, or INR"),
    ("country", "United States, United Kingdom, Germany, France, or India"),
    ("email", "Optional; syntax checked when supplied"),
    ("total_amount", "Nonnegative decimal equal to quantity multiplied by unit price"),
], [1.55,5.15])
p("Required identifiers and product text are limited to 200 characters. Email checks require one @ sign, no whitespace, and a dotted domain; they do not establish that an address exists. Money is stored as Decimal in Python and NUMERIC(18,2) in PostgreSQL.")
h("Why the source profile matters")
table(["Profile", "Declared dates", "Numeric example", "Total repair"], [
    ("us_sales", "YYYY-MM-DD or MM/DD/YYYY", "1,234.50", "Enabled"),
    ("eu_sales", "YYYY-MM-DD or DD/MM/YYYY", "1.234,50", "Disabled"),
    ("iso_strict", "YYYY-MM-DD", "1234.50", "Disabled"),
], [1.05,2.35,1.6,1.7])
p("For example, 01/02/2026 means January 2 in us_sales and February 1 in eu_sales. The selected profile supplies that interpretation; the application does not guess it. A value such as 01/02/03 is rejected by the configured formats. If multiple declared formats produce different dates, the date is quarantined.")
h("File and column policies")
p("Files must be comma separated UTF-8 CSV, with an optional byte order mark, and stay within 5 MiB and 10,000 rows. Cells are limited to 10,000 characters. Explicit aliases include cust_id to customer_id and txn_id to transaction_id in the US and European profiles. Missing required columns or conflicting mappings fail the batch. Unknown columns remain in raw input and are excluded from accepted sales fields.")

page("Validation and correction flow")
p("Processing separates format repair from the decision to accept a business record. Successfully changing one field does not guarantee that the whole row is safe.")
for lead, text in [
    ("1  Preserve input. ", "Store the exact file bytes and batch identity, then retain parsed raw rows and their physical source line numbers."),
    ("2  Map and validate. ", "Apply declared header aliases and run initial Pandera validation against the canonical sales fields."),
    ("3  Apply eligible rules. ", "Visit rules in a fixed order once. Each rule has an ID, version, fields, an applicability condition, and a structured result."),
    ("4  Revalidate the result. ", "Run Pandera again, check the total equation, and retain any failed correction attempt as a reason for quarantine."),
    ("5  Resolve duplicates and persist. ", "Check normalized content and transaction keys, then atomically store sales, quarantine snapshots, audit events, and duplicate decisions."),
]:
    p(text, lead)
h("A safe correction example")
p("Assume the remaining fields are valid and the source is us_sales. Its policy explicitly declares quantity and unit price authoritative for repairing an existing valid total.")
table(["Field", "Original", "Result", "Reason"], [
    ("country", "USA", "United States", "Configured country alias"),
    ("quantity", "2.0", "2", "Exact whole number"),
    ("unit_price", "$10.25", "10.25", "Symbol matches USD"),
    ("total_amount", "20.00", "20.50", "2 multiplied by 10.25"),
], [1.25,1.15,1.4,2.9])
p("The result is accepted after correction only if all other validations and duplicate checks pass. Each changed field receives an audit entry. Header mappings also create per-row column_mapping events, distinguished by a column: prefix in the audit field name.")
h("When the pipeline refuses a repair")
p("A row containing transaction_date=01/02/03 and unit_price=€10.25 with currency=USD is quarantined. The date is unsupported and the symbol conflicts with the currency. The system does not rewrite the currency or invent a date. Missing business values, fractional quantities, unknown countries, malformed email addresses, and invalid numeric separators also remain actionable issues.")
p("Amounts use ROUND_HALF_UP to two decimal places. Supplied amounts with extra fractional digits are rejected rather than silently rounded. A missing or unparseable total is not invented, even under an authoritative source policy. One ordered correction pass prevents loops and values toggling between rules.")

page("Duplicate handling and row outcomes")
h("File identity and safe replay")
p("Idempotency means that repeating an equivalent submission does not create another set of sales or audit events. The application combines a SHA-256 hash of exact file bytes with the source profile and a rule and configuration fingerprint to create the submission identity. A database uniqueness constraint protects this identity even when submissions arrive concurrently.")
p("Changing only the filename reuses the existing batch. Changed file bytes, a different profile, or changed configuration produce a new batch. A completed batch is returned without reprocessing its rows. Database sales constraints still protect against overlapping transactions in different files.")
h("Record duplicate decisions")
table(["Situation", "Implemented decision"], [
    ("Identical valid rows in one batch", "Keep the first source row and exclude the repeated rows with lineage to their representative."),
    ("Same key with different normalized content", "Quarantine every conflicting version in the batch, including invalid siblings."),
    ("Incoming content equals an accepted sale", "Exclude the incoming duplicate and link to the original accepted record."),
    ("Incoming content conflicts with an accepted sale", "Preserve the accepted sale and quarantine the incoming conflict."),
    ("Identical invalid rows", "Retain each row in quarantine so its validation issues remain visible."),
], [2.05,4.65])
p("Equality uses normalized fields, including email. Money is compared in a canonical two-decimal representation and quantities as canonical integers. Unknown columns remain in raw provenance but do not change sales content equality.")
h("Counts that reconcile")
table(["Final outcome", "Meaning"], [
    ("accepted_valid", "Accepted with no applied correction"),
    ("accepted_corrected", "Accepted after an automated correction or successful manual review"),
    ("quarantined", "Retained for unresolved quality or business key issues"),
    ("excluded_duplicate", "Excluded as a repeat of equivalent normalized content"),
], [1.75,4.95])
p("For a completed batch, these four mutually exclusive counts sum to input rows. Rates use all input rows as their denominator. Validity is stored separately from duplicate disposition: a corrected row may still be excluded as a duplicate. A quarantined row never counts as accepted merely because a field was repaired. Reviews update the current row outcome while preserving history.")

page("Persistence and audit design")
p("PostgreSQL stores both the accepted business data and the evidence needed to explain each source row. SQLAlchemy models define relationships and constraints; a version table and transactional migration runner initialize schema version 1.")
table(["Table", "Purpose"], [
    ("batches", "Exact input bytes, file hash, profile, configuration fingerprint, state, timing, and error information"),
    ("raw_records", "Original and mapped values, source line, current values, initial issues, validity, and final outcome"),
    ("sales", "Accepted typed transactions with a unique transaction ID and NUMERIC money"),
    ("quarantine", "Snapshots of unresolved values and actionable issues, including resolution timestamps"),
    ("correction_attempts", "Before and proposed values, rule ID and version, reason, applied flag, time, and revalidation result"),
    ("duplicate_decisions", "Exact or conflicting duplicate decisions and links between related raw records"),
    ("manual_reviews", "Reviewer label, prior values, submitted edits, normalized result, issues, outcome, and time"),
    ("schema_versions", "Applied database migration version"),
], [1.6,5.1])
h("Why transactions matter")
p("The original file is committed before schema normalization, and parsed raw rows are committed before output processing. All sales and processing outputs then share one database transaction. If an unexpected exception occurs, those output writes roll back together. The application attempts to mark the batch failed while retaining the durable input for retry.")
p("Batch states are pending, processing, completed, and failed. A completed batch can legitimately contain quarantined records. A malformed CSV or invalid schema is an input failure; a database or unexpected processing exception is an operational failure. Operational failures are not reported as bad individual sales records.")
h("Concurrency and recovery")
p("A PostgreSQL advisory transaction lock serializes acceptance decisions across ingestion and manual review. Unique transaction keys and checks on quantities, amounts, supported country and currency, and the total equation provide a final safeguard. This favors clear local behavior over high throughput.")
p("A retry can resume a pending, processing, or failed batch safely. A database outage can prevent the failure marker itself from being saved; after connectivity returns, retry the durable batch or resubmit identical bytes if the initial insert never committed. Old batches cannot be reviewed or retried under changed global rule configuration without an explicit new submission.")

page("Interface and manual review")
p("The Streamlit application exposes six views. All processing actions call the same service used by the CLI, keeping business behavior consistent between entry points.")
table(["View", "What the user can do"], [
    ("Upload", "Choose a declared source profile, preview original values, see unknown columns, and process a CSV."),
    ("Batch history", "Inspect state, counts, duration, current row lineage, common issues, and duplicate relationships; retry eligible batches."),
    ("Accepted records", "Inspect typed sales originating from the selected batch and download them."),
    ("Correction audit", "Inspect every correction attempt, including before and proposed values and whole-record revalidation."),
    ("Quarantine review", "Inspect original input and reasons, edit canonical fields, submit a review, and inspect its history."),
    ("Rules and profiles", "Read active rules, supported values, aliases, and source format declarations."),
], [1.45,5.25])
h("How a review works")
for lead, text in [
    ("Inspect. ", "Select a quarantined snapshot and compare its current values, original input, and reasons."),
    ("Edit explicitly. ", "Enter a reviewer name and supply verified values in the canonical field form. The original raw record is not overwritten."),
    ("Resubmit. ", "The service applies the same corrections and revalidation, then checks against existing accepted sales. The user cannot bypass validation."),
    ("Read the result. ", "A valid new sale is accepted as corrected; a matching existing sale is excluded; an invalid or conflicting edit remains quarantined. Every submitted review is retained."),
]:
    p(text, lead)
p("A human may explicitly resolve a conflict within a batch by resubmitting the verified version. Other conflicting rows remain quarantined until separately reviewed. Reviewer names are local audit labels rather than authenticated identities.")
h("Exports and untrusted input")
p("Accepted data, quarantine data, and correction history can be downloaded as CSV. Spreadsheet-oriented exports prefix risky values with an apostrophe to reduce formula injection risk while preserving stored values. File size, row, encoding, column, and numeric-format checks bound and validate input. No uploaded file is treated as executable code.")
p("A true revalidation flag in the correction audit means the row passed data validation after correction. Duplicate checks occur later, so that flag alone does not establish that a sale was accepted.")

page("Run the application and demonstrate it")
h("Start the local services")
p("With Docker Desktop running its Linux engine, open a terminal in the project directory and run:")
code("docker compose up --build -d\ndocker compose logs -f app")
p("Open http://localhost:8501. PostgreSQL is exposed locally on port 5432 and Streamlit on port 8501. A Docker volume keeps database data across restarts. The application initializes its schema on connection. Compose credentials are local development defaults.")
h("Process and replay the sample")
p("In Upload, choose us_sales and upload samples/messy.csv. Inspect the preview, process the file, and select the batch in the sidebar. Review its correction audit, quarantine reasons, and duplicate lineage. The equivalent CLI command below uses us_sales by default.")
code("docker compose exec app pipeline ingest samples/messy.csv\ndocker compose exec app pipeline summary 1")
p("For an initially empty accepted store, the deterministic 240-row messy sample produces:")
table(["Outcome", "Rows", "Share of input"], [
    ("Accepted without correction", "20", "8.33%"),
    ("Accepted after correction", "60", "25.00%"),
    ("Quarantined", "140", "58.33%"),
    ("Excluded duplicates", "20", "8.33%"),
    ("Total", "240", "100% before display rounding"),
], [3.55,.65,2.5])
p("The displayed shares round individually. Run the same ingestion command again: it should return the same batch and counts. Batch 1 is illustrative; use the returned ID if your store already contains other batches. Then review a quarantined row, fix verified values, and confirm that its current outcome and review history change together.")
h("Generate data and run tests")
code("docker compose exec app python scripts/generate_samples.py\ndocker compose exec app python -m pytest -q\ndocker compose exec app pipeline retry 1\ndocker compose down")
p("The generator also creates a 5-row clean sample and a 1-row European sample. It uses no randomness or current clock. Expected counts are in samples/expected.json. Integration tests use the dedicated pipeline_test database and truncate its tables; never use a database containing valuable data for that purpose. Detailed native Python setup is in README.md.")

page("Verification and project structure")
h("What was actually verified")
p("During implementation on 29 October 2026, all 44 tests passed locally with Python 3.13 and inside the Python 3.12 Docker application, against real PostgreSQL. The final container run reported 44 passed in 7.80 seconds. This is a recorded verification result, not a guarantee for future environment changes.")
p("Coverage includes safe corrections and their audit entries, ambiguous values, Decimal arithmetic, failures after partial repair, duplicate conflicts and existing sales, equivalent concurrent submissions, manual edits, bounded passes, transactional rollback and retry, metric reconciliation, and the 240-row end-to-end demo. Automated Streamlit interaction covered all views and a successful manual review. The running app health endpoint returned ok, and a CLI replay returned the original completed demo batch.")
h("Where the implementation lives")
table(["File or directory", "Responsibility"], [
    ("pipeline/input.py", "Strict CSV parsing, schema mapping, limits, and source lineage"),
    ("pipeline/quality.py", "Pandera validation, Decimal checks, rules, and revalidation"),
    ("pipeline/service.py", "Batch lifecycle, atomic processing, duplicates, reviews, and summaries"),
    ("pipeline/db.py", "SQLAlchemy models, PostgreSQL connections, and migrations"),
    ("pipeline/config.py and profiles.json", "Supported values, aliases, versions, limits, and source profiles"),
    ("pipeline/cli.py and export.py", "Command-line entry point and protected CSV export"),
    ("streamlit_app.py", "Six interface views and review forms"),
    ("tests and samples", "Automated verification and reproducible demo fixtures"),
], [2.2,4.5])
h("How to extend it")
p("Add a rule with a stable ID, version, target fields, applicability predicate, and structured result, then place it in the explicit rule order. Test safe and unsafe cases and increment RULESET_VERSION when behavior changes. Add source profiles with declared formats, column aliases, and authority policy. Append database migrations rather than changing an already deployed migration.")
h("Current limits and future work")
p("This is a local MVP for bounded files and demonstration volumes. Country and currency coverage is intentionally limited. It has no authentication, production deployment setup, streaming, automated retention, exchange-rate conversion, or AI-generated corrections. Production access controls, backups, performance work, and retention policies would require separate engineering.")
p("Source basis: the project README, Python service and validation modules, source profiles, database models, interface, tests, and samples/expected.json. This document explains implemented behavior rather than proposing additional functionality.")

doc.core_properties.title = "Self Correcting Data Pipeline Project Explanation"
doc.core_properties.subject = "Architecture, data quality rules, audit, demonstration, and verification"
doc.core_properties.author = ""
doc.core_properties.keywords = "data quality, PostgreSQL, Pandera, Streamlit, deterministic corrections"
path = OUT / "Self_Correcting_Data_Pipeline_Project_Explanation.docx"
doc.save(path)
print(path)
