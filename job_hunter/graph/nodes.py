"""Graph nodes: find posting → find email → validate → letter → send."""
from __future__ import annotations

import random
import sys
import time
from datetime import date

from job_hunter.apply import collect_jobs
from job_hunter.careers import scrape_company_careers, scrape_directory_careers
from job_hunter.config import OUTPUT_DIR, ROOT
from job_hunter.emails import (
    attach_description_emails,
    attach_known_emails,
    pick_hr_email,
    resolve_company_domain,
)
from job_hunter.excel import write_csv, write_workbook
from job_hunter.graph.state import GraphState, JobCard
from job_hunter.models import Job
from job_hunter.personalize import location_clause, pick_letter, role_label

if str(ROOT / "outreach") not in sys.path:
    sys.path.insert(0, str(ROOT / "outreach"))

from send_emails import (  # noqa: E402
    BLOCKED_COMPANIES,
    DEFAULT_RESUME,
    SKIP_LOCAL,
    already_sent,
    log_sent,
    render_body,
    send_via_smtp,
    sent_today_count,
)
from smtp_verify import bounced_emails, verify_mailbox  # noqa: E402

JUNK_LOCAL = set(SKIP_LOCAL) | {"help", "bd", "pr", "press", "support", "sales"}


def _log(state: GraphState, line: str) -> None:
    print(line, flush=True)
    state.setdefault("log", []).append(line)


def _job_to_card(job: Job) -> JobCard:
    return {
        "title": (job.title or "").strip(),
        "company": (job.company or "").strip(),
        "url": job.url or "",
        "location": job.location or "",
        "description": (job.description or job.excerpt or "")[:4000],
        "excerpt": (job.excerpt or job.description or "")[:400],
        "skills": ", ".join(job.matched_skills),
        "domain": job.company_domain or "",
        "email": (job.hr_email or "").strip().lower(),
        "email_source": job.email_source or "",
        "status": "found",
        "reason": "",
        "smtp": "",
        "letter": "",
        "letter_kind": "",
    }


def _card_to_job(card: JobCard) -> Job:
    emails = [card["email"]] if card.get("email") else []
    return Job(
        source="graph",
        source_id=card.get("url") or card.get("title") or "",
        title=card.get("title") or "",
        company=card.get("company") or "",
        url=card.get("url") or "",
        location=card.get("location") or "",
        description=card.get("description") or "",
        excerpt=card.get("excerpt") or "",
        company_domain=card.get("domain") or "",
        hr_email=card.get("email") or "",
        email_source=card.get("email_source") or "",
        emails=emails,
        matched_skills=[s.strip() for s in (card.get("skills") or "").split(",") if s.strip()],
    )


def _usable_email(email: str, source: str) -> bool:
    if not email or "@" not in email:
        return False
    if "guess" in (source or "").lower():
        return False
    local = email.split("@", 1)[0]
    if local in JUNK_LOCAL or local.startswith("info-xx"):
        return False
    return True


def find_jobs(state: GraphState) -> GraphState:
    """Step 1 — pull junior SWE/AI/product postings (boards + career pages)."""
    _log(state, "STEP 1  Find job postings")
    sent_emails, sent_companies = already_sent()
    sent_domains = {e.split("@", 1)[1] for e in sent_emails if "@" in e}
    career_jobs = scrape_directory_careers(
        skip_companies=sent_companies,
        skip_domains=sent_domains,
        limit=max(int(state.get("limit") or 8) * 4, 40),
    )
    board_jobs = collect_jobs(junior_only=True, scrape_emails=False)
    jobs = list(board_jobs) + list(career_jobs)
    best: dict[str, Job] = {}
    for job in jobs:
        key = job.dedupe_key
        existing = best.get(key)
        if existing is None or job.score > existing.score:
            best[key] = job
    jobs = sorted(best.values(), key=lambda j: (-j.score, j.company.lower()))
    cards: list[JobCard] = []
    seen_co: set[str] = set()
    blocked = {b.lower() for b in BLOCKED_COMPANIES}
    for job in jobs:
        company = (job.company or "").strip()
        key = company.lower()
        if not (job.title or "").strip():
            continue
        if key in sent_companies or key in seen_co:
            continue
        if any(b == key or b in key for b in blocked):
            continue
        seen_co.add(key)
        cards.append(_job_to_card(job))
    stamp = date.today().isoformat()
    write_workbook(jobs, OUTPUT_DIR / f"jobs_junior_{stamp}.xlsx")
    write_csv(jobs, OUTPUT_DIR / f"jobs_junior_{stamp}.csv")
    _log(state, f"  {len(jobs)} matching roles, {len(cards)} unsent companies to walk")
    state["jobs"] = cards
    state["index"] = 0
    state["sent_count"] = 0
    state["skipped"] = []
    state["results"] = []
    state["done"] = not cards
    state["current"] = {}
    return state


