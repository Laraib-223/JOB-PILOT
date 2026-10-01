"""My CV — upload/parse a resume, run AI extraction, review and edit the profile."""

import streamlit as st

from services import ai_service as ai
from services import cv_service as cs
from services import database as db
from utils import ui

st.set_page_config(page_title="My CV — CareerPilot AI", page_icon="📄", layout="wide")
ui.inject_css()
db.init_db()

st.title("📄 My CV")
st.caption("Upload your resume, or load the demo profile, to power every other feature in the app.")
st.caption(
    "🔒 Your CV is used only to generate career recommendations. Avoid uploading sensitive "
    "information (SSNs, ID numbers, etc.) that isn't necessary for your job search."
)

profile = db.get_profile()

tab_upload, tab_profile = st.tabs(["📤 Upload / Analyze", "👤 Profile Summary"])

with tab_upload:
    col1, col2 = st.columns([2, 1])
    with col1:
        uploaded = st.file_uploader("Upload your CV", type=["pdf", "docx", "txt"])
        pasted_text = st.text_area(
            "...or paste your CV text directly",
            height=200,
            placeholder="Paste your resume text here if you'd rather not upload a file.",
        )
    with col2:
        st.markdown("**Or, for a quick demo:**")
        if st.button("🧪 Load Demo Profile", use_container_width=True):
            cs.load_demo_profile()
            st.success("Demo profile loaded — see the Profile Summary tab.")
            st.rerun()
        st.caption("Loads a sample CS-student profile (JavaScript, Node.js, PostgreSQL — missing React & Docker) so you can demo the full flow immediately.")

    if st.button("🔍 Analyze CV", type="primary", disabled=not (uploaded or pasted_text.strip())):
        raw_text = None
        if uploaded:
            try:
                raw_text = cs.extract_text_from_upload(uploaded)
            except cs.CVParsingError as e:
                st.error(str(e))
        else:
            raw_text = pasted_text

        if raw_text:
            if not ai.api_key_configured():
                ui.ai_error_box("CV analysis needs an AI key. Add one for free in **Settings** to enable this feature.")
            else:
                with st.spinner("Extracting skills, education, projects, and experience..."):
                    result = ai.analyze_cv(raw_text)
                if result.get("error"):
                    st.error(result["error"])
                else:
                    db.save_profile(result)
                    st.success("CV analyzed and profile saved! See the Profile Summary tab.")
                    st.rerun()

with tab_profile:
    profile = db.get_profile()
    if not profile:
        ui.empty_state("📄", "No profile yet", "Upload a CV or load the demo profile in the Upload tab.")
    else:
        st.markdown(f"### {profile.get('name') or 'Unnamed Profile'}")
        st.markdown(f"**Career Level:** {profile.get('career_level') or 'Not specified'} · "
                    f"**Est. Experience:** {profile.get('estimated_years_experience', 0)} year(s)")

        with st.form("edit_profile_form"):
            st.markdown("#### Technical Skills")
            skills_text = st.text_area(
                "Comma-separated", value=", ".join(profile.get("skills", [])), height=80,
            )

            st.markdown("#### Education")
            edu_rows = profile.get("education", []) or [{}]
            edu_text = st.text_area(
                "One per line: Degree | Field | Institution | Year", height=100,
                value="\n".join(
                    f"{e.get('degree','')} | {e.get('field','')} | {e.get('institution','')} | {e.get('year','')}"
                    for e in edu_rows
                ),
            )

            st.markdown("#### Experience")
            exp_rows = profile.get("experience", []) or [{}]
            exp_text = st.text_area(
                "One per line: Title | Company | Duration | Description", height=100,
                value="\n".join(
                    f"{e.get('title','')} | {e.get('company','')} | {e.get('duration','')} | {e.get('description','')}"
                    for e in exp_rows
                ),
            )

            st.markdown("#### Projects")
            proj_rows = profile.get("projects", []) or [{}]
            proj_text = st.text_area(
                "One per line: Name | Description | Tech1,Tech2,...", height=100,
                value="\n".join(
                    f"{p.get('name','')} | {p.get('description','')} | {','.join(p.get('technologies', []))}"
                    for p in proj_rows
                ),
            )

            st.markdown("#### Certifications")
            certs_text = st.text_area(
                "Comma-separated", value=", ".join(profile.get("certifications", [])), height=60,
            )

            career_level = st.selectbox(
                "Career Level",
                ["Student", "Internship", "Entry-Level", "Mid-Level", "Senior", "Not Specified"],
                index=["Student", "Internship", "Entry-Level", "Mid-Level", "Senior", "Not Specified"].index(
                    profile.get("career_level")
                ) if profile.get("career_level") in ["Student", "Internship", "Entry-Level", "Mid-Level", "Senior", "Not Specified"] else 0,
            )
            years_exp = st.number_input(
                "Estimated Years of Experience", min_value=0.0, max_value=50.0, step=0.5,
                value=float(profile.get("estimated_years_experience", 0) or 0),
            )

            submitted = st.form_submit_button("💾 Save Changes", type="primary")

            if submitted:
                def parse_pipe_rows(text, fields):
                    rows = []
                    for line in text.strip().split("\n"):
                        if not line.strip():
                            continue
                        parts = [p.strip() for p in line.split("|")]
                        parts += [""] * (len(fields) - len(parts))
                        rows.append(dict(zip(fields, parts)))
                    return rows

                updated = {
                    "name": profile.get("name"),
                    "raw_text": profile.get("raw_text", ""),
                    "career_level": career_level,
                    "estimated_years_experience": years_exp,
                    "skills": [s.strip() for s in skills_text.split(",") if s.strip()],
                    "education": parse_pipe_rows(edu_text, ["degree", "field", "institution", "year"]),
                    "experience": parse_pipe_rows(exp_text, ["title", "company", "duration", "description"]),
                    "projects": [
                        {**row, "technologies": [t.strip() for t in row.get("technologies", "").split(",") if t.strip()]}
                        for row in parse_pipe_rows(proj_text, ["name", "description", "technologies"])
                    ],
                    "certifications": [c.strip() for c in certs_text.split(",") if c.strip()],
                }
                db.save_profile(updated)
                st.success("Profile updated.")
                st.rerun()

        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("##### 🧩 Skills")
            st.write(", ".join(profile.get("skills", [])) or "—")
            st.markdown("##### 🎓 Education")
            for e in profile.get("education", []):
                st.markdown(f"- {e.get('degree','')} in {e.get('field','')}, {e.get('institution','')} ({e.get('year','')})")
        with c2:
            st.markdown("##### 💼 Experience")
            for e in profile.get("experience", []):
                st.markdown(f"- **{e.get('title','')}** at {e.get('company','')} ({e.get('duration','')})")
                st.caption(e.get("description", ""))
            st.markdown("##### 🚀 Projects")
            for p in profile.get("projects", []):
                st.markdown(f"- **{p.get('name','')}** — {', '.join(p.get('technologies', []))}")
                st.caption(p.get("description", ""))

        if profile.get("certifications"):
            st.markdown("##### 📜 Certifications")
            st.write(", ".join(profile.get("certifications", [])))

        st.divider()
        if st.button("🗑️ Clear Profile", type="secondary"):
            db.delete_profile()
            st.success("Profile cleared.")
            st.rerun()
