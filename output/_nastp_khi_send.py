#!/usr/bin/env python3
"""NASTP Karachi outreach: verified emails only, no trainee/intern programs."""
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

from job_hunter.http import HttpClient  # noqa: E402
from job_hunter.textutil import extract_emails, html_to_text  # noqa: E402
from send_emails import (  # noqa: E402
    BLOCKED_DOMAINS,
    SAFE_LOCAL,
    SKIP_LOCAL,
    already_sent,
    log_sent,
    render_body,
    subject_for,
)
from smtp_verify import bounced_emails, verify_mailbox  # noqa: E402

OUT_CSV = ROOT / "output" / "emails_nastp_khi_2026-08-31.csv"
SENT_LOG = ROOT / "outreach" / "sent_log.csv"
RESUME = ROOT / "Muhammad_Muddasir_Resume.pdf"
FROM = os.getenv("GMAIL_ADDRESS", "").strip()
PASS = os.getenv("GMAIL_APP_PASSWORD", "").strip()
DELAY = 52.0

# NASTP Silicon / Silicon Valley Karachi — software/product companies only.
# Excluded: Ashrei Tech Academy (trainee), internship-only listings.
NASTP_COMPANIES: list[dict[str, str]] = [
    {"company": "DynaSys Network", "domain": "dynasysnetworks.com", "role": "Software Engineer", "posted": "info@dynasysnetworks.com"},
    {"company": "Shispare", "domain": "shispare.com", "role": "Software Engineer", "posted": "info@shispare.com"},
    {"company": "Woot Tech", "domain": "woot-tech.com", "role": "Software Engineer", "posted": "info@woot-tech.com"},
    {"company": "Asani.io", "domain": "asani.io", "role": "Software Engineer", "posted": "hello@asani.io"},
    {"company": "Techbey", "domain": "techbey.pk", "role": "Software Engineer"},
    {"company": "Peekaboo Guru", "domain": "peekaboo.guru", "role": "Software Engineer", "posted": "contact@peekaboo.guru"},
    {"company": "Tapsys", "domain": "tapsys.pk", "role": "Software Engineer"},
    {"company": "FetchSky", "domain": "fetchsky.com", "role": "Software Engineer"},
    {"company": "Future Technologies", "domain": "futuretech.com.pk", "role": "Software Engineer"},
    {"company": "Avanza Premier Payment Services", "domain": "avanza.com.pk", "role": "Software Engineer"},
    {"company": "Crystal System Solution", "domain": "crystalsystem.com.pk", "role": "Software Engineer"},
    {"company": "Integrated System Engineering", "domain": "ise.com.pk", "role": "Software Engineer"},
    {"company": "AKS iQ", "domain": "aksiq.com", "role": "Software Engineer"},
    {"company": "Knowledge Hub Global", "domain": "knowledgehub.global", "role": "Software Engineer"},
    {"company": "Rely", "domain": "rely.co", "role": "Software Engineer"},
    {"company": "Softech Worldwide", "domain": "softechww.com", "role": "Software Engineer"},
    {"company": "Systems Limited", "domain": "systemsltd.com", "role": "Software Engineer"},
    {"company": "Novocall", "domain": "novocall.co", "role": "Software Engineer"},
    {"company": "Delve Deeper", "domain": "delvedeeper.com", "role": "Software Engineer"},
]

TRAINING_SKIP = re.compile(
    r"\b(trainee|internship|intern\b|apprentice|graduate\s+trainee|bootcamp|"
    r"training\s+program|academy\s+only|nastp\s+intern)\b",
    re.I,
)


def is_training_company(company: str, role: str = "") -> bool:
    blob = f"{company} {role}"
    if TRAINING_SKIP.search(blob):
        return True
    # Ashrei runs an academy — already contacted; skip any pure academy brand.
    if re.search(r"\bacademy\b", company, re.I) and "tech" not in company.lower():
        return True
    return False


def usable(email: str, sent_e: set[str], bounced: set[str]) -> bool:
    email = email.lower().strip()
    if not email or email in sent_e or email in bounced or "@" not in email:
        return False
    local, _, host = email.partition("@")
    if local in SKIP_LOCAL or host in BLOCKED_DOMAINS:
        return False
    if host in {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "linkedin.com"}:
        return False
    hiring = any(
        t in local
        for t in ("career", "job", "hr", "talent", "recruit", "hello", "hi", "contact", "info", "apply", "team", "join")
    )
    return hiring or local in SAFE_LOCAL or "." in local


