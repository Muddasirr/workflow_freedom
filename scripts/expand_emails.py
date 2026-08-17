#!/usr/bin/env python3
"""Scrape new GCC + remote company contacts and merge into emails CSV."""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from job_hunter.directory import (  # noqa: E402
    COMPANY_DIRECTORY,
    CompanyContact,
    merge_contacts,
    scrape_directory_contacts,
)
from job_hunter.excel import write_emails_csv  # noqa: E402

OUT = ROOT / "output" / "emails_2026-08-10.csv"


def load_existing(path: Path) -> list[CompanyContact]:
    if not path.exists():
        return []
    rows: list[CompanyContact] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            emails = [row.get("HR / Recruiter Email") or ""]
            extra = [e.strip() for e in (row.get("Other Emails") or "").split(",") if e.strip()]
            emails = [e for e in [*emails, *extra] if e]
            if not emails:
                continue
            rows.append(
                CompanyContact(
                    name=row.get("Company") or "",
                    domain=row.get("Domain") or "",
                    region=row.get("Region") or "Remote",
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
    print(f"Directory companies: {len(COMPANY_DIRECTORY)}", flush=True)
    existing = load_existing(OUT)
    print(f"Existing unique rows: {len(existing)}", flush=True)
    known_domains = {c.domain.lower() for c in existing if c.domain}
    print("Scraping GCC + remote career pages…", flush=True)
    directory = scrape_directory_contacts(max_workers=20)
    directory = [c for c in directory if c.domain.lower() not in known_domains] + [
        c for c in directory if c.domain.lower() in known_domains and c.emails
    ]
    merged = merge_contacts(directory, existing)
    write_emails_csv(merged, OUT)
    counts: dict[str, int] = {}
    verified = 0
    for c in merged:
        if not c.emails:
            continue
        counts[c.region] = counts.get(c.region, 0) + 1
        if "guess" not in (c.email_source or "").lower():
            verified += 1
    total = sum(counts.values())
    print(f"\nWrote {OUT}")
    print(f"Unique company emails: {total}")
    for region in (
        "Karachi",
        "Pakistan",
        "Qatar",
        "Bahrain",
        "Kuwait",
        "Oman",
        "UAE",
        "KSA",
        "Egypt",
        "MENA",
        "Remote",
    ):
        if counts.get(region):
            print(f"  {region}: {counts[region]}")
    print(f"Verified (not guessed): {verified}")


if __name__ == "__main__":
    main()
