#!/usr/bin/env python3
"""Apply to findings jobs: posting-backed short email → STRICT-verified inbox only."""
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
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "outreach"))
load_dotenv(ROOT / ".env")

from job_hunter.agent_letter import agent_enabled, write_short_cold_email  # noqa: E402
from job_hunter.directory import COMPANY_DIRECTORY  # noqa: E402
from send_emails import BLOCKED_DOMAINS, already_sent, log_sent  # noqa: E402
from smtp_verify import verify_mailbox  # noqa: E402

FINDINGS = ROOT / "output" / f"job_findings_{date.today().isoformat()}.json"
if not FINDINGS.exists():
    FINDINGS = ROOT / "output" / "job_findings_2026-09-09.json"
RESUME = ROOT / "Muhammad_Muddasir_Resume.pdf"
LETTERS = ROOT / "ai-job-search" / "output_scrape" / "until50" / "letters" / "findings_apply"
FROM = os.getenv("GMAIL_ADDRESS", "").strip()
PASS = os.getenv("GMAIL_APP_PASSWORD", "").strip()
TAG = "findings_apply+strict+reddit"
TARGET = int(os.getenv("FINDINGS_TARGET", "20"))
DELAY = float(os.getenv("SEND_DELAY", "35"))
OUT = ROOT / "output" / f"emails_findings_{date.today().isoformat()}.csv"

# Skip pure staffing / noise companies
SKIP_CO = re.compile(
    r"\b(kforce|huron|hr pod|staffing|recruiting agency|consulting services llc|"
    r"technology staffing|b[cC]forward|vaco|teksystems|robert half)\b",
    re.I,
)

LOCALS = ("careers", "jobs", "talent", "recruiting", "hr", "hello", "people", "join")


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def load_strict() -> set[str]:
    out: set[str] = set()
    path = ROOT / "outreach" / "mailbox_cache.csv"
    if not path.exists():
        return out
    for r in csv.DictReader(path.open(encoding="utf-8-sig")):
        if (r.get("status") or "") != "strict-valid":
            continue
        em = (r.get("email") or "").lower().strip()
        if "@" in em:
            out.add(em)
    return out


def load_co_dom() -> dict[str, str]:
    mapping: dict[str, str] = {}

    def add(co: str, domain: str) -> None:
        domain = (domain or "").strip().lower().removeprefix("www.")
        if not co or not domain or "." not in domain:
            return
        if domain in BLOCKED_DOMAINS:
            return
        mapping.setdefault(norm(co), domain)

    for name, domain, *_rest in COMPANY_DIRECTORY:
        add(name, domain)
    for path in (ROOT / "output").glob("emails_*.csv"):
        try:
            for r in csv.DictReader(path.open(encoding="utf-8-sig")):
                co = (r.get("Company") or "").strip()
                em = (r.get("HR / Recruiter Email") or r.get("Email") or "").strip().lower()
                if co and "@" in em:
                    add(co, em.split("@", 1)[1])
        except Exception:
            continue
    sent = ROOT / "outreach" / "sent_log.csv"
    if sent.exists():
        for r in csv.DictReader(sent.open(encoding="utf-8-sig")):
            co = (r.get("company") or "").strip()
            em = (r.get("email") or "").strip().lower()
            if co and "@" in em:
                add(co, em.split("@", 1)[1])
    return mapping


def guess_domains(company: str, url: str = "") -> list[str]:
    domains: list[str] = []
    # From apply URL host when it's a company site
    if url:
        host = urlparse(url).netloc.lower().removeprefix("www.")
        junk = (
            "linkedin.com",
            "dice.com",
            "wellfound.com",
            "weworkremotely.com",
            "remoteok.com",
            "remotive.com",
            "jobicy.com",
            "arbeitnow",
            "whatjobs.com",
            "freehire",
            "careers-page.com",
            "t.me",
        )
        if host and not any(j in host for j in junk):
            # careers.x.com → x.com
            parts = host.split(".")
            if parts[0] in {"careers", "jobs", "job", "apply", "boards"} and len(parts) >= 3:
                host = ".".join(parts[1:])
            domains.append(host)
    # Wellfound slug style in URL
    m = re.search(r"wellfound\.com/jobs/([a-z0-9\-]+)-\d+", url or "")
    if m:
        slug = m.group(1)
        # strip trailing role words sometimes baked in — keep first segments
        domains.append(f"{slug.split('-')[0]}.com")
    # Company name → common TLDs
    base = re.sub(r"[^a-z0-9]+", "", company.lower())
    base = re.sub(
        r"(inc|llc|ltd|limited|corp|corporation|technologies|technology|software|"
        r"group|holdings|company|co|pk|pvt|private)$",
        "",
        base,
    )
    if len(base) >= 3:
        for tld in (".com", ".io", ".ai", ".co", ".com.pk", ".pk", ".dev"):
            domains.append(base + tld)
    # spaced brand
    words = re.findall(r"[a-z0-9]+", company.lower())
    if len(words) >= 2:
        joined = "".join(words[:2])
        if len(joined) >= 4:
            domains.append(joined + ".com")
    # dedupe
    out: list[str] = []
    for d in domains:
        d = d.lower().removeprefix("www.")
        if d and d not in out and "." in d:
            out.append(d)
    return out[:8]


