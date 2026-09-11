#!/usr/bin/env python3
"""Qualified leads CSV → company job posting → tailored letter → send to contact email."""
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
from datetime import datetime, timezone
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
from send_emails import already_sent, log_sent  # noqa: E402

LEADS_CSV = ROOT / "Qualified Leads connections - CSV.csv"
OUT_CSV = ROOT / "output" / "emails_qualified_leads_2026-08-31.csv"
LETTERS = AIJS / "output_scrape" / "letters" / "qualified_leads"
FH_CLI = AIJS / ".agents/skills/freehire-search/cli/src/cli.ts"
LI_CLI = AIJS / ".agents/skills/linkedin-search/cli/src/cli.ts"
RESUME = ROOT / "Muhammad_Muddasir_Resume.pdf"
FROM = os.getenv("GMAIL_ADDRESS", "").strip()
PASS = os.getenv("GMAIL_APP_PASSWORD", "").strip()
TAG = "qualified_leads+cursor"
DELAY = 50.0

PERSONAL_HOSTS = {
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "icloud.com",
    "live.com",
    "proton.me",
    "protonmail.com",
}

ROLE_OK = re.compile(
    r"full.?stack|software engineer|frontend|front.?end|backend|AI engineer|"
    r"machine learning engineer|product engineer|react|typescript|developer|platform engineer",
    re.I,
)
ROLE_SKIP = re.compile(
    r"\b(intern|trainee|apprentice|recruiter|talent acquisition|sales|marketing|"
    r"customer success|account executive|devops manager|director of)\b",
    re.I,
)
NON_TECH = re.compile(
    r"\b(university|hospital|medical|nutrition|church|nonprofit|real estate|"
    r"insurance agency|law firm|sales training|coaching|wellness|fitness)\b",
    re.I,
)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _email(row: dict) -> str:
    for k in ("email", "email_found (apollo.io)"):
        e = (row.get(k) or "").strip().lower()
        if e and "@" in e:
            return e
    return ""


def _company(row: dict) -> str:
    for k in ("org_name", "experience_1_company"):
        v = (row.get(k) or "").strip()
        if v and v.lower() not in {"self-employed", "freelance", "stealth"}:
            return v
    return ""


def _domain(row: dict, email: str) -> str:
    d = (row.get("org_domain") or "").strip().lower()
    if d:
        return d.lstrip("www.")
    host = email.split("@", 1)[-1] if "@" in email else ""
    if host and host not in PERSONAL_HOSTS:
        return host
    return ""


def _contact_name(row: dict) -> str:
    fn = (row.get("first_name") or "").strip()
    ln = (row.get("last_name") or "").strip()
    return _norm(f"{fn} {ln}") or (row.get("full_name") or "").strip()


def _today_sent_count() -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    n = 0
    log = ROOT / "outreach" / "sent_log.csv"
    if not log.exists():
        return 0
    for row in csv.DictReader(log.open(encoding="utf-8-sig")):
        if row.get("status") == "sent" and (row.get("sent_at") or "").startswith(today):
            n += 1
    return n


def load_leads() -> list[dict]:
    rows = list(csv.DictReader(LEADS_CSV.open(encoding="utf-8-sig")))
    sent_e, _ = already_sent()
    out: list[dict] = []
    for row in rows:
        email = _email(row)
        company = _company(row)
        if not email or not company:
            continue
        if email in sent_e or "codet.ai" in email or "codet.com" in email:
            continue
        domain = _domain(row, email)
        blob = f"{company} {row.get('org_industry') or ''} {row.get('headline') or ''}"
        if NON_TECH.search(blob):
            continue
        cat = row.get("_category") or ""
        if not any(x in cat for x in ("tech_exec", "top_company", "founder")):
            continue
        # founders without a corporate domain rarely have scrapeable job boards
        if "founder" in cat and "top_company" not in cat and "tech_exec" not in cat:
            if not domain or domain in PERSONAL_HOSTS:
                continue
        priority = 0
        if (row.get("email_status") or "").lower() == "verified":
            priority -= 2
        if "top_company" in cat:
            priority -= 1
        if domain:
            priority -= 1
        out.append(
            {
                "email": email,
                "company": company,
                "domain": domain,
                "contact": _contact_name(row),
                "title": (row.get("title") or row.get("experience_1_position") or "").strip(),
                "headline": (row.get("headline") or "").strip(),
                "category": cat,
                "priority": priority,
                "_row": row,
            }
        )
    out.sort(key=lambda x: (x["priority"], x["company"].lower()))
    # one lead per company email
    seen_co: set[str] = set()
    deduped: list[dict] = []
    for lead in out:
        key = lead["company"].lower()
        if key in seen_co:
            continue
        seen_co.add(key)
        deduped.append(lead)
    return deduped


def _freehire_slugs(company: str, domain: str) -> list[str]:
    slugs: list[str] = []
    if domain:
        root = domain.split(".")[0]
        if len(root) >= 3:
            slugs.append(root)
    compact = re.sub(r"[^a-z0-9]", "", company.lower())
    if len(compact) >= 3:
        slugs.append(compact)
    hyphen = re.sub(r"[^a-z0-9]+", "-", company.lower()).strip("-")
    if hyphen:
        slugs.append(hyphen.replace("-", ""))
    return list(dict.fromkeys(slugs))


