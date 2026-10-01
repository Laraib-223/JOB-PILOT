"""Job Match — AI + rule-based match report between profile and selected job."""

import streamlit as st

from services import ai_service as ai
from services import database as db
from utils import ui

st.set_page_config(page_title="Job Match — CareerPilot AI", page_icon="🎯", layout="wide")
ui.inject_css()
db.init_db()

st.title("🎯 Job Match")
st.caption("A visual, explainable breakdown of how your profile lines up with a specific job.")

profile = db.get_profile()
if not ui.require_profile(profile):
    st.stop()

job = ui.job_selector_widget("jobmatch")
if not ui.require_selected_job(job):
    st.stop()

st.markdown(f"### {job['title']} at {job['company']}")
st.caption(f"{job['location']} · {job['remote_status']} · {job['employment_type']}")

existing_app = db.get_application_by_job_id(job["id"])
cached = existing_app.get("match_json") if existing_app else None

run_col, save_col = st.columns([1, 3])
with run_col:
    run_clicked = st.button("🔄 Run Match Analysis", type="primary")

if run_clicked:
    if not ai.api_key_configured():
        ui.ai_error_box("Full job matching needs an AI key. Add one for free in **Settings** for the project-relevance assessment.")
    else:
        with st.spinner("Comparing your profile to this job..."):
            result = ai.match_job(profile, job)
        st.session_state["match_result"] = result
        if not existing_app:
            app_id = db.add_application(job, status="Saved")
        else:
            app_id = existing_app["id"]
        db.update_application(app_id, {
            "match_score": result["overall_match_pct"],
            "match_json": result,
        })
        cached = result

result = st.session_state.get("match_result") or cached

if not result:
    ui.empty_state("🎯", "No match analysis yet", "Click **Run Match Analysis** to generate one.")
    st.stop()

if result.get("ai_warning"):
    ui.ai_error_box(result["ai_warning"])

st.markdown("#### Overall Match")
ui.progress_bar(result["overall_match_pct"], "Overall")
st.caption(f"📐 {result['overall_calculation_note']}")

c1, c2 = st.columns(2)
with c1:
    ui.progress_bar(result["skill_match_pct"], "Skills")
    st.caption(result["skill_calculation_note"])
    ui.progress_bar(result["experience_pct"], "Experience")
    st.caption(result["experience_note"])
with c2:
    ui.progress_bar(result["education_pct"], "Education")
    st.caption(result["education_note"])
    ui.progress_bar(result["project_relevance_pct"], "Projects")
    st.caption(result.get("project_relevance_reasoning", ""))

st.divider()
c3, c4 = st.columns(2)
with c3:
    st.markdown("##### ✅ Skills You Have")
    for s in result["required_matched"]:
        st.markdown(f"- {s}")
    if result["required_partial"]:
        st.markdown("##### 🟡 Partial Matches")
        for s in result["required_partial"]:
            st.markdown(f"- {s}")
with c4:
    st.markdown("##### ❌ Missing Required Skills")
    if result["required_missing"]:
        for s in result["required_missing"]:
            st.markdown(f"- {s}")
    else:
        st.caption("None — you meet all required skills!")
    st.write("")
    if st.button("🧩 See full Skill Gap breakdown →"):
        st.switch_page("pages/04_Skill_Gap_Detective.py")
