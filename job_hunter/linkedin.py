"""Scrape published hiring emails from LinkedIn using a throwaway login.

Set in .env (do not commit):
  LINKEDIN_EMAIL=...
  LINKEDIN_PASSWORD=...
Optional and more stable than password login:
  LINKEDIN_LI_AT=...   # browser cookie named li_at

This only extracts emails that already appear on posts / contact sections.
It does not guess mailboxes.
"""
from __future__ import annotations

import argparse
import csv
import os
import random
import re
import time
from datetime import date
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

from job_hunter.config import OUTPUT_DIR, ROOT
from job_hunter.textutil import extract_emails

load_dotenv(ROOT / ".env")

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
SKIP_LOCAL = {
    "noreply",
    "no-reply",
    "donotreply",
    "privacy",
    "legal",
    "unsubscribe",
    "support",
    "press",
    "media",
}
HRISH = ("hr", "career", "job", "recruit", "talent", "people", "hiring", "join")
SEARCHES = (
    'Karachi ("send your CV" OR "send your resume" OR "apply at") (hr@ OR careers@ OR jobs@) software',
    'Karachi hiring software engineer (hr@ OR careers@ OR jobs@)',
    '"Karachi" "software house" (hr@ OR jobs@ OR careers@)',
    'Karachi "Talent Acquisition" (hr@ OR careers@)',
)


def _pause(a: float = 1.4, b: float = 3.2) -> None:
    time.sleep(random.uniform(a, b))


def _clean_email(raw: str) -> str:
    email = raw.strip().strip(".,;:()[]<>").lower()
    if email.endswith("."):
        email = email[:-1]
    return email


def _keep_email(email: str) -> bool:
    if "@" not in email:
        return False
    local, _, domain = email.partition("@")
    if local in SKIP_LOCAL:
        return False
    if domain.endswith(("linkedin.com", "sentry.io", "example.com", "email.com")):
        return False
    if "lnkd.in" in domain:
        return False
    return True


def _company_from_domain(domain: str) -> str:
    host = domain.split("@")[-1] if "@" in domain else domain
    host = host.lower().removeprefix("www.")
    base = host.split(".")[0]
    return base.replace("-", " ").title()


def _need_creds() -> tuple[str, str, str]:
    email = os.getenv("LINKEDIN_EMAIL", "").strip()
    password = os.getenv("LINKEDIN_PASSWORD", "").strip()
    li_at = os.getenv("LINKEDIN_LI_AT", "").strip()
    if not li_at and not (email and password):
        raise SystemExit(
            "No LinkedIn login in .env. Add LINKEDIN_EMAIL + LINKEDIN_PASSWORD "
            "for the throwaway account, or LINKEDIN_LI_AT (cookie from a logged-in browser)."
        )
    return email, password, li_at


def _launch_browser():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit("Install Playwright first: pip install playwright && playwright install chromium") from exc
    return sync_playwright()


def _login(page, email: str, password: str, li_at: str) -> None:
    if li_at:
        page.context.add_cookies(
            [
                {
                    "name": "li_at",
                    "value": li_at,
                    "domain": ".linkedin.com",
                    "path": "/",
                    "httpOnly": True,
                    "secure": True,
                }
            ]
        )
        page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=60000)
        _pause(2.0, 4.0)
        if "login" in page.url or "checkpoint" in page.url:
            raise SystemExit("LINKEDIN_LI_AT cookie was rejected. Log in once in Chrome, copy li_at, try again.")
        return

    page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=60000)
    page.fill("#username", email)
    _pause(0.4, 0.9)
    page.fill("#password", password)
    _pause(0.3, 0.8)
    page.click('button[type="submit"]')
    page.wait_for_timeout(4000)
    if "checkpoint" in page.url or "challenge" in page.url:
        raise SystemExit(
            "LinkedIn asked for extra verification on this throwaway. "
            "Finish it in a real browser, then put the li_at cookie in .env."
        )
    if "login" in page.url:
        raise SystemExit("LinkedIn login failed. Check LINKEDIN_EMAIL / LINKEDIN_PASSWORD.")


