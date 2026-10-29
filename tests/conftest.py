import csv
import io

import pytest

from pipeline.config import FIELDS, profiles
from pipeline.db import engine, migrate
from pipeline.service import Pipeline


@pytest.fixture
def row():
    return dict(zip(FIELDS, ["T1", "C1", "2026-01-15", "Widget", "2", "10.25", "USD", "United States", "a@example.com", "20.50"]))


@pytest.fixture
def profile():
    return profiles()["us_sales"]


def encoded(rows):
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode()


@pytest.fixture
def service(tmp_path):
    db = engine(f"sqlite:///{(tmp_path / 'pipeline.sqlite3').as_posix()}")
    migrate(db)
    yield Pipeline(db)
    db.dispose()
