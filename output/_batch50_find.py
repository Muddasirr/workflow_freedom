#!/usr/bin/env python3
"""Find published hiring emails from job boards + directory, SMTP-verify, write CSV for 50+ sends."""
from __future__ import annotations

import csv
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "outreach"))

from job_hunter.config import PK_CONTACT_PATHS  # noqa: E402
from job_hunter.directory import COMPANY_DIRECTORY, JUNK_LOCAL  # noqa: E402
from job_hunter.emails import pick_hr_email  # noqa: E402
from job_hunter.http import HttpClient  # noqa: E402
from job_hunter.sources import fetch_all  # noqa: E402
from job_hunter.textutil import extract_emails, html_to_text  # noqa: E402
from send_emails import (  # noqa: E402
    BLOCKED_COMPANIES,
    BLOCKED_DOMAINS,
    SKIP_LOCAL,
    WEAK_LOCAL,
    already_sent,
)
from smtp_verify import bounced_emails, verify_mailbox  # noqa: E402

OUT = ROOT / "output" / "emails_batch50_2026-08-20.csv"
HIRING_TOKS = ("career", "recruit", "talent", "hiring", "people", "job", "hr", "join", "apply", "team")
EXTRA_SKIP_LOCAL = {
    "feedback",
    "compliance",
    "fraud",
    "gdpr",
    "marketing",
    "mktg",
    "newsletter",
    "press",
    "media",
    "sales",
    "support",
    "help",
    "billing",
    "legal",
    "privacy",
    "noreply",
    "no-reply",
    "notices",
    "service",
    "customerservice",
    "partnerships",
    "partners",
    "security",
    "investors",
    "ir",
}


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


