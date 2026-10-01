"""
Deterministic scoring logic for skill matching, experience/education fit,
reality-check factors, and application strength.

DESIGN PRINCIPLE: every percentage or point value shown to the user is
computed here with plain arithmetic, not invented by the LLM. The model is
used elsewhere (ai_service.py) only for the parts that genuinely need
language understanding: reading a project description, writing a roadmap,
evaluating an interview answer, spotting vague wording in a job post.
This keeps scores reproducible and makes "explain how it was calculated"
actually true.
"""

import re
from datetime import datetime, date

# ---------------------------------------------------------------------------
# Skill normalization
# ---------------------------------------------------------------------------

_ALIASES = {
    "js": "javascript",
    "ts": "typescript",
    "node": "node.js",
    "nodejs": "node.js",
    "reactjs": "react",
    "react.js": "react",
    "postgres": "postgresql",
    "postgressql": "postgresql",
    "py": "python",
    "k8s": "kubernetes",
    "ml": "machine learning",
    "ai": "artificial intelligence",
    "html5": "html",
    "css3": "css",
    "rest api": "rest apis",
    "restful apis": "rest apis",
    "sql server": "sql",
    "mssql": "sql",
    "amazon web services": "aws",
    "google cloud platform": "gcp",
    "ci/cd pipelines": "ci/cd",
}


