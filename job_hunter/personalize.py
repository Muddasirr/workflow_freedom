"""Pick the letter + one-line hook that matches a job opening."""
from __future__ import annotations

from pathlib import Path

from job_hunter.config import ROOT
from job_hunter.models import Job

LETTER_PRODUCT = ROOT / "emailll.txt"
LETTER_AI = ROOT / "emailll_ai.txt"
LETTER_GO = ROOT / "emailll_go.txt"

AI_HINTS = (
    "ai engineer",
    "artificial intelligence",
    "machine learning",
    "ml engineer",
    "llm",
    "genai",
    "generative",
    "langchain",
    "langgraph",
    "rag",
    "nlp",
)
GO_HINTS = ("golang", " go ", "go engineer", "go developer", "backend")
PRODUCT_HINTS = (
    "product engineer",
    "frontend",
    "front-end",
    "front end",
    "next.js",
    "nextjs",
    "react",
    "full stack",
    "fullstack",
    "full-stack",
)


def _title_blob(job: Job) -> str:
    return f"{job.title} {' '.join(job.matched_skills)} {' '.join(job.role_fit)} {job.excerpt}".lower()


def pick_letter(job: Job) -> Path:
    blob = _title_blob(job)
    if any(h in blob for h in AI_HINTS) or "AI Engineer" in job.role_fit:
        return LETTER_AI if LETTER_AI.is_file() else LETTER_PRODUCT
    if any(h in blob for h in GO_HINTS) and "AI Engineer" not in job.role_fit:
        return LETTER_GO if LETTER_GO.is_file() else LETTER_PRODUCT
    if any(h in blob for h in PRODUCT_HINTS) or "Product Engineer" in job.role_fit or "Frontend Engineer" in job.role_fit:
        return LETTER_PRODUCT
    if LETTER_PRODUCT.is_file():
        return LETTER_PRODUCT
    return LETTER_AI


def role_label(job: Job) -> str:
    title = (job.title or "Software Engineer").strip()
    # Keep subject readable.
    if len(title) > 70:
        title = title[:67].rsplit(" ", 1)[0] + "…"
    return title


def location_clause(job: Job) -> str:
    loc = (job.location or "").strip()
    fit = (job.location_fit or "").strip()
    if job.work_mode == "remote" or "remote" in fit.lower() or "worldwide" in fit.lower():
        if loc and loc.lower() not in {"remote", "worldwide", "anywhere"}:
            return f" ({loc}, remote)"
        return " (remote)"
    if loc:
        return f" ({loc})"
    return ""
