#!/usr/bin/env python3
"""Aggressive blast: unsent directory companies with usable email + open junior-ish role
from LinkedIn scrape OR careers page OR known stack match. Tailored letter → send.
"""
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
from datetime import date
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
from job_hunter.directory import COMPANY_DIRECTORY  # noqa: E402
from job_hunter.experience import role_ok_for_junior  # noqa: E402
from send_emails import BLOCKED_DOMAINS, already_sent, log_sent  # noqa: E402
from smtp_verify import verify_mailbox  # noqa: E402

RESUME_NEXT = ROOT / "Muhammad_Muddasir_Resume.pdf"
RESUME_GO = ROOT / "go" / "MuddasirRizwan_Resume.pdf"
FROM = os.getenv("GMAIL_ADDRESS", "").strip()
PASS = os.getenv("GMAIL_APP_PASSWORD", "").strip()
TAG = "blast_directory+cursor"
DELAY = 42.0
TARGET = int(os.getenv("BLAST_TARGET", "25"))
OUT = ROOT / "output" / f"emails_blast_{date.today().isoformat()}.csv"
LETTERS = ROOT / "ai-job-search" / "output_scrape" / "until50" / "letters"

STACK = re.compile(
    r"react|next\.?js|frontend|front[- ]?end|full[- ]?stack|typescript|python|"
    r"ai engineer|software engineer|backend|golang|go developer|product engineer",
    re.I,
)
GO = re.compile(r"\b(golang|go developer|go engineer)\b", re.I)
BAD = re.compile(r"\b(intern\b|trainee|sqa|qa engineer|sales|php developer)\b", re.I)


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def load_scrape_jobs() -> list[dict]:
    jobs: list[dict] = []
    roots = [
        ROOT / "ai-job-search" / "output_scrape" / "until50",
        ROOT / "ai-job-search" / "output_scrape" / "batch50",
    ]
    for base in roots:
        if not base.exists():
            continue
        for path in base.glob("*.json"):
            if path.parent.name in {"details", "letters"}:
                continue
            try:
                data = json.loads(path.read_text())
            except Exception:
                continue
            results = data.get("results") if isinstance(data, dict) else data
            for r in results or []:
                title = (r.get("title") or "").strip()
                company = (r.get("company") or "").strip()
                if not title or not company:
                    continue
                if BAD.search(title) or not STACK.search(title):
                    continue
                if not role_ok_for_junior(title):
                    continue
                loc = r.get("location") or ""
                if isinstance(loc, dict):
                    loc = loc.get("label") or ""
                jobs.append(
                    {
                        "company": company,
                        "title": title,
                        "location": str(loc),
                        "url": (r.get("url") or "").strip(),
                        "id": r.get("id") or "",
                    }
                )
    return jobs


def load_mb_hr() -> dict[str, list[str]]:
    by: dict[str, list[str]] = {}
    path = ROOT / "outreach" / "mailbox_cache.csv"
    for r in csv.DictReader(path.open(encoding="utf-8-sig")):
        if r.get("status") not in ("strict-valid", "valid"):
            continue
        em = (r.get("email") or "").lower().strip()
        if "@" not in em:
            continue
        local, _, host = em.partition("@")
        if host in BLOCKED_DOMAINS:
            continue
        if not any(t in local for t in ("career", "hr", "hello", "job", "talent", "recruit", "people", "join")):
            continue
        by.setdefault(host, []).append(em)
    return by


def pick_email(domain: str, listed: tuple[str, ...], sent_e: set[str], mb: dict[str, list[str]]) -> tuple[str, str] | None:
    cands = list(listed) + mb.get(domain, []) + [f"careers@{domain}", f"hr@{domain}", f"hello@{domain}", f"jobs@{domain}"]
    for em in dict.fromkeys(e.lower() for e in cands if e):
        if em in sent_e or "@" not in em:
            continue
        host = em.split("@", 1)[1]
        if host in BLOCKED_DOMAINS:
            continue
        if em in set(mb.get(domain, [])):
            return em, "cache-strict"
        ok, detail = verify_mailbox(em)
        if ok:
            return em, "strict-valid"
        if "catch-all" in (detail or "").lower() and any(
            t in em.split("@")[0] for t in ("career", "hr", "hello", "job", "talent", "recruit", "join")
        ):
            return em, "catch-all-hr"
    return None


def match_role(company: str, jobs: list[dict]) -> dict | None:
    kn = norm(company)
    best = None
    for j in jobs:
        jk = norm(j["company"])
        if jk == kn or (len(kn) >= 6 and (kn in jk or jk in kn) and min(len(kn), len(jk)) / max(len(kn), len(jk)) >= 0.7):
            if best is None or ("junior" in j["title"].lower() or "associate" in j["title"].lower() or "1" in j["title"]):
                best = j
                if "junior" in j["title"].lower() or "associate" in j["title"].lower():
                    return j
    return best


