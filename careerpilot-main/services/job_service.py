"""
Job data access layer.

Currently backed by the bundled demo dataset (data/demo_jobs.json), which
is clearly labeled as demo data throughout the UI. This module is the only
place that knows where job data comes from — to plug in a real job API
later (e.g. a job board partner), implement a new loader function here
with the same return shape (list of job dicts) and swap it into
`load_jobs()`. Nothing else in the app needs to change.
"""

import json
import os

_DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "demo_jobs.json")

_cache = None


def is_demo_data() -> bool:
    return True


def load_jobs() -> list:
    """Loads and caches the active job dataset."""
    global _cache
    if _cache is None:
        with open(_DATA_PATH, "r") as f:
            data = json.load(f)
        _cache = data["jobs"]
    return _cache


def get_job_by_id(job_id: str) -> dict | None:
    for job in load_jobs():
        if job["id"] == job_id:
            return job
    return None


def get_categories() -> list:
    return sorted({j["category"] for j in load_jobs()})


def get_locations() -> list:
    return sorted({j["location"] for j in load_jobs()})


def search_jobs(
    query: str = "",
    categories: list = None,
    remote_statuses: list = None,
    employment_types: list = None,
    experience_levels: list = None,
    skills: list = None,
) -> list:
    jobs = load_jobs()
    results = []
    query_lower = (query or "").strip().lower()

    for job in jobs:
        if query_lower:
            haystack = f"{job['title']} {job['company']} {' '.join(job['required_skills'])}".lower()
            if query_lower not in haystack:
                continue
        if categories and job["category"] not in categories:
            continue
        if remote_statuses and job["remote_status"] not in remote_statuses:
            continue
        if employment_types and job["employment_type"] not in employment_types:
            continue
        if experience_levels and job["experience_level"] not in experience_levels:
            continue
        if skills:
            job_skills_norm = {s.lower() for s in job["required_skills"] + job["preferred_skills"]}
            if not any(s.lower() in job_skills_norm for s in skills):
                continue
        results.append(job)
    return results
