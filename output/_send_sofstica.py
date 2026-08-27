#!/usr/bin/env python3
"""One-off Sofstica AI Engineer application with required subject + CC."""
from __future__ import annotations

import csv
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

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "outreach"))

from send_emails import (  # noqa: E402
    APP_PASSWORD,
    FROM_EMAIL,
    ROOT as SEND_ROOT,
    load_letter,
    log_sent,
    render_body,
)

TO = "hadiqa.shahid@sofstica.com"
CC = "career@sofstica.com"
COMPANY = "Sofstica"
ROLE = "AI Engineer"
SUBJECT = "Applying for AI Engineer"
LETTER = SEND_ROOT / "emailll_agent.txt"
RESUME = SEND_ROOT / "Muhammad_Muddasir_Resume.pdf"
CACHE = ROOT / "outreach" / "mailbox_cache.csv"


def promote_cache(*emails: str) -> None:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with CACHE.open("a", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        for email in emails:
            writer.writerow(
                [
                    now,
                    email,
                    "strict-valid",
                    "published apply address in job posting; outlook RCPT 250 / named recruiter",
                ]
            )


def build_message(*, body: str) -> MIMEMultipart:
    msg = MIMEMultipart()
    msg["From"] = f"Muhammad Muddasir <{FROM_EMAIL}>"
    msg["To"] = TO
    msg["Cc"] = CC
    msg["Reply-To"] = FROM_EMAIL
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=FROM_EMAIL.split("@", 1)[-1])
    msg["Subject"] = SUBJECT
    msg.attach(MIMEText(body, "plain", "utf-8"))
    part = MIMEApplication(RESUME.read_bytes(), _subtype="pdf")
    part.add_header("Content-Disposition", "attachment", filename="Muhammad_Muddasir_Resume.pdf")
    msg.attach(part)
    return msg


def main() -> int:
    promote_cache(TO, CC)
    template = load_letter(LETTER)
    body = render_body(
        template,
        COMPANY,
        role=ROLE,
        location_clause=" (Karachi — onsite)",
        letter_name=LETTER.name,
    ).replace("Hi Sofstica team,", "Hi Hadiqa,")

    msg = build_message(body=body)
    context = ssl.create_default_context()
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as smtp:
        smtp.starttls(context=context)
        smtp.login(FROM_EMAIL, APP_PASSWORD)
        smtp.sendmail(FROM_EMAIL, [TO, CC], msg.as_string())

    log_sent(TO, COMPANY, "sent", error=f"cc:{CC}", letter=LETTER.name)
    print(f"SENT  {TO}  cc:{CC}  [{LETTER.name}]  subject:{SUBJECT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
