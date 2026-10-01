"""
SQLite persistence layer for CareerPilot AI.

Three tables:
  - profile:        single-row user profile (structured CV data)
  - applications:   tracked applications, referencing demo job IDs
  - interview_qa:   interview simulator question/answer/score history

All JSON-shaped fields (skills, education, etc.) are stored as JSON text
and decoded on read, so callers always work with plain Python objects.
"""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "careerpilot.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    name TEXT,
    raw_text TEXT,
    career_level TEXT,
    estimated_years_experience REAL DEFAULT 0,
    skills_json TEXT DEFAULT '[]',
    education_json TEXT DEFAULT '[]',
    experience_json TEXT DEFAULT '[]',
    projects_json TEXT DEFAULT '[]',
    certifications_json TEXT DEFAULT '[]',
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    job_title TEXT NOT NULL,
    company TEXT NOT NULL,
    job_url TEXT,
    date_saved TEXT,
    date_applied TEXT,
    status TEXT NOT NULL DEFAULT 'Saved',
    match_score INTEGER,
    match_json TEXT,
    skill_gap_json TEXT,
    reality_check_json TEXT,
    application_score INTEGER,
    application_score_json TEXT,
    interview_readiness_json TEXT,
    notes TEXT,
    rejection_reason TEXT,
    recruiter_feedback TEXT,
    interview_feedback TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS interview_qa (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER,
    job_id TEXT,
    category TEXT,
    question TEXT NOT NULL,
    user_answer TEXT,
    ai_score REAL,
    ai_feedback_json TEXT,
    created_at TEXT NOT NULL
);
"""


def _ensure_data_dir():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


@contextmanager
def get_connection():
    _ensure_data_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_connection() as conn:
        conn.executescript(SCHEMA)


def _now():
    return datetime.utcnow().isoformat(timespec="seconds")


def _loads(text, default):
    if not text:
        return default
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

def save_profile(profile: dict):
    now = _now()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO profile
               (id, name, raw_text, career_level, estimated_years_experience,
                skills_json, education_json, experience_json, projects_json,
                certifications_json, updated_at)
               VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 name=excluded.name, raw_text=excluded.raw_text,
                 career_level=excluded.career_level,
                 estimated_years_experience=excluded.estimated_years_experience,
                 skills_json=excluded.skills_json, education_json=excluded.education_json,
                 experience_json=excluded.experience_json, projects_json=excluded.projects_json,
                 certifications_json=excluded.certifications_json, updated_at=excluded.updated_at
            """,
            (
                profile.get("name"),
                profile.get("raw_text", ""),
                profile.get("career_level"),
                profile.get("estimated_years_experience", 0),
                json.dumps(profile.get("skills", [])),
                json.dumps(profile.get("education", [])),
                json.dumps(profile.get("experience", [])),
                json.dumps(profile.get("projects", [])),
                json.dumps(profile.get("certifications", [])),
                now,
            ),
        )


def get_profile() -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM profile WHERE id = 1").fetchone()
    if not row:
        return None
    return {
        "name": row["name"],
        "raw_text": row["raw_text"],
        "career_level": row["career_level"],
        "estimated_years_experience": row["estimated_years_experience"],
        "skills": _loads(row["skills_json"], []),
        "education": _loads(row["education_json"], []),
        "experience": _loads(row["experience_json"], []),
        "projects": _loads(row["projects_json"], []),
        "certifications": _loads(row["certifications_json"], []),
        "updated_at": row["updated_at"],
    }


def delete_profile():
    with get_connection() as conn:
        conn.execute("DELETE FROM profile WHERE id = 1")


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

def add_application(job: dict, status: str = "Saved") -> int:
    now = _now()
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO applications
               (job_id, job_title, company, job_url, date_saved, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (job["id"], job["title"], job["company"], job.get("application_url", ""),
             _now()[:10], status, now, now),
        )
        return cur.lastrowid


def get_application_by_job_id(job_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM applications WHERE job_id = ? ORDER BY id DESC LIMIT 1", (job_id,)
        ).fetchone()
    return _row_to_application(row) if row else None


