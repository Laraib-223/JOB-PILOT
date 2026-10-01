"""Job Reality Checker — signature feature: should I actually apply for this job?"""

import streamlit as st

from services import ai_service as ai
from services import database as db
from utils import ui

st.set_page_config(page_title="Job Reality Checker — CareerPilot AI", page_icon="🚦", layout="wide")
ui.inject_css()
db.init_db()

st.title("🚦 Job Reality Checker")
st.caption("An honest read on whether this job is actually worth your time right now.")

profile = db.get_profile()
if not ui.require_profile(profile):
    st.stop()

job = ui.job_selector_widget("reality")
if not ui.require_selected_job(job):
    st.stop()

st.markdown(f"### {job['title']} at {job['company']}")

existing_app = db.get_application_by_job_id(job["id"])
cached = existing_app.get("reality_check_json") if existing_app else None

if st.button("🔄 Run Reality Check", type="primary"):
    with st.spinner("Weighing skill fit, experience, education, and reading the job description..."):
        result = ai.reality_check(profile, job)
    st.session_state["reality_result"] = result
    if not existing_app:
        app_id = db.add_application(job, status="Saved")
    else:
        app_id = existing_app["id"]
    db.update_application(app_id, {"reality_check_json": result})
    cached = result

result = st.session_state.get("reality_result") or cached

if not result:
    ui.empty_state("🚦", "No reality check yet", "Click **Run Reality Check** to generate one.")
    st.stop()

if result.get("ai_warning"):
    ui.ai_error_box(result["ai_warning"])

category_bg = {
    "Strong Apply": "#0f3d2e", "Apply With Preparation": "#3d3410",
    "Stretch Opportunity": "#3d2a10", "Low Priority": "#3d1414",
}.get(result["category"], "#1e1e2e")

st.markdown(
    f"<div class='cp-card' style='background:{category_bg}; text-align:center; padding:2rem;'>"
    f"<div style='font-size:2.4rem;'>{result['emoji']}</div>"
    f"<div style='font-size:1.6rem; font-weight:800; font-family:Sora,sans-serif;'>{result['category']}</div>"
    f"<div style='color:#9CA3AF; margin-top:4px;'>Composite fit score: {result['weighted_score']}/100</div>"
    f"</div>", unsafe_allow_html=True,
)
st.caption(f"📐 How this was calculated: {result['calculation_note']}")

st.write("")
c1, c2, c3 = st.columns(3)
with c1:
    ui.progress_bar(result["skill_pct"], "Skill Match (40%)")
with c2:
    ui.progress_bar(result["experience_pct"], "Experience Fit (30%)")
with c3:
    ui.progress_bar(result["education_pct"], "Education Fit (15%)")
st.caption(f"Seniority gap assessed as: **{result['seniority_gap']}** (15% weight)")

st.divider()
st.markdown("#### Why this recommendation")
for reason in result.get("reasons", []):
    st.markdown(f"- {reason}")

if result.get("concerns"):
    st.markdown("#### ⚠️ Worth Verifying")
    for concern in result["concerns"]:
        st.markdown(f"- {concern}")
    st.caption(
        "These are wording-based observations from the job description, not accusations. "
        "Verify directly with the employer if anything is unclear."
    )

st.divider()
bc1, bc2 = st.columns(2)
with bc1:
    if st.button("🧩 See Skill Gap breakdown →"):
        st.switch_page("pages/04_Skill_Gap_Detective.py")
with bc2:
    if st.button("📊 See Application Strength →"):
        st.switch_page("pages/06_Application_Predictor.py")
