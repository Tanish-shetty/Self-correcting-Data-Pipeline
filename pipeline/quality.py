"""One bounded correction pass followed by independent Pandera validation."""
import re
from dataclasses import dataclass
from datetime import datetime, date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from typing import Callable

import pandas as pd
import pandera.pandas as pa

from .config import (COUNTRIES, COUNTRY_ALIASES, CURRENCIES, CURRENCY_ALIASES,
                     FIELDS, SYMBOLS, Profile)

CENT = Decimal("0.01")


def money(value):
    """NUMERIC(18,2), no exponent notation and no implicit precision loss."""
    if not isinstance(value, str) or not re.fullmatch(r"-?\d{1,16}(?:\.\d{1,2})?", value):
        raise ValueError("use a decimal with at most 16 integer and 2 fractional digits")
    return Decimal(value)


def total(quantity, price):
    with localcontext() as ctx:
        ctx.prec = 50
        return (quantity * price).quantize(CENT, rounding=ROUND_HALF_UP)


def email_ok(value):
    return value == "" or (len(value) <= 254 and bool(re.fullmatch(r"[^\s@]+@[^\s@.]+(?:\.[^\s@.]+)+", value)))


def positive_int(value):
    return bool(re.fullmatch(r"[0-9]{1,10}", value)) and 0 < int(value) <= 2147483647


def date_ok(value):
    try:
        return date.fromisoformat(value).isoformat() == value
    except (ValueError, TypeError):
        return False


def price_ok(value):
    try:
        return money(value) >= 0
    except (ValueError, InvalidOperation):
        return False


def check(fn, reason):
    return pa.Check(fn, element_wise=True, error=reason)


SCHEMA = pa.DataFrameSchema({
    **{f: pa.Column(object, check(lambda x: isinstance(x, str) and 0 < len(x) <= 200,
                                 "required text (1–200 characters)"))
       for f in ("transaction_id", "customer_id", "product")},
    "transaction_date": pa.Column(object, check(date_ok, "requires a declared date format")),
    "quantity": pa.Column(object, check(positive_int, "requires a positive 32-bit integer")),
    "unit_price": pa.Column(object, check(price_ok, "requires nonnegative NUMERIC(18,2)")),
    "currency": pa.Column(object, check(lambda x: x in CURRENCIES, "unsupported currency")),
    "country": pa.Column(object, check(lambda x: x in COUNTRIES, "unsupported country")),
    "email": pa.Column(object, check(email_ok, "invalid email syntax; edit explicitly")),
    "total_amount": pa.Column(object, check(price_ok, "requires nonnegative NUMERIC(18,2)")),
}, strict=True)


def validate(row):
    issues = []
    try:
        SCHEMA.validate(pd.DataFrame([{f: row.get(f, "") for f in FIELDS}], dtype=object), lazy=True)
    except pa.errors.SchemaErrors as exc:
        for failure in exc.failure_cases.to_dict("records"):
            issues.append({"field": str(failure["column"]), "reason": str(failure["check"])})
    if positive_int(row.get("quantity", "")) and price_ok(row.get("unit_price", "")) and price_ok(row.get("total_amount", "")):
        if money(row["total_amount"]) != total(int(row["quantity"]), money(row["unit_price"])):
            issues.append({"field": "total_amount", "reason": "must equal quantity × unit_price (ROUND_HALF_UP, 2 decimal places)"})
    return issues


@dataclass(frozen=True)
class Result:
    value: str
    reason: str
    applied: bool = True


@dataclass(frozen=True)
class Rule:
    id: str
    version: str
    fields: tuple[str, ...]
    applies: Callable
    transform: Callable


def parse_date(value, row, profile):
    candidates = set()
    for fmt in profile.date_formats:
        try:
            parsed = datetime.strptime(value, fmt).date()
            # strptime permits non-padded days; profile still explicitly determines order.
            candidates.add(parsed.isoformat())
        except ValueError:
            pass
    if len(candidates) != 1:
        return Result(value, "date is unsupported or ambiguous under declared formats", False)
    return Result(candidates.pop(), "parsed using declared source date formats")


