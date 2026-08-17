"""Scrape a company's careers/jobs pages for real SWE/AI/product postings."""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from job_hunter.emails import _scrape_contact_emails, pick_hr_email
from job_hunter.experience import classify_experience, is_junior_keepable
from job_hunter.http import HttpClient
from job_hunter.matcher import is_keepable, score_job
from job_hunter.models import Job
from job_hunter.textutil import extract_emails, html_to_text

CAREER_PATHS = (
    "/careers",
    "/jobs",
    "/join-us",
    "/join",
    "/work-with-us",
    "/opportunities",
    "/openings",
    "/vacancies",
    "/hiring",
    "/career",
    "/en/careers",
    "/community/jobs",
    "/careers/karachi",
    "/careers/lahore",
    "/careers/islamabad",
    "/jobs/karachi",
)

TITLE_RE = re.compile(
    r"\b(?:engineers?|developers?|programmers?)\b",
    re.I,
)
NOISE_TITLE = re.compile(
    r"^(?:careers?|jobs?|openings?|vacancies|opportunities|join us|"
    r"work with us|see all|view all|all jobs|current openings|"
    r"life at|our teams?|benefits|apply now|read more|learn more|"
    r"developers?|for developers|developer newsletter|developer schools?)$",
    re.I,
)
BAD_TITLE = re.compile(
    r"^(?:which|explore|i['’]?m|i am|track|subscribe|output-arrow)\b|"
    r"as a service|job opportunit|opportunities in|"
    r"which llm|llm to use|llm gateway|llm evaluations|"
    r"react to any|react renderer|react hooks|react native|"
    r"triggering python|powering insurance|learn more|"
    r"relations|evangelist|advocate|"
    r"forrester|marketscape|wave™|whitepaper|ebook|webinar|newsletter|"
    r"low-code development platforms|"
    r"developer (?:tools|hub|program|information|overview|portal|newsletter)|"
    r"join \d|documentation admin|maintenance engineer|"
    r"solutions engineer|customer engineer",
    re.I,
)
ROLE_RE = re.compile(
    r"\b(?:engineer|developer|programmer)\b",
    re.I,
)
JUNK_PATH = re.compile(
    r"/(?:blog|docs|documentation|pricing|about|login|signup|privacy|"
    r"cookie|press|news|events|resources|customers?|case-stud|"
    r"product|platform|solutions?|features?)/?",
    re.I,
)
JOBISH_URL = re.compile(
    r"job|career|opening|position|lever|greenhouse|ashby|workable|recruitee",
    re.I,
)
JUNK_EMAIL_LOCAL = {
    "sales",
    "support",
    "security",
    "privacy",
    "legal",
    "press",
    "media",
    "billing",
    "noreply",
    "no-reply",
    "donotreply",
    "ping",
    "sentry",
}
GREENHOUSE_RE = re.compile(
    r"(?:boards(?:-api)?|job-boards)\.greenhouse\.io/([a-z0-9\-]+)",
    re.I,
)
LEVER_RE = re.compile(r"jobs\.lever\.co/([a-z0-9\-]+)", re.I)
ASHBY_RE = re.compile(r"jobs\.ashbyhq\.com/([A-Za-z0-9_\-]+)", re.I)
WORKABLE_RE = re.compile(r"apply\.workable\.com/([a-z0-9\-]+)", re.I)
RECRUITEE_RE = re.compile(r"([a-z0-9\-]+)\.recruitee\.com", re.I)
CAREER_LINK_RE = re.compile(
    r"career|jobs?|join[- ]?us|openings?|vacancies|hiring|"
    r"work[- ]with[- ]us|opportunit|we[- ]are[- ]hiring",
    re.I,
)
ATS_HOST_RE = re.compile(
    r"greenhouse\.io|lever\.co|ashbyhq\.com|workable\.com|"
    r"recruitee\.com|teamtailor\.com|bamboohr\.com|"
    r"smartrecruiters\.com|myworkdayjobs\.com|jobvite\.com",
    re.I,
)
SOFT_NAME = re.compile(
    r"(tech|soft|dev|digital|solutions|systems|studio|labs|cloud|data|code|software|ai\b|app)",
    re.I,
)


def _abs(base: str, href: str) -> str:
    if not href or href.startswith(("mailto:", "tel:", "javascript:")):
        return ""
    return urljoin(base, href.split("#")[0])


