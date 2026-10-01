"""
All LLM interaction for CareerPilot AI lives here, matching the
required function set: analyze_cv, match_job, detect_skill_gap,
reality_check, predict_application_strength, generate_interview,
evaluate_interview_answer, analyze_rejections, generate_career_roadmap,
generate_next_action.

The model is served through OpenRouter, which exposes an OpenAI-compatible
API — so this module uses the `openai` SDK pointed at OpenRouter's base URL.
The default model is a free-tier one; override it with OPENROUTER_MODEL in
.streamlit/secrets.toml or the environment (free model IDs on OpenRouter
come and go, so this is the one knob you may need to turn).

Design principle: numeric scores that need to be reproducible and
explainable are computed deterministically in utils/helpers.py. The model is
called for the parts that genuinely require language understanding —
reading project descriptions, writing roadmaps, evaluating free-text
interview answers, spotting vague wording in a job post. Every function
degrades gracefully: if the API key is missing or a call fails, it
returns a dict with an "error" key instead of raising, so the UI can
show a clear message instead of crashing.
"""

import json
import os
import re
import sys
import time

import openai
import streamlit as st

from utils import helpers as h

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Free-tier default. Picked for being fast (a few seconds, not the 60-90s a
# large free model can take under load) while still following the JSON
# schemas reliably. OpenRouter's free lineup changes often — if this model
# ever 404s as "unavailable for free", check https://openrouter.ai/models?max_price=0
# and swap via the OPENROUTER_MODEL secret / env var, e.g.
#   "nex-agi/nex-n2.5-pro:free"       (slower, ~20s, slightly stronger)
#   "liquid/lfm-2.5-2.6b:free"        (fast, smaller model)
DEFAULT_MODEL = "nex-agi/nex-n2.5-mini:free"

# Optional, used by OpenRouter for app attribution on their leaderboards.
APP_URL = "https://github.com/your-username/careerpilot-ai"
APP_TITLE = "CareerPilot AI"


# ---------------------------------------------------------------------------
# Client / key handling
# ---------------------------------------------------------------------------

def _setting(name: str):
    """Read a value from Streamlit secrets, falling back to the environment."""
    try:
        if name in st.secrets:
            value = st.secrets[name]
            if value:
                return value
    except Exception:
        pass
    return os.environ.get(name)


def get_api_key():
    return _setting("OPENROUTER_API_KEY")


def get_model() -> str:
    return _setting("OPENROUTER_MODEL") or DEFAULT_MODEL


def api_key_configured() -> bool:
    return bool(get_api_key())


def _get_client():
    key = get_api_key()
    if not key:
        return None
    return openai.OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=key,
        default_headers={"HTTP-Referer": APP_URL, "X-Title": APP_TITLE},
    )


def _extract_json(text: str):
    text = text.strip()
    # Some free models (DeepSeek R1 and friends) emit a reasoning block first.
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
    if match:
        text = match.group(0)
    return json.loads(text)


def _log_technical_error(kind: str, detail) -> None:
    """
    Logs the real, technical failure to the console for whoever is running
    the app — never shown in the UI. Free-tier providers occasionally return
    vendor-specific error payloads (status codes, upstream provider names)
    that are meaningless and alarming to an end user; those stay here.
    """
    print(f"[ai_service] AI call failed ({kind}): {detail}", file=sys.stderr)


_FRIENDLY_ERRORS = {
    "busy": "The AI is getting a lot of requests right now. Please wait a moment and try again.",
    "status": "The AI service is temporarily unavailable. Please try again in a moment.",
    "connection": "Couldn't reach the AI service. Check your internet connection and try again.",
    "no_choices": "The AI is temporarily overloaded. Please try again in a moment.",
    "empty": "The AI didn't return a response. Please try again.",
    "unexpected": "Something went wrong talking to the AI. Please try again.",
}


