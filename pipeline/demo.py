"""Shared live correction view used by the main app and report capture entry point."""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from .config import FIELDS, RULESET_VERSION, profiles
from .quality import correct

BASE = dict(zip(FIELDS, ["DEMO-SAFE", " C1 ", "01/15/2026", "Widget", "2.0", "$10.25",
                         "usd", "USA", "a@example.com", "20.00"]))
CASES = {
    "Safe corrections": BASE,
    "Unsafe values": {**BASE, "transaction_id": "DEMO-UNSAFE", "customer_id": "C1",
                      "quantity": "2", "currency": "USD", "transaction_date": "01/02/03",
                      "unit_price": "€10.25", "email": "bad@@mail"},
}


def render_live_correction(*, evidence_directory=None):
    st.subheader("Live correction engine evidence")
    st.caption(f"us_sales | Ruleset {RULESET_VERSION}")
    st.info("Try the real correction rules below. Demonstration runs do not save sales. "
            "Use Upload to process a CSV with local saving and duplicate checks.")
    case = st.radio("Evidence case", [*CASES, "Automated tests"], horizontal=True)
    if case == "Automated tests":
        _show_recorded_tests()
        return

    profile = profiles()["us_sales"]
    raw = dict(CASES[case])
    key = f"live_correction:{profile.fingerprint}:{case}"
    result = st.session_state.get(key)
    run_col, reset_col = st.columns([1, 3])
    with run_col:
        run = st.button("Run one correction pass", type="primary", disabled=result is not None)
    with reset_col:
        reset = st.button("Reset this case", disabled=result is None)
    if reset:
        st.session_state.pop(key, None)
        st.rerun()
    if run:
        stages = []
        started = time.perf_counter()
        fixed, initial, issues, attempts = correct(raw, profile, on_stage=stages.append)
        result = {
            "case": case, "source": "pipeline/quality.py:correct", "profile": profile.name,
            "ruleset_version": RULESET_VERSION, "correction_calls": 1,
            "automatic_passes": stages.count("correction_pass"),
            "validation_calls": sum(stage in ("initial_validation", "revalidation") for stage in stages),
            "stages": stages, "raw": raw, "corrected": fixed,
            "initial_issues": initial, "final_issues": issues, "attempts": attempts,
            "elapsed_seconds": round(time.perf_counter() - started, 6),
            "captured_utc": datetime.now(timezone.utc).isoformat(),
        }
        st.session_state[key] = result
        if evidence_directory is not None:
            target = Path(evidence_directory)
            target.mkdir(parents=True, exist_ok=True)
            filename = "safe.json" if case == "Safe corrections" else "unsafe.json"
            (target / filename).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        st.rerun()

    cols = st.columns(4)
    cols[0].metric("Automatic passes", result["automatic_passes"] if result else 0)
    cols[1].metric("Validation calls", result["validation_calls"] if result else 0)
    cols[2].metric("Applied field changes", sum(a["applied"] for a in result["attempts"]) if result else 0)
    cols[3].metric("Remaining issues", len(result["final_issues"]) if result else "Not evaluated")
    if result:
        if result["final_issues"]:
            st.warning("AFTER PASS 1: QUARANTINE REQUIRED - unsuccessful parsing is not guessed.")
        else:
            st.success("AFTER PASS 1: ALL DATA CHECKS PASS - ready for downstream duplicate checks.")
    else:
        st.warning("BEFORE CORRECTION: no automatic correction pass has run.")

    st.markdown("#### Original values and result")
    st.dataframe([{"Field": field, "Original input": raw[field],
                   "After pass 1": result["corrected"][field] if result else "Not run"}
                  for field in FIELDS], hide_index=True, width="stretch", height=390)
    if result:
        detail = st.radio("Detail view", ["Correction audit", "Validation reasons"], horizontal=True)
        if detail == "Correction audit":
            st.markdown("#### Rule audit from the actual execution")
            st.dataframe([{"Rule": a["rule_id"], "Field": a["field"], "Before": a["original"],
                           "After": a["proposed"], "Applied": a["applied"],
                           "Revalidation OK": a["revalidation_ok"]} for a in result["attempts"]],
                         hide_index=True, width="stretch", height=300)
        else:
            st.markdown("#### Unresolved reasons after revalidation")
            if result["final_issues"]:
                st.dataframe(result["final_issues"], hide_index=True, width="stretch")
            else:
                st.success("No unresolved validation issues.")
        st.caption("One pass visits the configured rules once, then checks the total policy and revalidates. "
                   "Individual field repairs are not separate iterations. Reset starts a new demonstration run.")
        st.download_button("Download this execution as JSON", json.dumps(result, indent=2, ensure_ascii=False),
                           file_name=f"{raw['transaction_id']}_execution.json", mime="application/json")


def _show_recorded_tests():
    st.header("Automated test results")
    st.code('python -m pytest -q -p no:cacheprovider', language="powershell")
    path = Path(__file__).resolve().parents[1] / "artifacts/healing-report/tests.json"
    if not path.exists():
        st.info("Run the command above to check this installation. To display its captured output here, "
                "run python scripts/run_healing_report_tests.py.")
        return
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
        st.caption(f"Recorded run: {result['captured_utc']}. This tab does not start a new test run.")
        st.code(result["stdout"], language="text")
        if result.get("stderr"):
            st.code(result["stderr"], language="text")
        st.metric("Process exit code", result["exit_code"])
        st.caption(result.get("scope", "Historical recorded run; see the command above for its scope."))
    except (OSError, ValueError, KeyError, TypeError):
        st.warning("The recorded test result could not be read. Regenerate it using the command above.")
