from __future__ import annotations

from job_hunter.config import LEVER_BOARDS
from job_hunter.http import HttpClient
from job_hunter.models import Job
from job_hunter.textutil import html_to_text, unix_to_iso


def fetch_lever(client: HttpClient) -> list[Job]:
    jobs: list[Job] = []
    for board in LEVER_BOARDS:
        try:
            listings = client.get_json(f"https://api.lever.co/v0/postings/{board}?mode=json")
        except Exception:
            continue
        if not isinstance(listings, list):
            continue
        company = board.title()
        for item in listings:
            cats = item.get("categories") or {}
            location = cats.get("location") or item.get("workplaceType") or ""
            work_type = (item.get("workplaceType") or "").lower()
            if work_type == "remote":
                work_mode = "remote"
            elif work_type == "hybrid":
                work_mode = "hybrid"
            elif work_type in {"onsite", "on-site"}:
                work_mode = "onsite"
            else:
                work_mode = "remote" if "remote" in location.lower() else "unknown"
            description = html_to_text(item.get("descriptionPlain") or item.get("description") or "")
            jobs.append(
                Job(
                    source=f"Lever/{company}",
                    source_id=str(item.get("id") or item.get("hostedUrl") or ""),
                    title=item.get("text") or "",
                    company=company,
                    url=item.get("hostedUrl") or item.get("applyUrl") or "",
                    location=location,
                    work_mode=work_mode,
                    job_type=cats.get("commitment") or "",
                    posted_at=unix_to_iso(item.get("createdAt")),
                    description=description,
                    tags=[cats.get("team") or "", cats.get("department") or ""],
                    location_restrictions=[location] if location else [],
                )
            )
    return jobs
