#!/usr/bin/env python3
"""Find hiring / talent / careers emails for PK-open remote NON-Pakistan companies.

Hunter preferred; on 429/credit-empty falls back to:
  1) emails already on job postings
  2) SMTP-strict guesses (careers/jobs/talent/recruiting/people/hr)
  3) published website scrapes

A/B arms assigned alternately for Reddit strategy test.
"""
from __future__ import annotations

import csv
import re
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "outreach"))
load_dotenv(ROOT / ".env")

from job_hunter.config import HUNTER_API_KEY, PK_CONTACT_PATHS  # noqa: E402
from job_hunter.directory import COMPANY_DIRECTORY, JUNK_LOCAL  # noqa: E402
from job_hunter.emails import WELL_KNOWN_COMPANY_DOMAINS, pick_hr_email, resolve_company_domain  # noqa: E402
from job_hunter.http import HttpClient  # noqa: E402
from job_hunter.models import Job  # noqa: E402
from job_hunter.textutil import extract_emails, html_to_text  # noqa: E402
from send_emails import BLOCKED_COMPANIES, BLOCKED_DOMAINS, SKIP_LOCAL, already_sent  # noqa: E402
from smtp_verify import verify_mailbox  # noqa: E402

OUT = ROOT / "output" / "emails_hm_ab_2026-08-25.csv"
JOB_CSV = ROOT / "output" / "jobs_pk_remote_fresh_2026-08-25.csv"
TARGET = 16
GUESS_LOCALS = ("jobs", "careers", "talent", "recruiting", "people", "hr", "join")