def _collect_from_text(text: str, source: str, hits: list[dict[str, str]]) -> None:
    seen = {(h["email"], h["source"]) for h in hits}
    for raw in EMAIL_RE.findall(text or ""):
        email = _clean_email(raw)
        if not _keep_email(email) or (email, source) in seen:
            continue
        hits.append(
            {
                "email": email,
                "company": _company_from_domain(email),
                "source": source,
                "hrish": "yes" if any(tok in email.split("@", 1)[0] for tok in HRISH) else "no",
            }
        )
        seen.add((email, source))


def scrape_linkedin(limit: int = 40, headless: bool = True) -> list[dict[str, str]]:
    email, password, li_at = _need_creds()
    hits: list[dict[str, str]] = []
    with _launch_browser() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            viewport={"width": 1365, "height": 900},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        _login(page, email, password, li_at)
        print("LinkedIn session is up. Searching Karachi hiring posts…", flush=True)

        for query in SEARCHES:
            url = (
                "https://www.linkedin.com/search/results/content/"
                f"?keywords={quote_plus(query)}&origin=GLOBAL_SEARCH_HEADER"
            )
            print(f"  search: {query}", flush=True)
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            _pause(2.5, 4.5)
            for _ in range(6):
                page.mouse.wheel(0, 2400)
                _pause(0.8, 1.6)
            _collect_from_text(page.inner_text("body"), f"linkedin search: {query}", hits)
            if len({h['email'] for h in hits}) >= limit:
                break

        # People search as a second pass: open contact-info overlays when present.
        people_url = (
            "https://www.linkedin.com/search/results/people/"
            "?keywords=" + quote_plus("HR OR Recruiter OR \"Talent Acquisition\" Karachi software")
            + "&origin=GLOBAL_SEARCH_HEADER"
        )
        print("  people search: Karachi HR / recruiters", flush=True)
        page.goto(people_url, wait_until="domcontentloaded", timeout=60000)
        _pause(2.5, 4.5)
        for _ in range(4):
            page.mouse.wheel(0, 2200)
            _pause(0.7, 1.4)
        profile_links = []
        for href in page.eval_on_selector_all(
            "a[href*='/in/']",
            "els => els.map(e => e.href).filter(Boolean)",
        ):
            if "/in/" in href and href not in profile_links:
                profile_links.append(href.split("?")[0])
        for href in profile_links[: min(12, limit)]:
            try:
                page.goto(href, wait_until="domcontentloaded", timeout=45000)
                _pause(1.6, 3.0)
                _collect_from_text(page.inner_text("body"), href, hits)
                contact = href.rstrip("/") + "/overlay/contact-info/"
                page.goto(contact, wait_until="domcontentloaded", timeout=30000)
                _pause(1.0, 2.0)
                _collect_from_text(page.inner_text("body"), contact, hits)
            except Exception as exc:
                print(f"  skip profile {href}: {exc}", flush=True)
            if len({h['email'] for h in hits}) >= limit:
                break
        browser.close()

    uniq: dict[str, dict[str, str]] = {}
    for hit in hits:
        uniq.setdefault(hit["email"], hit)
    return list(uniq.values())[:limit]


def write_csv(rows: list[dict[str, str]], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
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
        "SMTP Verification",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            domain = row["email"].split("@", 1)[1]
            writer.writerow(
                {
                    "Company": row["company"],
                    "Region": "Karachi",
                    "City": "Karachi",
                    "HR / Recruiter Email": row["email"],
                    "Email Source": row["source"],
                    "Other Emails": "",
                    "Domain": domain,
                    "Careers / Apply URL": row["source"] if row["source"].startswith("http") else "",
                    "Sample Role": "",
                    "Location Clause": "Karachi",
                    "Letter": "",
                    "SMTP Verification": "",
                }
            )
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape published Karachi HR emails from LinkedIn.")
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--headed", action="store_true", help="Show the browser (useful for first login).")
    parser.add_argument(
        "--out",
        type=Path,
        default=OUTPUT_DIR / f"emails_linkedin_khi_{date.today().isoformat()}.csv",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = scrape_linkedin(limit=args.limit, headless=not args.headed)
    print(f"Published emails found: {len(rows)}", flush=True)
    for row in rows:
        print(f"  {row['email']}  {row['company']}  [{row['hrish']}]", flush=True)
    if rows:
        write_csv(rows, args.out)
        print(f"Wrote {args.out}", flush=True)
    else:
        print("No published emails visible on the scraped LinkedIn pages.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
