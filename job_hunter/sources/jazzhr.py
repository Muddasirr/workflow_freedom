from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from job_hunter.config import JAZZHR_BOARDS
from job_hunter.http import HttpClient
from job_hunter.models import Job

APPLY_HREF = re.compile(r"/apply/[A-Za-z0-9]+/")


def _job_from_item(item, slug: str, company: str, domain: str, base: str) -> Job | None:
    link = item.select_one("h3 a[href], h2 a[href], a[href*='/apply/']")
    if not link:
        return None
    href = (link.get("href") or "").strip()
    if not APPLY_HREF.search(href):
        return None
    title = link.get_text(" ", strip=True)
    if not title or title.lower() in {"apply", "view", "read more"}:
        return None
    url = urljoin(base, href)
    loc_el = item.select_one(".fa-map-marker")
    location = ""
    if loc_el and loc_el.parent:
        location = loc_el.parent.get_text(" ", strip=True)
    elif item.select_one("ul.list-inline"):
        location = item.select_one("ul.list-inline").get_text(" ", strip=True)
    loc_l = location.lower()
    work_mode = "remote" if "remote" in loc_l else "unknown"
    if "hybrid" in loc_l:
        work_mode = "hybrid"
    return Job(
        source=f"JazzHR/{company}",
        source_id=url or f"{slug}:{title}",
        title=title,
        company=company,
        url=url,
        location=location or "Pakistan",
        work_mode=work_mode,
        description=f"{title} {location} {company}",
        company_domain=domain,
        location_restrictions=[location] if location else ["Pakistan"],
    )


def _jobs_from_links(html: str, slug: str, company: str, domain: str, base: str) -> list[Job]:
    jobs: list[Job] = []
    seen: set[str] = set()
    soup = BeautifulSoup(html, "lxml")
    for a in soup.select("a[href*='/apply/']"):
        href = (a.get("href") or "").strip()
        if not APPLY_HREF.search(href):
            continue
        url = urljoin(base, href)
        if url in seen or url.rstrip("/").endswith("/apply"):
            continue
        title = a.get_text(" ", strip=True)
        if not title or len(title) < 6:
            slug_title = url.rstrip("/").rsplit("/", 1)[-1].replace("-", " ")
            title = slug_title
        if title.lower() in {"apply now", "apply", "view job"}:
            continue
        seen.add(url)
        loc_l = title.lower()
        work_mode = "remote" if "remote" in loc_l else "unknown"
        jobs.append(
            Job(
                source=f"JazzHR/{company}",
                source_id=url,
                title=title,
                company=company,
                url=url,
                location="Pakistan",
                work_mode=work_mode,
                description=f"{title} {company} Pakistan",
                company_domain=domain,
                location_restrictions=["Pakistan"],
            )
        )
    return jobs


def fetch_jazzhr(_client: HttpClient | None = None) -> list[Job]:
    jobs: list[Job] = []

    def one(slug: str, company: str, domain: str) -> list[Job]:
        base = f"https://{slug}.applytojob.com/apply"
        local = HttpClient()
        try:
            html = local.get_html(base)
        finally:
            local.close()
        if not html:
            return []
        low = html.lower()
        if "jazzhr.com/job-seekers" in low and "list-group-item" not in low and "/apply/" not in low:
            return []
        soup = BeautifulSoup(html, "lxml")
        batch: list[Job] = []
        seen: set[str] = set()
        for item in soup.select("li.list-group-item, div.list-group-item, tr.job, div.job"):
            job = _job_from_item(item, slug, company, domain, base)
            if job and job.url not in seen:
                seen.add(job.url)
                batch.append(job)
        if not batch:
            batch = _jobs_from_links(html, slug, company, domain, base)
        return batch

    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = [pool.submit(one, slug, company, domain) for slug, company, domain in JAZZHR_BOARDS]
        for fut in as_completed(futs):
            jobs.extend(fut.result())
    return jobs
