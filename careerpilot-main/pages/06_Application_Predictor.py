"""Application Success Predictor — explainable application strength score."""

import streamlit as st

from services import ai_service as ai
from services import database as db
from utils import ui

st.set_page_config(page_title="Application Predictor — CareerPilot AI", page_icon="📊", layout="wide")
ui.inject_css()
db.init_db()

st.title("📊 Application Success Predictor")
st.caption("An explainable strength score for your application — not a guaranteed probability of getting hired.")

profile = db.get_profile()
if not ui.require_profile(profile):
    st.stop()

job = ui.job_selector_widget("predictor")
if not ui.require_selected_job(job):
    st.stop()

st.markdown(f"### {job['title']} at {job['company']}")

existing_app = db.get_application_by_job_id(job["id"])
cached = existing_app.get("application_score_json") if existing_app else None
match_cached = existing_app.get("match_json") if existing_app else None

if st.button("🔄 Calculate Application Strength", type="primary"):
    with st.spinner("Scoring your application..."):
        match_result = match_cached or ai.match_job(profile, job)
        result = ai.predict_application_strength(profile, job, match_result)
    st.session_state["app_strength_result"] = result
    if not existing_app:
        app_id = db.add_application(job, status="Saved")
    else:
        app_id = existing_app["id"]
    db.update_application(app_id, {
        "application_score": result["score"],
        "application_score_json": result,
        "match_json": match_result,
        "match_score": match_result.get("overall_match_pct"),
    })
    cached = result

result = st.session_state.get("app_strength_result") or cached

if not result:
    ui.empty_state("📊", "No score yet", "Click **Calculate Application Strength** to generate one.")
    st.stop()

if result.get("ai_warning"):
    ui.ai_error_box(result["ai_warning"])

st.markdown(
    f"<div class='cp-card' style='text-align:center; padding:1.5rem;'>"
    f"<div class='cp-metric-label'>Application Strength</div>"
    f"<div style='font-size:3rem; font-weight:800; font-family:Sora,sans-serif; "
    f"color:{'#34D399' if result['score']>=70 else '#FBBF24' if result['score']>=50 else '#F87171'};'>"
    f"{result['score']}/100</div></div>", unsafe_allow_html=True,
)
st.caption(f"📐 {result['calculation_note']}")
st.info(result.get("summary", ""))

st.markdown("#### Score Breakdown")
for factor in result["factors"]:
    sign = "+" if factor["points"] >= 0 else ""
    st.markdown(f"**{sign}{factor['points']}** — {factor['label']} (max {factor['max']})")
    ui.progress_bar(round(factor["points"] / factor["max"] * 100) if factor["max"] else 0, "")

st.divider()
st.markdown("#### 📈 What Would Increase Your Score?")
suggestions = result.get("improvement_suggestions", [])
if not suggestions:
    st.success("No clear quick wins identified — your application is already well-aligned!")
else:
    for s in suggestions:
        st.markdown(f"**{s['action']} → +{s['estimated_points']} estimated points**")
        if s.get("explanation"):
            st.caption(s["explanation"])

st.caption("⚠️ This is an AI-generated estimate based on your profile data — not a guaranteed hiring probability.")

st.divider()
if st.button("🎤 Practice interview for this job →"):
    st.switch_page("pages/07_Interview_Twin.py")