def domain_from_url(url: str) -> str:
    host = (urlparse(url or "").hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def is_blocked_company(name: str) -> bool:
    key = (name or "").strip().lower()
    return any(b == key or b in key for b in BLOCKED_COMPANIES)


def usable_email(email: str) -> bool:
    email = (email or "").strip().lower()
    if "@" not in email:
        return False
    local, _, host = email.partition("@")
    if local in SKIP_LOCAL or local in EXTRA_SKIP_LOCAL:
        return False
    if any(j in local for j in JUNK_LOCAL):
        return False
    if host in BLOCKED_DOMAINS or host.endswith(".codet.ai"):
        return False
    if host in {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "proton.me", "icloud.com"}:
        return False
    hiringish = any(tok in local for tok in HIRING_TOKS) or local.startswith("hr")
    named = "." in local and not local.startswith("info.")
    weak_ok = local in WEAK_LOCAL  # accepted later with trusted source
    if not hiringish and not named and local not in {"hello", "hi", "contact", "info", "team", "join", "apply", "founders", "founder"} and not weak_ok:
        # allow opportunities / nextbit style from hiring posts
        if local in {"opportunities", "nextbit", "business"}:
            return True
        return False
    return True


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
            if local in SKIP_LOCAL or local in EXTRA_SKIP_LOCAL:
                continue
            if host == domain or host.endswith("." + domain):
                found.append(email.lower())
            elif any(tok in local for tok in HIRING_TOKS):
                if host not in {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com"}:
                    found.append(email.lower())
        if any(any(tok in e.split("@")[0] for tok in HIRING_TOKS) for e in found):
            break
        if found and path in {"/impressum", "/imprint", "/contact", "/contact-us", "/careers", "/"}:
            break
    return list(dict.fromkeys(found))


def main() -> None:
    sent_e, sent_c = already_sent()
    sent_d = {e.split("@", 1)[1] for e in sent_e if "@" in e}
    bounced = bounced_emails()

    candidates: dict[str, dict[str, str]] = {}  # email -> row

    def add(company: str, email: str, domain: str, source: str, role: str = "", url: str = "", region: str = "Remote") -> None:
        email = email.strip().lower()
        company = company.strip()
        domain = (domain or email.split("@", 1)[1]).lower()
        if not usable_email(email):
            return
        if email in sent_e or email in bounced or email in candidates:
            return
        if company.lower() in sent_c or is_blocked_company(company):
            return
        if domain in sent_d or domain in BLOCKED_DOMAINS:
            return
        # one per domain
        if any(r["Domain"] == domain for r in candidates.values()):
            return
        candidates[email] = {
            "Company": company,
            "Region": region,
            "City": "",
            "HR / Recruiter Email": email,
            "Email Source": source,
            "Other Emails": "",
            "Domain": domain,
            "Careers / Apply URL": url,
            "Sample Role": role,
            "Location Clause": " (remote)" if region == "Remote" else "",
            "Letter": "",
            "SMTP Verification": "",
        }

    # 1) Known published emails from directory (no scrape yet)
    print("Loading directory known emails…", flush=True)
    for name, domain, region, city, known in COMPANY_DIRECTORY:
        if domain.lower() in sent_d or name.lower() in sent_c or is_blocked_company(name):
            continue
        for email in known:
            add(name, email, domain, "known company contact", region=region)

    # 2) Job boards — emails in postings
    print("Fetching job boards…", flush=True)
    client = HttpClient(timeout=20.0)
    try:
        jobs = fetch_all(client)
    except Exception as exc:
        print(f"  board fetch error: {exc}", flush=True)
        jobs = []
    print(f"  jobs: {len(jobs)}", flush=True)
    board_companies: dict[str, tuple[str, str, str]] = {}  # domain -> (company, role, url)
    for job in jobs:
        blob = f"{job.description or ''}\n{job.url or ''}\n{job.company or ''}"
        emails = extract_emails(blob)
        company = (job.company or "").strip()
        if not company:
            continue
        domain = ""
        for e in emails:
            host = e.split("@", 1)[1]
            if host not in {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com"}:
                domain = host
                break
        if not domain:
            # try company website field if present
            for attr in ("company_url", "url", "apply_url"):
                val = getattr(job, attr, "") or ""
                d = domain_from_url(val)
                if d and "." in d and d not in {
                    "remoteok.com",
                    "remotive.com",
                    "arbeitnow.com",
                    "jobicy.com",
                    "himalayas.app",
                    "linkedin.com",
                }:
                    domain = d
                    break
        role = (job.title or "").strip()
        url = (job.url or "").strip()
        for email in emails:
            add(company, email, domain or email.split("@", 1)[1], "job posting", role=role, url=url)
        if domain and domain not in sent_d and company.lower() not in sent_c:
            board_companies.setdefault(domain, (company, role, url))

    print(f"  after boards: {len(candidates)} candidates", flush=True)

    # 3) Scrape unsent directory + board company sites for published emails
    scrape_targets: list[tuple[str, str, str, str, str]] = []
    seen_dom: set[str] = set()
    for name, domain, region, city, known in COMPANY_DIRECTORY:
        d = domain.lower()
        if d in sent_d or d in seen_dom or name.lower() in sent_c or is_blocked_company(name):
            continue
        if any(r["Domain"] == d for r in candidates.values()):
            continue
        seen_dom.add(d)
        scrape_targets.append((name, d, region, "", f"https://{d}/careers"))
    for domain, (company, role, url) in board_companies.items():
        if domain in seen_dom or domain in sent_d or is_blocked_company(company):
            continue
        if any(r["Domain"] == domain for r in candidates.values()):
            continue
        seen_dom.add(domain)
        scrape_targets.append((company, domain, "Remote", role, url or f"https://{domain}/careers"))

    # Cap scrape volume for speed — prioritize Europe/Remote/MENA/PK
    scrape_targets = scrape_targets[:280]
    print(f"Scraping {len(scrape_targets)} company sites…", flush=True)

    def one(item: tuple[str, str, str, str, str]) -> tuple[str, str, str, str, str, list[str]]:
        name, domain, region, role, url = item
        local = HttpClient(timeout=10.0)
        try:
            emails = scrape_domain(local, domain)
        finally:
            local.close()
        return name, domain, region, role, url, emails

    scraped_hits = 0
    with ThreadPoolExecutor(max_workers=14) as pool:
        futs = [pool.submit(one, t) for t in scrape_targets]
        done = 0
        for fut in as_completed(futs):
            done += 1
            name, domain, region, role, url, emails = fut.result()
            picked = pick_hr_email(emails)
            if done % 25 == 0 or picked:
                print(f"  [{done}/{len(scrape_targets)}] {name[:32]:32} {domain:28} {picked or '-'}", flush=True)
            if not picked:
                continue
            scraped_hits += 1
            add(name, picked, domain, "company website", role=role, url=url, region=region)

    print(f"scrape hits with email: {scraped_hits}; candidates: {len(candidates)}", flush=True)

    # 4) SMTP verify (stop early once we have ~70 ok — buffer over 50)
    rows = list(candidates.values())
    # Prefer hiring-ish locals
    def rank(r: dict[str, str]) -> tuple[int, str]:
        local = r["HR / Recruiter Email"].split("@", 1)[0]
        score = 0
        if any(t in local for t in ("career", "recruit", "talent", "hiring", "hr", "job", "people", "join")):
            score -= 10
        if local in WEAK_LOCAL:
            score += 5
        return (score, r["Company"].lower())

    rows.sort(key=rank)
    ready: list[dict[str, str]] = []
    print(f"SMTP-probing up to {min(len(rows), 160)}…", flush=True)
    for i, row in enumerate(rows[:160], 1):
        email = row["HR / Recruiter Email"]
        ok, detail = verify_mailbox(email)
        row["SMTP Verification"] = (detail or "")[:400]
        print(f"  SMTP {'OK' if ok else 'NO '} [{i}] {email:46} {row['Company'][:20]:20} {detail[:60]}", flush=True)
        if ok:
            ready.append(row)
        if len(ready) >= 70:
            print("enough SMTP-ok (70+)", flush=True)
            break
        time.sleep(0.05)

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
    with OUT.open("w", encoding="utf-8-sig", newline="") as h:
        w = csv.DictWriter(h, fieldnames=fields)
        w.writeheader()
        w.writerows(ready)
    print(f"READY {len(ready)} -> {OUT}", flush=True)
    for r in ready:
        print(f"  SENDABLE {r['HR / Recruiter Email']} ({r['Company']})", flush=True)


if __name__ == "__main__":
    main()
