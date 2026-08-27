#!/usr/bin/env python3
"""BytesPak application — published hr@ from job posting."""
from __future__ import annotations

import csv
import smtplib
import ssl
import sys
from datetime import datetime, timezone
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "outreach"))

from send_emails import APP_PASSWORD, FROM_EMAIL, load_letter, log_sent, render_body  # noqa: E402

TO = "hr@bytesplatform.com"
COMPANY = "BytesPak"
ROLE = "Software Engineer"
SUBJECT = "Applying for Software Engineer"
LETTER = ROOT / "emailll_frontend.txt"
RESUME = ROOT / "Muhammad_Muddasir_Resume.pdf"
CACHE = ROOT / "outreach" / "mailbox_cache.csv"


def main() -> int:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with CACHE.open("a", encoding="utf-8-sig", newline="") as handle:
        csv.writer(handle).writerow(
            [now, TO, "strict-valid", "published apply address in job posting; Google catch-all"]
        )

    template = load_letter(LETTER)
    body = render_body(
        template,
        COMPANY,
        role=ROLE,
        location_clause=" (Karachi — remote-friendly)",
        letter_name=LETTER.name,
    )

    msg = MIMEMultipart()
    msg["From"] = f"Muhammad Muddasir <{FROM_EMAIL}>"
    msg["To"] = TO
    msg["Reply-To"] = FROM_EMAIL
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=FROM_EMAIL.split("@", 1)[-1])
    msg["Subject"] = SUBJECT
    msg.attach(MIMEText(body, "plain", "utf-8"))
    part = MIMEApplication(RESUME.read_bytes(), _subtype="pdf")
    part.add_header("Content-Disposition", "attachment", filename="Muhammad_Muddasir_Resume.pdf")
    msg.attach(part)

    context = ssl.create_default_context()
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as smtp:
        smtp.starttls(context=context)
        smtp.login(FROM_EMAIL, APP_PASSWORD)
        smtp.sendmail(FROM_EMAIL, [TO], msg.as_string())

    log_sent(TO, COMPANY, "sent", letter=LETTER.name)
    print(f"SENT  {TO}  [{LETTER.name}]  subject:{SUBJECT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
