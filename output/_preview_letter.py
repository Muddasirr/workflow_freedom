#!/usr/bin/env python3
"""Print a sample Reddit-style letter for one company (no send)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "outreach"))

from send_emails import load_letter, render_body, subject_for  # noqa: E402

letter = load_letter(ROOT / "emailll.txt")
company = sys.argv[1] if len(sys.argv) > 1 else "Trigger.dev"
role = sys.argv[2] if len(sys.argv) > 2 else ""
contact = sys.argv[3] if len(sys.argv) > 3 else "Matt"
body = render_body(
    letter,
    company,
    role=role,
    location_clause=" (remote)" if role else "",
    letter_name="emailll.txt",
    contact_name=contact,
)
print("SUBJECT:", subject_for(company, role))
print("---")
print(body)
