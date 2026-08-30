#!/usr/bin/env python3
"""Batch apply pipeline: find PK-friendly jobs → cover-letter email → find contact → send.

Combines:
  - job_hunter sources + matcher (Pakistan-friendly / remote worldwide)
  - ai-job-search candidate profile for tailored cover-letter email bodies
  - outreach SMTP send + resume attachment

Target: 50+ successful sends. Hunter optional (often exhausted).
"""
from __future__ import annotations

import csv
import os
import random
import re
import smtplib
import ssl
import sys
import time
from datetime import datetime, timezone
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "outreach"))
load_dotenv(ROOT / ".env")

from job_hunter.directory import COMPANY_DIRECTORY, JUNK_LOCAL  # noqa: E402
from job_hunter.emails import (  # noqa: E402
    WELL_KNOWN_COMPANY_DOMAINS,
    resolve_company_domain,
)
from job_hunter.http import HttpClient  # noqa: E402
from job_hunter.matcher import is_keepable, score_job  # noqa: E402
from job_hunter.models import Job  # noqa: E402
from job_hunter.sources import fetch_all  # noqa: E402
from job_hunter.textutil import extract_emails, html_to_text  # noqa: E402
from send_emails import (  # noqa: E402
    BLOCKED_COMPANIES,
    BLOCKED_DOMAINS,
    SAFE_LOCAL,
    SKIP_LOCAL,
    already_sent,
)
from smtp_verify import verify_mailbox  # noqa: E402

OUT_CSV = ROOT / "output" / "emails_batch50_apply_2026-08-29.csv"
SENT_LOG = ROOT / "outreach" / "sent_log.csv"
RESUME = ROOT / "Muhammad_Muddasir_Resume.pdf"
TRACKER = ROOT / "ai-job-search" / "job_search_tracker.csv"
FROM = os.getenv("GMAIL_ADDRESS", "").strip()
PASS = os.getenv("GMAIL_APP_PASSWORD", "").strip()

TARGET_SENDS = 55
DELAY = 48.0
DAILY_CAP = 80
GUESS_LOCALS = ("careers", "jobs", "hr", "talent", "recruiting", "people", "join", "cv", "apply")

EXTRA_DOMAINS = {
    "proxify ab": "proxify.io",
    "proxify": "proxify.io",
    "a.team": "a.team",
    "base.com": "base.com",
    "huzzle": "huzzle.app",
    "clickhouse": "clickhouse.com",
    "sticker mule": "stickermule.com",
    "fueled": "fueled.com",
    "cohere": "cohere.com",
    "highlevel": "gohighlevel.com",
    "camunda": "camunda.com",
    "socket": "socket.dev",
    "vonage": "vonage.com",
    "lithic": "lithic.com",
    "descript": "descript.com",
    "hygraph": "hygraph.com",
    "memberspace": "memberspace.com",
    "crost ai": "crost.ai",
    "crost": "crost.ai",
}