def _score_result(title: str, location: str = "", work_mode: str = "") -> tuple[int, int]:
    t = title.lower()
    loc = (location or "").lower()
    wm = (work_mode or "").lower()
    rank = 0
    if re.search(r"\b(junior|jr\.|associate|entry|new grad|early career|engineer i\b|software engineer i\b)", t):
        rank -= 5
    if "fullstack" in t or "full stack" in t or "full-stack" in t:
        rank -= 3
    elif "software engineer" in t and not re.search(r"\b(ii|iii|iv|senior|staff|lead)\b", t):
        rank -= 2
    elif "frontend" in t or "react" in t:
        rank -= 2
    if "remote" in loc or wm == "remote" or "worldwide" in loc:
        rank -= 2
    if re.search(r"\b(senior|staff|principal|lead|manager|l[4-9]|\(l[4-9]\)|iii|iv)\b", t):
        rank += 20
    return rank, 0


def _role_usable(title: str, description: str = "") -> bool:
    if not ROLE_OK.search(title or ""):
        return False
    if ROLE_SKIP.search(title or ""):
        return False
    return role_ok_for_junior(title, description)


def _freehire_jobs(company: str, domain: str) -> list[dict]:
    hits: list[dict] = []
    for slug in _freehire_slugs(company, domain):
        cmd = [
            "bun",
            "run",
            str(FH_CLI),
            "search",
            "-q",
            "software engineer",
            "--company",
            slug,
            "--jobage",
            "30",
            "--limit",
            "15",
            "--no-description",
            "--format",
            "json",
        ]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=str(AIJS))
            if p.returncode != 0:
                continue
            data = json.loads(p.stdout)
            for r in data.get("results") or []:
                title = (r.get("title") or "").strip()
                if not title or not _role_usable(title):
                    continue
                hits.append(
                    {
                        "title": title,
                        "url": r.get("url") or "",
                        "id": r.get("id") or "",
                        "location": r.get("location") or "",
                        "work_mode": r.get("work_mode") or "",
                        "portal": "freehire-search",
                        "company": company,
                    }
                )
            if hits:
                break
        except Exception:
            continue
    return hits


def _careers_jobs(company: str, domain: str) -> list[dict]:
    if not domain:
        return []
    jobs, _ = scrape_company_careers(company, domain, ())
    out: list[dict] = []
    for j in jobs:
        title = (j.title or "").strip()
        if not title or not _role_usable(title, j.description or ""):
            continue
        if not (j.description or "").strip():
            continue
        out.append(
            {
                "title": title,
                "url": j.url or f"https://{domain}/careers",
                "id": j.source_id or "",
                "location": j.location or "",
                "work_mode": j.work_mode or "",
                "portal": "careers-scrape",
                "company": company,
                "description": j.description,
            }
        )
    return out


def _linkedin_jobs(company: str) -> list[dict]:
    cmd = [
        "bun",
        "run",
        str(LI_CLI),
        "search",
        "-q",
        f"software engineer {company}",
        "-l",
        "Remote",
        "--jobage",
        "30",
        "--limit",
        "10",
        "--format",
        "json",
    ]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=str(AIJS))
        if p.returncode != 0:
            return []
        data = json.loads(p.stdout)
        out: list[dict] = []
        co_l = company.lower()
        for r in data.get("results") or []:
            rc = (r.get("company") or "").lower()
            if co_l not in rc and rc not in co_l:
                continue
            title = (r.get("title") or "").strip()
            if not title or ROLE_SKIP.search(title) or not ROLE_OK.search(title):
                continue
            rid = r.get("id") or ""
            url = r.get("url") or (f"https://www.linkedin.com/jobs/view/{rid}" if rid else "")
            out.append(
                {
                    "title": title,
                    "url": url,
                    "id": rid,
                    "location": r.get("location") or "",
                    "work_mode": "",
                    "portal": "linkedin-search",
                    "company": company,
                }
            )
        return out
    except Exception:
        return []


def _fetch_description(job: dict) -> str:
    if job.get("description"):
        return str(job["description"])
    portal = job.get("portal") or ""
    jid = job.get("id") or job.get("url") or ""
    if portal.startswith("freehire"):
        cmd = ["bun", "run", str(FH_CLI), "detail", jid, "--format", "json"]
    elif portal.startswith("linkedin"):
        cmd = ["bun", "run", str(LI_CLI), "detail", jid, "--format", "json"]
    else:
        return ""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=90, cwd=str(AIJS))
        if p.returncode != 0:
            return ""
        data = json.loads(p.stdout)
        if "result" in data:
            data = data["result"]
        if isinstance(data.get("results"), list) and data["results"]:
            data = data["results"][0]
        return str(data.get("description") or "")
    except Exception:
        return ""


