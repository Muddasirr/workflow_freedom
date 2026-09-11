#!/usr/bin/env python3
"""One-shot follow-ups for recent high-signal applications (no prior follow-up)."""
from __future__ import annotations

import csv
import os
import random
import re
import smtplib
import ssl
import sys
import time
from datetime import datetime, timedelta, timezone
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "outreach"))
load_dotenv(ROOT / ".env")

from send_emails import log_sent  # noqa: E402

RESUME = ROOT / "Muhammad_Muddasir_Resume.pdf"
FROM = os.getenv("GMAIL_ADDRESS", "").strip()
PASS = os.getenv("GMAIL_APP_PASSWORD", "").strip()
TPL = (ROOT / "emailll_followup.txt").read_text(encoding="utf-8")
TAG = "followup_v1"
TARGET = int(os.getenv("FOLLOWUP_TARGET", "12"))
DELAY = 35.0

# Prefer product/tech over pure banks for follow-up
SKIP_CO = re.compile(r"\b(bank|ptcl|ufone|telenor|zong|meezan)\b", re.I)


def send_one(*, to: str, subject: str, body: str) -> None:
    msg = MIMEMultipart()
    msg["From"] = f"Muhammad Muddasir <{FROM}>"
    msg["To"] = to
    msg["Reply-To"] = FROM
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=FROM.split("@", 1)[-1])
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))
    part = MIMEApplication(RESUME.read_bytes(), _subtype="pdf")
    part.add_header("Content-Disposition", "attachment", filename=RESUME.name)
    msg.attach(part)
    ctx = ssl.create_default_context()
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=90) as smtp:
        smtp.starttls(context=ctx)
        smtp.login(FROM, PASS)
        smtp.sendmail(FROM, [to], msg.as_string())


def main() -> None:
    if not FROM or not PASS or not RESUME.exists():
        raise SystemExit("missing gmail/resume")
    rows = list(csv.DictReader((ROOT / "outreach" / "sent_log.csv").open(encoding="utf-8-sig")))
    followed = {
        (r.get("email") or "").lower()
        for r in rows
        if r.get("status") == "sent" and "followup" in (r.get("letter") or "").lower()
    }
    cutoff = datetime.now(timezone.utc) - timedelta(days=21)
    # latest send per email
    latest: dict[str, dict] = {}
    for r in rows:
        if (r.get("status") or "").lower() != "sent":
            continue
        em = (r.get("email") or "").lower()
        if not em or "@" not in em:
            continue
        if "followup" in (r.get("letter") or "").lower():
            continue
        ts = r.get("sent_at") or ""
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            continue
        if dt < cutoff:
            continue
        co = r.get("company") or ""
        if SKIP_CO.search(co):
            continue
        prev = latest.get(em)
        if not prev or ts > (prev.get("sent_at") or ""):
            latest[em] = r

    queue = [r for em, r in latest.items() if em not in followed]
    queue.sort(key=lambda r: r.get("sent_at") or "", reverse=True)
    queue = queue[:TARGET]
    print(f"followup queue={len(queue)}", flush=True)
    sent_n = 0
    for r in queue:
        em = (r.get("email") or "").lower()
        co = r.get("company") or "the team"
        name = "team"
        body = (
            TPL.replace("{company}", co)
            .replace("{name}", name)
            .replace("{greeting}", f"Hi {co} team,")
        )
        # template uses Hi {name}, — keep simple
        if "Hi {name}" in TPL:
            body = TPL.replace("{company}", co).replace("{name}", "team")
        subj = f"Re: {co} engineering — quick note"
        print(f"[{sent_n+1}] follow-up → {em} ({co})", flush=True)
        try:
            send_one(to=em, subject=subj, body=body)
            log_sent(em, co, "sent", letter=TAG, subject=subj)
            sent_n += 1
            print(f"  SENT follow-up", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"  FAIL {exc}", flush=True)
            continue
        if sent_n < len(queue):
            wait = DELAY + random.uniform(-4, 6)
            print(f"  wait {wait:.0f}s…", flush=True)
            time.sleep(wait)
    print(f"DONE followups {sent_n}", flush=True)


if __name__ == "__main__":
    main()