SKIP_US_ONLY = {
    "coinbase", "dropbox", "airbnb", "reddit", "datadog", "twilio", "gusto",
    "canonical", "stripe", "vercel", "toptal", "andela", "gitlab", "openai",
    "anthropic", "cloudflare", "airtable", "lemon.io", "n8n", "huggingface",
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def role_bucket(title: str) -> str:
    t = (title or "").lower()
    if any(k in t for k in ("ai ", "llm", "machine learning", "ml engineer", "genai", "agent")):
        return "ai"
    if any(k in t for k in ("frontend", "front-end", "front end", "react", "next.js", "ui engineer")):
        return "frontend"
    if any(k in t for k in ("backend", "java", "golang", "go engineer", "api engineer")):
        return "backend"
    if any(k in t for k in ("full stack", "full-stack", "fullstack", "product engineer", "software engineer")):
        return "fullstack"
    return "fullstack"


def cover_letter_email(*, company: str, role: str, location: str, bucket: str) -> str:
    """Short Reddit-style cover letter as email body (ai-job-search profile facts)."""
    loc = f" ({location})" if location else ""
    if bucket == "ai":
        proof = (
            "At Codet.ai I build LLM/workflow features: an n8n-style trigger → condition → action canvas "
            "and an in-app assistant. Strongest proof: AutoCloudEngineerAgent (LangGraph) — proposes infra, "
            "deploys only to a Kubernetes canary, benches, then rejects / rolls back / promotes under hard safety constraints."
        )
    elif bucket == "frontend":
        proof = (
            "At Codet.ai I ship product frontend in Next.js, React, and TypeScript: a drag-and-drop no-code "
            "canvas (trigger → condition → action) and an in-app AI assistant beside the editor — nodes, edges, live validation."
        )
    elif bucket == "backend":
        proof = (
            "I ship APIs and product systems in Python/Node and Java when needed. At Euronet I built Java payment "
            "APIs (ISO 8583, JWT, PostgreSQL). Also designed AutoCloudEngineerAgent: propose infra → canary-only K8s → bench → promote/rollback."
        )
    else:
        proof = (
            "I'm a full-stack product engineer at Codet.ai (Next.js/React/TypeScript + Python agents). "
            "I shipped a no-code builder with drag-and-drop workflows and an in-app AI assistant, plus "
            "AutoCloudEngineerAgent (LangGraph control plane with Kubernetes canary deploys)."
        )

    return (
        f"Hi {company} team,\n\n"
        f"Saw the {role} role{loc}. {proof}\n\n"
        f"If you're still hiring for {role}, open to a 15-minute call this week? Resume attached — "
        f"more at muddasirrizwan.com. Remote from Karachi (UTC+5) / Pakistan-friendly.\n\n"
        f"Muhammad Muddasir\n"
        f"+92-3249867842 · muddasirrizwan9@gmail.com · muddasirrizwan.com\n"
    )


def subject_for(company: str, role: str) -> str:
    subj = f"{role} at {company}"
    if len(subj) > 58:
        subj = f"{role[:40]} — {company}"[:58]
    return subj


def resolve_domain(company: str, url: str = "", existing: str = "") -> str:
    if existing and not any(
        x in existing for x in ("weworkremotely", "jobicy", "remotive", "greenhouse", "lever.co", "linkedin.com")
    ):
        return existing.lower()
    key = _norm(company)
    if key in EXTRA_DOMAINS:
        return EXTRA_DOMAINS[key]
    if key in WELL_KNOWN_COMPANY_DOMAINS:
        return WELL_KNOWN_COMPANY_DOMAINS[key]
    job = Job(source="batch", source_id="", title="", company=company, url=url)
    domain = resolve_company_domain(job)
    if domain and not any(x in domain for x in ("weworkremotely", "jobicy", "remotive", "greenhouse", "lever.co")):
        return domain
    for listed, dom, *_rest in COMPANY_DIRECTORY:
        if _norm(listed) == key:
            return dom.lower()
    return ""


def usable_email(email: str) -> bool:
    email = (email or "").strip().lower()
    if "@" not in email:
        return False
    local, _, host = email.partition("@")
    if local in SKIP_LOCAL or any(j in local for j in JUNK_LOCAL):
        return False
    if host in BLOCKED_DOMAINS or host.endswith(".codet.ai"):
        return False
    if host in {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "proton.me"}:
        return False
    hiringish = any(t in local for t in ("career", "recruit", "talent", "hiring", "people", "job", "cv", "hr"))
    if local in SAFE_LOCAL or hiringish:
        return True
    if "." in local or (local.isalpha() and len(local) >= 3):
        return True
    return local in {"hello", "hi", "join", "apply", "team", "info"}


def scrape_domain(domain: str) -> list[str]:
    client = HttpClient()
    found: list[str] = []
    try:
        for path in ("/careers", "/jobs", "/about", "/contact", "/contact-us", "/"):
            html = client.get_html(f"https://www.{domain}{path}") or client.get_html(f"https://{domain}{path}")
            if not html:
                continue
            for email in extract_emails(html_to_text(html) + " " + html):
                email = email.lower()
                if usable_email(email):
                    host = email.split("@", 1)[1]
                    if host == domain or host.endswith("." + domain) or any(
                        t in email.split("@")[0] for t in ("career", "job", "hr", "talent", "recruit")
                    ):
                        found.append(email)
            if any(any(t in e.split("@")[0] for t in ("career", "job", "hr", "talent")) for e in found):
                break
    finally:
        client.close()
    return list(dict.fromkeys(found))


def find_email(domain: str, posted: str, sent_e: set[str]) -> tuple[str, str] | None:
    """Return (email, smtp_tag) or None."""
    candidates: list[tuple[str, str]] = []
    if posted and usable_email(posted) and posted not in sent_e:
        candidates.append((posted.lower(), "job posting"))

    # SMTP-strict guesses first (fast)
    for local in GUESS_LOCALS:
        email = f"{local}@{domain}"
        if email in sent_e:
            continue
        ok, detail = verify_mailbox(email)
        if ok:
            return email, "strict-valid"
        if "catch-all" in detail.lower():
            # Stop guessing on catch-all; only use posted/named later
            break

    # Scrape
    for email in scrape_domain(domain):
        if email in sent_e:
            continue
        ok, detail = verify_mailbox(email)
        if ok:
            return email, "strict-valid"

    # Posted on catch-all — allow if published
    if candidates:
        email, src = candidates[0]
        return email, "user-forced"

    return None


def collect_jobs() -> list[dict[str, str]]:
    print("Fetching job boards…", flush=True)
    client = HttpClient()
    try:
        raw = fetch_all(client)
    finally:
        client.close()
    print(f"Raw listings: {len(raw)}", flush=True)

    by_co: dict[str, dict[str, str]] = {}
    for job in raw:
        score_job(job)
        if not is_keepable(
            job,
            include_restricted=False,
            karachi_only=False,
            pakistan_friendly_only=True,
            junior_only=False,
        ):
            continue
        if job.pakistan_friendly != "Yes":
            continue
        # Prefer remote / Pakistan
        fit = (job.location_fit or "").lower()
        if "on-site outside" in fit:
            continue
        key = _norm(job.company)
        if not key or key in SKIP_US_ONLY:
            continue
        if any(b == key or b in key for b in BLOCKED_COMPANIES):
            continue
        domain = resolve_domain(job.company, job.url, job.company_domain)
        if domain.endswith(".codet.ai") or domain in BLOCKED_DOMAINS:
            continue
        title = job.title or "Software Engineer"
        prefer = role_bucket(title) in {"ai", "frontend", "fullstack", "backend"}
        prev = by_co.get(key)
        if prev and not prefer:
            continue
        by_co[key] = {
            "company": job.company.strip(),
            "role": title,
            "location": job.location or job.location_fit or "Remote",
            "fit": job.location_fit or "",
            "url": job.url or "",
            "domain": domain,
            "posted_email": (job.hr_email or "").lower(),
            "bucket": role_bucket(title),
            "score": str(job.score),
            "pk": job.pakistan_friendly,
        }

    # Directory supplement: Karachi/Pakistan/Remote known contacts not yet covered
    for name, domain, region, city, known in COMPANY_DIRECTORY:
        key = _norm(name)
        if key in by_co or key in SKIP_US_ONLY:
            continue
        if any(b == key or b in key for b in BLOCKED_COMPANIES):
            continue
        if region not in {"Karachi", "Pakistan", "Remote", "UAE", "MENA", "Europe", "Singapore", "Australia"}:
            continue
        emails = [e.strip().lower() for e in known if isinstance(e, str)]
        posted = ""
        for e in emails:
            if usable_email(e):
                posted = e
                break
        by_co[key] = {
            "company": name,
            "role": "Software Engineer",
            "location": f"{city} / {region}" if city else region,
            "fit": "Directory remote/PK",
            "url": f"https://{domain}",
            "domain": domain,
            "posted_email": posted,
            "bucket": "fullstack",
            "score": "5",
            "pk": "Yes" if region in {"Karachi", "Pakistan", "Remote"} else "Maybe",
        }

    rows = list(by_co.values())
    # Prefer higher score, then ones with posted email / domain
    rows.sort(key=lambda r: (-int(r.get("score") or 0), 0 if r.get("posted_email") else 1, r["company"]))
    print(f"Candidate companies: {len(rows)}", flush=True)
    return rows


def send_one(*, to: str, company: str, role: str, body: str, subject: str) -> None:
    msg = MIMEMultipart()
    msg["From"] = f"Muhammad Muddasir <{FROM}>"
    msg["To"] = to
    msg["Reply-To"] = FROM
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=FROM.split("@", 1)[-1])
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))
    part = MIMEApplication(RESUME.read_bytes(), _subtype="pdf")
    part.add_header("Content-Disposition", "attachment", filename="Muhammad_Muddasir_Resume.pdf")
    msg.attach(part)
    ctx = ssl.create_default_context()
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as smtp:
        smtp.starttls(context=ctx)
        smtp.login(FROM, PASS)
        smtp.sendmail(FROM, [to], msg.as_string())
    with SENT_LOG.open("a", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerow(
            [
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                company,
                to,
                "sent",
                "",
                "batch50_cover_email",
                "",
                subject,
            ]
        )


def main() -> None:
    if not FROM or not PASS:
        raise SystemExit("Gmail credentials missing")
    if not RESUME.exists():
        raise SystemExit(f"Missing resume: {RESUME}")

    sent_e, sent_c = already_sent()
    today = datetime.now(timezone.utc).date().isoformat()
    today_count = 0
    if SENT_LOG.exists():
        for row in csv.DictReader(SENT_LOG.open(encoding="utf-8-sig")):
            if row.get("status") == "sent" and (row.get("sent_at") or "").startswith(today):
                today_count += 1
    room = max(0, DAILY_CAP - today_count)
    target = min(TARGET_SENDS, room)
    print(f"Today sent={today_count} room={room} target={target}", flush=True)
    if target < 1:
        raise SystemExit("Daily cap reached")

    jobs = collect_jobs()
    queue: list[dict[str, str]] = []
    seen_emails: set[str] = set(sent_e)

    for row in jobs:
        if len(queue) >= target + 15:  # buffer for send failures
            break
        company = row["company"]
        company_key = _norm(company)
        if company_key in sent_c:
            print(f"  skip already contacted: {company}", flush=True)
            continue
        domain = row.get("domain") or resolve_domain(company, row.get("url") or "")
        if not domain:
            print(f"  skip no domain: {company}", flush=True)
            continue
        if domain in BLOCKED_DOMAINS:
            continue
        print(f"→ contact {company} ({domain})", flush=True)
        hit = find_email(domain, row.get("posted_email") or "", seen_emails)
        if not hit:
            print("  no email", flush=True)
            continue
        email, smtp_tag = hit
        if email in seen_emails:
            continue
        bucket = row.get("bucket") or "fullstack"
        body = cover_letter_email(
            company=company,
            role=row["role"],
            location=row.get("location") or "",
            bucket=bucket,
        )
        subj = subject_for(company, row["role"])
        queue.append(
            {
                **row,
                "domain": domain,
                "email": email,
                "smtp": smtp_tag,
                "body": body,
                "subject": subj,
                "letter_bucket": bucket,
            }
        )
        seen_emails.add(email)
        print(f"  queued {email} [{smtp_tag}] {subj[:50]}", flush=True)

    # Write CSV for audit
    fields = [
        "Company", "HR / Recruiter Email", "Sample Role", "Domain", "Location Clause",
        "SMTP Verification", "Letter", "Careers / Apply URL", "Pakistan Evidence", "Email Source",
    ]
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for q in queue:
            w.writerow(
                {
                    "Company": q["company"],
                    "HR / Recruiter Email": q["email"],
                    "Sample Role": q["role"],
                    "Domain": q["domain"],
                    "Location Clause": f" ({q.get('location')})",
                    "SMTP Verification": q["smtp"],
                    "Letter": q["letter_bucket"],
                    "Careers / Apply URL": q.get("url") or "",
                    "Pakistan Evidence": q.get("fit") or "",
                    "Email Source": "batch50 pipeline",
                }
            )
    print(f"Wrote queue CSV ({len(queue)}): {OUT_CSV}", flush=True)

    sent_n = 0
    for i, q in enumerate(queue, 1):
        if sent_n >= target:
            break
        email = q["email"]
        company = q["company"]
        try:
            send_one(
                to=email,
                company=company,
                role=q["role"],
                body=q["body"],
                subject=q["subject"],
            )
            sent_n += 1
            print(f"[{sent_n}/{target}] SENT {email} ({company}) {q['subject'][:45]}", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL {email}: {exc}", flush=True)
            with SENT_LOG.open("a", encoding="utf-8-sig", newline="") as f:
                csv.writer(f).writerow(
                    [
                        datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        company,
                        email,
                        "failed",
                        str(exc)[:200],
                        "batch50_cover_email",
                        "",
                        q["subject"],
                    ]
                )
            if any(x in str(exc).lower() for x in ("quota", "rate", "blocked", "auth", "421", "454")):
                print("Stopping on Gmail rate/auth issue", flush=True)
                break
        if sent_n < target and i < len(queue):
            wait = max(40.0, DELAY + random.uniform(-8, 18))
            print(f"  wait {wait:.0f}s…", flush=True)
            time.sleep(wait)

    # Update tracker lightly
    try:
        with TRACKER.open("a", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(
                [
                    datetime.now(timezone.utc).date().isoformat(),
                    f"BATCH50 ({sent_n} companies)",
                    "mixed",
                    "various",
                    "mixed",
                    "email",
                    "sent",
                    "",
                    "",
                    f"batch cover-letter emails sent={sent_n}",
                    "",
                    "",
                    "job_hunter+ai-job-search pipeline",
                    "",
                ]
            )
    except Exception:
        pass

    print(f"\nDONE. Sent {sent_n} applications.", flush=True)


if __name__ == "__main__":
    main()
