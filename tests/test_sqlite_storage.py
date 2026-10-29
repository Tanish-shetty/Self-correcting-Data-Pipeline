from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from conftest import encoded
from pipeline.db import MoneyCents, Sale, engine, migrate
from pipeline.service import Pipeline


def test_exact_large_money_survives_reopening(service, row, profile):
    amount = "90071992547409.93"  # cents exceed the exact range of binary double floats
    content = encoded([{**row, "quantity": "1", "unit_price": amount, "total_amount": amount}])
    batch = service.submit(content, "exact.csv", profile)
    url = service.db.url
    service.db.dispose()
    reopened = engine(url)
    try:
        migrate(reopened)
        pipeline = Pipeline(reopened)
        assert pipeline.submit(content, "again.csv", profile) == batch
        with pipeline.session() as session:
            assert session.get(Sale, row["transaction_id"]).total_amount == Decimal(amount)
            assert session.execute(text("SELECT total_amount FROM sales")).scalar_one() == 9007199254740993
            assert session.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
        with pytest.raises(IntegrityError):
            with reopened.begin() as connection:
                connection.execute(text("UPDATE sales SET total_amount = total_amount + 1"))
        with pytest.raises(IntegrityError):
            with reopened.begin() as connection:
                connection.execute(text("DELETE FROM raw_records"))
    finally:
        reopened.dispose()


@pytest.mark.parametrize("amount", [1.01, "1.001", "NaN", "-0.01", "10000000000000000.00"])
def test_money_storage_refuses_lossy_or_invalid_values(amount):
    with pytest.raises(ValueError):
        MoneyCents().process_bind_param(amount, None)


def test_default_storage_ignores_legacy_server_url(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused.invalid/unused")
    monkeypatch.setenv("PIPELINE_DB_PATH", str(tmp_path / "local.sqlite3"))
    db = engine()
    try:
        migrate(db)
        assert db.url.get_backend_name() == "sqlite"
        assert (tmp_path / "local.sqlite3").exists()
    finally:
        db.dispose()
