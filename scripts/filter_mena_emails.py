#!/usr/bin/env python3
"""Keep only GCC / MENA / PK product+software contacts; drop global remote giants."""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from job_hunter.directory import COMPANY_DIRECTORY, CompanyContact, scrape_directory_contacts  # noqa: E402
from job_hunter.excel import write_emails_csv  # noqa: E402

OUT = ROOT / "output" / "emails_2026-08-10.csv"

KEEP_REGIONS = {
    "Karachi",
    "Pakistan",
    "Qatar",
    "Bahrain",
    "Kuwait",
    "Oman",
    "UAE",
    "KSA",
    "Egypt",
    "Jordan",
    "Lebanon",
    "MENA",
}

DROP_COMPANIES = {
    "gitlab",
    "automattic",
    "canonical",
    "anthropic",
    "openai",
    "vercel",
    "hugging face",
    "huggingface",
    "toptal",
    "andela",
    "lemon.io",
    "lemon",
    "n8n",
    "stripe",
    "cloudflare",
    "zapier",
    "supabase",
    "hashicorp",
    "elastic",
    "mongodb",
    "datadog",
    "digitalocean",
    "shopify",
    "crossover",
    "remote.com",
    "x-team",
    "arc.dev",
    "epam",
    "globant",
    "bairesdev",
    "temporal",
    "langchain",
    "cohere",
    "together ai",
    "replicate",
    "notion",
    "figma",
    "linear",
    "spotify",
    "binance",
    "consensys",
    "twilio",
    "plaid",
    "ramp",
    "airtable",
    "asana",
    "dropbox",
    "airbnb",
    "databricks",
    "1password",
    "6sense",
    "upstart",
    "mitre media",
    "clickhouse",
    "toast",
    "azumo",
    "cision",
    "deepgram",
    "launchdarkly",
    "varicent",
    "pair team",
    "planet labs",
    "pointclickcare",
    "caylent",
    "coursera",
    "crowdstrike",
    "customer.io",
    "mirantis",
    "phaidra",
    "samsara",
    "cresta",
}


def load_csv(path: Path) -> list[CompanyContact]:
    rows: list[CompanyContact] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            name = (row.get("Company") or "").strip()
            region = (row.get("Region") or "").strip()
            if region not in KEEP_REGIONS:
                continue
            if name.lower() in DROP_COMPANIES:
                continue
            emails = [row.get("HR / Recruiter Email") or ""]
            extra = [e.strip() for e in (row.get("Other Emails") or "").split(",") if e.strip()]
            emails = [e for e in [*emails, *extra] if e]
            if not emails:
                continue
            rows.append(
                CompanyContact(
                    name=name,
                    domain=row.get("Domain") or "",
                    region=region,
                    city=row.get("City") or "",
                    emails=emails,
                    email_source=row.get("Email Source") or "",
                    careers_url=row.get("Careers / Apply URL") or "",
                    apply_url=row.get("Careers / Apply URL") or "",
                    sample_role=row.get("Sample Role") or "",
                )
            )
    return rows


def main() -> None:
    existing = load_csv(OUT)
    have = {c.domain.lower() for c in existing if c.domain}
    new_rows = [row for row in COMPANY_DIRECTORY if row[1].lower() not in have]
    print(f"Keeping {len(existing)} MENA/PK rows; scraping {len(new_rows)} new GCC/MENA startups…", flush=True)

    # Temporarily scrape only missing directory entries
    # scrape only missing directory entries
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from job_hunter.directory import _clean_emails
    from job_hunter.emails import _scrape_contact_emails, guess_generic_emails
    from job_hunter.http import HttpClient

    def one(row):
        name, domain, region, city, known = row
        local = HttpClient()
        try:
            scraped = _scrape_contact_emails(local, domain)
        finally:
            local.close()
        emails = _clean_emails([*known, *scraped], domain)
        source = "company website" if scraped else ("known company contact" if known else "guessed pattern (verify before sending)")
        if not emails:
            emails = guess_generic_emails(domain)[:2]
            source = "guessed pattern (verify before sending)"
        return CompanyContact(name=name, domain=domain, region=region, city=city, emails=emails, email_source=source, careers_url=f"https://{domain}/careers")

    fresh: list[CompanyContact] = []
    with ThreadPoolExecutor(max_workers=16) as pool:
        futs = [pool.submit(one, row) for row in new_rows]
        for fut in as_completed(futs):
            fresh.append(fut.result())

    by_key: dict[str, CompanyContact] = {}
    for c in [*existing, *fresh]:
        key = (c.domain or c.name).lower()
        if c.name.lower() in DROP_COMPANIES or c.region not in KEEP_REGIONS:
            continue
        prev = by_key.get(key)
        if prev is None:
            by_key[key] = c
            continue
        prev.emails = list(dict.fromkeys([*prev.emails, *c.emails]))
    contacts = list(by_key.values())
    order = {k: i for i, k in enumerate(["Karachi", "Pakistan", "Qatar", "Bahrain", "Kuwait", "Oman", "UAE", "KSA", "Egypt", "Jordan", "Lebanon", "MENA"])}
    contacts.sort(key=lambda c: (order.get(c.region, 20), c.name.lower()))
    write_emails_csv(contacts, OUT)
    counts: dict[str, int] = {}
    for c in contacts:
        counts[c.region] = counts.get(c.region, 0) + 1
    print(f"Wrote {OUT}")
    print(f"Unique companies: {len(contacts)}")
    for k, v in sorted(counts.items(), key=lambda kv: order.get(kv[0], 99)):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
