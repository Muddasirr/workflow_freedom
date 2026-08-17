from __future__ import annotations

import xml.etree.ElementTree as ET

from job_hunter.http import HttpClient
from job_hunter.models import Job
from job_hunter.textutil import html_to_text

FEEDS = (
    "https://weworkremotely.com/categories/remote-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-front-end-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-back-end-programming-jobs.rss",
)


def fetch_wwr(client: HttpClient) -> list[Job]:
    jobs: dict[str, Job] = {}
    for feed in FEEDS:
        try:
            xml_text = client.get_text(feed)
        except Exception:
            continue
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            continue
        for item in root.findall("./channel/item"):
            title_raw = (item.findtext("title") or "").strip()
            url = (item.findtext("link") or "").strip()
            if not title_raw or not url or url in jobs:
                continue
            if ": " in title_raw:
                company, title = title_raw.split(": ", 1)
            else:
                company, title = "", title_raw
            region = (item.findtext("region") or "").strip()
            category = (item.findtext("category") or "").strip()
            description = html_to_text(item.findtext("description") or "")
            jobs[url] = Job(
                source="We Work Remotely",
                source_id=url,
                title=title.strip(),
                company=company.strip(),
                url=url,
                location=region or "Remote",
                work_mode="remote",
                job_type=category,
                description=description,
                location_restrictions=[]
                if region.lower() in {"anywhere in the world", "worldwide", "anywhere", "remote", ""}
                else [region],
            )
    return list(jobs.values())
