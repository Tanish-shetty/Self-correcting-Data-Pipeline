from dataclasses import replace
from decimal import Decimal

import pytest

from pipeline.config import profiles
from pipeline.quality import RULES, correct, total, validate


def test_safe_corrections_and_audit(row, profile):
    row.update(customer_id=" C1 ", currency="usd", country="USA", quantity="2.0", unit_price="$10.25", total_amount="20.00", transaction_date="01/15/2026")
    fixed, initial, issues, attempts = correct(row, profile)
    assert initial and not issues
    assert fixed["total_amount"] == "20.50"
    assert {a["rule_id"] for a in attempts} == {"trim", "currency_alias", "country_alias", "quantity_format", "money_format", "date_format", "authoritative_total"}
    assert all(a["applied"] and a["revalidation_ok"] and a["rule_version"] for a in attempts)


@pytest.mark.parametrize("field,value", [("transaction_date", "01/02/03"), ("quantity", "2.5"), ("unit_price", "€10.25"), ("unit_price", "1,23.45"), ("email", "bad@@mail"), ("country", "Atlantis"), ("customer_id", ""), ("unit_price", "0.001")])
def test_unsafe_values_quarantined(row, profile, field, value):
    row[field] = value
    assert correct(row, profile)[2]


def test_ambiguous_date_formats_not_guessed(row, profile):
    ambiguous = replace(profile, date_formats=("%d/%m/%Y", "%m/%d/%Y"))
    row["transaction_date"] = "01/02/2026"
    _, _, issues, attempts = correct(row, ambiguous)
    assert issues and not attempts[0]["applied"]


def test_declared_eu_format(row):
    row.update(currency="EUR", country="DE", transaction_date="15/01/2026", unit_price="1.234,50", total_amount="2.469,00")
    fixed, _, issues, _ = correct(row, profiles()["eu_sales"])
    assert not issues and fixed["unit_price"] == "1234.50"


def test_decimal_and_rounding(row, profile):
    assert total(3, Decimal("0.10")) == Decimal("0.30")
    assert total(1, Decimal("1.005")) == Decimal("1.01")
    row.update(quantity="3", unit_price="0.10", total_amount="0.30")
    assert not validate(row)


def test_corrected_field_does_not_hide_invalid_email(row, profile):
    row.update(country="USA", email="invalid")
    fixed, _, issues, attempts = correct(row, profile)
    assert fixed["country"] == "United States" and issues
    assert attempts[0]["applied"] and not attempts[0]["revalidation_ok"]


def test_totals_require_explicit_authority_and_existing_value(row, profile):
    row["total_amount"] = "1.00"
    assert correct(row, replace(profile, authoritative_totals=False))[2]
    row["total_amount"] = ""
    assert correct(row, profile)[2]


def test_bounded_idempotent_pass(row, profile):
    row.update(country="USA", quantity="2.0")
    fixed, _, _, attempts = correct(row, profile)
    assert len(attempts) <= sum(len(r.fields) for r in RULES) + 1
    assert correct(fixed, profile)[3] == []


def test_oversized_quantity_is_quality_failure(row, profile):
    row["quantity"] = "9" * 10000
    assert correct(row, profile)[2]


def test_quantity_does_not_accept_money_symbols(row, profile):
    row["quantity"] = "$2.0"
    assert correct(row, profile)[2]


def test_correction_reports_actual_processing_stages(row, profile):
    stages = []
    row["country"] = "USA"
    assert not correct(row, profile, on_stage=stages.append)[2]
    assert stages == ["initial_validation", "correction_pass", "revalidation"]
