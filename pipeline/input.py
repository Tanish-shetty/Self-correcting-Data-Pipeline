import csv
import io
from dataclasses import dataclass

from .config import FIELDS, MAX_BYTES, MAX_ROWS, REQUIRED


class InputError(ValueError):
    pass


@dataclass
class Parsed:
    raw: list[dict]
    mapped: list[dict]
    line_numbers: list[int]
    unknown_columns: list[str]
    mappings: dict[str, str]


def parse_csv(content, profile):
    if len(content) > MAX_BYTES:
        raise InputError(f"File exceeds {MAX_BYTES} bytes (5 MiB)")
    try:
        text = content.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as exc:
        raise InputError("CSV must use UTF-8 encoding; save as UTF-8 and retry") from exc
    if "\x00" in text:
        raise InputError("CSV contains NUL bytes")
    try:
        reader = csv.reader(io.StringIO(text, newline=""), strict=True)
        headers = next(reader, [])
        if not headers:
            raise InputError("CSV is empty or lacks a header")
        mappings = {h: profile.column_aliases.get(h.strip(), h.strip()) for h in headers}
        targets = list(mappings.values())
        if len(set(headers)) != len(headers) or len(set(targets)) != len(targets):
            raise InputError("Duplicate headers or conflicting column aliases; provide one column per field")
        missing = REQUIRED - set(targets)
        if missing:
            raise InputError("Missing required columns: " + ", ".join(sorted(missing)))
        raw, mapped, lines = [], [], []
        while True:
            line = reader.line_num + 1
            values = next(reader, None)
            if values is None:
                break
            if len(values) != len(headers):
                raise InputError(f"Source line {line}: expected {len(headers)} cells, got {len(values)}")
            if any(len(v) > 10000 for v in values):
                raise InputError(f"Source line {line}: cell exceeds 10,000 characters")
            raw.append(dict(zip(headers, values)))
            mapped.append({mappings[h]: v for h, v in zip(headers, values) if mappings[h] in FIELDS})
            lines.append(line)
            if len(raw) > MAX_ROWS:
                raise InputError(f"File exceeds {MAX_ROWS} rows")
        if not raw:
            raise InputError("CSV contains no data rows")
        return Parsed(raw, mapped, lines, sorted(set(targets) - set(FIELDS)), mappings)
    except csv.Error as exc:
        raise InputError(f"Malformed CSV: {exc}") from exc
