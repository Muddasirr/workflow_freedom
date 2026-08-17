from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

import httpx

from job_hunter.config import (
    ATS_DOMAINS,
    GENERIC_HR_LOCAL_PARTS,
    HUNTER_API_KEY,
    PK_COMPANY_DOMAINS,
    PK_CONTACT_PATHS,
    PK_KNOWN_EMAILS,
)
from job_hunter.http import HttpClient
from job_hunter.models import Job
from job_hunter.textutil import domain_from_url, extract_emails, html_to_text


WELL_KNOWN_COMPANY_DOMAINS = {
    "canonical": "canonical.com",
    "canonical ltd.": "canonical.com",
    "canonical ltd": "canonical.com",
    "vercel": "vercel.com",
    "toptal": "toptal.com",
    "gitlab": "gitlab.com",
    "binance": "binance.com",
    "twilio": "twilio.com",
    "stripe": "stripe.com",
    "tamara": "tamara.co",
    "celonis": "celonis.com",
    "turing": "turing.com",
    "careem": "careem.com",
    "sticker mule": "stickermule.com",
    "doximity": "doximity.com",
    "hightouch": "hightouch.com",
    "maptiler": "maptiler.com",
    "onthegosystems": "onthegosystems.com",
    "on the go systems": "onthegosystems.com",
    "saas.group": "saas.group",
    "dbt labs": "getdbt.com",
    "linear": "linear.app",
    "lovable": "lovable.dev",
    "trigger.dev": "trigger.dev",
    "codecov": "codecov.io",
    "outsystems": "outsystems.com",
    "tractable": "tractable.ai",
    "mustakbil tech": "mustakbil.com",
    "mustakbil": "mustakbil.com",
}


def pick_hr_email(emails: list[str]) -> str:
    if not emails:
        return ""
    ranked: list[tuple[int, str]] = []
    for email in emails:
        local, _, domain = email.partition("@")
        score = 0
        if any(j in local for j in ("accommodation", "accomodation", "paytransparency", "noreply")):
            score -= 50
        if local in {
            "pr",
            "press",
            "media",
            "help",
            "support",
            "sales",
            "bd",
            "billing",
            "security",
            "partners",
            "legal",
        }:
            score -= 80
        if local in GENERIC_HR_LOCAL_PARTS:
            score += 20
        if any(token in local for token in ("hr", "recruit", "talent", "career", "hiring", "people", "job")):
            score += 12
        if local in {"hello", "contact", "info", "admin"}:
            score += 4
        ranked.append((score, email))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return ranked[0][1]


def resolve_company_domain(job: Job) -> str:
    existing = (job.company_domain or "").strip().lower()
    if existing and not _is_ats_domain(existing):
        return existing
    name = re.sub(r"[\s,]+ltd\.?$", "", (job.company or "").strip(), flags=re.I).strip().lower()
    name = re.sub(r"\s+", " ", name)
    if name in PK_COMPANY_DOMAINS:
        return PK_COMPANY_DOMAINS[name]
    for key, domain in PK_COMPANY_DOMAINS.items():
        if key in name or name in key:
            return domain
    if name in WELL_KNOWN_COMPANY_DOMAINS:
        return WELL_KNOWN_COMPANY_DOMAINS[name]
    try:
        from job_hunter.directory import COMPANY_DIRECTORY

        for listed, domain, *_rest in COMPANY_DIRECTORY:
            listed_n = listed.strip().lower()
            if listed_n == name or listed_n == (job.company or "").strip().lower():
                return domain
    except Exception:
        pass
    url = job.url or ""
    slug = ""
    m = re.search(r"greenhouse\.io/([a-z0-9\-]+)", url, re.I)
    if m:
        slug = m.group(1).lower()
    m = re.search(r"jobs\.lever\.co/([a-z0-9\-]+)", url, re.I)
    if m:
        slug = m.group(1).lower()
    if slug and slug in WELL_KNOWN_COMPANY_DOMAINS:
        return WELL_KNOWN_COMPANY_DOMAINS[slug]
    return domain_from_url(url)


