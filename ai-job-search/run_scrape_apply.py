#!/usr/bin/env python3
"""ai-job-search flow: scrape results → detail → find email → tailored letter → send.

Uses portal CLI outputs under output_scrape/, Cursor letter agent (ai-job-search voice),
and Gmail SMTP. Never uses leftover CSV Mad-Libs or unverified careers@ guesses.
"""
from __future__ import annotations

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
from job_hunter.http import HttpClient  # noqa: E402
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
RESUME = ROOT / "Muhammad_Muddasir_Resume.pdf"
FROM = os.getenv("GMAIL_ADDRESS", "").strip()
PASS = os.getenv("GMAIL_APP_PASSWORD", "").strip()

TARGET = 50
DELAY = 50.0
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

DOMAIN_HINTS = {
    "crost ai": "crost.ai",
    "dash0": "dash0.com",
    "innovage.io": "innovage.io",
    "expertshub.ai": "expertshub.ai",
    "remotedxb": "remotedxb.com",
    "remotestar-team": "remotestar.io",
    "remotestar": "remotestar.io",
    "kellton europe": "kellton.com",
    "cloud people": "cloudpeople.com",
    "be-it": "be-it.co.uk",
    "remote raven": "remoteraven.com",
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def fit_for(title: str, location: str = "") -> str:
    t = (title or "").lower()
    loc = (location or "").lower()
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
        )
    )
    bad = any(k in t for k in ("board director", "civil engineer", "sales", "qa engineer", "wordpress"))
    if bad:
        return "low"
    pk_or_remote = any(
        k in loc for k in ("pakistan", "karachi", "lahore", "islamabad", "remote", "worldwide", "emea", "dubai")
    ) or "remote" in t
    if core and pk_or_remote:
        return "high"
    if core:
        return "medium"
    return "low"


def pk_rank(loc: str) -> int:
    loc = (loc or "").lower()
    if any(x in loc for x in ("pakistan", "karachi", "lahore", "islamabad", "peshawar")):
        return 0
    if "worldwide" in loc or "emea" in loc or loc.strip() in {"remote", ""}:
        return 1
    if any(x in loc for x in ("united kingdom", "dubai", "uae")):
        return 2
    bad = (
        "united states",
        "canada",
        "brazil",
        "brasil",
        "mexico",
        "australia",
        "india",
        "germany",
        "lithuania",
    )
    if any(b in loc for b in bad):
        return 9
    return 3


def load_scrape_results() -> list[dict]:
    pool = []
    for path in SCRAPE.glob("*.json"):
        if path.name in {"new_matches.json", "apply_queue.json", "ready_to_send.json", "email_resolve.json", "wave.json"}:
            continue
        if path.parent.name == "details" or "letters" in str(path):
            continue
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue
        results = data.get("results") or []
        portal = "linkedin-search" if path.name.startswith("li_") else "freehire-search"
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
            fit = fit_for(title, str(loc))
            if fit == "low":
                continue
            if pk_rank(str(loc)) >= 9:
                continue
            pool.append(
                {
                    "title": title,
                    "company": company,
                    "url": url,
                    "location": str(loc),
                    "portal": portal,
                    "id": rid,
                    "fit": fit,
                    "rank": pk_rank(str(loc)),
                }
            )
    # dedupe company
    by_co: dict[str, dict] = {}
    for j in pool:
        key = _norm(j["company"])
        if "tuotempo" in key:
            key = "tuotempo"
        if "smart working" in key:
            key = "smart working"
        prev = by_co.get(key)
        if not prev or j["rank"] < prev["rank"] or (j["rank"] == prev["rank"] and j["fit"] == "high" and prev["fit"] != "high"):
            by_co[key] = j
    return sorted(by_co.values(), key=lambda x: (x["rank"], 0 if x["fit"] == "high" else 1, x["company"]))


