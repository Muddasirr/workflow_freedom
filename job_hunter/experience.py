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
    " iii",
    " iii,",
    " iii)",
    " iv",
    " iv,",
    "l4",
    "l5",
    "l6",
    "l7",
    "l8",
    "(l4",
    "(l5",
    "(l6",
    "(l7",
    "(l8",
    "ic4",
    "ic5",
    "ic6",
)

# Level II+ engineer titles (Amazon SDE II, Google SWE III, etc.) = above 0–2 YOE target.
LEVEL_TWO_PLUS = re.compile(
    r"\b(?:software engineer|developer|sde|swe|engineer)\s*,?\s*(?:ii|iii|iv|2|3|4)\b"
    r"|\b(?:ii|iii|iv)\s*,?\s*(?:software engineer|developer|engineer)\b"
    r"|\bengineer\s+(?:ii|iii|iv)\b",
    re.I,
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

    senior_title = any(h in title for h in SENIOR_TITLE_HINTS) or bool(LEVEL_TWO_PLUS.search(job.title or ""))
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


def role_ok_for_junior(title: str, description: str = "") -> bool:
    """Drop senior/staff/L4+ and 3+ year postings for 0–2 YOE outreach."""
    title_l = (title or "").lower()
    if LEVEL_TWO_PLUS.search(title or ""):
        return False
    if any(h in title_l for h in SENIOR_TITLE_HINTS):
        # Google/Netflix-style L3 is entry-level; L4+ is not.
        if re.search(r"\bl3\b", title_l) and not re.search(r"\bl[4-9]\b", title_l):
            pass
        else:
            return False
    if re.search(r"\b(?:lead|manager|director|head of)\b", title_l):
        return False
    blob = f"{title} {description}"[:5000].lower()
    if TOO_SENIOR_YEARS.search(blob) and not JUNIOR_YEARS.search(blob):
        return False
    return True
