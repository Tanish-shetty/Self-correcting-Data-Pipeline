"""Run: streamlit run streamlit_app.py"""
import logging
from collections import Counter
from dataclasses import asdict

import streamlit as st
from sqlalchemy import select

from pipeline.config import FIELDS, profiles, COUNTRIES, CURRENCIES, COUNTRY_ALIASES, CURRENCY_ALIASES
from pipeline.db import Attempt, Batch, Duplicate, Quarantine, RawRecord, Review, Sale, engine, migrate
from pipeline.export import csv_bytes
from pipeline.input import parse_csv
from pipeline.quality import RULES
from pipeline.service import Pipeline
from pipeline.demo import render_live_correction

st.set_page_config(page_title="Self-Correcting Data Pipeline", page_icon="🔎", layout="wide")
st.title("Self-Correcting Data Pipeline")
st.caption("Deterministic sales validation · Explicit corrections · Complete row lineage")

view = st.sidebar.radio("View", ["Live correction", "Upload", "Batch history", "Accepted records",
                                 "Correction audit", "Quarantine review", "Rules & profiles"])
if view == "Live correction":
    render_live_correction()
    st.stop()


@st.cache_resource
def connect():
    db = engine()
    migrate(db)
    return Pipeline(db)


batch_id = None
if view != "Rules & profiles":
    try:
        service = connect()
        st.sidebar.caption("History and reviews are saved locally on this computer.")
        with service.session() as session:
            batches = list(session.scalars(select(Batch).order_by(Batch.id.desc())))
    except Exception:
        logging.exception("Local storage initialization failed")
        st.error("Could not open local storage. Check that the data folder is writable. "
                 "Live correction and Rules & profiles remain available from the sidebar.")
        if st.button("Retry local storage"):
            connect.clear()
            st.rerun()
        st.stop()
    batch_options = [b.id for b in batches]
    batch_id = st.sidebar.selectbox("Batch", batch_options, index=0 if batch_options else None)
    if batch_id is not None:
        st.sidebar.caption(f"Selected batch #{batch_id}")


def dicts(objects):
    return [{column.name: getattr(obj, column.name) for column in obj.__table__.columns
             if column.name != "content"} for obj in objects]


def show_table(rows, name):
    st.dataframe(rows, width="stretch")
    st.download_button(f"Download {name} CSV", csv_bytes(rows), file_name=f"{name}.csv", mime="text/csv")


if view == "Upload":
    st.header("Upload sales CSV")
    name = st.selectbox("Declared source profile", list(profiles()))
    profile = profiles()[name]
    st.json(asdict(profile), expanded=False)
    uploaded = st.file_uploader("UTF-8 CSV · maximum 5 MiB / 10,000 rows", type=["csv"])
    if uploaded:
        content = uploaded.getvalue()
        try:
            parsed = parse_csv(content, profile)
            st.write(f"{len(parsed.raw)} input rows. Preview retains original values.")
            st.dataframe(parsed.raw[:20], width="stretch")
            if parsed.unknown_columns:
                st.info("Unknown columns retained in raw input only: " + ", ".join(parsed.unknown_columns))
        except ValueError as exc:
            st.warning(str(exc))
        if st.button("Process and persist", type="primary"):
            try:
                with st.spinner("Validating, correcting, and persisting…"):
                    result = service.submit(content, uploaded.name, profile)
                st.success(f"Batch #{result} completed (equivalent submissions reuse the same batch).")
                st.json(service.summary(result))
                st.cache_data.clear()
            except Exception as exc:
                logging.exception("Ingestion failed")
                st.error(str(exc) if isinstance(exc, ValueError) else "Operational failure. Check logs and Batch history; retry after resolving the cause.")
