#!/usr/bin/env python3
"""Rebuild Qualified Leads queue: company-domain emails at small/tech startups (not big corps)."""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEADS = ROOT / "Qualified Leads connections - CSV.csv"
OUT = ROOT / "output" / "_ql_remote_startups.json"

BIG = re.compile(
    r"\b(google|meta|facebook|amazon|microsoft|apple|netflix|uber|airbnb|linkedin|"
    r"oracle|ibm|salesforce|adobe|intel|nvidia|deloitte|accenture|cognizant|infosys|"
    r"wipro|\btcs\b|spotify|openai|anthropic|samsung|bytedance|huawei)\b",
    re.I,
)
CONTACT = re.compile(
    r"\b(cto|chief technology|vp.?engineering|head of eng|founding engineer|"
    r"co-?founder|founder|ceo|talent|recruiting|people ops|engineering manager)\b",
    re.I,
)
TECH = re.compile(
    r"\b(software|saas|ai\b|ml\b|developer|engineer|cloud|fintech|platform|data|"
    r"startup|devtools|automation|product|cyber|security)\b",
    re.I,
)
REMOTE = re.compile(r"\b(remote|distributed|wfh|worldwide|anywhere|remote.?first)\b", re.I)
PERSONAL = {
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "icloud.com",
    "live.com",
    "proton.me",
    "me.com",
}


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def main() -> None:
    rows = list(csv.DictReader(LEADS.open(encoding="utf-8-sig")))
    out: list[dict] = []
    for r in rows:
        em = ""
        for k in ("email", "email_found (apollo.io)"):
            e = (r.get(k) or "").strip().lower()
            if e and "@" in e and "not found" not in e and " " not in e:
                em = e
                break
        if not em:
            continue
        host = em.split("@", 1)[1]
        if host in PERSONAL:
            continue
        org = (r.get("org_name") or r.get("experience_1_company") or "").strip()
        domain = (r.get("org_domain") or host).lower().removeprefix("www.")
        title = (r.get("title") or r.get("experience_1_position") or "")
        headline = r.get("headline") or ""
        blob = f"{org} {domain} {title} {headline} {r.get('org_keywords') or ''} {r.get('org_industry') or ''}"
        if not org or BIG.search(org) or BIG.search(domain):
            continue
        try:
            n = int(float(r.get("org_employee_count") or 0))
        except Exception:
            n = 0
        if n and n > 300:
            continue
        if not TECH.search(blob):
            continue
        if not CONTACT.search(title) and not CONTACT.search(headline):
            continue
        # Prefer emails where domain relates to company name
        root = re.sub(r"[^a-z0-9]", "", domain.split(".")[0])
        on = norm(org)
        domain_linked = bool(root and len(root) >= 3 and (root in on or on[:6] in root or root[:6] in on))
        if not domain_linked and domain != host and not host.endswith(domain):
            # still allow if email host == org_domain
            if host != domain and not host.endswith("." + domain):
                continue
        out.append(
            {
                "name": f"{(r.get('first_name') or '').strip()} {(r.get('last_name') or '').strip()}".strip(),
                "email": em,
                "org": org,
                "domain": domain,
                "title": title[:90],
                "headline": headline[:180],
                "about": (r.get("about") or "")[:500],
                "emp": n,
                "industry": r.get("org_industry") or "",
                "remote_flag": bool(REMOTE.search(blob)),
                "domain_linked": domain_linked,
            }
        )
    seen: set[str] = set()
    uniq: list[dict] = []
    for c in out:
        if c["email"] in seen:
            continue
        seen.add(c["email"])
        uniq.append(c)
    uniq.sort(key=lambda c: (0 if c["remote_flag"] else 1, 0 if c["domain_linked"] else 1, c["emp"] or 80, c["org"]))
    OUT.write_text(json.dumps(uniq[:250], indent=2))
    print(f"wrote {min(250, len(uniq))} / {len(uniq)} → {OUT}", flush=True)
    for c in uniq[:20]:
        print(f"  {c['org'][:28]:28} {c['email'][:36]:36} rem={c['remote_flag']} linked={c['domain_linked']}", flush=True)


if __name__ == "__main__":
    main()
