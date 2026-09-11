#!/usr/bin/env python3
"""Qualified Leads → extract company from email domain → find REAL job posting →
short Reddit-style tailored email → send.

Skips big corporations. Only sends when a junior/associate-friendly posting is found
for that company (or a close name match on LinkedIn/Freehire).
"""
from __future__ import annotations

import json
import os
import random
import re
import smtplib
import ssl
import subprocess
import sys
import time
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
AIJS = ROOT / "ai-job-search"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "outreach"))
load_dotenv(ROOT / ".env")

from job_hunter.agent_letter import agent_enabled, write_short_cold_email  # noqa: E402
from job_hunter.experience import role_ok_for_junior  # noqa: E402
from send_emails import already_sent, log_sent  # noqa: E402

QUEUE = ROOT / "output" / "_ql_remote_startups.json"
RESUME = ROOT / "Muhammad_Muddasir_Resume.pdf"
LETTERS = AIJS / "output_scrape" / "letters" / "ql_posting_first"
LI_CLI = AIJS / ".agents/skills/linkedin-search/cli/src/cli.ts"
FH_CLI = AIJS / ".agents/skills/freehire-search/cli/src/cli.ts"
FROM = os.getenv("GMAIL_ADDRESS", "").strip()
PASS = os.getenv("GMAIL_APP_PASSWORD", "").strip()
TAG = "ql_posting_first+reddit"
DELAY = 48.0
TARGET = int(os.getenv("QL_TARGET", "15"))

BIG = re.compile(
    r"\b(google|meta|facebook|amazon|microsoft|apple|netflix|uber|airbnb|linkedin|"
    r"oracle|ibm|salesforce|adobe|intel|nvidia|samsung|deloitte|accenture|cognizant|"
    r"infosys|wipro|\btcs\b|capgemini|spotify|openai|anthropic)\b",
    re.I,
)
STACK = re.compile(
    r"\b(software engineer|full.?stack|frontend|front.?end|react|next\.?js|typescript|"
    r"python|ai engineer|machine learning engineer|ml engineer|data engineer|"
    r"backend engineer|product engineer|platform engineer|web developer|"
    r"software developer|fullstack)\b",
    re.I,
)
JUNK_TITLE = re.compile(
    r"(sourceURL|elementor|webpack|function\s*\(|\{|\}|</|https?://|javascript:|"
    r"cookie|privacy policy|subscribe|newsletter|all rights reserved)",
    re.I,
)
SENIOR = re.compile(
    r"\b(senior|staff|principal|lead |manager|director|l[4-9]\b|iii\b|iv\b|5\+|4\+|3\+ years)\b",
    re.I,
)
PERSONAL = {
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "icloud.com",
    "live.com",
    "me.com",
    "proton.me",
    "protonmail.com",
}


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def company_from_email(email: str, org_hint: str = "", domain_hint: str = "") -> tuple[str, str]:
    """Return (company_display, domain) from email host when it encodes the company."""
    host = email.split("@", 1)[-1].lower().removeprefix("www.")
    if host in PERSONAL:
        return org_hint or "", domain_hint or ""
    domain = domain_hint or host
    # Prefer org hint if domain matches
    if org_hint and domain and (norm(org_hint) in norm(domain) or norm(domain.split(".")[0]) in norm(org_hint)):
        return org_hint, domain
    # Derive brand from domain root
    root = domain.split(".")[0]
    brand = re.sub(r"[-_]+", " ", root).strip().title()
    return (org_hint or brand), domain


def _li_search(query: str, location: str, limit: int = 10) -> list[dict]:
    cmd = [
        "bun",
        "run",
        str(LI_CLI),
        "search",
        "-q",
        query,
        "-l",
        location,
        "--limit",
        str(limit),
        "--jobage",
        "60",
        "--format",
        "json",
    ]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=90, cwd=str(AIJS))
        if p.returncode != 0:
            return []
        data = json.loads(p.stdout)
        return list(data.get("results") or [])
    except Exception:
        return []


def _fh_search(company_slug: str) -> list[dict]:
    cmd = [
        "bun",
        "run",
        str(FH_CLI),
        "search",
        "-q",
        "software engineer",
        "--company",
        company_slug,
        "--jobage",
        "60",
        "--limit",
        "15",
        "--format",
        "json",
    ]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=str(AIJS))
        if p.returncode != 0:
            return []
        data = json.loads(p.stdout)
        return list(data.get("results") or [])
    except Exception:
        return []


