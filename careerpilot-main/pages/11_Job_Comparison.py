"""Job Comparison — compare up to 3 jobs side by side with an AI recommendation."""

import streamlit as st

from services import ai_service as ai
from services import database as db
from services import job_service as js
from utils import helpers as h
from utils import ui

st.set_page_config(page_title="Job Comparison — CareerPilot AI", page_icon="📑", layout="wide")
ui.inject_css()
db.init_db()

st.title("📑 Job Comparison")
st.caption("Compare up to 3 jobs side by side and get a prioritization recommendation.")

profile = db.get_profile()
if not ui.require_profile(profile):
    st.stop()

jobs = js.load_jobs()
labels = {f"{j['company']} — {j['title']}": j["id"] for j in jobs}
selected_labels = st.multiselect("Select 2-3 jobs to compare", list(labels.keys()), max_selections=3)

if len(selected_labels) < 2:
    ui.empty_state("📑", "Select at least 2 jobs", "Choose 2-3 jobs above to compare them.")
    st.stop()

selected_jobs = [js.get_job_by_id(labels[lbl]) for lbl in selected_labels]

if st.button("🔄 Compare", type="primary"):
    rows = []
    with st.spinner("Analyzing each job..."):
        for job in selected_jobs:
            existing_app = db.get_application_by_job_id(job["id"])
            match = existing_app.get("match_json") if existing_app else None
            if not match:
                match = ai.match_job(profile, job)
            skill_match = h.compute_skill_match(profile["skills"], job["required_skills"], job["preferred_skills"])
            factors = h.compute_reality_factors(profile, job, skill_match)
            strength = h.compute_application_strength(profile, job, skill_match, match.get("project_relevance_pct", 50))
            rows.append({"job": job, "match": match, "factors": factors, "strength": strength})
    st.session_state["comparison_rows"] = rows

rows = st.session_state.get("comparison_rows")

if rows and len(rows) == len(selected_jobs) and all(r["job"]["id"] in [j["id"] for j in selected_jobs] for r in rows):
    st.markdown("#### Comparison Table")

    labels_row = ["Job Title", "Company", "Match", "Skill Gap", "Experience Fit", "Remote", "Application Score", "Recommendation"]
    cols = st.columns(len(rows) + 1)
    with cols[0]:
        st.write("")
        for label in labels_row:
            st.markdown(f"**{label}**")

    def gap_word(missing_count):
        if missing_count == 0:
            return "Low"
        if missing_count <= 2:
            return "Medium"
        return "High"

    for col, r in zip(cols[1:], rows):
        with col:
            job = r["job"]
            st.write("")
            st.markdown(job["title"])
            st.markdown(job["company"])
            st.markdown(f"{r['match']['overall_match_pct']}%")
            st.markdown(gap_word(len(r["match"]["required_missing"])))
            st.markdown(f"{r['factors']['experience_pct']}%")
            st.markdown("Yes" if job["remote_status"] == "Remote" else "No")
            st.markdown(f"{r['strength']['score']}")
            st.markdown(f"{r['factors']['emoji']} {r['factors']['category']}")

    st.divider()
    if st.button("🤖 Which job should I prioritize?", type="primary"):
        if not ai.api_key_configured():
            ui.ai_error_box("This recommendation needs an AI key. Add one for free in **Settings** to enable this feature.")
        else:
            compact = [{
                "title": r["job"]["title"], "company": r["job"]["company"],
                "overall_match": r["match"]["overall_match_pct"],
                "missing_skills": r["match"]["required_missing"],
                "reality_check": r["factors"]["category"],
                "application_score": r["strength"]["score"],
            } for r in rows]
            with st.spinner("Weighing the options..."):
                res = ai.recommend_job_priority(compact)
            if res.get("error"):
                st.error(res["error"])
            else:
                ui.ai_badge()
                st.markdown(f"### Prioritize: {res.get('recommended_job', '')}")
                st.write(res.get("explanation", ""))
else:
    st.caption("Click **Compare** to run the analysis.")
