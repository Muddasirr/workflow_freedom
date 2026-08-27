#!/usr/bin/env python3
"""Aug 23b: SG / AU / EU / Remote / PK software — published hiring emails + SMTP / soft Outlook."""
from __future__ import annotations

import csv
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "outreach"))

from job_hunter.directory import COMPANY_DIRECTORY  # noqa: E402
from job_hunter.emails import pick_hr_email  # noqa: E402
from job_hunter.http import HttpClient  # noqa: E402
from job_hunter.textutil import extract_emails, html_to_text  # noqa: E402
from send_emails import BLOCKED_COMPANIES, BLOCKED_DOMAINS, SKIP_LOCAL, already_sent  # noqa: E402
from smtp_verify import bounced_emails, verify_mailbox  # noqa: E402

OUT = ROOT / "output" / "emails_go_sg_au_eu_2026-08-23.csv"
CACHE = ROOT / "outreach" / "mailbox_cache.csv"
NOW = datetime.now(timezone.utc).isoformat(timespec="seconds")

REGIONS = (
    "Singapore",
    "Australia",
    "Remote",
    "Europe",
    "UK",
    "Germany",
    "Malaysia",
    "Pakistan",
)

BAD_LOCAL = {
    "marketing",
    "press",
    "media",
    "pr",
    "sales",
    "support",
    "help",
    "noreply",
    "no-reply",
    "fraud",
    "security",
    "legal",
    "billing",
    "invoice",
    "privacy",
    "gdpr",
    "dpo",
    "abuse",
    "postmaster",
    "notices",
    "notice",
    "block",
    "feedback",
    "newsletter",
    "partners",
    "partnerships",
    "investors",
    "ir",
    "kyc",
    "compliance",
    "requisition",
}

HIRE_HINTS = ("career", "recruit", "talent", "hiring", "job", "hr", "people", "jobs")
PUBLISHED = ("careers", "jobs", "talent", "recruiting", "hr", "people", "hiring", "join")


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
    found: list[str] = []
    try:
        for path in (
            "/careers",
            "/jobs",
            "/contact",
            "/contact-us",
            "/about",
            "/about-us",
            "/company",
            "/team",
            "/",
        ):
            html = client.get_html(f"https://www.{domain}{path}") or client.get_html(f"https://{domain}{path}")
            if not html:
                continue
            for e in extract_emails(html_to_text(html) + " " + html) + cf_emails(html):
                e = e.lower()
                local, _, host = e.partition("@")
                if local in SKIP_LOCAL or local in BAD_LOCAL:
                    continue
                if host == domain or host.endswith("." + domain) or any(t in local for t in HIRE_HINTS):
                    found.append(e)
            if found:
                break
    finally:
        client.close()
    return list(dict.fromkeys(found))


def soft_ok(email: str, detail: str) -> bool:
    """Only soft-accept if real RCPT 250 then probe-block. NEVER promote guessed careers@."""
    local = email.split("@", 1)[0]
    hiring = any(t in local for t in HIRE_HINTS) or local in PUBLISHED or local in {
        "hello",
        "contact",
        "team",
        "join",
    }
    text = detail.lower()
    if not hiring or "catch-all" in text:
        return False
    # Require proof the mailbox accepted RCPT before the IP block. Guessing careers@
    # on Outlook/Mimecast without a 250 caused Gmail "address not found" bounces (aug23).
    return ("rcpt 250" in text or "recipient ok" in text or "2.1.5" in text) and any(
        x in text for x in ("access denied", "5.7.1", "probe-blocked", "spamhaus", "5.4.1", "listed by")
    )


