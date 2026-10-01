"""Career Roadmap — dynamically updates based on profile, skill gaps, and rejection history."""

import streamlit as st

from services import ai_service as ai
from services import database as db
from utils import ui

st.set_page_config(page_title="Career Roadmap — CareerPilot AI", page_icon="🗺", layout="wide")
ui.inject_css()
db.init_db()

st.title("🗺️ Your Career Roadmap")
st.caption("A phased plan that updates as your applications, rejections, and skill gaps change.")

profile = db.get_profile()
if not ui.require_profile(profile):
    st.stop()

applications = db.get_all_applications()
rejection_analysis = st.session_state.get("rejection_analysis")
if not rejection_analysis:
    rejected = [a for a in applications if a["status"] == "Rejected"]
    if len(rejected) >= 2:
        st.caption("💡 Tip: run **Rejection Analyzer** first for a roadmap that accounts for your rejection patterns.")

if st.button("🔄 Generate / Refresh Roadmap", type="primary"):
    if not ai.api_key_configured():
        ui.ai_error_box("Building your roadmap needs an AI key. Add one for free in **Settings** to enable this feature.")
    else:
        with st.spinner("Building your personalized roadmap..."):
            result = ai.generate_career_roadmap(profile, applications, rejection_analysis)
        st.session_state["career_roadmap"] = result

result = st.session_state.get("career_roadmap")

if not result:
    ui.empty_state("🗺️", "No roadmap yet", "Click **Generate / Refresh Roadmap** to build one from your current data.")
    st.stop()

if result.get("error"):
    st.error(result["error"])
    st.stop()

ui.ai_badge()
if result.get("top_missing_skills"):
    st.caption(f"Based on skills that keep appearing as gaps across your applications: {', '.join(result['top_missing_skills'])}")

stages = [
    ("now", "🟢 NOW", "#34D399"),
    ("next", "🟡 NEXT", "#FBBF24"),
    ("then", "🟠 THEN", "#FB923C"),
    ("finally", "🔵 FINALLY", "#60A5FA"),
]

for key, label, color in stages:
    stage = result.get(key, {})
    if not stage:
        continue
    st.markdown(
        f"<div class='cp-card' style='border-left: 4px solid {color};'>"
        f"<div style='font-weight:800; font-family:Sora,sans-serif; color:{color};'>{label} — {stage.get('title','')}</div>"
        + "".join(f"<div style='margin-top:6px;'>• {a}</div>" for a in stage.get("actions", []))
        + "</div>",
        unsafe_allow_html=True,
    )
    if key != "finally":
        st.markdown("<div style='text-align:center; color:#6B7280; margin: -4px 0 4px 0;'>↓</div>", unsafe_allow_html=True)