PK_REGIONS = {"Karachi", "Pakistan"}
SKIP_LIKELY_US_ONLY = {
    "coinbase", "dropbox", "airbnb", "reddit", "datadog", "twilio", "gusto",
    "gusto, inc.", "doximity", "hightouch", "nuuly", "faire", "lattice",
    "reveleer", "canonical", "canonical ltd.", "stripe", "vercel", "toptal",
    "andela", "gitlab", "openai", "anthropic", "cloudflare", "airtable",
    "lemon.io", "n8n", "huggingface", "hugging face",
}
EXTRA_DOMAINS = {
    "proxify ab": "proxify.io", "proxify": "proxify.io", "a.team": "a.team",
    "base.com": "base.com", "huzzle": "huzzle.app", "clickhouse": "clickhouse.com",
    "sticker mule": "stickermule.com", "fueled": "fueled.com", "cohere": "cohere.com",
    "highlevel": "gohighlevel.com", "trafilea": "trafilea.com", "cosuno": "cosuno.com",
    "confluent": "confluent.io", "zeta global": "zetaglobal.com",
    "collaboration.ai": "collaboration.ai", "camunda": "camunda.com",
    "socket": "socket.dev", "vonage": "vonage.com", "relationalai": "relational.ai",
    "harbor": "goharbor.io", "memberspace": "memberspace.com", "hygraph": "hygraph.com",
    "speechify": "speechify.com", "speechify inc": "speechify.com",
    "descript": "descript.com", "azumo": "azumo.com", "lithic": "lithic.com",
    "superplane": "superplane.io", "wonderdog": "wonderdog.ai", "Kruger NearShore LLC - Rekluti": "rekluti.com",
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def pk_hq() -> tuple[set[str], set[str]]:
    names, domains = set(), set()
    for name, domain, region, *_ in COMPANY_DIRECTORY:
        if region in PK_REGIONS:
            names.add(_norm(name))
            domains.add(domain.lower())
    return names, domains


def load_companies() -> list[dict[str, str]]:
    pk_names, _ = pk_hq()
    by_co: dict[str, dict[str, str]] = {}
    with JOB_CSV.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if (row.get("Pakistan Friendly") or "").strip() != "Yes":
                continue
            if (row.get("Work Mode") or "").strip().lower() != "remote":
                continue
            fit = (row.get("Location Fit") or "").lower()
            if "on-site" in fit:
                continue
            co = (row.get("Company") or "").strip()
            if not co:
                continue
            key = _norm(co)
            if key in pk_names or key in SKIP_LIKELY_US_ONLY:
                continue
            if any(b == key or b in key for b in BLOCKED_COMPANIES):
                continue
            # skip .pk employers
            dom = (row.get("Company Domain") or "").lower()
            if dom.endswith(".pk"):
                continue
            title = (row.get("Title") or "").strip()
            prefer = any(
                t in title.lower()
                for t in (
                    "software", "frontend", "front-end", "full stack", "full-stack",
                    "product engineer", "ai engineer", "react", "typescript", "python",
                    "backend", "platform",
                )
            )
            prev = by_co.get(key)
            posted = (row.get("HR / Recruiter Email") or "").strip().lower()
            if prev:
                prev["n"] = str(int(prev.get("n") or "1") + 1)
                if posted and not prev.get("posted_email"):
                    prev["posted_email"] = posted
                    prev["email_source"] = row.get("Email Source") or "job posting"
                if prefer and not any(
                    t in (prev.get("title") or "").lower()
                    for t in ("software", "frontend", "full", "product", "ai ", "react")
                ):
                    prev["title"] = title
                continue
            by_co[key] = {
                "company": co,
                "title": title,
                "fit": row.get("Location Fit") or "",
                "location": row.get("Location") or "",
                "url": row.get("URL") or "",
                "domain": dom,
                "posted_email": posted,
                "email_source": row.get("Email Source") or "",
                "n": "1",
            }
    return sorted(by_co.values(), key=lambda r: -int(r.get("n") or "1"))


def resolve_domain(company: str, url: str = "", existing: str = "") -> str:
    if existing and not any(x in existing for x in ("weworkremotely", "jobicy", "remotive", "greenhouse", "lever.co")):
        return existing
    key = _norm(company)
    if key in EXTRA_DOMAINS:
        return EXTRA_DOMAINS[key]
    if key in WELL_KNOWN_COMPANY_DOMAINS:
        return WELL_KNOWN_COMPANY_DOMAINS[key]
    job = Job(source="hm", source_id="", title="", company=company, url=url)
    domain = resolve_company_domain(job)
    if domain and not any(x in domain for x in ("weworkremotely", "jobicy", "remotive", "greenhouse", "lever.co")):
        return domain
    for listed, dom, region, *_ in COMPANY_DIRECTORY:
        if region in PK_REGIONS:
            continue
        if _norm(listed) == key:
            return dom.lower()
    return ""


def usable(email: str, pk_domains: set[str]) -> bool:
    email = (email or "").strip().lower()
    if "@" not in email:
        return False
    local, _, host = email.partition("@")
    if local in SKIP_LOCAL or host in BLOCKED_DOMAINS or host in pk_domains or host.endswith(".pk"):
        return False
    if host in {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com"}:
        return False
    hiringish = any(t in local for t in ("career", "recruit", "talent", "hiring", "people", "job")) or local.startswith("hr")
    return hiringish or local in {"hello", "hi", "join", "apply", "team", "jobs", "careers"}


def scrape_domain(domain: str) -> list[str]:
    client = HttpClient()
    found: list[str] = []
    try:
        for path in ("/careers", "/jobs", "/about", "/contact", "/contact-us", "/company", "/"):
            html = client.get_html(f"https://www.{domain}{path}") or client.get_html(f"https://{domain}{path}")
            if not html:
                continue
            for email in extract_emails(html_to_text(html) + " " + html):
                email = email.lower()
                local, _, host = email.partition("@")
                if local in SKIP_LOCAL or any(j in local for j in JUNK_LOCAL):
                    continue
                if host == domain or host.endswith("." + domain) or usable(email, set()):
                    found.append(email)
            if any(any(t in e.split("@")[0] for t in ("career", "job", "recruit", "talent", "hr")) for e in found):
                break
    finally:
        client.close()
    return list(dict.fromkeys(found))


def smtp_ok(email: str) -> tuple[bool, str]:
    ok, detail = verify_mailbox(email)
    if ok:
        return True, "strict-valid"
    return False, detail


def main() -> None:
    companies = load_companies()
    print(f"Companies: {len(companies)}", flush=True)
    sent_e, _sent_c = already_sent()
    _, pk_domains = pk_hq()

    candidates: list[dict[str, str]] = []
    for row in companies:
        domain = resolve_domain(row["company"], row.get("url") or "", row.get("domain") or "")
        if not domain or domain in BLOCKED_DOMAINS or domain in pk_domains or domain.endswith(".pk"):
            continue
        candidates.append({**row, "domain": domain})
    by_d: dict[str, dict[str, str]] = {}
    for row in candidates:
        prev = by_d.get(row["domain"])
        if not prev or int(row["n"]) > int(prev["n"]):
            by_d[row["domain"]] = row
    candidates = sorted(by_d.values(), key=lambda r: -int(r["n"]))
    print(f"With domains: {len(candidates)}", flush=True)

    hunter_enabled = bool(HUNTER_API_KEY)
    hunter_dead = False
    http = httpx.Client(timeout=25.0) if hunter_enabled else None
    rows_out: list[dict[str, str]] = []
    seen_emails: set[str] = set()

    for row in candidates:
        if len(rows_out) >= TARGET:
            break
        domain = row["domain"]
        company = row["company"]
        print(f"\n→ {company} ({domain})", flush=True)

        hit: dict[str, str] | None = None

        # 1) Job posting email
        posted = row.get("posted_email") or ""
        if posted and usable(posted, pk_domains) and posted not in sent_e and posted not in seen_emails:
            ok, tag = smtp_ok(posted)
            if ok:
                hit = {
                    "email": posted,
                    "source": row.get("email_source") or "job posting",
                    "smtp": tag,
                    "first_name": "",
                    "position": "Hiring contact",
                }
                print(f"  posting OK {posted}", flush=True)
            else:
                print(f"  posting fail {posted}: {tag[:60]}", flush=True)

        # 2) Hunter (until credits die)
        if not hit and hunter_enabled and http and not hunter_dead:
            try:
                r = http.get(
                    "https://api.hunter.io/v2/domain-search",
                    params={"domain": domain, "department": "hr", "limit": 10, "api_key": HUNTER_API_KEY},
                )
                if r.status_code == 429:
                    hunter_dead = True
                    print("  Hunter exhausted — scrape/guess only from here", flush=True)
                elif r.status_code == 200:
                    emails = (r.json().get("data") or {}).get("emails") or []
                    for item in emails:
                        value = (item.get("value") or "").lower()
                        pos = (item.get("position") or "").lower()
                        dept = (item.get("department") or "").lower()
                        local = value.split("@")[0] if value else ""
                        interesting = (
                            dept == "hr"
                            or any(t in pos for t in ("recruit", "talent", "hiring", "people", "hr"))
                            or any(t in local for t in ("career", "recruit", "talent", "hiring", "people", "hr", "job"))
                        )
                        if not interesting or not usable(value, pk_domains) or value in sent_e:
                            continue
                        ok, tag = smtp_ok(value)
                        if ok or (tag.lower().find("catch-all") >= 0):
                            # For hunter personal names on catch-all, still allow with hunter-valid
                            smtp_tag = "strict-valid" if ok else "hunter-valid"
                            if not ok and "." not in local:
                                continue
                            hit = {
                                "email": value,
                                "source": f"Hunter.io ({item.get('position') or 'HR'})",
                                "smtp": smtp_tag,
                                "first_name": (item.get("first_name") or "").strip(),
                                "position": (item.get("position") or "Recruiter").strip(),
                            }
                            print(f"  hunter OK {value}", flush=True)
                            break
                time.sleep(0.3)
            except Exception as exc:  # noqa: BLE001
                print(f"  hunter err {exc}", flush=True)

        # 3) SMTP-strict guesses
        if not hit:
            for local in GUESS_LOCALS:
                email = f"{local}@{domain}"
                if email in sent_e or email in seen_emails:
                    continue
                ok, tag = smtp_ok(email)
                if ok:
                    hit = {
                        "email": email,
                        "source": "SMTP-verified hiring alias",
                        "smtp": tag,
                        "first_name": "",
                        "position": local,
                    }
                    print(f"  guess OK {email}", flush=True)
                    break
                if "catch-all" in tag.lower():
                    print(f"  guess catch-all domain — stop guessing", flush=True)
                    break

        # 4) Website scrape
        if not hit:
            found = [e for e in scrape_domain(domain) if usable(e, pk_domains) and e not in sent_e and e not in seen_emails]
            best = pick_hr_email(found) if found else ""
            if best:
                ok, tag = smtp_ok(best)
                if ok:
                    hit = {
                        "email": best,
                        "source": "company website",
                        "smtp": tag,
                        "first_name": "",
                        "position": "Published contact",
                    }
                    print(f"  scrape OK {best}", flush=True)
                else:
                    print(f"  scrape fail {best}: {tag[:60]}", flush=True)
            else:
                print("  none", flush=True)

        if not hit:
            continue

        email = hit["email"]
        seen_emails.add(email)
        arm = "A" if len(rows_out) % 2 == 0 else "B"
        rows_out.append(
            {
                "Company": company,
                "Region": "Remote",
                "City": row.get("location") or "Worldwide remote",
                "Contact Name": hit.get("first_name") or "",
                "HR / Recruiter Email": email,
                "Email Source": hit["source"],
                "Other Emails": "",
                "Domain": domain,
                "Careers / Apply URL": row.get("url") or f"https://{domain}",
                "Sample Role": row.get("title") or "",
                "Location Clause": " (remote)",
                "Letter": f"emailll_ab_{arm.lower()}.txt",
                "SMTP Verification": hit["smtp"],
                "AB Arm": arm,
                "Pakistan Evidence": f"{row['fit']} | {row['location']} | n={row['n']}",
            }
        )
        print(f"  QUEUED [{arm}] {email}", flush=True)

    fields = [
        "Company", "Region", "City", "Contact Name", "HR / Recruiter Email",
        "Email Source", "Other Emails", "Domain", "Careers / Apply URL",
        "Sample Role", "Location Clause", "Letter", "SMTP Verification",
        "AB Arm", "Pakistan Evidence",
    ]
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows_out)
    print(f"\nWrote {len(rows_out)} → {OUT}", flush=True)
    if hunter_dead:
        print("Hunter free tier used up — renew at https://hunter.io/api-keys for named recruiters.", flush=True)


if __name__ == "__main__":
    main()