def _host(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _keep_url(url: str, domain: str) -> bool:
    if not url or not url.startswith("http"):
        return False
    host = _host(url)
    if not host or host.endswith(("facebook.com", "linkedin.com", "twitter.com", "instagram.com", "youtube.com")):
        return False
    if host == domain or host.endswith("." + domain):
        return True
    return bool(ATS_HOST_RE.search(host))


def _career_urls_from(html: str, page_url: str, domain: str) -> list[str]:
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    found: list[str] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        text = a.get_text(" ", strip=True)
        href = a["href"]
        if not (CAREER_LINK_RE.search(text) or CAREER_LINK_RE.search(href.split("?")[0])):
            continue
        url = _abs(page_url, href)
        if not _keep_url(url, domain) or url in seen:
            continue
        seen.add(url)
        found.append(url)
    return found


def _clean_title(text: str) -> str:
    title = re.sub(r"\s+", " ", (text or "")).strip(" -|·•")
    title = re.sub(r"\s*[•·|]\s*(?:full[- ]time|part[- ]time|contract).*$", "", title, flags=re.I)
    loc_m = re.search(
        r"\s*[•·|]\s*(Stockholm|London|Berlin|Amsterdam|Dublin|Paris|Munich|"
        r"New York|NYC|San Francisco|Toronto|Austin|Boston|Seattle|Remote|"
        r"Karachi|Lahore|Islamabad|Dubai|Riyadh)\b.*$",
        title,
        re.I,
    )
    if loc_m:
        title = title[: loc_m.start()].strip(" -|·•,")
    if len(title) < 8 or len(title) > 80:
        return ""
    if NOISE_TITLE.match(title) or BAD_TITLE.search(title):
        return ""
    if re.search(r"\b(?:senior|staff|principal|director|head of|lead)\b", title, re.I):
        return ""
    if not TITLE_RE.search(title):
        return ""
    if title.lower().count(" ") >= 12:
        return ""
    return title


def _title_location(text: str) -> tuple[str, str]:
    loc = ""
    mode = "unknown"
    blob = text or ""
    m = re.search(
        r"\b(Stockholm|London|Berlin|Amsterdam|Dublin|Paris|Munich|"
        r"New York|NYC|San Francisco|Toronto|Austin|Boston|Seattle|Remote|"
        r"Karachi|Lahore|Islamabad|Dubai|Riyadh)\b",
        blob,
        re.I,
    )
    if m:
        loc = m.group(1)
        if loc.lower() == "remote" or re.search(r"\bremote\b", blob, re.I):
            mode = "remote"
        elif loc.lower() in {"karachi", "lahore", "islamabad"}:
            mode = "unknown"
        else:
            mode = "onsite"
    elif re.search(r"\bremote\b", blob, re.I):
        loc = "Remote"
        mode = "remote"
    return loc, mode


def _jsonld_jobs(html: str, company: str, domain: str, page_url: str) -> list[Job]:
    jobs: list[Job] = []
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = (tag.string or tag.get_text() or "").strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        items = data if isinstance(data, list) else [data]
        graph = []
        for item in items:
            if isinstance(item, dict) and "@graph" in item:
                graph.extend(item.get("@graph") or [])
            else:
                graph.append(item)
        for item in graph:
            if not isinstance(item, dict):
                continue
            types = item.get("@type") or ""
            type_s = " ".join(types) if isinstance(types, list) else str(types)
            if "jobposting" not in type_s.lower():
                continue
            title = _clean_title(item.get("title") or "")
            if not title:
                continue
            desc = html_to_text(item.get("description") or "")
            url = str(item.get("url") or page_url)
            loc = ""
            job_loc = item.get("jobLocation") or {}
            if isinstance(job_loc, list) and job_loc:
                job_loc = job_loc[0]
            if isinstance(job_loc, dict):
                addr = job_loc.get("address") or {}
                if isinstance(addr, dict):
                    loc = " ".join(
                        str(addr.get(k) or "")
                        for k in ("addressLocality", "addressRegion", "addressCountry")
                    ).strip()
            jobs.append(
                Job(
                    source="career-page",
                    source_id=url or f"{domain}:{title}",
                    title=title,
                    company=company,
                    url=url,
                    location=loc,
                    work_mode="remote" if "remote" in (loc + " " + desc).lower() else "unknown",
                    description=desc[:4000],
                    excerpt=desc[:280],
                    company_domain=domain,
                )
            )
    return jobs


def _link_jobs(html: str, company: str, domain: str, page_url: str) -> list[Job]:
    jobs: list[Job] = []
    soup = BeautifulSoup(html, "lxml")
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        raw = a.get_text(" ", strip=True)
        title = _clean_title(raw)
        if not title:
            continue
        href = _abs(page_url, a["href"])
        if not href:
            continue
        path = urlparse(href).path or ""
        if JUNK_PATH.search(path):
            continue
        if not JOBISH_URL.search(href) and not JOBISH_URL.search(path):
            continue
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)
        loc, mode = _title_location(raw)
        jobs.append(
            Job(
                source="career-page",
                source_id=href or f"{domain}:{title}",
                title=title,
                company=company,
                url=href,
                location=loc,
                work_mode=mode,
                description="",
                excerpt="",
                company_domain=domain,
            )
        )
    return jobs


