#!/usr/bin/env python3
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "outreach"))

from send_emails import SKIP_LOCAL, already_sent  # noqa: E402
from smtp_verify import bounced_emails, verify_mailbox  # noqa: E402

EXTRA_SKIP = {
    "compliance",
    "feedback",
    "fraud",
    "partnerships",
    "gdpr",
    "service",
    "salessupport",
    "customerservice",
    "csoc",
    "mktg",
    "marketing",
    "announce",
    "comercial",
    "office",
    "win",
    "questions",
    "inquiries",
    "osrd",
    "oddinfo",
    "getapebl",
    "fieldguides",
    "vn",
    "acarrier",
}

RAW = Path(
    "/home/sleepwellsystem/.cursor/projects/home-sleepwellsystem-Desktop-codet-webb/terminals/557851.txt"
).read_text(errors="replace")


def main() -> None:
    sent_e, sent_c = already_sent()
    sent_d = {e.split("@", 1)[1] for e in sent_e if "@" in e}
    bounced = bounced_emails()
    seen: set[str] = set()
    candidates: list[dict[str, str]] = []
    for line in RAW.splitlines():
        m = re.search(r"SCRAPE \d+/437 (.+?)\s{2,}(\S+)\s{2,}(\S+@\S+)\s*$", line)
        if not m:
            continue
        company, domain, email = m.group(1).strip(), m.group(2).strip().lower(), m.group(3).strip().lower()
        email = email.replace("u003e", "")
        local, _, host = email.partition("@")
        if local in SKIP_LOCAL or local in EXTRA_SKIP or local.startswith("info-"):
            continue
        if email in sent_e or email in bounced or email in seen:
            continue
        if company.lower() in sent_c or domain in sent_d or host in sent_d:
            continue
        seen.add(email)
        candidates.append(
            {
                "Company": company,
                "Region": "Remote",
                "City": "",
                "HR / Recruiter Email": email,
                "Email Source": "company website",
                "Other Emails": "",
                "Domain": domain,
                "Careers / Apply URL": "https://jsgurujobs.com/jobs",
                "Sample Role": "",
                "Location Clause": "",
                "Letter": "",
                "SMTP Verification": "",
            }
        )
    print(f"to probe {len(candidates)}", flush=True)
    ready = []
    for row in candidates:
        email = row["HR / Recruiter Email"]
        ok, detail = verify_mailbox(email)
        row["SMTP Verification"] = (detail or "")[:400]
        print(f"  SMTP {'OK' if ok else 'NO '} {email:48} {row['Company'][:22]:22} {detail[:70]}", flush=True)
        if ok:
            ready.append(row)
    out = ROOT / "output" / "emails_jsguru_2026-08-19.csv"
    fields = list(ready[0].keys()) if ready else list(candidates[0].keys())
    with out.open("w", encoding="utf-8-sig", newline="") as h:
        w = csv.DictWriter(h, fieldnames=fields)
        w.writeheader()
        w.writerows(ready)
    print(f"READY {len(ready)} -> {out}", flush=True)
    for row in ready:
        print(f"  SENDABLE {row['HR / Recruiter Email']} ({row['Company']})", flush=True)


if __name__ == "__main__":
    main()