def _company_match(result_co: str, target: str, domain: str) -> bool:
    a, b = norm(result_co), norm(target)
    if not a or not b:
        return False
    # Exact / containment only when names are clearly related (avoid care ⊂ alayacare)
    if a == b:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    if len(shorter) >= 5 and shorter in longer and len(shorter) / len(longer) >= 0.55:
        return True
    root = norm(domain.split(".")[0]) if domain else ""
    if root and len(root) >= 5:
        if a == root or b == root:
            return True
        if a.startswith(root) or root.startswith(a):
            return True
    return False


def _ats_search(company: str, domain: str) -> list[dict]:
    """Check common ATS boards for this domain slug (Greenhouse / Lever / Ashby)."""
    try:
        import httpx
    except ImportError:
        return []

    slug = re.sub(r"[^a-z0-9]+", "", (domain.split(".")[0] if domain else "").lower())
    brand = re.sub(r"[^a-z0-9]+", "", norm(company))[:24]
    candidates: list[str] = []
    for s in (slug, brand):
        if s and len(s) >= 3 and s not in candidates:
            candidates.append(s)
    boards: list[tuple[str, str]] = []
    for s in candidates[:2]:
        boards.extend(
            [
                (f"https://job-boards.greenhouse.io/{s}", "greenhouse"),
                (f"https://boards.greenhouse.io/{s}", "greenhouse"),
                (f"https://jobs.lever.co/{s}", "lever"),
                (f"https://jobs.ashbyhq.com/{s}", "ashby"),
            ]
        )
    allowed_hosts = (
        "greenhouse.io",
        "lever.co",
        "ashbyhq.com",
    )
    hits: list[dict] = []
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }

    def _add_title(title: str, url: str, src: str) -> None:
        title = " ".join((title or "").split())
        if not (8 <= len(title) <= 90):
            return
        if JUNK_TITLE.search(title) or not STACK.search(title) or SENIOR.search(title):
            return
        if not role_ok_for_junior(title):
            return
        hits.append(
            {
                "title": title,
                "company": company,
                "location": "Remote",
                "url": url,
                "id": "",
                "source": src,
            }
        )

    with httpx.Client(headers=headers, timeout=15.0, follow_redirects=True) as client:
        for url, src in boards:
            if len(hits) >= 5:
                break
            try:
                resp = client.get(url)
            except Exception:
                continue
            if resp.status_code >= 400:
                continue
            final = str(resp.url)
            if not any(h in final for h in allowed_hosts):
                # Redirected off ATS onto marketing site — ignore
                continue
            html = resp.text or ""
            if len(html) < 400:
                continue
            for m in re.finditer(r'"title"\s*:\s*"([^"\\]{6,120})"', html):
                _add_title(m.group(1).encode().decode("unicode_escape", errors="ignore"), final, src)
            for m in re.finditer(
                r'<a[^>]+href="[^"]*(?:jobs?|opening)[^"]*"[^>]*>([^<]{6,120})</a>',
                html,
                re.I,
            ):
                _add_title(m.group(1), final, src)
    return hits


def find_posting(company: str, domain: str) -> dict | None:
    """Find a junior-friendly SWE/frontend/AI posting for this company."""
    # ATS first — fast + exact company boards (Ashby/Greenhouse/Lever)
    hits: list[dict] = _ats_search(company, domain)

    if not hits:
        queries = [
            f'"{company}" software engineer',
            f'"{company}" frontend engineer',
            f"{company} full stack engineer",
            f"{company} software engineer",
        ]
        locations = ["Remote", "United States", "United Kingdom"]
        for q in queries[:3]:
            for loc in locations[:2]:
                for r in _li_search(q, loc, limit=10):
                    title = (r.get("title") or "").strip()
                    co = (r.get("company") or "").strip()
                    if not title or not STACK.search(title):
                        continue
                    if SENIOR.search(title):
                        continue
                    if not role_ok_for_junior(title):
                        continue
                    if not _company_match(co, company, domain):
                        continue
                    hits.append(
                        {
                            "title": title,
                            "company": co,
                            "location": str(r.get("location") or "Remote"),
                            "url": r.get("url") or "",
                            "id": r.get("id") or "",
                            "source": "linkedin",
                        }
                    )
                if hits:
                    break
            if hits:
                break

    if not hits and domain:
        slug = domain.split(".")[0]
        for r in _fh_search(slug):
            title = (r.get("title") or "").strip()
            co = (r.get("company") or company).strip()
            if not title or not STACK.search(title) or SENIOR.search(title):
                continue
            if not role_ok_for_junior(title):
                continue
            hits.append(
                {
                    "title": title,
                    "company": co,
                    "location": str(r.get("location") or "Remote"),
                    "url": r.get("url") or "",
                    "id": r.get("id") or "",
                    "source": "freehire",
                }
            )

    if not hits:
        return None

    def score(h: dict) -> int:
        t = h["title"].lower()
        s = 0
        if re.search(r"junior|associate|entry|engineer i\b|new grad", t):
            s -= 5
        if "full stack" in t or "fullstack" in t:
            s -= 3
        if "frontend" in t or "react" in t:
            s -= 3
        if "data engineer" in t or "ai" in t:
            s -= 2
        if "remote" in (h.get("location") or "").lower():
            s -= 2
        # Prefer ATS over noisy LinkedIn matches
        if h.get("source") in {"ashby", "greenhouse", "lever"}:
            s -= 4
        return s

    hits.sort(key=score)
    return hits[0]


