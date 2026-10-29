import pytest

from pipeline.export import csv_bytes, safe_cell
from pipeline.input import InputError, parse_csv
from conftest import encoded


def test_aliases_raw_unknown_columns(row, profile):
    content = encoded([row]).replace(b"customer_id", b"cust_id").replace(b"total_amount\r", b"total_amount,extra\r").replace(b"20.50\r", b"20.50,retain me\r")
    parsed = parse_csv(content, profile)
    assert parsed.raw[0]["cust_id"] == "C1"
    assert parsed.mapped[0]["customer_id"] == "C1"
    assert parsed.unknown_columns == ["extra"]


@pytest.mark.parametrize("content", [b"", b"id\n1\n", b"\xff", b"a,a\n1,2\n", b'a\n"unterminated', b"a\x00\n1"])
def test_bad_csv(content, profile):
    with pytest.raises(InputError):
        parse_csv(content, profile)


def test_conflicting_mapping(row, profile):
    content = encoded([row]).replace(b"email", b"cust_id")
    with pytest.raises(InputError, match="conflicting"):
        parse_csv(content, profile)


@pytest.mark.parametrize("value", ["=1+1", " @SUM(A1)", "\t=cmd", "-2", "+3", "\n=4"])
def test_formula_injection(value):
    assert safe_cell(value).startswith("'")
    assert value in csv_bytes([{"value": value}]).decode("utf-8-sig")


def test_multiline_lineage(row, profile):
    parsed = parse_csv(encoded([{**row, "product": "two\nlines"}, row]), profile)
    assert parsed.line_numbers == [2, 4]
