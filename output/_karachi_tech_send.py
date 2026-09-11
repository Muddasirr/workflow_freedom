#!/usr/bin/env python3
"""Karachi tech outreach: all software/product companies in Karachi (not NASTP-only)."""
from __future__ import annotations

import argparse
import csv
import os
import random
import re
import smtplib
import ssl
import sys
import time
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

from job_hunter.directory import COMPANY_DIRECTORY  # noqa: E402
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

OUT_CSV = ROOT / "output" / "emails_karachi_tech_2026-08-31.csv"
RESUME = ROOT / "Muhammad_Muddasir_Resume.pdf"
FROM = os.getenv("GMAIL_ADDRESS", "").strip()
PASS = os.getenv("GMAIL_APP_PASSWORD", "").strip()
DELAY = 52.0
TAG = "karachi_tech_cursor"

TRAINING_SKIP = re.compile(
    r"\b(trainee|internship|intern\b|apprentice|graduate\s+trainee|bootcamp|"
    r"training\s+program|academy\s+only)\b",
    re.I,
)

NON_TECH_SKIP = re.compile(
    r"\b(bank|hbl|ubl|meezan|faysal|askari|bankislami|silkbank|dib pakistan|"
    r"jazz|telenor|ufone|zong|ptcl|telemart|homeshopping|rozee|mustakbil|"
    r"tcs|mulphi|stormfiber|cybernet|engro|logistics|courier|alfalah|soneri|"
    r"js bank|foodpanda|olx)\b",
    re.I,
)

VARIANT_SUFFIX = re.compile(r"\s+(Pakistan|Tech|Digital)$", re.I)


def is_training(company: str, role: str = "") -> bool:
    return bool(TRAINING_SKIP.search(f"{company} {role}"))


def company_already_sent(name: str, domain: str, sent_c: set[str], sent_domains: set[str]) -> bool:
    n = name.lower().strip()
    if n in sent_c:
        return True
    for c in sent_c:
        if n == c or (len(n) > 4 and (n in c or c in n)):
            return True
    if domain in sent_domains:
        return True
    root = domain.split(".", 1)[0]
    if len(root) > 3 and any(root in d or d.startswith(root) for d in sent_domains):
        return True
    return False


def build_targets(sent_c: set[str], sent_domains: set[str]) -> list[dict[str, str]]:
    seen: set[str] = set()
    rows: list[dict[str, str]] = []
    for name, domain, region, city, known in COMPANY_DIRECTORY:
        if region != "Karachi":
            continue
        if VARIANT_SUFFIX.search(name):
            continue
        if NON_TECH_SKIP.search(name):
            continue
        dom = domain.lower().strip()
        if not dom or dom in seen:
            continue
        if company_already_sent(name, dom, sent_c, sent_domains):
            continue
        seen.add(dom)
        posted = ""
        for e in known:
            e = e.lower().strip()
            if e and "@" in e:
                posted = e
                break
        rows.append(
            {
                "company": name,
                "domain": dom,
                "role": "Software Engineer",
                "posted": posted,
                "city": city or "Karachi",
            }
        )
    rows.sort(key=lambda r: r["company"].lower())
    return rows


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
        ok, _detail = verify_mailbox(email)
        if ok:
            return email, "strict-valid"
    return None


def letter_body(company: str, role: str, city: str) -> str:
    try:
        from job_hunter.agent_letter import agent_enabled, write_cover_letter

        if agent_enabled():
            return write_cover_letter(
                company=company,
                role=role,
                location=f"{city}, Pakistan",
                summary=(
                    f"{company} is a Karachi-based tech company. Hiring for {role}. "
                    "Full-time software/product engineering (not internship or trainee). "
                    "Stack: React, Next.js, TypeScript, Python, product engineering."
                ),
                skills="Next.js, React, TypeScript, Python, full-stack",
                apply_url="",
            )
    except Exception:
        pass
    template = (ROOT / "emailll_proof.txt").read_text(encoding="utf-8")
    loc = f" ({city})"
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
    log_sent(to, company, "sent", letter=TAG, subject=subject)


def queue_targets(limit: int) -> list[dict]:
    sent_e, sent_c = already_sent()
    bounced = bounced_emails()
    sent_domains: set[str] = set()
    for e in sent_e:
        if "@" in e:
            sent_domains.add(e.split("@", 1)[1])

    targets = build_targets(sent_c, sent_domains)
    print(f"Karachi tech targets (unsent): {len(targets)}", flush=True)

    client = HttpClient()
    queue: list[dict] = []
    try:
        for row in targets:
            if len(queue) >= limit:
                break
            company = row["company"]
            role = row.get("role") or "Software Engineer"
            if is_training(company, role):
                print(f"SKIP trainee: {company}", flush=True)
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
        "Company",
        "Region",
        "City",
        "HR / Recruiter Email",
        "Email Source",
        "Domain",
        "Sample Role",
        "SMTP Verification",
        "Letter",
    ]
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for q in queue:
            w.writerow(
                {
                    "Company": q["company"],
                    "Region": "Karachi",
                    "City": q.get("city") or "Karachi",
                    "HR / Recruiter Email": q["email"],
                    "Email Source": "karachi directory scrape",
                    "Domain": q["domain"],
                    "Sample Role": q.get("role") or "Software Engineer",
                    "SMTP Verification": q["smtp"],
                    "Letter": TAG,
                }
            )
    print(f"\nQueue: {len(queue)} → {OUT_CSV}", flush=True)
    return queue


def send_queue(queue: list[dict]) -> int:
    sent_n = 0
    sent_e, _ = already_sent()
    for q in queue:
        company = q["company"]
        role = q.get("role") or "Software Engineer"
        email = q["email"]
        city = q.get("city") or "Karachi"
        subj = subject_for(company, role)
        try:
            print(f"\nLetter for {company}…", flush=True)
            body = letter_body(company, role, city)
            send_one(to=email, company=company, body=body, subject=subj)
            sent_n += 1
            sent_e.add(email)
            print(f"SENT [{sent_n}] {email} ({company})", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL {email}: {exc}", flush=True)
            log_sent(email, company, "failed", str(exc)[:200], letter=TAG, subject=subj)
            if any(x in str(exc).lower() for x in ("quota", "rate", "blocked", "auth", "421", "454")):
                break
        wait = max(42.0, DELAY + random.uniform(-8, 15))
        print(f"wait {wait:.0f}s…", flush=True)
        time.sleep(wait)
    return sent_n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=30, help="Max companies to queue/send")
    ap.add_argument("--queue-only", action="store_true", help="Build queue CSV only")
    ap.add_argument("--send-only", action="store_true", help="Send from existing queue CSV")
    args = ap.parse_args()

    if not FROM or not PASS or not RESUME.exists():
        raise SystemExit("Gmail/resume missing")

    if args.send_only:
        if not OUT_CSV.exists():
            raise SystemExit(f"Missing queue: {OUT_CSV}")
        queue = []
        for r in csv.DictReader(OUT_CSV.open(encoding="utf-8-sig")):
            queue.append(
                {
                    "company": r["Company"],
                    "email": r["HR / Recruiter Email"],
                    "role": r.get("Sample Role") or "Software Engineer",
                    "city": r.get("City") or "Karachi",
                }
            )
    else:
        queue = queue_targets(args.limit)

    if args.queue_only:
        print("Queue-only mode; not sending.", flush=True)
        return

    sent_n = send_queue(queue)
    print(f"\nDONE. Karachi tech sent={sent_n}", flush=True)


if __name__ == "__main__":
    main()