def attach_known_emails(job: Job) -> None:
    if job.hr_email and job.email_source not in {"", "guessed pattern (verify before sending)"}:
        return
    domain = resolve_company_domain(job)
    if not domain:
        return
    job.company_domain = domain
    known = PK_KNOWN_EMAILS.get(domain) or []
    if not known:
        for host, emails in PK_KNOWN_EMAILS.items():
            if domain.endswith(host) or host.endswith(domain):
                known = emails
                break
    if not known:
        return
    job.emails = list(dict.fromkeys([*known, *job.emails]))
    job.hr_email = pick_hr_email(job.emails)
    job.email_source = "known company contact"


def attach_description_emails(job: Job) -> None:
    blob = f"{html_to_text(job.description)}\n{job.url}\n{job.company}"
    emails = extract_emails(blob)
    if emails:
        job.emails = emails
        job.hr_email = pick_hr_email(emails)
        job.email_source = "job posting"
    if not job.company_domain:
        job.company_domain = resolve_company_domain(job)
    attach_known_emails(job)


def guess_generic_emails(domain: str) -> list[str]:
    if not domain:
        return []
    return [f"{local}@{domain}" for local in ("careers", "hr", "jobs", "talent", "recruiting")]


class HunterClient:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = (api_key or HUNTER_API_KEY).strip()
        self._http = httpx.Client(timeout=25.0) if self.api_key else None
        self._domain_cache: dict[str, list[str]] = {}
        self._company_cache: dict[str, str] = {}

    @property
    def enabled(self) -> bool:
        return bool(self.api_key and self._http)

    def close(self) -> None:
        if self._http:
            self._http.close()

    def enrich(self, job: Job) -> None:
        if job.hr_email or not self.enabled:
            return
        domain = job.company_domain or self._find_domain(job.company)
        if domain:
            job.company_domain = domain
        emails = self._domain_search(domain, job.company)
        if emails:
            job.emails = list(dict.fromkeys([*job.emails, *emails]))
            job.hr_email = pick_hr_email(job.emails)
            job.email_source = "Hunter.io"
            return
        if domain and not job.emails:
            guessed = guess_generic_emails(domain)
            job.emails = guessed
            job.hr_email = guessed[0]
            job.email_source = "guessed pattern (verify before sending)"

    def _find_domain(self, company: str) -> str:
        if not company or not self._http:
            return ""
        key = company.strip().lower()
        if key in self._company_cache:
            return self._company_cache[key]
        try:
            response = self._http.get(
                "https://api.hunter.io/v2/domain-search",
                params={"company": company, "limit": 1, "api_key": self.api_key},
            )
            if response.status_code == 429:
                time.sleep(2)
                return ""
            response.raise_for_status()
            data = response.json().get("data") or {}
            domain = (data.get("domain") or "").lower()
            self._company_cache[key] = domain
            time.sleep(0.35)
            return domain
        except Exception:  # noqa: BLE001
            self._company_cache[key] = ""
            return ""

    def _domain_search(self, domain: str, company: str) -> list[str]:
        if not self._http:
            return []
        cache_key = (domain or company).lower()
        if cache_key in self._domain_cache:
            return self._domain_cache[cache_key]
        params: dict[str, str | int] = {"api_key": self.api_key, "limit": 10}
        if domain:
            params["domain"] = domain
        else:
            params["company"] = company
        emails: list[str] = []
        try:
            response = self._http.get("https://api.hunter.io/v2/domain-search", params=params)
            if response.status_code == 429:
                time.sleep(2)
                return []
            response.raise_for_status()
            payload = response.json().get("data") or {}
            for item in payload.get("emails") or []:
                value = (item.get("value") or "").lower()
                department = (item.get("department") or "").lower()
                position = (item.get("position") or "").lower()
                etype = (item.get("type") or "").lower()
                if not value:
                    continue
                interesting = (
                    etype == "generic"
                    or department in {"hr", "executive", "management"}
                    or any(token in position for token in ("recruit", "talent", "hr", "people", "hiring"))
                )
                if interesting:
                    emails.append(value)
            time.sleep(0.35)
        except Exception:  # noqa: BLE001
            emails = []
        self._domain_cache[cache_key] = emails
        return emails


def fallback_guess(job: Job) -> None:
    if job.hr_email:
        return
    if not job.company_domain:
        job.company_domain = resolve_company_domain(job)
    host = job.company_domain
    if not host:
        return
    if any(host.endswith(d) for d in (".io", ".com", ".co", ".ai", ".dev", ".pk", ".app", ".ltd")):
        guessed = guess_generic_emails(host)
        job.emails = guessed
        job.hr_email = guessed[0]
        job.email_source = "guessed pattern (verify before sending)"


