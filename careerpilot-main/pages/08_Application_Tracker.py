"""Application Tracker — Kanban-style board over the SQLite-backed applications table."""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from services import database as db
from utils import helpers as h
from utils import ui

st.set_page_config(page_title="Application Tracker — CareerPilot AI", page_icon="📋", layout="wide")
ui.inject_css()
db.init_db()

st.title("📋 Application Tracker")
st.caption("Every application you've saved or applied to, tracked end-to-end.")

applications = db.get_all_applications()

if not applications:
    ui.empty_state("📭", "No applications yet", "Save a job from **Find Jobs** to start tracking it here.")
    st.stop()

stats = db.get_dashboard_stats()

c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
for col, (label, value) in zip(
    [c1, c2, c3, c4, c5, c6, c7],
    [
        ("Total", stats["total"]), ("This Week", stats["this_week"]),
        ("Interviews", stats["interviews"]), ("Offers", stats["offers"]),
        ("Rejections", stats["rejections"]), ("Interview Rate", f"{stats['interview_rate']}%"),
        ("Success Rate", f"{stats['success_rate']}%"),
    ],
):
    with col:
        ui.metric_card(label, str(value))

st.write("")
chart_col1, chart_col2 = st.columns(2)
df = pd.DataFrame(applications)

with chart_col1:
    status_counts = df["status"].value_counts().reset_index()
    status_counts.columns = ["status", "count"]
    fig = px.pie(status_counts, names="status", values="count", hole=0.55,
                 color="status", color_discrete_map=h.STATUS_COLORS)
    fig.update_traces(textinfo="percent+label")
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                       font_color="#E5E7EB", title="Applications by Status", height=320,
                       margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig, use_container_width=True)

with chart_col2:
    df["date_key"] = pd.to_datetime(df["date_saved"], errors="coerce")
    timeline = df.dropna(subset=["date_key"]).groupby(df["date_key"].dt.date).size().reset_index(name="count")
    if not timeline.empty:
        fig2 = go.Figure(go.Bar(x=timeline["date_key"], y=timeline["count"], marker_color="#8B7CF6"))
        fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                           font_color="#E5E7EB", title="Applications Over Time", height=320,
                           margin=dict(l=10, r=10, t=40, b=10))
        fig2.update_xaxes(gridcolor="rgba(148,163,184,0.15)")
        fig2.update_yaxes(gridcolor="rgba(148,163,184,0.15)")
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Not enough dated applications yet for a timeline.")

st.divider()

KANBAN_COLUMNS = ["Saved", "Applied", "Interview", "Offer", "Rejected"]
STATUS_TRANSITIONS = ["Saved", "Applied", "Interview", "Offer", "Rejected", "Withdrawn"]

kanban_cols = st.columns(len(KANBAN_COLUMNS))

for col, status in zip(kanban_cols, KANBAN_COLUMNS):
    with col:
        color = h.STATUS_COLORS.get(status, "#60A5FA")
        st.markdown(
            f"<div style='border-top:3px solid {color}; padding-top:6px; font-weight:700;'>{status} "
            f"({sum(1 for a in applications if a['status']==status)})</div>",
            unsafe_allow_html=True,
        )
        for app in [a for a in applications if a["status"] == status]:
            with st.container():
                st.markdown('<div class="cp-card">', unsafe_allow_html=True)
                st.markdown(f"**{app['company']}**")
                st.caption(app["job_title"])
                if app.get("match_score") is not None:
                    st.caption(f"🎯 Match: {app['match_score']}%")
                if app.get("application_score") is not None:
                    st.caption(f"📊 Strength: {app['application_score']}%")

                with st.expander("Edit"):
                    new_status = st.selectbox(
                        "Status", STATUS_TRANSITIONS,
                        index=STATUS_TRANSITIONS.index(app["status"]),
                        key=f"status_{app['id']}",
                    )
                    date_applied = st.text_input(
                        "Date Applied (YYYY-MM-DD)", value=app.get("date_applied") or "",
                        key=f"date_{app['id']}",
                    )
                    notes = st.text_area("Notes", value=app.get("notes") or "", key=f"notes_{app['id']}", height=70)

                    rejection_reason = recruiter_feedback = interview_feedback = None
                    if new_status in ("Rejected", "Interview", "Offer", "Withdrawn"):
                        rejection_reason = st.text_input(
                            "Rejection reason (optional)", value=app.get("rejection_reason") or "",
                            key=f"rr_{app['id']}",
                        )
                        recruiter_feedback = st.text_input(
                            "Recruiter feedback (optional)", value=app.get("recruiter_feedback") or "",
                            key=f"rf_{app['id']}",
                        )
                        interview_feedback = st.text_input(
                            "Interview feedback (optional)", value=app.get("interview_feedback") or "",
                            key=f"if_{app['id']}",
                        )

                    bcol1, bcol2 = st.columns(2)
                    with bcol1:
                        if st.button("💾 Save", key=f"savebtn_{app['id']}", use_container_width=True):
                            update_fields = {
                                "status": new_status, "date_applied": date_applied, "notes": notes,
                            }
                            if rejection_reason is not None:
                                update_fields["rejection_reason"] = rejection_reason
                                update_fields["recruiter_feedback"] = recruiter_feedback
                                update_fields["interview_feedback"] = interview_feedback
                            db.update_application(app["id"], update_fields)
                            st.success("Updated.")
                            st.rerun()
                    with bcol2:
                        if st.button("🗑️ Delete", key=f"delbtn_{app['id']}", use_container_width=True):
                            db.delete_application(app["id"])
                            st.rerun()

                    if st.button("🎯 View Job", key=f"viewjob_{app['id']}", use_container_width=True):
                        st.session_state["selected_job_id"] = app["job_id"]
                        st.switch_page("pages/03_Job_Match.py")
                st.markdown("</div>", unsafe_allow_html=True)

withdrawn = [a for a in applications if a["status"] == "Withdrawn"]
if withdrawn:
    st.divider()
    st.markdown(f"#### Withdrawn ({len(withdrawn)})")
    for app in withdrawn:
        st.markdown(f"- {app['company']} — {app['job_title']}")
