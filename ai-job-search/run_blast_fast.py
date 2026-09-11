#!/usr/bin/env python3
"""Fast blast: scrape jobs → match known emails (cache/directory) → letter → send."""
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
TAG = "blast_fast+cursor"
DELAY = 40.0
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


def load_jobs() -> list[dict]:
    jobs: list[dict] = []
    for base in (
        ROOT / "ai-job-search" / "output_scrape" / "until50",
        ROOT / "ai-job-search" / "output_scrape" / "batch50",
    ):
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
                    }
                )
    # dedupe company+title
    seen: set[str] = set()
    out: list[dict] = []
    for j in jobs:
        k = norm(j["company"]) + "|" + j["title"].lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(j)
    return out


def load_email_maps() -> tuple[dict[str, str], dict[str, list[str]], dict[str, str], set[str], set[str]]:
    """company_norm→email, domain→emails, company_norm→domain, strict_set, catchall_set"""
    co_em: dict[str, str] = {}
    dom_em: dict[str, list[str]] = {}
    co_dom: dict[str, str] = {}
    strict: set[str] = set()
    catchall: set[str] = set()

    for name, domain, city, loc, emails in COMPANY_DIRECTORY:
        kn = norm(name)
        co_dom[kn] = domain
        for em in emails:
            em = em.lower()
            if "@" in em:
                co_em.setdefault(kn, em)
                dom_em.setdefault(domain, []).append(em)

    for path in (ROOT / "output").glob("emails_*.csv"):
        if "qualified" in path.name.lower() or "lead" in path.name.lower():
            continue
        try:
            for r in csv.DictReader(path.open(encoding="utf-8-sig")):
                co = (r.get("Company") or "").strip()
                em = (r.get("HR / Recruiter Email") or r.get("Email") or "").strip().lower()
                if co and "@" in em:
                    kn = norm(co)
                    co_em.setdefault(kn, em)
                    co_dom.setdefault(kn, em.split("@", 1)[1])
                    dom_em.setdefault(em.split("@", 1)[1], []).append(em)
        except Exception:
            continue

    mb = ROOT / "outreach" / "mailbox_cache.csv"
    for r in csv.DictReader(mb.open(encoding="utf-8-sig")):
        st = r.get("status") or ""
        em = (r.get("email") or "").lower().strip()
        if "@" not in em:
            continue
        local, _, host = em.partition("@")
        if host in BLOCKED_DOMAINS:
            continue
        if st in ("strict-valid", "valid"):
            strict.add(em)
            if any(t in local for t in ("career", "hr", "hello", "job", "talent", "recruit", "people", "join")):
                dom_em.setdefault(host, []).append(em)
        elif st == "catch-all" and any(
            t in local for t in ("career", "hr", "hello", "job", "talent", "recruit", "people", "join")
        ):
            catchall.add(em)
            dom_em.setdefault(host, []).append(em)

    for d in list(dom_em):
        dom_em[d] = list(dict.fromkeys(dom_em[d]))
    return co_em, dom_em, co_dom, strict, catchall


def resolve_email_for_company(
    company: str,
    co_em: dict[str, str],
    dom_em: dict[str, list[str]],
    co_dom: dict[str, str],
    sent_e: set[str],
    strict: set[str],
    catchall: set[str],
) -> tuple[str, str] | None:
    kn = norm(company)
    cands: list[str] = []
    if kn in co_em:
        cands.append(co_em[kn])
    for pk, em in co_em.items():
        if len(pk) < 8 or len(kn) < 8:
            continue
        shorter, longer = (pk, kn) if len(pk) <= len(kn) else (kn, pk)
        if shorter in longer and len(shorter) / len(longer) >= 0.72:
            cands.append(em)
    domain = co_dom.get(kn, "")
    if not domain:
        for pk, dom in co_dom.items():
            if len(pk) < 8 or len(kn) < 8:
                continue
            shorter, longer = (pk, kn) if len(pk) <= len(kn) else (kn, pk)
            if shorter in longer and len(shorter) / len(longer) >= 0.72:
                domain = dom
                break
    if domain:
        cands.extend(dom_em.get(domain, []))
        cands.extend([f"careers@{domain}", f"hr@{domain}", f"hello@{domain}", f"jobs@{domain}"])

    ordered = list(dict.fromkeys(e.lower() for e in cands if e and "@" in e))
    # STRICT ONLY — never catch-all or live-guess careers@
    for em in ordered:
        if em in sent_e or em.split("@", 1)[1] in BLOCKED_DOMAINS:
            continue
        if em in strict:
            return em, "cache-strict"
    return None