def fetch_detail(job: dict) -> str:
    jid = job.get("id") or job.get("url") or ""
    if not jid or job.get("source") != "linkedin":
        return ""
    cmd = ["bun", "run", str(LI_CLI), "detail", str(jid), "--format", "json"]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=90, cwd=str(AIJS))
        if p.returncode != 0:
            return ""
        data = json.loads(p.stdout)
        if "result" in data:
            data = data["result"]
        if isinstance(data.get("results"), list) and data["results"]:
            data = data["results"][0]
        return str(data.get("description") or "")[:3500]
    except Exception:
        return ""


def scrape_junior_pool(limit_pages: int = 3) -> list[dict]:
    """Pull a pool of junior-friendly SWE/FE/AI jobs once, then match to QL companies."""
    queries = [
        "junior software engineer",
        "associate software engineer",
        "frontend engineer react",
        "full stack engineer",
        "AI engineer",
        "software engineer I",
    ]
    locations = ["Remote", "United States", "United Kingdom", "Pakistan", "Singapore"]
    pool: list[dict] = []
    seen: set[str] = set()
    for q in queries:
        for loc in locations[:3]:
            for r in _li_search(q, loc, limit=10):
                title = (r.get("title") or "").strip()
                co = (r.get("company") or "").strip()
                key = f"{norm(co)}|{norm(title)}"
                if not title or not co or key in seen:
                    continue
                if not STACK.search(title) or SENIOR.search(title):
                    continue
                if not role_ok_for_junior(title):
                    continue
                if BIG.search(co):
                    continue
                seen.add(key)
                pool.append(
                    {
                        "title": title,
                        "company": co,
                        "location": str(r.get("location") or "Remote"),
                        "url": r.get("url") or "",
                        "id": r.get("id") or "",
                        "source": "linkedin",
                    }
                )
            if len(pool) >= 80:
                break
        if len(pool) >= 80:
            break
    print(f"junior job pool: {len(pool)}", flush=True)
    return pool


def match_pool_job(company: str, domain: str, pool: list[dict]) -> dict | None:
    hits = [j for j in pool if _company_match(j.get("company") or "", company, domain)]
    if not hits:
        return None

    def score(h: dict) -> int:
        t = h["title"].lower()
        s = 0
        if re.search(r"junior|associate|entry|engineer i\b|new grad", t):
            s -= 5
        if "frontend" in t or "react" in t or "full stack" in t:
            s -= 3
        return s

    hits.sort(key=score)
    return hits[0]


def send_one(*, to: str, subject: str, body: str) -> None:
    msg = MIMEMultipart()
    msg["From"] = f"Muhammad Muddasir <{FROM}>"
    msg["To"] = to
    msg["Reply-To"] = FROM
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=FROM.split("@", 1)[-1])
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))
    # Reddit tip: still attach resume but keep email short; portfolio link in body
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