elif view == "Batch history":
    st.header("Batch history")
    show_table(dicts(batches), "batches")
    if batch_id:
        summary = service.summary(batch_id)
        st.json(summary)
        st.caption("Final outcomes are mutually exclusive; their sum equals input rows for completed batches. Rates use input rows as denominator. Reviews update current outcomes; audit history remains immutable.")
        columns = st.columns(4)
        for col, key in zip(columns, ("accepted_valid", "accepted_corrected", "quarantined", "excluded_duplicate")):
            col.metric(key.replace("_", " ").title(), summary[key])
        with service.session() as s:
            raw = list(s.scalars(select(RawRecord).where(RawRecord.batch_id == batch_id).order_by(RawRecord.source_line)))
            show_table(dicts(raw), "row_lineage")
            attempts = list(s.scalars(select(Attempt).where(Attempt.batch_id == batch_id)))
            issues = list(s.scalars(select(Quarantine).join(RawRecord, RawRecord.id == Quarantine.raw_id).where(RawRecord.batch_id == batch_id, Quarantine.resolved_at.is_(None))))
            st.write("Correction types", dict(Counter(a.rule_id for a in attempts)))
            st.write("Current quarantine issue types", dict(Counter(i["reason"] for q in issues for i in q.issues)))
            st.write("Duplicate lineage")
            decisions = list(s.scalars(select(Duplicate).join(RawRecord, RawRecord.id == Duplicate.raw_id).where(RawRecord.batch_id == batch_id)))
            st.dataframe(dicts(decisions), width="stretch")
        if summary["status"] in ("failed", "pending", "processing") and st.button("Retry batch"):
            try:
                service.process(batch_id)
                st.rerun()
            except Exception:
                logging.exception("Retry failed")
                st.error("Retry failed. See batch error and server logs.")
elif view == "Accepted records":
    st.header("Accepted sales")
    st.caption("Shows accepted records originating from the selected batch. Excluded duplicates point to the original sale in Batch history.")
    with service.session() as s:
        rows = list(s.scalars(select(Sale).join(RawRecord).where(RawRecord.batch_id == batch_id))) if batch_id else []
        show_table(dicts(rows), "accepted")
elif view == "Correction audit":
    st.header("Correction attempts")
    st.caption("Revalidation describes the whole record after correction, before duplicate checks. An applied field correction does not imply row acceptance.")
    with service.session() as s:
        attempts = list(s.scalars(select(Attempt).where(Attempt.batch_id == batch_id).order_by(Attempt.id))) if batch_id else []
        show_table(dicts(attempts), "corrections")
elif view == "Quarantine review":
    st.header("Quarantine review")
    with service.session() as s:
        query = select(Quarantine).join(RawRecord).where(RawRecord.batch_id == batch_id, Quarantine.resolved_at.is_(None)).order_by(Quarantine.id)
        items = list(s.scalars(query)) if batch_id else []
    show_table(dicts(items), "quarantine")
    selected = st.selectbox("Quarantine snapshot", [q.id for q in items], index=0 if items else None)
    if selected:
        q = next(q for q in items if q.id == selected)
        with service.session() as lookup:
            raw = lookup.get(RawRecord, q.raw_id)
        st.write("Original input", raw.original)
        st.write("Reasons", q.issues)
        with st.form(f"review_{selected}"):
            actor = st.text_input("Reviewer name (local audit identity; no authentication)")
            edited = {f: st.text_input(f, value=q.values.get(f, "")) for f in FIELDS}
            submitted = st.form_submit_button("Validate and resubmit")
        if submitted:
            try:
                outcome = service.review(q.raw_id, edited, actor)
                st.success(f"Review recorded. Outcome: {outcome}")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
            except Exception:
                logging.exception("Review failed")
                st.error("Operational failure; no review changes committed. Resolve the cause and retry.")
    st.subheader("Review history")
    with service.session() as s:
        reviews = list(s.scalars(select(Review).join(RawRecord).where(RawRecord.batch_id == batch_id).order_by(Review.id))) if batch_id else []
        st.dataframe(dicts(reviews), width="stretch")
else:
    st.header("Explicit rules and source profiles")
    st.write("Currencies", sorted(CURRENCIES))
    st.write("Canonical countries", sorted(COUNTRIES))
    st.write("Country aliases", COUNTRY_ALIASES)
    st.write("Currency aliases", CURRENCY_ALIASES)
    st.json({k: asdict(v) for k, v in profiles().items()})
    st.table([{"rule_id": r.id, "version": r.version, "fields": ", ".join(r.fields)} for r in RULES] + [
        {"rule_id": "authoritative_total", "version": "1.0.0", "fields": "total_amount (only authoritative profiles)"},
        {"rule_id": "column_mapping", "version": "1.0.0", "fields": "column:<canonical name> (explicit header mappings)"}])
    st.info("One ordered correction pass. Missing business values are never inferred. Money uses Decimal, two fractional digits, and ROUND_HALF_UP. Unknown columns remain raw only. No currency conversion or statistical outlier repair.")