def send_one(*, to: str, subject: str, body: str, resume: Path) -> None:
    msg = MIMEMultipart()
    msg["From"] = f"Muhammad Muddasir <{FROM}>"
    msg["To"] = to
    msg["Reply-To"] = FROM
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=FROM.split("@", 1)[-1])
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))
    part = MIMEApplication(resume.read_bytes(), _subtype="pdf")
    part.add_header("Content-Disposition", "attachment", filename=resume.name)
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
            time.sleep(10 * (attempt + 1))
    raise last or RuntimeError("send failed")


def main() -> None:
    if not agent_enabled() or not FROM or not PASS or not RESUME_NEXT.exists():
        raise SystemExit("missing gmail/cursor/resume")
    sent_e, sent_c_raw = already_sent()
    sent_c = {norm(c) for c in sent_c_raw} | {c.strip().lower() for c in sent_c_raw}
    jobs = load_jobs()
    co_em, dom_em, co_dom, strict, catchall = load_email_maps()
    print(
        f"jobs={len(jobs)} co_emails={len(co_em)} strict={len(strict)} catchall={len(catchall)} sent_co={len(sent_c)}",
        flush=True,
    )

    queue: list[dict] = []
    seen_co: set[str] = set()
    for j in jobs:
        kn = norm(j["company"])
        if kn in sent_c or j["company"].strip().lower() in sent_c or kn in seen_co:
            continue
        hit = resolve_email_for_company(j["company"], co_em, dom_em, co_dom, sent_e, strict, catchall)
        if not hit:
            continue
        email, tag = hit
        seen_co.add(kn)
        queue.append({**j, "email": email, "tag": tag})
        print(f"  match {j['company'][:35]} | {j['title'][:40]} → {email} [{tag}]", flush=True)
        if len(queue) >= TARGET * 3:
            break

    print(f"queue={len(queue)} target={TARGET}", flush=True)
    LETTERS.mkdir(parents=True, exist_ok=True)
    sent_rows: list[dict] = []
    sent_n = 0
    for q in queue:
        if sent_n >= TARGET:
            break
        if q["email"] in sent_e or norm(q["company"]) in sent_c or q["company"].strip().lower() in sent_c:
            continue
        print(f"\n[{sent_n+1}] {q['title'][:55]} @ {q['company']}", flush=True)
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
                    summary=(
                        f"Job posting: {q['title']} at {q['company']} ({q['location']}). "
                        f"URL: {q['url']}. Junior/associate-friendly full-stack/frontend/AI role."
                    ),
                    skills="React, Next.js, TypeScript, Python, AI/LLM",
                    apply_url=q["url"],
                )
                letter_path.write_text(body, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            print(f"  letter fail: {exc}", flush=True)
            continue
        print(f"  preview: {' '.join(body.split())[:130]}…", flush=True)
        resume = RESUME_GO if GO.search(q["title"]) and RESUME_GO.exists() else RESUME_NEXT
        subj = f"{q['title'][:42]} at {q['company']}"[:58]
        try:
            send_one(to=q["email"], subject=subj, body=body, resume=resume)
            sent_n += 1
            sent_e.add(q["email"])
            sent_c.add(norm(q["company"]))
            sent_c.add(q["company"].strip().lower())
            log_sent(q["email"], q["company"], "sent", letter=TAG, subject=subj)
            sent_rows.append(
                {"Company": q["company"], "Email": q["email"], "Role": q["title"], "Location": q["location"], "URL": q["url"]}
            )
            print(f"  SENT [{sent_n}/{TARGET}] {q['email']}", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"  SEND FAIL {exc}", flush=True)
            log_sent(q["email"], q["company"], "failed", str(exc)[:200], letter=TAG, subject=subj)
            continue
        if sent_n < TARGET:
            wait = DELAY + random.uniform(-5, 8)
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
