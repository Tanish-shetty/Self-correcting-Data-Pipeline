import csv
import io
import json


def safe_cell(value):
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    value = "" if value is None else str(value)
    # Protect formulas even when spreadsheet import trims leading whitespace/control chars.
    if value.lstrip(" \t\r\n\ufeff").startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")):
        value = "'" + value
    return value


def csv_bytes(rows):
    output = io.StringIO(newline="")
    columns = list(dict.fromkeys(k for row in rows for k in row))
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    for row in rows:
        writer.writerow({k: safe_cell(v) for k, v in row.items()})
    return output.getvalue().encode("utf-8-sig")