def get_application(app_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM applications WHERE id = ?", (app_id,)).fetchone()
    return _row_to_application(row) if row else None


def get_all_applications() -> list:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM applications ORDER BY updated_at DESC").fetchall()
    return [_row_to_application(r) for r in rows]


def _row_to_application(row) -> dict:
    d = dict(row)
    d["match_json"] = _loads(d.get("match_json"), None)
    d["skill_gap_json"] = _loads(d.get("skill_gap_json"), None)
    d["reality_check_json"] = _loads(d.get("reality_check_json"), None)
    d["application_score_json"] = _loads(d.get("application_score_json"), None)
    d["interview_readiness_json"] = _loads(d.get("interview_readiness_json"), None)
    return d


def update_application(app_id: int, fields: dict):
    if not fields:
        return
    json_fields = {"match_json", "skill_gap_json", "reality_check_json",
                    "application_score_json", "interview_readiness_json"}
    set_parts, values = [], []
    for k, v in fields.items():
        if k in json_fields and not isinstance(v, str):
            v = json.dumps(v)
        set_parts.append(f"{k} = ?")
        values.append(v)
    set_parts.append("updated_at = ?")
    values.append(_now())
    values.append(app_id)
    with get_connection() as conn:
        conn.execute(f"UPDATE applications SET {', '.join(set_parts)} WHERE id = ?", values)


def delete_application(app_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM applications WHERE id = ?", (app_id,))
        conn.execute("DELETE FROM interview_qa WHERE application_id = ?", (app_id,))


def reset_all_data():
    with get_connection() as conn:
        conn.execute("DELETE FROM applications")
        conn.execute("DELETE FROM interview_qa")
        conn.execute("DELETE FROM profile")


def get_dashboard_stats() -> dict:
    apps = get_all_applications()
    total = len(apps)
    from datetime import date, timedelta
    week_ago = (date.today() - timedelta(days=7)).isoformat()

    this_week = sum(1 for a in apps if (a.get("date_applied") or a.get("date_saved") or "") >= week_ago)
    interviews = sum(1 for a in apps if a["status"] == "Interview")
    offers = sum(1 for a in apps if a["status"] == "Offer")
    rejections = sum(1 for a in apps if a["status"] == "Rejected")
    applied_or_beyond = sum(1 for a in apps if a["status"] in ("Applied", "Interview", "Offer", "Rejected"))

    interview_rate = round((interviews + offers) / applied_or_beyond * 100, 1) if applied_or_beyond else 0.0
    success_rate = round(offers / applied_or_beyond * 100, 1) if applied_or_beyond else 0.0

    scored = [a["match_score"] for a in apps if a.get("match_score") is not None]
    avg_match = round(sum(scored) / len(scored)) if scored else 0

    app_scores = [a["application_score"] for a in apps if a.get("application_score") is not None]
    avg_app_strength = round(sum(app_scores) / len(app_scores)) if app_scores else 0

    return {
        "total": total,
        "this_week": this_week,
        "interviews": interviews,
        "offers": offers,
        "rejections": rejections,
        "interview_rate": interview_rate,
        "success_rate": success_rate,
        "avg_match": avg_match,
        "avg_app_strength": avg_app_strength,
    }


# ---------------------------------------------------------------------------
# Interview Q&A
# ---------------------------------------------------------------------------

def add_interview_qa(application_id, job_id, category, question, user_answer, ai_score, ai_feedback: dict) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO interview_qa
               (application_id, job_id, category, question, user_answer, ai_score, ai_feedback_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (application_id, job_id, category, question, user_answer, ai_score,
             json.dumps(ai_feedback), _now()),
        )
        return cur.lastrowid


def get_interview_history(job_id: str = None) -> list:
    with get_connection() as conn:
        if job_id:
            rows = conn.execute(
                "SELECT * FROM interview_qa WHERE job_id = ? ORDER BY id ASC", (job_id,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM interview_qa ORDER BY id ASC").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["ai_feedback_json"] = _loads(d.get("ai_feedback_json"), {})
        out.append(d)
    return out
