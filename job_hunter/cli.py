from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from job_hunter.config import HUNTER_API_KEY, OUTPUT_DIR
from job_hunter.directory import (
    contacts_from_csv,
    contacts_from_jobs,
    merge_contacts,
    scrape_directory_contacts,
)
from job_hunter.emails import (
    HunterClient,
    attach_description_emails,
    enrich_from_websites,
    fallback_guess,
)
from job_hunter.excel import write_csv, write_emails_csv, write_workbook
from job_hunter.http import HttpClient
from job_hunter.matcher import is_keepable, score_job
from job_hunter.models import Job
from job_hunter.sources import fetch_all


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Find 0–2 year software / AI / product engineer jobs, scrape published hiring emails, and optionally send a personalized letter + resume."
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=OUTPUT_DIR / f"jobs_{date.today().isoformat()}.xlsx",
        help="Excel output path (CSV is written next to it)",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help="CSV output path (default: same name as --out with .csv)",
    )
    parser.add_argument(
        "--exclude-restricted",
        action="store_true",
        help="Drop remote jobs that look US/EU-only.",
    )
    parser.add_argument(
        "--include-restricted",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--pakistan-friendly-only",
        action="store_true",
        help="Only keep worldwide / Pakistan / Karachi-friendly roles.",
    )
    parser.add_argument(
        "--karachi-only",
        action="store_true",
        help="Only keep Karachi listings.",
    )
    parser.add_argument(
        "--max-hunter",
        type=int,
        default=40,
        help="Max companies to look up via Hunter.io (saves free credits).",
    )
    parser.add_argument(
        "--skip-emails",
        action="store_true",
        help="Do not call Hunter.io even if HUNTER_API_KEY is set.",
    )
    parser.add_argument(
        "--emails-only",
        action="store_true",
        help="Only rebuild the company email CSVs (skip job boards).",
    )
    parser.add_argument(
        "--pk-only",
        action="store_true",
        help="With --emails-only: scrape only Karachi / Pakistan companies.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Find 0–2 year SWE/AI/product jobs, scrape published emails, write apply CSV (add --send to mail).",
    )
    parser.add_argument(
        "--junior",
        action="store_true",
        help="Keep junior / 0–2 year / unspecified-year roles; drop senior and 3+ year postings.",
    )
    parser.add_argument(
        "--junior-strict",
        action="store_true",
        help="Only keep postings that explicitly say junior / entry / 0–2 years.",
    )
    parser.add_argument("--send", action="store_true", help="With --apply: actually send personalized emails.")
    parser.add_argument("--limit", type=int, default=12, help="With --apply --send: max emails this run.")
    parser.add_argument("--delay", type=float, default=90.0, help="With --apply --send: seconds between emails.")
    parser.add_argument("--daily-cap", type=int, default=80, help="With --apply --send: max sends per UTC day.")
    parser.add_argument(
        "--graph",
        action="store_true",
        help="Run the LangGraph apply agent (job → email → SMTP → letter). Add --send to mail.",
    )
    parser.add_argument(
        "--no-agent",
        action="store_true",
        help="Skip Cursor agent letters; use the 4 generic templates.",
    )
    return parser.parse_args()


def dedupe(jobs: list[Job]) -> list[Job]:
    best: dict[str, Job] = {}
    for job in jobs:
        key = job.dedupe_key
        existing = best.get(key)
        if existing is None or job.score > existing.score or (job.score == existing.score and len(job.description) > len(existing.description)):
            best[key] = job
    return list(best.values())


def _print_email_stats(contacts, emails_csv: Path) -> None:
    verified = sum(1 for c in contacts if c.emails and "guess" not in (c.email_source or "").lower())
    gcc_mena = {"MENA", "UAE", "KSA", "Qatar", "Bahrain", "Kuwait", "Oman", "Egypt", "Jordan", "Lebanon"}
    asia = {"Singapore", "Malaysia"}
    print(f"  Emails CSV (unique companies): {emails_csv}")
    verified_csv = emails_csv.with_name(emails_csv.stem.replace("emails", "emails_verified") + emails_csv.suffix)
    print(f"  Verified-only CSV (use this to send): {verified_csv}")
    print(f"  Unique company emails: {sum(1 for c in contacts if c.emails)}")
    print(f"    Karachi:  {sum(1 for c in contacts if c.region == 'Karachi' and c.emails)}")
    print(f"    Pakistan: {sum(1 for c in contacts if c.region == 'Pakistan' and c.emails)}")
    print(f"    GCC/MENA: {sum(1 for c in contacts if c.region in gcc_mena and c.emails)}")
    print(f"    SG/MY:    {sum(1 for c in contacts if c.region in asia and c.emails)}")
    print(f"    Europe:   {sum(1 for c in contacts if c.region == 'Europe' and c.emails)}")
    print(f"    Australia:{sum(1 for c in contacts if c.region == 'Australia' and c.emails)}")
    print(f"    Remote:   {sum(1 for c in contacts if c.region == 'Remote' and c.emails)}")
    print(f"  Verified (not guessed): {verified}")


