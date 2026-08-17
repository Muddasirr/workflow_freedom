from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from job_hunter.config import ATS_DOMAINS

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
NOISE_EMAIL_PARTS = (
    "example.com",
    "email.com",
    "domain.com",
    "sentry.io",
    "wixpress.com",
    "github.com",
    "noreply",
    "no-reply",
    "donotreply",
    "notifications@",
    "mailer-daemon",
    "privacy@",
    "legal@",
    "support@linkedin",
)


def html_to_text(value: str | None) -> str:
    if not value:
        return ""
    text = html.unescape(str(value))
    soup = BeautifulSoup(text, "lxml")
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()


def excerpt(text: str, limit: int = 280) -> str:
    clean = re.sub(r"\s+", " ", text or "").strip()
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1].rsplit(" ", 1)[0] + "…"


def extract_emails(text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for match in EMAIL_RE.findall(text or ""):
        email = match.strip(".,;:()<>[]\"'").lower()
        if email in seen:
            continue
        if any(part in email for part in NOISE_EMAIL_PARTS):
            continue
        if email.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")):
            continue
        seen.add(email)
        found.append(email)
    return found


def domain_from_url(url: str) -> str:
    if not url:
        return ""
    host = (urlparse(url).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if not host or any(host == d or host.endswith("." + d) for d in ATS_DOMAINS):
        return ""
    return host


def format_salary(min_val: object = None, max_val: object = None, currency: str = "", period: str = "") -> str:
    def _num(value: object) -> str:
        try:
            number = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return ""
        if number <= 0:
            return ""
        if number >= 1000:
            return f"{int(number):,}"
        return str(int(number) if number.is_integer() else number)

    low, high = _num(min_val), _num(max_val)
    if not low and not high:
        return ""
    amount = f"{low}–{high}" if low and high and low != high else (low or high)
    currency = (currency or "").upper()
    suffix = f" / {period}" if period else ""
    return f"{currency} {amount}{suffix}".strip()


def unix_to_iso(value: object) -> str:
    try:
        ts = int(float(str(value)))
    except (TypeError, ValueError):
        return str(value or "")
    if ts > 10_000_000_000:
        ts //= 1000
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
    except (OverflowError, OSError, ValueError):
        return str(value or "")
