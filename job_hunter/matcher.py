from __future__ import annotations

import re

from job_hunter.config import (
    CORE_SKILLS,
    DESCRIPTION_WEIGHT,
    EXCLUDE_TITLE_HINTS,
    MIN_SCORE,
    MIN_SCORE_PK,
    PAKISTAN_TZ_OFFSETS,
    RELEVANT_TITLE_HINTS,
    SKILL_PATTERNS,
    TITLE_WEIGHT,
)
from job_hunter.models import Job
from job_hunter.textutil import excerpt, html_to_text

REMOTE_HINTS = ("remote", "work from home", "wfh", "distributed", "anywhere", "work-from-home")
HYBRID_HINTS = ("hybrid",)
ONSITE_HINTS = ("on-site", "onsite", "in-office", "in office", "office-based")
WORLDWIDE_HINTS = (
    "worldwide",
    "anywhere",
    "unrestricted",
    "no restriction",
    "work from anywhere",
    "global",
    "remote - worldwide",
)
US_ONLY_HINTS = (
    "united states only",
    "usa only",
    "us only",
    "must be in the us",
    "must be located in the us",
    "us work authorization",
    "authorized to work in the us",
    "us citizen",
    "green card",
)
EU_ONLY_HINTS = (
    "eu only",
    "europe only",
    "uk only",
    "right to work in the uk",
    "must be in europe",
    "emea only",
)
PK_HINTS = (
    "pakistan",
    "pakistani",
    "karachi",
    "lahore",
    "islamabad",
    "rawalpindi",
    "sindh",
    "peshawar",
    "faisalabad",
    "multan",
    "quetta",
    "hyderabad",
    "gujranwala",
    "sialkot",
)
KARACHI_HINTS = ("karachi", "khi")
OTHER_PK_CITIES = ("lahore", "islamabad", "rawalpindi", "peshawar", "faisalabad", "multan", "quetta")


def _compile() -> dict[str, list[re.Pattern[str]]]:
    return {
        name: [re.compile(pat, re.I) for pat in patterns]
        for name, patterns in SKILL_PATTERNS.items()
    }


_SKILL_RE = _compile()


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(n in text for n in needles)


def title_looks_relevant(title: str) -> bool:
    t = title.lower()
    if _contains_any(t, EXCLUDE_TITLE_HINTS):
        # still allow if a core skill is explicitly in the title
        if not any(p.search(title) for skill, regs in _SKILL_RE.items() if skill in CORE_SKILLS for p in regs):
            return False
    return _contains_any(t, RELEVANT_TITLE_HINTS)


def score_job(job: Job) -> Job:
    title = job.title or ""
    description = html_to_text(job.description)
    blob = f"{title}\n{' '.join(job.tags)}\n{description}"
    title_l = title.lower()

    matched: list[str] = []
    score = 0
    for skill, patterns in _SKILL_RE.items():
        in_title = any(p.search(title) for p in patterns)
        in_body = any(p.search(blob) for p in patterns)
        if in_title:
            matched.append(skill)
            score += TITLE_WEIGHT
            if skill in CORE_SKILLS:
                score += 6
        elif in_body:
            matched.append(skill)
            score += DESCRIPTION_WEIGHT
            if skill in CORE_SKILLS:
                score += 2

    if "next.js" in title_l or "nextjs" in title_l:
        score += 8
    if any(k in title_l for k in ("ai engineer", "llm", "machine learning", "genai")):
        score += 8
    if "product engineer" in title_l:
        score += 7
    if "software engineer" in title_l or "software developer" in title_l:
        score += 6
    if any(k in title_l for k in ("frontend engineer", "front-end engineer", "front end engineer", "frontend developer")):
        score += 7
    if "python" in title_l:
        score += 5
    if "react" in title_l:
        score += 5

    job.matched_skills = matched
    job.score = score
    job.excerpt = excerpt(description)
    job.role_fit = _role_fit(matched, title_l)
    _classify_location(job, description)
    from job_hunter.experience import classify_experience

    classify_experience(job)
    return job


