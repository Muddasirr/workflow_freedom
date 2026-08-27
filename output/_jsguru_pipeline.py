#!/usr/bin/env python3
"""Scrape jsgurujobs.com listings, find published company emails, SMTP-verify, write CSV."""
from __future__ import annotations

import csv
import re
import sys
import time
from html import unescape
from pathlib import Path
from urllib.parse import urlparse

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "outreach"))

from job_hunter.config import PK_CONTACT_PATHS  # noqa: E402
from job_hunter.directory import COMPANY_DIRECTORY  # noqa: E402
from job_hunter.emails import WELL_KNOWN_COMPANY_DOMAINS, pick_hr_email  # noqa: E402
from job_hunter.http import HttpClient  # noqa: E402
from job_hunter.textutil import extract_emails, html_to_text  # noqa: E402
from send_emails import (  # noqa: E402
    BLOCKED_COMPANIES,
    BLOCKED_DOMAINS,
    SKIP_LOCAL,
    already_sent,
)
from smtp_verify import bounced_emails, verify_mailbox  # noqa: E402

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
SKIP_HOST_PARTS = (
    "linkedin.",
    "facebook.",
    "twitter.",
    "x.com",
    "instagram.",
    "youtube.",
    "tiktok.",
    "wikipedia.",
    "crunchbase.",
    "glassdoor.",
    "indeed.",
    "wellfound.",
    "angel.co",
    "github.com",
    "play.google",
    "apps.apple",
    "jsgurujobs.",
    "medium.com",
    "reddit.com",
    "g2.com",
)
CARD_RE = re.compile(
    r'href="https://jsgurujobs.com/jobs/(\d+)"[^>]*>\s*([^<]+?)\s*</a>'
    r'.*?<p class="mt-1 text-sm text-gray-500[^"]*"[^>]*>([^<]+)</p>',
    re.S,
)


def cf_decode(encoded: str) -> str:
    key = int(encoded[:2], 16)
    return "".join(chr(int(encoded[n : n + 2], 16) ^ key) for n in range(2, len(encoded), 2))


def cf_emails(html: str) -> list[str]:
    out: list[str] = []
    for encoded in re.findall(r"(?:data-cfemail|email-protection#)(?:=|\")?([0-9a-f]{6,})", html):
        try:
            decoded = cf_decode(encoded).lower()
        except Exception:
            continue
        if "@" in decoded and " " not in decoded:
            out.append(decoded)
    return out


def host_ok(host: str) -> bool:
    host = (host or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if not host or "." not in host:
        return False
    return not any(p in host for p in SKIP_HOST_PARTS)


def listing_jobs() -> list[dict[str, str]]:
    client = httpx.Client(headers={"User-Agent": UA}, follow_redirects=True, timeout=30)
    first = client.get("https://jsgurujobs.com/jobs").text
    pages = {int(x) for x in re.findall(r"/jobs\?page=(\d+)", first)}
    last = max(pages) if pages else 1
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for page in range(1, last + 1):
        html = first if page == 1 else client.get(f"https://jsgurujobs.com/jobs?page={page}").text
        for jid, title, company in CARD_RE.findall(html):
            company = unescape(company).strip()
            title = unescape(title).strip()
            if not company or company.lower() in {"default company"}:
                continue
            key = f"{jid}:{company.lower()}"
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "id": jid,
                    "title": title,
                    "company": company,
                    "url": f"https://jsgurujobs.com/jobs/{jid}",
                }
            )
        print(f"  listing page {page}/{last}  jobs {len(rows)}", flush=True)
        time.sleep(0.08)
    client.close()
    return rows


def directory_domain(name: str) -> str:
    key = re.sub(r"\s+", " ", name.strip().lower())
    if key in WELL_KNOWN_COMPANY_DOMAINS:
        return WELL_KNOWN_COMPANY_DOMAINS[key]
    for listed, domain, *_rest in COMPANY_DIRECTORY:
        listed_n = listed.strip().lower()
        if listed_n == key or listed_n.startswith(key + " ") or key.startswith(listed_n):
            return domain
    return ""


def company_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def host_matches_company(host: str, name: str) -> bool:
    host = host.lower()
    if host.endswith(".edu") or ".ac." in host:
        return False
    slug = company_slug(name)
    first = host.split(".")[0].replace("-", "")
    if not slug or len(slug) < 5:
        return False
    if slug == first:
        return True
    shorter, longer = (slug, first) if len(slug) <= len(first) else (first, slug)
    if len(shorter) >= 6 and longer.startswith(shorter) and len(shorter) / len(longer) >= 0.75:
        return True
    return False


def clearbit_domain(name: str) -> str:
    try:
        r = httpx.get(
            "https://autocomplete.clearbit.com/v1/companies/suggest",
            params={"query": name},
            headers={"User-Agent": UA},
            timeout=20,
        )
        items = r.json() if r.status_code == 200 else []
    except Exception:
        items = []
    namel = name.strip().lower()
    ranked: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        host = (item.get("domain") or "").lower().strip()
        label = (item.get("name") or "").strip().lower()
        if not host_ok(host):
            continue
        if label == namel:
            ranked.append(host)
        elif host_matches_company(host, name):
            ranked.append(host)
    return ranked[0] if ranked else ""


