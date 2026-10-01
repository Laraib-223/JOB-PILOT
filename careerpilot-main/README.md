# 🧭 CareerPilot AI

**Don't just find jobs. Find the right job — and become ready for it.**

An AI career agent, not a job board. Upload a CV once, and CareerPilot AI
connects the whole job-search loop — matching, skill gaps, reality checks,
interview practice, tracking, and rejection analysis — into one system
where each module feeds the next.


## Why it's different

| Feature | What it does |
|---|---|
| 🧩 **Skill Gap Detective** | Matched / partial / missing skills vs. a job, with Critical / Important / Nice-to-Have priorities and an AI-generated learning roadmap. |
| 🚦 **Job Reality Checker** | "Should I actually apply?" — Strong Apply / Apply With Preparation / Stretch Opportunity / Low Priority, with reasons and cautious, evidence-based concern flags (never accusations). |
| 🎤 **Interview Twin** | A personalized mock interview generated from *your* CV and *this* job — asks about your named projects, your missing skills, this job's actual responsibilities. Scores each answer live and produces a 4-part readiness score. |
| 📊 **Application Success Predictor** | An explainable point-by-point application-strength score (not a guaranteed hire probability), with concrete "what would increase your score" suggestions. |
| 🔍 **Rejection Analyzer** | Finds recurring patterns across your rejected applications ("React missing in 4/5 jobs") and names your single biggest improvement opportunity. |

These modules talk to each other: a skill that shows up as a gap in
**Skill Gap Detective** lowers match scores in **Job Match**, gets
prioritized in the **Career Roadmap**, gets probed in **Interview Twin**,
and gets flagged again if it shows up as a **Rejection Analyzer** pattern.

## How scoring actually works

Every percentage or point value shown in the app is computed with plain,
inspectable arithmetic in `utils/helpers.py` — not invented by the LLM.
The LLM is used only where language understanding is actually needed:
reading a project description for relevance, writing a learning roadmap,
evaluating a free-text interview answer, or spotting genuinely vague
wording in a job post. This makes every score reproducible and means
"here's how this was calculated" is always a true statement, shown
directly under each score in the UI.

## Tech Stack

- Python + Streamlit (UI, native multi-page navigation via `pages/`)
- OpenRouter (free-tier open models, OpenAI-compatible API via the `openai` SDK) — isolated entirely in `services/ai_service.py`
- SQLite (`services/database.py`) — profile, applications, interview history
- Pandas + Plotly — Application Tracker dashboard
- pypdf / python-docx — CV file parsing

## Project Structure

```
careerpilot/
├── app.py                          # Career Dashboard (home page)
├── requirements.txt
├── .streamlit/
│   ├── config.toml                 # Dark theme
│   └── secrets.toml.example        # Copy to secrets.toml and add your key
├── data/
│   └── demo_jobs.json              # 20 demo jobs, 8 categories — clearly labeled as demo data
├── pages/
│   ├── 1_📄_My_CV.py                # Upload/parse CV, AI extraction, editable profile
│   ├── 2_🔎_Find_Jobs.py            # Search/filter demo jobs, quick match %, save/apply
│   ├── 3_🎯_Job_Match.py            # Full visual match report (skills/experience/education/projects)
│   ├── 4_🧩_Skill_Gap_Detective.py  # Priority-ranked gaps + AI learning roadmap
│   ├── 5_🚦_Job_Reality_Checker.py  # Apply / Prepare / Stretch / Low-priority verdict
│   ├── 6_📊_Application_Predictor.py# Explainable application strength score
│   ├── 7_🎤_Interview_Twin.py       # Interactive personalized mock interview
│   ├── 8_📋_Application_Tracker.py  # Kanban board + Plotly stats (SQLite-backed)
│   ├── 9_🔍_Rejection_Analyzer.py   # Pattern detection across rejections
│   ├── 10_🗺_Career_Roadmap.py      # Now / Next / Then / Finally, updates with your data
│   ├── 11_📑_Job_Comparison.py      # Compare up to 3 jobs + AI prioritization call
│   └── 12_⚙️_Settings.py            # API key status, data reset, privacy notice
├── services/
│   ├── ai_service.py                # All LLM calls (10 functions, see below)
│   ├── job_service.py               # Job data access — swap in a real API here later
│   ├── cv_service.py                # File parsing + demo profile
│   └── database.py                  # SQLite layer
└── utils/
    ├── helpers.py                   # Deterministic scoring engine
    └── ui.py                        # Shared CSS + components
```

### AI functions (`services/ai_service.py`)

`analyze_cv`, `match_job`, `detect_skill_gap`, `reality_check`,
`predict_application_strength`, `generate_interview`,
`evaluate_interview_answer`, `analyze_rejections`,
`generate_career_roadmap`, `generate_next_action`, plus
`recommend_job_priority` for Job Comparison.

Every function returns a dict. On any failure (missing key, API error,
malformed JSON) it returns `{"error": "..."}` instead of raising, and
every page checks for that key and shows a clear message — the app never
crashes because one AI call failed.

## Setup

### 1. Install

```bash
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure your API key 

**Option A — Streamlit secrets (recommended for local dev):**

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# edit .streamlit/secrets.toml and paste your real key
```

**Option B — Environment variable:**

```bash
export OPENROUTER_API_KEY="sk-or-v1-..."     # macOS/Linux
setx OPENROUTER_API_KEY "sk-or-v1-..."       # Windows
```

### 3. Run

```bash
streamlit run app.py
```

The app works without an API key for browsing jobs, tracking
applications, and viewing quick rule-based skill match % — but CV
analysis, full Job Match, Skill Gap roadmap, Reality Check reasoning,
Interview Twin, Rejection Analyzer, Career Roadmap, and Job Comparison
all need the LLM and will show a clear setup prompt until a key is added.

## Deploying to Streamlit Community Cloud

1. Push this repo to GitHub (`.gitignore` already excludes secrets and the local DB).
2. On [share.streamlit.io](https://share.streamlit.io), create a new app pointing at `app.py`.
3. Under **App settings → Secrets**, add:
   ```toml
   OPENROUTER_API_KEY = "sk-or-v1-..."
   ```
4. Deploy. Note: Streamlit Cloud's filesystem is ephemeral across
   redeploys/restarts, so the SQLite data resets then — `services/database.py`
   is a small, isolated module specifically so it's easy to swap in a
   hosted database for a persistent production deployment.


## External APIs required

- **OpenRouter** (`OPENROUTER_API_KEY`) — the only external dependency.
  Free-tier models work; get a key at https://openrouter.ai/keys (no card
  required). Override the model with `OPENROUTER_MODEL` — free model IDs on
  OpenRouter change over time, see https://openrouter.ai/models?max_price=0.
  Free models are rate-limited (roughly 20 requests/minute plus a daily cap). No job-board API is used; `services/job_service.py` is
  built so a real one can be plugged in later without touching any page.

## Privacy

Your CV is used only to generate career recommendations within this app.
Avoid uploading sensitive information (SSNs, ID numbers, financial
details) that isn't necessary for your job search. The app never asks for
passwords or payment information. All data lives locally in SQLite;
nothing leaves the machine except the text sent to OpenRouter (and on to
the selected model provider) for analysis.
