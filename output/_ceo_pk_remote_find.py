#!/usr/bin/env python3
"""Find CEO/founder emails for NON-Pakistan companies that post Pakistan-open remote jobs.

Evidence gate: job must be Work Mode=remote AND Pakistan Friendly=Yes
(from scraped job CSVs / live fetch). Pakistan HQ companies are excluded.
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

from job_hunter.config import HUNTER_API_KEY  # noqa: E402
from job_hunter.directory import COMPANY_DIRECTORY  # noqa: E402
from job_hunter.emails import WELL_KNOWN_COMPANY_DOMAINS, resolve_company_domain  # noqa: E402
from job_hunter.models import Job  # noqa: E402
from send_emails import BLOCKED_COMPANIES, BLOCKED_DOMAINS, already_sent  # noqa: E402

OUT = ROOT / "output" / "emails_ceo_pk_remote_2026-08-24.csv"
JOB_CSVS = [
    ROOT / "output" / "jobs_junior_2026-08-20.csv",
    ROOT / "output" / "jobs_junior_2026-08-18.csv",
    ROOT / "output" / "jobs_junior_2026-08-17.csv",
    ROOT / "output" / "jobs_2026-08-10.csv",
]
MAX_HUNTER = 25  # keep free-tier credits

PK_REGIONS = {"Karachi", "Pakistan"}
# WWR often lists "Anywhere" for US-only employers — skip these for CEO outreach.
SKIP_LIKELY_US_ONLY = {
    "coinbase",
    "dropbox",
    "airbnb",
    "reddit",
    "datadog",
    "twilio",
    "gusto, inc.",
    "gusto",
    "doximity",
    "hightouch",
    "nuuly",
    "faire",
    "lattice",
    "reveleer",
}
EXTRA_DOMAINS = {
    "proxify ab": "proxify.io",
    "proxify": "proxify.io",
    "superplane": "superplane.io",
    "wonderdog": "wonderdog.ai",
    "yoko co": "yokoco.com",
    "business web solutions": "bws.com",  # verify later
    "charles technology africa": "charles.tech",
    "welo global": "weloglobal.com",
    "a.team": "a.team",
    "lithic": "lithic.com",
    "huzzle": "huzzle.app",
    "valsoft corporation": "valsoftcorp.com",
    "charisma-tec": "charisma-tec.com",
    "alphorm": "alphorm.com",
    "appodeal": "appodeal.com",
    "base.com": "base.com",
    "zowie": "getzowie.com",
    "yooli": "yooli.com",
    "memberspace": "memberspace.com",
    "hygraph": "hygraph.com",
    "lawnstarter": "lawnstarter.com",
    "stellar ai": "stellar.ai",
    "azumo": "azumo.com",
    "speechify inc": "speechify.com",
    "speechify": "speechify.com",
    "descript": "descript.com",
    "bybit": "bybit.com",
    "redspace": "redspace.com",
    "collibra": "collibra.com",
    "softgic": "softgic.com",
    "trigger.dev": "trigger.dev",
    "clickhouse": "clickhouse.com",
    "customer.io": "customer.io",
    "maptiler": "maptiler.com",
    "sticker mule": "stickermule.com",
    "onthegosystems": "onthegosystems.com",
    "saas.group": "saas.group",
}
LEADER_POS = (
    "ceo",
    "chief executive",
    "founder",
    "co-founder",
    "cofounder",
    "co founder",
    "owner",
    "president",
    "managing director",
)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def pk_hq_maps() -> tuple[set[str], set[str]]:
    names: set[str] = set()
    domains: set[str] = set()
    for name, domain, region, *_rest in COMPANY_DIRECTORY:
        if region in PK_REGIONS:
            names.add(_norm(name))
            domains.add(domain.lower())
    return names, domains


def load_pk_remote_companies() -> dict[str, dict[str, str]]:
    """company_key -> evidence row (must prove remote + Pakistan-friendly)."""
    pk_names, _pk_domains = pk_hq_maps()
    out: dict[str, dict[str, str]] = {}
    for path in JOB_CSVS:
        if not path.exists():
            continue
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if (row.get("Pakistan Friendly") or "").strip() != "Yes":
                    continue
                if (row.get("Work Mode") or "").strip().lower() != "remote":
                    continue
                fit = (row.get("Location Fit") or "").strip().lower()
                # Require worldwide / timezone / APAC remote — not PK on-site.
                if "on-site" in fit or "onsite" in fit:
                    continue
                if not any(
                    t in fit
                    for t in ("worldwide", "timezone", "apac", "pakistan remote", "remote")
                ):
                    # Location Fit should still say Worldwide remote etc.
                    if "remote" not in fit and "anywhere" not in (row.get("Location") or "").lower():
                        continue
                company = (row.get("Company") or "").strip()
                if not company:
                    continue
                key = _norm(company)
                if key in pk_names or any(b == key or b in key for b in BLOCKED_COMPANIES):
                    continue
                if key in SKIP_LIKELY_US_ONLY:
                    continue
                # Prefer stronger evidence (worldwide) when merging.
                loc = (row.get("Location") or "").strip()
                title = (row.get("Title") or "").strip()
                url = (
                    row.get("Apply URL")
                    or row.get("URL")
                    or row.get("Job URL")
                    or row.get("Link")
                    or ""
                ).strip()
                prev = out.get(key)
                score = 2 if "worldwide" in fit else 1
                if prev and int(prev.get("_score", "0")) >= score:
                    prev["n"] = str(int(prev.get("n") or "0") + 1)
                    continue
                out[key] = {
                    "company": company,
                    "fit": row.get("Location Fit") or "",
                    "location": loc,
                    "title": title,
                    "url": url,
                    "source_file": path.name,
                    "n": str(int(prev.get("n") or "0") + 1) if prev else "1",
                    "_score": str(score),
                }
    for row in out.values():
        row.pop("_score", None)
    return out


def resolve_domain(company: str, url: str = "", client: httpx.Client | None = None, api_key: str = "") -> str:
    key = _norm(company)
    if key in EXTRA_DOMAINS:
        return EXTRA_DOMAINS[key]
    job = Job(source="ceo-find", source_id="", title="", company=company, url=url)
    domain = resolve_company_domain(job)
    if domain and "weworkremotely" not in domain and "jobicy" not in domain and "remotive" not in domain:
        return domain
    if key in WELL_KNOWN_COMPANY_DOMAINS:
        return WELL_KNOWN_COMPANY_DOMAINS[key]
    for listed, dom, region, *_rest in COMPANY_DIRECTORY:
        if region in PK_REGIONS:
            continue
        if _norm(listed) == key:
            return dom.lower()
    # Last resort disabled by default — burns Hunter credits.
    # Pass allow_hunter_domain=True only for a small high-priority set.
    if client and api_key and False:
        try:
            response = client.get(
                "https://api.hunter.io/v2/domain-search",
                params={"company": company, "limit": 1, "api_key": api_key},
            )
            if response.status_code == 200:
                domain = ((response.json().get("data") or {}).get("domain") or "").lower()
                time.sleep(0.35)
                if domain:
                    return domain
        except Exception:
            pass
    return ""


def leader_score(item: dict) -> tuple[int, int]:
    pos = (item.get("position") or "").lower()
    seniority = (item.get("seniority") or "").lower()
    local = (item.get("value") or "").split("@", 1)[0].lower()
    score = 0
    # Strict: CEO / founder only (not random VPs).
    if any(t in pos for t in ("ceo", "chief executive")):
        score += 100
    if any(t in pos for t in ("founder", "co-founder", "cofounder", "co founder")):
        score += 90
    if local in {"ceo", "founder", "founders", "cofounder"}:
        score += 80
    if any(t in pos for t in ("owner", "managing director")):
        score += 60
    if seniority == "executive" and score > 0:
        score += 20
    # Explicitly reject communications / sales / HR VPs even if executive seniority.
    if any(
        bad in pos
        for bad in (
            "communications",
            "marketing",
            "deal desk",
            "revenue",
            "sales",
            "people",
            "recruit",
            "talent",
            "hr ",
            "human resources",
            "counsel",
            "legal",
            "finance",
            "accounting",
        )
    ):
        score = 0
    conf = int(item.get("confidence") or 0)
    return (score, conf)


def hunter_find_leader(client: httpx.Client, domain: str, api_key: str) -> dict | None:
    """One domain-search (executive first), pick best CEO/founder hit."""
    for params in (
        {"domain": domain, "seniority": "executive", "limit": 10, "api_key": api_key},
        {"domain": domain, "department": "executive", "limit": 10, "api_key": api_key},
        {"domain": domain, "limit": 10, "api_key": api_key},
    ):
        try:
            response = client.get("https://api.hunter.io/v2/domain-search", params=params)
            if response.status_code == 429:
                time.sleep(2)
                return None
            response.raise_for_status()
            emails = (response.json().get("data") or {}).get("emails") or []
        except Exception as exc:  # noqa: BLE001
            print(f"  hunter error {domain}: {exc}")
            return None
        time.sleep(0.4)
        ranked = sorted(emails, key=leader_score, reverse=True)
        for item in ranked:
            value = (item.get("value") or "").lower()
            if not value or "@" not in value:
                continue
            sc, conf = leader_score(item)
            if sc < 60:
                continue
            first = (item.get("first_name") or "").strip()
            pos = (item.get("position") or "").strip()
            return {
                "email": value,
                "first_name": first,
                "position": pos,
                "confidence": str(item.get("confidence") or ""),
                "verification": "hunter-valid" if conf >= 70 else f"hunter-conf-{conf}",
                "filter": str(params.get("seniority") or params.get("department") or "all"),
            }
        # If executive filter returned nothing useful, try next filter.
        if params.get("seniority") or params.get("department"):
            continue
        break
    return None


def hunter_verify(client: httpx.Client, email: str, api_key: str) -> str:
    try:
        response = client.get(
            "https://api.hunter.io/v2/email-verifier",
            params={"email": email, "api_key": api_key},
        )
        if response.status_code != 200:
            return "hunter-unverified"
        status = ((response.json().get("data") or {}).get("status") or "").lower()
        time.sleep(0.35)
        if status == "valid":
            return "hunter-valid"
        if status in {"accept_all", "webmail"}:
            return f"hunter-{status}"
        return f"hunter-{status or 'unknown'}"
    except Exception:  # noqa: BLE001
        return "hunter-unverified"


def main() -> None:
    if not HUNTER_API_KEY:
        raise SystemExit("HUNTER_API_KEY missing in .env")

    companies = load_pk_remote_companies()
    print(f"Evidence pool (PK-friendly remote, non-PK HQ): {len(companies)}")

    sent_emails, sent_companies = already_sent()
    _, pk_domains = pk_hq_maps()

    # Resolve domains + rank by evidence count.
    candidates: list[dict[str, str]] = []
    client = httpx.Client(timeout=30.0)
    for row in sorted(companies.values(), key=lambda r: -int(r.get("n") or "1")):
        domain = resolve_domain(row["company"], row.get("url") or "", client=client, api_key=HUNTER_API_KEY)
        if not domain or domain in BLOCKED_DOMAINS or domain in pk_domains:
            continue
        if domain.endswith(".pk"):
            continue
        if any(domain == d or domain.endswith("." + d) for d in BLOCKED_DOMAINS):
            continue
        candidates.append({**row, "domain": domain})

    # Dedupe by domain (keep highest evidence count).
    by_domain: dict[str, dict[str, str]] = {}
    for row in candidates:
        prev = by_domain.get(row["domain"])
        if not prev or int(row.get("n") or "0") > int(prev.get("n") or "0"):
            by_domain[row["domain"]] = row
    candidates = sorted(by_domain.values(), key=lambda r: -int(r.get("n") or "1"))

    print(f"With resolvable domains: {len(candidates)}")
    rows_out: list[dict[str, str]] = []
    used = 0

    # Skip domains already in a prior CEO CSV this session if present.
    already_ceo: set[str] = set()
    if OUT.exists():
        with OUT.open(encoding="utf-8-sig", newline="") as handle:
            for old in csv.DictReader(handle):
                already_ceo.add((old.get("HR / Recruiter Email") or "").lower())
                already_ceo.add((old.get("Domain") or "").lower())

    for row in candidates:
        if used >= MAX_HUNTER:
            break
        domain = row["domain"]
        company = row["company"]
        if domain in already_ceo:
            print(f"  SKIP domain already in CEO CSV ({domain})")
            continue
        print(f"[{used + 1}/{MAX_HUNTER}] {company} ({domain}) — {row['fit']} / {row['location']}")
        used += 1
        hit = hunter_find_leader(client, domain, HUNTER_API_KEY)
        if not hit:
            print("  no CEO/founder email")
            continue
        email = hit["email"]
        if email in sent_emails or email in already_ceo:
            print(f"  SKIP already sent {email}")
            continue
        if email.split("@", 1)[1] in pk_domains or email.endswith(".pk"):
            print(f"  SKIP PK domain email {email}")
            continue
        verify = hunter_verify(client, email, HUNTER_API_KEY)
        if verify not in {"hunter-valid", "hunter-accept_all"}:
            print(f"  SKIP verify={verify} {email}")
            continue
        smtp_tag = "hunter-valid"
        print(f"  OK {email}  {hit['first_name']} | {hit['position']} | {verify}")
        rows_out.append(
            {
                "Company": company,
                "Region": "Remote",
                "City": row.get("location") or "Worldwide remote",
                "Contact Name": hit["first_name"],
                "HR / Recruiter Email": email,
                "Email Source": f"Hunter.io leadership ({hit['position'] or hit['filter']})",
                "Other Emails": "",
                "Domain": domain,
                "Careers / Apply URL": row.get("url") or f"https://{domain}",
                "Sample Role": row.get("title") or "",
                "Location Clause": " (remote)",
                "Letter": "emailll.txt",
                "SMTP Verification": smtp_tag,
                "Pakistan Evidence": f"{row['fit']} | {row['location']} | n={row['n']} | {row['source_file']}",
            }
        )

    fields = [
        "Company",
        "Region",
        "City",
        "Contact Name",
        "HR / Recruiter Email",
        "Email Source",
        "Other Emails",
        "Domain",
        "Careers / Apply URL",
        "Sample Role",
        "Location Clause",
        "Letter",
        "SMTP Verification",
        "Pakistan Evidence",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows_out)
    print(f"\nWrote {len(rows_out)} CEO/leadership rows → {OUT}")
    print(f"Hunter domain searches used this run: {used}")


if __name__ == "__main__":
    main()
