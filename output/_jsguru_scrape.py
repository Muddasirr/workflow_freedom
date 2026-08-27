#!/usr/bin/env python3
"""Parallel scrape + SMTP for domains already resolved from JSGuru listings."""
from __future__ import annotations

import csv
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "outreach"))

from job_hunter.emails import pick_hr_email  # noqa: E402
from job_hunter.textutil import extract_emails, html_to_text  # noqa: E402
from send_emails import SKIP_LOCAL, already_sent  # noqa: E402
from smtp_verify import bounced_emails, verify_mailbox  # noqa: E402

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
PATHS = ("/careers", "/contact", "/jobs", "/", "/about", "/impressum")
LOG = Path(
    "/home/sleepwellsystem/.cursor/projects/home-sleepwellsystem-Desktop-codet-webb/terminals/557850.txt"
)
LISTING_RE = re.compile(
    r'href="https://jsgurujobs.com/jobs/(\d+)"[^>]*>\s*([^<]+?)\s*</a>'
    r'.*?<p class="mt-1 text-sm text-gray-500[^"]*"[^>]*>([^<]+)</p>',
    re.S,
)


def cf_decode(encoded: str) -> str:
    key = int(encoded[:2], 16)
    return "".join(chr(int(encoded[n : n + 2], 16) ^ key) for n in range(2, len(encoded), 2))


def cf_emails(html: str) -> list[str]:
    out: list[str] = []
    for encoded in re.findall(r"(?:data-cfemail|email-protection#)(?:=|\")?([0-9a-f]{6,})", html):
        try:
            decoded = cf_decode(encoded).lower()
        except Exception:
            continue
        if "@" in decoded and " " not in decoded:
            out.append(decoded)
    return out


def load_resolved() -> list[tuple[str, str]]:
    text = LOG.read_text(errors="replace")
    rows = re.findall(r"^  DOMAIN  (.+?)\s{2,}(\S+)$", text, re.M)
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for name, domain in rows:
        name = name.strip()
        domain = domain.strip().lower()
        if domain in seen:
            continue
        seen.add(domain)
        out.append((name, domain))
    return out


def listing_titles() -> dict[str, str]:
    titles: dict[str, str] = {}
    client = httpx.Client(headers={"User-Agent": UA}, follow_redirects=True, timeout=25)
    first = client.get("https://jsgurujobs.com/jobs").text
    pages = {int(x) for x in re.findall(r"/jobs\?page=(\d+)", first)}
    last = max(pages) if pages else 1
    for page in range(1, last + 1):
        html = first if page == 1 else client.get(f"https://jsgurujobs.com/jobs?page={page}").text
        for _jid, title, company in LISTING_RE.findall(html):
            titles[unescape(company).strip().lower()] = unescape(title).strip()
    client.close()
    return titles


def scrape_one(domain: str) -> list[str]:
    found: list[str] = []
    client = httpx.Client(headers={"User-Agent": UA}, follow_redirects=True, timeout=6.0)
    try:
        for path in PATHS:
            for url in (f"https://www.{domain}{path}", f"https://{domain}{path}"):
                try:
                    r = client.get(url)
                except Exception:
                    continue
                if r.status_code >= 400 or not r.text:
                    continue
                emails = extract_emails(html_to_text(r.text) + " " + r.text) + cf_emails(r.text)
                for email in emails:
                    local, _, host = email.partition("@")
                    if local in SKIP_LOCAL:
                        continue
                    if host == domain or host.endswith("." + domain):
                        found.append(email)
                    elif any(tok in local for tok in ("hr", "career", "recruit", "talent", "people", "hiring", "job")):
                        if host not in {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com"}:
                            found.append(email)
                if found:
                    return list(dict.fromkeys(found))
    finally:
        client.close()
    return list(dict.fromkeys(found))


def main() -> None:
    resolved = load_resolved()
    print(f"scrape {len(resolved)} domains", flush=True)
    titles = listing_titles()
    print(f"listing titles {len(titles)}", flush=True)
    sent_e, sent_c = already_sent()
    sent_d = {e.split("@", 1)[1] for e in sent_e if "@" in e}
    bounced = bounced_emails()

    candidates: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=16) as pool:
        futs = {pool.submit(scrape_one, domain): (name, domain) for name, domain in resolved}
        done = 0
        for fut in as_completed(futs):
            name, domain = futs[fut]
            done += 1
            try:
                emails = fut.result()
            except Exception as exc:
                emails = []
                print(f"  ERR {name} {domain} {exc}", flush=True)
            picked = pick_hr_email(emails)
            print(f"  SCRAPE {done}/{len(resolved)} {name:32} {domain:28} {picked or '-'}", flush=True)
            if not picked or picked in sent_e or picked in bounced:
                continue
            if domain in sent_d or name.strip().lower() in sent_c:
                continue
            if picked.split("@", 1)[0] in SKIP_LOCAL:
                continue
            candidates.append(
                {
                    "Company": name,
                    "Region": "Remote",
                    "City": "",
                    "HR / Recruiter Email": picked,
                    "Email Source": "company website",
                    "Other Emails": "; ".join(emails[:6]),
                    "Domain": domain,
                    "Careers / Apply URL": "https://jsgurujobs.com/jobs",
                    "Sample Role": titles.get(name.strip().lower(), ""),
                    "Location Clause": "",
                    "Letter": "",
                    "SMTP Verification": "",
                }
            )

    print(f"published emails to probe: {len(candidates)}", flush=True)
    ready: list[dict[str, str]] = []
    for row in candidates:
        email = row["HR / Recruiter Email"]
        ok, detail = verify_mailbox(email)
        row["SMTP Verification"] = (detail or "")[:400]
        print(f"  SMTP {'OK' if ok else 'NO '} {email:48} {row['Company'][:22]:22} {detail[:70]}", flush=True)
        if ok:
            ready.append(row)

    out = ROOT / "output" / "emails_jsguru_2026-08-19.csv"
    fields = list(ready[0].keys()) if ready else [
        "Company", "Region", "City", "HR / Recruiter Email", "Email Source",
        "Other Emails", "Domain", "Careers / Apply URL", "Sample Role",
        "Location Clause", "Letter", "SMTP Verification",
    ]
    with out.open("w", encoding="utf-8-sig", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=fields)
        w.writeheader()
        w.writerows(ready)
    print(f"READY {len(ready)} -> {out}", flush=True)
    for row in ready:
        print(f"  SENDABLE {row['HR / Recruiter Email']} ({row['Company']})", flush=True)


if __name__ == "__main__":
    main()
