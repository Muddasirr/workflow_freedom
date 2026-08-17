"""Find 0–2 year SWE/AI/product jobs, scrape published emails, send personalized letters."""
from __future__ import annotations

import csv
import sys
from datetime import date
from pathlib import Path

from job_hunter.config import OUTPUT_DIR, ROOT
from job_hunter.emails import (
    HunterClient,
    attach_description_emails,
    enrich_from_websites,
    pick_hr_email,
)
from job_hunter.excel import write_csv, write_workbook
from job_hunter.http import HttpClient
from job_hunter.matcher import is_keepable, score_job
from job_hunter.models import Job
from job_hunter.personalize import location_clause, pick_letter, role_label
from job_hunter.sources import fetch_all

if str(ROOT / "outreach") not in sys.path:
    sys.path.insert(0, str(ROOT / "outreach"))

from smtp_verify import bounced_emails, verify_mailbox  # noqa: E402


APPLY_FIELDS = [
    "Company",
    "Region",
    "City",
    "HR / Recruiter Email",
    "Email Source",
    "Other Emails",
    "Domain",
    "Careers / Apply URL",
    "Sample Role",
    "Location Clause",
    "Letter",
    "Seniority",
    "Experience Fit",
    "Matched Skills",
    "Job Summary",
    "SMTP Verification",
]


def _region_for(job: Job) -> tuple[str, str]:
    fit = (job.location_fit or "").lower()
    loc = (job.location or "").lower()
    if "karachi" in fit or "karachi" in loc:
        return "Karachi", job.location or "Karachi"
    if "pakistan" in fit or "pakistan" in loc:
        return "Pakistan", job.location or "Pakistan"
    if any(k in loc or k in fit for k in ("uae", "dubai", "saudi", "qatar", "kuwait", "bahrain", "oman", "egypt")):
        return "MENA", job.location or "MENA"
    if "europe" in loc or "london" in loc or "berlin" in loc or "amsterdam" in loc:
        return "Europe", job.location or "Europe"
    if "australia" in loc or "sydney" in loc or "melbourne" in loc:
        return "Australia", job.location or "Australia"
    if job.work_mode == "remote" or "remote" in fit or "worldwide" in fit:
        return "Remote", job.location or "Remote"
    return "Remote", job.location or job.location_fit or ""


def collect_jobs(
    *,
    junior_only: bool = True,
    junior_strict: bool = False,
    karachi_only: bool = False,
    pakistan_friendly_only: bool = False,
    include_restricted: bool = False,
) -> list[Job]:
    print("Fetching job boards…", flush=True)
    client = HttpClient()
    hunter = HunterClient()
    try:
        raw = fetch_all(client)
        print(f"Pulled {len(raw)} raw listings. Scoring junior SWE/AI/product roles…", flush=True)
        scored: list[Job] = []
        for job in raw:
            score_job(job)
            attach_description_emails(job)
            if is_keepable(
                job,
                include_restricted=include_restricted,
                karachi_only=karachi_only,
                pakistan_friendly_only=pakistan_friendly_only,
                junior_only=junior_only,
                junior_strict=junior_strict,
            ):
                scored.append(job)
        best: dict[str, Job] = {}
        for job in scored:
            key = job.dedupe_key
            existing = best.get(key)
            if existing is None or job.score > existing.score:
                best[key] = job
        scored = sorted(best.values(), key=lambda j: (-j.score, j.company.lower()))
        print(f"  Matching 0–2 year / junior-friendly roles: {len(scored)}", flush=True)

        if hunter.enabled:
            print("Looking up published HR emails via Hunter.io…", flush=True)
            looked = 0
            for job in scored:
                if job.hr_email and "guess" not in (job.email_source or "").lower():
                    continue
                if looked >= 40:
                    break
                hunter.enrich(job)
                looked += 1
                if "guess" in (job.email_source or "").lower():
                    job.hr_email = ""
                    job.email_source = ""
            print(f"  Hunter lookups used: {looked}", flush=True)

        print(f"Scraping company / careers pages for published emails ({len(scored)} roles)…", flush=True)
        enrich_from_websites(client, scored, allow_guess=False)
        # Never keep guessed careers@ in the apply pipeline.
        for job in scored:
            if "guess" in (job.email_source or "").lower():
                job.hr_email = ""
                job.email_source = ""
            if job.emails and not job.hr_email:
                job.hr_email = pick_hr_email(job.emails)
                job.email_source = job.email_source or "company website"
        return scored
    finally:
        client.close()
        hunter.close()


def jobs_to_apply_rows(jobs: list[Job], *, verify: bool = True, max_verify: int = 40) -> list[dict[str, str]]:
    bounced = bounced_emails()
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    candidates = [j for j in jobs if (j.hr_email or "").strip() and "guess" not in (j.email_source or "").lower()]
    candidates = candidates[: max(max_verify, 1)]
    print(f"Checking {len(candidates)} published hiring emails…", flush=True)
    for job in candidates:
        email = (job.hr_email or "").strip().lower()
        if not email or "@" not in email or email in seen or email in bounced:
            continue
        if "guess" in (job.email_source or "").lower():
            continue
        detail = "skipped probe"
        if verify:
            ok, detail = verify_mailbox(email)
            text = (detail or "").lower()
            published = any(
                k in (job.email_source or "").lower()
                for k in ("job posting", "company website", "hunter", "known")
            )
            probe_blocked = any(h in text for h in ("probe-blocked", "5.7.1", "spamhaus", "timed out", "timeout"))
            if not ok and not (published and probe_blocked):
                print(f"  SKIP {email}  ({job.company})  {detail[:90]}", flush=True)
                continue
            if not ok:
                print(f"  KEEP published Outlook-blocked  {email}  ({job.company})", flush=True)
        seen.add(email)
        region, city = _region_for(job)
        title = (job.title or "").strip()
        if title:
            letter = pick_letter(job)
            letter_name = letter.name
            sample_role = role_label(job)
            loc_clause = location_clause(job)
        else:
            letter_name = ""
            sample_role = ""
            loc_clause = ""
        rows.append(
            {
                "Company": job.company,
                "Region": region,
                "City": city,
                "HR / Recruiter Email": email,
                "Email Source": job.email_source or "job posting",
                "Other Emails": ", ".join(e for e in job.emails if e != email),
                "Domain": job.company_domain or (email.split("@", 1)[-1]),
                "Careers / Apply URL": job.url,
                "Sample Role": sample_role,
                "Location Clause": loc_clause,
                "Letter": letter_name,
                "Seniority": job.seniority,
                "Experience Fit": job.experience_fit,
                "Matched Skills": ", ".join(job.matched_skills),
                "Job Summary": job.excerpt or "",
                "SMTP Verification": (detail or "")[:400],
            }
        )
    return rows


