#!/usr/bin/env python3
"""Send tailored applications to unsent geo companies with known careers inboxes.

Uses careers page as apply source. Role title is stack-fit Software/Full-Stack Engineer
when a board posting isn't available — still company-specific letters.
"""
from __future__ import annotations

import json
import os
import random
import re
import smtplib
import ssl
import sys
import time
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "outreach"))
load_dotenv(ROOT / ".env")

from job_hunter.agent_letter import agent_enabled, write_cover_letter  # noqa: E402
from send_emails import already_sent, log_sent  # noqa: E402

RESUME = ROOT / "Muhammad_Muddasir_Resume.pdf"
FROM = os.getenv("GMAIL_ADDRESS", "").strip()
PASS = os.getenv("GMAIL_APP_PASSWORD", "").strip()
TAG = "blast_careers+cursor"
DELAY = 40.0
TARGET = int(os.getenv("BLAST_TARGET", "15"))
READY = ROOT / "output" / "_blast_ready_geo.json"
LETTERS = ROOT / "ai-job-search" / "output_scrape" / "until50" / "letters"

# Prefer product/engineering orgs over banks/telco for first wave
PREFER = re.compile(
    r"confiz|netsol|empiric|tintash|tkxel|securiti|swvl|talabat|anghami|bosta|salla|"
    r"hungerstation|paymob|namshi|mumzworld|nearpay|tajawal|opensooq|mawdoo3|jawaker|"
    r"synapse|nymcard|foodpanda|sadapay|abhi|dawaai|bookme|priceoye|keenu|haball|"
    r"zigron|elixir|sekel|stormfiber|jazzcash|ufone|ptcl|meezan|valeo|magnati|rain|"
    r"qatar airways|snoonu|credimax|murex|telenor|zong|front|alokai|cartlow|bayzat|"
    r"careem|dubizzle|emumba|folio|venture|10pearls|thoughtworks|turing|motive|"
    r"delivery hero|checkout|geidea|lean|khazna|bosta|instashop|tabby|tamara",
    re.I,
)


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


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
    last: Exception | None = None
    for attempt in range(3):
        try:
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=90) as smtp:
                smtp.starttls(context=ctx)
                smtp.login(FROM, PASS)
                smtp.sendmail(FROM, [to], msg.as_string())
            return
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(10 * (attempt + 1))
    raise last or RuntimeError("send failed")


def main() -> None:
    if not agent_enabled() or not FROM or not PASS or not RESUME.exists():
        raise SystemExit("missing creds/resume")
    sent_e, sent_c_raw = already_sent()
    sent_c = {norm(c) for c in sent_c_raw} | {c.strip().lower() for c in sent_c_raw}
    ready = json.loads(READY.read_text())
    # STRICT ONLY — never catch-all / unverified careers@
    prefer_strict = [r for r in ready if r.get("tag") == "strict" and PREFER.search(r.get("company") or "")]
    other_strict = [r for r in ready if r.get("tag") == "strict" and r not in prefer_strict]
    queue = []
    for r in prefer_strict + other_strict:
        if norm(r["company"]) in sent_c or r["company"].lower() in sent_c:
            continue
        if r["email"] in sent_e:
            continue
        queue.append(r)
        if len(queue) >= TARGET:
            break
    print(f"queue={len(queue)} target={TARGET} (STRICT verified only)", flush=True)
    for r in queue:
        print(f"  {r['company'][:32]} → {r['email']} [{r['tag']}]", flush=True)

    LETTERS.mkdir(parents=True, exist_ok=True)
    sent_n = 0
    used_emails: set[str] = set()
    for r in queue:
        if sent_n >= TARGET:
            break
        if r["email"] in sent_e or r["email"] in used_emails:
            print(f"  skip dup email {r['email']}", flush=True)
            continue
        if norm(r["company"]) in sent_c or r["company"].lower() in sent_c:
            continue
        title = "Software Engineer / Full Stack Engineer"
        print(f"\n[{sent_n+1}] {title} @ {r['company']}", flush=True)
        print(f"  email {r['email']} [{r['tag']}]", flush=True)
        safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", r["company"])[:40]
        letter_path = LETTERS / f"careers_{safe}.txt"
        summary = (
            f"{r['company']} ({r['domain']}) careers inbox application for junior/associate "
            f"Software Engineer or Full Stack / Frontend / AI-adjacent engineering in {r['location']}. "
            f"Apply via {r['url']}. Candidate has ~1 YOE Next.js/React/Python/AI at Codet.ai, "
            f"based in Karachi, open to onsite/hybrid in region."
        )
        try:
            if letter_path.exists() and letter_path.stat().st_size > 80:
                body = letter_path.read_text(encoding="utf-8")
                print("  reuse letter", flush=True)
            else:
                print("  writing tailored letter…", flush=True)
                body = write_cover_letter(
                    company=r["company"],
                    role=title,
                    location=r["location"],
                    summary=summary,
                    skills="React, Next.js, TypeScript, Python, AI/LLM, APIs",
                    apply_url=r["url"],
                )
                letter_path.write_text(body, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            print(f"  letter fail: {exc}", flush=True)
            continue
        print(f"  preview: {' '.join(body.split())[:120]}…", flush=True)
        subj = f"{title} — {r['company']}"[:58]
        try:
            send_one(to=r["email"], subject=subj, body=body)
            sent_n += 1
            sent_e.add(r["email"])
            used_emails.add(r["email"])
            sent_c.add(norm(r["company"]))
            sent_c.add(r["company"].lower())
            log_sent(r["email"], r["company"], "sent", letter=TAG, subject=subj)
            print(f"  SENT [{sent_n}/{TARGET}] {r['email']}", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"  SEND FAIL {exc}", flush=True)
            log_sent(r["email"], r["company"], "failed", str(exc)[:200], letter=TAG, subject=subj)
            continue
        if sent_n < TARGET:
            wait = DELAY + random.uniform(-5, 8)
            print(f"  wait {wait:.0f}s…", flush=True)
            time.sleep(wait)
    print(f"\nDONE. Sent {sent_n}/{TARGET}", flush=True)


if __name__ == "__main__":
    main()
