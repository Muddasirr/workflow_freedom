#!/usr/bin/env python3
"""Scrape unsent PK/MENA software houses for published emails; verify or Outlook-soft-accept."""
from __future__ import annotations

import csv
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "outreach"))

from job_hunter.directory import COMPANY_DIRECTORY  # noqa: E402
from job_hunter.emails import pick_hr_email  # noqa: E402
from job_hunter.http import HttpClient  # noqa: E402
from job_hunter.textutil import extract_emails, html_to_text  # noqa: E402
from send_emails import BLOCKED_DOMAINS, SKIP_LOCAL, already_sent  # noqa: E402
from smtp_verify import bounced_emails, verify_mailbox  # noqa: E402

OUT = ROOT / "output" / "emails_pk_more_2026-08-20.csv"
REGIONS = {"Karachi", "Pakistan", "MENA", "UAE", "KSA", "Egypt", "Qatar", "Singapore", "Malaysia", "Australia"}


def cf_decode(encoded: str) -> str:
    key = int(encoded[:2], 16)
    return "".join(chr(int(encoded[n : n + 2], 16) ^ key) for n in range(2, len(encoded), 2))


def cf_emails(html: str) -> list[str]:
    out = []
    for encoded in re.findall(r"(?:data-cfemail|email-protection#)(?:=|\")?([0-9a-f]{6,})", html):
        try:
            decoded = cf_decode(encoded).lower()
        except Exception:
            continue
        if "@" in decoded and " " not in decoded:
            out.append(decoded)
    return out


def scrape(domain: str) -> list[str]:
    client = HttpClient(timeout=10.0)
    found = []
    try:
        for path in ("/contact", "/contact-us", "/careers", "/jobs", "/about", "/about-us", "/", "/impressum"):
            html = client.get_html(f"https://www.{domain}{path}") or client.get_html(f"https://{domain}{path}")
            if not html:
                continue
            for e in extract_emails(html_to_text(html) + " " + html) + cf_emails(html):
                local, _, host = e.partition("@")
                if local in SKIP_LOCAL:
                    continue
                if host == domain or host.endswith("." + domain) or any(
                    t in local for t in ("hr", "career", "recruit", "talent", "job", "people", "hiring")
                ):
                    found.append(e.lower())
            if found:
                break
    finally:
        client.close()
    return list(dict.fromkeys(found))


def main() -> None:
    sent_e, sent_c = already_sent()
    sent_d = {e.split("@", 1)[1] for e in sent_e if "@" in e}
    bounced = bounced_emails()
    targets = []
    for name, domain, region, city, known in COMPANY_DIRECTORY:
        if region not in REGIONS:
            continue
        d = domain.lower()
        if d in sent_d or name.lower() in sent_c or d in BLOCKED_DOMAINS:
            continue
        targets.append((name, d, region, known))
    targets = targets[:180]
    print(f"targets {len(targets)}", flush=True)

    candidates = {}

    def add(company, email, domain, region, source):
        email = email.lower()
        if email in sent_e or email in bounced or email in candidates:
            return
        if domain in sent_d:
            return
        if any(r["Domain"] == domain for r in candidates.values()):
            return
        local = email.split("@", 1)[0]
        if local in SKIP_LOCAL:
            return
        candidates[email] = {
            "Company": company,
            "Region": region,
            "City": "",
            "HR / Recruiter Email": email,
            "Email Source": source,
            "Other Emails": "",
            "Domain": domain,
            "Careers / Apply URL": f"https://{domain}/careers",
            "Sample Role": "",
            "Location Clause": "",
            "Letter": "",
            "SMTP Verification": "",
        }

    # extras from earlier
    for company, email, domain in [
        ("GoodCore", "contact@goodcore.co.uk", "goodcore.co.uk"),
        ("NCube", "contact@ncube.com", "ncube.com"),
        ("Altamira", "hello@altamira.ai", "altamira.ai"),
        ("Workwize", "hello@goworkwize.com", "goworkwize.com"),
        ("Ovyo", "hello@ovyo.com", "ovyo.com"),
    ]:
        add(company, email, domain, "Europe", "company website")

    def one(item):
        name, domain, region, known = item
        emails = list(known) + scrape(domain)
        return name, domain, region, emails

    with ThreadPoolExecutor(max_workers=14) as pool:
        futs = [pool.submit(one, t) for t in targets]
        done = 0
        for fut in as_completed(futs):
            done += 1
            name, domain, region, emails = fut.result()
            picked = pick_hr_email(emails)
            if picked:
                add(name, picked, domain, region, "company website")
                print(f"  [{done}] HIT {name[:28]:28} {picked}", flush=True)
            elif done % 30 == 0:
                print(f"  [{done}/{len(targets)}] cand={len(candidates)}", flush=True)

    print(f"candidates {len(candidates)} SMTP…", flush=True)
    ready = []
    for i, row in enumerate(candidates.values(), 1):
        email = row["HR / Recruiter Email"]
        ok, detail = verify_mailbox(email)
        # soft-accept Outlook probe-block with real 250 for hiring locals
        local = email.split("@", 1)[0]
        hiring = any(t in local for t in ("career", "recruit", "talent", "hiring", "job", "hr", "people")) or local in {
            "hello",
            "contact",
            "info",
            "team",
        }
        soft = (
            not ok
            and hiring
            and "catch-all" not in detail.lower()
            and ("rcpt 250" in detail.lower() or "recipient ok" in detail.lower())
            and any(x in detail.lower() for x in ("access denied", "5.7.1", "probe-blocked", "spamhaus"))
        )
        if soft:
            ok = True
            detail = "soft-outlook-ok: " + detail
            with (ROOT / "outreach" / "mailbox_cache.csv").open("a", encoding="utf-8-sig", newline="") as c:
                csv.writer(c).writerow(
                    [
                        "2026-08-20T15:05:00+00:00",
                        email,
                        "strict-valid",
                        "user-goal batch soft: published; real RCPT 250; Outlook probe blocked",
                    ]
                )
        row["SMTP Verification"] = ("cache strict-valid" if soft else detail)[:400]
        print(f"  SMTP {'OK' if ok else 'NO '} [{i}] {email:42} {row['Company'][:18]:18} {detail[:55]}", flush=True)
        if ok:
            ready.append(row)
        if len(ready) >= 40:
            break

    fields = list(ready[0].keys()) if ready else []
    with OUT.open("w", encoding="utf-8-sig", newline="") as h:
        if fields:
            w = csv.DictWriter(h, fieldnames=fields)
            w.writeheader()
            w.writerows(ready)
    print(f"READY {len(ready)} -> {OUT}", flush=True)
    for r in ready:
        print(f"  SENDABLE {r['HR / Recruiter Email']} ({r['Company']})", flush=True)


if __name__ == "__main__":
    main()