TARGET_TITLE_HINTS = (
    "ai engineer",
    "artificial intelligence",
    "machine learning engineer",
    "ml engineer",
    "llm",
    "genai",
    "product engineer",
    "software engineer",
    "software developer",
    "frontend engineer",
    "front-end engineer",
    "front end engineer",
    "frontend developer",
    "front-end developer",
    "full stack engineer",
    "fullstack engineer",
    "full-stack engineer",
)


def title_is_target(title: str) -> bool:
    t = (title or "").lower()
    if _contains_any(t, EXCLUDE_TITLE_HINTS) and not any(
        k in t for k in ("ai engineer", "product engineer", "software engineer", "frontend", "front-end")
    ):
        return False
    return any(h in t for h in TARGET_TITLE_HINTS) or _contains_any(t, RELEVANT_TITLE_HINTS)


def _role_fit(skills: list[str], title_l: str) -> list[str]:
    labels: list[str] = []
    skillset = set(skills)
    if "ai engineer" in title_l or "artificial intelligence" in title_l or skillset & {
        "AI Engineering",
        "LangChain",
        "RAG",
        "OpenAI / GPT",
        "Machine Learning",
    } or any(k in title_l for k in ("llm", "machine learning", "ml engineer", "genai")):
        labels.append("AI Engineer")
    if "product engineer" in title_l:
        labels.append("Product Engineer")
    if "software engineer" in title_l or "software developer" in title_l:
        labels.append("Software Engineer")
    if skillset & {"Next.js", "React", "Frontend", "TypeScript"} or any(
        k in title_l for k in ("frontend", "front-end", "front end", "react", "next")
    ):
        labels.append("Frontend Engineer")
    if skillset & {"Python", "FastAPI", "Django", "Flask", "Backend"} or "python" in title_l:
        labels.append("Python / Backend")
    if "Full Stack" in skillset or "full stack" in title_l or "fullstack" in title_l:
        labels.append("Full Stack")
    return labels


