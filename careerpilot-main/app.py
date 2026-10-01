"""
CareerPilot AI — main entry point and Career Dashboard.

Run locally:
    streamlit run app.py
"""

from collections import Counter
from datetime import datetime

import streamlit as st

from services import ai_service as ai
from services import cv_service as cs
from services import database as db
from utils import ui

st.set_page_config(
    page_title="CareerPilot AI",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)

ui.inject_css()
db.init_db()

if "selected_job_id" not in st.session_state:
    st.session_state["selected_job_id"] = None


def _time_greeting() -> str:
    hour = datetime.now().hour
    if hour < 12:
        return "Good Morning"
    if hour < 18:
        return "Good Afternoon"
    return "Good Evening"


def _deterministic_insights(profile: dict, applications: list) -> list:
    """
    Rule-based insights computed directly from stored data — no AI call
    needed since this is a straightforward aggregation, and it keeps the
    dashboard fast and always available.
    """
    insights = []
    if not applications:
        return ["Save a few jobs and run Skill Gap / Job Match on them to start seeing insights here."]

    all_missing = []
    category_scores = {}
    for a in applications:
        gap = a.get("skill_gap_json")
        if gap:
            all_missing.extend(gap.get("skill_match", {}).get("required_missing", []))
        if a.get("match_score") is not None:
            job = None
            from services import job_service as js
            job = js.get_job_by_id(a["job_id"])
            if job:
                category_scores.setdefault(job["category"], []).append(a["match_score"])

    if all_missing:
        top_skill, count = Counter(all_missing).most_common(1)[0]
        total_with_gap = sum(1 for a in applications if a.get("skill_gap_json"))
        insights.append(
            f"**{top_skill}** appears as a missing skill in {count} of {total_with_gap} analyzed jobs — "
            f"it's your most common gap right now."
        )

    if category_scores:
        avg_by_cat = {cat: sum(scores) / len(scores) for cat, scores in category_scores.items()}
        best_cat = max(avg_by_cat, key=avg_by_cat.get)
        insights.append(f"Your strongest average match is in **{best_cat}** roles ({round(avg_by_cat[best_cat])}% avg).")
        if len(avg_by_cat) > 1:
            worst_cat = min(avg_by_cat, key=avg_by_cat.get)
            if worst_cat != best_cat:
                insights.append(
                    f"Your weakest average match is in **{worst_cat}** roles ({round(avg_by_cat[worst_cat])}% avg) — "
                    f"consider closing skill gaps before applying to more of these."
                )

    rejected = [a for a in applications if a["status"] == "Rejected"]
    if len(rejected) >= 2:
        insights.append(
            f"You have {len(rejected)} rejected applications — visit **Rejection Analyzer** to find recurring patterns."
        )

    if not insights:
        insights.append("Keep tracking applications and running analyses — insights get sharper with more data.")

    return insights


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

profile = db.get_profile()

with st.sidebar:
    st.markdown("## 🧭 CareerPilot AI")
    st.caption("Don't just find jobs. Find the right job — and become ready for it.")
    st.divider()

    if profile:
        st.markdown(f"**{profile.get('name') or 'Your Profile'}**")
        st.caption(profile.get("career_level") or "")
    else:
        st.info("No profile loaded yet.")

    if st.button("🧪 Load Demo Profile", use_container_width=True):
        cs.load_demo_profile()
        st.success("Demo profile loaded!")
        st.rerun()

    st.divider()
    if ai.api_key_configured():
        st.success("AI features enabled", icon="✅")
    else:
        st.warning("AI features off — add a free key", icon="🔑")
    st.caption("See **Settings** to set it up.")


# ---------------------------------------------------------------------------
# Main dashboard
# ---------------------------------------------------------------------------

name = profile.get("name") if profile else None
st.title(f"🧭 {_time_greeting()}{', ' + name if name else ''}")
st.caption("Your Career Overview")

if not profile:
    ui.empty_state(
        "👋", "Welcome to CareerPilot AI",
        "Load the demo profile from the sidebar, or head to **My CV** to upload your own resume.",
    )
else:
    applications = db.get_all_applications()
    stats = db.get_dashboard_stats()

    all_missing = []
    for a in applications:
        gap = a.get("skill_gap_json")
        if gap:
            all_missing.extend(gap.get("skill_match", {}).get("required_missing", []))
    top_gap = Counter(all_missing).most_common(1)[0][0] if all_missing else "—"

    qa_scores = [q["ai_score"] for q in db.get_interview_history() if q.get("ai_score") is not None]
    interview_readiness = round((sum(qa_scores) / len(qa_scores)) * 10) if qa_scores else 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        ui.metric_card("Avg Application Strength", f"{stats['avg_app_strength']}%")
    with c2:
        ui.metric_card("Avg Job Match", f"{stats['avg_match']}%")
    with c3:
        ui.metric_card("Interview Readiness", f"{interview_readiness}%")
    with c4:
        ui.metric_card("Top Skill Gap", top_gap)

    c5, c6, c7, c8 = st.columns(4)
    with c5:
        ui.metric_card("Applications", str(stats["total"]))
    with c6:
        ui.metric_card("Interviews", str(stats["interviews"]))
    with c7:
        ui.metric_card("Offers", str(stats["offers"]))
    with c8:
        ui.metric_card("Interview Rate", f"{stats['interview_rate']}%")

    st.write("")
    left, right = st.columns([1.4, 1])

    with left:
        st.markdown("#### 📌 Insights From Your Data")
        for insight in _deterministic_insights(profile, applications):
            st.markdown(f"<div class='cp-card'>{insight}</div>", unsafe_allow_html=True)

    with right:
        st.markdown("#### 🤖 What Should I Do Next?")
        st.caption("Your AI career agent's single highest-value recommendation.")
        if not ai.api_key_configured():
            ui.ai_error_box("Add an API key to enable this feature.")
        elif st.button("What Should I Do Next?", type="primary", use_container_width=True):
            with st.spinner("Analyzing your full profile and pipeline..."):
                result = ai.generate_next_action(profile, applications, stats)
            st.session_state["next_action_result"] = result

        result = st.session_state.get("next_action_result")
        if result:
            if result.get("error"):
                st.error(result["error"])
            else:
                ui.ai_badge()
                st.markdown(f"### {result.get('headline', '')}")
                st.write(result.get("detail", ""))

    st.divider()

st.markdown("#### 💡 Why CareerPilot AI is different")
d1, d2, d3, d4, d5 = st.columns(5)
features = [
    ("🕵️", "Skill Gap Detective", "Find exactly what you're missing."),
    ("⚖️", "Job Reality Checker", "Know whether a job is actually worth applying to."),
    ("🎤", "Interview Twin", "Practice questions based on YOUR CV and YOUR job."),
    ("📈", "Application Predictor", "Understand your application strength."),
    ("🔍", "Rejection Analyzer", "Turn rejection patterns into an improvement strategy."),
]
for col, (emoji, title, desc) in zip([d1, d2, d3, d4, d5], features):
    with col:
        st.markdown(
            f"<div class='cp-card' style='text-align:center; min-height:150px;'>"
            f"<div style='font-size:1.8rem;'>{emoji}</div>"
            f"<div style='font-weight:700; margin:0.3rem 0;'>{title}</div>"
            f"<div style='font-size:0.82rem; color:#9CA3AF;'>{desc}</div></div>",
            unsafe_allow_html=True,
        )

st.caption(
    "🔒 Privacy: your CV is used only to generate career recommendations locally in this app. "
    "Avoid uploading sensitive information that isn't necessary for your job search."
)
