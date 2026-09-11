#!/usr/bin/env python3
"""Until-50: ai-job-search scrape → <3 YOE filter → email → tailored letter → send.

Regions: Karachi onsite, Pakistan, MENA/GCC (Dubai/UAE/Saudi/Qatar/Bahrain/Kuwait),
Singapore, Malaysia, remote worldwide.
No Qualified Leads CSV. Uses Hunter + careers scrape + posting emails (SMTP-strict).
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
from job_hunter.careers import scrape_company_careers  # noqa: E402
from job_hunter.emails import (  # noqa: E402
    HunterClient,
    pick_hr_email,
    resolve_company_domain,
)
from job_hunter.experience import role_ok_for_junior  # noqa: E402
from job_hunter.harvester_emails import harvest_emails, harvester_available  # noqa: E402
from job_hunter.http import HttpClient  # noqa: E402
from job_hunter.models import Job  # noqa: E402
from job_hunter.textutil import extract_emails, html_to_text  # noqa: E402
from send_emails import BLOCKED_DOMAINS, SKIP_LOCAL, already_sent, log_sent  # noqa: E402
from smtp_verify import bounced_emails, verify_mailbox  # noqa: E402

SCRAPE = AIJS / "output_scrape" / "until50"
DETAILS = SCRAPE / "details"
LETTERS = SCRAPE / "letters"
TRACKER = AIJS / "job_search_tracker.csv"
OUT_CSV = ROOT / "output" / f"emails_until50_{date.today().isoformat()}.csv"
RESUME_NEXT = ROOT / "Muhammad_Muddasir_Resume.pdf"
RESUME_AI = ROOT / "Muhammad_Muddasir_Resume.pdf"  # Next/Python/AI
RESUME_GO = Path(os.getenv("GO_RESUME", str(ROOT / "go" / "MuddasirRizwan_Resume.pdf")))

FROM = os.getenv("GMAIL_ADDRESS", "").strip()
PASS = os.getenv("GMAIL_APP_PASSWORD", "").strip()
TAG = "until50_aijs+cursor"
DELAY = 45.0
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
    "myworkdayjobs.com",
    "manatal.com",
    "icims.com",
    "workable.com",
    "recruitee.com",
    "bamboohr.com",
    "smartrecruiters.com",
    "jobvite.com",
    "greenhouse.io",
    "applytojob.com",
    "teamtailor.com",
    "personio.de",
    "personio.com",
    "rippling.com",
}

STACK_OK = re.compile(
    r"\b(react|next\.?js|frontend|front[- ]?end|full[- ]?stack|typescript|"
    r"python|fastapi|golang|go engineer|go developer|ai engineer|llm|"
    r"langgraph|software engineer|backend engineer|product engineer)\b",
    re.I,
)
STACK_GO = re.compile(r"\b(golang|go developer|go engineer)\b", re.I)
STACK_AI = re.compile(r"\b(ai engineer|llm|langgraph|agentic|rag)\b", re.I)
BAD = re.compile(
    r"\b(wordpress|php developer|sales executive|recruiter|qa engineer|"
    r"intern\b|trainee|apprentice|phd required)\b",
    re.I,
)
GEO_OK = re.compile(
    r"pakistan|karachi|lahore|islamabad|remote|worldwide|emea|gulf|mena|"
    r"uae|dubai|abu dhabi|saudi|riyadh|jeddah|qatar|doha|bahrain|kuwait|oman|"
    r"singapore|malaysia|kuala lumpur|egypt|jordan|lebanon|work from anywhere",
    re.I,
)
GEO_BAD_ONSITE = re.compile(
    r"\b(united states|usa|canada|brazil|mexico|australia|india|germany|"
    r"lithuania|poland|netherlands|sweden|norway|france|uk only)\b",
    re.I,
)

LI_SEARCHES = [
    ("React Next.js", "Karachi, Sindh, Pakistan"),
    ("Frontend React", "Karachi, Sindh, Pakistan"),
    ("Software Engineer", "Karachi, Sindh, Pakistan"),
    ("AI Engineer", "Karachi, Sindh, Pakistan"),
    ("Full Stack Developer", "Pakistan"),
    ("React Developer", "Dubai, United Arab Emirates"),
    ("Frontend Engineer", "Dubai, United Arab Emirates"),
    ("Software Engineer", "United Arab Emirates"),
    ("AI Engineer", "United Arab Emirates"),
    ("Golang", "Dubai, United Arab Emirates"),
    ("React Developer", "Riyadh, Saudi Arabia"),
    ("Software Engineer", "Doha, Qatar"),
    ("Frontend Developer", "Bahrain"),
    ("React Next.js", "Singapore"),
    ("Golang", "Singapore"),
    ("Software Engineer Python", "Singapore"),
    ("Frontend React", "Kuala Lumpur, Malaysia"),
    ("Full Stack", "Malaysia"),
    ("React Next.js", "Remote"),
    ("AI Engineer LangChain", "Remote"),
    ("Golang Developer", "Remote"),
    ("Frontend TypeScript", "Remote"),
    ("Junior Software Engineer", "Remote"),
    ("Python FastAPI", "Remote"),
    ("Full Stack Next.js", "Remote"),
]

FH_SEARCHES = [
    (["-q", "Next.js React", "--country", "PK", "--jobage", "30", "--limit", "25", "--no-description"]),
    (["-q", "AI engineer", "--country", "PK", "--jobage", "30", "--limit", "20", "--no-description"]),
    (["-q", "React", "--remote", "remote", "--jobage", "30", "--limit", "25", "--no-description"]),
    (["-q", "Golang", "--remote", "remote", "--jobage", "30", "--limit", "20", "--no-description"]),
    (["-q", "Next.js", "--remote", "remote", "--jobage", "30", "--limit", "25", "--no-description"]),
    (["-q", "AI engineer", "--remote", "remote", "--jobage", "30", "--limit", "20", "--no-description"]),
    (["-q", "frontend", "--country", "AE", "--jobage", "30", "--limit", "15", "--no-description"]),
    (["-q", "software engineer", "--country", "SG", "--jobage", "30", "--limit", "20", "--no-description"]),
    (["-q", "React", "--country", "MY", "--jobage", "30", "--limit", "15", "--no-description"]),
]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _run(cmd: list[str], out: Path) -> int:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=str(AIJS))
        if p.returncode != 0:
            return 0
        data = json.loads(p.stdout)
        out.write_text(json.dumps(data, indent=2))
        return len(data.get("results") or [])
    except Exception:
        return 0


def scrape_all() -> None:
    SCRAPE.mkdir(parents=True, exist_ok=True)
    print("=== LinkedIn scrape ===", flush=True)
    for q, loc in LI_SEARCHES:
        safe = re.sub(r"[^a-z0-9]+", "_", f"li_{q}_{loc}".lower())[:50]
        out = SCRAPE / f"{safe}.json"
        n = _run(
            [
                "bun",
                "run",
                str(LI_CLI),
                "search",
                "-q",
                q,
                "-l",
                loc,
                "--jobage",
                "30",
                "--limit",
                "20",
                "--format",
                "json",
            ],
            out,
        )
        print(f"  {q} @ {loc}: {n}", flush=True)
    print("=== freehire scrape ===", flush=True)
    for i, flags in enumerate(FH_SEARCHES):
        out = SCRAPE / f"fh_{i}.json"
        n = _run(["bun", "run", str(FH_CLI), "search", *flags, "--format", "json"], out)
        print(f"  fh_{i}: {n}", flush=True)


def geo_ok(loc: str, title: str = "") -> bool:
    blob = f"{loc} {title}"
    if GEO_OK.search(blob):
        return True
    if "remote" in title.lower() or loc.strip().lower() in {"remote", ""}:
        return True
    if GEO_BAD_ONSITE.search(loc) and "remote" not in loc.lower():
        return False
    return False


def load_prior_emails() -> dict[str, str]:
    """Map company→verified email from prior output CSVs (not leads CSV)."""
    mapping: dict[str, str] = {}
    for path in Path(ROOT / "output").glob("emails_*.csv"):
        if "qualified" in path.name.lower() or "lead" in path.name.lower():
            continue
        try:
            for r in csv.DictReader(path.open(encoding="utf-8-sig")):
                co = (r.get("Company") or "").strip()
                em = (r.get("HR / Recruiter Email") or r.get("Email") or "").strip().lower()
                smtp = (r.get("SMTP Verification") or "").lower()
                if not co or "@" not in em:
                    continue
                if "guess" in (r.get("Email Source") or "").lower():
                    continue
                if "strict-valid" in smtp or "cache strict" in smtp or not smtp:
                    mapping.setdefault(_norm(co), em)
        except Exception:
            continue
    return mapping


def load_mailbox_by_domain() -> dict[str, list[str]]:
    """domain → strict-valid emails from outreach/mailbox_cache.csv."""
    by: dict[str, list[str]] = {}
    path = ROOT / "outreach" / "mailbox_cache.csv"
    if not path.exists():
        return by
    try:
        for r in csv.DictReader(path.open(encoding="utf-8-sig")):
            if (r.get("status") or "") not in ("strict-valid", "valid"):
                continue
            em = (r.get("email") or "").strip().lower()
            if "@" not in em:
                continue
            dom = em.split("@", 1)[1]
            by.setdefault(dom, [])
            if em not in by[dom]:
                by[dom].append(em)
    except Exception:
        return by
    return by


def load_invalid_emails() -> set[str]:
    bad: set[str] = set()
    path = ROOT / "outreach" / "mailbox_cache.csv"
    if not path.exists():
        return bad
    try:
        for r in csv.DictReader(path.open(encoding="utf-8-sig")):
            if (r.get("status") or "") in ("invalid", "reject", "no-mx"):
                em = (r.get("email") or "").strip().lower()
                if "@" in em:
                    bad.add(em)
    except Exception:
        return bad
    return bad


def load_company_domains() -> dict[str, str]:
    """Fuzzy company-name → domain from prior sends/CSVs (Hunter is out of credits)."""
    mapping: dict[str, str] = {}

    def add(co: str, domain: str) -> None:
        domain = (domain or "").strip().lower().removeprefix("www.")
        if not co or not domain or "." not in domain:
            return
        if domain in BLOCKED_DOMAINS or domain in AGGREGATOR_HOSTS:
            return
        if any(domain.endswith(h) or domain == h for h in AGGREGATOR_HOSTS):
            return
        mapping.setdefault(_norm(co), domain)

    for path in Path(ROOT / "output").glob("emails_*.csv"):
        if "qualified" in path.name.lower() or "lead" in path.name.lower():
            continue
        try:
            for r in csv.DictReader(path.open(encoding="utf-8-sig")):
                co = (r.get("Company") or "").strip()
                em = (r.get("HR / Recruiter Email") or r.get("Email") or "").strip().lower()
                if co and "@" in em:
                    add(co, em.split("@", 1)[1])
        except Exception:
            continue
    sent_path = ROOT / "outreach" / "sent_log.csv"
    if sent_path.exists():
        try:
            for r in csv.DictReader(sent_path.open(encoding="utf-8-sig")):
                co = (r.get("company") or "").strip()
                em = (r.get("email") or "").strip().lower()
                if co and "@" in em:
                    add(co, em.split("@", 1)[1])
        except Exception:
            pass
    return mapping


def domain_from_maps(company: str, co_dom: dict[str, str]) -> str:
    k = _norm(company)
    if not k:
        return ""
    if k in co_dom:
        return co_dom[k]
    best = ""
    best_score = 0.0
    for pk, dom in co_dom.items():
        if len(pk) < 8 or len(k) < 8:
            continue
        if pk in k or k in pk:
            shorter, longer = (pk, k) if len(pk) <= len(k) else (k, pk)
            score = len(shorter) / max(1, len(longer))
            # require strong containment (Systems Limited vs Systems Limited APAC)
            if score >= 0.72 and score > best_score:
                best_score = score
                best = dom
    return best


def detail_has_email(job: dict) -> bool:
    """True if cached detail JSON already contains a mailto-ish address."""
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", f"{job.get('company','')}_{job.get('title','')}")[:50]
    path = DETAILS / f"{safe}.json"
    if not path.exists():
        return False
    try:
        blob = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False
    return bool(re.search(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", blob, re.I))


def load_jobs() -> list[dict]:
    pool: list[dict] = []
    for path in list(SCRAPE.glob("*.json")) + list((AIJS / "output_scrape" / "batch50").glob("*.json")):
        if path.parent.name in {"details", "letters"}:
            continue
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
            url = (r.get("url") or "").strip()
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
            if BAD.search(title) or not STACK_OK.search(title):
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
                    "description": r.get("description") or "",
                }
            )
    by_co: dict[str, dict] = {}
    for j in pool:
        key = _norm(j["company"])
        prev = by_co.get(key)
        # prefer Karachi / PK, then remote, then longer description
        score = (
            0 if "karachi" in j["location"].lower() else 1,
            0 if "pakistan" in j["location"].lower() else 1,
            0 if "remote" in j["location"].lower() else 1,
            0 if j.get("description") else 1,
        )
        if not prev:
            by_co[key] = j
            continue
        prev_score = (
            0 if "karachi" in prev["location"].lower() else 1,
            0 if "pakistan" in prev["location"].lower() else 1,
            0 if "remote" in prev["location"].lower() else 1,
            0 if prev.get("description") else 1,
        )
        if score < prev_score:
            by_co[key] = j
    return sorted(by_co.values(), key=lambda x: x["company"].lower())


def resume_for(title: str) -> Path:
    t = title.lower()
    if STACK_GO.search(t) and RESUME_GO.exists():
        return RESUME_GO
    if STACK_AI.search(t) and RESUME_AI.exists():
        return RESUME_AI
    return RESUME_NEXT


def fetch_detail(job: dict) -> dict | None:
    if job.get("description") and len(str(job["description"])) > 150:
        return {"description": job["description"], "_meta": job, "url": job.get("url")}
    DETAILS.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", f"{job['company']}_{job['title']}")[:50]
    out = DETAILS / f"{safe}.json"
    if out.exists():
        data = json.loads(out.read_text())
        data["_meta"] = {**job, **(data.get("_meta") or {})}
        return data
    jid = job.get("id") or job.get("url") or ""
    if job["portal"].startswith("freehire"):
        cmd = ["bun", "run", str(FH_CLI), "detail", jid, "--format", "json"]
    else:
        cmd = ["bun", "run", str(LI_CLI), "detail", jid, "--format", "json"]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=90, cwd=str(AIJS))
        if p.returncode != 0:
            return None
        data = json.loads(p.stdout)
        if "result" in data:
            data = data["result"]
        if isinstance(data.get("results"), list) and data["results"]:
            data = data["results"][0]
        data["_meta"] = job
        out.write_text(json.dumps(data, indent=2))
        return data
    except Exception:
        return None


def usable(email: str, sent_e: set[str], bounced: set[str]) -> bool:
    email = email.lower().strip()
    if not email or email in sent_e or email in bounced or "@" not in email:
        return False
    local, _, host = email.partition("@")
    if local in SKIP_LOCAL or host in BLOCKED_DOMAINS or host in AGGREGATOR_HOSTS:
        return False
    if host in {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "linkedin.com"}:
        return False
    return True


def resolve_email(
    detail: dict,
    sent_e: set[str],
    bounced: set[str],
    client: HttpClient,
    hunter: HunterClient,
    prior: dict[str, str],
    mb_by_dom: dict[str, list[str]] | None = None,
    co_dom: dict[str, str] | None = None,
    invalid_emails: set[str] | None = None,
) -> tuple[str, str] | None:
    meta = detail.get("_meta") or {}
    company = meta.get("company") or detail.get("company") or ""
    title = meta.get("title") or ""
    desc = str(detail.get("description") or "")
    if not role_ok_for_junior(title, desc):
        return None
    mb_by_dom = mb_by_dom or {}
    co_dom = co_dom or {}
    invalid_emails = invalid_emails or set()

    candidates: list[str] = []
    # prior verified CSV emails for this company — trust unless known-invalid
    if _norm(company) in prior:
        pem = prior[_norm(company)]
        if usable(pem, sent_e, bounced) and pem not in invalid_emails:
            return pem, "prior-csv"
    candidates += extract_emails(desc)

    apply_url = detail.get("url") or meta.get("url") or ""
    for u in dict.fromkeys([apply_url]):
        if not u or any(h in u for h in AGGREGATOR_HOSTS):
            continue
        html = client.get_html(u) or ""
        candidates += extract_emails(html_to_text(html) + " " + html)

    # resolve domain + careers scrape
    job = Job(
        source="until50",
        source_id=meta.get("id") or "",
        title=title,
        company=company,
        url=apply_url or "",
        location=meta.get("location") or "",
        description=desc,
    )
    domain = resolve_company_domain(job) or ""
    if not domain:
        domain = domain_from_maps(company, co_dom)
    if hunter.enabled and not domain:
        domain = hunter._find_domain(company)  # noqa: SLF001
    if domain:
        # Fast path: already SMTP-proven addresses for this domain
        for em in mb_by_dom.get(domain, []) + mb_by_dom.get(domain.removeprefix("www."), []):
            if usable(em, sent_e, bounced):
                candidates.append(em)
        try:
            _jobs, emails = scrape_company_careers(company, domain, ())
            candidates += emails
            for j in _jobs[:3]:
                candidates += j.emails
        except Exception:
            pass
        for path in ("/careers", "/jobs", "/contact", "/"):
            html = client.get_html(f"https://{domain}{path}") or client.get_html(f"https://www.{domain}{path}") or ""
            if html:
                candidates += extract_emails(html_to_text(html) + " " + html)
        if hunter.enabled:
            tmp = Job(
                source="h",
                source_id="",
                title=title,
                company=company,
                url="",
                company_domain=domain,
            )
            hunter.enrich(tmp)
            if tmp.hr_email:
                candidates.append(tmp.hr_email)
            candidates += tmp.emails
        # theHarvester OSINT (local ./harvester) — public emails for this domain
        try:
            hv = harvest_emails(domain, timeout_sec=75)
            if hv:
                print(f"  harvester emails: {len(hv)}", flush=True)
                candidates += hv
        except Exception as exc:  # noqa: BLE001
            print(f"  harvester skip: {exc}", flush=True)
        # Always try HR locals when we know the domain (Hunter may be rate-limited)
        for local in ("careers", "jobs", "hr", "hello", "talent", "join", "team", "recruiting"):
            candidates.append(f"{local}@{domain}")

    emails = list(dict.fromkeys(e.lower() for e in candidates if usable(e, sent_e, bounced) and e not in invalid_emails))
    # Prefer emails on the company domain when known
    if domain:
        same_dom = [e for e in emails if e.endswith("@" + domain) or e.split("@")[-1].endswith("." + domain)]
        other = [e for e in emails if e not in same_dom]
        emails = same_dom + other
    desc_set = {e.lower() for e in extract_emails(desc)}
    cache_set = set()
    if domain:
        cache_set = set(mb_by_dom.get(domain, [])) | set(mb_by_dom.get(domain.removeprefix("www."), []))
    ordered = sorted(
        emails,
        key=lambda e: (
            0 if e in cache_set else 1,
            0 if domain and (e.endswith("@" + domain) or e.split("@")[-1].endswith("." + domain)) else 1,
            0 if e in desc_set else 1,
            0
            if any(t in e.split("@")[0] for t in ("career", "job", "hr", "talent", "hello", "hi", "apply", "team", "join", "recruit"))
            else 1,
        ),
    )
    for email in ordered:
        if email in cache_set:
            return email, "cache-strict"
        ok, detail_s = verify_mailbox(email)
        if ok:
            return email, "strict-valid"
        detail_l = (detail_s or "").lower()
        local = email.split("@")[0]
        hrish = any(
            t in local
            for t in ("career", "job", "hr", "talent", "hello", "hi", "apply", "team", "join", "recruit", "people")
        )
        # Catch-all domains: still deliver to careers/hr/hello on the company domain
        if (
            hrish
            and domain
            and (email.endswith("@" + domain) or email.split("@")[-1].endswith("." + domain))
            and "catch-all" in detail_l
            and "user unknown" not in detail_l
            and "does not exist" not in detail_l
        ):
            return email, "catch-all-hr"
        if email in desc_set and "user unknown" not in detail_l and "does not exist" not in detail_l:
            return email, "published"
    # SMTP-strict common locals only for known domain
    if domain:
        for local in ("careers", "jobs", "hr", "hello", "talent", "join", "team"):
            email = f"{local}@{domain}"
            if not usable(email, sent_e, bounced) or email in invalid_emails:
                continue
            if email in cache_set:
                return email, "cache-strict"
            ok, detail_s = verify_mailbox(email)
            if ok:
                return email, "strict-valid"
            detail_l = (detail_s or "").lower()
            if "catch-all" in detail_l and "user unknown" not in detail_l:
                return email, "catch-all-hr"
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
    last: Exception | None = None
    for attempt in range(3):
        try:
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=90) as smtp:
                smtp.starttls(context=ctx)
                smtp.login(FROM, PASS)
                smtp.sendmail(FROM, [to], msg.as_string())
            log_sent(to, company, "sent", letter=TAG, subject=subject)
            return
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(12 * (attempt + 1))
    raise last or RuntimeError("send failed")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=50)
    ap.add_argument("--daily-cap", type=int, default=100)
    ap.add_argument("--skip-scrape", action="store_true")
    args = ap.parse_args()

    if not agent_enabled():
        raise SystemExit("CURSOR_API_KEY required")
    if not FROM or not PASS or not RESUME_NEXT.exists():
        raise SystemExit("Gmail/resume missing")

    today = datetime.now(timezone.utc).date().isoformat()
    today_n = sum(
        1
        for row in csv.DictReader((ROOT / "outreach" / "sent_log.csv").open(encoding="utf-8-sig"))
        if row.get("status") == "sent" and (row.get("sent_at") or "").startswith(today)
    )
    room = max(0, args.daily_cap - today_n)
    target = min(args.target, room)
    print(f"Today={today_n} room={room} target={target}", flush=True)
    if target <= 0:
        return

    if not args.skip_scrape:
        scrape_all()

    sent_e, sent_c = already_sent()
    bounced = bounced_emails()
    prior = load_prior_emails()
    mb_by_dom = load_mailbox_by_domain()
    co_dom = load_company_domains()
    invalid_emails = load_invalid_emails()
    print(f"Prior verified company emails (non-leads): {len(prior)}", flush=True)
    print(f"Mailbox cache domains (strict/valid): {len(mb_by_dom)}", flush=True)
    print(f"Company→domain map: {len(co_dom)} (Hunter free tier exhausted)", flush=True)
    print(f"theHarvester: {'ready' if harvester_available() else 'MISSING (uv/harvester)'}", flush=True)

    jobs = [j for j in load_jobs() if _norm(j["company"]) not in sent_c]
    # Prefer postings that already expose an email in cached details
    jobs.sort(key=lambda j: (0 if detail_has_email(j) else 1, j.get("company") or ""))
    print(f"Job pool (<3y title filter, geo OK): {len(jobs)}", flush=True)
    print(f"  of which detail-has-email: {sum(1 for j in jobs if detail_has_email(j))}", flush=True)

    LETTERS.mkdir(parents=True, exist_ok=True)
    if not TRACKER.exists():
        TRACKER.write_text(
            "date,company,sector,role,role_type,channel,status,contact_person,fit_rating,notes,cv_file,cover_letter_file,source,deadline\n"
        )

    client = HttpClient()
    hunter = HunterClient()
    # Free Hunter plan is exhausted this period — skip API calls (local domain map only)
    try:
        import httpx

        key = os.getenv("HUNTER_API_KEY", "").strip()
        if key:
            r = httpx.get("https://api.hunter.io/v2/account", params={"api_key": key}, timeout=20.0)
            rem = (
                (((r.json() or {}).get("data") or {}).get("requests") or {})
                .get("credits") or {}
            ).get("remaining")
            if rem is not None and float(rem) <= 0:
                print("Hunter credits remaining=0 — disabling Hunter for this run", flush=True)
                hunter.close()
                hunter = HunterClient(api_key="")  # disabled
    except Exception as exc:  # noqa: BLE001
        print(f"Hunter account check skipped: {exc}", flush=True)
    sent_n = 0
    tried = 0
    sent_rows: list[dict] = []

    try:
        # keep going through pool; if low yield, rescrape once mid-run
        wave = 0
        while sent_n < target and wave < 3:
            wave += 1
            if wave > 1:
                print(f"\n=== Rescrape wave {wave} ===", flush=True)
                scrape_all()
                jobs = [j for j in load_jobs() if _norm(j["company"]) not in sent_c]
                # skip companies already tried this session via sent_e domain matching later
            for job in jobs:
                if sent_n >= target:
                    break
                if tried >= target * 20:
                    break
                tried += 1
                co = job["company"]
                title = job["title"]
                if _norm(co) in sent_c:
                    continue
                print(f"\n[{tried}] {title[:55]} @ {co} | {job['location'][:40]}", flush=True)
                detail = fetch_detail(job)
                if not detail:
                    print("  detail fail", flush=True)
                    continue
                desc = str(detail.get("description") or "")
                if len(desc) < 100:
                    print("  thin posting", flush=True)
                    continue
                if not role_ok_for_junior(title, desc):
                    print("  skip >=3y / senior", flush=True)
                    continue
                hit = resolve_email(
                    detail, sent_e, bounced, client, hunter, prior, mb_by_dom, co_dom, invalid_emails
                )
                if not hit:
                    print("  no verified email", flush=True)
                    continue
                email, tag = hit
                if email in sent_e:
                    continue
                print(f"  email {email} [{tag}]", flush=True)
                resume = resume_for(title)
                safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", co)[:40]
                letter_path = LETTERS / f"{safe}.txt"
                try:
                    if letter_path.exists() and letter_path.stat().st_size > 80:
                        body = letter_path.read_text(encoding="utf-8")
                        print("  reuse letter", flush=True)
                    else:
                        print("  writing tailored letter…", flush=True)
                        skills = detail.get("skills") or []
                        skills_s = ", ".join(skills) if isinstance(skills, list) else str(skills)
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
                print(f"  preview: {' '.join(body.split())[:140]}…", flush=True)
                subj = f"{title[:42]} at {co}"[:58]
                try:
                    send_one(to=email, company=co, subject=subj, body=body, resume=resume)
                    sent_n += 1
                    sent_e.add(email)
                    sent_c.add(_norm(co))
                    sent_rows.append({"Company": co, "Email": email, "Role": title, "Location": job.get("location"), "URL": job.get("url")})
                    print(f"  SENT [{sent_n}/{target}] {email}", flush=True)
                    with TRACKER.open("a", encoding="utf-8", newline="") as f:
                        csv.writer(f).writerow(
                            [
                                date.today().isoformat(),
                                co,
                                "tech",
                                title,
                                "IC",
                                "email",
                                "sent",
                                email,
                                "",
                                f"until50→{email}",
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
                        wave = 99
                        break
                if sent_n < target:
                    wait = max(36.0, DELAY + random.uniform(-6, 14))
                    print(f"  wait {wait:.0f}s…", flush=True)
                    time.sleep(wait)
            if sent_n >= target:
                break
            print(f"Wave {wave} done with {sent_n}/{target} — continuing…", flush=True)
    finally:
        client.close()
        hunter.close()

    if sent_rows:
        with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(sent_rows[0].keys()))
            w.writeheader()
            w.writerows(sent_rows)
        print(f"CSV → {OUT_CSV}", flush=True)
    print(f"\nDONE. Sent {sent_n}/{target}", flush=True)


if __name__ == "__main__":
    main()
