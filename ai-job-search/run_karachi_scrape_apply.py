#!/usr/bin/env python3
"""Karachi tech: scrape real job postings → tailored letter → email → send.

Uses ai-job-search portal CLIs (LinkedIn + freehire) plus careers-page scrape
for Karachi directory companies. Never sends generic cold emails.
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
from concurrent.futures import ThreadPoolExecutor, as_completed
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
from job_hunter.careers import scrape_company_careers  # noqa: E402
from job_hunter.directory import COMPANY_DIRECTORY  # noqa: E402
from job_hunter.emails import pick_hr_email  # noqa: E402
from job_hunter.http import HttpClient  # noqa: E402
from job_hunter.matcher import is_keepable, score_job  # noqa: E402
from job_hunter.models import Job  # noqa: E402
from job_hunter.textutil import extract_emails, html_to_text  # noqa: E402
from send_emails import (  # noqa: E402
    BLOCKED_DOMAINS,
    SKIP_LOCAL,
    already_sent,
    log_sent,
)
from smtp_verify import bounced_emails, verify_mailbox  # noqa: E402

SCRAPE = AIJS / "output_scrape"
DETAILS = SCRAPE / "details"
LETTERS = SCRAPE / "letters"
SEEN = AIJS / "job_scraper" / "seen_jobs.json"
TRACKER = AIJS / "job_search_tracker.csv"
TRACKER_HEADER = "date,company,sector,role,role_type,channel,status,contact_person,fit_rating,notes,cv_file,cover_letter_file,source,deadline"
RESUME = ROOT / "Muhammad_Muddasir_Resume.pdf"
FROM = os.getenv("GMAIL_ADDRESS", "").strip()
PASS = os.getenv("GMAIL_APP_PASSWORD", "").strip()
TAG = "ai-job-search-karachi+cursor"
DELAY = 50.0

LI_CLI = AIJS / ".agents/skills/linkedin-search/cli/src/cli.ts"
FH_CLI = AIJS / ".agents/skills/freehire-search/cli/src/cli.ts"

LI_QUERIES = (
    "software engineer",
    "full stack developer",
    "frontend developer react",
    "AI engineer",
    "next.js typescript",
    "backend developer node",
    "react developer",
    "product engineer",
)

FH_QUERIES = (
    "software engineer",
    "full stack",
    "frontend react",
    "AI engineer",
    "typescript",
)

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

TRAINING_SKIP = re.compile(
    r"\b(trainee|internship|intern\b|apprentice|graduate\s+trainee|bootcamp)\b",
    re.I,
)

NON_TECH_SKIP = re.compile(
    r"\b(bank|hbl|ubl|meezan|faysal|askari|bankislami|jazz|telenor|ufone|zong|ptcl|"
    r"rozee|mustakbil|denim|bestseller|recruitment agency|staffing)\b",
    re.I,
)

VARIANT_SUFFIX = re.compile(r"\s+(Pakistan|Tech|Digital)$", re.I)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


# company name (lower) -> domain from directory
DIR_DOMAIN: dict[str, str] = {}
for _n, _d, _r, _c, _k in COMPANY_DIRECTORY:
    DIR_DOMAIN[_norm(_n)] = _d.lower()


def _domain_for(company: str) -> str:
    key = _norm(company)
    if key in DIR_DOMAIN:
        return DIR_DOMAIN[key]
    for name, dom in DIR_DOMAIN.items():
        if key == name or (len(key) > 4 and (key in name or name in key)):
            return dom
    return ""


def _karachi_loc(loc: str) -> bool:
    return "karachi" in (loc or "").lower() or "karāchi" in (loc or "").lower()


def _ensure_tracker() -> None:
    if not TRACKER.exists():
        TRACKER.write_text(TRACKER_HEADER + "\n", encoding="utf-8")


def _tracker_applied() -> set[str]:
    keys: set[str] = set()
    if not TRACKER.exists():
        return keys
    for row in csv.DictReader(TRACKER.open(encoding="utf-8-sig")):
        co = _norm(row.get("company") or "")
        role = _norm(row.get("role") or "")
        if co and role:
            keys.add(f"{co}::{role}")
    return keys


def _run_cli(cmd: list[str], out_path: Path) -> int:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=str(AIJS))
        if p.returncode != 0:
            print(f"  CLI fail {out_path.name}: {p.stderr[:160]}", flush=True)
            return 0
        data = json.loads(p.stdout)
        results = data.get("results") or []
        out_path.write_text(json.dumps(data, indent=2))
        return len(results)
    except Exception as exc:  # noqa: BLE001
        print(f"  CLI exc {out_path.name}: {exc}", flush=True)
        return 0


def scrape_portals() -> int:
    SCRAPE.mkdir(parents=True, exist_ok=True)
    total = 0
    print("=== LinkedIn Karachi scrape ===", flush=True)
    for q in LI_QUERIES:
        safe = re.sub(r"[^a-z0-9]+", "_", q.lower())[:30]
        out = SCRAPE / f"li_khi_{safe}.json"
        cmd = [
            "bun",
            "run",
            str(LI_CLI),
            "search",
            "-q",
            q,
            "-l",
            "Karachi, Sindh, Pakistan",
            "--jobage",
            "14",
            "--limit",
            "20",
            "--format",
            "json",
        ]
        n = _run_cli(cmd, out)
        print(f"  {q}: {n} hits", flush=True)
        total += n

    print("=== freehire Pakistan scrape ===", flush=True)
    for q in FH_QUERIES:
        safe = re.sub(r"[^a-z0-9]+", "_", q.lower())[:30]
        out = SCRAPE / f"fh_pk_{safe}.json"
        cmd = [
            "bun",
            "run",
            str(FH_CLI),
            "search",
            "-q",
            q,
            "--country",
            "PK",
            "--jobage",
            "14",
            "--limit",
            "25",
            "--no-description",
            "--format",
            "json",
        ]
        n = _run_cli(cmd, out)
        print(f"  {q}: {n} hits", flush=True)
        total += n
    return total


def scrape_karachi_careers(limit: int = 80) -> list[dict]:
    """Scrape careers pages for Karachi tech companies in the directory."""
    sent_e, sent_c = already_sent()
    targets: list[tuple[str, str, tuple[str, ...]]] = []
    seen_dom: set[str] = set()
    for name, domain, region, _city, known in COMPANY_DIRECTORY:
        if region != "Karachi":
            continue
        if VARIANT_SUFFIX.search(name):
            continue
        if NON_TECH_SKIP.search(name):
            continue
        dom = (domain or "").lower()
        if not dom or dom in seen_dom:
            continue
        if name.lower() in sent_c:
            continue
        seen_dom.add(dom)
        targets.append((name, dom, tuple(e for e in known if e)))
    targets = targets[:limit]
    print(f"=== Careers scrape: {len(targets)} Karachi companies ===", flush=True)
    jobs: list[dict] = []

    def one(item: tuple[str, str, tuple[str, ...]]) -> list[dict]:
        name, domain, known = item
        found_jobs, emails = scrape_company_careers(name, domain, known)
        hr = pick_hr_email(emails) or ""
        out: list[dict] = []
        for job in found_jobs:
            if not job.location:
                job.location = "Karachi"
            score_job(job)
            if not is_keepable(
                job,
                include_restricted=False,
                karachi_only=False,
                pakistan_friendly_only=False,
                junior_only=False,
            ):
                continue
            if TRAINING_SKIP.search(f"{job.title} {job.description}"):
                continue
            if hr:
                job.hr_email = hr
                job.emails = list(dict.fromkeys([hr, *emails, *job.emails]))
            out.append(
                {
                    "title": job.title,
                    "company": job.company or name,
                    "url": job.url,
                    "location": job.location or "Karachi",
                    "portal": "careers-scrape",
                    "id": job.source_id or job.dedupe_key,
                    "fit": "high" if job.score >= 55 else "medium",
                    "rank": 0,
                    "description": job.description or "",
                    "hr_email": job.hr_email or "",
                    "emails": job.emails,
                    "domain": domain,
                }
            )
        if out:
            print(f"  HIT {name}: {len(out)} roles", flush=True)
        return out

    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = [pool.submit(one, t) for t in targets]
        for fut in as_completed(futs):
            try:
                jobs.extend(fut.result())
            except Exception as exc:  # noqa: BLE001
                print(f"  careers error: {exc}", flush=True)
    return jobs


def fit_for(title: str, location: str = "") -> str:
    t = (title or "").lower()
    if TRAINING_SKIP.search(t):
        return "low"
    core = any(
        k in t
        for k in (
            "full stack",
            "fullstack",
            "full-stack",
            "frontend",
            "front-end",
            "react",
            "next.js",
            "software engineer",
            "ai engineer",
            "llm",
            "product engineer",
            "typescript",
            "backend",
            "developer",
        )
    )
    bad = any(k in t for k in ("board director", "civil engineer", "wordpress", "sales executive", "qa engineer"))
    if bad or not core:
        return "low"
    return "high" if _karachi_loc(location) else "medium"


def load_portal_jobs() -> list[dict]:
    pool: list[dict] = []
    for path in SCRAPE.glob("*.json"):
        if path.name in {"new_matches.json", "apply_queue.json"}:
            continue
        if "details" in str(path) or "letters" in str(path):
            continue
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue
        portal = "linkedin-search" if path.name.startswith("li_") else "freehire-search"
        if isinstance(data, list):
            results = data
        else:
            results = data.get("results") or []
        for r in results:
            title = (r.get("title") or "").strip()
            company = (r.get("company") or "").strip()
            url = (r.get("url") or r.get("jobUrl") or "").strip()
            rid = r.get("id") or ""
            if not url:
                if portal.startswith("linkedin") and rid:
                    url = f"https://www.linkedin.com/jobs/view/{rid}"
                elif portal.startswith("freehire") and rid:
                    url = f"https://freehire.me/jobs/{rid}"
            loc = r.get("location") or ""
            if isinstance(loc, dict):
                loc = loc.get("label") or loc.get("name") or ""
            if not title or not company or not url:
                continue
            if NON_TECH_SKIP.search(company):
                continue
            if not _karachi_loc(str(loc)):
                continue
            fit = fit_for(title, str(loc))
            if fit == "low":
                continue
            desc = r.get("description") or ""
            pool.append(
                {
                    "title": title,
                    "company": company,
                    "url": url,
                    "location": str(loc),
                    "portal": portal,
                    "id": rid,
                    "fit": fit,
                    "rank": 0,
                    "description": desc,
                }
            )
    return pool


def merge_jobs(portal: list[dict], careers: list[dict], applied: set[str]) -> list[dict]:
    by_url: dict[str, dict] = {}
    for j in portal + careers:
        url = (j.get("url") or "").strip()
        if not url:
            continue
        role_key = f"{_norm(j['company'])}::{_norm(j['title'])}"
        if role_key in applied:
            continue
        if url in by_url:
            continue
        dom = _domain_for(j["company"])
        if dom:
            j = {**j, "domain": dom}
        by_url[url] = j
    return sorted(
        by_url.values(),
        key=lambda x: (0 if x["fit"] == "high" else 1, 0 if x.get("description") else 1, x["company"]),
    )


def fetch_detail(job: dict) -> dict | None:
    if job.get("description"):
        return {"description": job["description"], "_meta": job}
    DETAILS.mkdir(parents=True, exist_ok=True)
    portal = job["portal"]
    jid = job.get("id") or ""
    url = job["url"]
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", job["company"])[:40]
    out = DETAILS / f"{safe}.json"
    if out.exists():
        data = json.loads(out.read_text())
        data["_meta"] = {**job, **(data.get("_meta") or {})}
        return data
    if portal.startswith("freehire"):
        cmd = ["bun", "run", str(FH_CLI), "detail", jid or url, "--format", "json"]
    elif portal.startswith("linkedin"):
        cmd = ["bun", "run", str(LI_CLI), "detail", jid or url, "--format", "json"]
    else:
        return {"description": job.get("description") or "", "_meta": job}
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=90, cwd=str(AIJS))
        if p.returncode != 0:
            print(f"  detail fail {job['company']}: {p.stderr[:120]}", flush=True)
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
        print(f"  detail exc {job['company']}: {exc}", flush=True)
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
    company = meta.get("company") or detail.get("company") or ""
    desc = str(detail.get("description") or "")
    if TRAINING_SKIP.search(desc):
        return None

    posted = (meta.get("hr_email") or "").strip().lower()
    domain = (meta.get("domain") or _domain_for(company)).lower()
    apply_url = detail.get("url") or meta.get("url") or ""

    found: list[str] = []
    if posted and usable_email(posted, sent_e, bounced):
        found.append(posted)
    for e in meta.get("emails") or []:
        if usable_email(e, sent_e, bounced):
            found.append(e.lower())
    found += extract_emails(desc)
    for u in dict.fromkeys([apply_url, meta.get("url") or ""]):
        if not u or any(h in u for h in ("linkedin.com", "freehire.me", "whatjobs.com")):
            continue
        html = client.get_html(u) or ""
        found += extract_emails(html_to_text(html) + " " + html)
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
            0 if e in desc_set or e == posted else 1,
            0
            if any(t in e.split("@")[0] for t in ("career", "job", "hr", "talent", "hello", "hi", "apply", "team"))
            else 1,
        ),
    )
    for email in ordered:
        ok, detail_s = verify_mailbox(email)
        if ok:
            return email, "strict-valid"
        if email in desc_set or email == posted:
            if "user unknown" not in detail_s.lower() and "does not exist" not in detail_s.lower():
                return email, "user-forced published"
            if "catch-all" in detail_s.lower():
                return email, "user-forced published catch-all"
    if domain:
        for local in ("hello", "hi", "careers", "jobs", "talent", "hr", "team"):
            email = f"{local}@{domain}"
            if not usable_email(email, sent_e, bounced):
                continue
            ok, _detail_s = verify_mailbox(email)
            if ok:
                return email, "strict-valid"
    return None


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
                wait = 15 * (attempt + 1)
                print(f"  send retry {attempt + 2}/3 after {wait}s ({exc})…", flush=True)
                time.sleep(wait)
    raise last_exc or RuntimeError("send failed")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-scrape", action="store_true", help="Reuse output_scrape JSON")
    ap.add_argument("--skip-careers", action="store_true", help="Skip careers-page crawl")
    ap.add_argument("--limit", type=int, default=40, help="Max sends this run")
    ap.add_argument("--daily-cap", type=int, default=75, help="Max sends today total")
    args = ap.parse_args()

    if not agent_enabled():
        raise SystemExit("CURSOR_API_KEY required for tailored letters")
    if not FROM or not PASS or not RESUME.exists():
        raise SystemExit("Gmail/resume missing")

    _ensure_tracker()
    sent_e, _sent_c = already_sent()
    bounced = bounced_emails()
    applied = _tracker_applied()

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
        print("Daily cap reached.", flush=True)
        return

    if not args.skip_scrape:
        scrape_portals()

    portal_jobs = load_portal_jobs()
    careers_jobs = [] if args.skip_careers else scrape_karachi_careers(limit=90)
    jobs = merge_jobs(portal_jobs, careers_jobs, applied)
    print(f"Karachi posting pool (deduped): {len(jobs)}  (portal={len(portal_jobs)} careers={len(careers_jobs)})", flush=True)

    seen = json.loads(SEEN.read_text()) if SEEN.exists() else {"seen": {}}
    today_d = date.today().isoformat()
    for j in jobs:
        key = j["url"]
        if key not in seen["seen"]:
            seen["seen"][key] = {
                "title": j["title"],
                "company": j["company"],
                "url": j["url"],
                "first_seen": today_d,
                "deadline": None,
                "fit": j["fit"],
                "status": "new",
                "portal": j["portal"],
                "source": "cli",
                "location": j["location"],
            }
    SEEN.write_text(json.dumps(seen, indent=2) + "\n")

    client = HttpClient()
    LETTERS.mkdir(parents=True, exist_ok=True)
    sent_n = 0
    tried = 0
    try:
        for job in jobs:
            if sent_n >= target:
                break
            if tried >= target * 10:
                break
            tried += 1
            co = job["company"]
            title = job["title"]
            print(f"\n[{tried}] {title[:55]} @ {co}", flush=True)
            if TRAINING_SKIP.search(title):
                print("  skip trainee/intern title", flush=True)
                continue
            detail = fetch_detail(job)
            if not detail:
                continue
            desc = str(detail.get("description") or "")
            if len(desc) < 80:
                print("  skip — posting too thin for tailored letter", flush=True)
                continue
            if TRAINING_SKIP.search(desc):
                print("  skip trainee/intern in posting", flush=True)
                continue
            hit = resolve_email(detail, sent_e, bounced, client)
            if not hit:
                print("  no verified email on posting", flush=True)
                continue
            email, smtp_tag = hit
            if email in sent_e:
                print(f"  skip already sent {email}", flush=True)
                continue
            print(f"  email {email} [{smtp_tag}]", flush=True)
            skills = detail.get("skills") or []
            skills_s = ", ".join(skills) if isinstance(skills, list) else str(skills)
            safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", co)[:40]
            letter_path = LETTERS / f"{safe}.txt"
            if letter_path.exists() and letter_path.stat().st_size > 80:
                body = letter_path.read_text(encoding="utf-8")
                print("  reusing cached tailored letter", flush=True)
            else:
                try:
                    print("  writing tailored letter from posting…", flush=True)
                    body = write_cover_letter(
                        company=co,
                        role=title,
                        location=job.get("location") or "Karachi",
                        summary=desc[:5000],
                        skills=skills_s,
                        apply_url=job.get("url") or "",
                    )
                except Exception as exc:  # noqa: BLE001
                    print(f"  letter fail: {exc}", flush=True)
                    continue
                letter_path.write_text(body)
            print(f"  preview: {' '.join(body.split())[:160]}…", flush=True)
            subj = f"{title[:42]} at {co}"[:58]
            try:
                send_one(to=email, company=co, subject=subj, body=body)
                sent_n += 1
                sent_e.add(email)
                print(f"  SENT [{sent_n}/{target}] {email}", flush=True)
                with TRACKER.open("a", encoding="utf-8", newline="") as f:
                    csv.writer(f).writerow(
                        [
                            today_d,
                            co,
                            "tech",
                            title,
                            "IC",
                            "email",
                            "sent",
                            email,
                            "",
                            f"karachi scrape→{email}",
                            "",
                            str(LETTERS / f"{safe}.txt"),
                            job.get("url") or "",
                            "",
                        ]
                    )
                if key := job.get("url"):
                    if key in seen["seen"]:
                        seen["seen"][key]["status"] = "applied"
                        SEEN.write_text(json.dumps(seen, indent=2) + "\n")
            except Exception as exc:  # noqa: BLE001
                print(f"  SEND FAIL {exc}", flush=True)
                log_sent(email, co, "failed", str(exc)[:200], letter=TAG, subject=subj)
                if any(x in str(exc).lower() for x in ("quota", "rate", "blocked", "auth", "421", "454")):
                    break
            if sent_n < target:
                wait = max(40.0, DELAY + random.uniform(-8, 18))
                print(f"  wait {wait:.0f}s…", flush=True)
                time.sleep(wait)
    finally:
        client.close()
    print(f"\nDONE. Karachi posting-based sent={sent_n}", flush=True)


if __name__ == "__main__":
    main()