def normalize_skill(skill: str) -> str:
    if not skill:
        return ""
    s = skill.strip().lower()
    s = re.sub(r"[^\w\s./+#-]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return _ALIASES.get(s, s)


def _is_partial_match(a: str, b: str) -> bool:
    """True if two normalized skill strings are related but not identical."""
    if a == b:
        return False
    if len(a) < 3 or len(b) < 3:
        return False
    return a in b or b in a


# ---------------------------------------------------------------------------
# Skill matching
# ---------------------------------------------------------------------------

def compute_skill_match(user_skills: list, required_skills: list, preferred_skills: list) -> dict:
    """
    Returns a fully explainable breakdown of how the user's skills line up
    against a job's required and preferred skills.
    """
    user_norm = {normalize_skill(s): s for s in (user_skills or []) if s}
    user_keys = set(user_norm.keys())

    def classify(job_skills):
        matched, partial, missing = [], [], []
        for raw in job_skills or []:
            norm = normalize_skill(raw)
            if norm in user_keys:
                matched.append(raw)
            else:
                found_partial = any(_is_partial_match(norm, uk) for uk in user_keys)
                (partial if found_partial else missing).append(raw)
        return matched, partial, missing

    req_matched, req_partial, req_missing = classify(required_skills)
    pref_matched, pref_partial, pref_missing = classify(preferred_skills)

    total_required = len(required_skills or [])
    if total_required > 0:
        weighted = len(req_matched) * 1.0 + len(req_partial) * 0.5
        skill_pct = round((weighted / total_required) * 100)
        calc_note = (
            f"{len(req_matched)} of {total_required} required skills fully matched, "
            f"{len(req_partial)} partially matched (each worth half credit): "
            f"({len(req_matched)} × 1.0 + {len(req_partial)} × 0.5) / {total_required} × 100 = {skill_pct}%"
        )
    else:
        skill_pct = 100
        calc_note = "No required skills listed for this job, so skill match defaults to 100%."

    return {
        "skill_match_pct": skill_pct,
        "calculation_note": calc_note,
        "required_matched": req_matched,
        "required_partial": req_partial,
        "required_missing": req_missing,
        "preferred_matched": pref_matched,
        "preferred_partial": pref_partial,
        "preferred_missing": pref_missing,
    }


def assign_skill_priority(skill_match: dict) -> list:
    """
    Deterministic priority assignment (no AI):
      - Missing + required        -> Critical
      - Partial + required        -> Important
      - Missing + preferred       -> Nice to Have
    Returns a flat list sorted Critical -> Important -> Nice to Have.
    """
    items = []
    for skill in skill_match["required_missing"]:
        items.append({"skill": skill, "status": "Missing", "priority": "Critical", "rank": 0})
    for skill in skill_match["required_partial"]:
        items.append({"skill": skill, "status": "Partial", "priority": "Important", "rank": 1})
    for skill in skill_match["preferred_missing"]:
        items.append({"skill": skill, "status": "Missing", "priority": "Nice to Have", "rank": 2})
    items.sort(key=lambda x: x["rank"])
    return items


# ---------------------------------------------------------------------------
# Experience / education
# ---------------------------------------------------------------------------

def compute_experience_score(user_years: float, min_years: int) -> dict:
    user_years = user_years or 0
    min_years = min_years or 0
    if min_years == 0:
        pct = 100
        note = "This role lists no minimum experience requirement."
    elif user_years >= min_years:
        pct = 100
        note = f"You have {user_years} year(s) of experience, meeting the {min_years}-year requirement."
    elif user_years >= min_years * 0.5:
        pct = 60
        note = (
            f"You have {user_years} year(s) against a {min_years}-year requirement — "
            f"partial credit since you're over halfway there."
        )
    else:
        pct = max(20, round((user_years / min_years) * 100)) if min_years else 20
        note = f"You have {user_years} year(s) against a {min_years}-year requirement — a meaningful gap."
    return {"experience_pct": pct, "calculation_note": note}


_DEGREE_RANK = {
    "high school": 1, "associate": 2, "bachelor": 3, "bachelor's": 3,
    "master": 4, "master's": 4, "mba": 4, "phd": 5, "doctorate": 5,
}


def _degree_rank_from_text(text: str) -> int:
    text = (text or "").lower()
    best = 0
    for key, rank in _DEGREE_RANK.items():
        if key in text:
            best = max(best, rank)
    return best


def compute_education_score(user_education: list, requirement_text: str) -> dict:
    req_rank = _degree_rank_from_text(requirement_text)
    if req_rank == 0:
        return {"education_pct": 100, "calculation_note": "No specific degree level required for this role."}

    user_rank = 0
    for edu in user_education or []:
        combined = f"{edu.get('degree', '')} {edu.get('field', '')}"
        user_rank = max(user_rank, _degree_rank_from_text(combined))

    if user_rank >= req_rank:
        pct = 100
        note = "Your highest listed education meets or exceeds the stated requirement."
    elif user_rank == 0:
        pct = 40
        note = "No matching education level detected in your profile against the stated requirement."
    else:
        pct = 70
        note = "Your education is close to, but below, the stated requirement level."
    return {"education_pct": pct, "calculation_note": note}


def compute_overall_match(skill_pct, experience_pct, education_pct, project_pct,
                           weights=(0.35, 0.20, 0.15, 0.30)) -> dict:
    w_skill, w_exp, w_edu, w_proj = weights
    overall = round(
        skill_pct * w_skill + experience_pct * w_exp + education_pct * w_edu + project_pct * w_proj
    )
    note = (
        f"Overall = Skills({skill_pct}%×{int(w_skill*100)}%) + Experience({experience_pct}%×{int(w_exp*100)}%) "
        f"+ Education({education_pct}%×{int(w_edu*100)}%) + Projects({project_pct}%×{int(w_proj*100)}%) = {overall}%"
    )
    return {"overall_match_pct": overall, "calculation_note": note}


# ---------------------------------------------------------------------------
# Reality Check factors
# ---------------------------------------------------------------------------

def compute_reality_factors(profile: dict, job: dict, skill_match: dict) -> dict:
    exp = compute_experience_score(profile.get("estimated_years_experience", 0), job.get("min_experience_years", 0))
    edu = compute_education_score(profile.get("education", []), job.get("education_requirement", ""))

    seniority_gap = "None"
    exp_level = (job.get("experience_level") or "").lower()
    user_level = (profile.get("career_level") or "").lower()
    if "senior" in exp_level and user_level in ("student", "entry-level", "entry level", "internship"):
        seniority_gap = "Large"
    elif "mid" in exp_level and user_level in ("student", "internship"):
        seniority_gap = "Moderate"

    weighted_score = round(
        skill_match["skill_match_pct"] * 0.40
        + exp["experience_pct"] * 0.30
        + edu["education_pct"] * 0.15
        + (60 if seniority_gap == "Large" else 85 if seniority_gap == "Moderate" else 100) * 0.15
    )

    if weighted_score >= 85:
        category = "Strong Apply"
        emoji = "🟢"
    elif weighted_score >= 70:
        category = "Apply With Preparation"
        emoji = "🟡"
    elif weighted_score >= 50:
        category = "Stretch Opportunity"
        emoji = "🟠"
    else:
        category = "Low Priority"
        emoji = "🔴"

    return {
        "weighted_score": weighted_score,
        "category": category,
        "emoji": emoji,
        "skill_pct": skill_match["skill_match_pct"],
        "experience_pct": exp["experience_pct"],
        "experience_note": exp["calculation_note"],
        "education_pct": edu["education_pct"],
        "education_note": edu["calculation_note"],
        "seniority_gap": seniority_gap,
        "calculation_note": (
            f"Weighted score = Skills(40%) + Experience(30%) + Education(15%) + Seniority fit(15%) = {weighted_score}. "
            f"Strong Apply ≥85, Apply With Preparation ≥70, Stretch Opportunity ≥50, else Low Priority."
        ),
    }


# ---------------------------------------------------------------------------
# Application Strength
# ---------------------------------------------------------------------------

def compute_application_strength(profile: dict, job: dict, skill_match: dict, project_relevance_pct: int) -> dict:
    exp = compute_experience_score(profile.get("estimated_years_experience", 0), job.get("min_experience_years", 0))
    edu = compute_education_score(profile.get("education", []), job.get("education_requirement", ""))

    location_pts = 10 if job.get("remote_status") == "Remote" else 5
    seniority_pts = 5
    exp_level = (job.get("experience_level") or "").lower()
    user_level = (profile.get("career_level") or "").lower()
    if "senior" in exp_level and user_level in ("student", "entry-level", "internship"):
        seniority_pts = 0

    skill_pts = round(skill_match["skill_match_pct"] * 0.30)
    exp_pts = round(exp["experience_pct"] * 0.20)
    edu_pts = round(edu["education_pct"] * 0.15)
    proj_pts = round((project_relevance_pct or 0) * 0.20)

    factors = [
        {"label": "Skill Match", "points": skill_pts, "max": 30},
        {"label": "Experience Match", "points": exp_pts, "max": 20},
        {"label": "Education Match", "points": edu_pts, "max": 15},
        {"label": "Project Relevance", "points": proj_pts, "max": 20},
        {"label": "Location Match", "points": location_pts, "max": 10},
        {"label": "Seniority Match", "points": seniority_pts, "max": 5},
    ]
    score = sum(f["points"] for f in factors)
    score = max(0, min(100, score))

    # Deterministic improvement estimates based on what's actually missing.
    improvements = []
    n_required = max(1, len(job.get("required_skills", [])))
    per_skill_value = round(30 / n_required)
    for item in skill_match["required_missing"][:3]:
        improvements.append({
            "action": f"Learn {item}",
            "estimated_points": min(per_skill_value, 30 - skill_pts) if per_skill_value > 0 else 3,
        })
    if project_relevance_pct is not None and project_relevance_pct < 70:
        improvements.append({
            "action": "Add or highlight a project directly relevant to this role",
            "estimated_points": min(8, 20 - proj_pts),
        })
    if edu_pts < 15:
        improvements.append({
            "action": "Clarify or complete education credentials relevant to this role",
            "estimated_points": 15 - edu_pts,
        })
    improvements = [i for i in improvements if i["estimated_points"] > 0]

    return {
        "score": score,
        "factors": factors,
        "improvements": improvements,
        "calculation_note": (
            "Score = Skill Match (30 max) + Experience (20 max) + Education (15 max) + "
            "Project Relevance (20 max) + Location (10 max) + Seniority (5 max)."
        ),
    }


# ---------------------------------------------------------------------------
# Misc formatting helpers
# ---------------------------------------------------------------------------

STATUS_COLORS = {
    "Saved": "#94A3B8",
    "Applied": "#60A5FA",
    "Interview": "#FBBF24",
    "Offer": "#34D399",
    "Rejected": "#F87171",
    "Withdrawn": "#A78BFA",
}

PRIORITY_COLORS = {
    "Critical": "#F87171",
    "Important": "#FBBF24",
    "Nice to Have": "#34D399",
}

PRIORITY_EMOJI = {
    "Critical": "🔴",
    "Important": "🟠",
    "Nice to Have": "🟢",
}


def today_str() -> str:
    return date.today().isoformat()


def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def clamp(value, low=0, high=100):
    return max(low, min(high, value))


def pct_bar_color(pct: int) -> str:
    if pct >= 75:
        return "#34D399"
    if pct >= 50:
        return "#FBBF24"
    return "#F87171"
