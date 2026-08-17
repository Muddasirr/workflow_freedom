from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from job_hunter.config import REMOTIVE_SEARCHES
from job_hunter.http import HttpClient
from job_hunter.models import Job
from job_hunter.textutil import html_to_text


def fetch_remotive(_client: HttpClient | None = None) -> list[Job]:
    jobs: dict[str, Job] = {}

    def one(query: str) -> list[Job]:
        local = HttpClient()
        try:
            data = local.get_json(
                "https://remotive.com/api/remote-jobs",
                params={"search": query, "limit": 100},
            )
        except Exception:
            return []
        finally:
            local.close()
        batch: list[Job] = []
        for item in data.get("jobs") or []:
            source_id = str(item.get("id") or item.get("url") or "")
            if not source_id:
                continue
            location = item.get("candidate_required_location") or "Worldwide"
            batch.append(
                Job(
                    source="Remotive",
                    source_id=source_id,
                    title=item.get("title") or "",
                    company=item.get("company_name") or "",
                    url=item.get("url") or "",
                    location=location,
                    work_mode="remote",
                    job_type=item.get("job_type") or "",
                    salary=item.get("salary") or "",
                    posted_at=(item.get("publication_date") or "")[:10],
                    description=html_to_text(item.get("description") or ""),
                    tags=list(item.get("tags") or []),
                    location_restrictions=[] if location.lower() in {"worldwide", "anywhere", ""} else [location],
                )
            )
        return batch

    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = [pool.submit(one, query) for query in REMOTIVE_SEARCHES]
        for fut in as_completed(futs):
            for job in fut.result():
                jobs.setdefault(job.source_id, job)
    return list(jobs.values())