def find_best_job(company: str, domain: str, *, fetch_desc: bool = True) -> dict | None:
    pool = _freehire_jobs(company, domain)
    if not pool:
        pool = _linkedin_jobs(company)
    if not pool:
        return None
    pool.sort(key=lambda j: _score_result(j["title"], j.get("location", ""), j.get("work_mode", "")))
    job = dict(pool[0])
    if fetch_desc:
        for candidate in pool[:5]:
            desc = _fetch_description(candidate)
            if len(desc) >= 120:
                job = dict(candidate)
                job["description"] = desc[:6000]
                return job
        return None
    return job


def letter_body(lead: dict, job: dict) -> str:
    contact = lead.get("contact") or ""
    company = lead["company"]
    role = job["title"]
    desc = job["description"]
    loc = job.get("location") or "Remote"
    greet = f"Hi {contact.split()[0]}," if contact else f"Hi {company} team,"
    summary = (
        f"{greet} (use this greeting). This email goes directly to {contact or 'a contact'} "
        f"at {company}. They are a LinkedIn connection / qualified lead, not a generic careers inbox. "
        f"Mention you noticed the open {role} role at {company} and are applying. "
        f"Keep tone respectful and concise, as if writing to a senior contact who may forward internally.\n\n"
        f"JOB POSTING:\n{desc}"
    )
    return write_cover_letter(
        company=company,
        role=role,
        location=loc,
        summary=summary,
        skills="",
        apply_url=job.get("url") or "",
    )


def send_one(*, to: str, company: str, subject: str, body: str) -> None:
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
                time.sleep(15 * (attempt + 1))
    raise last_exc or RuntimeError("send failed")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=50, help="Max sends this run")
    ap.add_argument("--daily-cap", type=int, default=50, help="Max sends today total")
    ap.add_argument("--queue-only", action="store_true")
    args = ap.parse_args()

    if not agent_enabled():
        raise SystemExit("CURSOR_API_KEY required")
    if not FROM or not PASS or not RESUME.exists():
        raise SystemExit("Gmail/resume missing")
    if not LEADS_CSV.exists():
        raise SystemExit(f"Missing {LEADS_CSV}")

    today_n = _today_sent_count()
    room = max(0, args.daily_cap - today_n)
    target = min(args.limit, room)
    print(f"Today sent={today_n} room={room} target={target}", flush=True)
    if target <= 0:
        print("Daily cap reached.", flush=True)
        return

    leads = load_leads()
    print(f"Qualified leads with email: {len(leads)}", flush=True)

    LETTERS.mkdir(parents=True, exist_ok=True)
    queue: list[dict] = []
    sent_e, _ = already_sent()

    for i, lead in enumerate(leads, 1):
        if len(queue) >= target:
            break
        co = lead["company"]
        print(f"\n[{i}] {lead['contact']} @ {co} ({lead['email']})", flush=True)
        job = find_best_job(co, lead["domain"], fetch_desc=False)
        if not job:
            print("  no matching job posting", flush=True)
            continue
        print(f"  job: {job['title'][:55]}", flush=True)
        queue.append({**lead, **job})

    fields = ["Contact", "Email", "Company", "Domain", "Job Title", "Job URL", "Portal", "Letter"]
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for q in queue:
            w.writerow(
                {
                    "Contact": q.get("contact"),
                    "Email": q["email"],
                    "Company": q["company"],
                    "Domain": q.get("domain"),
                    "Job Title": q["title"],
                    "Job URL": q.get("url"),
                    "Portal": q.get("portal"),
                    "Letter": TAG,
                }
            )
    print(f"\nQueue: {len(queue)} → {OUT_CSV}", flush=True)
    if args.queue_only:
        return

    sent_n = 0
    for q in queue:
        if sent_n >= target:
            break
        email = q["email"]
        if email in sent_e:
            continue
        co = q["company"]
        role = q["title"]
        safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", co)[:40]
        letter_path = LETTERS / f"{safe}.txt"
        try:
            desc = q.get("description") or _fetch_description(q)
            if len(desc) < 120:
                print(f"  skip thin posting for {co}", flush=True)
                continue
            q["description"] = desc[:6000]
            if letter_path.exists() and letter_path.stat().st_size > 80:
                body = letter_path.read_text(encoding="utf-8")
                print(f"  reusing letter for {co}", flush=True)
            else:
                print(f"  writing tailored letter for {role} @ {co}…", flush=True)
                body = letter_body(q, q)
                letter_path.write_text(body)
            subj = f"{role[:40]} at {co}"[:58]
            send_one(to=email, company=co, subject=subj, body=body)
            sent_n += 1
            sent_e.add(email)
            print(f"  SENT [{sent_n}/{target}] {email}", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"  FAIL {email}: {exc}", flush=True)
            log_sent(email, co, "failed", str(exc)[:200], letter=TAG, subject=f"{role} at {co}")
            if any(x in str(exc).lower() for x in ("quota", "rate", "blocked", "auth", "421", "454")):
                break
        if sent_n < target:
            wait = max(40.0, DELAY + random.uniform(-8, 18))
            print(f"  wait {wait:.0f}s…", flush=True)
            time.sleep(wait)

    print(f"\nDONE. Qualified leads sent={sent_n}", flush=True)


if __name__ == "__main__":
    main()
