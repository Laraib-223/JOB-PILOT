"""Find Jobs — search/filter the (clearly labeled) demo job dataset."""

import streamlit as st

from services import database as db
from services import job_service as js
from utils import helpers as h
from utils import ui

st.set_page_config(page_title="Find Jobs — CareerPilot AI", page_icon="🔎", layout="wide")
ui.inject_css()
db.init_db()

st.title("🔎 Find Jobs")
ui.demo_badge()
st.caption("Browsing sample job listings so you can try out every feature right away.")

profile = db.get_profile()

with st.container():
    f1, f2, f3 = st.columns([2, 1, 1])
    with f1:
        query = st.text_input("Search title, company, or skill", "")
    with f2:
        categories = st.multiselect("Category", js.get_categories())
    with f3:
        remote = st.multiselect("Work type", ["Remote", "Hybrid", "On-site"])

    f4, f5 = st.columns(2)
    with f4:
        employment = st.multiselect("Employment type", ["Full-time", "Part-time", "Internship"])
    with f5:
        exp_level = st.multiselect("Experience level", ["Internship", "Entry-Level", "Mid-Level", "Senior"])

results = js.search_jobs(
    query=query, categories=categories, remote_statuses=remote,
    employment_types=employment, experience_levels=exp_level,
)

st.caption(f"Showing {len(results)} of {len(js.load_jobs())} jobs")
st.divider()

for job in results:
    with st.container():
        st.markdown('<div class="cp-card cp-job-card">', unsafe_allow_html=True)
        c1, c2 = st.columns([3, 1.3])
        with c1:
            st.markdown(f"### {job['title']}")
            st.markdown(f"**{job['company']}** · {job['location']}")
            st.caption(
                f"{job['remote_status']} · {job['employment_type']} · {job['experience_level']} · "
                f"{job.get('salary') or 'Salary not listed'}"
            )
            st.write(job["description"][:220] + ("…" if len(job["description"]) > 220 else ""))
            st.markdown(
                "**Required:** " + ", ".join(job["required_skills"]) +
                ("  \n**Preferred:** " + ", ".join(job["preferred_skills"]) if job["preferred_skills"] else "")
            )
        with c2:
            if profile and profile.get("skills"):
                sm = h.compute_skill_match(profile["skills"], job["required_skills"], job["preferred_skills"])
                ui.progress_bar(sm["skill_match_pct"], "Quick Skill Match")
            else:
                st.caption("Load your profile to see match %")

            existing = db.get_application_by_job_id(job["id"])
            if existing:
                st.markdown(ui.status_pill(existing["status"]), unsafe_allow_html=True)

            if st.button("🎯 Job Match", key=f"match_{job['id']}", use_container_width=True):
                st.session_state["selected_job_id"] = job["id"]
                st.switch_page("pages/03_Job_Match.py")
            if st.button("🧩 Skill Gap", key=f"gap_{job['id']}", use_container_width=True):
                st.session_state["selected_job_id"] = job["id"]
                st.switch_page("pages/04_Skill_Gap_Detective.py")
            if st.button("🚦 Reality Check", key=f"reality_{job['id']}", use_container_width=True):
                st.session_state["selected_job_id"] = job["id"]
                st.switch_page("pages/05_Job_Reality_Checker.py")

            if not existing:
                if st.button("💾 Save Job", key=f"save_{job['id']}", use_container_width=True):
                    db.add_application(job, status="Saved")
                    st.success(f"Saved {job['title']} at {job['company']}")
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

if not results:
    ui.empty_state("🔎", "No jobs match your filters", "Try widening your search criteria.")
