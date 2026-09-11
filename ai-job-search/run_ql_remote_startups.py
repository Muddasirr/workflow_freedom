#!/usr/bin/env python3
"""Qualified Leads → remote/small tech startups only (not big corps) → tailored letter → send."""
from __future__ import annotations

import csv
import json
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "outreach"))
load_dotenv(ROOT / ".env")

from job_hunter.agent_letter import agent_enabled, write_cover_letter  # noqa: E402
from send_emails import already_sent, log_sent  # noqa: E402

LEADS = ROOT / "Qualified Leads connections - CSV.csv"
QUEUE = ROOT / "output" / "_ql_remote_startups.json"
RESUME = ROOT / "Muhammad_Muddasir_Resume.pdf"
LETTERS = ROOT / "ai-job-search" / "output_scrape" / "letters" / "ql_remote"
FROM = os.getenv("GMAIL_ADDRESS", "").strip()
PASS = os.getenv("GMAIL_APP_PASSWORD", "").strip()
TAG = "ql_remote_startup+cursor"
DELAY = 45.0
TARGET = int(os.getenv("QL_TARGET", "20"))

BIG = re.compile(
    r"\b(google|meta|facebook|amazon|microsoft|apple|netflix|uber|airbnb|linkedin|"
    r"oracle|ibm|salesforce|adobe|intel|nvidia|samsung|huawei|tencent|alibaba|"
    r"bytedance|spotify|openai|anthropic|deepmind|deloitte|accenture|cognizant|"
    r"infosys|wipro|\btcs\b|capgemini|thoughtworks|atlassian|stripe|paypal|"
    r"care\.com|cirrus)\b",
    re.I,
)
SKIP_ORG = re.compile(
    r"\b(university|hospital|church|nonprofit|real estate|law|hair|nutrition|"
    r"wellness|coaching|venture|capital|podcast|music|marketing agency|"
    r"recruit|staffing|insights|asset management)\b",
    re.I,
)
SKIP_TITLE = re.compile(
    r"\b(account executive|sales|marketing manager|steering committee|"
    r"managing partner|cio\b|chief investment)\b",
    re.I,
)
PRODUCTY = re.compile(
    r"\b(saas|software|ai\b|ml\b|platform|devtools|developer|engineer|automation|"
    r"fintech|cloud|data|product|api|qa\b|workflow|remote)\b",
    re.I,
)
PERSONAL = {
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "icloud.com",
    "live.com",
    "proton.me",
    "post.harvard.edu",
}


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def send_one(*, to: str, subject: str, body: str) -> None:
    msg = MIMEMultipart()
    msg["From"] = f"Muhammad Muddasir <{FROM}>"
    msg["To"] = to
    msg["Reply-To"] = FROM
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=FROM.split("@", 1)[-1])
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))
    part = MIMEApplication(RESUME.read_bytes(), _subtype="pdf")
    part.add_header("Content-Disposition", "attachment", filename=RESUME.name)
    msg.attach(part)
    ctx = ssl.create_default_context()
    last: Exception | None = None
    for attempt in range(3):
        try:
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=90) as smtp:
                smtp.starttls(context=ctx)
                smtp.login(FROM, PASS)
                smtp.sendmail(FROM, [to], msg.as_string())
            return
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(12 * (attempt + 1))
    raise last or RuntimeError("send failed")


def load_queue() -> list[dict]:
    leads = json.loads(QUEUE.read_text()) if QUEUE.exists() else []
    sent_e, sent_c_raw = already_sent()
    sent_c = {norm(c) for c in sent_c_raw} | {c.lower() for c in sent_c_raw}
    out: list[dict] = []
    seen_em: set[str] = set()
    seen_co: set[str] = set()
    for c in leads:
        em = (c.get("email") or "").lower()
        org = c.get("org") or ""
        title = c.get("title") or ""
        host = em.split("@", 1)[-1] if "@" in em else ""
        if not em or em in sent_e or em in seen_em:
            continue
        if host in PERSONAL:
            continue
        if norm(org) in sent_c or org.lower() in sent_c or norm(org) in seen_co:
            continue
        if BIG.search(org) or BIG.search(host):
            continue
        if SKIP_ORG.search(org) or SKIP_TITLE.search(title):
            continue
        blob = f"{org} {title} {c.get('headline') or ''} {c.get('industry') or ''} {c.get('about') or ''}"
        if not PRODUCTY.search(blob):
            continue
        # Prefer explicit remote; still allow tiny product startups
        if not c.get("remote_flag") and (c.get("emp") or 0) > 80:
            continue
        out.append(c)
        seen_em.add(em)
        seen_co.add(norm(org))
    # explicit remote first
    out.sort(key=lambda x: (0 if x.get("remote_flag") else 1, x.get("emp") or 40, x.get("org") or ""))
    return out