def fetch_detail(job: dict) -> dict | None:
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
        cmd = [
            "bun",
            "run",
            str(AIJS / ".agents/skills/freehire-search/cli/src/cli.ts"),
            "detail",
            jid or url,
            "--format",
            "json",
        ]
    else:
        cmd = [
            "bun",
            "run",
            str(AIJS / ".agents/skills/linkedin-search/cli/src/cli.ts"),
            "detail",
            jid or url,
            "--format",
            "json",
        ]
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
    apply_url = detail.get("url") or meta.get("url") or ""
    domain = DOMAIN_HINTS.get(_norm(company), "")
    if not domain and apply_url:
        # try company slug from freehire
        slug = detail.get("company_slug") or ""
        if slug and "." not in slug:
            domain = slug.replace("-", "") + ".com"  # weak; skip
            domain = ""

    found: list[str] = []
    found += extract_emails(desc)
    for u in dict.fromkeys([apply_url, meta.get("url") or ""]):
        if not u or any(h in u for h in ("linkedin.com", "freehire.me")):
            continue
        html = client.get_html(u) or ""
        found += extract_emails(html_to_text(html) + " " + html)
    if domain:
        for path in ("/careers", "/jobs", "/contact", "/about", "/"):
            html = client.get_html(f"https://{domain}{path}") or client.get_html(f"https://www.{domain}{path}") or ""
            if html:
                found += extract_emails(html_to_text(html) + " " + html)
                if any(e.lower().endswith("@" + domain) for e in found):
                    break

    emails = list(dict.fromkeys(e.lower() for e in found if usable_email(e, sent_e, bounced)))
    desc_set = {e.lower() for e in extract_emails(desc)}
    ordered = sorted(
        emails,
        key=lambda e: (
            0 if e in desc_set else 1,
            0
            if any(t in e.split("@")[0] for t in ("career", "job", "hr", "talent", "hello", "hi", "developer", "apply", "team", "join"))
            else 1,
        ),
    )
    for email in ordered:
        ok, detail_s = verify_mailbox(email)
        if ok:
            return email, "strict-valid"
        if email in desc_set and "user unknown" not in detail_s.lower() and "mailbox does not exist" not in detail_s.lower():
            return email, "user-forced published"
        if email in desc_set and "catch-all" in detail_s.lower():
            return email, "user-forced published catch-all"
    # SMTP-strict common locals only for known domains from hints
    if domain:
        for local in ("hello", "hi", "careers", "jobs", "talent", "hr", "team", "join"):
            email = f"{local}@{domain}"
            if not usable_email(email, sent_e, bounced):
                continue
            ok, detail_s = verify_mailbox(email)
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
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as smtp:
        smtp.starttls(context=ctx)
        smtp.login(FROM, PASS)
        smtp.sendmail(FROM, [to], msg.as_string())
    log_sent(to, company, "sent", letter="ai-job-search-scrape+cursor", subject=subject)


def main() -> None:
    if not agent_enabled():
        raise SystemExit("CURSOR_API_KEY required for tailored letters")
    if not FROM or not PASS or not RESUME.exists():
        raise SystemExit("Gmail/resume missing")

    sent_e, sent_c = already_sent()
    bounced = bounced_emails()
    today = datetime.now(timezone.utc).date().isoformat()
    today_n = 0
    slog = ROOT / "outreach" / "sent_log.csv"
    if slog.exists():
        for row in csv.DictReader(slog.open(encoding="utf-8-sig")):
            if row.get("status") == "sent" and (row.get("sent_at") or "").startswith(today):
                today_n += 1
    room = max(0, 80 - today_n)
    target = min(TARGET, room)
    print(f"Today sent={today_n} room={room} target={target}", flush=True)

    jobs = load_scrape_results()
    print(f"Scrape pool (deduped PK-friendly): {len(jobs)}", flush=True)

    # update seen_jobs
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
            if tried >= target * 8:
                break
            tried += 1
            co = job["company"]
            print(f"\n[{tried}] {job['title'][:50]} @ {co}", flush=True)
            detail = fetch_detail(job)
            if not detail:
                continue
            hit = resolve_email(detail, sent_e, bounced, client)
            if not hit:
                print("  no verified email", flush=True)
                continue
            email, smtp_tag = hit
            if email in sent_e:
                print(f"  skip already sent {email}", flush=True)
                continue
            print(f"  email {email} [{smtp_tag}]", flush=True)
            desc = str(detail.get("description") or "")[:4000]
            skills = detail.get("skills") or []
            skills_s = ", ".join(skills) if isinstance(skills, list) else str(skills)
            try:
                print("  writing tailored letter…", flush=True)
                body = write_cover_letter(
                    company=co,
                    role=job["title"],
                    location=job.get("location") or "",
                    summary=desc,
                    skills=skills_s,
                    apply_url=job.get("url") or "",
                )
            except Exception as exc:  # noqa: BLE001
                print(f"  letter fail: {exc}", flush=True)
                continue
            LETTERS.joinpath(re.sub(r"[^a-zA-Z0-9_-]+", "_", co)[:40] + ".txt").write_text(body)
            preview = " ".join(body.split())[:160]
            print(f"  preview: {preview}", flush=True)
            subj = f"{job['title'][:40]} at {co}"[:58]
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
                            job["title"],
                            "IC",
                            "email",
                            "sent",
                            "",
                            "",
                            f"ai-job-search scrape→{email}",
                            "",
                            "",
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
                log_sent(email, co, "failed", str(exc)[:200], letter="ai-job-search-scrape+cursor", subject=subj)
                if any(x in str(exc).lower() for x in ("quota", "rate", "blocked", "auth", "421", "454")):
                    break
            if sent_n < target:
                wait = max(40.0, DELAY + random.uniform(-8, 18))
                print(f"  wait {wait:.0f}s…", flush=True)
                time.sleep(wait)
    finally:
        client.close()
    print(f"\nDONE. Sent {sent_n} via ai-job-search scrape flow.", flush=True)


if __name__ == "__main__":
    main()
