"""Settings — API key status, data management, privacy notice."""

import streamlit as st

from services import ai_service as ai
from services import database as db
from services import job_service as js
from utils import ui

st.set_page_config(page_title="Settings — CareerPilot AI", page_icon="⚙️", layout="wide")
ui.inject_css()
db.init_db()

st.title("⚙️ Settings")

st.markdown("#### AI Features")
if ai.api_key_configured():
    st.success("You're all set! AI-powered features are enabled.")
else:
    st.warning(
        "AI features aren't turned on yet. Get a free key from "
        "[openrouter.ai/keys](https://openrouter.ai/keys) (no card needed) "
        "and add it to the app."
    )

with st.expander("How do I add my key?"):
    st.markdown(
        """
1. Create a free account and API key at [openrouter.ai/keys](https://openrouter.ai/keys).
2. Open the `.streamlit/secrets.toml` file in the project folder and paste it in:

    ```toml
    OPENROUTER_API_KEY = "your-key-here"
    ```

3. Restart the app.

If you're hosting this on Streamlit Community Cloud, add the same key under
*App settings → Secrets* instead of editing a local file.

*Currently using a free model, which has usage limits. If AI features stop working*
*for a bit, it's likely a temporary limit — just wait a minute and try again.*
    """
    )

st.divider()
st.markdown("#### Data")
profile = db.get_profile()
applications = db.get_all_applications()
st.caption(f"Profile loaded: {'Yes — ' + profile['name'] if profile and profile.get('name') else 'No'}")
st.caption(f"Applications tracked: {len(applications)}")
st.caption(f"Job dataset: {len(js.load_jobs())} demo jobs ({'demo data' if js.is_demo_data() else 'live data'})")

c1, c2 = st.columns(2)
with c1:
    if st.button("🗑️ Clear Profile Only"):
        db.delete_profile()
        st.success("Profile cleared.")
        st.rerun()
with c2:
    if st.button("🧨 Reset All Data (profile + applications + interviews)"):
        db.reset_all_data()
        st.success("All local data cleared.")
        st.rerun()

st.divider()
st.markdown("#### 🔒 Privacy")
st.info(
    "Your CV is used to generate career recommendations. Avoid uploading sensitive information "
    "(SSNs, ID numbers, financial details) that isn't necessary for your job search. "
    "CareerPilot AI never asks for passwords or payment information. Everything is stored on "
    "your own computer — nothing is shared except the text sent to the AI when you use an "
    "AI-powered feature."
)

st.divider()
st.markdown("#### About")
st.caption(
    "**CareerPilot AI** — your all-in-one career toolkit. Skill Gap Detective, Job Reality "
    "Checker, Interview Twin, Application Success Predictor, and Rejection Analyzer all connect "
    "through your profile and application history, combining AI insight with clear, explainable "
    "scoring."
)
