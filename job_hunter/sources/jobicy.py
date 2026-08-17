from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from job_hunter.config import JOBICY_TAGS
from job_hunter.http import HttpClient
from job_hunter.models import Job
from job_hunter.textutil import format_salary, html_to_text


def fetch_jobicy(_client: HttpClient | None = None) -> list[Job]:
    jobs: dict[str, Job] = {}
    queries = [("tag", tag) for tag in JOBICY_TAGS] + [("industry", "engineering")]

    def one(key: str, value: str) -> list[Job]:
        local = HttpClient()
        try:
            data = local.get_json(
                "https://jobicy.com/api/v2/remote-jobs",
                params={key: value, "count": 100},
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
            geo = item.get("jobGeo") or "Remote"
            job_types = item.get("jobType") or []
            if isinstance(job_types, str):
                job_types = [job_types]
            batch.append(
                Job(
                    source="Jobicy",
                    source_id=source_id,
                    title=item.get("jobTitle") or "",
                    company=item.get("companyName") or "",
                    url=item.get("url") or "",
                    location=geo if isinstance(geo, str) else ", ".join(geo),
                    work_mode="remote",
                    job_type=", ".join(job_types),
                    salary=format_salary(
                        item.get("salaryMin"),
                        item.get("salaryMax"),
                        item.get("salaryCurrency") or "USD",
                        item.get("salaryPeriod") or "yearly",
                    ),
                    posted_at=(item.get("pubDate") or "")[:10],
                    description=html_to_text(item.get("jobDescription") or item.get("jobExcerpt") or ""),
                    location_restrictions=[] if str(geo).lower() in {"anywhere", "worldwide", "remote", ""} else [str(geo)],
                )
            )
        return batch

    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = [pool.submit(one, key, value) for key, value in queries]
        for fut in as_completed(futs):
            for job in fut.result():
                jobs.setdefault(job.source_id, job)
    return list(jobs.values())
