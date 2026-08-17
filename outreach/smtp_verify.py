"""Strict mailbox checks for outreach.

RCPT 250 alone is NOT enough — many MX hosts are catch-alls or accept then bounce.
We require:
  1) real mailbox probe passes
  2) a random fake local-part on the same domain is REJECTED (proves not catch-all)
  3) otherwise treat as unverified / do not send
"""
from __future__ import annotations

import csv
import random
import smtplib
import string
import time
from datetime import datetime, timezone
from pathlib import Path

import dns.resolver

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "outreach" / "mailbox_cache.csv"
BOUNCE_LOG = ROOT / "outreach" / "bounces.csv"
PROBE_FROM = "probe@muddasirrizwan.com"

IP_BLOCK_HINTS = (
    "spamhaus",
    "pbl",
    "sbl",
    "xbl",
    "blocklist",
    "blacklist",
    "listed by",
    "client host rejected",
    "blocked using",
    "access denied",
    "not allowed to connect",
    "too many connections",
    "rate limit",
)
MAILBOX_MISS_HINTS = (
    "5.1.1",
    "nosuchuser",
    "no such user",
    "does not exist",
    "user unknown",
    "unknown user",
    "invalid recipient",
    "recipient address rejected",
    "mailbox unavailable",
    "no mailbox",
    "undeliverable",
    "address rejected",
)