def send_one(*, to: str, subject: str, body: str, resume: Path, cc: list[str] | None = None) -> None:
    msg = MIMEMultipart()
    msg["From"] = f"Muhammad Muddasir <{FROM}>"
    msg["To"] = to
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Reply-To"] = FROM
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=FROM.split("@", 1)[-1])
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))
    part = MIMEApplication(resume.read_bytes(), _subtype="pdf")
    part.add_header("Content-Disposition", "attachment", filename=resume.name)
    msg.attach(part)
    recipients = [to] + (cc or [])
    ctx = ssl.create_default_context()
    last: Exception | None = None
    for attempt in range(3):
        try:
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=90) as smtp:
                smtp.starttls(context=ctx)
                smtp.login(FROM, PASS)
                smtp.sendmail(FROM, recipients, msg.as_string())
            return
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(10 * (attempt + 1))
    raise last or RuntimeError("send failed")


def main() -> None:
    if not agent_enabled() or not FROM or not PASS or not RESUME_NEXT.exists():
        raise SystemExit("missing gmail/cursor/resume")
    sent_e, sent_c = already_sent()
    mb = load_mb_hr()
    jobs = load_scrape_jobs()
    print(f"scrape junior jobs: {len(jobs)}", flush=True)
    print(f"mailbox hr domains: {len(mb)}", flush=True)

    queue: list[dict] = []
    for name, domain, city, loc, emails in COMPANY_DIRECTORY:
        if norm(name) in sent_c:
            continue
        hit = pick_email(domain, emails, sent_e, mb)
        if not hit:
            continue
        email, tag = hit
        role = match_role(name, jobs)
        if role:
            title = role["title"]
            location = role["location"] or loc
            url = role["url"]
            summary = (
                f"Open role found via job boards for {name}: {title} ({location}). "
                f"Stack fit: React/Next/Python/AI/full-stack as applicable. Apply URL: {url}"
            )
        else:
            # Still apply when we have a real careers inbox for a tech company in scope —
            # letter references product-engineering interest, not a fake JD.
            title = "Software Engineer / Full Stack (open roles)"
            location = loc or city
            url = f"https://{domain}/careers"
            summary = (
                f"{name} ({domain}) is in our Karachi/MENA/tech target list. "
                f"Applying for junior/associate full-stack or frontend/AI-adjacent engineering. "
                f"Location focus: {location}. Careers: {url}"
            )
        # Prefer real board roles; deprioritize generic
        pri = 0 if role else 1
        queue.append(
            {
                "pri": pri,
                "company": name,
                "domain": domain,
                "email": email,
                "tag": tag,
                "title": title,
                "location": location,
                "url": url,
                "summary": summary,
                "has_posting": bool(role),
            }
        )

    queue.sort(key=lambda x: (x["pri"], x["company"]))
    # Posting-backed only (user rule: find job posting → letter → email → send)
    selected = [q for q in queue if q["has_posting"]][:TARGET]
    print(f"queue posting={len([q for q in queue if q['has_posting']])} selected={len(selected)}", flush=True)
    for q in selected[:15]:
        print(f"  [{q['tag']}] {q['company'][:30]} | {q['title'][:40]} → {q['email']}", flush=True)

    LETTERS.mkdir(parents=True, exist_ok=True)
    sent_rows: list[dict] = []
    sent_n = 0
    for q in selected:
        if sent_n >= TARGET:
            break
        if q["email"] in sent_e or norm(q["company"]) in sent_c:
            continue
        print(f"\n[{sent_n+1}] {q['title'][:50]} @ {q['company']}", flush=True)
        print(f"  email {q['email']} [{q['tag']}]", flush=True)
        safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", q["company"])[:40]
        letter_path = LETTERS / f"blast_{safe}.txt"
        try:
            if letter_path.exists() and letter_path.stat().st_size > 80:
                body = letter_path.read_text(encoding="utf-8")
                print("  reuse letter", flush=True)
            else:
                print("  writing tailored letter…", flush=True)
                body = write_cover_letter(
                    company=q["company"],
                    role=q["title"],
                    location=q["location"],
                    summary=q["summary"],
                    skills="React, Next.js, TypeScript, Python, AI/LLM",
                    apply_url=q["url"],
                )
                letter_path.write_text(body, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            print(f"  letter fail: {exc}", flush=True)
            continue
        print(f"  preview: {' '.join(body.split())[:120]}…", flush=True)
        resume = RESUME_GO if GO.search(q["title"]) and RESUME_GO.exists() else RESUME_NEXT
        subj = f"{q['title'][:42]} at {q['company']}"[:58]
        try:
            send_one(to=q["email"], subject=subj, body=body, resume=resume)
            sent_n += 1
            sent_e.add(q["email"])
            sent_c.add(norm(q["company"]))
            log_sent(q["email"], q["company"], "sent", letter=TAG, subject=subj)
            sent_rows.append({"Company": q["company"], "Email": q["email"], "Role": q["title"], "Location": q["location"], "URL": q["url"]})
            print(f"  SENT [{sent_n}/{TARGET}] {q['email']}", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"  SEND FAIL {exc}", flush=True)
            log_sent(q["email"], q["company"], "failed", str(exc)[:200], letter=TAG, subject=subj)
            continue
        if sent_n < TARGET:
            wait = DELAY + random.uniform(-6, 10)
            print(f"  wait {wait:.0f}s…", flush=True)
            time.sleep(wait)

    if sent_rows:
        with OUT.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(sent_rows[0].keys()))
            w.writeheader()
            w.writerows(sent_rows)
        print(f"CSV → {OUT}", flush=True)
    print(f"\nDONE. Sent {sent_n}/{TARGET}", flush=True)


if __name__ == "__main__":
    main()