def find_email(row: dict, sent_e: set[str], bounced: set[str], client: HttpClient) -> tuple[str, str] | None:
    domain = row["domain"]
    posted = (row.get("posted") or "").strip().lower()
    candidates: list[str] = []
    if posted and usable(posted, sent_e, bounced):
        candidates.append(posted)
    for path in ("/careers", "/jobs", "/contact", "/about", "/"):
        for base in (f"https://www.{domain}", f"https://{domain}"):
            html = client.get_html(f"{base}{path}") or ""
            if not html:
                continue
            for e in extract_emails(html_to_text(html) + " " + html):
                e = e.lower()
                if usable(e, sent_e, bounced) and (e.endswith("@" + domain) or domain in e.split("@")[-1]):
                    candidates.append(e)
            if candidates:
                break
        if candidates:
            break
    candidates = list(dict.fromkeys(candidates))
    posted_set = {posted} if posted else set()
    for email in sorted(candidates, key=lambda e: (0 if e in posted_set else 1, e)):
        ok, detail = verify_mailbox(email)
        if ok:
            return email, "strict-valid"
        if email in posted_set and "user unknown" not in detail.lower() and "does not exist" not in detail.lower():
            return email, "user-forced published"
    for local in ("careers", "jobs", "hr", "hello", "hi", "info", "contact", "talent"):
        email = f"{local}@{domain}"
        if not usable(email, sent_e, bounced):
            continue
        ok, detail = verify_mailbox(email)
        if ok:
            return email, "strict-valid"
    return None


def letter_body(company: str, role: str) -> str:
    """Karachi/NASTP cold email — product engineer, not trainee application."""
    try:
        from job_hunter.agent_letter import agent_enabled, write_cover_letter

        if agent_enabled():
            return write_cover_letter(
                company=company,
                role=role,
                location="Karachi (NASTP)",
                summary=(
                    f"{company} is based at NASTP Silicon, Karachi. Hiring for {role}. "
                    "Full-time software/product engineering (not internship or trainee). "
                    "Stack: React, Next.js, TypeScript, Python, product engineering."
                ),
                skills="Next.js, React, TypeScript, Python, full-stack",
                apply_url="",
            )
    except Exception:
        pass
    template = (ROOT / "emailll_proof.txt").read_text(encoding="utf-8")
    loc = " (Karachi / NASTP)"
    return render_body(template, company, role=role, location_clause=loc, letter_name="emailll_proof.txt")


def send_one(*, to: str, company: str, body: str, subject: str) -> None:
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
    log_sent(to, company, "sent", letter="nastp_khi_cursor", subject=subject)


def main() -> None:
    if not FROM or not PASS or not RESUME.exists():
        raise SystemExit("Gmail/resume missing")

    sent_e, sent_c = already_sent()
    bounced = bounced_emails()
    client = HttpClient()
    queue: list[dict] = []

    try:
        for row in NASTP_COMPANIES:
            company = row["company"]
            role = row.get("role") or "Software Engineer"
            if is_training_company(company, role):
                print(f"SKIP trainee/training: {company}", flush=True)
                continue
            if company.lower() in sent_c:
                print(f"SKIP already contacted: {company}", flush=True)
                continue
            print(f"→ {company} ({row['domain']})", flush=True)
            hit = find_email(row, sent_e, bounced, client)
            if not hit:
                print("  no verified email", flush=True)
                continue
            email, smtp_tag = hit
            if email in sent_e:
                continue
            queue.append({**row, "email": email, "smtp": smtp_tag})
            print(f"  queued {email} [{smtp_tag}]", flush=True)
    finally:
        client.close()

    fields = [
        "Company", "Region", "City", "HR / Recruiter Email", "Email Source",
        "Domain", "Sample Role", "SMTP Verification", "Letter",
    ]
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for q in queue:
            w.writerow(
                {
                    "Company": q["company"],
                    "Region": "Karachi",
                    "City": "NASTP Karachi",
                    "HR / Recruiter Email": q["email"],
                    "Email Source": "nastp batch scrape",
                    "Domain": q["domain"],
                    "Sample Role": q.get("role") or "Software Engineer",
                    "SMTP Verification": q["smtp"],
                    "Letter": "nastp_khi_cursor",
                }
            )
    print(f"\nQueue: {len(queue)} → {OUT_CSV}", flush=True)

    sent_n = 0
    for q in queue:
        company = q["company"]
        role = q.get("role") or "Software Engineer"
        email = q["email"]
        subj = subject_for(company, role)
        try:
            print(f"\nLetter for {company}…", flush=True)
            body = letter_body(company, role)
            send_one(to=email, company=company, body=body, subject=subj)
            sent_n += 1
            sent_e.add(email)
            print(f"SENT [{sent_n}] {email} ({company})", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL {email}: {exc}", flush=True)
            log_sent(email, company, "failed", str(exc)[:200], letter="nastp_khi_cursor", subject=subj)
            if any(x in str(exc).lower() for x in ("quota", "rate", "blocked", "auth", "421", "454")):
                break
        wait = max(42.0, DELAY + random.uniform(-8, 15))
        print(f"wait {wait:.0f}s…", flush=True)
        time.sleep(wait)

    print(f"\nDONE. NASTP Karachi sent={sent_n}", flush=True)


if __name__ == "__main__":
    main()