def process_send(
    *,
    lead: dict,
    company: str,
    job: dict,
    sent_e: set[str],
    sent_c: set[str],
    sent_n: int,
) -> bool:
    em = (lead.get("email") or "").lower().strip()
    desc = fetch_detail(job)
    if len(desc) < 80:
        desc = (
            f"Open role: {job['title']} at {job['company']} ({job.get('location')}). "
            f"URL: {job.get('url')}. Contact {lead.get('name')} ({lead.get('title')}). "
            f"Company headline: {lead.get('headline') or ''}"
        )
    else:
        desc = f"{job['title']} at {job['company']} ({job.get('location')})\nURL: {job.get('url')}\n\n{desc}"

    safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", company)[:40]
    letter_path = LETTERS / f"{safe}.txt"
    print("  writing SHORT reddit-style letter…", flush=True)
    body = write_short_cold_email(
        company=company,
        role=job["title"],
        contact_name=lead.get("name") or "",
        location=job.get("location") or "Remote",
        summary=desc,
        apply_url=job.get("url") or "",
    )
    letter_path.write_text(body, encoding="utf-8")
    words = len(body.split())
    print(f"  words≈{words} preview: {' '.join(body.split())[:140]}…", flush=True)
    subj = f"{job['title'].split('(')[0].strip()[:40]} @ {company}"[:58]
    send_one(to=em, subject=subj, body=body)
    sent_e.add(em)
    sent_c.add(norm(company))
    sent_c.add(company.lower())
    log_sent(em, company, "sent", f"job:{job['title'][:40]}", letter=TAG, subject=subj)
    print(f"  SENT [{sent_n + 1}/{TARGET}] {em}", flush=True)
    return True