def pick_job(state: GraphState) -> GraphState:
    jobs = state.get("jobs") or []
    index = int(state.get("index") or 0)
    sent_count = int(state.get("sent_count") or 0)
    lookups = int(state.get("lookups") or 0)
    limit = int(state.get("limit") or 8)
    max_lookups = max(limit * 6, 24)
    today = sent_today_count()
    remaining = max(0, int(state.get("daily_cap") or 80) - today)
    if sent_count >= limit or sent_count >= remaining or index >= len(jobs) or lookups >= max_lookups:
        state["done"] = True
        state["current"] = {}
        _log(state, "Done walking jobs.")
        return state
    card = dict(jobs[index])
    state["current"] = card
    state["index"] = index + 1
    state["lookups"] = lookups + 1
    _log(state, f"\n[{index + 1}/{len(jobs)}] {card.get('title')} @ {card.get('company')}")
    return state


def find_email(state: GraphState) -> GraphState:
    """Step 2 — published hiring email only. Never guess careers@."""
    card = dict(state.get("current") or {})
    job = _card_to_job(card)
    attach_description_emails(job)
    attach_known_emails(job)
    domain = resolve_company_domain(job)
    job.company_domain = domain
    if domain and not _usable_email(job.hr_email, job.email_source):
        extra_jobs, emails = scrape_company_careers(job.company, domain)
        merged = list(dict.fromkeys([*(job.emails or []), *emails]))
        for extra in extra_jobs:
            merged.extend(extra.emails)
            if extra.hr_email:
                merged.append(extra.hr_email)
        job.emails = list(dict.fromkeys(merged))
        picked = pick_hr_email(job.emails)
        if picked:
            job.hr_email = picked
            job.email_source = job.email_source or "company website"
    if "guess" in (job.email_source or "").lower():
        job.hr_email = ""
        job.email_source = ""
    email = (job.hr_email or "").strip().lower()
    source = job.email_source or ""
    if not _usable_email(email, source):
        card["email"] = ""
        card["status"] = "no-email"
        card["reason"] = "no published hiring inbox"
        _log(state, "  STEP 2  no published hiring email — skip")
    else:
        card["email"] = email
        card["email_source"] = source
        card["domain"] = job.company_domain
        card["status"] = "has-email"
        _log(state, f"  STEP 2  {email}  ({source or 'published'})")
    state["current"] = card
    return state


def validate_email(state: GraphState) -> GraphState:
    """Step 3 — mailbox must accept AND domain must reject a fake address."""
    card = dict(state.get("current") or {})
    email = (card.get("email") or "").strip().lower()
    if email in bounced_emails():
        card["status"] = "invalid"
        card["reason"] = "known bounce"
        card["smtp"] = "known bounce"
        _log(state, "  STEP 3  known bounce — skip")
        state["current"] = card
        return state
    ok, detail = verify_mailbox(email)
    card["smtp"] = (detail or "")[:400]
    if not ok:
        card["status"] = "invalid"
        card["reason"] = detail[:120]
        _log(state, f"  STEP 3  fail  {detail[:100]}")
    else:
        card["status"] = "valid"
        _log(state, "  STEP 3  strict-valid")
    state["current"] = card
    return state


