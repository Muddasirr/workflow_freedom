#!/usr/bin/env python3
"""Batch 50: scrape PK/MENA/SG/remote → tailored letter → email → send.

Stacks: React/Next.js, Python/AI, Go.
Resumes:
  - Next/AI: Muhammad_Muddasir_Resume.pdf (or crost tailored CV)
  - Go: GO_RESUME env or Muhammad_Muddasir_Resume_Go.pdf if present, else same Next CV
Junior/0–2 YOE filter enforced. No senior/L4+/3+ year titles.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import smtplib
import ssl
import subprocess
import sys
import time
from datetime import date, datetime, timezone
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from pathlib import Path

from dotenv import load_dotenv

AIJS = Path(__file__).resolve().parent
ROOT = AIJS.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "outreach"))
load_dotenv(ROOT / ".env")

from job_hunter.agent_letter import agent_enabled, write_cover_letter  # noqa: E402
from job_hunter.experience import role_ok_for_junior  # noqa: E402
from job_hunter.http import HttpClient  # noqa: E402
from job_hunter.textutil import extract_emails, html_to_text  # noqa: E402
from send_emails import BLOCKED_DOMAINS, SKIP_LOCAL, already_sent, log_sent  # noqa: E402
from smtp_verify import bounced_emails, verify_mailbox  # noqa: E402

SCRAPE = AIJS / "output_scrape" / "batch50"
DETAILS = AIJS / "output_scrape" / "details" / "batch50"
LETTERS = AIJS / "output_scrape" / "letters" / "batch50"
TRACKER = AIJS / "job_search_tracker.csv"
SEEN = AIJS / "job_scraper" / "seen_jobs.json"
OUT_CSV = ROOT / "output" / f"emails_batch50_pk_mena_sg_{date.today().isoformat()}.csv"

RESUME_NEXT = ROOT / "Muhammad_Muddasir_Resume.pdf"
RESUME_AI = AIJS / "cv" / "main_crost_ai_full_stack_product_engineer.pdf"
RESUME_GO = Path(os.getenv("GO_RESUME", str(ROOT / "Muhammad_Muddasir_Resume_Go.pdf")))

FROM = os.getenv("GMAIL_ADDRESS", "").strip()
PASS = os.getenv("GMAIL_APP_PASSWORD", "").strip()
TAG = "batch50_pk_mena_sg+cursor"
DELAY = 48.0

LI_CLI = AIJS / ".agents/skills/linkedin-search/cli/src/cli.ts"
FH_CLI = AIJS / ".agents/skills/freehire-search/cli/src/cli.ts"

AGGREGATOR_HOSTS = {
    "nofluffjobs.com",
    "powertofly.com",
    "whatjobs.com",
    "getonbrd.com",
    "linkedin.com",
    "freehire.me",
    "ashbyhq.com",
    "greenhouse.io",
    "lever.co",
}

STACK_REACT = re.compile(r"\b(react|next\.?js|frontend|front[- ]?end|typescript|full[- ]?stack)\b", re.I)
STACK_AI = re.compile(r"\b(ai engineer|llm|langgraph|langchain|agentic|machine learning engineer|rag)\b", re.I)
STACK_PY = re.compile(r"\b(python|fastapi|django)\b", re.I)
STACK_GO = re.compile(r"\b(golang|go developer|go engineer|backend.*\bgo\b|\bgo\b.*backend)\b", re.I)
STACK_ANY = re.compile(
    r"\b(react|next\.?js|frontend|full[- ]?stack|typescript|python|fastapi|golang|"
    r"go engineer|go developer|ai engineer|llm|langgraph|software engineer)\b",
    re.I,
)
BAD = re.compile(
    r"\b(wordpress|php developer|sales|recruiter|qa engineer|intern\b|trainee|wordpress)\b",
    re.I,
)

GEO_GOOD = re.compile(
    r"pakistan|karachi|lahore|islamabad|peshawar|remote|worldwide|emea|gulf|"
    r"uae|dubai|abu dhabi|saudi|riyadh|jeddah|qatar|doha|bahrain|kuwait|oman|"
    r"singapore|malaysia|egypt|jordan|lebanon|mena",
    re.I,
)
GEO_BAD = re.compile(
    r"united states|canada|brazil|mexico|australia|india|germany|lithuania|"
    r"poland|netherlands|sweden|norway(?!.*remote)",
    re.I,
)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def resume_for(title: str) -> tuple[Path, str]:
    t = title.lower()
    if STACK_GO.search(t) and not STACK_REACT.search(t) and not STACK_AI.search(t):
        if RESUME_GO.exists():
            return RESUME_GO, "go"
        return RESUME_NEXT, "go-fallback-next-cv"
    if STACK_AI.search(t) and RESUME_AI.exists():
        return RESUME_AI, "ai-next"
    return RESUME_NEXT, "next"


def track_arm(title: str) -> str:
    t = title.lower()
    if STACK_GO.search(t):
        return "go"
    if STACK_AI.search(t):
        return "ai"
    if STACK_REACT.search(t):
        return "react-next"
    if STACK_PY.search(t):
        return "python"
    return "swe"


def geo_ok(loc: str, title: str = "") -> bool:
    blob = f"{loc} {title}"
    if GEO_GOOD.search(blob):
        return True
    if GEO_BAD.search(loc) and "remote" not in loc.lower():
        return False
    if "remote" in title.lower() or loc.strip() in {"", "Remote"}:
        return True
    return False


def load_jobs() -> list[dict]:
    pool: list[dict] = []
    for path in SCRAPE.glob("*.json"):
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue
        results = data.get("results") if isinstance(data, dict) else data
        portal = "linkedin-search" if path.name.startswith("li_") else "freehire-search"
        for r in results or []:
            title = (r.get("title") or "").strip()
            company = (r.get("company") or "").strip()
            rid = r.get("id") or ""
            url = (r.get("url") or r.get("jobUrl") or "").strip()
            loc = r.get("location") or ""
            if isinstance(loc, dict):
                loc = loc.get("label") or loc.get("name") or ""
            loc = str(loc)
            if not title or not company:
                continue
            if not url:
                if portal.startswith("linkedin") and rid:
                    url = f"https://www.linkedin.com/jobs/view/{rid}"
                elif portal.startswith("freehire") and rid:
                    url = f"https://freehire.me/jobs/{rid}"
            if BAD.search(title):
                continue
            if not STACK_ANY.search(title):
                skills = r.get("skills") or []
                sk = " ".join(skills) if isinstance(skills, list) else str(skills)
                if not STACK_ANY.search(sk):
                    continue
            if not role_ok_for_junior(title):
                continue
            if not geo_ok(loc, title):
                continue
            pool.append(
                {
                    "title": title,
                    "company": company,
                    "url": url,
                    "id": rid,
                    "location": loc,
                    "portal": portal,
                    "arm": track_arm(title),
                    "description": r.get("description") or "",
                }
            )
    # dedupe by url (or company+title); keep multiple companies
    prio = {"react-next": 0, "ai": 1, "go": 2, "python": 3, "swe": 4}
    by_key: dict[str, dict] = {}
    for j in pool:
        key = j["url"] or f"{_norm(j['company'])}::{_norm(j['title'])}"
        prev = by_key.get(key)
        if not prev or prio.get(j["arm"], 9) < prio.get(prev["arm"], 9):
            by_key[key] = j
    # one role per company to avoid spamming same inbox
    by_co: dict[str, dict] = {}
    for j in by_key.values():
        co = _norm(j["company"])
        prev = by_co.get(co)
        if not prev or prio.get(j["arm"], 9) < prio.get(prev["arm"], 9):
            by_co[co] = j
    return sorted(by_co.values(), key=lambda x: (prio.get(x["arm"], 9), x["company"]))


def fetch_detail(job: dict) -> dict | None:
    if job.get("description") and len(str(job["description"])) > 120:
        return {"description": job["description"], "_meta": job}
    DETAILS.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", job["company"])[:40]
    out = DETAILS / f"{safe}.json"
    if out.exists():
        data = json.loads(out.read_text())
        data["_meta"] = {**job, **(data.get("_meta") or {})}
        return data
    portal = job["portal"]
    jid = job.get("id") or job.get("url") or ""
    if portal.startswith("freehire"):
        cmd = ["bun", "run", str(FH_CLI), "detail", jid, "--format", "json"]
    elif portal.startswith("linkedin"):
        cmd = ["bun", "run", str(LI_CLI), "detail", jid, "--format", "json"]
    else:
        return None
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=90, cwd=str(AIJS))
        if p.returncode != 0:
            print(f"  detail fail: {p.stderr[:120]}", flush=True)
            return None
        data = json.loads(p.stdout)
        if "result" in data:
            data = data["result"]
        if isinstance(data.get("results"), list) and data["results"]:
            data = data["results"][0]
        data["_meta"] = job
        out.write_text(json.dumps(data, indent=2))
        return data
    except Exception as exc:  # noqa: BLE001
        print(f"  detail exc: {exc}", flush=True)
        return None


def usable_email(email: str, sent_e: set[str], bounced: set[str]) -> bool:
    email = email.lower().strip()
    if email in sent_e or email in bounced or "@" not in email:
        return False
    local, _, host = email.partition("@")
    if local in SKIP_LOCAL or host in BLOCKED_DOMAINS or host in AGGREGATOR_HOSTS:
        return False
    if host in {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "linkedin.com"}:
        return False
    return True


def resolve_email(detail: dict, sent_e: set[str], bounced: set[str], client: HttpClient) -> tuple[str, str] | None:
    meta = detail.get("_meta") or {}
    desc = str(detail.get("description") or "")
    if not role_ok_for_junior(meta.get("title") or "", desc):
        return None
    found = extract_emails(desc)
    apply_url = detail.get("url") or meta.get("url") or ""
    for u in dict.fromkeys([apply_url, meta.get("url") or ""]):
        if not u or any(h in u for h in ("linkedin.com", "freehire.me", "whatjobs.com")):
            continue
        html = client.get_html(u) or ""
        found += extract_emails(html_to_text(html) + " " + html)

    # directory domain scrape for known companies
    company = meta.get("company") or ""
    domain = ""
    try:
        from job_hunter.directory import COMPANY_DIRECTORY

        for name, dom, *_rest in COMPANY_DIRECTORY:
            if _norm(name) == _norm(company) or _norm(company) in _norm(name):
                domain = dom
                break
    except Exception:
        pass
    if domain:
        for path in ("/careers", "/jobs", "/contact", "/about", "/"):
            html = client.get_html(f"https://{domain}{path}") or client.get_html(f"https://www.{domain}{path}") or ""
            if html:
                found += extract_emails(html_to_text(html) + " " + html)

    emails = list(dict.fromkeys(e.lower() for e in found if usable_email(e, sent_e, bounced)))
    desc_set = {e.lower() for e in extract_emails(desc)}
    ordered = sorted(
        emails,
        key=lambda e: (
            0 if e in desc_set else 1,
            0
            if any(t in e.split("@")[0] for t in ("career", "job", "hr", "talent", "hello", "hi", "apply", "team"))
            else 1,
        ),
    )
    for email in ordered:
        ok, detail_s = verify_mailbox(email)
        if ok:
            return email, "strict-valid"
        if email in desc_set and "user unknown" not in detail_s.lower() and "does not exist" not in detail_s.lower():
            return email, "user-forced published"
    if domain:
        for local in ("hello", "hi", "careers", "jobs", "hr", "talent", "team"):
            email = f"{local}@{domain}"
            if not usable_email(email, sent_e, bounced):
                continue
            ok, _ = verify_mailbox(email)
            if ok:
                return email, "strict-valid"
    return None


def send_one(*, to: str, company: str, subject: str, body: str, resume: Path) -> None:
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
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=90) as smtp:
                smtp.starttls(context=ctx)
                smtp.login(FROM, PASS)
                smtp.sendmail(FROM, [to], msg.as_string())
            log_sent(to, company, "sent", letter=TAG, subject=subject)
            return
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < 2:
                time.sleep(12 * (attempt + 1))
    raise last_exc or RuntimeError("send failed")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--daily-cap", type=int, default=80)
    ap.add_argument("--dry-queue", action="store_true")
    args = ap.parse_args()

    if not agent_enabled():
        raise SystemExit("CURSOR_API_KEY required")
    if not FROM or not PASS or not RESUME_NEXT.exists():
        raise SystemExit("Gmail/resume missing")

    if not RESUME_GO.exists():
        print(f"NOTE: Go resume not found at {RESUME_GO} — Go roles will use Next/AI CV", flush=True)

    today = datetime.now(timezone.utc).date().isoformat()
    today_n = sum(
        1
        for row in csv.DictReader((ROOT / "outreach" / "sent_log.csv").open(encoding="utf-8-sig"))
        if row.get("status") == "sent" and (row.get("sent_at") or "").startswith(today)
    )
    room = max(0, args.daily_cap - today_n)
    target = min(args.limit, room)
    print(f"Today sent={today_n} room={room} target={target}", flush=True)
    if target <= 0:
        print("Daily cap reached", flush=True)
        return

    sent_e, sent_c = already_sent()
    bounced = bounced_emails()
    jobs = load_jobs()
    jobs = [j for j in jobs if _norm(j["company"]) not in sent_c]
    print(f"Pool junior-friendly PK/MENA/SG/remote: {len(jobs)}", flush=True)
    for arm in ("react-next", "ai", "go", "python", "swe"):
        print(f"  {arm}: {sum(1 for j in jobs if j['arm']==arm)}", flush=True)

    if args.dry_queue:
        for i, j in enumerate(jobs[:target], 1):
            print(f"{i}. [{j['arm']}] {j['title'][:50]} @ {j['company']} | {j['location'][:40]}")
        return

    LETTERS.mkdir(parents=True, exist_ok=True)
    client = HttpClient()
    queue_rows: list[dict] = []
    sent_n = 0
    tried = 0

    try:
        for job in jobs:
            if sent_n >= target:
                break
            if tried >= target * 12:
                break
            tried += 1
            co = job["company"]
            title = job["title"]
            print(f"\n[{tried}] [{job['arm']}] {title[:55]} @ {co}", flush=True)
            detail = fetch_detail(job)
            if not detail:
                continue
            desc = str(detail.get("description") or "")
            if len(desc) < 100:
                print("  skip thin posting", flush=True)
                continue
            if not role_ok_for_junior(title, desc):
                print("  skip senior/3+ years in posting", flush=True)
                continue
            hit = resolve_email(detail, sent_e, bounced, client)
            if not hit:
                print("  no verified email", flush=True)
                continue
            email, smtp_tag = hit
            if email in sent_e:
                continue
            print(f"  email {email} [{smtp_tag}]", flush=True)
            resume, rtag = resume_for(title)
            skills = detail.get("skills") or []
            skills_s = ", ".join(skills) if isinstance(skills, list) else str(skills)
            safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", co)[:40]
            letter_path = LETTERS / f"{safe}.txt"
            try:
                if letter_path.exists() and letter_path.stat().st_size > 80:
                    body = letter_path.read_text(encoding="utf-8")
                    print("  reusing letter", flush=True)
                else:
                    print(f"  writing letter (resume={rtag})…", flush=True)
                    body = write_cover_letter(
                        company=co,
                        role=title,
                        location=job.get("location") or "",
                        summary=desc[:5000],
                        skills=skills_s,
                        apply_url=job.get("url") or "",
                    )
                    letter_path.write_text(body)
            except Exception as exc:  # noqa: BLE001
                print(f"  letter fail: {exc}", flush=True)
                continue
            print(f"  preview: {' '.join(body.split())[:150]}…", flush=True)
            subj = f"{title[:42]} at {co}"[:58]
            try:
                send_one(to=email, company=co, subject=subj, body=body, resume=resume)
                sent_n += 1
                sent_e.add(email)
                queue_rows.append(
                    {
                        "Company": co,
                        "Email": email,
                        "Role": title,
                        "Location": job.get("location"),
                        "Arm": job["arm"],
                        "Resume": rtag,
                        "URL": job.get("url"),
                        "SMTP": smtp_tag,
                    }
                )
                print(f"  SENT [{sent_n}/{target}] {email}", flush=True)
                if TRACKER.exists() or True:
                    if not TRACKER.exists():
                        TRACKER.write_text(
                            "date,company,sector,role,role_type,channel,status,contact_person,fit_rating,notes,cv_file,cover_letter_file,source,deadline\n"
                        )
                    with TRACKER.open("a", encoding="utf-8", newline="") as f:
                        csv.writer(f).writerow(
                            [
                                date.today().isoformat(),
                                co,
                                job["arm"],
                                title,
                                "IC",
                                "email",
                                "sent",
                                email,
                                "",
                                f"batch50→{email}",
                                str(resume),
                                str(letter_path),
                                job.get("url") or "",
                                "",
                            ]
                        )
            except Exception as exc:  # noqa: BLE001
                print(f"  SEND FAIL {exc}", flush=True)
                log_sent(email, co, "failed", str(exc)[:200], letter=TAG, subject=subj)
                if any(x in str(exc).lower() for x in ("quota", "rate", "blocked", "auth", "421", "454")):
                    break
            if sent_n < target:
                wait = max(38.0, DELAY + random.uniform(-8, 16))
                print(f"  wait {wait:.0f}s…", flush=True)
                time.sleep(wait)
    finally:
        client.close()

    if queue_rows:
        with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(queue_rows[0].keys()))
            w.writeheader()
            w.writerows(queue_rows)
        print(f"CSV → {OUT_CSV}", flush=True)
    print(f"\nDONE. Sent {sent_n}/{target}", flush=True)


if __name__ == "__main__":
    main()
