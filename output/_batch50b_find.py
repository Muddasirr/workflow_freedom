#!/usr/bin/env python3
"""Aggressive published-email hunter for 50 sends. Directory leftovers + WWR/Jobicy mailtos."""
from __future__ import annotations

import csv
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "outreach"))

from job_hunter.config import PK_CONTACT_PATHS  # noqa: E402
from job_hunter.directory import COMPANY_DIRECTORY, JUNK_LOCAL  # noqa: E402
from job_hunter.emails import pick_hr_email  # noqa: E402
from job_hunter.http import HttpClient  # noqa: E402
from job_hunter.textutil import extract_emails, html_to_text  # noqa: E402
from send_emails import BLOCKED_COMPANIES, BLOCKED_DOMAINS, SKIP_LOCAL, WEAK_LOCAL, already_sent  # noqa: E402
from smtp_verify import bounced_emails, verify_mailbox  # noqa: E402

OUT = ROOT / "output" / "emails_batch50b_2026-08-20.csv"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
HIRING = ("career", "recruit", "talent", "hiring", "people", "job", "hr", "join", "apply")
EXTRA_SKIP = {
    "feedback", "compliance", "fraud", "gdpr", "marketing", "mktg", "newsletter",
    "press", "media", "sales", "support", "help", "billing", "legal", "privacy",
    "noreply", "no-reply", "notices", "vulnerability", "kyc", "assistenza",
    "partners", "partnerships", "security", "investors", "ir", "email",
}
REGIONS = {"Europe", "Remote", "Australia", "Singapore", "MENA", "UAE", "KSA", "Qatar", "Egypt", "Malaysia", "Pakistan", "Karachi"}


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


def blocked_co(name: str) -> bool:
    key = name.strip().lower()
    return any(b == key or b in key for b in BLOCKED_COMPANIES)