def parse_number(value, row, profile):
    original = value
    found = [s for s in SYMBOLS if s in value]
    if found:
        if len(found) != 1 or SYMBOLS[found[0]] != row.get("currency") or not value.startswith(found[0]) or value.count(found[0]) != 1:
            return Result(original, "currency symbol conflicts with declared currency or position", False)
        value = value[len(found[0]):].strip()
    dec, group = profile.decimal_separator, profile.thousands_separator
    integer = r"\d+" if not group else rf"(?:\d+|\d{{1,3}}(?:{re.escape(group)}\d{{3}})+)"
    if not re.fullmatch(rf"-?{integer}(?:{re.escape(dec)}\d+)?", value):
        return Result(original, "number does not match declared decimal/thousands separators", False)
    if group:
        value = value.replace(group, "")
    value = value.replace(dec, ".")
    return Result(value, "parsed declared numeric separators and consistent currency symbol")


def quantity(value, row, profile):
    if any(s in value for s in SYMBOLS):
        return Result(value, "quantity must not contain currency symbols", False)
    parsed = parse_number(value, row, profile)
    if not parsed.applied:
        return parsed
    number = Decimal(parsed.value)
    if number != number.to_integral_value() or abs(number) > 2147483647:
        return Result(value, "quantity is fractional or outside 32-bit range", False)
    return Result(str(int(number)), "converted exact whole-number quantity")


RULES = (
    Rule("trim", "1.0.0", FIELDS, lambda v, r, p: v != v.strip(), lambda v, r, p: Result(v.strip(), "trim surrounding whitespace")),
    Rule("country_alias", "1.0.0", ("country",), lambda v, r, p: v in COUNTRY_ALIASES, lambda v, r, p: Result(COUNTRY_ALIASES[v], "explicit country alias")),
    Rule("currency_alias", "1.0.0", ("currency",), lambda v, r, p: v in CURRENCY_ALIASES, lambda v, r, p: Result(CURRENCY_ALIASES[v], "explicit currency alias")),
    Rule("date_format", "1.0.0", ("transaction_date",), lambda v, r, p: bool(v) and not date_ok(v), parse_date),
    Rule("quantity_format", "1.0.0", ("quantity",), lambda v, r, p: bool(v) and not re.fullmatch(r"[0-9]+", v), quantity),
    Rule("money_format", "1.0.0", ("unit_price", "total_amount"), lambda v, r, p: bool(v), parse_number),
)


def correct(row, profile: Profile, *, on_stage=None):
    current = {f: row.get(f, "") for f in FIELDS}
    initial_issues = validate(current)
    if on_stage:
        on_stage("initial_validation")
    attempts = []

    def record(rule_id, version, field, result):
        old = current[field]
        if old != result.value or not result.applied:
            attempts.append({"field": field, "original": old, "proposed": result.value,
                             "rule_id": rule_id, "rule_version": version,
                             "reason": result.reason, "applied": result.applied})
            if result.applied:
                current[field] = result.value

    # Each rule visits each field once. Rules never restart earlier rules.
    if on_stage:
        on_stage("correction_pass")
    for rule in RULES:
        for field in rule.fields:
            if rule.applies(current[field], current, profile):
                record(rule.id, rule.version, field, rule.transform(current[field], current, profile))
    if (profile.authoritative_totals and positive_int(current["quantity"]) and price_ok(current["unit_price"])):
        expected = total(int(current["quantity"]), money(current["unit_price"]))
        # Missing/invalid totals are not invented. Only a valid supplied total may be replaced.
        if price_ok(current["total_amount"]) and money(current["total_amount"]) != expected and price_ok(str(expected)):
            record("authoritative_total", "1.0.0", "total_amount", Result(str(expected), "source declares quantity and unit_price authoritative"))
    issues = validate(current)
    if on_stage:
        on_stage("revalidation")
    # A failed parse must not accidentally be accepted by the canonical validator.
    for attempt in attempts:
        if not attempt["applied"]:
            issues.append({"field": attempt["field"], "reason": attempt["reason"]})
    for attempt in attempts:
        attempt["revalidation_ok"] = not issues
    return current, initial_issues, issues, attempts


def canonical(row):
    """Normalized equality includes optional email; money representations compare equally."""
    result = dict(row)
    for field in ("unit_price", "total_amount"):
        if price_ok(result.get(field, "")):
            result[field] = format(money(result[field]), ".2f")
    if positive_int(result.get("quantity", "")):
        result["quantity"] = str(int(result["quantity"]))
    return result
