"""No randomness or clock dependency: regenerating produces byte-identical fixtures."""
import csv
from pathlib import Path

from pipeline.config import FIELDS

ROOT = Path(__file__).resolve().parents[1]


def base(i):
    return dict(zip(FIELDS, [f"TX-{i:04d}", f"C-{i:04d}", "2026-01-15", "Widget", "2", "10.25", "USD", "United States", "demo@example.com", "20.50"]))


def write(path, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def generate():
    out = ROOT / "samples"
    out.mkdir(exist_ok=True)
    write(out / "clean.csv", [base(i) for i in range(1, 6)])
    rows = []
    # 20 blocks × 12 rows. Each block: 1 valid, 3 corrected, 7 quarantine, 1 duplicate.
    for block in range(20):
        chunk = [base(1000 + block * 12 + j) for j in range(12)]
        chunk[1].update(customer_id=" C-DEMO ", country="USA", currency="usd", quantity="2.0", transaction_date="01/15/2026")
        chunk[2].update(unit_price="$10.25", total_amount="20.00")
        chunk[3].update(transaction_date="15/01/2026", customer_id="")
        chunk[4].update(transaction_date="01/02/03", quantity="0")
        chunk[5].update(unit_price="-1", total_amount="-2")
        chunk[6].update(email="broken@@mail", country="Atlantis")
        chunk[7].update(unit_price="€10.25")
        chunk[8] = dict(chunk[0])
        chunk[9].update(transaction_id=chunk[10]["transaction_id"], product="Different")
        chunk[11].update(unit_price="1,000.00", total_amount="2,000.00")
        rows.extend(chunk)
    write(out / "messy.csv", rows)
    eu = base(9000)
    eu.update(transaction_date="15/01/2026", currency="EUR", country="DE", unit_price="1.234,50", total_amount="2.469,00")
    write(out / "eu.csv", [eu])
    corrections = [base(10001 + i) for i in range(5)]
    corrections[0].update(customer_id=" C-10001 ", product=" Widget ")
    corrections[1].update(transaction_date="01/15/2026")
    corrections[2].update(quantity="2.0", unit_price="$10.25")
    corrections[3].update(currency="usd", country="USA")
    corrections[4].update(total_amount="19.00")
    write(out / "test_corrections.csv", corrections)

    quarantine = [base(11001 + i) for i in range(5)]
    quarantine[0].update(email="broken@@mail")
    quarantine[1].update(transaction_date="01/02/03")
    quarantine[2].update(quantity="0", total_amount="0.00")
    quarantine[3].update(currency="XYZ")
    quarantine[4].update(unit_price="\u20ac10.25")
    write(out / "test_quarantine.csv", quarantine)

    first, conflict, other = base(12001), base(12002), base(12003)
    write(out / "test_duplicates.csv", [first, dict(first), conflict,
          {**conflict, "product": "Different Widget"}, other])
    print("Generated clean (5), messy (240), eu (1), and three focused test files (5 each). See samples/README.md.")


if __name__ == "__main__":
    generate()
