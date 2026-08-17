from __future__ import annotations

import xml.etree.ElementTree as ET

from job_hunter.http import HttpClient
from job_hunter.models import Job
from job_hunter.textutil import html_to_text


def fetch_himalayas(client: HttpClient) -> list[Job]:
    jobs: dict[str, Job] = {}
    try:
        xml_text = client.get_text("https://himalayas.app/jobs/rss")
        root = ET.fromstring(xml_text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        items = root.findall("./channel/item") or root.findall("atom:entry", ns)
        for item in items:
            title = (item.findtext("title") or "").strip()
            url = (item.findtext("link") or item.findtext("guid") or "").strip()
            if not title:
                continue
            company = ""
            for child in list(item):
                tag = child.tag.lower()
                if "companyname" in tag:
                    company = (child.text or "").strip()
            jobs[url or title] = Job(
                source="Himalayas",
                source_id=url or title,
                title=title,
                company=company,
                url=url,
                location="Remote",
                work_mode="remote",
                description=html_to_text(item.findtext("description") or item.findtext("content") or ""),
            )
    except Exception:
        pass
    return list(jobs.values())