def _is_ats_domain(domain: str) -> bool:
    return any(domain == ats or domain.endswith("." + ats) for ats in ATS_DOMAINS)


def enrich_from_websites(_client: HttpClient, jobs: list[Job], max_sites: int = 80, *, allow_guess: bool = True) -> None:
    """Scrape contact/career pages (and apply URLs) for HR emails."""
    domains: list[str] = []
    seen_domains: set[str] = set()
    for job in jobs:
        domain = resolve_company_domain(job)
        if not domain:
            continue
        job.company_domain = domain
        if _is_ats_domain(domain) or domain in seen_domains:
            continue
        seen_domains.add(domain)
        domains.append(domain)
        if len(domains) >= max_sites:
            break

    cache: dict[str, list[str]] = {}

    def scrape(domain: str) -> tuple[str, list[str]]:
        local = HttpClient()
        try:
            return domain, _scrape_contact_emails(local, domain)
        finally:
            local.close()

    with ThreadPoolExecutor(max_workers=12) as pool:
        futs = [pool.submit(scrape, d) for d in domains]
        for fut in as_completed(futs):
            domain, emails = fut.result()
            cache[domain] = emails

    still_need_page: list[Job] = []
    for job in jobs:
        domain = job.company_domain or resolve_company_domain(job)
        job.company_domain = domain
        emails = cache.get(domain) or []
        if emails:
            job.emails = list(dict.fromkeys([*emails, *job.emails]))
            job.hr_email = pick_hr_email(job.emails)
            job.email_source = "company website"
            continue
        if job.hr_email and job.email_source != "guessed pattern (verify before sending)":
            continue
        if job.url and not _is_ats_domain(domain_from_apply_url(job.url) or ""):
            still_need_page.append(job)
        elif not job.hr_email and allow_guess:
            fallback_guess(job)

    def scrape_job(job: Job) -> tuple[str, list[str]]:
        local = HttpClient()
        try:
            html = local.get_html(job.url)
            return job.url, extract_emails(html_to_text(html) + " " + html) if html else []
        finally:
            local.close()

    page_hits = 0
    with ThreadPoolExecutor(max_workers=10) as pool:
        futs = {pool.submit(scrape_job, job): job for job in still_need_page[:50]}
        for fut in as_completed(futs):
            job = futs[fut]
            _, emails = fut.result()
            useful = [
                e
                for e in emails
                if any(tok in e.split("@")[0] for tok in ("hr", "career", "recruit", "talent", "people", "job", "hello", "contact"))
                or (job.company_domain and e.endswith(job.company_domain))
            ]
            if useful:
                job.emails = list(dict.fromkeys([*useful, *job.emails]))
                job.hr_email = pick_hr_email(job.emails)
                job.email_source = "job posting page"
                page_hits += 1
            elif not job.hr_email and allow_guess:
                fallback_guess(job)
    print(f"  Website domains scraped: {len(cache)}  |  posting pages with email: {page_hits}", flush=True)


def _scrape_contact_emails(client: HttpClient, domain: str, max_pages: int = 6) -> list[str]:
    found: list[str] = []
    tried = 0
    for path in PK_CONTACT_PATHS:
        if tried >= max_pages:
            break
        html = client.get_html(f"https://www.{domain}{path}") or client.get_html(f"https://{domain}{path}")
        tried += 1
        if not html:
            continue
        for email in extract_emails(html_to_text(html) + " " + html):
            host = email.split("@")[-1]
            local = email.split("@")[0]
            if host == domain or host.endswith("." + domain):
                found.append(email)
            elif any(tok in local for tok in ("hr", "career", "recruit", "talent", "people", "hiring", "job")) and host not in {
                "gmail.com",
                "yahoo.com",
                "hotmail.com",
                "outlook.com",
            }:
                found.append(email)
        if any(
            any(tok in e.split("@")[0] for tok in ("hr", "career", "recruit", "talent", "people", "hiring", "job"))
            for e in found
        ):
            break
        if found and path in {"/impressum", "/imprint", "/contact", "/contact-us", "/"}:
            break
    return list(dict.fromkeys(found))


def domain_from_apply_url(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host