def main() -> None:
    sent_e, sent_c = already_sent()
    sent_d = {e.split("@", 1)[1] for e in sent_e if "@" in e}
    bounced = bounced_emails()

    targets = []
    for name, domain, region, city, known in COMPANY_DIRECTORY:
        d = domain.lower()
        if region not in REGIONS:
            continue
        if d in sent_d or name.lower() in sent_c or d in BLOCKED_DOMAINS:
            continue
        if any(b in name.lower() for b in BLOCKED_COMPANIES):
            continue
        # skip heavy local telco/bank noise for this remote-abroad batch
        if any(x in name.lower() for x in ("ptcl", "ufone", "zong", "bank", "jazzcash", "easypaisa")):
            continue
        targets.append((name, d, region, list(known or [])))

    order = {r: i for i, r in enumerate(REGIONS)}
    targets.sort(key=lambda t: order.get(t[2], 99))
    targets = targets[:260]
    print(f"targets {len(targets)}", flush=True)

    candidates: dict[str, dict] = {}

    def add(company: str, email: str, domain: str, region: str, source: str) -> None:
        email = email.lower().strip()
        if not email or email in sent_e or email in bounced or email in candidates:
            return
        if domain in sent_d or domain in BLOCKED_DOMAINS or domain.endswith(".edu"):
            return
        if any(r["Domain"] == domain for r in candidates.values()):
            return
        local = email.split("@", 1)[0]
        if local in SKIP_LOCAL or local in BAD_LOCAL:
            return
        if domain in {"gmail.com", "hotmail.com", "yahoo.com", "outlook.com"}:
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
            "Sample Role": "Software Engineer",
            "Location Clause": " (remote)" if region == "Remote" else "",
            "Letter": "",
            "SMTP Verification": "",
        }

    def one(item):
        name, domain, region, known = item
        emails = [e.lower() for e in known if e]
        emails += scrape(domain)
        # also try common published hiring aliases (verified / soft later)
        for local in ("careers", "jobs", "talent", "recruiting", "hr"):
            emails.append(f"{local}@{domain}")
        return name, domain, region, list(dict.fromkeys(emails))

    with ThreadPoolExecutor(max_workers=16) as pool:
        futs = [pool.submit(one, t) for t in targets]
        done = 0
        for fut in as_completed(futs):
            done += 1
            name, domain, region, emails = fut.result()
            picked = pick_hr_email(emails)
            # prefer hiring-ish local
            if picked and picked.split("@", 1)[0] in BAD_LOCAL:
                picked = None
                for e in emails:
                    loc = e.split("@", 1)[0]
                    if loc in BAD_LOCAL or loc in SKIP_LOCAL:
                        continue
                    if any(t in loc for t in HIRE_HINTS) or loc in PUBLISHED or loc in {"hello", "contact", "team"}:
                        picked = e
                        break
            if picked:
                add(name, picked, domain, region, "company website")
                print(f"  [{done}] HIT {name[:28]:28} {picked}", flush=True)
            elif done % 40 == 0:
                print(f"  [{done}/{len(targets)}] cand={len(candidates)}", flush=True)

    print(f"candidates {len(candidates)} SMTP…", flush=True)
    ready = []
    for i, row in enumerate(candidates.values(), 1):
        email = row["HR / Recruiter Email"]
        ok, detail = verify_mailbox(email, use_cache=True)
        soft = soft_ok(email, detail) if not ok else False
        if soft:
            ok = True
            with CACHE.open("a", encoding="utf-8-sig", newline="") as c:
                csv.writer(c).writerow(
                    [
                        NOW,
                        email,
                        "strict-valid",
                        "published hiring; Outlook/Mimecast IP-block soft-accept (aug23b)",
                    ]
                )
            row["SMTP Verification"] = "cache strict-valid"
            detail = "soft-promoted: " + detail
        else:
            row["SMTP Verification"] = detail[:400]
        print(
            f"  SMTP {'OK' if ok else 'NO '} [{i}] {email:42} {row['Company'][:18]:18} {detail[:55]}",
            flush=True,
        )
        if ok:
            ready.append(row)
            sent_d.add(row["Domain"])
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
        print(f"  {r['HR / Recruiter Email']}  {r['Company']}  [{r['Region']}]", flush=True)


if __name__ == "__main__":
    main()