def resolve_strict_email(
    company: str,
    url: str,
    sent_e: set[str],
    strict: set[str],
    co_dom: dict[str, str],
) -> tuple[str, str] | None:
    kn = norm(company)
    domains: list[str] = []
    if kn in co_dom:
        domains.append(co_dom[kn])
    for pk, dom in co_dom.items():
        if len(pk) < 6 or len(kn) < 6:
            continue
        shorter, longer = (pk, kn) if len(pk) <= len(kn) else (kn, pk)
        if shorter in longer and len(shorter) / len(longer) >= 0.72:
            domains.append(dom)
    domains.extend(guess_domains(company, url))
    # unique
    seen: set[str] = set()
    doms = []
    for d in domains:
        if d not in seen and d not in BLOCKED_DOMAINS:
            seen.add(d)
            doms.append(d)

    # 1) cache strict only
    for d in doms:
        for loc in LOCALS:
            em = f"{loc}@{d}"
            if em in sent_e:
                continue
            if em in strict:
                return em, "cache-strict"

    # 2) live SMTP strict verify (slow but required)
    for d in doms[:4]:
        for loc in LOCALS[:5]:
            em = f"{loc}@{d}"
            if em in sent_e:
                continue
            print(f"    verifying {em}…", flush=True)
            ok, detail = verify_mailbox(em, use_cache=True)
            if ok:
                strict.add(em)
                return em, "live-strict"
            print(f"      no ({detail[:60]})", flush=True)
    return None


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
            time.sleep(10 * (attempt + 1))
    raise last or RuntimeError("send failed")


def main() -> None:
    if not agent_enabled() or not FROM or not PASS or not RESUME.exists():
        raise SystemExit("missing gmail/cursor/resume")
    if not FINDINGS.exists():
        raise SystemExit(f"missing {FINDINGS}")

    payload = json.loads(FINDINGS.read_text())
    jobs = list(payload.get("jobs") or [])
    sent_e, sent_c_raw = already_sent()
    sent_c = {norm(c) for c in sent_c_raw} | {c.strip().lower() for c in sent_c_raw}
    strict = load_strict()
    co_dom = load_co_dom()
    print(
        f"jobs={len(jobs)} target={TARGET} strict_cache={len(strict)} "
        f"(STRICT ONLY — no catch-all)",
        flush=True,
    )

    # Prefer high score, PK/remote, non-staffing
    jobs = sorted(jobs, key=lambda j: -int(j.get("score") or 0))
    LETTERS.mkdir(parents=True, exist_ok=True)
    sent_n = 0
    sent_rows: list[dict] = []
    tried = 0

    for j in jobs:
        if sent_n >= TARGET:
            break
        if tried >= TARGET * 8:
            break
        company = (j.get("company") or "").strip()
        title = (j.get("title") or "").strip()
        # clean unicode escapes in dice titles
        title = title.replace("\\u0026", "&")
        if not company or not title:
            continue
        if SKIP_CO.search(company):
            continue
        kn = norm(company)
        if kn in sent_c or company.lower() in sent_c:
            continue
        tried += 1
        print(f"\n[{tried}] {title[:50]} @ {company} [{j.get('source')}]", flush=True)
        hit = resolve_strict_email(company, j.get("url") or "", sent_e, strict, co_dom)
        if not hit:
            print("  no STRICT email — skip", flush=True)
            continue
        email, tag = hit
        # final gate
        ok, detail = verify_mailbox(email, use_cache=True)
        if not ok:
            print(f"  gate fail {email}: {detail[:80]}", flush=True)
            continue
        print(f"  STRICT → {email} [{tag}]", flush=True)

        safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", company)[:40]
        letter_path = LETTERS / f"{safe}.txt"
        try:
            if letter_path.exists() and letter_path.stat().st_size > 60:
                body = letter_path.read_text(encoding="utf-8")
                print("  reuse letter", flush=True)
            else:
                print("  writing SHORT letter…", flush=True)
                body = write_short_cold_email(
                    company=company,
                    role=title,
                    contact_name="",
                    location=j.get("location") or "Remote",
                    summary=(
                        f"Real posting: {title} at {company} ({j.get('location')}). "
                        f"URL: {j.get('url')}. Source: {j.get('source')}. "
                        f"Candidate: Karachi-based, React/Next.js/TypeScript/Python/AI at Codet.ai."
                    ),
                    apply_url=j.get("url") or "",
                )
                letter_path.write_text(body, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            print(f"  letter fail: {exc}", flush=True)
            continue
        print(f"  words≈{len(body.split())} | {' '.join(body.split())[:110]}…", flush=True)
        subj = f"{title.split('(')[0].strip()[:40]} @ {company}"[:58]
        try:
            send_one(to=email, subject=subj, body=body)
            sent_n += 1
            sent_e.add(email)
            sent_c.add(kn)
            sent_c.add(company.lower())
            log_sent(email, company, "sent", f"job:{title[:40]}", letter=TAG, subject=subj)
            sent_rows.append(
                {
                    "Company": company,
                    "Email": email,
                    "Role": title,
                    "Location": j.get("location") or "",
                    "URL": j.get("url") or "",
                    "Source": j.get("source") or "",
                    "Verify": tag,
                }
            )
            print(f"  SENT [{sent_n}/{TARGET}]", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"  SEND FAIL {exc}", flush=True)
            log_sent(email, company, "failed", str(exc)[:200], letter=TAG, subject=subj)
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
    print(f"\nDONE. Sent {sent_n}/{TARGET} (STRICT verified only)", flush=True)


if __name__ == "__main__":
    main()