def main() -> None:
    if not agent_enabled() or not FROM or not PASS or not RESUME.exists():
        raise SystemExit("missing gmail/cursor/resume")
    if not QUEUE.exists():
        raise SystemExit(f"missing {QUEUE} — build queue first")
    queue = load_queue()[:TARGET]
    print(f"queue={len(queue)} target={TARGET}", flush=True)
    for c in queue:
        print(
            f"  rem={c.get('remote_flag')} n={c.get('emp') or '?'} {c['org'][:28]} → {c['email']} ({c.get('name')})",
            flush=True,
        )

    LETTERS.mkdir(parents=True, exist_ok=True)
    sent_n = 0
    used: set[str] = set()
    for c in queue:
        if sent_n >= TARGET:
            break
        em = c["email"].lower()
        if em in used:
            continue
        org = c["org"]
        name = (c.get("name") or "").strip() or "there"
        role = "Junior / Associate Software Engineer (Full Stack / Frontend / AI)"
        print(f"\n[{sent_n+1}] {org} → {em}", flush=True)
        safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", org)[:40]
        letter_path = LETTERS / f"{safe}.txt"
        summary = (
            f"Cold outreach to {name}, {c.get('title') or 'leader'} at {org} "
            f"({'remote-friendly startup' if c.get('remote_flag') else 'early-stage tech startup'}, "
            f"~{c.get('emp') or 'small'} people, domain {c.get('domain')}). "
            f"Headline: {c.get('headline') or 'n/a'}. "
            f"About snippet: {(c.get('about') or '')[:350]}. "
            f"Ask about junior/associate full-stack, frontend (React/Next.js), or AI-engineering roles "
            f"that can be remote from Karachi (UTC+5). Do NOT invent a specific open req title if unknown; "
            f"ask whether they are hiring IC engineers at early career level."
        )
        try:
            if letter_path.exists() and letter_path.stat().st_size > 80:
                body = letter_path.read_text(encoding="utf-8")
                print("  reuse letter", flush=True)
            else:
                print("  writing tailored letter…", flush=True)
                body = write_cover_letter(
                    company=org,
                    role=role,
                    location="Remote",
                    summary=summary,
                    skills="React, Next.js, TypeScript, Python, LangGraph, AI tooling",
                    apply_url=f"https://{c.get('domain') or ''}",
                )
                # Prefer greeting with first name when present
                if name and name.lower() != "there" and body.startswith("Hi "):
                    first = name.split()[0]
                    body = re.sub(r"^Hi [^,\n]+", f"Hi {first}", body, count=1)
                letter_path.write_text(body, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            print(f"  letter fail: {exc}", flush=True)
            continue
        print(f"  preview: {' '.join(body.split())[:130]}…", flush=True)
        subj = f"Junior full-stack / frontend engineer — {org}"[:58]
        try:
            send_one(to=em, subject=subj, body=body)
            sent_n += 1
            used.add(em)
            log_sent(em, org, "sent", f"to:{name}", letter=TAG, subject=subj)
            print(f"  SENT [{sent_n}/{TARGET}] {em}", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"  SEND FAIL {exc}", flush=True)
            log_sent(em, org, "failed", str(exc)[:200], letter=TAG, subject=subj)
            continue
        if sent_n < TARGET:
            wait = DELAY + random.uniform(-5, 10)
            print(f"  wait {wait:.0f}s…", flush=True)
            time.sleep(wait)
    print(f"\nDONE. Sent {sent_n}/{TARGET}", flush=True)


if __name__ == "__main__":
    main()
