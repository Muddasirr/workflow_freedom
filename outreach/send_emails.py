#!/usr/bin/env python3
"""Send the outreach letter + resume via Gmail. Dry-run by default.

Auth (pick one):
  1. App Password in .env as GMAIL_APP_PASSWORD  (needs 2-Step Verification on)
  2. Gmail OAuth: put outreach/credentials.json then run --auth
"""
from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import random
import smtplib
import ssl
import sys
import time
from datetime import datetime, timezone
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
OUTREACH_DIR = Path(__file__).resolve().parent
if str(OUTREACH_DIR) not in sys.path:
    sys.path.insert(0, str(OUTREACH_DIR))
load_dotenv(ROOT / ".env")

from smtp_verify import bounced_emails, mark_bounce, smtp_detail_is_unverified, verify_mailbox  # noqa: E402

DEFAULT_CSV = ROOT / "output" / "emails_2026-08-11.csv"
DEFAULT_LETTER = ROOT / "emailll_proof.txt"
# Round-robin order: 1st send → product, 2nd → AI/n8n, 3rd → Go, 4th → product, …
# Round-robin: Reddit-style short letters (proof → frontend → AI agent → backend).
DEFAULT_LETTER_VARIANTS = (
    ROOT / "emailll_proof.txt",
    ROOT / "emailll_frontend.txt",
    ROOT / "emailll_agent.txt",
    ROOT / "emailll_backend.txt",
)
DEFAULT_RESUME = ROOT / "Muhammad_Muddasir_Resume.pdf"
SENT_LOG = ROOT / "outreach" / "sent_log.csv"
SENT_LOG_FIELDS = ["sent_at", "company", "email", "status", "error", "letter", "ab_arm", "subject"]
LOCK_FILE = ROOT / "outreach" / ".send.lock"
OAUTH_CREDS = ROOT / "outreach" / "credentials.json"
OAUTH_TOKEN = ROOT / "outreach" / "token.json"
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
FROM_EMAIL = os.getenv("GMAIL_ADDRESS", "muddasirrizwan9@gmail.com").strip()
APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "").strip()

SUBJECT_ROLE = "Software Engineer"
SUBJECT_WITH_NAME = f"{SUBJECT_ROLE} - Muhammad Muddasir"
SUBJECT_WITH_RESUME = f"{SUBJECT_ROLE} - Resume"
SUBJECT_STATE = OUTREACH_DIR / "subject_state.json"
SUBJECT_NAME_LIMIT = 20
AB_STATE = OUTREACH_DIR / "ab_state.json"
BAN_HINTS = (
    "daily sending quota",
    "user sending quota",
    "try again later",
    "421",
    "please log in",
    "unusual activity",
    "temporarily blocked",
    "rate limit",
    "authentication failed",
    "username and password not accepted",
)
SKIP_LOCAL = (
    "info-xx",
    "accommodations",
    "noreply",
    "no-reply",
    "donotreply",
    "pr",
    "press",
    "media",
    "investors",
    "investor",
    "ir",
    "investor_relations",
    "accessibility",
    "website",
    "webmaster",
    "legal",
    "privacy",
    "guest",
    "abuse",
    "block",
    "spam",
    "postmaster",
    "partners",
    "partner",
    "security",
    "noc",
    "complaints",
    "billing",
    "customer",
    "customer.care",
    "customercare",
    "pharmacy",
    "support",
    "help",
    "sales",
    "inquiry",
    "enquiry",
    "bd",
)
BLOCKED_COMPANIES = {
    "codet",
    "codet.ai",
    "cloudflare",
    "airtable",
    "launchdarkly",
    "gitlab",
    "anthropic",
    "openai",
    "vercel",
    "hugging face",
    "huggingface",
    "toptal",
    "andela",
    "lemon.io",
    "n8n",
    "stripe",
    "automattic",
    "canonical",
}
BLOCKED_DOMAINS = {
    "codet.ai",
    "codet.com",
    "hf.co",
    "huggingface.co",
    "n8n.io",
}
SAFE_LOCAL = {
    "hr",
    "careers",
    "career",
    "jobs",
    "job",
    "cv",
    "resume",
    "resumes",
    "founders",
    "founder",
    "ceo",
    "cto",
    "coo",
    "cso",
    "recruiting",
    "recruitment",
    "talent",
    "people",
    "people.ops",
    "peopleops",
    "hiring",
    "join",
    "apply",
}
# Weak aliases often exist as web text but not as real mailboxes.
WEAK_LOCAL = {
    "hello",
    "hi",
    "contact",
    "info",
    "team",
    "work",
    "opportunities",
    "services",
    "kontakt",
}
TRUSTED_SOURCES = {
    "known company contact",
    "known + company website",
    "hunter.io",
}


