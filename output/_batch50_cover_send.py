#!/usr/bin/env python3
"""Fast batch: mine unused contacts → cover-letter email body → send 55+ with resume.

Uses prior output/emails_*.csv leftovers + COMPANY_DIRECTORY knowns that were never mailed.
Cover letter is the email body (ai-job-search profile), not a PDF.
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
from send_emails import (  # noqa: E402
    BLOCKED_COMPANIES,
    BLOCKED_DOMAINS,
    SAFE_LOCAL,
    SKIP_LOCAL,
    already_sent,
)

OUT_CSV = ROOT / "output" / "emails_batch50_cover_send_2026-08-29.csv"
SENT_LOG = ROOT / "outreach" / "sent_log.csv"
RESUME = ROOT / "Muhammad_Muddasir_Resume.pdf"
TRACKER = ROOT / "ai-job-search" / "job_search_tracker.csv"
FROM = os.getenv("GMAIL_ADDRESS", "").strip()
PASS = os.getenv("GMAIL_APP_PASSWORD", "").strip()

TARGET = 55
DELAY = 48.0
DAILY_CAP = 80

SKIP_US_ONLY = {
    "coinbase", "dropbox", "airbnb", "reddit", "datadog", "twilio", "gusto",
    "canonical", "stripe", "vercel", "toptal", "andela", "gitlab", "openai",
    "anthropic", "cloudflare", "airtable", "lemon.io", "n8n", "huggingface",
    "notion", "figma", "meta", "google", "amazon", "microsoft", "apple",
    "uber", "lyft", "netflix", "shopify", "salesforce", "oracle", "ibm",
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
    return "fullstack"


def cover_letter_email(*, company: str, role: str, location: str, bucket: str) -> str:
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
        f"Saw the {role} opening{loc}. {proof}\n\n"
        f"If you're still hiring for {role}, open to a 15-minute call this week? Resume attached — "
        f"more at muddasirrizwan.com. Remote from Karachi (UTC+5) / Pakistan-friendly.\n\n"
        f"Muhammad Muddasir\n"
        f"+92-3249867842 · muddasirrizwan9@gmail.com · muddasirrizwan.com\n"
    )


def subject_for(company: str, role: str) -> str:
    subj = f"{role} at {company}"
    return subj[:58] if len(subj) > 58 else subj


JUNK_PREFIX = (
    "notice", "notices", "feedback", "accreditation", "noreply", "no-reply",
    "donotreply", "mailer", "bounce", "newsletter", "marketing", "press",
    "media", "support", "help", "billing", "invoice", "security", "abuse",
    "postmaster", "webmaster", "unsubscribe", "alert", "alerts", "system",
)


def usable_email(email: str) -> bool:
    email = (email or "").strip().lower()
    if "@" not in email:
        return False
    local, _, host = email.partition("@")
    if local in SKIP_LOCAL or any(j in local for j in JUNK_LOCAL):
        return False
    if any(local == j or local.startswith(j + ".") or local.startswith(j + "-") for j in JUNK_PREFIX):
        return False
    if host in BLOCKED_DOMAINS or host.endswith(".codet.ai"):
        return False
    if host in {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "proton.me", "icloud.com"}:
        return False
    hiringish = any(
        t in local
        for t in ("career", "recruit", "talent", "hiring", "people", "job", "cv", "hr", "join")
    )
    if local in SAFE_LOCAL or hiringish:
        return True
    # first.last style people emails OK
    if "." in local and local.replace(".", "").isalpha() and len(local) >= 5:
        return True
    # generic office inboxes (PK banks etc.) — allow sparingly
    if local in {"hello", "hi", "apply", "team", "info", "contact", "contactus", "connect"}:
        return True
    return False


def smtp_rank(tag: str) -> int:
    t = (tag or "").lower()
    if "strict-valid" in t or "user-forced" in t:
        return 0
    if "job posting" in t or "known" in t:
        return 1
    if "cache" in t and "valid" in t:
        return 1
    if "catch-all" in t:
        return 3
    if not t:
        return 2
    return 2


def region_rank(region: str, city: str) -> int:
    blob = f"{region} {city}".lower()
    if any(x in blob for x in ("karachi", "pakistan", "lahore", "islamabad")):
        return 0
    if "remote" in blob:
        return 1
    if any(x in blob for x in ("uae", "mena", "europe", "singapore", "australia", "uk", "germany", "canada")):
        return 2
    return 3


def email_quality(email: str) -> int:
    local = email.split("@", 1)[0]
    if any(t in local for t in ("career", "job", "talent", "recruit", "hiring", "hr", "cv", "people", "join")):
        return 0
    if "." in local:
        return 1
    if local in SAFE_LOCAL or local in {"hello", "apply", "team"}:
        return 2
    return 3


def load_candidates(sent_e: set[str], sent_c: set[str]) -> list[dict[str, str]]:
    cand: dict[str, dict[str, str]] = {}  # email -> row

    def consider(
        *,
        email: str,
        company: str,
        role: str,
        region: str = "",
        city: str = "",
        smtp: str = "",
        url: str = "",
        src: str = "",
    ) -> None:
        email = (email or "").strip().lower()
        company = (company or "").strip()
        if not email or not company or not usable_email(email):
            return
        if email in sent_e:
            return
        ck = _norm(company)
        if not ck or ck in sent_c or ck in SKIP_US_ONLY:
            return
        if any(b == ck or b in ck for b in BLOCKED_COMPANIES):
            return
        host = email.split("@", 1)[1]
        if host in BLOCKED_DOMAINS:
            return
        # Prefer not reusing same company under different email in this batch
        for existing in cand.values():
            if _norm(existing["company"]) == ck:
                # keep better smtp
                if smtp_rank(smtp) >= smtp_rank(existing.get("smtp") or ""):
                    return
        role = role or "Software Engineer"
        # skip obvious non-IC leadership-only product manager if we have better — still ok for outreach
        row = {
            "email": email,
            "company": company,
            "role": role,
            "region": region or "",
            "city": city or "",
            "smtp": smtp or "",
            "url": url or "",
            "src": src,
            "bucket": role_bucket(role),
            "location": ", ".join(x for x in (city, region) if x) or region or "Remote",
        }
        prev = cand.get(email)
        if prev and smtp_rank(prev.get("smtp") or "") < smtp_rank(smtp):
            return
        cand[email] = row

    # From prior CSVs (prefer newer filenames via sort reverse)
    for path in sorted(Path(ROOT / "output").glob("emails_*.csv"), reverse=True):
        try:
            with path.open(encoding="utf-8-sig", newline="") as f:
                for r in csv.DictReader(f):
                    email = (
                        r.get("HR / Recruiter Email")
                        or r.get("email")
                        or r.get("Email")
                        or ""
                    ).strip()
                    company = (r.get("Company") or r.get("company") or "").strip()
                    role = (r.get("Sample Role") or r.get("Role") or r.get("Title") or "Software Engineer").strip()
                    consider(
                        email=email,
                        company=company,
                        role=role,
                        region=(r.get("Region") or "").strip(),
                        city=(r.get("City") or "").strip(),
                        smtp=(r.get("SMTP Verification") or "").strip(),
                        url=(r.get("Careers / Apply URL") or "").strip(),
                        src=path.name,
                    )
        except Exception:
            continue

    # Directory known contacts never mailed
    for name, domain, region, city, known in COMPANY_DIRECTORY:
        for e in known:
            if isinstance(e, str) and "@" in e:
                consider(
                    email=e,
                    company=name,
                    role="Software Engineer",
                    region=region,
                    city=city,
                    smtp="known company contact",
                    url=f"https://{domain}",
                    src="directory",
                )

    rows = list(cand.values())
    rows.sort(
        key=lambda r: (
            email_quality(r["email"]),
            smtp_rank(r.get("smtp") or ""),
            region_rank(r.get("region") or "", r.get("city") or ""),
            0 if r["bucket"] in {"ai", "frontend", "fullstack", "backend"} else 1,
            r["company"].lower(),
        )
    )
    # Dedupe by company keeping best
    out: list[dict[str, str]] = []
    seen_co: set[str] = set()
    for r in rows:
        ck = _norm(r["company"])
        if ck in seen_co:
            continue
        seen_co.add(ck)
        out.append(r)
    return out


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
    with SENT_LOG.open("a", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerow(
            [
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                company,
                to,
                "sent",
                "",
                "cover_email_body",
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
    today_count = sum(
        1
        for r in csv.DictReader(SENT_LOG.open(encoding="utf-8-sig"))
        if r.get("status") == "sent" and (r.get("sent_at") or "").startswith(today)
    ) if SENT_LOG.exists() else 0
    room = max(0, DAILY_CAP - today_count)
    target = min(TARGET, room)
    print(f"Today sent={today_count} room={room} target={target}", flush=True)
    if target < 1:
        raise SystemExit("Daily cap reached")

    all_cands = load_candidates(sent_e, sent_c)
    print(f"Unused new-company contacts: {len(all_cands)}", flush=True)
    queue = all_cands[: target + 20]

    fields = [
        "Company", "HR / Recruiter Email", "Sample Role", "Region", "City",
        "SMTP Verification", "Letter", "Source", "Subject",
    ]
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for q in queue:
            bucket = q["bucket"]
            subj = subject_for(q["company"], q["role"])
            body = cover_letter_email(
                company=q["company"],
                role=q["role"],
                location=q.get("location") or "",
                bucket=bucket,
            )
            q["subject"] = subj
            q["body"] = body
            w.writerow(
                {
                    "Company": q["company"],
                    "HR / Recruiter Email": q["email"],
                    "Sample Role": q["role"],
                    "Region": q.get("region") or "",
                    "City": q.get("city") or "",
                    "SMTP Verification": q.get("smtp") or "",
                    "Letter": bucket,
                    "Source": q.get("src") or "",
                    "Subject": subj,
                }
            )
    print(f"Queue written ({len(queue)}): {OUT_CSV}", flush=True)
    for i, q in enumerate(queue[:12], 1):
        print(f"  preview {i}: {q['email']} | {q['company']} | {q['subject'][:50]}", flush=True)

    sent_n = 0
    for i, q in enumerate(queue, 1):
        if sent_n >= target:
            break
        try:
            send_one(to=q["email"], company=q["company"], body=q["body"], subject=q["subject"])
            sent_n += 1
            print(f"[{sent_n}/{target}] SENT {q['email']} ({q['company']})", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL {q['email']}: {exc}", flush=True)
            with SENT_LOG.open("a", encoding="utf-8-sig", newline="") as f:
                csv.writer(f).writerow(
                    [
                        datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        q["company"],
                        q["email"],
                        "failed",
                        str(exc)[:200],
                        "cover_email_body",
                        "",
                        q["subject"],
                    ]
                )
            if any(x in str(exc).lower() for x in ("quota", "rate", "blocked", "auth", "421", "454", "550")):
                # 550 might be recipient; only stop on rate/auth
                if any(x in str(exc).lower() for x in ("quota", "rate", "blocked", "auth", "421", "454")):
                    print("Stopping on Gmail rate/auth", flush=True)
                    break
        if sent_n < target and i < len(queue):
            wait = max(40.0, DELAY + random.uniform(-8, 18))
            print(f"  wait {wait:.0f}s…", flush=True)
            time.sleep(wait)

    try:
        with TRACKER.open("a", encoding="utf-8", newline="") as f:
            csv.writer(f).writerow(
                [
                    datetime.now(timezone.utc).date().isoformat(),
                    f"BATCH_COVER_EMAIL ({sent_n})",
                    "mixed",
                    "various",
                    "mixed",
                    "email",
                    "sent",
                    "",
                    "",
                    f"cover-letter-as-email body + resume; sent={sent_n}",
                    "",
                    "",
                    "ai-job-search profile + leftover contacts",
                    "",
                ]
            )
    except Exception:
        pass

    print(f"\nDONE. Sent {sent_n} cover-letter applications.", flush=True)


if __name__ == "__main__":
    main()