def main() -> None:
    if not agent_enabled() or not FROM or not PASS or not RESUME.exists():
        raise SystemExit("missing gmail/cursor/resume")
    if not QUEUE.exists():
        raise SystemExit(f"missing {QUEUE}")

    sent_e, sent_c_raw = already_sent()
    sent_c = {norm(c) for c in sent_c_raw} | {c.lower() for c in sent_c_raw}
    leads = json.loads(QUEUE.read_text())
    print(f"leads in queue file: {len(leads)}", flush=True)

    LETTERS.mkdir(parents=True, exist_ok=True)
    sent_n = 0

    # Pass A: ATS boards only (fast, high-signal)
    print("\n=== Pass A: ATS boards (Ashby/Greenhouse/Lever) ===", flush=True)
    for lead in leads:
        if sent_n >= TARGET:
            break
        em = (lead.get("email") or "").lower().strip()
        if not em or em in sent_e or "@" not in em:
            continue
        host = em.split("@", 1)[1]
        if host in PERSONAL or BIG.search(host):
            continue
        company, domain = company_from_email(em, lead.get("org") or "", lead.get("domain") or "")
        if not company or BIG.search(company):
            continue
        if norm(company) in sent_c or company.lower() in sent_c:
            continue
        print(f"\n[A] {company} <{em}>", flush=True)
        job = None
        ats = _ats_search(company, domain)
        if ats:
            job = ats[0]
            print(f"  FOUND {job['title'][:55]} [{job['source']}]", flush=True)
        else:
            print("  no ATS board — defer", flush=True)
            continue
        try:
            process_send(lead=lead, company=company, job=job, sent_e=sent_e, sent_c=sent_c, sent_n=sent_n)
            sent_n += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  FAIL {exc}", flush=True)
            log_sent(em, company, "failed", str(exc)[:200], letter=TAG)
            continue
        if sent_n < TARGET:
            wait = DELAY + random.uniform(-6, 10)
            print(f"  wait {wait:.0f}s…", flush=True)
            time.sleep(wait)

    if sent_n >= TARGET:
        print(f"\nDONE. Sent {sent_n}/{TARGET} (ATS pass)", flush=True)
        return

    # Pass B: scrape junior openings once, match to QL companies (Reddit: posting first)
    print("\n=== Pass B: LinkedIn junior pool → match QL companies ===", flush=True)
    pool = scrape_junior_pool()
    ql_by_co: dict[str, dict] = {}
    for lead in leads:
        co = lead.get("org") or ""
        if co:
            ql_by_co.setdefault(norm(co), lead)
            # also index by domain root
            dom = (lead.get("domain") or "").split(".")[0]
            if dom and len(dom) >= 4:
                ql_by_co.setdefault(norm(dom), lead)

    for lead in leads:
        if sent_n >= TARGET:
            break
        em = (lead.get("email") or "").lower().strip()
        if not em or em in sent_e or "@" not in em:
            continue
        host = em.split("@", 1)[1]
        if host in PERSONAL or BIG.search(host):
            continue
        company, domain = company_from_email(em, lead.get("org") or "", lead.get("domain") or "")
        if not company or BIG.search(company):
            continue
        if norm(company) in sent_c or company.lower() in sent_c:
            continue
        job = match_pool_job(company, domain, pool)
        if not job:
            continue
        print(f"\n[B] MATCH {job['title'][:50]} @ {job['company']} → {em}", flush=True)
        try:
            process_send(lead=lead, company=company, job=job, sent_e=sent_e, sent_c=sent_c, sent_n=sent_n)
            sent_n += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  FAIL {exc}", flush=True)
            log_sent(em, company, "failed", str(exc)[:200], letter=TAG)
            continue
        if sent_n < TARGET:
            wait = DELAY + random.uniform(-6, 10)
            print(f"  wait {wait:.0f}s…", flush=True)
            time.sleep(wait)

    # Pass D: job-first — real junior posting → resolve email (mailbox/QL/careers@)
    # This is the Reddit high-signal path when QL companies aren't hiring publicly.
    if sent_n < TARGET:
        print("\n=== Pass D: junior postings → resolve company email ===", flush=True)
        import csv as _csv

        mb_by_dom: dict[str, list[str]] = {}
        mb_path = ROOT / "outreach" / "mailbox_cache.csv"
        if mb_path.exists():
            for r in _csv.DictReader(mb_path.open(encoding="utf-8-sig")):
                if (r.get("status") or "") not in ("strict-valid", "valid", "catch-all"):
                    continue
                emx = (r.get("email") or "").strip().lower()
                if "@" not in emx:
                    continue
                d = emx.split("@", 1)[1]
                mb_by_dom.setdefault(d, [])
                if emx not in mb_by_dom[d]:
                    mb_by_dom[d].append(emx)

        co_dom: dict[str, str] = {}
        for lead in leads:
            org = lead.get("org") or ""
            dom = (lead.get("domain") or "").lower().removeprefix("www.")
            if org and dom and "." in dom:
                co_dom.setdefault(norm(org), dom)
        sent_path = ROOT / "outreach" / "sent_log.csv"
        if sent_path.exists():
            for r in _csv.DictReader(sent_path.open(encoding="utf-8-sig")):
                co = (r.get("company") or "").strip()
                emx = (r.get("email") or "").strip().lower()
                if co and "@" in emx:
                    co_dom.setdefault(norm(co), emx.split("@", 1)[1])

        prefer_local = ("careers", "jobs", "talent", "recruiting", "hr", "hello", "team")
        used_jobs: set[str] = set()
        for job in pool:
            if sent_n >= TARGET:
                break
            co = job.get("company") or ""
            if not co or BIG.search(co):
                continue
            if norm(co) in sent_c or co.lower() in sent_c:
                continue
            jkey = f"{norm(co)}|{norm(job.get('title') or '')}"
            if jkey in used_jobs:
                continue
            # Resolve domain
            domain = co_dom.get(norm(co), "")
            if not domain:
                for pk, d in co_dom.items():
                    if len(pk) >= 5 and (pk in norm(co) or norm(co) in pk):
                        domain = d
                        break
            # Prefer QL contact if company matches
            lead = ql_by_co.get(norm(co))
            em = ""
            if lead:
                em = (lead.get("email") or "").lower().strip()
                if not domain:
                    domain = (lead.get("domain") or "").lower()
            if (not em or em in sent_e) and domain:
                cands = mb_by_dom.get(domain, [])
                # Prefer recruiting locals
                ranked = sorted(
                    cands,
                    key=lambda e: (
                        0 if e.split("@", 1)[0] in prefer_local else 1,
                        len(e),
                    ),
                )
                for c in ranked:
                    if c not in sent_e:
                        em = c
                        break
                if not em:
                    # try careers@ catch-all style
                    for loc in prefer_local:
                        guess = f"{loc}@{domain}"
                        if guess not in sent_e:
                            em = guess
                            break
            if not em or em in sent_e or "@" not in em:
                continue
            host = em.split("@", 1)[1]
            if host in PERSONAL:
                continue
            used_jobs.add(jkey)
            fake_lead = lead or {
                "name": "",
                "email": em,
                "title": "Hiring",
                "headline": f"{co} — {job.get('title')}",
            }
            print(f"\n[D] {job['title'][:50]} @ {co} → {em}", flush=True)
            try:
                process_send(
                    lead=fake_lead,
                    company=co,
                    job=job,
                    sent_e=sent_e,
                    sent_c=sent_c,
                    sent_n=sent_n,
                )
                sent_n += 1
            except Exception as exc:  # noqa: BLE001
                print(f"  FAIL {exc}", flush=True)
                log_sent(em, co, "failed", str(exc)[:200], letter=TAG)
                continue
            if sent_n < TARGET:
                wait = DELAY + random.uniform(-6, 10)
                print(f"  wait {wait:.0f}s…", flush=True)
                time.sleep(wait)

    print(f"\nDONE. Sent {sent_n}/{TARGET} (posting-backed Reddit strategy)", flush=True)


if __name__ == "__main__":
    main()
