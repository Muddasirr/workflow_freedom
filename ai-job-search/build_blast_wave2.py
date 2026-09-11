#!/usr/bin/env python3
"""Build wave2 queue from scrape + cache (no live SMTP)."""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "outreach"))

from job_hunter.directory import COMPANY_DIRECTORY  # noqa: E402
from job_hunter.experience import role_ok_for_junior  # noqa: E402
from send_emails import BLOCKED_DOMAINS, already_sent  # noqa: E402

STACK = re.compile(
    r"react|next|frontend|full.?stack|typescript|python|ai engineer|software engineer|backend|golang|go ",
    re.I,
)
BAD = re.compile(r"\b(intern|trainee|sqa|qa engineer|sales|php)\b", re.I)


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def main() -> None:
    se, sc = already_sent()
    print(f"sent emails={len(se)} companies={len(sc)}", flush=True)

    status: dict[str, str] = {}
    for r in csv.DictReader((ROOT / "outreach" / "mailbox_cache.csv").open(encoding="utf-8-sig")):
        em = (r.get("email") or "").lower().strip()
        if em:
            status[em] = r.get("status") or ""

    co_dom: dict[str, str] = {}
    co_em: dict[str, str] = {}
    for name, domain, _city, _loc, emails in COMPANY_DIRECTORY:
        co_dom[norm(name)] = domain
        for e in emails:
            if "@" in e:
                co_em.setdefault(norm(name), e.lower())
    for path in (ROOT / "output").glob("emails_*.csv"):
        if "lead" in path.name.lower() or "qualified" in path.name.lower():
            continue
        try:
            for r in csv.DictReader(path.open(encoding="utf-8-sig")):
                co = (r.get("Company") or "").strip()
                em = (r.get("HR / Recruiter Email") or r.get("Email") or "").strip().lower()
                if co and "@" in em:
                    co_em.setdefault(norm(co), em)
                    co_dom.setdefault(norm(co), em.split("@", 1)[1])
        except Exception:
            continue
    print(f"maps co_em={len(co_em)} co_dom={len(co_dom)}", flush=True)

    def usable(em: str) -> bool:
        if not em or "@" not in em or em in se:
            return False
        host = em.split("@", 1)[1]
        if host in BLOCKED_DOMAINS:
            return False
        st = status.get(em, "")
        local = em.split("@")[0]
        hrish = any(t in local for t in ("career", "hr", "hello", "job", "talent", "recruit", "join", "people"))
        if st in ("invalid", "reject", "no-mx", "probe-blocked"):
            return False
        if st in ("strict-valid", "valid"):
            return True
        if st == "catch-all" and hrish:
            return True
        # prior CSV / directory emails with no cache row
        if not st and hrish:
            return True
        return False

    jobs: list[dict] = []
    for base in (
        ROOT / "ai-job-search" / "output_scrape" / "until50",
        ROOT / "ai-job-search" / "output_scrape" / "batch50",
    ):
        for p in base.glob("*.json"):
            if p.parent.name in ("details", "letters"):
                continue
            try:
                data = json.loads(p.read_text())
            except Exception:
                continue
            results = data.get("results") if isinstance(data, dict) else data
            for r in results or []:
                title = (r.get("title") or "").strip()
                co = (r.get("company") or "").strip()
                if not title or not co:
                    continue
                if BAD.search(title) or not STACK.search(title):
                    continue
                if not role_ok_for_junior(title):
                    continue
                if norm(co) in sc:
                    continue
                loc = r.get("location") or ""
                if isinstance(loc, dict):
                    loc = loc.get("label") or ""
                jobs.append({"company": co, "title": title, "location": str(loc), "url": r.get("url") or ""})

    seen: set[str] = set()
    uniq: list[dict] = []
    for j in jobs:
        k = norm(j["company"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(j)
    print(f"uniq unsent companies={len(uniq)}", flush=True)

    found: list[dict] = []
    for j in uniq:
        kn = norm(j["company"])
        cands: list[str] = []
        if kn in co_em:
            cands.append(co_em[kn])
        for pk, em in co_em.items():
            if len(pk) < 8 or len(kn) < 8:
                continue
            s, l = (pk, kn) if len(pk) <= len(kn) else (kn, pk)
            if s in l and len(s) / len(l) >= 0.72:
                cands.append(em)
        dom = co_dom.get(kn)
        if not dom:
            for pk, d in co_dom.items():
                if len(pk) < 8 or len(kn) < 8:
                    continue
                s, l = (pk, kn) if len(pk) <= len(kn) else (kn, pk)
                if s in l and len(s) / len(l) >= 0.72:
                    dom = d
                    break
        if dom:
            for local in ("careers", "hr", "hello", "jobs", "talent", "recruiting"):
                cands.append(f"{local}@{dom}")
            for em, st in status.items():
                if em.endswith("@" + dom) and usable(em):
                    cands.append(em)
        picked = None
        for em in dict.fromkeys(e.lower() for e in cands if e):
            if usable(em):
                picked = em
                break
        if picked:
            st = status.get(picked, "unknown")
            found.append({**j, "email": picked, "tag": st or "unknown"})
            print(f"FOUND {j['company'][:28]} | {j['title'][:32]} → {picked} [{st}]", flush=True)
        if len(found) >= 40:
            break

    out = ROOT / "output" / "_blast_wave2.json"
    out.write_text(json.dumps(found, indent=2))
    print(f"TOTAL {len(found)} → {out}", flush=True)


if __name__ == "__main__":
    main()
