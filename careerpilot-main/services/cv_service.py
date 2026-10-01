"""
CV ingestion: extracts raw text from PDF/DOCX/TXT uploads, then hands off
to ai_service.analyze_cv() for structured extraction. Also manages the
demo profile used for hackathon demonstrations.
"""

import io

from services import database as db


class CVParsingError(Exception):
    pass


def extract_text_from_upload(uploaded_file) -> str:
    """
    uploaded_file: a Streamlit UploadedFile object.
    Returns extracted plain text, or raises CVParsingError with a clear message.
    """
    name = uploaded_file.name.lower()
    raw_bytes = uploaded_file.getvalue()

    if not raw_bytes:
        raise CVParsingError("The uploaded file appears to be empty.")

    if name.endswith(".txt"):
        try:
            return raw_bytes.decode("utf-8", errors="ignore")
        except Exception as e:
            raise CVParsingError(f"Could not read text file: {e}")

    if name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
        except ImportError:
            raise CVParsingError("PDF support isn't installed. Run: pip install pypdf")
        try:
            reader = PdfReader(io.BytesIO(raw_bytes))
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception as e:
            raise CVParsingError(f"Could not parse PDF: {e}")
        if not text.strip():
            raise CVParsingError(
                "No extractable text found in this PDF. It may be a scanned image — "
                "try a text-based PDF, DOCX, or TXT file instead."
            )
        return text

    if name.endswith(".docx"):
        try:
            import docx
        except ImportError:
            raise CVParsingError("DOCX support isn't installed. Run: pip install python-docx")
        try:
            document = docx.Document(io.BytesIO(raw_bytes))
            text = "\n".join(p.text for p in document.paragraphs)
        except Exception as e:
            raise CVParsingError(f"Could not parse DOCX: {e}")
        if not text.strip():
            raise CVParsingError("No text found in this DOCX file.")
        return text

    raise CVParsingError("Unsupported file type. Please upload a PDF, DOCX, or TXT file.")


def demo_profile() -> dict:
    """
    A realistic demo profile: a CS student with JS/Node/PostgreSQL skills,
    missing React and Docker — intentionally mirrors the worked example
    used throughout the app's AI features for a consistent demo narrative.
    """
    return {
        "name": "Alex Morgan",
        "raw_text": (
            "Alex Morgan\nComputer Science student, expected graduation 2026.\n\n"
            "EDUCATION\nB.S. Computer Science, State University, Expected 2026\n\n"
            "EXPERIENCE\nSoftware Engineering Intern, Campus Tech Solutions (Summer 2025, 3 months)\n"
            "Built REST APIs and fixed bugs in an internal inventory system using Node.js and PostgreSQL.\n\n"
            "PROJECTS\nGym Management System — a full-stack gym management system for tracking "
            "memberships and payments, built with Java, Spring Boot, and MySQL.\n"
            "Personal Finance Tracker — a personal finance web app to log expenses and visualize "
            "spending trends, built with JavaScript, Node.js, Express, and MongoDB.\n\n"
            "SKILLS\nJavaScript, Node.js, PostgreSQL, HTML, CSS, Python, SQL, MongoDB, Git, Java\n\n"
            "CERTIFICATIONS\nfreeCodeCamp — JavaScript Algorithms and Data Structures"
        ),
        "career_level": "Student",
        "estimated_years_experience": 0.5,
        "skills": ["JavaScript", "Node.js", "PostgreSQL", "HTML", "CSS", "Python", "SQL", "MongoDB", "Git", "Java"],
        "education": [
            {"degree": "Bachelor of Science", "field": "Computer Science",
             "institution": "State University", "year": "Expected 2026"}
        ],
        "experience": [
            {"title": "Software Engineering Intern", "company": "Campus Tech Solutions",
             "duration": "Summer 2025 (3 months)",
             "description": "Built REST APIs and fixed bugs in an internal inventory system using Node.js and PostgreSQL."}
        ],
        "projects": [
            {"name": "Gym Management System",
             "description": "A full-stack gym management system for tracking memberships and payments.",
             "technologies": ["Java", "Spring Boot", "MySQL"]},
            {"name": "Personal Finance Tracker",
             "description": "A personal finance web app to log expenses and visualize spending trends.",
             "technologies": ["JavaScript", "Node.js", "Express", "MongoDB"]},
        ],
        "certifications": ["freeCodeCamp - JavaScript Algorithms and Data Structures"],
    }


def load_demo_profile():
    db.save_profile(demo_profile())


def profile_is_complete(profile: dict) -> bool:
    if not profile:
        return False
    return bool(profile.get("skills"))
