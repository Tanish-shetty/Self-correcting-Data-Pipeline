"""Compatibility entry point; this view is also the main app landing screen."""
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.demo import render_live_correction

st.set_page_config(page_title="Self-Correcting Data Pipeline", page_icon="🔎", layout="wide")
st.title("Self-Correcting Data Pipeline")
render_live_correction(evidence_directory=ROOT / "artifacts/healing-report")