def write_letter(state: GraphState) -> GraphState:
    """Step 4a — Cursor letter from the posting; template fallback if the agent fails."""
    card = dict(state.get("current") or {})
    job = _card_to_job(card)
    role = role_label(job)
    loc = location_clause(job)
    template = pick_letter(job)
    body = ""
    kind = template.name
    if role and not state.get("no_agent"):
        try:
            from job_hunter.agent_letter import agent_enabled, write_cover_letter

            if agent_enabled():
                _log(state, f"  STEP 4  Cursor agent writing letter for {role} @ {card.get('company')}…")
                body = write_cover_letter(
                    company=card.get("company") or "",
                    role=role,
                    location=card.get("location") or "",
                    summary=card.get("excerpt") or "",
                    skills=card.get("skills") or "",
                    apply_url=card.get("url") or "",
                )
                kind = "cursor-agent"
        except Exception as exc:  # noqa: BLE001
            _log(state, f"  agent fallback: {exc}")
            body = ""
    if not body:
        body = render_body(
            template.read_text(encoding="utf-8"),
            card.get("company") or "",
            role=role,
            location_clause=loc,
            letter_name=template.name,
        )
        kind = template.name
    card["letter"] = body
    card["letter_kind"] = kind
    card["title"] = role
    _log(state, f"  STEP 4  letter ready  [{kind}]")
    state["current"] = card
    return state


def deliver(state: GraphState) -> GraphState:
    """Step 4b — send resume + letter, or dry-run."""
    card = dict(state.get("current") or {})
    email = card.get("email") or ""
    company = card.get("company") or ""
    body = card.get("letter") or ""
    role = card.get("title") or ""
    if not state.get("send"):
        card["status"] = "dry-run"
        _log(state, f"  DRY-RUN  would send to {email}  [{card.get('letter_kind')}]")
        state.setdefault("results", []).append(card)
        state["current"] = card
        return state
    try:
        import smtplib
        import ssl

        from send_emails import APP_PASSWORD, FROM_EMAIL

        context = ssl.create_default_context()
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as smtp:
            smtp.starttls(context=context)
            smtp.login(FROM_EMAIL, APP_PASSWORD)
            send_via_smtp(
                smtp,
                to_email=email,
                company=company,
                body=body,
                resume=DEFAULT_RESUME,
                role=role,
            )
        log_sent(email, company, "sent", letter=card.get("letter_kind") or "")
        card["status"] = "sent"
        state["sent_count"] = int(state.get("sent_count") or 0) + 1
        _log(state, f"  SENT  {email}  [{card.get('letter_kind')}]")
        delay = float(state.get("delay") or 90)
        if delay > 0:
            wait = max(45.0, delay + random.uniform(-15, 25))
            _log(state, f"    waiting {wait:.0f}s…")
            time.sleep(wait)
    except Exception as exc:  # noqa: BLE001
        log_sent(email, company, "failed", str(exc), letter=card.get("letter_kind") or "")
        card["status"] = "failed"
        card["reason"] = str(exc)[:200]
        _log(state, f"  FAIL  {email}  {exc}")
    state.setdefault("results", []).append(card)
    state["current"] = card
    return state


def skip(state: GraphState) -> GraphState:
    card = dict(state.get("current") or {})
    reason = card.get("reason") or card.get("status") or "skip"
    line = f"  SKIP  {card.get('company')}  {reason}"
    state.setdefault("skipped", []).append(line)
    state.setdefault("results", []).append(card)
    return state


def route_pick(state: GraphState) -> str:
    return "done" if state.get("done") else "find_email"


def route_email(state: GraphState) -> str:
    if (state.get("current") or {}).get("email"):
        return "validate_email"
    return "skip"


def route_validate(state: GraphState) -> str:
    if (state.get("current") or {}).get("status") == "valid":
        return "write_letter"
    return "skip"