def usable(email: str) -> bool:
    email = email.strip().lower()
    if "@" not in email:
        return False
    local, _, host = email.partition("@")
    if local in SKIP_LOCAL or local in EXTRA_SKIP or any(j in local for j in JUNK_LOCAL):
        return False
    if host in BLOCKED_DOMAINS or host.endswith((".gov", ".gov.au", ".edu", ".ac.uk")):
        return False
    if host in {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com"}:
        return False
    if any(t in local for t in HIRING) or local.startswith("hr") or "." in local:
        return True
    if local in WEAK_LOCAL | {"hello", "hi", "contact", "info", "team", "business", "opportunities", "nextbit"}:
        return True
    return False


def scrape_domain(client: HttpClient, domain: str) -> list[str]:
    found: list[str] = []
    paths = list(PK_CONTACT_PATHS[:10])
    # prefer impressum early for EU
    for extra in ("/impressum", "/imprint", "/legal-notice", "/legal", "/team", "/about/contact"):
        if extra not in paths:
            paths.insert(0, extra)
    for path in paths[:12]:
        html = client.get_html(f"https://www.{domain}{path}") or client.get_html(f"https://{domain}{path}")
        if not html:
            continue
        emails = extract_emails(html_to_text(html) + " " + html) + cf_emails(html)
        for email in emails:
            local, _, host = email.partition("@")
            if local in SKIP_LOCAL or local in EXTRA_SKIP:
                continue
            if host == domain or host.endswith("." + domain) or any(t in local for t in HIRING):
                if usable(email):
                    found.append(email.lower())
        if any(any(t in e.split("@")[0] for t in HIRING) for e in found):
            break
        if found:
            break
    return list(dict.fromkeys(found))


def wwr_emails() -> list[tuple[str, str, str, str]]:
    """Return (company, email, role, url) from WWR category pages."""
    out = []
    client = httpx.Client(headers={"User-Agent": UA}, follow_redirects=True, timeout=30)
    urls = [
        "https://weworkremotely.com/categories/remote-programming-jobs",
        "https://weworkremotely.com/categories/remote-full-stack-programming-jobs",
        "https://weworkremotely.com/categories/remote-front-end-programming-jobs",
        "https://weworkremotely.com/categories/remote-back-end-programming-jobs",
    ]
    job_links = []
    for u in urls:
        try:
            html = client.get(u).text
        except Exception:
            continue
        job_links += re.findall(r'href="(/remote-jobs/[^"]+)"', html)
        time.sleep(0.2)
    job_links = list(dict.fromkeys(job_links))[:120]
    print(f"  WWR job links: {len(job_links)}", flush=True)
    for path in job_links:
        try:
            html = client.get(f"https://weworkremotely.com{path}").text
        except Exception:
            continue
        company = ""
        m = re.search(r'class="company"[^>]*>\s*([^<]+)', html)
        if m:
            company = m.group(1).strip()
        title = ""
        m = re.search(r'class="listing-header-container"[^>]*>.*?<h1[^>]*>\s*([^<]+)', html, re.S)
        if not m:
            m = re.search(r"<h1[^>]*>\s*([^<]+)", html)
        if m:
            title = m.group(1).strip()
        emails = extract_emails(html) + cf_emails(html)
        for email in emails:
            if usable(email) and "weworkremotely" not in email:
                out.append((company or email.split("@")[1], email.lower(), title, f"https://weworkremotely.com{path}"))
                break
        time.sleep(0.12)
    client.close()
    return out


def main() -> None:
    sent_e, sent_c = already_sent()
    sent_d = {e.split("@", 1)[1] for e in sent_e if "@" in e}
    bounced = bounced_emails()
    candidates: dict[str, dict[str, str]] = {}

    def add(company: str, email: str, domain: str, source: str, role: str = "", url: str = "", region: str = "Remote") -> None:
        email = email.strip().lower()
        domain = (domain or email.split("@", 1)[1]).lower()
        company = company.strip()
        if not usable(email):
            return
        if email in sent_e or email in bounced or email in candidates:
            return
        if company.lower() in sent_c or blocked_co(company):
            return
        if domain in sent_d or domain in BLOCKED_DOMAINS:
            return
        if any(r["Domain"] == domain for r in candidates.values()):
            return
        candidates[email] = {
            "Company": company,
            "Region": region,
            "City": "",
            "HR / Recruiter Email": email,
            "Email Source": source,
            "Other Emails": "",
            "Domain": domain,
            "Careers / Apply URL": url,
            "Sample Role": role,
            "Location Clause": " (remote)" if region in {"Remote", "Europe", "Australia", "Singapore"} else "",
            "Letter": "",
            "SMTP Verification": "",
        }

    # Seed from cache strict-valid unsent (published historically)
    print("Seeding from mailbox cache…", flush=True)
    status = {}
    with (ROOT / "outreach" / "mailbox_cache.csv").open(encoding="utf-8-sig") as h:
        for r in csv.DictReader(h):
            e = (r.get("email") or "").lower().strip()
            s = (r.get("status") or "").lower().strip()
            if e and s:
                status[e] = s
    seed_map = {
        "mdpi.com": ("MDPI", "hr.singapore@mdpi.com"),
        "dinindustries.com": ("Din Industries", "hrdpl@dinindustries.com"),
        "bsscommerce.com": ("BSS Commerce", "middle.east@bsscommerce.com"),
        "eocean.net": ("eOcean", "anum.khan@eocean.net"),
        "pointnine.com": ("Point Nine", "info@pointnine.com"),
        "earlybird.com": ("Earlybird", "info@earlybird.com"),
        "narsunstudios.com": ("Narsun Studios", "info@narsunstudios.com"),
        "vizteck.com": ("Vizteck", "info@vizteck.com"),
        "agilebits.com": ("1Password", "nextbit@agilebits.com"),
        "solutioninn.com": ("SolutionInn", "mahrukh@solutioninn.com"),
        "1password.com": ("1Password", "business@1password.com"),
        "suzukicanal.com.pk": ("Suzuki Canal", "sohail@suzukicanal.com.pk"),
        "gamedistrict.co": ("Game District", "hassanmahmood@gamedistrict.co"),
        "remotebase.com": ("RemoteBase", "people@remotebase.com"),
        "webnet.com.pk": ("Webnet", "info@webnet.com.pk"),
        "ephlux.com": ("Ephlux", "info@ephlux.com"),
        "iconosquare.com": ("Iconosquare", "hr@iconosquare.com"),
        "imweb.me": ("imweb", "hr@imweb.me"),
        "leadiq.com": ("LeadIQ", "hr@leadiq.com"),
        "bandwidth.com": ("Bandwidth", "hr@bandwidth.com"),
        "baydin.com": ("Baydin", "jobs@baydin.com"),
        "thefabulous.co": ("The Fabulous", "jobs@thefabulous.co"),
        "devathon.com": ("Devathon", "hello@devathon.com"),
        "dubizzle.com": ("dubizzle", "hr@dubizzle.com"),
        "doctrine.fr": ("Doctrine", "contact@doctrine.fr"),
        "cabify.com": ("Cabify", "contact@cabify.com"),
        "backmarket.com": ("Back Market", "hello@backmarket.com"),
        "blablacar.com": ("BlaBlaCar", "contact@blablacar.com"),
    }
    for domain, (company, email) in seed_map.items():
        if status.get(email) == "strict-valid":
            add(company, email, domain, "company website", region="Remote")
    print(f"  seeded {len(candidates)}", flush=True)

    # WWR mailtos
    print("Scraping We Work Remotely job pages…", flush=True)
    for company, email, role, url in wwr_emails():
        add(company, email, email.split("@", 1)[1], "hiring post apply-to", role=role, url=url)
    print(f"  after WWR: {len(candidates)}", flush=True)

    # Directory leftovers
    targets = []
    for name, domain, region, city, known in COMPANY_DIRECTORY:
        if region not in REGIONS:
            continue
        d = domain.lower()
        if d in sent_d or name.lower() in sent_c or blocked_co(name):
            continue
        if any(r["Domain"] == d for r in candidates.values()):
            continue
        for email in known:
            add(name, email, d, "known company contact", region=region)
        targets.append((name, d, region))
    # Prefer Europe/Remote first
    order = {"Europe": 0, "Remote": 1, "Australia": 2, "Singapore": 3, "MENA": 4}
    targets.sort(key=lambda t: (order.get(t[2], 9), t[0].lower()))
    targets = targets[:400]
    print(f"Scraping {len(targets)} directory companies…", flush=True)

    def one(item):
        name, domain, region = item
        local = HttpClient(timeout=10.0)
        try:
            emails = scrape_domain(local, domain)
        finally:
            local.close()
        return name, domain, region, emails

    with ThreadPoolExecutor(max_workers=16) as pool:
        futs = [pool.submit(one, t) for t in targets]
        done = 0
        for fut in as_completed(futs):
            done += 1
            name, domain, region, emails = fut.result()
            picked = pick_hr_email(emails)
            if picked and usable(picked):
                add(name, picked, domain, "company website", region=region)
                print(f"  [{done}/{len(targets)}] HIT {name[:30]:30} {picked}", flush=True)
            elif done % 40 == 0:
                print(f"  [{done}/{len(targets)}] … candidates={len(candidates)}", flush=True)

    print(f"candidates before SMTP: {len(candidates)}", flush=True)
    rows = list(candidates.values())

    def rank(r):
        local = r["HR / Recruiter Email"].split("@", 1)[0]
        score = 0
        if any(t in local for t in ("career", "recruit", "talent", "hiring", "job", "hr", "people")):
            score -= 10
        if local in WEAK_LOCAL:
            score += 5
        return (score, r["Company"].lower())

    rows.sort(key=rank)
    ready = []
    print(f"SMTP probing {len(rows)}…", flush=True)
    for i, row in enumerate(rows, 1):
        email = row["HR / Recruiter Email"]
        # skip known junk guesses
        if email == "hr@datics.ai":
            continue
        ok, detail = verify_mailbox(email)
        row["SMTP Verification"] = (detail or "")[:400]
        print(f"  SMTP {'OK' if ok else 'NO '} [{i}/{len(rows)}] {email:46} {row['Company'][:20]:20} {detail[:55]}", flush=True)
        if ok:
            ready.append(row)
        if len(ready) >= 60:
            break

    fields = list(ready[0].keys()) if ready else [
        "Company", "Region", "City", "HR / Recruiter Email", "Email Source", "Other Emails",
        "Domain", "Careers / Apply URL", "Sample Role", "Location Clause", "Letter", "SMTP Verification",
    ]
    with OUT.open("w", encoding="utf-8-sig", newline="") as h:
        w = csv.DictWriter(h, fieldnames=fields)
        w.writeheader()
        w.writerows(ready)
    print(f"READY {len(ready)} -> {OUT}", flush=True)
    for r in ready:
        print(f"  SENDABLE {r['HR / Recruiter Email']} ({r['Company']})", flush=True)


if __name__ == "__main__":
    main()
