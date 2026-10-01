"""Rejection Analyzer — turns rejection history into actionable pattern detection."""

import streamlit as st

from services import ai_service as ai
from services import database as db
from utils import ui

st.set_page_config(page_title="Rejection Analyzer — CareerPilot AI", page_icon="🔍", layout="wide")
ui.inject_css()
db.init_db()

st.title("🔍 Rejection Analyzer")
st.caption("Turn your rejection history into a concrete improvement strategy.")

applications = db.get_all_applications()
rejected = [a for a in applications if a["status"] == "Rejected"]

st.markdown(f"**{len(rejected)}** rejected application(s) currently logged.")

if rejected:
    with st.expander("📋 Review / add rejection details", expanded=False):
        for app in rejected:
            st.markdown(f"**{app['company']} — {app['job_title']}**")
            c1, c2 = st.columns(2)
            with c1:
                reason = st.text_input("Rejection reason", value=app.get("rejection_reason") or "",
                                        key=f"reason_{app['id']}")
            with c2:
                feedback = st.text_input("Recruiter feedback", value=app.get("recruiter_feedback") or "",
                                          key=f"feedback_{app['id']}")
            if st.button("Save", key=f"save_rej_{app['id']}"):
                db.update_application(app["id"], {"rejection_reason": reason, "recruiter_feedback": feedback})
                st.success("Saved.")
                st.rerun()
            st.divider()

if st.button("🔍 Analyze Rejection Patterns", type="primary", disabled=len(rejected) < 2):
    if not ai.api_key_configured():
        ui.ai_error_box("Finding patterns needs an AI key. Add one for free in **Settings** to enable this feature.")
    else:
        with st.spinner("Looking for recurring patterns across your rejections..."):
            result = ai.analyze_rejections(applications)
        st.session_state["rejection_analysis"] = result

if len(rejected) < 2:
    st.info("Log at least 2 rejected applications (with reasons/feedback where possible) to unlock pattern detection.")

result = st.session_state.get("rejection_analysis")
if result:
    if result.get("error"):
        st.error(result["error"])
    elif result.get("insufficient_data"):
        st.info(result["message"])
    else:
        ui.ai_badge()
        st.markdown("### 🧩 Pattern Detected")
        st.write(result.get("summary", ""))

        for p in result.get("patterns", []):
            st.markdown(
                f"<div class='cp-card'><b>{p['issue']}</b> — appears in {p['frequency']}<br>"
                f"<span style='color:#9CA3AF;'>{p['detail']}</span></div>",
                unsafe_allow_html=True,
            )

        if result.get("top_improvement_area"):
            st.markdown(
                f"<div class='cp-card' style='border-color:#8B7CF6;'>"
                f"<b>🎯 Your biggest improvement opportunity:</b><br>{result['top_improvement_area']}</div>",
                unsafe_allow_html=True,
            )

        st.divider()
        if st.button("🗺️ Update my Career Roadmap based on this →"):
            st.switch_page("pages/10_Career_Roadmap.py")