def _load_csv_map(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            email = (row.get("email") or "").strip().lower()
            status = (row.get("status") or "").strip().lower()
            if email and status:
                out[email] = status
    return out


def _append_row(path: Path, headers: list[str], row: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists()
    with path.open("a", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        if new_file:
            writer.writerow(headers)
        writer.writerow(row)


UNSENDABLE_HINTS = (
    "probe-blocked",
    "catch-all",
    "known bounce",
    "untrusted accept",
    "accept-then-unknown",
    "cache invalid",
    "cache reject",
    "cache bounce",
    "cache no-mx",
    "no mx",
    "malformed",
)


def smtp_detail_is_unverified(detail: str) -> bool:
    """True if a probe/CSV note means we must not send."""
    text = (detail or "").lower()
    return any(h in text for h in UNSENDABLE_HINTS)


def bounced_emails() -> set[str]:
    return {e for e, status in _load_csv_map(BOUNCE_LOG).items() if status in {"bounce", "invalid", "reject"}}


def mark_bounce(email: str, company: str = "", detail: str = "") -> None:
    email = email.lower().strip()
    _append_row(
        BOUNCE_LOG,
        ["checked_at", "company", "email", "status", "detail"],
        [
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
            company,
            email,
            "bounce",
            detail[:300],
        ],
    )
    _append_row(
        CACHE,
        ["checked_at", "email", "status", "detail"],
        [
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
            email,
            "invalid",
            detail[:300],
        ],
    )


def mx_hosts(domain: str) -> list[str]:
    try:
        answers = dns.resolver.resolve(domain, "MX")
        ranked = sorted((r.preference, str(r.exchange).rstrip(".")) for r in answers)
        return [host for _, host in ranked]
    except Exception:  # noqa: BLE001
        try:
            dns.resolver.resolve(domain, "A")
            return [domain]
        except Exception:  # noqa: BLE001
            return []


def _fake_address(domain: str) -> str:
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=12))
    return f"no-mailbox-{suffix}@{domain}"


def _rcpt(host: str, email: str, timeout: float) -> tuple[int, str]:
    with smtplib.SMTP(timeout=timeout) as smtp:
        smtp.connect(host, 25)
        smtp.helo("muddasirrizwan.com")
        code, msg = smtp.mail(PROBE_FROM)
        if code >= 400:
            return code, f"mail-from {code} {msg!r}"
        code, msg = smtp.rcpt(email)
        return code, f"{host} rcpt {code} {msg!r}"


def _is_ip_block(detail: str) -> bool:
    text = detail.lower()
    return any(h in text for h in IP_BLOCK_HINTS)


def _is_mailbox_miss(code: int, detail: str) -> bool:
    text = detail.lower()
    if any(h in text for h in MAILBOX_MISS_HINTS):
        return True
    return code in {550, 551, 552, 553, 554}


def verify_mailbox(email: str, *, use_cache: bool = True, timeout: float = 20.0) -> tuple[bool, str]:
    """Strict verify. ok=True only if mailbox accepts AND domain rejects a fake address."""
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        return False, "malformed"
    if email in bounced_emails():
        return False, "known bounce"
    if use_cache:
        cached = _load_csv_map(CACHE).get(email)
        if cached == "strict-valid":
            return True, "cache strict-valid"
        if cached in {
            "invalid",
            "reject",
            "bounce",
            "no-mx",
            "catch-all",
            "accept-then-unknown",
            "probe-blocked",
        }:
            return False, f"cache {cached}"
        # Old loose "valid" is no longer trusted.
        if cached == "valid":
            pass

    domain = email.split("@", 1)[1]
    hosts = mx_hosts(domain)
    if not hosts:
        _append_row(
            CACHE,
            ["checked_at", "email", "status", "detail"],
            [datetime.now(timezone.utc).isoformat(timespec="seconds"), email, "no-mx", "no mx/a"],
        )
        return False, "no mx"

    fake = _fake_address(domain)
    last_detail = "unreachable"

    for host in hosts[:2]:
        try:
            real_code, real_detail = _rcpt(host, email, timeout)
            time.sleep(0.3)
            fake_code, fake_detail = _rcpt(host, fake, timeout)
            detail = f"{real_detail} | fake:{fake_detail}"
            last_detail = detail

            if _is_ip_block(real_detail) or _is_ip_block(fake_detail):
                _append_row(
                    CACHE,
                    ["checked_at", "email", "status", "detail"],
                    [
                        datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        email,
                        "probe-blocked",
                        detail[:300],
                    ],
                )
                return False, detail

            if _is_mailbox_miss(real_code, real_detail):
                _append_row(
                    CACHE,
                    ["checked_at", "email", "status", "detail"],
                    [
                        datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        email,
                        "invalid",
                        detail[:300],
                    ],
                )
                return False, detail

            # Catch-all / accept-everything MX: fake also 250 → RCPT proves nothing.
            if real_code in {250, 251} and fake_code in {250, 251}:
                _append_row(
                    CACHE,
                    ["checked_at", "email", "status", "detail"],
                    [
                        datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        email,
                        "catch-all",
                        detail[:300],
                    ],
                )
                return False, f"catch-all mx: {detail}"

            # Strict pass: real accepted, fake rejected as unknown user.
            if real_code in {250, 251} and _is_mailbox_miss(fake_code, fake_detail):
                _append_row(
                    CACHE,
                    ["checked_at", "email", "status", "detail"],
                    [
                        datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        email,
                        "strict-valid",
                        detail[:300],
                    ],
                )
                return True, detail

            # Real accepted but fake response ambiguous → do not trust.
            if real_code in {250, 251}:
                _append_row(
                    CACHE,
                    ["checked_at", "email", "status", "detail"],
                    [
                        datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        email,
                        "accept-then-unknown",
                        detail[:300],
                    ],
                )
                return False, f"untrusted accept: {detail}"

            last_detail = detail
        except Exception as exc:  # noqa: BLE001
            last_detail = f"{host} {exc}"
            continue
        time.sleep(0.25)

    timeoutish = any(h in last_detail.lower() for h in ("timed out", "timeout", "unreachable"))
    status = "probe-blocked" if timeoutish else "reject"
    _append_row(
        CACHE,
        ["checked_at", "email", "status", "detail"],
        [
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
            email,
            status,
            last_detail[:300],
        ],
    )
    return False, last_detail