def probe_slug_domain(name: str) -> str:
    slug = company_slug(name)
    if len(slug) < 5:
        return ""
    hyphen = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    hosts = []
    for tld in (".com", ".io", ".ai", ".dev", ".co", ".app"):
        hosts.append(slug + tld)
        if "-" in hyphen:
            hosts.append(hyphen + tld)
    client = httpx.Client(headers={"User-Agent": UA}, follow_redirects=True, timeout=8)
    try:
        for host in list(dict.fromkeys(hosts))[:8]:
            for url in (f"https://{host}", f"https://www.{host}"):
                try:
                    r = client.get(url)
                except Exception:
                    continue
                if r.status_code >= 400 or not r.text:
                    continue
                title_m = re.search(r"<title[^>]*>(.*?)</title>", r.text, re.I | re.S)
                title = unescape(re.sub("<[^>]+>", "", title_m.group(1) if title_m else "")).lower()
                if host_matches_company(host, name) and (
                    slug in title.replace(" ", "") or name.lower() in title or host_matches_company(host, name)
                ):
                    if slug in re.sub(r"[^a-z0-9]+", "", title) or name.lower().split()[0] in title:
                        return host
    finally:
        client.close()
    return ""


def search_domain(name: str) -> str:
    return clearbit_domain(name) or probe_slug_domain(name)


def scrape_domain(client: HttpClient, domain: str) -> list[str]:
    found: list[str] = []
    for path in PK_CONTACT_PATHS[:8]:
        html = client.get_html(f"https://www.{domain}{path}") or client.get_html(f"https://{domain}{path}")
        if not html:
            continue
        blob = html_to_text(html) + " " + html
        emails = extract_emails(blob) + cf_emails(html)
        for email in emails:
            local, _, host = email.partition("@")
            if local in SKIP_LOCAL:
                continue
            if host == domain or host.endswith("." + domain):
                found.append(email)
            elif any(tok in local for tok in ("hr", "career", "recruit", "talent", "people", "hiring", "job")):
                if host not in {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com"}:
                    found.append(email)
        if found:
            break
        time.sleep(0.05)
    return list(dict.fromkeys(found))


def main() -> None:
    print("Crawling JSGuru job listings…", flush=True)
    jobs = listing_jobs()
    companies: dict[str, dict[str, str]] = {}
    for job in jobs:
        key = job["company"].strip().lower()
        if key not in companies:
            companies[key] = job
        elif any(tok in job["title"].lower() for tok in ("front", "react", "next", "full stack", "fullstack")):
            companies[key] = job
    print(f"unique companies: {len(companies)}  (from {len(jobs)} jobs)", flush=True)

    sent_e, sent_c = already_sent()
    sent_e = {e.strip().lower() for e in sent_e}
    sent_d = {e.split("@", 1)[1] for e in sent_e if "@" in e}
    bounced = bounced_emails()

    resolved: list[tuple[str, str, dict[str, str]]] = []
    for key, job in companies.items():
        name = job["company"]
        if any(b == key or b in key for b in BLOCKED_COMPANIES):
            continue
        if key in sent_c:
            continue
        domain = directory_domain(name)
        if not domain:
            domain = search_domain(name)
            time.sleep(0.12)
        if not domain or domain in BLOCKED_DOMAINS or domain in sent_d:
            print(f"  NO DOMAIN  {name}", flush=True)
            continue
        resolved.append((name, domain, job))
        print(f"  DOMAIN  {name:40} {domain}", flush=True)
    print(f"domains resolved: {len(resolved)}", flush=True)

    http = HttpClient(timeout=12.0)
    candidates: list[dict[str, str]] = []
    seen_email: set[str] = set()
    seen_dom: set[str] = set()
    try:
        for name, domain, job in resolved:
            if domain in seen_dom or domain in sent_d:
                continue
            emails = scrape_domain(http, domain)
            picked = pick_hr_email(emails)
            print(f"  SCRAPE {name:40} {domain:28} {picked or '-'}", flush=True)
            if not picked or picked in sent_e or picked in bounced or picked in seen_email:
                continue
            local = picked.split("@", 1)[0]
            if local in SKIP_LOCAL:
                continue
            seen_email.add(picked)
            seen_dom.add(domain)
            candidates.append(
                {
                    "Company": name,
                    "Region": "Remote",
                    "City": "",
                    "HR / Recruiter Email": picked,
                    "Email Source": "company website",
                    "Other Emails": "; ".join(emails[:6]),
                    "Domain": domain,
                    "Careers / Apply URL": job["url"],
                    "Sample Role": job["title"],
                    "Location Clause": "",
                    "Letter": "",
                    "SMTP Verification": "",
                }
            )
    finally:
        http.close()

    print(f"published emails to probe: {len(candidates)}", flush=True)
    sent_e, _sent_c = already_sent()
    sent_e = {e.strip().lower() for e in sent_e}
    ready: list[dict[str, str]] = []
    seen_ready: set[str] = set()
    for row in candidates:
        email = row["HR / Recruiter Email"].strip().lower()
        row["HR / Recruiter Email"] = email
        if email in sent_e or email in seen_ready:
            print(f"  SKIP already sent   {email}  ({row['Company']})", flush=True)
            continue
        ok, detail = verify_mailbox(email)
        row["SMTP Verification"] = (detail or "")[:400]
        print(f"  SMTP {'OK' if ok else 'NO '} {email:48} {row['Company'][:22]:22} {detail[:70]}", flush=True)
        if ok:
            seen_ready.add(email)
            ready.append(row)

    out = ROOT / "output" / "emails_jsguru_2026-08-19.csv"
    fields = [
        "Company",
        "Region",
        "City",
        "HR / Recruiter Email",
        "Email Source",
        "Other Emails",
        "Domain",
        "Careers / Apply URL",
        "Sample Role",
        "Location Clause",
        "Letter",
        "SMTP Verification",
    ]
    with out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(ready)
    print(f"READY {len(ready)} -> {out}", flush=True)
    for row in ready:
        print(f"  SENDABLE {row['HR / Recruiter Email']} ({row['Company']}) [{row['Sample Role']}]", flush=True)


if __name__ == "__main__":
    main()
