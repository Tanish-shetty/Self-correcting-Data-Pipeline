"""The main landing screen must run real corrections without opening local storage."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

from pipeline import db

ROOT = Path(__file__).resolve().parents[1]


def offline_app(monkeypatch):
    def unavailable(*args, **kwargs):
        raise RuntimeError("local storage intentionally unavailable for this test")
    monkeypatch.setattr(db, "engine", unavailable)
    return AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=15).run()


def test_main_screen_runs_safe_correction_and_reset_offline(monkeypatch):
    app = offline_app(monkeypatch)
    assert not app.exception and not app.error
    assert app.sidebar.radio[0].value == "Live correction"
    assert app.metric[0].value == "0"
    next(b for b in app.button if b.label == "Run one correction pass").click().run()
    assert not app.exception
    assert [m.value for m in app.metric] == ["1", "2", "7", "0"]
    values = app.dataframe[0].value.set_index("Field")
    assert values.loc["total_amount", "After pass 1"] == "20.50"
    assert values.loc["country", "After pass 1"] == "United States"
    assert len(app.dataframe[1].value) == 7
    assert next(b for b in app.button if b.label == "Run one correction pass").disabled
    next(b for b in app.button if b.label == "Reset this case").click().run()
    assert app.metric[0].value == "0"
    assert not next(b for b in app.button if b.label == "Run one correction pass").disabled


def test_main_screen_preserves_unsafe_values_and_reasons_offline(monkeypatch):
    app = offline_app(monkeypatch)
    next(r for r in app.radio if r.label == "Evidence case").set_value("Unsafe values").run()
    next(b for b in app.button if b.label == "Run one correction pass").click().run()
    assert not app.exception
    assert [m.value for m in app.metric] == ["1", "2", "1", "5"]
    assert any("QUARANTINE REQUIRED" in w.value for w in app.warning)
    values = app.dataframe[0].value.set_index("Field")
    assert values.loc["transaction_date", "After pass 1"] == "01/02/03"
    assert values.loc["unit_price", "After pass 1"] == "€10.25"
    next(r for r in app.radio if r.label == "Detail view").set_value("Validation reasons").run()
    assert set(app.dataframe[1].value["field"]) == {"transaction_date", "unit_price", "email"}
    next(r for r in app.radio if r.label == "Evidence case").set_value("Safe corrections").run()
    assert app.metric[0].value == "0"


def test_database_failure_keeps_navigation_available(monkeypatch):
    app = offline_app(monkeypatch)
    app.sidebar.radio[0].set_value("Upload").run()
    assert not app.exception
    assert any("Could not open local storage" in e.value for e in app.error)
    app.sidebar.radio[0].set_value("Rules & profiles").run()
    assert not app.exception and not app.error
    app.sidebar.radio[0].set_value("Live correction").run()
    assert not app.exception and not app.error
