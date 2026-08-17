from __future__ import annotations

from job_hunter.http import HttpClient
from job_hunter.models import Job
from job_hunter.textutil import html_to_text, unix_to_iso


def fetch_arbeitnow(client: HttpClient, pages: int = 2) -> list[Job]:
    jobs: list[Job] = []
    for page in range(1, pages + 1):
        data = client.get_json(
            "https://www.arbeitnow.com/api/job-board-api",
            params={"page": page},
        )
        for item in data.get("data") or []:
            remote = bool(item.get("remote"))
            location = item.get("location") or ""
            loc_l = location.lower()
            # Keep remote roles, plus anything mentioning Pakistan / Karachi.
            if not remote and "karachi" not in loc_l and "pakistan" not in loc_l:
                continue
            jobs.append(
                Job(
                    source="Arbeitnow",
                    source_id=item.get("slug") or item.get("url") or "",
                    title=item.get("title") or "",
                    company=item.get("company_name") or "",
                    url=item.get("url") or "",
                    location=location,
                    work_mode="remote" if remote else "onsite",
                    job_type=", ".join(item.get("job_types") or []),
                    posted_at=unix_to_iso(item.get("created_at")),
                    description=html_to_text(item.get("description") or ""),
                    tags=[str(t) for t in (item.get("tags") or [])],
                    location_restrictions=[location] if location else [],
                )
            )
        if not (data.get("links") or {}).get("next"):
            break
    return jobs
