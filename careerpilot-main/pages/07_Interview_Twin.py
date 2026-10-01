"""
Interview Twin — signature feature: a personalized mock interview generated
from the user's actual CV, projects, and the selected job's requirements,
with a real interactive Q&A loop and AI evaluation of each answer.
"""

import streamlit as st

from services import ai_service as ai
from services import database as db
from utils import helpers as h
from utils import ui

st.set_page_config(page_title="Interview Twin — CareerPilot AI", page_icon="🎤", layout="wide")
ui.inject_css()
db.init_db()

st.title("🎤 Interview Twin")
st.caption("Practice questions generated from YOUR CV and YOUR selected job — not generic prep.")

profile = db.get_profile()
if not ui.require_profile(profile):
    st.stop()

job = ui.job_selector_widget("interview")
if not ui.require_selected_job(job):
    st.stop()

job_id = job["id"]
st.markdown(f"### {job['title']} at {job['company']}")

# Ensure we have an application row to attach Q&A history to.
existing_app = db.get_application_by_job_id(job_id)
if not existing_app:
    app_id = db.add_application(job, status="Saved")
    existing_app = db.get_application(app_id)
else:
    app_id = existing_app["id"]

QUEUE_KEY = f"interview_queue_{job_id}"
IDX_KEY = f"interview_idx_{job_id}"
FEEDBACK_KEY = f"interview_feedback_{job_id}"

CATEGORY_ORDER = ["HR", "Technical", "Project-based", "Behavioral", "Job-specific", "CV-specific", "Weak-area"]

if QUEUE_KEY not in st.session_state:
    st.session_state[QUEUE_KEY] = None
    st.session_state[IDX_KEY] = 0

col_gen, col_reset = st.columns([1, 1])
with col_gen:
    generate_clicked = st.button(
        "🎬 Generate Interview" if not st.session_state[QUEUE_KEY] else "🔁 Regenerate Interview",
        type="primary",
    )
with col_reset:
    if st.session_state[QUEUE_KEY] and st.button("⏮️ Restart This Interview"):
        st.session_state[IDX_KEY] = 0
        st.session_state.pop(FEEDBACK_KEY, None)
        st.rerun()

if generate_clicked:
    if not ai.api_key_configured():
        ui.ai_error_box("Generating interview questions needs an AI key. Add one for free in **Settings** to enable this feature.")
    else:
        with st.spinner("Building a personalized interview from your CV and this job..."):
            skill_match = h.compute_skill_match(profile.get("skills", []), job["required_skills"], job["preferred_skills"])
            skill_gap_stub = {"skill_match": skill_match}
            questions = ai.generate_interview(profile, job, skill_gap_stub)
        if questions.get("error"):
            st.error(questions["error"])
        else:
            queue = []
            for cat in CATEGORY_ORDER:
                for q in questions.get(cat, []):
                    queue.append({"category": cat, "question": q})
            st.session_state[QUEUE_KEY] = queue
            st.session_state[IDX_KEY] = 0
            st.session_state.pop(FEEDBACK_KEY, None)
            st.rerun()

queue = st.session_state.get(QUEUE_KEY)

if not queue:
    ui.empty_state("🎤", "No interview generated yet", "Click **Generate Interview** to build your personalized session.")
    st.stop()

idx = st.session_state[IDX_KEY]
total = len(queue)

if idx >= total:
    # ---- Interview complete: show readiness scores ----
    st.success("🎉 Interview complete! Here's your readiness breakdown.")
    history = db.get_interview_history(job_id)

    readiness_map = {
        "Technical": ["Technical", "Weak-area"],
        "Communication": ["HR", "Behavioral"],
        "Job-specific Knowledge": ["Job-specific"],
        "Project Confidence": ["Project-based", "CV-specific"],
    }
    readiness_scores = {}
    for label, cats in readiness_map.items():
        relevant = [q["ai_score"] for q in history if q["category"] in cats and q.get("ai_score") is not None]
        readiness_scores[label] = round((sum(relevant) / len(relevant)) * 10) if relevant else None

    cols = st.columns(4)
    for col, (label, score) in zip(cols, readiness_scores.items()):
        with col:
            if score is not None:
                ui.metric_card(label, f"{score}%")
            else:
                ui.metric_card(label, "—", "not assessed")

    db.update_application(app_id, {"interview_readiness_json": readiness_scores})

    st.divider()
    st.markdown("#### Full Transcript")
    for i, qa in enumerate(history, 1):
        with st.expander(f"{i}. [{qa['category']}] {qa['question'][:80]}"):
            st.markdown(f"**Your answer:** {qa['user_answer']}")
            fb = qa["ai_feedback_json"]
            st.markdown(f"**Score:** {qa['ai_score']}/10")
            st.markdown(f"**What was good:** {fb.get('what_was_good','')}")
            st.markdown(f"**What was missing:** {fb.get('what_was_missing','')}")
            st.markdown(f"**How to improve:** {fb.get('how_to_improve','')}")

    if st.button("⏮️ Restart Interview"):
        st.session_state[IDX_KEY] = 0
        st.session_state.pop(FEEDBACK_KEY, None)
        st.rerun()
    st.stop()

# ---- Active question ----
current = queue[idx]
st.progress(idx / total, text=f"Question {idx + 1} of {total}")
st.markdown(f'<span class="cp-pill" style="background:#8B7CF6;">{current["category"]}</span>', unsafe_allow_html=True)
st.markdown(f"### {current['question']}")

feedback = st.session_state.get(FEEDBACK_KEY)

if feedback is None:
    answer = st.text_area("Your answer", height=180, key=f"answer_input_{idx}")
    if st.button("✅ Submit Answer", type="primary", disabled=not answer.strip()):
        if not ai.api_key_configured():
            ui.ai_error_box("Scoring your answer needs an AI key. Add one for free in **Settings** to enable this feature.")
        else:
            with st.spinner("Evaluating your answer..."):
                result = ai.evaluate_interview_answer(current["question"], answer, job, profile, current["category"])
            if result.get("error"):
                st.error(result["error"])
            else:
                db.add_interview_qa(app_id, job_id, current["category"], current["question"], answer,
                                     result["score"], result)
                st.session_state[FEEDBACK_KEY] = result
                st.rerun()
else:
    ui.ai_badge()
    st.markdown(f"### Score: {feedback['score']}/10")
    ui.progress_bar(round(feedback["score"] * 10), "")
    st.markdown(f"**✅ What was good:** {feedback.get('what_was_good','')}")
    st.markdown(f"**⚠️ What was missing:** {feedback.get('what_was_missing','')}")
    st.markdown(f"**💡 How to improve:** {feedback.get('how_to_improve','')}")
    st.markdown(f"**🧱 Suggested structure:** {feedback.get('better_answer_structure','')}")
    if feedback.get("follow_up_question"):
        st.info(f"🔁 Likely follow-up: {feedback['follow_up_question']}")

    if st.button("➡️ Next Question", type="primary"):
        st.session_state[IDX_KEY] += 1
        st.session_state.pop(FEEDBACK_KEY, None)
        st.rerun()
