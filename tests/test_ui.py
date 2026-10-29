from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from pipeline.db import RawRecord
from sqlalchemy import select
from conftest import encoded

pytestmark = pytest.mark.integration


def test_streamlit_views_and_review(service, row, profile, monkeypatch):
    monkeypatch.setenv("PIPELINE_DB_PATH", service.db.url.database)
    service.submit(encoded([{**row, "email": "bad"}]), "ui.csv", profile)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "streamlit_app.py"), default_timeout=20)
    app.run()
    assert not app.exception
    for view in ("Batch history", "Accepted records", "Correction audit", "Rules & profiles", "Quarantine review"):
        app.sidebar.radio[0].set_value(view).run()
        assert not app.exception, (view, app.exception)
    inputs = {item.label: item for item in app.text_input}
    inputs["Reviewer name (local audit identity; no authentication)"].input("UI tester")
    inputs["email"].input("a@example.com")
    app.button[0].click().run()
    assert not app.exception
    with service.session() as s:
        assert s.scalar(select(RawRecord)).outcome == "accepted_corrected"
