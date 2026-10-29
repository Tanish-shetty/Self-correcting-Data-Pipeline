import hashlib
import json
from dataclasses import asdict, dataclass
from importlib.resources import files

RULESET_VERSION = "1.0.0"
CURRENCIES = {"USD", "EUR", "GBP", "INR"}
COUNTRIES = {"United States", "United Kingdom", "Germany", "France", "India"}
COUNTRY_ALIASES = {"US": "United States", "USA": "United States", "UK": "United Kingdom", "DE": "Germany", "FR": "France", "IN": "India"}
CURRENCY_ALIASES = {"usd": "USD", "eur": "EUR", "gbp": "GBP", "inr": "INR", "US Dollar": "USD", "Euro": "EUR"}
SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP", "₹": "INR"}
FIELDS = ("transaction_id", "customer_id", "transaction_date", "product", "quantity", "unit_price", "currency", "country", "email", "total_amount")
REQUIRED = set(FIELDS) - {"email"}
MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 10000


@dataclass(frozen=True)
class Profile:
    name: str
    version: str
    date_formats: tuple[str, ...]
    decimal_separator: str
    thousands_separator: str | None
    authoritative_totals: bool
    column_aliases: dict[str, str]

    @property
    def fingerprint(self):
        config = {"profile": asdict(self), "rules": RULESET_VERSION,
                  "countries": sorted(COUNTRIES), "currencies": sorted(CURRENCIES),
                  "country_aliases": COUNTRY_ALIASES, "currency_aliases": CURRENCY_ALIASES,
                  "symbols": SYMBOLS, "fields": FIELDS, "max_bytes": MAX_BYTES, "max_rows": MAX_ROWS}
        return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()


def profiles():
    data = json.loads(files("pipeline").joinpath("profiles.json").read_text(encoding="utf-8"))
    return {name: Profile(name=name, **{**value, "date_formats": tuple(value["date_formats"])}) for name, value in data.items()}
