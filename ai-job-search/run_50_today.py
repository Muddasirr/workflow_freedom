#!/usr/bin/env python3
"""Hit 50 sends today: real job posting → short Reddit email → known inbox.

Pass 1: scraped / LinkedIn junior jobs matched to mailbox/directory emails
Pass 2: fill remaining from geo careers queue (short letters, company-specific)
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
from datetime import date
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
from job_hunter.directory import COMPANY_DIRECTORY  # noqa: E402
from job_hunter.experience import role_ok_for_junior  # noqa: E402
from send_emails import BLOCKED_DOMAINS, already_sent, log_sent  # noqa: E402

RESUME = ROOT / "Muhammad_Muddasir_Resume.pdf"
RESUME_GO = ROOT / "go" / "MuddasirRizwan_Resume.pdf"
FROM = os.getenv("GMAIL_ADDRESS", "").strip()
PASS = os.getenv("GMAIL_APP_PASSWORD", "").strip()
TAG = "today50+reddit"
DELAY = float(os.getenv("SEND_DELAY", "36"))
TARGET = int(os.getenv("TODAY_TARGET", "50"))
OUT = ROOT / "output" / f"emails_today50_{date.today().isoformat()}.csv"
LETTERS = AIJS / "output_scrape" / "until50" / "letters" / "today50"
LI_CLI = AIJS / ".agents/skills/linkedin-search/cli/src/cli.ts"
READY = ROOT / "output" / "_blast_ready_geo.json"

STACK = re.compile(
    r"\b(react|next\.?js|frontend|front.?end|full.?stack|typescript|python|"
    r"ai engineer|software engineer|backend|golang|go developer|product engineer|"
    r"data engineer|web developer|software developer)\b",
    re.I,
)
GO = re.compile(r"\b(golang|go developer|go engineer)\b", re.I)
BAD = re.compile(r"\b(intern\b|trainee|sqa|qa engineer|sales|php developer)\b", re.I)
SENIOR = re.compile(
    r"\b(senior|staff|principal|lead |manager|director|l[4-9]\b|iii\b|iv\b|5\+|4\+)\b",
    re.I,
)
PREFER = re.compile(
    r"confiz|netsol|empiric|tintash|tkxel|securiti|swvl|talabat|anghami|bosta|salla|"
    r"foodpanda|sadapay|emumba|folio|10pearls|thoughtworks|turing|motive|careem|"
    r"dubizzle|checkout|tabby|tamara|geidea|nearpay|paymob|namshi|synapse|nymcard|"
    r"elixir|zigron|stormfiber|alokai|cartlow|bayzat|instashop|keenu|abhi|dawaai|"
    r"venture|folio3|systems limited|arbisoft|devsinc|contour|purelogics",
    re.I,
)


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def load_scraped_jobs() -> list[dict]:
    jobs: list[dict] = []
    for base in (AIJS / "output_scrape" / "until50", AIJS / "output_scrape" / "batch50"):
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
                if BAD.search(title) or SENIOR.search(title) or not STACK.search(title):
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
                        "location": str(loc) or "Remote",
                        "url": (r.get("url") or "").strip(),
                        "source": "scrape",
                    }
                )
    return jobs


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
        "45",
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


def scrape_fresh_jobs() -> list[dict]:
    queries = [
        "junior software engineer",
        "associate software engineer",
        "frontend engineer react",
        "full stack engineer",
        "software engineer I",
        "AI engineer",
        "product engineer",
    ]
    locations = ["Remote", "Pakistan", "United Arab Emirates", "Singapore", "United Kingdom"]
    out: list[dict] = []
    seen: set[str] = set()
    for q in queries:
        for loc in locations[:3]:
            for r in _li_search(q, loc, limit=10):
                title = (r.get("title") or "").strip()
                company = (r.get("company") or "").strip()
                key = f"{norm(company)}|{norm(title)}"
                if not title or not company or key in seen:
                    continue
                if BAD.search(title) or SENIOR.search(title) or not STACK.search(title):
                    continue
                if not role_ok_for_junior(title):
                    continue
                seen.add(key)
                out.append(
                    {
                        "company": company,
                        "title": title,
                        "location": str(r.get("location") or loc),
                        "url": r.get("url") or "",
                        "source": "linkedin",
                    }
                )
            if len(out) >= 120:
                return out
    return out


def load_email_maps() -> tuple[dict[str, str], dict[str, list[str]], dict[str, str], set[str], set[str]]:
    co_em: dict[str, str] = {}
    dom_em: dict[str, list[str]] = {}
    co_dom: dict[str, str] = {}
    strict: set[str] = set()
    catchall: set[str] = set()

    for name, domain, _city, _loc, emails in COMPANY_DIRECTORY:
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


def resolve_email(
    company: str,
    co_em: dict[str, str],
    dom_em: dict[str, list[str]],
    co_dom: dict[str, str],
    sent_e: set[str],
    strict: set[str],
    catchall: set[str],
) -> tuple[str, str] | None:
    """ONLY return SMTP-verified mailboxes (strict-valid / valid). Never catch-all or guesses."""
    del catchall  # intentionally unused — do not send to catch-all
    kn = norm(company)
    cands: list[str] = []
    if kn in co_em:
        cands.append(co_em[kn])
    for pk, em in co_em.items():
        if len(pk) < 6 or len(kn) < 6:
            continue
        shorter, longer = (pk, kn) if len(pk) <= len(kn) else (kn, pk)
        if shorter in longer and len(shorter) / len(longer) >= 0.72:
            cands.append(em)
    domain = co_dom.get(kn, "")
    if not domain:
        for pk, dom in co_dom.items():
            if len(pk) < 6 or len(kn) < 6:
                continue
            shorter, longer = (pk, kn) if len(pk) <= len(kn) else (kn, pk)
            if shorter in longer and len(shorter) / len(longer) >= 0.72:
                domain = dom
                break
    if domain:
        cands.extend(dom_em.get(domain, []))

    ordered = list(dict.fromkeys(e.lower() for e in cands if e and "@" in e))
    for em in ordered:
        if em in sent_e or em.split("@", 1)[1] in BLOCKED_DOMAINS:
            continue
        if em in strict:
            return em, "cache-strict"
    return None


def load_strict_emails() -> set[str]:
    """Emails with real SMTP mailbox proof (not catch-all)."""
    out: set[str] = set()
    mb = ROOT / "outreach" / "mailbox_cache.csv"
    if not mb.exists():
        return out
    for r in csv.DictReader(mb.open(encoding="utf-8-sig")):
        if (r.get("status") or "") not in ("strict-valid", "valid"):
            continue
        em = (r.get("email") or "").lower().strip()
        if "@" in em:
            out.add(em)
    return out


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


def build_queue(
    jobs: list[dict],
    sent_e: set[str],
    sent_c: set[str],
    co_em: dict[str, str],
    dom_em: dict[str, list[str]],
    co_dom: dict[str, str],
    strict: set[str],
    catchall: set[str],
) -> list[dict]:
    queue: list[dict] = []
    seen_co: set[str] = set()
    # Prefer remote / junior titles first
    def score(j: dict) -> int:
        t = j["title"].lower()
        s = 0
        if re.search(r"junior|associate|entry|engineer i\b|new grad", t):
            s -= 8
        if "frontend" in t or "react" in t or "full stack" in t:
            s -= 4
        if "remote" in (j.get("location") or "").lower():
            s -= 3
        if j.get("source") == "linkedin":
            s -= 1
        return s

    for j in sorted(jobs, key=score):
        kn = norm(j["company"])
        if not kn or kn in sent_c or j["company"].strip().lower() in sent_c or kn in seen_co:
            continue
        hit = resolve_email(j["company"], co_em, dom_em, co_dom, sent_e, strict, catchall)
        if not hit:
            continue
        email, tag = hit
        if email in sent_e:
            continue
        seen_co.add(kn)
        queue.append({**j, "email": email, "tag": tag})
        print(f"  + {j['company'][:32]:32} | {j['title'][:38]:38} → {email} [{tag}]", flush=True)
        if len(queue) >= TARGET * 2:
            break
    return queue


def careers_fill(
    sent_e: set[str],
    sent_c: set[str],
    already_emails: set[str],
    strict: set[str],
) -> list[dict]:
    """Only queue careers contacts that are already SMTP-verified (strict/valid)."""
    out: list[dict] = []
    seen_em: set[str] = set(already_emails)
    need = TARGET * 2 + 15

    def add(co: str, em: str, domain: str, tag: str, loc: str = "") -> None:
        em = (em or "").lower().strip()
        co = (co or "").strip()
        if not co or not em or "@" not in em:
            return
        if em not in strict:
            return  # HARD RULE: no catch-all, no unverified
        if em in sent_e or em in seen_em:
            return
        if norm(co) in sent_c or co.lower() in sent_c:
            return
        host = em.split("@", 1)[1]
        if host in BLOCKED_DOMAINS:
            return
        seen_em.add(em)
        domain = domain or host
        out.append(
            {
                "company": co,
                "title": "Software Engineer (Full Stack / Frontend / AI)",
                "location": loc or "Remote / MENA / PK",
                "url": f"https://{domain}/careers",
                "email": em,
                "tag": tag,
                "source": "careers",
            }
        )

    if READY.exists():
        ready = json.loads(READY.read_text())
        prefer = [r for r in ready if PREFER.search(r.get("company") or "")]
        rest = [r for r in ready if r not in prefer]
        for r in prefer + rest:
            add(
                r.get("company") or "",
                r.get("email") or "",
                r.get("domain") or "",
                f"strict-{r.get('tag') or 'geo'}",
                r.get("location") or "",
            )
            if len(out) >= need:
                return out

    for name, domain, _city, loc, emails in COMPANY_DIRECTORY:
        if len(out) >= need:
            break
        for em in emails:
            em = em.lower()
            local = em.split("@", 1)[0] if "@" in em else ""
            if local not in {"careers", "jobs", "hr", "talent", "recruiting", "hello", "people"}:
                continue
            add(name, em, domain, "directory-strict", str(loc or ""))
            break

    ql_path = ROOT / "output" / "_ql_remote_startups.json"
    if ql_path.exists() and len(out) < need:
        for lead in json.loads(ql_path.read_text()):
            if len(out) >= need:
                break
            add(
                lead.get("org") or "",
                lead.get("email") or "",
                lead.get("domain") or "",
                "ql-strict",
                "Remote" if lead.get("remote_flag") else "",
            )

    # Also pull unused strict recruiting inboxes from mailbox cache directly
    if len(out) < need:
        for em in sorted(strict):
            if len(out) >= need:
                break
            local, _, host = em.partition("@")
            if not any(t in local for t in ("career", "hr", "job", "talent", "recruit", "hello", "people", "join")):
                continue
            brand = host.split(".")[0].replace("-", " ").title()
            add(brand, em, host, "mailbox-strict", "Remote")

    return out


def main() -> None:
    if not agent_enabled() or not FROM or not PASS or not RESUME.exists():
        raise SystemExit("missing gmail/cursor/resume")

    sent_e, sent_c_raw = already_sent()
    sent_c = {norm(c) for c in sent_c_raw} | {c.strip().lower() for c in sent_c_raw}
    print(f"GOAL={TARGET} already_sent_emails={len(sent_e)} companies={len(sent_c)}", flush=True)

    print("loading scraped jobs…", flush=True)
    jobs = load_scraped_jobs()
    print(f"  scraped={len(jobs)}", flush=True)
    fresh: list[dict] = []
    if os.getenv("SKIP_LI", "0") != "1":
        print("fresh LinkedIn junior scrape…", flush=True)
        fresh = scrape_fresh_jobs()
        print(f"  linkedin={len(fresh)}", flush=True)
    else:
        print("SKIP_LI=1 — using scraped jobs only", flush=True)
    # merge, prefer fresh
    seen = set()
    merged: list[dict] = []
    for j in fresh + jobs:
        k = norm(j["company"]) + "|" + norm(j["title"])
        if k in seen:
            continue
        seen.add(k)
        merged.append(j)

    co_em, dom_em, co_dom, strict, catchall = load_email_maps()
    print(f"email maps: co={len(co_em)} strict={len(strict)} catchall={len(catchall)}", flush=True)

    print("\n=== Pass 1: job → inbox match ===", flush=True)
    queue = build_queue(merged, sent_e, sent_c, co_em, dom_em, co_dom, strict, catchall)
    print(f"pass1 queue={len(queue)}", flush=True)

    if len(queue) < TARGET:
        print("\n=== Pass 2: STRICT-verified careers fill only ===", flush=True)
        fill = careers_fill(sent_e, sent_c, {q["email"] for q in queue}, strict)
        # avoid dup companies
        have = {norm(q["company"]) for q in queue}
        for f in fill:
            if norm(f["company"]) in have:
                continue
            queue.append(f)
            have.add(norm(f["company"]))
            print(f"  + {f['company'][:32]:32} → {f['email']} [{f['tag']}]", flush=True)
            if len(queue) >= TARGET + 10:
                break
        print(f"total queue={len(queue)} (strict only)", flush=True)

    LETTERS.mkdir(parents=True, exist_ok=True)
    sent_rows: list[dict] = []
    sent_n = 0
    for q in queue:
        if sent_n >= TARGET:
            break
        if q["email"] in sent_e or norm(q["company"]) in sent_c or q["company"].strip().lower() in sent_c:
            continue
        # HARD GATE: never send to unverified / catch-all / guessed
        if q["email"] not in strict:
            print(f"\nSKIP unverified {q['email']} @ {q['company']}", flush=True)
            continue
        print(f"\n[{sent_n + 1}/{TARGET}] {q['title'][:50]} @ {q['company']}", flush=True)
        print(f"  → {q['email']} [{q['tag']}] (STRICT)", flush=True)
        safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", q["company"])[:40]
        letter_path = LETTERS / f"{safe}.txt"
        try:
            if letter_path.exists() and letter_path.stat().st_size > 60:
                body = letter_path.read_text(encoding="utf-8")
                print("  reuse letter", flush=True)
            else:
                print("  writing SHORT letter…", flush=True)
                body = write_short_cold_email(
                    company=q["company"],
                    role=q["title"],
                    contact_name="",
                    location=q.get("location") or "Remote",
                    summary=(
                        f"Open role: {q['title']} at {q['company']} ({q.get('location')}). "
                        f"URL: {q.get('url')}. Stack fit: React/Next.js/TypeScript/Python/AI."
                    ),
                    apply_url=q.get("url") or "",
                )
                letter_path.write_text(body, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            print(f"  letter fail: {exc}", flush=True)
            continue
        words = len(body.split())
        print(f"  words≈{words} | {' '.join(body.split())[:120]}…", flush=True)
        resume = RESUME_GO if GO.search(q["title"]) and RESUME_GO.exists() else RESUME
        subj = f"{q['title'].split('(')[0].strip()[:40]} @ {q['company']}"[:58]
        try:
            send_one(to=q["email"], subject=subj, body=body, resume=resume)
            sent_n += 1
            sent_e.add(q["email"])
            sent_c.add(norm(q["company"]))
            sent_c.add(q["company"].strip().lower())
            log_sent(q["email"], q["company"], "sent", f"job:{q['title'][:40]}", letter=TAG, subject=subj)
            sent_rows.append(
                {
                    "Company": q["company"],
                    "Email": q["email"],
                    "Role": q["title"],
                    "Location": q.get("location") or "",
                    "URL": q.get("url") or "",
                    "Tag": q.get("tag") or "",
                }
            )
            print(f"  SENT [{sent_n}/{TARGET}]", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"  SEND FAIL {exc}", flush=True)
            log_sent(q["email"], q["company"], "failed", str(exc)[:200], letter=TAG, subject=subj)
            continue
        if sent_n < TARGET:
            wait = DELAY + random.uniform(-4, 8)
            print(f"  wait {wait:.0f}s…", flush=True)
            time.sleep(wait)

    if sent_rows:
        with OUT.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(sent_rows[0].keys()))
            w.writeheader()
            w.writerows(sent_rows)
        print(f"CSV → {OUT}", flush=True)
    print(f"\nDONE. Sent {sent_n}/{TARGET} today", flush=True)


if __name__ == "__main__":
    main()