def generic_directory_rows(
    *,
    already_emails: set[str],
    already_companies: set[str],
    verify: bool = True,
    limit: int = 24,
) -> list[dict[str, str]]:
    """Companies we have a published email for, but no matching job opening → generic letter."""
    from job_hunter.directory import COMPANY_DIRECTORY
    from job_hunter.emails import pick_hr_email

    bounced = bounced_emails()
    rows: list[dict[str, str]] = []
    print("Adding companies with no job opening — generic product/AI/Go letters…", flush=True)
    for name, domain, region, city, emails in COMPANY_DIRECTORY:
        if len(rows) >= limit:
            break
        if (name or "").strip().lower() in already_companies:
            continue
        cleaned = [e.strip().lower() for e in emails if e and "@" in e]
        if not cleaned:
            continue
        email = pick_hr_email(cleaned)
        if not email or email in already_emails or email in bounced:
            continue
        if "guess" in email:  # never happens; keep obvious
            continue
        detail = "skipped probe"
        if verify:
            ok, detail = verify_mailbox(email)
            text = (detail or "").lower()
            probe_blocked = any(h in text for h in ("probe-blocked", "5.7.1", "spamhaus", "timed out", "timeout"))
            if not ok and not probe_blocked:
                print(f"  SKIP generic {email}  ({name})  {detail[:90]}", flush=True)
                continue
            if not ok:
                print(f"  KEEP published Outlook-blocked  {email}  ({name})", flush=True)
        already_emails.add(email)
        already_companies.add(name.strip().lower())
        rows.append(
            {
                "Company": name,
                "Region": region,
                "City": city,
                "HR / Recruiter Email": email,
                "Email Source": "known company contact",
                "Other Emails": ", ".join(e for e in cleaned if e != email),
                "Domain": domain,
                "Careers / Apply URL": "",
                "Sample Role": "",
                "Location Clause": "",
                "Letter": "",
                "Seniority": "",
                "Experience Fit": "",
                "Matched Skills": "",
                "Job Summary": "",
                "SMTP Verification": (detail or "")[:400],
            }
        )
    print(f"  Generic fallback companies: {len(rows)}", flush=True)
    return rows


def write_apply_csv(rows: list[dict[str, str]], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=APPLY_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def run_apply(
    *,
    send: bool = False,
    limit: int = 12,
    delay: float = 90.0,
    daily_cap: int = 80,
    junior_strict: bool = False,
    karachi_only: bool = False,
    pakistan_friendly_only: bool = False,
    skip_verify: bool = False,
    no_agent: bool = False,
) -> int:
    jobs = collect_jobs(
        junior_only=True,
        junior_strict=junior_strict,
        karachi_only=karachi_only,
        pakistan_friendly_only=pakistan_friendly_only,
    )
    stamp = date.today().isoformat()
    jobs_xlsx = OUTPUT_DIR / f"jobs_junior_{stamp}.xlsx"
    jobs_csv = OUTPUT_DIR / f"jobs_junior_{stamp}.csv"
    write_workbook(jobs, jobs_xlsx)
    write_csv(jobs, jobs_csv)

    print("SMTP-checking published hiring emails (no guessed careers@)…", flush=True)
    rows = jobs_to_apply_rows(jobs, verify=not skip_verify, max_verify=max(limit * 3, 24))
    seen_emails = {(r.get("HR / Recruiter Email") or "").strip().lower() for r in rows}
    seen_cos = {(r.get("Company") or "").strip().lower() for r in rows}
    rows.extend(
        generic_directory_rows(
            already_emails=seen_emails,
            already_companies=seen_cos,
            verify=not skip_verify,
            limit=max(limit, 12),
        )
    )
    apply_csv = OUTPUT_DIR / f"emails_apply_{stamp}.csv"
    write_apply_csv(rows, apply_csv)
    print()
    print(f"Junior/0–2 jobs: {len(jobs)}")
    print(f"  Excel: {jobs_xlsx}")
    print(f"  Jobs CSV: {jobs_csv}")
    print(f"  Apply CSV (verified emails): {apply_csv}  ({len(rows)} ready)")
    if not rows:
        print("No published, verified hiring emails yet. Re-run later or add HUNTER_API_KEY.")
        return 0

    from send_emails import main as send_main

    argv = [
        "outreach/send_emails.py",
        "--csv",
        str(apply_csv),
        "--limit",
        str(limit),
        "--delay",
        str(delay),
        "--daily-cap",
        str(daily_cap),
        "--skip-guessed",
    ]
    if send:
        argv.append("--send")
    if no_agent:
        argv.append("--no-agent")
    old = sys.argv
    try:
        sys.argv = argv
        return send_main()
    finally:
        sys.argv = old
