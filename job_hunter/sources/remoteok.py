from __future__ import annotations

from job_hunter.http import HttpClient
from job_hunter.models import Job
from job_hunter.textutil import format_salary, html_to_text


def fetch_remoteok(client: HttpClient) -> list[Job]:
    payload = client.get_json("https://remoteok.com/api")
    jobs: list[Job] = []
    if not isinstance(payload, list):
        return jobs
    for item in payload:
        if not isinstance(item, dict) or not item.get("id") or not item.get("position"):
            continue
        location = item.get("location") or "Remote"
        jobs.append(
            Job(
                source="RemoteOK",
                source_id=str(item.get("id")),
                title=item.get("position") or "",
                company=item.get("company") or "",
                url=item.get("url") or item.get("apply_url") or "",
                location=location,
                work_mode="remote",
                salary=format_salary(item.get("salary_min"), item.get("salary_max"), "USD", "yearly"),
                posted_at=(item.get("date") or "")[:10],
                description=html_to_text(item.get("description") or ""),
                tags=[str(t) for t in (item.get("tags") or [])],
                location_restrictions=[] if "worldwide" in location.lower() else [location] if location.lower() not in {"remote", ""} else [],
            )
        )
    return jobs