def _should_retry(kind: str, detail) -> bool:
    """Only retry failures that a second attempt is actually likely to fix."""
    if kind in ("busy", "connection", "no_choices", "empty"):
        return True
    if kind == "status":
        code = getattr(detail, "status_code", None)
        return code is None or code >= 500 or code == 429
    return False


def _attempt_call(client, system: str, user: str, max_tokens: int):
    """One raw attempt. Returns ("ok", text) or (error_kind, detail)."""
    try:
        response = client.chat.completions.create(
            model=get_model(),
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
    except openai.RateLimitError as e:
        return "busy", e
    except openai.APIStatusError as e:
        return "status", e
    except openai.APIConnectionError as e:
        return "connection", e
    except Exception as e:
        return "unexpected", e

    if not getattr(response, "choices", None):
        return "no_choices", getattr(response, "error", None) or "no choices returned"

    text = (response.choices[0].message.content or "").strip()
    if not text:
        return "empty", "empty completion"
    return "ok", text


def _call(system: str, user: str, max_tokens: int = 2000) -> dict:
    """
    Returns {"ok": True, "text": ...} or {"ok": False, "error": ...}.
    Never raises, and never puts raw provider/vendor error details in front
    of the user — those are logged to the console instead. Automatically
    retries once on failures a retry is likely to fix (the free model pool
    being briefly overloaded is common and usually clears up immediately).
    """
    client = _get_client()
    if client is None:
        return {"ok": False, "error": (
            "AI features aren't turned on yet. Add a free API key in Settings to enable them."
        )}

    kind, detail = _attempt_call(client, system, user, max_tokens)
    if kind == "ok":
        return {"ok": True, "text": detail}

    if _should_retry(kind, detail):
        _log_technical_error(kind, detail)
        time.sleep(1.5)
        kind, detail = _attempt_call(client, system, user, max_tokens)
        if kind == "ok":
            return {"ok": True, "text": detail}

    _log_technical_error(kind, detail)
    return {"ok": False, "error": _FRIENDLY_ERRORS.get(kind, _FRIENDLY_ERRORS["unexpected"])}


def _call_json(system: str, user: str, max_tokens: int = 2000) -> dict:
    for attempt in range(2):
        result = _call(system, user, max_tokens)
        if not result["ok"]:
            return {"error": result["error"]}
        try:
            return _extract_json(result["text"])
        except (json.JSONDecodeError, AttributeError):
            if attempt == 0:
                continue
            return {"error": "The AI returned a response that couldn't be parsed. Please try again.",
                    "_raw": result["text"]}


# ---------------------------------------------------------------------------
# 1. CV Analysis
# ---------------------------------------------------------------------------

def analyze_cv(raw_text: str) -> dict:
    if not raw_text or not raw_text.strip():
        return {"error": "The CV text is empty — nothing to analyze."}

    system = (
        "You are an expert technical recruiter who extracts structured data from resumes. "
        "You always respond with strictly valid JSON matching the given schema and nothing else. "
        "Be conservative: only include information that is actually present or strongly implied "
        "in the text. Estimate total years of professional experience from listed roles/internships "
        "(education alone does not count as experience)."
    )
    user = f"""Extract structured information from this resume/CV text.

RESUME TEXT:
\"\"\"{raw_text[:12000]}\"\"\"

Respond with ONLY a JSON object with this exact schema:
{{
  "name": "<full name or null>",
  "career_level": "<one of: Student, Internship, Entry-Level, Mid-Level, Senior, Not Specified>",
  "estimated_years_experience": <number, e.g. 0.5, 1, 2.5>,
  "skills": ["<skill1>", "<skill2>", "..."],
  "education": [{{"degree": "<degree>", "field": "<field>", "institution": "<school>", "year": "<year or expected year>"}}],
  "experience": [{{"title": "<title>", "company": "<company>", "duration": "<duration>", "description": "<1-2 sentence summary>"}}],
  "projects": [{{"name": "<project name>", "description": "<1-2 sentence summary>", "technologies": ["<tech1>", "..."]}}],
  "certifications": ["<cert1>", "..."]
}}"""
    result = _call_json(system, user, max_tokens=2500)
    if "error" in result:
        return result

    result.setdefault("skills", [])
    result.setdefault("education", [])
    result.setdefault("experience", [])
    result.setdefault("projects", [])
    result.setdefault("certifications", [])
    result["raw_text"] = raw_text
    return result


# ---------------------------------------------------------------------------
# 2. Job Matching
# ---------------------------------------------------------------------------

def match_job(profile: dict, job: dict) -> dict:
    skill_match = h.compute_skill_match(profile.get("skills", []), job["required_skills"], job["preferred_skills"])
    exp = h.compute_experience_score(profile.get("estimated_years_experience", 0), job.get("min_experience_years", 0))
    edu = h.compute_education_score(profile.get("education", []), job.get("education_requirement", ""))

    system = (
        "You are a career-matching assistant. You assess how relevant a candidate's projects "
        "and experience are to a specific job, on a 0-100 scale, and explain your reasoning in "
        "plain language. You always respond with strictly valid JSON and nothing else."
    )
    user = f"""Given this candidate's projects/experience and this job, estimate a "project relevance" score.

CANDIDATE PROJECTS: {json.dumps(profile.get("projects", []))}
CANDIDATE EXPERIENCE: {json.dumps(profile.get("experience", []))}

JOB TITLE: {job['title']}
JOB DESCRIPTION: \"\"\"{job['description']}\"\"\"
REQUIRED SKILLS: {job['required_skills']}

Respond with ONLY this JSON schema:
{{
  "project_relevance_pct": <integer 0-100>,
  "project_relevance_reasoning": "<1-2 sentences citing specific projects/experience>"
}}"""
    ai_result = _call_json(system, user, max_tokens=800)

    if "error" in ai_result:
        project_pct = 50
        project_reasoning = "AI project-relevance analysis unavailable — using a neutral default."
        ai_error = ai_result["error"]
    else:
        project_pct = h.clamp(ai_result.get("project_relevance_pct", 50))
        project_reasoning = ai_result.get("project_relevance_reasoning", "")
        ai_error = None

    overall = h.compute_overall_match(skill_match["skill_match_pct"], exp["experience_pct"],
                                       edu["education_pct"], project_pct)

    return {
        "overall_match_pct": overall["overall_match_pct"],
        "overall_calculation_note": overall["calculation_note"],
        "skill_match_pct": skill_match["skill_match_pct"],
        "skill_calculation_note": skill_match["calculation_note"],
        "experience_pct": exp["experience_pct"],
        "experience_note": exp["calculation_note"],
        "education_pct": edu["education_pct"],
        "education_note": edu["calculation_note"],
        "project_relevance_pct": project_pct,
        "project_relevance_reasoning": project_reasoning,
        "required_matched": skill_match["required_matched"],
        "required_partial": skill_match["required_partial"],
        "required_missing": skill_match["required_missing"],
        "ai_warning": ai_error,
    }


# ---------------------------------------------------------------------------
# 3. Skill Gap Detective
# ---------------------------------------------------------------------------

def detect_skill_gap(profile: dict, job: dict) -> dict:
    skill_match = h.compute_skill_match(profile.get("skills", []), job["required_skills"], job["preferred_skills"])
    priorities = h.assign_skill_priority(skill_match)

    if not priorities:
        return {
            "alignment_pct": skill_match["skill_match_pct"],
            "calculation_note": skill_match["calculation_note"],
            "skill_match": skill_match,
            "priorities": [],
            "roadmap": [],
            "ai_warning": None,
        }

    system = (
        "You are a pragmatic career coach who builds concrete, time-boxed learning roadmaps "
        "for job seekers closing specific skill gaps. You always respond with strictly valid "
        "JSON matching the schema given, and nothing else."
    )
    user = f"""A candidate is missing or only partially has these skills for a "{job['title']}" role:

{json.dumps(priorities, indent=2)}

The candidate's existing skills are: {profile.get('skills', [])}

Respond with ONLY a JSON array, ordered by learning priority (Critical skills first), where each item is:
{{
  "skill": "<skill name, must match one from the list above>",
  "learning_approach": "<concrete 1-2 sentence suggestion for how to learn/practice this, given their existing skills>",
  "estimated_time": "<rough time estimate, e.g. '1-2 weeks', '2-3 days'>"
}}"""
    ai_result = _call(system, user, max_tokens=1200)
    roadmap = []
    ai_warning = None
    if ai_result["ok"]:
        try:
            roadmap = _extract_json(ai_result["text"])
            if not isinstance(roadmap, list):
                roadmap = []
        except (json.JSONDecodeError, AttributeError):
            ai_warning = "Could not parse the AI-generated roadmap; showing priority list only."
    else:
        ai_warning = ai_result["error"]

    return {
        "alignment_pct": skill_match["skill_match_pct"],
        "calculation_note": skill_match["calculation_note"],
        "skill_match": skill_match,
        "priorities": priorities,
        "roadmap": roadmap,
        "ai_warning": ai_warning,
    }


# ---------------------------------------------------------------------------
# 4. Job Reality Checker
# ---------------------------------------------------------------------------

def reality_check(profile: dict, job: dict) -> dict:
    skill_match = h.compute_skill_match(profile.get("skills", []), job["required_skills"], job["preferred_skills"])
    factors = h.compute_reality_factors(profile, job, skill_match)

    system = (
        "You are an honest, level-headed career advisor. Given computed fit factors for a "
        "candidate and job, write clear reasons for the given recommendation category, and "
        "separately flag any genuinely vague or concerning wording in the job description "
        "itself (e.g. no salary info, vague responsibilities, unrealistic scope for the level). "
        "Never claim a job or company is fraudulent — use cautious phrasing like 'Potential "
        "concern' or 'Needs verification' only when there is real textual evidence. If you see "
        "nothing concerning, return an empty concerns list. Respond with strictly valid JSON only."
    )
    user = f"""RECOMMENDATION CATEGORY (already decided, do not change): {factors['category']}

COMPUTED FACTORS:
- Skill match: {factors['skill_pct']}%
- Experience fit: {factors['experience_pct']}% ({factors['experience_note']})
- Education fit: {factors['education_pct']}% ({factors['education_note']})
- Seniority gap: {factors['seniority_gap']}
- Missing required skills: {skill_match['required_missing']}
- Partially matched skills: {skill_match['required_partial']}

JOB DESCRIPTION:
\"\"\"{job['description']}\"\"\"
Employment type: {job['employment_type']}, Experience level: {job['experience_level']}, Remote status: {job['remote_status']}
Salary listed: {job.get('salary') or 'Not listed'}

Respond with ONLY this JSON schema:
{{
  "reasons": ["<specific reason 1 grounded in the factors above>", "<reason 2>", "..."],
  "concerns": ["<Potential concern: ...>", "..."]
}}
Include 2-4 reasons. Only include concerns with real textual evidence from the job description; otherwise return an empty list."""
    ai_result = _call_json(system, user, max_tokens=1000)

    if "error" in ai_result:
        reasons = [
            f"Skill match is {factors['skill_pct']}%.",
            f"Experience fit is {factors['experience_pct']}% — {factors['experience_note']}",
            f"Education fit is {factors['education_pct']}% — {factors['education_note']}",
        ]
        concerns = []
        ai_warning = ai_result["error"]
    else:
        reasons = ai_result.get("reasons", [])
        concerns = ai_result.get("concerns", [])
        ai_warning = None

    return {**factors, "reasons": reasons, "concerns": concerns, "skill_match": skill_match, "ai_warning": ai_warning}


# ---------------------------------------------------------------------------
# 5. Application Success Predictor
# ---------------------------------------------------------------------------

def predict_application_strength(profile: dict, job: dict, match_result: dict = None) -> dict:
    skill_match = h.compute_skill_match(profile.get("skills", []), job["required_skills"], job["preferred_skills"])
    project_pct = match_result.get("project_relevance_pct") if match_result else 50
    strength = h.compute_application_strength(profile, job, skill_match, project_pct)

    system = (
        "You are a career coach writing brief, encouraging, specific improvement suggestions "
        "based on an already-computed application strength breakdown. Do not invent new point "
        "values — use the ones given. You always respond with strictly valid JSON and nothing else."
    )
    user = f"""Application strength score: {strength['score']}/100
Factor breakdown: {json.dumps(strength['factors'])}
Computed improvement opportunities: {json.dumps(strength['improvements'])}
Job: {job['title']} at {job['company']}

Respond with ONLY this JSON schema:
{{
  "summary": "<1-2 sentence honest summary of this candidate's application strength for this role>",
  "improvement_suggestions": [
    {{"action": "<action, ideally reusing one of the computed improvement actions>", "estimated_points": <integer, reuse given estimate>, "explanation": "<why this helps>"}}
  ]
}}"""
    ai_result = _call_json(system, user, max_tokens=900)

    if "error" in ai_result:
        summary = f"This application scores {strength['score']}/100 based on skill, experience, education, and project fit."
        suggestions = [{"action": i["action"], "estimated_points": i["estimated_points"],
                         "explanation": "Directly addresses a gap identified in your profile."}
                        for i in strength["improvements"]]
        ai_warning = ai_result["error"]
    else:
        summary = ai_result.get("summary", "")
        suggestions = ai_result.get("improvement_suggestions", strength["improvements"])
        ai_warning = None

    return {**strength, "summary": summary, "improvement_suggestions": suggestions, "ai_warning": ai_warning}


# ---------------------------------------------------------------------------
# 6. Interview Twin — question generation
# ---------------------------------------------------------------------------

def generate_interview(profile: dict, job: dict, skill_gap: dict = None) -> dict:
    missing_skills = skill_gap["skill_match"]["required_missing"] if skill_gap else []

    system = (
        "You are a senior hiring manager creating a personalized mock interview. Ground "
        "questions in the CANDIDATE'S ACTUAL projects, experience, and skill gaps — not "
        "generic questions. If the candidate lists a specific project, ask about it by name. "
        "You always respond with strictly valid JSON matching the schema, and nothing else."
    )
    user = f"""Build a personalized interview question set.

CANDIDATE PROFILE:
Skills: {profile.get('skills', [])}
Projects: {json.dumps(profile.get('projects', []))}
Experience: {json.dumps(profile.get('experience', []))}
Career level: {profile.get('career_level')}

JOB: {job['title']} at {job['company']}
JOB DESCRIPTION: \"\"\"{job['description']}\"\"\"
REQUIRED SKILLS: {job['required_skills']}
CANDIDATE'S MISSING SKILLS FOR THIS JOB: {missing_skills}

Respond with ONLY this JSON schema — an object with these exact category keys, each a list of question strings:
{{
  "HR": ["<2 questions>"],
  "Technical": ["<2-3 questions based on required skills the candidate DOES have>"],
  "Project-based": ["<2 questions referencing the candidate's actual named projects>"],
  "Behavioral": ["<2 questions>"],
  "Job-specific": ["<2 questions based on this specific job's responsibilities>"],
  "CV-specific": ["<1-2 questions referencing something specific from their experience/education>"],
  "Weak-area": ["<1-2 questions specifically probing the candidate's missing skills: {missing_skills}>"]
}}"""
    result = _call_json(system, user, max_tokens=2000)
    if "error" in result:
        return {"error": result["error"]}
    return result


# ---------------------------------------------------------------------------
# 7. Interview Twin — answer evaluation
# ---------------------------------------------------------------------------

def evaluate_interview_answer(question: str, user_answer: str, job: dict, profile: dict, category: str = "") -> dict:
    if not user_answer or not user_answer.strip():
        return {"error": "No answer provided to evaluate."}

    system = (
        "You are a senior hiring manager giving direct, constructive interview feedback. "
        "Be honest — do not inflate scores. You always respond with strictly valid JSON "
        "matching the schema, and nothing else."
    )
    user = f"""JOB: {job['title']} at {job['company']}
QUESTION CATEGORY: {category}
QUESTION: {question}
CANDIDATE'S ANSWER: \"\"\"{user_answer}\"\"\"

Respond with ONLY this JSON schema:
{{
  "score": <number 0-10, one decimal allowed>,
  "what_was_good": "<1-2 sentences, specific>",
  "what_was_missing": "<1-2 sentences, specific>",
  "how_to_improve": "<1-2 concrete, actionable sentences>",
  "better_answer_structure": "<a short structural suggestion, e.g. 'Use STAR: Situation, Task, Action, Result'>",
  "follow_up_question": "<a natural follow-up question an interviewer might ask next>"
}}"""
    result = _call_json(system, user, max_tokens=800)
    if "error" in result:
        return result
    result["score"] = h.clamp(result.get("score", 0), 0, 10)
    return result


# ---------------------------------------------------------------------------
# 8. Rejection Analyzer
# ---------------------------------------------------------------------------

def analyze_rejections(applications: list) -> dict:
    rejected = [a for a in applications if a.get("status") == "Rejected"]
    if len(rejected) < 2:
        return {
            "insufficient_data": True,
            "message": f"You have {len(rejected)} rejected application(s) logged. "
                       "Add rejection reasons/feedback to at least 2 rejected applications to detect patterns.",
        }

    compact = [{
        "job_title": a["job_title"], "company": a["company"],
        "rejection_reason": a.get("rejection_reason") or "Not provided",
        "recruiter_feedback": a.get("recruiter_feedback") or "Not provided",
        "missing_skills": (a.get("skill_gap_json") or {}).get("skill_match", {}).get("required_missing", []),
    } for a in rejected]

    system = (
        "You are a career strategist analyzing a job seeker's rejection history to find "
        "real, recurring patterns — not generic advice. Only report a pattern if it actually "
        "recurs across multiple applications in the data given. You always respond with "
        "strictly valid JSON matching the schema, and nothing else."
    )
    user = f"""Here are this candidate's rejected applications:

{json.dumps(compact, indent=2)}

Respond with ONLY this JSON schema:
{{
  "patterns": [
    {{"issue": "<specific recurring issue>", "frequency": "<e.g. '4/5 jobs'>", "detail": "<1 sentence>"}}
  ],
  "top_improvement_area": "<the single highest-impact thing to fix>",
  "summary": "<2-3 sentence honest overall summary>"
}}"""
    result = _call_json(system, user, max_tokens=1200)
    if "error" in result:
        return result
    result["insufficient_data"] = False
    result["rejected_count"] = len(rejected)
    return result


# ---------------------------------------------------------------------------
# 9. Career Roadmap
# ---------------------------------------------------------------------------

def generate_career_roadmap(profile: dict, applications: list, rejection_analysis: dict = None) -> dict:
    if not profile:
        return {"error": "No profile found. Upload or load a CV first."}

    all_missing = []
    for a in applications:
        gap = a.get("skill_gap_json")
        if gap:
            all_missing.extend(gap.get("skill_match", {}).get("required_missing", []))
    from collections import Counter
    top_missing = [s for s, _ in Counter(all_missing).most_common(5)]

    system = (
        "You are a career strategist building a phased roadmap (Now / Next / Then / Finally) "
        "grounded in the candidate's actual profile and application history, not generic advice. "
        "You always respond with strictly valid JSON matching the schema, and nothing else."
    )
    user = f"""CANDIDATE PROFILE:
Skills: {profile.get('skills', [])}
Career level: {profile.get('career_level')}
Projects: {json.dumps(profile.get('projects', []))}

SKILLS THAT KEEP APPEARING AS MISSING ACROSS THEIR TARGET JOBS: {top_missing}

REJECTION PATTERN ANALYSIS: {json.dumps(rejection_analysis) if rejection_analysis and not rejection_analysis.get("insufficient_data") else "Not enough rejection data yet."}

APPLICATION HISTORY SUMMARY: {len(applications)} total applications tracked.

Respond with ONLY this JSON schema:
{{
  "now": {{"title": "Improve existing skills", "actions": ["<specific action 1>", "<action 2>"]}},
  "next": {{"title": "Learn missing high-priority skills", "actions": ["<specific action, name actual skills>"]}},
  "then": {{"title": "Build relevant projects", "actions": ["<specific project idea grounded in their gaps>"]}},
  "finally": {{"title": "Apply to higher-match jobs", "actions": ["<specific guidance>"]}}
}}"""
    result = _call_json(system, user, max_tokens=1200)
    if "error" in result:
        return result
    result["top_missing_skills"] = top_missing
    return result


# ---------------------------------------------------------------------------
# 10. What Should I Do Next?
# ---------------------------------------------------------------------------

def recommend_job_priority(comparison_data: list) -> dict:
    """Used by the Job Comparison page to recommend which of 2-3 jobs to prioritize."""
    system = (
        "You are a career strategist. Given comparison data for several jobs, recommend "
        "which one the candidate should prioritize and explain why, referencing the actual "
        "numbers given. You always respond with strictly valid JSON and nothing else."
    )
    user = f"""Compare these jobs and recommend which to prioritize:

{json.dumps(comparison_data, indent=2)}

Respond with ONLY this JSON schema:
{{
  "recommended_job": "<job title from the list above>",
  "explanation": "<2-4 sentences referencing the actual numbers given>"
}}"""
    return _call_json(system, user, max_tokens=500)


def generate_next_action(profile: dict, applications: list, dashboard_stats: dict) -> dict:
    if not profile:
        return {"headline": "Upload or load your CV to get started.",
                "detail": "CareerPilot AI needs your profile before it can recommend a next action.",
                "action_type": "onboarding"}

    saved_jobs = [a for a in applications if a["status"] == "Saved"]
    rejected = [a for a in applications if a["status"] == "Rejected"]

    compact_apps = [{
        "job_title": a["job_title"], "status": a["status"],
        "match_score": a.get("match_score"),
        "missing_skills": (a.get("skill_gap_json") or {}).get("skill_match", {}).get("required_missing", []),
    } for a in applications]

    system = (
        "You are an AI career agent. Given a candidate's full current state, recommend the "
        "SINGLE highest-value next action — not a list of five things. Be specific and concrete: "
        "name actual jobs, skills, or projects from the data given. You always respond with "
        "strictly valid JSON matching the schema, and nothing else."
    )
    user = f"""CANDIDATE: {profile.get('name')}, {profile.get('career_level')}, skills: {profile.get('skills', [])}

DASHBOARD STATS: {json.dumps(dashboard_stats)}
SAVED (NOT YET APPLIED) JOBS: {len(saved_jobs)}
REJECTED APPLICATIONS: {len(rejected)}
FULL APPLICATION LIST: {json.dumps(compact_apps)}

Respond with ONLY this JSON schema:
{{
  "headline": "<one punchy sentence, the single recommended action, e.g. 'Apply to these 3 jobs' or 'Improve your React skills'>",
  "detail": "<2-3 sentences explaining why this is the highest-value action right now, citing actual data above>",
  "action_type": "<one of: apply, skill_building, interview_prep, cv_update, review_rejections, explore_jobs>"
}}"""
    result = _call_json(system, user, max_tokens=600)
    if "error" in result:
        return result
    return result