def _ats_tokens(html: str, page_url: str) -> dict[str, set[str]]:
    blob = html + " " + page_url
    return {
        "greenhouse": set(GREENHOUSE_RE.findall(blob)),
        "lever": set(LEVER_RE.findall(blob)),
        "ashby": set(ASHBY_RE.findall(blob)),
        "workable": set(WORKABLE_RE.findall(blob)),
        "recruitee": set(RECRUITEE_RE.findall(blob)),
    }


def _fetch_greenhouse(token: str, company: str, domain: str) -> list[Job]:
    local = HttpClient(timeout=10.0)
    try:
        data = local.get_json(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs")
    except Exception:
        return []
    finally:
        local.close()
    jobs: list[Job] = []
    for item in data.get("jobs") or []:
        title = _clean_title(item.get("title") or "")
        if not title:
            continue
        loc = ((item.get("location") or {}).get("name") or "").strip()
        url = item.get("absolute_url") or ""
        jobs.append(
            Job(
                source=f"Greenhouse/{token}",
                source_id=str(item.get("id") or url),
                title=title,
                company=company,
                url=url,
                location=loc,
                work_mode="remote" if "remote" in loc.lower() else "unknown",
                company_domain=domain,
            )
        )
    return jobs


def _fetch_lever(token: str, company: str, domain: str) -> list[Job]:
    local = HttpClient(timeout=10.0)
    try:
        listings = local.get_json(f"https://api.lever.co/v0/postings/{token}?mode=json")
    except Exception:
        return []
    finally:
        local.close()
    if not isinstance(listings, list):
        return []
    jobs: list[Job] = []
    for item in listings:
        title = _clean_title(item.get("text") or "")
        if not title:
            continue
        cats = item.get("categories") or {}
        loc = cats.get("location") or ""
        jobs.append(
            Job(
                source=f"Lever/{token}",
                source_id=str(item.get("id") or ""),
                title=title,
                company=company,
                url=item.get("hostedUrl") or item.get("applyUrl") or "",
                location=loc,
                work_mode="remote" if "remote" in loc.lower() else "unknown",
                description=html_to_text(item.get("descriptionPlain") or "")[:4000],
                company_domain=domain,
            )
        )
    return jobs


def _fetch_ashby(token: str, company: str, domain: str) -> list[Job]:
    local = HttpClient(timeout=10.0)
    try:
        data = local.get_json(f"https://api.ashbyhq.com/posting-api/job-board/{token}")
    except Exception:
        return []
    finally:
        local.close()
    jobs: list[Job] = []
    for item in data.get("jobs") or []:
        title = _clean_title(item.get("title") or "")
        if not title:
            continue
        loc = item.get("location") or ""
        if isinstance(loc, dict):
            loc = loc.get("locationName") or loc.get("name") or ""
        jobs.append(
            Job(
                source=f"Ashby/{token}",
                source_id=str(item.get("id") or item.get("jobUrl") or ""),
                title=title,
                company=company,
                url=item.get("jobUrl") or "",
                location=str(loc),
                work_mode="remote" if "remote" in str(loc).lower() else "unknown",
                company_domain=domain,
            )
        )
    return jobs


def _fetch_workable(token: str, company: str, domain: str) -> list[Job]:
    local = HttpClient(timeout=10.0)
    try:
        data = local.get_json(f"https://apply.workable.com/api/v1/widget/accounts/{token}")
    except Exception:
        return []
    finally:
        local.close()
    jobs: list[Job] = []
    for item in data.get("jobs") or []:
        title = _clean_title(item.get("title") or "")
        if not title:
            continue
        locs = item.get("locations") or []
        loc = ""
        if locs and isinstance(locs[0], dict):
            loc = locs[0].get("city") or locs[0].get("country") or ""
        elif isinstance(locs, list):
            loc = " ".join(str(x) for x in locs[:2])
        url = item.get("application_url") or item.get("url") or ""
        jobs.append(
            Job(
                source=f"Workable/{token}",
                source_id=str(item.get("shortcode") or url),
                title=title,
                company=company,
                url=url,
                location=str(loc),
                work_mode="remote" if "remote" in str(loc).lower() else "unknown",
                company_domain=domain,
            )
        )
    return jobs


def _fetch_recruitee(token: str, company: str, domain: str) -> list[Job]:
    local = HttpClient(timeout=10.0)
    try:
        data = local.get_json(f"https://{token}.recruitee.com/api/offers")
    except Exception:
        return []
    finally:
        local.close()
    jobs: list[Job] = []
    for item in data.get("offers") or []:
        title = _clean_title(item.get("title") or "")
        if not title:
            continue
        loc = item.get("location") or item.get("city") or ""
        if isinstance(loc, dict):
            loc = loc.get("city") or loc.get("name") or ""
        url = item.get("careers_url") or item.get("url") or ""
        jobs.append(
            Job(
                source=f"Recruitee/{token}",
                source_id=str(item.get("id") or url),
                title=title,
                company=company,
                url=url,
                location=str(loc),
                work_mode="remote" if "remote" in str(loc).lower() else "unknown",
                description=html_to_text(item.get("description") or "")[:4000],
                company_domain=domain,
            )
        )
    return jobs


def _usable_emails(emails: list[str], domain: str) -> list[str]:
    kept: list[str] = []
    for raw in emails:
        email = (raw or "").strip().lower()
        if "@" not in email:
            continue
        local, _, host = email.partition("@")
        local = re.sub(r"^(?:u003[ec])+", "", local)
        if "sentry" in host or host.endswith(("example.com", "wixpress.com")):
            continue
        if not re.fullmatch(r"[a-z][a-z0-9._%+\-]{0,40}", local):
            continue
        if local in JUNK_EMAIL_LOCAL:
            continue
        if host == domain or host.endswith("." + domain):
            kept.append(email)
            continue
        if any(tok in local for tok in ("hr", "career", "recruit", "talent", "hiring", "job")):
            kept.append(email)
    return list(dict.fromkeys(kept))


def scrape_company_careers(
    name: str,
    domain: str,
    known_emails: tuple[str, ...] | list[str] = (),
) -> tuple[list[Job], list[str]]:
    """Return (jobs, published emails) from the company's careers/contact pages."""
    client = HttpClient(timeout=8.0)
    jobs: list[Job] = []
    emails = [e.strip().lower() for e in known_emails if e and "@" in e]
    ats: dict[str, set[str]] = {
        "greenhouse": set(),
        "lever": set(),
        "ashby": set(),
        "workable": set(),
        "recruitee": set(),
    }
    tried: set[str] = set()

    def visit(url: str) -> str:
        key = url.rstrip("/").lower()
        if key in tried:
            return ""
        tried.add(key)
        html = client.get_html(url)
        if not html:
            return ""
        found = _ats_tokens(html, url)
        for key_name in ats:
            ats[key_name] |= found[key_name]
        jobs.extend(_jsonld_jobs(html, name, domain, url))
        jobs.extend(_link_jobs(html, name, domain, url))
        for email in extract_emails(html_to_text(html) + " " + html):
            host = email.split("@")[-1]
            if host == domain or host.endswith("." + domain):
                emails.append(email)
        return html

    try:
        home = f"https://www.{domain}/"
        home_html = visit(home)
        if not home_html:
            home = f"https://{domain}/"
            home_html = visit(home)
        queue: list[str] = _career_urls_from(home_html, home, domain)
        for path in CAREER_PATHS:
            queue.append(f"https://www.{domain}{path}")
            queue.append(f"https://{domain}{path}")
        seen_q: set[str] = set()
        ordered: list[str] = []
        for url in queue:
            if not _keep_url(url, domain):
                continue
            key = url.rstrip("/").lower()
            if key in seen_q:
                continue
            seen_q.add(key)
            ordered.append(url)
        for url in ordered:
            if len(tried) >= 12:
                break
            html = visit(url)
            if not html:
                continue
            for more in _career_urls_from(html, url, domain)[:4]:
                key = more.rstrip("/").lower()
                if key in seen_q or not _keep_url(more, domain):
                    continue
                seen_q.add(key)
                ordered.append(more)
        if jobs and not emails:
            emails.extend(_scrape_contact_emails(client, domain, max_pages=4))
    finally:
        client.close()

    for token in list(ats["greenhouse"])[:2]:
        jobs.extend(_fetch_greenhouse(token, name, domain))
    for token in list(ats["lever"])[:2]:
        jobs.extend(_fetch_lever(token, name, domain))
    for token in list(ats["ashby"])[:2]:
        jobs.extend(_fetch_ashby(token, name, domain))
    for token in list(ats["workable"])[:2]:
        jobs.extend(_fetch_workable(token, name, domain))
    for token in list(ats["recruitee"])[:2]:
        jobs.extend(_fetch_recruitee(token, name, domain))
    usable_now = _usable_emails(emails, domain)
    if not jobs and usable_now:
        slug = re.sub(r"[^a-z0-9]+", "", (domain.split(".")[0] or ""))
        if slug:
            jobs.extend(_fetch_greenhouse(slug, name, domain))
            jobs.extend(_fetch_lever(slug, name, domain))
            jobs.extend(_fetch_ashby(slug, name, domain))

    best: dict[str, Job] = {}
    for job in jobs:
        job.company_domain = domain
        score_job(job)
        if job.score < 6 and TITLE_RE.search(job.title or ""):
            job.score = 6
        classify_experience(job)
        if not is_junior_keepable(job, strict=False):
            continue
        if not is_keepable(
            job,
            include_restricted=False,
            karachi_only=False,
            pakistan_friendly_only=False,
            junior_only=True,
        ):
            continue
        key = job.dedupe_key
        existing = best.get(key)
        if existing is None or job.score > existing.score:
            best[key] = job
    return list(best.values()), _usable_emails(emails, domain)


def scrape_directory_careers(
    *,
    skip_companies: set[str] | None = None,
    skip_domains: set[str] | None = None,
    limit: int = 40,
) -> list[Job]:
    """Walk unsent directory companies, scrape careers pages, return junior SWE jobs."""
    from job_hunter.directory import COMPANY_DIRECTORY

    skip_companies = {c.lower() for c in (skip_companies or set())}
    skip_domains = {d.lower() for d in (skip_domains or set())}
    with_email: list[tuple[str, str, str, tuple[str, ...]]] = []
    without: list[tuple[str, str, str, tuple[str, ...]]] = []
    for name, domain, region, _city, known in COMPANY_DIRECTORY:
        d = (domain or "").lower()
        if not d or d in skip_domains or name.strip().lower() in skip_companies:
            continue
        if not SOFT_NAME.search(name) and not SOFT_NAME.search(d):
            continue
        if any(k in name.lower() for k in ("bank", "telenor", "ufone", "zong", "ptcl")):
            continue
        item = (name, d, region, tuple(e for e in known if e))
        if item[3]:
            with_email.append(item)
        else:
            without.append(item)
    probe = min(90, max(limit * 6, 60))
    targets = with_email[:probe] + without[: max(0, probe - len(with_email[:probe]))]
    print(
        f"Scraping careers pages for {len(targets)} unsent software companies "
        f"({len(with_email[:probe])} already have a published email)…",
        flush=True,
    )
    found: list[Job] = []

    def one(item: tuple[str, str, str, tuple[str, ...]]) -> list[Job]:
        name, domain, region, known = item
        jobs, emails = scrape_company_careers(name, domain, known)
        email = pick_hr_email(emails)
        kept: list[Job] = []
        for job in jobs:
            if not job.location:
                job.location = region
            if email:
                job.emails = list(dict.fromkeys([email, *emails, *job.emails]))
                job.hr_email = email
                job.email_source = "company website"
            kept.append(job)
        if jobs:
            titles = ", ".join(j.title[:40] for j in jobs[:3])
            print(f"  HIT {name:28} {len(jobs)} roles  email={email or '-'}  {titles}", flush=True)
        return kept

    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = [pool.submit(one, t) for t in targets]
        for fut in as_completed(futs):
            try:
                found.extend(fut.result())
            except Exception as exc:  # noqa: BLE001
                print(f"  career scrape error: {exc}", flush=True)
    with_mail = sum(1 for j in found if j.hr_email)
    print(
        f"  Career-page junior SWE/AI/product roles: {len(found)}  ({with_mail} with a hiring email)",
        flush=True,
    )
    return found