def main() -> int:
    args = parse_args()
    if args.emails_only:
        regions = {"Karachi", "Pakistan"} if args.pk_only else None
        label = "Pakistan / Karachi" if args.pk_only else "all regions"
        print(f"Scraping {label} company sites for published HR emails…", flush=True)
        directory = scrape_directory_contacts(regions=regions)
        existing = contacts_from_csv(OUTPUT_DIR / f"emails_{date.today().isoformat()}.csv")
        # Also merge yesterday's file if present so we don't lose Europe etc.
        for extra in OUTPUT_DIR.glob("emails_*.csv"):
            if "verified" in extra.name:
                continue
            if extra.name.startswith("emails_") and extra != OUTPUT_DIR / f"emails_{date.today().isoformat()}.csv":
                existing = merge_contacts(existing, contacts_from_csv(extra))
        contacts = merge_contacts(directory, existing)
        csv_path = args.csv or OUTPUT_DIR / f"emails_{date.today().isoformat()}.csv"
        write_emails_csv(contacts, csv_path)
        print()
        _print_email_stats(contacts, csv_path)
        return 0

    if args.graph:
        from job_hunter.graph import run_apply_graph

        run_apply_graph(
            send=args.send,
            limit=args.limit,
            delay=args.delay,
            daily_cap=args.daily_cap,
            no_agent=args.no_agent,
        )
        return 0

    if args.apply:
        from job_hunter.apply import run_apply

        return run_apply(
            send=args.send,
            limit=args.limit,
            delay=args.delay,
            daily_cap=args.daily_cap,
            junior_strict=args.junior_strict,
            karachi_only=args.karachi_only,
            pakistan_friendly_only=args.pakistan_friendly_only,
            no_agent=args.no_agent,
        )

    print("Fetching job boards…", flush=True)
    client = HttpClient()
    hunter = HunterClient()
    try:
        raw = fetch_all(client)
        print(f"Pulled {len(raw)} raw listings. Scoring…", flush=True)
        scored: list[Job] = []
        for job in raw:
            score_job(job)
            attach_description_emails(job)
            if is_keepable(
                job,
                include_restricted=args.include_restricted or not args.exclude_restricted,
                karachi_only=args.karachi_only,
                pakistan_friendly_only=args.pakistan_friendly_only,
                junior_only=args.junior or args.junior_strict,
                junior_strict=args.junior_strict,
            ):
                scored.append(job)
        scored = dedupe(scored)
        scored.sort(key=lambda j: (-j.score, j.company.lower()))

        if hunter.enabled and not args.skip_emails:
            print(f"Looking up HR emails via Hunter.io (up to {args.max_hunter} companies)…", flush=True)
            company_emails: dict[str, tuple[str, list[str], str, str]] = {}
            looked_up = 0
            for job in scored:
                company_key = job.company.strip().lower()
                if job.hr_email:
                    company_emails.setdefault(
                        company_key,
                        (job.hr_email, job.emails, job.email_source, job.company_domain),
                    )
                    continue
                cached = company_emails.get(company_key)
                if cached:
                    job.hr_email, job.emails, job.email_source, domain = cached
                    job.company_domain = job.company_domain or domain
                    continue
                if looked_up >= args.max_hunter:
                    fallback_guess(job)
                    continue
                hunter.enrich(job)
                looked_up += 1
                if not job.hr_email:
                    fallback_guess(job)
                if job.hr_email:
                    company_emails[company_key] = (
                        job.hr_email,
                        job.emails,
                        job.email_source,
                        job.company_domain,
                    )
            print(f"  Hunter lookups used: {looked_up}", flush=True)
        else:
            if not HUNTER_API_KEY:
                print("No HUNTER_API_KEY set — scraping company sites + guessed careers@ patterns.", flush=True)
            for job in scored:
                fallback_guess(job)

        print(f"Scraping company websites + apply pages for emails ({len(scored)} roles)…", flush=True)
        enrich_from_websites(client, scored)

        print("Building Karachi / Pakistan / MENA / Europe company email directory…", flush=True)
        directory = scrape_directory_contacts()
        contacts = merge_contacts(directory, contacts_from_jobs(scored))

        xlsx_path = write_workbook(scored, args.out)
        csv_path = args.csv or args.out.with_suffix(".csv")
        write_csv(scored, csv_path)
        emails_csv = csv_path.with_name(
            csv_path.stem.replace("jobs", "emails") if "jobs" in csv_path.stem else csv_path.stem + "_emails"
        ).with_suffix(".csv")
        if emails_csv == csv_path:
            emails_csv = csv_path.with_name("emails_" + csv_path.name)
        write_emails_csv(contacts, emails_csv)
        pk_yes = sum(1 for j in scored if j.pakistan_friendly == "Yes")
        print()
        print(f"Saved {len(scored)} matching jobs")
        print(f"  Excel: {xlsx_path}")
        print(f"  CSV:   {csv_path}")
        _print_email_stats(contacts, emails_csv)
        print(f"  Pakistan-friendly jobs: {pk_yes}")
        print("Use the verified CSV for outreach — guessed addresses are not sent.")
        return 0
    finally:
        client.close()
        hunter.close()


if __name__ == "__main__":
    raise SystemExit(main())
