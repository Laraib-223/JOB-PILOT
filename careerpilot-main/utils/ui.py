"""Shared CSS injection and small reusable UI component renderers."""

import streamlit as st

from utils.helpers import PRIORITY_COLORS, PRIORITY_EMOJI, STATUS_COLORS, pct_bar_color

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Sora:wght@600;700;800&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.stApp {
    background: radial-gradient(circle at 15% 0%, #1a1b3a 0%, #0d0e21 45%, #0a0a18 100%);
    color: #E5E7EB;
}

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0d0e21 0%, #12132b 100%);
    border-right: 1px solid rgba(139,124,246,0.15);
}
section[data-testid="stSidebar"] * { color: #E5E7EB !important; }

h1, h2, h3 { font-family: 'Sora', sans-serif !important; letter-spacing: -0.01em; }
h1 {
    background: linear-gradient(90deg, #8B7CF6, #60A5FA);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    font-weight: 800 !important;
}

.cp-card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(139,124,246,0.18);
    border-radius: 16px;
    padding: 1.25rem 1.4rem;
    backdrop-filter: blur(10px);
    box-shadow: 0 8px 24px rgba(0,0,0,0.3);
    margin-bottom: 1rem;
}

.cp-metric-label { font-size: 0.78rem; color: #9CA3AF; text-transform: uppercase; letter-spacing: 0.06em; font-weight: 600; }
.cp-metric-value { font-size: 1.9rem; font-weight: 800; font-family: 'Sora', sans-serif; color: #F3F4F6; }
.cp-metric-sub { font-size: 0.8rem; color: #A5B4FC; }

.cp-pill { display: inline-block; padding: 0.2rem 0.7rem; border-radius: 999px; font-size: 0.75rem; font-weight: 700; color: #0a0a18; }
.cp-badge { display: inline-flex; align-items: center; gap: 6px; font-size: 0.72rem; font-weight: 700; padding: 2px 10px; border-radius: 999px; margin-bottom: 0.4rem; }
.cp-badge-ai { color: #A78BFA; background: rgba(167,139,250,0.12); border: 1px solid rgba(167,139,250,0.3); }
.cp-badge-demo { color: #FBBF24; background: rgba(251,191,36,0.12); border: 1px solid rgba(251,191,36,0.3); }

.cp-progress-track { background: rgba(255,255,255,0.08); border-radius: 999px; height: 10px; overflow: hidden; margin: 4px 0 10px 0; }
.cp-progress-fill { height: 100%; border-radius: 999px; }

.stButton > button, .stDownloadButton > button {
    border-radius: 10px; border: 1px solid rgba(139,124,246,0.3);
    background: linear-gradient(135deg, rgba(139,124,246,0.18), rgba(96,165,250,0.14));
    color: #F3F4F6; font-weight: 600; transition: all 0.15s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover {
    border-color: #8B7CF6; transform: translateY(-1px); box-shadow: 0 6px 16px rgba(139,124,246,0.3);
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #8B7CF6, #60A5FA); color: #0a0a18; border: none;
}

.stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div,
.stDateInput input, .stNumberInput input, .stMultiSelect div[data-baseweb="select"] > div {
    background-color: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(139,124,246,0.22) !important;
    border-radius: 10px !important; color: #F3F4F6 !important;
}

.stTabs [data-baseweb="tab-list"] { gap: 6px; }
.stTabs [data-baseweb="tab"] { background: rgba(255,255,255,0.04); border-radius: 10px 10px 0 0; padding: 8px 16px; color: #9CA3AF; }
.stTabs [aria-selected="true"] { background: rgba(139,124,246,0.18) !important; color: #F3F4F6 !important; }

[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; border: 1px solid rgba(139,124,246,0.18); }
hr { border-color: rgba(139,124,246,0.18); }

.cp-empty-state { text-align: center; padding: 3rem 1rem; color: #9CA3AF; }
.cp-empty-state .emoji { font-size: 2.6rem; margin-bottom: 0.5rem; }

.cp-kanban-col { min-height: 200px; }
.cp-job-card { border-left: 3px solid #8B7CF6; }
</style>
"""


def inject_css():
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def metric_card(label: str, value: str, sub: str = ""):
    sub_html = f'<div class="cp-metric-sub">{sub}</div>' if sub else ""
    st.markdown(
        f'<div class="cp-card"><div class="cp-metric-label">{label}</div>'
        f'<div class="cp-metric-value">{value}</div>{sub_html}</div>',
        unsafe_allow_html=True,
    )


def status_pill(status: str) -> str:
    color = STATUS_COLORS.get(status, "#60A5FA")
    return f'<span class="cp-pill" style="background:{color};">{status}</span>'


def priority_pill(priority: str) -> str:
    color = PRIORITY_COLORS.get(priority, "#60A5FA")
    emoji = PRIORITY_EMOJI.get(priority, "")
    return f'<span class="cp-pill" style="background:{color};">{emoji} {priority}</span>'


def ai_badge():
    st.markdown('<span class="cp-badge cp-badge-ai">✨ AI Generated</span>', unsafe_allow_html=True)


def demo_badge():
    st.markdown('<span class="cp-badge cp-badge-demo">🧪 Demo Job Data</span>', unsafe_allow_html=True)


def progress_bar(pct: int, label: str = ""):
    pct = max(0, min(100, pct))
    color = pct_bar_color(pct)
    label_html = f'<div style="display:flex; justify-content:space-between; font-size:0.85rem; color:#D1D5DB;"><span>{label}</span><span>{pct}%</span></div>' if label else ""
    st.markdown(
        f'{label_html}<div class="cp-progress-track"><div class="cp-progress-fill" '
        f'style="width:{pct}%; background:{color};"></div></div>',
        unsafe_allow_html=True,
    )


def empty_state(emoji: str, title: str, subtitle: str):
    st.markdown(
        f'<div class="cp-empty-state"><div class="emoji">{emoji}</div>'
        f'<div style="font-size:1.1rem; font-weight:700; color:#E5E7EB;">{title}</div>'
        f'<div>{subtitle}</div></div>',
        unsafe_allow_html=True,
    )


def ai_error_box(message: str):
    st.warning(f"🔑 {message}", icon="🔑")


def require_profile(profile) -> bool:
    """Returns True if a profile exists; otherwise renders guidance and returns False."""
    if profile and profile.get("skills"):
        return True
    empty_state(
        "📄", "No profile yet",
        "Go to **My CV** to upload your resume or load the demo profile first.",
    )
    return False


def require_selected_job(job) -> bool:
    if job:
        return True
    empty_state(
        "🔎", "No job selected",
        "Go to **Find Jobs** and pick a job to analyze first.",
    )
    return False


def job_selector_widget(key_suffix: str = ""):
    """
    Renders a job-picker dropdown pre-filled with the currently selected
    job (from session_state), so analysis pages work whether the user
    arrived via a "Job Match" button on Find Jobs, or navigated here
    directly. Returns the selected job dict, or None.
    """
    from services import job_service as js

    jobs = js.load_jobs()
    labels = {f"{j['company']} — {j['title']}": j["id"] for j in jobs}
    label_list = list(labels.keys())

    current_id = st.session_state.get("selected_job_id")
    current_label = next((lbl for lbl, jid in labels.items() if jid == current_id), None)
    default_index = label_list.index(current_label) if current_label in label_list else 0

    chosen_label = st.selectbox(
        "Job to analyze", label_list, index=default_index if label_list else 0,
        key=f"job_selector_{key_suffix}",
    )
    chosen_id = labels.get(chosen_label)
    if chosen_id and chosen_id != current_id:
        st.session_state["selected_job_id"] = chosen_id
    return js.get_job_by_id(chosen_id) if chosen_id else None
