import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from sqlalchemy import func, select

from pipeline.db import Attempt, Batch, Duplicate, Quarantine, RawRecord, Review, Sale
from pipeline.input import InputError
from conftest import encoded

pytestmark = pytest.mark.integration


def count(service, model):
    with service.session() as s:
        return s.scalar(select(func.count()).select_from(model))


def test_ingest_sqlite_idempotent_and_metrics(service, row, profile):
    rows = [row, {**row, "transaction_id": "T2", "country": "USA"}, {**row, "transaction_id": "T3", "email": "bad"}, row]
    content = encoded(rows)
    batch = service.submit(content, "demo.csv", profile)
    summary = service.summary(batch)
    assert [summary[k] for k in ("accepted_valid", "accepted_corrected", "quarantined", "excluded_duplicate")] == [1, 1, 1, 1]
    assert summary["input_rows"] == sum(summary[k] for k in ("accepted_valid", "accepted_corrected", "quarantined", "excluded_duplicate"))
    before = [count(service, model) for model in (Sale, RawRecord, Attempt, Duplicate, Quarantine)]
    assert service.submit(content, "renamed.csv", profile) == batch
    assert before == [count(service, model) for model in (Sale, RawRecord, Attempt, Duplicate, Quarantine)]
    with service.session() as s:
        assert str(s.get(Sale, "T1").unit_price) == "10.25"
        assert s.get(Batch, batch).content == content


def test_conflicting_keys_quarantine_every_version(service, row, profile):
    batch = service.submit(encoded([row, row, {**row, "product": "Other"}]), "conflict.csv", profile)
    assert service.summary(batch)["quarantined"] == 3
    assert count(service, Sale) == 0
    assert count(service, Duplicate) == 3


def test_invalid_sibling_does_not_choose_winner(service, row, profile):
    batch = service.submit(encoded([row, {**row, "email": "invalid"}]), "conflict.csv", profile)
    assert service.summary(batch)["quarantined"] == 2


def test_existing_conflict_and_normalized_exact(service, row, profile):
    service.submit(encoded([row]), "first.csv", profile)
    conflict = service.submit(encoded([{**row, "product": "Other"}]), "conflict.csv", profile)
    assert service.summary(conflict)["quarantined"] == 1
    duplicate = service.submit(encoded([{**row, "unit_price": "10.2", "total_amount": "20.4"}]), "different.csv", profile)
    assert service.summary(duplicate)["quarantined"] == 1
    exact = service.submit(encoded([{**row, "country": "USA"}]), "exact.csv", profile)
    assert service.summary(exact)["excluded_duplicate"] == 1
    with service.session() as s:
        assert s.get(Sale, "T1").product == "Widget"


def test_manual_review_revalidates_preserves_history(service, row, profile):
    batch = service.submit(encoded([{**row, "email": "bad"}]), "bad.csv", profile)
    with service.session() as s:
        raw_id = s.scalar(select(RawRecord.id))
    assert service.review(raw_id, {**row, "quantity": "-1"}, "tester") == "quarantined"
    assert service.review(raw_id, row, "tester") == "accepted_corrected"
    assert count(service, Review) == 2
    assert count(service, Sale) == 1
    assert service.summary(batch)["quarantined"] == 0
    with service.session() as s:
        assert s.get(RawRecord, raw_id).original["email"] == "bad"


def test_manual_edit_duplicate_checks(service, row, profile):
    service.submit(encoded([row]), "good.csv", profile)
    service.submit(encoded([{**row, "transaction_id": "T2", "email": "bad"}]), "bad.csv", profile)
    with service.session() as s:
        raw_id = s.scalar(select(RawRecord.id).where(RawRecord.outcome == "quarantined"))
    assert service.review(raw_id, {**row, "product": "Different"}, "tester") == "quarantined"
    assert service.review(raw_id, row, "tester") == "excluded_duplicate"


def test_transaction_rollback_and_retry(service, row, profile, monkeypatch):
    original = service.accept_or_duplicate
    calls = 0
    def fail(s, raw, values):
        nonlocal calls
        original(s, raw, values)
        calls += 1
        if calls == 2:
            raise RuntimeError("injected operational failure")
    monkeypatch.setattr(service, "accept_or_duplicate", fail)
    with pytest.raises(RuntimeError):
        service.submit(encoded([row, {**row, "transaction_id": "T2", "country": "USA"}]), "retry.csv", profile)
    assert count(service, Sale) == count(service, Attempt) == 0
    assert count(service, RawRecord) == 2
    with service.session() as s:
        batch = s.scalar(select(Batch))
        assert batch.status == "failed" and batch.error_kind == "operational"
        batch_id = batch.id
    monkeypatch.setattr(service, "accept_or_duplicate", original)
    service.process(batch_id)
    assert service.summary(batch_id)["status"] == "completed"
    assert count(service, Sale) == 2 and count(service, Attempt) == 1


def test_schema_error_preserves_file(service, profile):
    with pytest.raises(InputError):
        service.submit(b"a\n1\n", "bad.csv", profile)
    with service.session() as s:
        batch = s.scalar(select(Batch))
        assert batch.content == b"a\n1\n" and batch.status == "failed" and batch.error_kind == "input"


def test_concurrent_equivalent_submission(service, row, profile):
    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(lambda _: service.submit(encoded([row]), "race.csv", profile), range(2)))
    assert ids[0] == ids[1]
    assert count(service, Sale) == count(service, RawRecord) == 1


def test_reproducible_demo(service, profile):
    root = Path(__file__).resolve().parents[1]
    expected = json.loads((root / "samples/expected.json").read_text())["messy.csv"]
    batch = service.submit((root / "samples/messy.csv").read_bytes(), "messy.csv", profile)
    summary = service.summary(batch)
    assert {k: summary[k] for k in expected} == expected


def test_column_mapping_is_audited_per_row(service, row, profile):
    content = encoded([row]).replace(b"customer_id", b"cust_id")
    batch = service.submit(content, "alias.csv", profile)
    assert service.summary(batch)["accepted_corrected"] == 1
    with service.session() as s:
        attempt = s.scalar(select(Attempt))
        assert (attempt.rule_id, attempt.field, attempt.original, attempt.proposed) == ("column_mapping", "column:customer_id", "cust_id", "customer_id")
        assert attempt.applied and attempt.revalidation_ok