def _classify_location(job: Job, description: str) -> None:
    loc = (job.location or "").lower()
    restrictions = [r.lower() for r in job.location_restrictions]
    restriction_text = " ".join(restrictions)
    head = f"{job.title} {job.location} {restriction_text} {description[:2000]}".lower()

    if job.work_mode == "unknown":
        if _contains_any(head, HYBRID_HINTS):
            job.work_mode = "hybrid"
        elif _contains_any(head, ONSITE_HINTS) and not _contains_any(head, REMOTE_HINTS):
            job.work_mode = "onsite"
        elif _contains_any(head, REMOTE_HINTS) or job.source in {
            "Remotive",
            "RemoteOK",
            "Jobicy",
            "Himalayas",
            "We Work Remotely",
        }:
            job.work_mode = "remote"
        elif restrictions or "remote" in loc:
            job.work_mode = "remote"

    is_karachi = _contains_any(loc, KARACHI_HINTS) or _contains_any(head[:600], KARACHI_HINTS)
    is_pakistan = _contains_any(loc, PK_HINTS) or _contains_any(restriction_text, PK_HINTS)
    other_pk_city = _contains_any(loc, OTHER_PK_CITIES) and not is_karachi
    worldwide = (
        not restrictions
        and _contains_any(loc + " " + restriction_text, WORLDWIDE_HINTS)
    ) or _contains_any(restriction_text, WORLDWIDE_HINTS)
    if not restrictions and job.work_mode == "remote" and not loc.strip():
        worldwide = True
    if loc.strip() in {"worldwide", "anywhere", "remote", "remote - worldwide", "anywhere in the world"}:
        worldwide = True

    us_only = _contains_any(head, US_ONLY_HINTS) or restriction_text in {
        "united states",
        "usa",
        "us",
        "united states of america",
    }
    eu_only = _contains_any(head, EU_ONLY_HINTS)
    asia_friendly = any(
        token in restriction_text or token in loc
        for token in ("asia", "apac", "south asia", "pakistan", "india", "uae", "middle east")
    )

    tz_ok = False
    # Himalayas sometimes encodes timezone offsets on the job via notes later; parse "+05" too.
    if re.search(r"\b(?:utc|gmt)\s*\+?0?5(?:[:.]00)?\b", head):
        tz_ok = True

    existing_notes = job.notes.strip()
    tz_from_source = "timezone overlaps pk" in existing_notes.lower()

    if is_karachi:
        if job.work_mode == "unknown":
            job.work_mode = "onsite"
        job.location_fit = "Karachi on-site/hybrid" if job.work_mode != "remote" else "Karachi remote"
        job.pakistan_friendly = "Yes"
        job.score += 10
        job.notes = existing_notes
        return

    # Physical / hybrid anywhere in Pakistan is in scope (not Karachi-only).
    if (is_pakistan or other_pk_city) and job.work_mode in {"onsite", "hybrid", "unknown"}:
        if job.work_mode == "unknown" and (other_pk_city or is_pakistan):
            job.work_mode = "onsite"
        city_label = "Other Pakistan city" if other_pk_city and not is_karachi else "Pakistan"
        job.location_fit = (
            f"{city_label} on-site/hybrid" if job.work_mode != "remote" else "Pakistan remote"
        )
        job.pakistan_friendly = "Yes"
        job.score += 9
        job.notes = existing_notes
        return

    if job.work_mode == "onsite" and not is_karachi and not is_pakistan and not other_pk_city:
        job.location_fit = "On-site outside Pakistan"
        job.pakistan_friendly = "No"
        job.notes = _join_notes(existing_notes, "On-site role is outside Pakistan.")
        job.score = 0
        return

    if is_pakistan or other_pk_city:
        job.location_fit = "Pakistan remote" if job.work_mode == "remote" else "Pakistan"
        job.pakistan_friendly = "Yes"
        job.score += 8
        return

    if worldwide or (job.work_mode == "remote" and not restrictions and "united states" not in loc and "europe" not in loc):
        if us_only or eu_only:
            job.location_fit = "Restricted remote"
            job.pakistan_friendly = "No"
            job.notes = _join_notes(existing_notes, "Remote, but posting looks geo-restricted.")
            return
        job.location_fit = "Worldwide remote"
        job.pakistan_friendly = "Yes"
        job.score += 6
        job.notes = existing_notes
        return

    if tz_ok or asia_friendly or tz_from_source:
        job.location_fit = "Timezone / APAC remote"
        job.pakistan_friendly = "Maybe"
        job.notes = _join_notes(existing_notes, "Remote with APAC/timezone overlap — worth applying.")
        job.score += 3
        return

    if job.work_mode == "remote":
        job.location_fit = "Restricted remote"
        job.pakistan_friendly = "No"
        countries = ", ".join(job.location_restrictions) or job.location
        job.notes = _join_notes(existing_notes, f"Remote with location restriction: {countries}".strip())
        return

    job.location_fit = job.location or "Unknown"
    job.pakistan_friendly = "Maybe"
    job.notes = existing_notes


def _join_notes(*parts: str) -> str:
    return " | ".join(p.strip() for p in parts if p and p.strip())


def is_keepable(
    job: Job,
    *,
    include_restricted: bool,
    karachi_only: bool,
    pakistan_friendly_only: bool,
    junior_only: bool = False,
    junior_strict: bool = False,
) -> bool:
    pk_local = job.pakistan_friendly == "Yes" or "Karachi" in (job.location_fit or "") or "pakistan" in (job.location or "").lower()
    targeted = title_is_target(job.title)
    if job.score < (MIN_SCORE_PK if pk_local or targeted else MIN_SCORE):
        return False
    if not targeted and not title_looks_relevant(job.title) and not (set(job.matched_skills) & CORE_SKILLS):
        return False
    if not targeted and not (set(job.matched_skills) & CORE_SKILLS) and "Full Stack" not in job.matched_skills:
        if not (pk_local and title_looks_relevant(job.title)):
            return False
    if job.location_fit == "On-site outside Pakistan":
        return False
    if karachi_only and "Karachi" not in job.location_fit:
        return False
    if pakistan_friendly_only and job.pakistan_friendly != "Yes":
        return False
    if not include_restricted and job.pakistan_friendly == "No" and job.work_mode == "remote":
        return False
    if junior_only or junior_strict:
        from job_hunter.experience import is_junior_keepable

        if not is_junior_keepable(job, strict=junior_strict):
            return False
    return True
