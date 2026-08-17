from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from job_hunter.http import HttpClient
from job_hunter.models import Job
from job_hunter.sources.arbeitnow import fetch_arbeitnow
from job_hunter.sources.greenhouse import fetch_greenhouse
from job_hunter.sources.himalayas import fetch_himalayas
from job_hunter.sources.jazzhr import fetch_jazzhr
from job_hunter.sources.jobicy import fetch_jobicy
from job_hunter.sources.lever import fetch_lever
from job_hunter.sources.remoteok import fetch_remoteok
from job_hunter.sources.remotive import fetch_remotive
from job_hunter.sources.sadapay import fetch_sadapay
from job_hunter.sources.wwr import fetch_wwr


def fetch_all(_client: HttpClient | None = None) -> list[Job]:
    jobs: list[Job] = []
    fetchers = (
        ("Remotive", fetch_remotive),
        ("RemoteOK", fetch_remoteok),
        ("Arbeitnow", fetch_arbeitnow),
        ("Jobicy", fetch_jobicy),
        ("Himalayas", fetch_himalayas),
        ("We Work Remotely", fetch_wwr),
        ("Greenhouse", fetch_greenhouse),
        ("Lever", fetch_lever),
        ("JazzHR PK", fetch_jazzhr),
        ("SadaPay", fetch_sadapay),
    )

    def run(name, fetch):
        local = HttpClient()
        try:
            return name, fetch(local), None
        except Exception as exc:  # noqa: BLE001
            return name, [], exc
        finally:
            local.close()

    with ThreadPoolExecutor(max_workers=9) as pool:
        futures = [pool.submit(run, name, fetch) for name, fetch in fetchers]
        for fut in as_completed(futures):
            name, batch, exc = fut.result()
            if exc:
                print(f"  [{name}] skipped: {exc}", flush=True)
            else:
                print(f"  [{name}] {len(batch)} listings pulled", flush=True)
                jobs.extend(batch)
    return jobs