def load_letter(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip() + "\n"


def resolve_letter_pool(*, letter: Path, letters_dir: Path | None, single_only: bool) -> list[Path]:
    """Letter templates in fixed order for round-robin (product → AI → Go)."""
    if single_only:
        return [letter]
    pool: list[Path] = []
    if letters_dir is not None:
        # Prefer known names in rotation order, then any other emailll*.txt.
        known = [
            letters_dir / name
            for name in (
                "emailll_proof.txt",
                "emailll_frontend.txt",
                "emailll_agent.txt",
                "emailll_backend.txt",
            )
        ]
        pool = [p for p in known if p.is_file()]
        extras = sorted(
            p for p in letters_dir.glob("emailll*.txt") if p.is_file() and p not in pool
        )
        pool.extend(extras)
    if not pool:
        pool = [p for p in DEFAULT_LETTER_VARIANTS if p.is_file()]
    if letter.is_file() and letter not in pool and single_only is False:
        # Explicit --letter only joins rotation if it's an extra file outside defaults.
        if letter.name not in {p.name for p in pool}:
            pool.append(letter)
    if not pool:
        raise SystemExit(f"No letter templates found (tried {letter} and defaults).")
    return pool


def pick_letter(pool: list[Path], index: int) -> Path:
    """Round-robin: 1st recipient → pool[0], 2nd → pool[1], … then wrap."""
    return pool[(index - 1) % len(pool)]


def load_recipients(path: Path, *, skip_guessed: bool) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            email = (row.get("HR / Recruiter Email") or "").strip().lower()
            if not email or "@" not in email or email in seen:
                continue
            if skip_guessed and "guess" in (row.get("Email Source") or "").lower():
                continue
            local = email.split("@", 1)[0]
            domain = email.split("@", 1)[-1]
            if local in SKIP_LOCAL or local.startswith("info-xx"):
                continue
            if domain in BLOCKED_DOMAINS or domain.endswith(".codet.ai"):
                continue
            # Hiring aliases only. Guessed careers@ are OK if strict SMTP later proves
            # the mailbox exists and the domain is not a catch-all.
            src = (row.get("Email Source") or "").strip().lower()
            region = (row.get("Region") or "").strip()
            soft = local in {"contact", "jobs", "job", "hello", "hi", "info"} and (
                region in {"Karachi", "Pakistan"} or src.startswith("known") or "hunter" in src
            )
            trusted = (
                src.startswith("known")
                or "hunter" in src
                or "company website" in src
                or "company site" in src
                or "company contact" in src
            )
            # Weak aliases OK only if already proven strict-valid (shortlist / cache).
            try:
                from smtp_verify import CACHE as _MAIL_CACHE
                from smtp_verify import _load_csv_map

                _is_strict = _load_csv_map(_MAIL_CACHE).get(email) == "strict-valid"
            except Exception:
                _is_strict = False
            if local in WEAK_LOCAL and not trusted and not soft and not _is_strict:
                continue
            # Named people from trusted/published sources: first.last@ or single firstname@
            published_named = any(
                k in src
                for k in (
                    "linkedin",
                    "hiring post",
                    "job posting",
                    "apply-to",
                    "apply email",
                    "named hr",
                    "company contact",
                    "company website",
                    "company site",
                    "known",
                    "hunter",
                    "ceo",
                    "founder",
                    "leadership",
                )
            ) and (
                "." in local
                or (local.isalpha() and len(local) >= 2 and "hunter" in src)
                or (local.isalpha() and len(local) >= 3)
                or local in {"nextbit", "business", "opportunities", "ceo", "founder", "founders"}
            )
            hiringish = any(
                tok in local for tok in ("career", "recruit", "talent", "hiring", "people", "job")
            ) or local.startswith("hr.")
            ats_apply = domain.endswith("jobs.workablemail.com") and trusted
            if (
                local not in SAFE_LOCAL
                and local not in WEAK_LOCAL
                and not soft
                and not hiringish
                and not published_named
                and not ats_apply
            ):
                continue
            company_key = (row.get("Company") or "").strip().lower()
            if any(b == company_key or b in company_key for b in BLOCKED_COMPANIES):
                continue
            # Extra safety: never mail your own employer domain from any column.
            blob = " ".join(
                [
                    email,
                    company_key,
                    (row.get("Domain") or "").strip().lower(),
                    (row.get("Careers / Apply URL") or "").strip().lower(),
                ]
            )
            if "codet.ai" in blob or "codet.com" in blob:
                continue
            if email in bounced_emails():
                continue
            seen.add(email)
            rows.append(row)
    # Prefer already strict-valid (cache), then Pakistan, then known sources.
    try:
        from smtp_verify import CACHE as _MAIL_CACHE
        from smtp_verify import _load_csv_map

        _strict = {
            email
            for email, status in _load_csv_map(_MAIL_CACHE).items()
            if status == "strict-valid"
        }
    except Exception:
        _strict = set()

    def rank(row: dict[str, str]) -> tuple[int, int, int, str]:
        email = (row.get("HR / Recruiter Email") or "").strip().lower()
        region = (row.get("Region") or "").strip()
        src = (row.get("Email Source") or "").lower()
        cached = 0 if email in _strict else 1
        r = (
            0
            if region in {"Karachi", "Pakistan"}
            else 1
            if region
            in {
                "MENA",
                "UAE",
                "KSA",
                "Qatar",
                "Bahrain",
                "Kuwait",
                "Oman",
                "Egypt",
                "Jordan",
                "Lebanon",
                "Singapore",
                "Malaysia",
                "Australia",
            }
            else 2
        )
        s = 0 if src.startswith("known") or "hunter" in src else 1 if "guess" not in src else 2
        return (cached, r, s, (row.get("Company") or "").lower())

    rows.sort(key=rank)
    return rows


def acquire_lock():
    import fcntl

    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    handle = LOCK_FILE.open("w")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        handle.close()
        raise SystemExit("Another send_emails.py is already running. Kill it before starting another.") from exc
    handle.write(str(os.getpid()))
    handle.flush()
    return handle


def looks_like_ban(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(hint in text for hint in BAN_HINTS)


def sent_today_count() -> int:
    if not SENT_LOG.exists():
        return 0
    today = datetime.now(timezone.utc).date().isoformat()
    count = 0
    with SENT_LOG.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if (row.get("status") or "") != "sent":
                continue
            when = row.get("sent_at") or ""
            if when.startswith(today):
                count += 1
    return count


def already_sent() -> tuple[set[str], set[str]]:
    emails: set[str] = set()
    companies: set[str] = set()
    if not SENT_LOG.exists():
        return emails, companies
    with SENT_LOG.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if (row.get("status") or "").strip().lower() != "sent":
                continue
            email = (row.get("email") or "").strip().lower()
            company = (row.get("company") or "").strip().lower()
            if email:
                emails.add(email)
            if company and company != "test":
                companies.add(company)
    return emails, companies


def _load_subject_state() -> dict:
    default = {"name_subject_sent": 0, "limit": SUBJECT_NAME_LIMIT}
    if not SUBJECT_STATE.exists():
        return default
    try:
        data = json.loads(SUBJECT_STATE.read_text(encoding="utf-8"))
        return {**default, **data}
    except (json.JSONDecodeError, OSError):
        return default


def _save_subject_state(state: dict) -> None:
    SUBJECT_STATE.parent.mkdir(parents=True, exist_ok=True)
    SUBJECT_STATE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def bump_subject_sent_count() -> None:
    state = _load_subject_state()
    state["name_subject_sent"] = int(state.get("name_subject_sent", 0)) + 1
    _save_subject_state(state)


def log_sent(
    email: str,
    company: str,
    status: str,
    error: str = "",
    letter: str = "",
    ab_arm: str = "",
    subject: str = "",
) -> None:
    SENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    new_file = not SENT_LOG.exists()
    with SENT_LOG.open("a", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        if new_file:
            writer.writerow(SENT_LOG_FIELDS)
        writer.writerow(
            [
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                company,
                email,
                status,
                error,
                letter,
                ab_arm,
                subject,
            ]
        )
    if status == "sent":
        bump_subject_sent_count()
        _bump_ab(ab_arm)


def company_name(company: str) -> str:
    name = (company or "").strip()
    if not name or name.lower() == "test":
        return ""
    return name


GENERIC_ASK = {
    "emailll.txt": "Resume attached. Open to a 15-minute call this week if useful?",
    "emailll_ai.txt": "Resume attached. Open to a 15-minute call this week if useful?",
    "emailll_go.txt": "Resume attached. Open to a 15-minute call this week if useful?",
    "emailll_proof.txt": "Resume attached. Open to a 15-minute call this week if useful?",
    "emailll_frontend.txt": "Resume attached. Open to a 15-minute call this week if useful?",
    "emailll_agent.txt": "Resume attached. Open to a 15-minute call this week if useful?",
    "emailll_backend.txt": "Resume attached. Open to a 15-minute call this week if useful?",
    "emailll_ab_a.txt": "Resume attached. Open to a 15-minute call this week if useful?",
    "emailll_ab_b.txt": "Resume attached. Open to a 15-minute call this week if useful?",
}


def render_body(
    template: str,
    company: str,
    role: str = "",
    location_clause: str = "",
    letter_name: str = "",
    contact_name: str = "",
) -> str:
    name = company_name(company)
    person = (contact_name or "").strip()
    if person:
        greeting = f"Hi {person},"
    elif name:
        greeting = f"Hi {name} team,"
    else:
        greeting = "Hi,"
    label = name or "your team"
    role_label = (role or "").strip()
    if role_label:
        opening = f"Saw the {role_label} role{location_clause or ''}. "
        ask = (
            f"If you're still hiring for {role_label}, open to a 15-minute call this week? "
            "Resume attached."
        )
    else:
        opening = f"Quick note for {label} — " if label != "your team" else ""
        ask = GENERIC_ASK.get(letter_name, GENERIC_ASK["emailll.txt"]).format(company=label)
    return (
        template.replace("{greeting}", greeting)
        .replace("{company}", label)
        .replace("{role}", role_label)
        .replace("{location_clause}", location_clause or "")
        .replace("{opening}", opening)
        .replace("{ask}", ask)
        .replace("[Company]", label)
        .replace("[Name]", "")
        .replace("Hi ,", "Hi,")
        .replace("Hi,\n\n\n", "Hi,\n\n")
    )


def _bump_ab(arm: str) -> None:
    arm = (arm or "").strip().upper()
    if arm not in {"A", "B"}:
        return
    state = {"A": 0, "B": 0}
    if AB_STATE.exists():
        try:
            state = {**state, **json.loads(AB_STATE.read_text(encoding="utf-8"))}
        except (json.JSONDecodeError, OSError):
            pass
    state[arm] = int(state.get(arm, 0)) + 1
    AB_STATE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def subject_for(company: str, role: str = "", ab_arm: str = "") -> str:
    """Reddit A/B subjects — arm A = role@company, arm B = short noun line (<6 words)."""
    co = company_name(company)
    role_label = (role or "").strip()
    arm = (ab_arm or "").strip().upper()
    if arm == "B":
        # Short, specific, ends in a noun — Reddit/CVHive 2026 pattern.
        if co and role_label:
            stack = "React"
            blob = role_label.lower()
            if "ai" in blob or "llm" in blob or "machine" in blob:
                stack = "AI"
            elif "go " in blob or blob.startswith("go") or "golang" in blob:
                stack = "Go"
            elif "front" in blob or "ui" in blob:
                stack = "Frontend"
            elif "full" in blob:
                stack = "Full-stack"
            elif "product" in blob:
                stack = "Product"
            elif "backend" in blob or "platform" in blob:
                stack = "Backend"
            return f"{stack} note, {co}"[:58]
        if co:
            return f"{co} eng note"[:58]
        return "Engineering note"
    # Arm A (default): explicit role @ company
    if role_label and co:
        subj = f"{role_label} at {co}"
        if len(subj) > 58:
            subj = f"{role_label[:40]} — {co}"
        if len(subj) > 58:
            subj = role_label[:58]
        return subj
    if role_label:
        return role_label[:58]
    if co:
        return f"{co} engineering — quick note"
    return "Engineering intro — quick note"


def build_message(
    *,
    to_email: str,
    company: str,
    body: str,
    resume: Path,
    role: str = "",
    ab_arm: str = "",
) -> MIMEMultipart:
    msg = MIMEMultipart()
    msg["From"] = f"Muhammad Muddasir <{FROM_EMAIL}>"
    msg["To"] = to_email
    msg["Reply-To"] = FROM_EMAIL
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=FROM_EMAIL.split("@", 1)[-1])
    msg["Subject"] = subject_for(company, role, ab_arm=ab_arm)
    msg.attach(MIMEText(body, "plain", "utf-8"))
    part = MIMEApplication(resume.read_bytes(), _subtype="pdf")
    part.add_header("Content-Disposition", "attachment", filename="Muhammad_Muddasir_Resume.pdf")
    msg.attach(part)
    return msg


def oauth_service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if OAUTH_TOKEN.exists():
        creds = Credentials.from_authorized_user_file(str(OAUTH_TOKEN), GMAIL_SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not OAUTH_CREDS.exists():
                raise SystemExit(oauth_setup_help())
            flow = InstalledAppFlow.from_client_secrets_file(str(OAUTH_CREDS), GMAIL_SCOPES)
            creds = flow.run_local_server(port=0)
        OAUTH_TOKEN.write_text(creds.to_json(), encoding="utf-8")
        OAUTH_TOKEN.chmod(0o600)
    return build("gmail", "v1", credentials=creds)


def oauth_setup_help() -> str:
    return """
App passwords are not available on this Google account (that screenshot is expected
until 2-Step Verification is on, or if Google blocked app passwords).

Easiest fix — try App Password again:
  1. Turn on 2-Step Verification:
     https://myaccount.google.com/signinoptions/two-step-verification
  2. Wait 1–2 minutes, then open:
     https://myaccount.google.com/apppasswords
  3. Create a password named "job-hunter" and put it in .env as GMAIL_APP_PASSWORD

If App passwords still say "not available", use Gmail OAuth instead:
  1. https://console.cloud.google.com/ → new project (or pick one)
  2. APIs & Services → Enable Gmail API
  3. OAuth consent screen → External → add muddasirrizwan9@gmail.com as test user
  4. Credentials → Create OAuth client ID → Desktop app
  5. Download JSON → save as outreach/credentials.json
  6. python outreach/send_emails.py --auth
""".strip()


def auth_mode() -> str:
    if OAUTH_TOKEN.exists() or OAUTH_CREDS.exists():
        return "oauth"
    if APP_PASSWORD:
        return "smtp"
    return "none"


def send_via_smtp(
    smtp: smtplib.SMTP,
    *,
    to_email: str,
    company: str,
    body: str,
    resume: Path,
    role: str = "",
    ab_arm: str = "",
) -> None:
    msg = build_message(
        to_email=to_email, company=company, body=body, resume=resume, role=role, ab_arm=ab_arm
    )
    smtp.sendmail(FROM_EMAIL, [to_email], msg.as_string())


def send_via_oauth(
    service,
    *,
    to_email: str,
    company: str,
    body: str,
    resume: Path,
    role: str = "",
    ab_arm: str = "",
) -> None:
    msg = build_message(
        to_email=to_email, company=company, body=body, resume=resume, role=role, ab_arm=ab_arm
    )
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
    service.users().messages().send(userId="me", body={"raw": raw}).execute()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Outreach mailer for scraped GCC/MENA/PK emails.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument(
        "--letter",
        type=Path,
        default=DEFAULT_LETTER,
        help="Single letter file. Ignored for rotation unless --letter-only.",
    )
    parser.add_argument(
        "--letters-dir",
        type=Path,
        default=None,
        help="Directory of emailll*.txt variants (default: repo root defaults).",
    )
    parser.add_argument(
        "--letter-only",
        action="store_true",
        help="Use only --letter (disable random product/AI/Go rotation).",
    )
    parser.add_argument("--resume", type=Path, default=DEFAULT_RESUME)
    parser.add_argument("--limit", type=int, default=12, help="Max emails this run (default 12).")
    parser.add_argument("--delay", type=float, default=90.0, help="Seconds between sends.")
    parser.add_argument("--daily-cap", type=int, default=20, help="Max successful sends per UTC day.")
    parser.add_argument(
        "--skip-guessed",
        dest="skip_guessed",
        action="store_true",
        default=True,
        help="Skip guessed careers@ (default on).",
    )
    parser.add_argument("--to", default="", help="Send a single test email to this address.")
    parser.add_argument("--send", action="store_true", help="Actually send. Without this, dry-run only.")
    parser.add_argument("--auth", action="store_true", help="One-time Gmail OAuth login (opens browser).")
    parser.add_argument(
        "--no-smtp-check",
        action="store_true",
        help="Dangerous: skip SMTP mailbox probe (can bounce and hurt spam score).",
    )
    parser.add_argument(
        "--no-agent",
        action="store_true",
        help="Do not call the Cursor agent; use the 4 generic letter templates.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    lock = acquire_lock() if args.send else None
    if args.auth:
        oauth_service()
        print("Gmail OAuth saved to", OAUTH_TOKEN)
        print("Now test: python outreach/send_emails.py --to muddasirrizwan9@gmail.com --send --limit 1")
        return 0

    if args.letter_only and not args.letter.exists():
        raise SystemExit(f"Missing letter: {args.letter}")
    if not args.resume.exists():
        raise SystemExit(f"Missing resume: {args.resume}")
    letter_pool = resolve_letter_pool(
        letter=args.letter,
        letters_dir=args.letters_dir,
        single_only=args.letter_only,
    )
    templates = {path: load_letter(path) for path in letter_pool}

    if args.to:
        recipients = [{"HR / Recruiter Email": args.to, "Company": "Test"}]
    else:
        recipients = load_recipients(args.csv, skip_guessed=args.skip_guessed)

    sent_emails, sent_companies = already_sent()
    bounced = bounced_emails()
    retryable_companies = set()
    if SENT_LOG.exists():
        by_co: dict[str, list[str]] = {}
        with SENT_LOG.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                co = (row.get("company") or "").strip().lower()
                em = (row.get("email") or "").strip().lower()
                if co and em and co != "test":
                    by_co.setdefault(co, []).append(em)
        for co, emails in by_co.items():
            if emails and all(e in bounced for e in emails):
                retryable_companies.add(co)
    today_count = sent_today_count()
    remaining_today = max(0, args.daily_cap - today_count) if not args.to else args.limit
    cap = min(args.limit, remaining_today)
    queue = []
    queued_emails: set[str] = set()
    skipped_dead = 0
    for row in recipients:
        email = (row.get("HR / Recruiter Email") or "").strip().lower()
        company = (row.get("Company") or "").strip()
        company_key = company.lower()
        if email in sent_emails or email in queued_emails:
            print(f"  SKIP already sent   {email}  ({company})")
            continue
        if not args.to and company_key in sent_companies and company_key not in retryable_companies:
            # Allow a different leadership mailbox even if careers/hr was emailed before.
            src = (row.get("Email Source") or "").lower()
            leadership = any(
                t in src for t in ("leadership", "ceo", "founder", "cofounder", "co-founder")
            )
            if not leadership:
                continue
            print(f"  ALLOW leadership retry {email}  ({company})")
        if not args.to and not args.no_smtp_check:
            prior = (row.get("SMTP Verification") or "").strip()
            src = (row.get("Email Source") or "").strip().lower()
            hunter_ok = prior.lower().startswith("hunter-valid") or (
                "hunter" in src and prior.lower().startswith("hunter")
            )
            strict_ok = prior.lower().startswith("strict-valid")
            forced_ok = prior.lower().startswith("user-forced")
            if smtp_detail_is_unverified(prior) and not hunter_ok and not strict_ok and not forced_ok:
                skipped_dead += 1
                print(f"  SKIP unverified      {email}  ({company})  csv:{prior[:80]}")
                continue
            if hunter_ok or strict_ok or forced_ok:
                print(f"  TRUST {prior or 'verified'}  {email}  ({company})")
            else:
                ok, detail = verify_mailbox(email)
                text = detail.lower()
                if not ok:
                    skipped_dead += 1
                    if any(
                        h in text
                        for h in ("5.1.1", "does not exist", "no such user", "user unknown", "nosuchuser", "known bounce")
                    ):
                        mark_bounce(email, company, detail)
                        print(f"  SKIP dead mailbox  {email}  ({company})")
                    elif "catch-all" in text:
                        print(f"  SKIP catch-all mx   {email}  ({company})")
                    else:
                        print(f"  SKIP unverified      {email}  ({company})  {detail[:100]}")
                    continue
        elif not args.to and args.no_smtp_check:
            raise SystemExit("Refusing --no-smtp-check after bounce issues. Strict SMTP is mandatory.")
        queue.append(row)
        queued_emails.add(email)
        if len(queue) >= cap:
            break

    mode = auth_mode()
    print(f"From: {FROM_EMAIL}")
    print(f"Auth: {mode}")
    print(f"Letters ({len(letter_pool)}): " + ", ".join(p.name for p in letter_pool))
    print(f"Resume: {args.resume}")
    print(
        f"Queued: {len(queue)}  (already sent emails: {len(sent_emails)}, companies: {len(sent_companies)}, "
        f"dead skipped: {skipped_dead}, sent today: {today_count}/{args.daily_cap})"
    )
    print()
    for row in queue:
        company = (row.get("Company") or "").strip()
        email = (row.get("HR / Recruiter Email") or "").strip()
        print(f"  -> {email}  ({company})" + (f"  [{(row.get('Sample Role') or '').strip()}]" if row.get("Sample Role") else ""))

    if not args.send:
        print("\nDry-run only.")
        print("Rotation: round-robin proof → frontend → AI-agent → backend → proof …")
        print("Pin one:  python outreach/send_emails.py --letter-only --letter emailll_ai.txt ...")
        print("If App passwords page is broken, turn on 2-Step Verification first,")
        print("or run: python outreach/send_emails.py --auth")
        print("Test:  python outreach/send_emails.py --to muddasirrizwan9@gmail.com --send --limit 1")
        print("Batch: python outreach/send_emails.py --send --limit 20 --delay 45")
        return 0

    if mode == "none":
        raise SystemExit(oauth_setup_help())

    def deliver(to_email: str, company: str, body: str) -> None:
        raise RuntimeError("uninitialized")

    smtp = None
    context = ssl.create_default_context()
    if mode == "oauth":
        service = oauth_service()

        def deliver(to_email: str, company: str, body: str, role: str = "", ab_arm: str = "") -> None:
            send_via_oauth(
                service,
                to_email=to_email,
                company=company,
                body=body,
                resume=args.resume,
                role=role,
                ab_arm=ab_arm,
            )

    else:

        def deliver(to_email: str, company: str, body: str, role: str = "", ab_arm: str = "") -> None:
            nonlocal smtp
            if smtp is not None:
                try:
                    smtp.quit()
                except Exception:
                    pass
                smtp = None
            smtp = smtplib.SMTP("smtp.gmail.com", 587, timeout=30)
            smtp.starttls(context=context)
            smtp.login(FROM_EMAIL, APP_PASSWORD)
            send_via_smtp(
                smtp,
                to_email=to_email,
                company=company,
                body=body,
                resume=args.resume,
                role=role,
                ab_arm=ab_arm,
            )

    try:
        for i, row in enumerate(queue, 1):
            company = (row.get("Company") or "").strip()
            email = (row.get("HR / Recruiter Email") or "").strip().lower()
            if email.endswith("@codet.ai") or email.endswith("@codet.com") or "codet.ai" in email:
                print(f"[{i}/{len(queue)}] SKIP  {email}  (blocked: Codet)")
                continue
            if email in sent_emails:
                print(f"[{i}/{len(queue)}] SKIP  {email}  (already sent)")
                continue
            role = (row.get("Sample Role") or "").strip()
            location_clause = (row.get("Location Clause") or "").strip()
            ab_arm = (row.get("AB Arm") or "").strip().upper()
            if not ab_arm and "emailll_ab_a" in (row.get("Letter") or "").lower():
                ab_arm = "A"
            elif not ab_arm and "emailll_ab_b" in (row.get("Letter") or "").lower():
                ab_arm = "B"
            letter_override = (row.get("Letter") or "").strip()
            if letter_override:
                candidate = Path(letter_override)
                if not candidate.is_absolute():
                    candidate = ROOT / Path(letter_override).name
                letter_path = candidate if candidate.is_file() else pick_letter(letter_pool, i)
            else:
                letter_path = pick_letter(letter_pool, i)
            body_template = templates.get(letter_path)
            if body_template is None:
                body_template = load_letter(letter_path)
            body = render_body(
                body_template,
                company,
                role=role,
                location_clause=location_clause,
                letter_name=letter_path.name,
                contact_name=(row.get("Contact Name") or row.get("First Name") or "").strip(),
            )
            used_letter = letter_path.name
            if role and not args.no_agent:
                try:
                    if str(ROOT) not in sys.path:
                        sys.path.insert(0, str(ROOT))
                    from job_hunter.agent_letter import agent_enabled, write_cover_letter

                    if agent_enabled():
                        print(f"    Cursor agent writing letter for {role} @ {company}…")
                        body = write_cover_letter(
                            company=company,
                            role=role,
                            location=(row.get("City") or row.get("Region") or "").strip(),
                            summary=(row.get("Job Summary") or row.get("Summary") or "").strip(),
                            skills=(row.get("Matched Skills") or "").strip(),
                            apply_url=(row.get("Careers / Apply URL") or "").strip(),
                        )
                        used_letter = "cursor-agent"
                except Exception as exc:  # noqa: BLE001
                    print(f"    agent letter fallback to {letter_path.name}: {exc}")
            used_subject = subject_for(company, role, ab_arm=ab_arm)
            try:
                deliver(email, company, body, role=role, ab_arm=ab_arm)
                log_sent(
                    email,
                    company,
                    "sent",
                    letter=used_letter,
                    ab_arm=ab_arm,
                    subject=used_subject,
                )
                sent_emails.add(email)
                print(f"[{i}/{len(queue)}] sent  {email}  [{used_letter}|{ab_arm or '-'}]  subj:{used_subject}")
            except Exception as exc:  # noqa: BLE001
                log_sent(
                    email,
                    company,
                    "failed",
                    str(exc),
                    letter=used_letter,
                    ab_arm=ab_arm,
                    subject=used_subject,
                )
                print(f"[{i}/{len(queue)}] FAIL  {email}  [{used_letter}]  {exc}")
                if looks_like_ban(exc):
                    print("Stopping: Gmail rate-limit / auth warning. Try again tomorrow.")
                    break
            if i < len(queue) and args.delay > 0:
                wait = args.delay + random.uniform(-15, 25)
                wait = max(45.0, wait)
                print(f"    waiting {wait:.0f}s...")
                time.sleep(wait)
    finally:
        if smtp is not None:
            try:
                smtp.quit()
            except Exception:
                pass
    print("Done. Log:", SENT_LOG)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
