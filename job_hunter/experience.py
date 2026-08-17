"""Keep software/AI/product roles at 0–2 years. Drop senior / 3+ year postings."""
from __future__ import annotations

import re

from job_hunter.models import Job

SENIOR_TITLE_HINTS = (
    "senior",
    "sr.",
    "sr ",
    "staff ",
    "principal",
    "lead software",
    "lead engineer",
    "engineering manager",
    "eng manager",
    "head of engineering",
    "head of software",
    "director of",
    "architect",
    "iii",
    " iv",
    "l5",
    "l6",
    "l7",
    "ic4",
    "ic5",
)

JUNIOR_TITLE_RE = re.compile(
    r"\b(?:junior|jr\.?|associate\s+(?:software|engineer|developer)|"
    r"entry[\s-]?level|graduate|new[\s-]?grad|intern(?:ship)?s?|trainee|"
    r"early[\s-]?career|apprentice)\b",
    re.I,
)

# Explicit 3+ year requirements.
TOO_SENIOR_YEARS = re.compile(
    r"""
    (?:
        (?:minimum|min(?:imum)?|at\s+least|require[sd]?|must\s+have|looking\s+for)
        \s+(?:of\s+)?
        (?:[3-9]|[1-9]\d)
        \+?
        \s*(?:\+|or\s+more)?
        \s*years
    )
    |
    \b(?:[3-9]|[1-9]\d)\+\s*years
    |
    \b(?:[3-9])\s*[-–to]{1,3}\s*(?:\d{1,2})\s*years
    |
    \b(?:five|six|seven|eight|nine|ten)\s*\+?\s*years
    """,
    re.I | re.X,
)

JUNIOR_YEARS = re.compile(
    r"""
    (?:
        \b(?:0\s*[-–to]+\s*[123]|0-2|0-1|1-2|0\s+to\s+2|1\s+to\s+2)
        \s*years
    )
    |
    \b(?:up\s*to|upto|maximum|max(?:imum)?)\s*2\s*years
    |
    \b(?:0|1|2)\s*\+?\s*years?\s+(?:of\s+)?(?:experience|exp)\b
    |
    \bfresh(?:er)?s?\b
    |
    \bno\s+experience\s+required\b
    """,
    re.I | re.X,
)


def _blob(job: Job) -> str:
    return " ".join(
        [
            job.title or "",
            job.job_type or "",
            " ".join(job.tags),
            (job.description or "")[:4000],
            job.excerpt or "",
        ]
    ).lower()


def classify_experience(job: Job) -> Job:
    title = (job.title or "").lower()
    blob = _blob(job)

    senior_title = any(h in title for h in SENIOR_TITLE_HINTS)
    junior_title = bool(JUNIOR_TITLE_RE.search(title))
    junior_blob = bool(JUNIOR_TITLE_RE.search(blob))
    junior_years = bool(JUNIOR_YEARS.search(blob))
    too_senior = bool(TOO_SENIOR_YEARS.search(blob)) and not junior_years and not junior_blob

    if senior_title and not junior_title:
        job.seniority = "senior"
        job.experience_fit = "No"
        job.experience_note = "Title looks senior / staff / lead."
        return job
    if too_senior and not junior_title and not junior_blob:
        job.seniority = "mid-senior"
        job.experience_fit = "No"
        job.experience_note = "Posting asks for 3+ years."
        return job
    if junior_title or junior_blob or junior_years:
        job.seniority = "junior"
        job.experience_fit = "Yes"
        job.experience_note = "Junior / 0–2 years posting."
        job.score += 5
        return job

    job.seniority = "unspecified"
    job.experience_fit = "Maybe"
    job.experience_note = "No year requirement found — treat as 0–2 friendly."
    return job


def is_junior_keepable(job: Job, *, strict: bool = False) -> bool:
    if job.experience_fit == "No":
        return False
    if strict:
        return job.experience_fit == "Yes"
    return job.experience_fit in {"Yes", "Maybe"}
