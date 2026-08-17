from __future__ import annotations

import re

from bs4 import BeautifulSoup

from job_hunter.http import HttpClient
from job_hunter.models import Job

HINTS = (
    "engineer",
    "developer",
    "react",
    "python",
    "frontend",
    "backend",
    "full stack",
    "fullstack",
    "ai ",
    " llm",
    "automations",
)


def fetch_sadapay(client: HttpClient) -> list[Job]:
    html = client.get_html("https://sadapay.pk/careers")
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    jobs: dict[str, Job] = {}
    for a in soup.select("a[href]"):
        title = a.get_text(" ", strip=True)
        href = (a.get("href") or "").strip()
        if not title or len(title) > 120:
            continue
        t = title.lower()
        if not any(h in t for h in HINTS):
            continue
        if not re.search(r"https?://", href):
            if href.startswith("/"):
                href = "https://sadapay.pk" + href
            else:
                href = "https://sadapay.pk/careers"
        jobs[title] = Job(
            source="SadaPay",
            source_id=href or title,
            title=title,
            company="SadaPay",
            url=href,
            location="Pakistan",
            work_mode="unknown",
            description=f"{title} SadaPay Pakistan",
            company_domain="sadapay.pk",
            location_restrictions=["Pakistan"],
        )
    return list(jobs.values())
