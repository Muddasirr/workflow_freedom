#!/usr/bin/env python3
"""Find relevant junior/associate SWE/FE/AI postings across major boards.

Boards: LinkedIn, Remote OK, We Work Remotely, Rozee.pk, Freehire,
        Wellfound, Dice, Remotive, Arbeitnow, Himalayas, Jobicy.

Output: output/job_findings_<date>.json + stdout summary.
Does NOT send email.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from urllib.parse import quote_plus

import httpx

ROOT = Path(__file__).resolve().parents[1]
AIJS = ROOT / "ai-job-search"
sys.path.insert(0, str(ROOT))

from job_hunter.experience import role_ok_for_junior  # noqa: E402

OUT = ROOT / "output" / f"job_findings_{date.today().isoformat()}.json"
LI_CLI = AIJS / ".agents/skills/linkedin-search/cli/src/cli.ts"
FH_CLI = AIJS / ".agents/skills/freehire-search/cli/src/cli.ts"

UA = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/json,application/rss+xml,*/*",
}

STACK = re.compile(
    r"\b(react|next\.?js|typescript|frontend|front.?end|full.?stack|"
    r"software engineer|software developer|ai engineer|llm|python|"
    r"node\.?js|product engineer|web developer)\b",
    re.I,
)
SENIOR = re.compile(
    r"\b(senior|staff|principal|lead |manager|director|architect|"
    r"l[4-9]\b|iii\b|iv\b|5\+|4\+|3\+ years|10\+ years)\b",
    re.I,
)
GEO_BAD = re.compile(
    r"\b(onsite only|must (?:be|relocate).{0,40}(us|usa|united states|canada|australia)|"
    r"us citizen|green card|security clearance)\b",
    re.I,
)


def keep(title: str, company: str, location: str = "", tags: str = "") -> bool:
    blob = f"{title} {company} {location} {tags}"
    if not title or not company:
        return False
    if SENIOR.search(title):
        return False
    if not STACK.search(blob):
        return False
    if not role_ok_for_junior(title):
        return False
    if GEO_BAD.search(blob) and not re.search(r"\bremote\b", blob, re.I):
        return False
    return True


def score(job: dict) -> int:
    t = (job.get("title") or "").lower()
    loc = (job.get("location") or "").lower()
    tags = (job.get("tags") or "").lower()
    blob = f"{t} {loc} {tags}"
    s = 0
    if re.search(r"junior|associate|entry|engineer i\b|new grad", t):
        s += 12
    if "frontend" in t or "react" in t or "next" in t:
        s += 8
    if "full stack" in t or "fullstack" in t:
        s += 7
    if "ai" in t or "llm" in t:
        s += 7
    if "karachi" in loc or "pakistan" in loc:
        s += 10
    if "remote" in loc or "remote" in tags:
        s += 6
    if "typescript" in blob or "next" in blob:
        s += 3
    return s


def _client() -> httpx.Client:
    return httpx.Client(headers=UA, timeout=40.0, follow_redirects=True)


def _li(query: str, location: str, limit: int = 10) -> list[dict]:
    cmd = [
        "bun",
        "run",
        str(LI_CLI),
        "search",
        "-q",
        query,
        "-l",
        location,
        "--limit",
        str(limit),
        "--jobage",
        "30",
        "--format",
        "json",
    ]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=90, cwd=str(AIJS))
        if p.returncode != 0:
            return []
        data = json.loads(p.stdout)
        return list(data.get("results") or [])
    except Exception:
        return []


def find_linkedin() -> list[dict]:
    out: list[dict] = []
    queries = [
        ("junior software engineer", "Remote"),
        ("junior software engineer", "Karachi, Pakistan"),
        ("associate software engineer", "Pakistan"),
        ("frontend engineer react", "Remote"),
        ("full stack engineer", "Remote"),
        ("AI engineer", "Karachi, Pakistan"),
        ("AI engineer", "Remote"),
        ("react developer", "Pakistan"),
        ("software engineer I", "Remote"),
        ("Next.js developer", "Remote"),
    ]
    seen: set[str] = set()
    for q, loc in queries:
        for r in _li(q, loc, 10):
            title = (r.get("title") or "").strip()
            company = (r.get("company") or "").strip()
            location = str(r.get("location") or loc)
            key = f"{company}|{title}".lower()
            if key in seen:
                continue
            if not keep(title, company, location):
                continue
            seen.add(key)
            out.append(
                {
                    "source": "linkedin",
                    "title": title,
                    "company": company,
                    "location": location,
                    "url": r.get("url") or "",
                    "tags": "",
                    "posted": r.get("date") or "",
                }
            )
    return out


def find_remoteok() -> list[dict]:
    out: list[dict] = []
    try:
        with _client() as client:
            r = client.get("https://remoteok.com/api")
            r.raise_for_status()
            rows = r.json()
    except Exception as exc:
        print(f"  remoteok fail: {exc}", flush=True)
        return out
    for row in rows:
        if not isinstance(row, dict) or not row.get("id") or row.get("id") == "legal":
            continue
        title = (row.get("position") or row.get("title") or "").strip()
        company = (row.get("company") or "").strip()
        tags = " ".join(str(t) for t in (row.get("tags") or []))
        location = (row.get("location") or "Remote").strip() or "Remote"
        if not keep(title, company, location, tags):
            continue
        url = row.get("url") or row.get("apply_url") or ""
        if url and not str(url).startswith("http"):
            url = f"https://remoteok.com/remote-jobs/{row.get('id')}"
        out.append(
            {
                "source": "remoteok",
                "title": title,
                "company": company,
                "location": location,
                "url": url or f"https://remoteok.com/remote-jobs/{row.get('id')}",
                "tags": tags,
                "posted": str(row.get("date") or ""),
                "salary": row.get("salary") or "",
            }
        )
    return out


def find_wwr() -> list[dict]:
    out: list[dict] = []
    feeds = [
        "https://weworkremotely.com/categories/remote-programming-jobs.rss",
        "https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss",
        "https://weworkremotely.com/categories/remote-front-end-programming-jobs.rss",
    ]
    try:
        with _client() as client:
            for feed in feeds:
                try:
                    r = client.get(feed)
                    r.raise_for_status()
                except Exception:
                    continue
                try:
                    root = ET.fromstring(r.text)
                except ET.ParseError:
                    continue
                for item in root.findall(".//item"):
                    title_raw = (item.findtext("title") or "").strip()
                    link = (item.findtext("link") or "").strip()
                    if ": " in title_raw:
                        company, title = title_raw.split(": ", 1)
                    else:
                        company, title = "Unknown", title_raw
                    company, title = company.strip(), title.strip()
                    if not keep(title, company, "Remote"):
                        continue
                    out.append(
                        {
                            "source": "weworkremotely",
                            "title": title,
                            "company": company,
                            "location": "Remote",
                            "url": link,
                            "tags": "",
                            "posted": (item.findtext("pubDate") or "").strip(),
                        }
                    )
    except Exception as exc:
        print(f"  wwr fail: {exc}", flush=True)
    return out


def find_rozee() -> list[dict]:
    out: list[dict] = []
    queries = [
        "software engineer",
        "react developer",
        "full stack developer",
        "frontend developer",
        "ai engineer",
        "junior software engineer",
    ]
    try:
        with _client() as client:
            for q in queries:
                url = f"https://www.rozee.pk/job/jsearch/q/{quote_plus(q)}"
                try:
                    r = client.get(url)
                    if r.status_code >= 400:
                        continue
                    html = r.text
                except Exception:
                    continue
                for m in re.finditer(
                    r'href="(https://www\.rozee\.pk/job/[a-z0-9\-]+-\d+)"[^>]*>\s*([^<]{6,100})\s*<',
                    html,
                    re.I,
                ):
                    link, title = m.group(1), " ".join(m.group(2).split())
                    company = "Rozee listing"
                    window = html[max(0, m.start() - 200) : m.end() + 500]
                    cm = re.search(r"(?:company|employer)[^>]*>\s*([^<]{2,60})", window, re.I)
                    if cm:
                        company = " ".join(cm.group(1).split())
                    if not keep(title, company, "Pakistan"):
                        continue
                    out.append(
                        {
                            "source": "rozee.pk",
                            "title": title,
                            "company": company,
                            "location": "Pakistan",
                            "url": link,
                            "tags": q,
                            "posted": "",
                        }
                    )
    except Exception as exc:
        print(f"  rozee fail: {exc}", flush=True)
    seen: set[str] = set()
    uniq = []
    for j in out:
        if j["url"] in seen:
            continue
        seen.add(j["url"])
        uniq.append(j)
    return uniq


def find_freehire() -> list[dict]:
    out: list[dict] = []
    if not FH_CLI.exists():
        return out
    queries = ["software engineer", "frontend react", "full stack", "AI engineer"]
    for q in queries:
        cmd = [
            "bun",
            "run",
            str(FH_CLI),
            "search",
            "-q",
            q,
            "--jobage",
            "30",
            "--limit",
            "15",
            "--format",
            "json",
        ]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=str(AIJS))
            if p.returncode != 0:
                continue
            data = json.loads(p.stdout)
            for r in data.get("results") or []:
                title = (r.get("title") or "").strip()
                company = (r.get("company") or "").strip()
                location = str(r.get("location") or "Remote")
                if not keep(title, company, location):
                    continue
                out.append(
                    {
                        "source": "freehire",
                        "title": title,
                        "company": company,
                        "location": location,
                        "url": r.get("url") or "",
                        "tags": "",
                        "posted": "",
                    }
                )
        except Exception:
            continue
    return out


def find_wellfound() -> list[dict]:
    """Parse Wellfound Apollo cache from role listing pages."""
    out: list[dict] = []
    urls = [
        "https://wellfound.com/role/l/software-engineer/remote",
        "https://wellfound.com/role/l/frontend-engineer/remote",
        "https://wellfound.com/role/l/full-stack-engineer/remote",
        "https://wellfound.com/role/l/ai-engineer/remote",
        "https://wellfound.com/role/l/react-developer/remote",
    ]
    try:
        with _client() as client:
            for url in urls:
                try:
                    r = client.get(url)
                    if r.status_code >= 400:
                        continue
                    m = re.search(
                        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
                        r.text,
                        re.S,
                    )
                    if not m:
                        continue
                    apollo = json.loads(m.group(1))["props"]["pageProps"]["apolloState"]["data"]
                except Exception:
                    continue
                job_co: dict[str, tuple[str, str]] = {}
                for k, v in apollo.items():
                    if not k.startswith("StartupResult:") or not isinstance(v, dict):
                        continue
                    company = (v.get("name") or "").strip()
                    co_slug = (v.get("slug") or "").strip()
                    for ref in v.get("highlightedJobListings") or []:
                        rid = ref.get("__ref") if isinstance(ref, dict) else str(ref)
                        if rid:
                            job_co[rid] = (company, co_slug)
                for k, v in apollo.items():
                    if not k.startswith("JobListingSearchResult:") or not isinstance(v, dict):
                        continue
                    title = (v.get("title") or "").strip()
                    ymin = v.get("yearsExperienceMin")
                    if isinstance(ymin, (int, float)) and ymin >= 3:
                        continue
                    company, co_slug = job_co.get(k, ("Wellfound startup", ""))
                    locs = v.get("locationNames") or []
                    remote = bool(v.get("remote"))
                    location = "Remote" if remote else (", ".join(locs) if locs else "Unknown")
                    if remote:
                        accepted = v.get("acceptedRemoteLocationNames") or []
                        if accepted:
                            location = "Remote (" + ", ".join(accepted[:3]) + ")"
                    if not keep(title, company, location):
                        continue
                    jslug = v.get("slug") or "job"
                    jid = v.get("id") or k.split(":")[-1]
                    if co_slug:
                        job_url = f"https://wellfound.com/jobs/{co_slug}-{jid}-{jslug}"
                    else:
                        job_url = f"https://wellfound.com/jobs/{jid}"
                    out.append(
                        {
                            "source": "wellfound",
                            "title": title,
                            "company": company,
                            "location": location,
                            "url": job_url,
                            "tags": "startup " + (v.get("primaryRoleTitle") or ""),
                            "posted": str(v.get("liveStartAt") or ""),
                            "salary": (v.get("compensation") or "")
                            if isinstance(v.get("compensation"), str)
                            else "",
                        }
                    )
    except Exception as exc:
        print(f"  wellfound fail: {exc}", flush=True)
    return out


def find_dice() -> list[dict]:
    out: list[dict] = []
    queries = [
        "junior+software+engineer+react",
        "associate+software+engineer",
        "frontend+react+developer",
        "full+stack+engineer",
        "AI+engineer",
    ]
    try:
        with _client() as client:
            for q in queries:
                url = (
                    f"https://www.dice.com/jobs?q={q}"
                    f"&filters.workplaceTypes=Remote&pageSize=40&language=en"
                    f"&filters.postedDate=THIRTY"
                )
                try:
                    r = client.get(url)
                    if r.status_code >= 400:
                        continue
                    html = r.text
                except Exception:
                    continue
                for m in re.finditer(r"https://www\.dice\.com/job-detail/([a-f0-9-]{36})", html):
                    start = max(0, m.start() - 1200)
                    chunk = html[start : m.end() + 200].replace('\\"', '"')
                    tm = re.search(r'"title"\s*:\s*"([^"]{5,100})"', chunk)
                    cm = re.search(r'"companyName"\s*:\s*"([^"]{2,80})"', chunk)
                    if not tm or not cm:
                        continue
                    title, company = tm.group(1), cm.group(1)
                    if not keep(title, company, "Remote"):
                        continue
                    out.append(
                        {
                            "source": "dice",
                            "title": title,
                            "company": company,
                            "location": "Remote",
                            "url": m.group(0),
                            "tags": q.replace("+", " "),
                            "posted": "",
                        }
                    )
    except Exception as exc:
        print(f"  dice fail: {exc}", flush=True)
    seen: set[str] = set()
    uniq = []
    for j in out:
        if j["url"] in seen:
            continue
        seen.add(j["url"])
        uniq.append(j)
    return uniq


def find_remotive() -> list[dict]:
    out: list[dict] = []
    urls = [
        "https://remotive.com/api/remote-jobs?category=software-dev&limit=100",
        "https://remotive.com/api/remote-jobs?search=react&limit=50",
        "https://remotive.com/api/remote-jobs?search=AI%20engineer&limit=50",
    ]
    try:
        with _client() as client:
            for url in urls:
                try:
                    r = client.get(url)
                    r.raise_for_status()
                    jobs = r.json().get("jobs") or []
                except Exception:
                    continue
                for row in jobs:
                    title = (row.get("title") or "").strip()
                    company = (row.get("company_name") or "").strip()
                    location = (row.get("candidate_required_location") or "Remote").strip()
                    tags = " ".join(row.get("tags") or [])
                    if not keep(title, company, location, tags):
                        continue
                    out.append(
                        {
                            "source": "remotive",
                            "title": title,
                            "company": company,
                            "location": location,
                            "url": row.get("url") or "",
                            "tags": tags,
                            "posted": row.get("publication_date") or "",
                            "salary": row.get("salary") or "",
                        }
                    )
    except Exception as exc:
        print(f"  remotive fail: {exc}", flush=True)
    return out


def find_arbeitnow() -> list[dict]:
    out: list[dict] = []
    try:
        with _client() as client:
            r = client.get("https://www.arbeitnow.com/api/job-board-api")
            r.raise_for_status()
            jobs = r.json().get("data") or []
    except Exception as exc:
        print(f"  arbeitnow fail: {exc}", flush=True)
        return out
    for row in jobs:
        title = (row.get("title") or "").strip()
        company = (row.get("company_name") or "").strip()
        location = (row.get("location") or "").strip()
        tags = " ".join(row.get("tags") or [])
        remote = bool(row.get("remote"))
        if remote and "remote" not in location.lower():
            location = f"Remote / {location}".strip(" /")
        if re.search(r"\b(m/w/d|werkstudent|deutsch)\b", title, re.I):
            continue
        if not keep(title, company, location, tags):
            continue
        out.append(
            {
                "source": "arbeitnow",
                "title": title,
                "company": company,
                "location": location,
                "url": row.get("url") or "",
                "tags": tags,
                "posted": str(row.get("created_at") or ""),
            }
        )
    return out


def find_himalayas() -> list[dict]:
    out: list[dict] = []
    try:
        with _client() as client:
            r = client.get("https://himalayas.app/jobs/api?limit=100")
            r.raise_for_status()
            data = r.json()
            jobs = data.get("jobs") or data.get("data") or []
            if isinstance(data, list):
                jobs = data
    except Exception as exc:
        print(f"  himalayas fail: {exc}", flush=True)
        return out
    for row in jobs:
        if not isinstance(row, dict):
            continue
        title = (row.get("title") or row.get("jobTitle") or "").strip()
        company = row.get("companyName") or ""
        if isinstance(row.get("company"), dict):
            company = row["company"].get("name") or company
        elif row.get("company") and not company:
            company = str(row.get("company"))
        company = str(company or "").strip()
        location = str(row.get("location") or "Remote")
        if isinstance(row.get("locations"), list):
            location = ", ".join(str(x) for x in row["locations"][:3]) or "Remote"
        tags = " ".join(str(t) for t in (row.get("categories") or row.get("tags") or []))
        if not keep(title, company, str(location), tags):
            continue
        url = row.get("applicationLink") or row.get("url") or row.get("guid") or ""
        out.append(
            {
                "source": "himalayas",
                "title": title,
                "company": company,
                "location": str(location),
                "url": url,
                "tags": tags,
                "posted": str(row.get("pubDate") or row.get("publishedAt") or ""),
            }
        )
    return out


def find_jobicy() -> list[dict]:
    out: list[dict] = []
    urls = [
        "https://jobicy.com/api/v2/remote-jobs?count=50&tag=software-dev",
        "https://jobicy.com/api/v2/remote-jobs?count=50&tag=javascript",
        "https://jobicy.com/api/v2/remote-jobs?count=50&tag=python",
    ]
    try:
        with _client() as client:
            for url in urls:
                try:
                    r = client.get(url)
                    r.raise_for_status()
                    jobs = r.json().get("jobs") or []
                except Exception:
                    continue
                for row in jobs:
                    title = (row.get("jobTitle") or "").strip()
                    company = (row.get("companyName") or "").strip()
                    location = (row.get("jobGeo") or "Remote").strip()
                    tags = (
                        " ".join(row.get("jobIndustry") or [])
                        if isinstance(row.get("jobIndustry"), list)
                        else str(row.get("jobIndustry") or "")
                    )
                    if not keep(title, company, location, tags):
                        continue
                    out.append(
                        {
                            "source": "jobicy",
                            "title": title,
                            "company": company,
                            "location": location,
                            "url": row.get("url") or "",
                            "tags": tags,
                            "posted": row.get("pubDate") or "",
                            "salary": row.get("annualSalaryMin") or "",
                        }
                    )
    except Exception as exc:
        print(f"  jobicy fail: {exc}", flush=True)
    return out


def try_blocked_boards() -> dict[str, str]:
    status: dict[str, str] = {}
    probes = {
        "indeed": "https://www.indeed.com/jobs?q=junior+software+engineer+react&l=Remote",
        "bayt": "https://www.bayt.com/en/international/jobs/software-engineer-jobs/",
        "ziprecruiter": "https://www.ziprecruiter.com/jobs-search?search=junior+software+engineer&location=Remote",
        "glassdoor": "https://www.glassdoor.com/Job/remote-junior-software-engineer-jobs-SRCH_IL.0,6_IS11047_KO7,31.htm",
    }
    with _client() as client:
        for name, url in probes.items():
            try:
                r = client.get(url)
                if r.status_code == 200 and len(r.text) > 5000 and "captcha" not in r.text.lower():
                    status[name] = f"reachable ({len(r.text)} bytes) — no parser yet"
                else:
                    status[name] = f"blocked/empty HTTP {r.status_code}"
            except Exception as exc:
                status[name] = f"error: {exc}"
    return status


def main() -> None:
    print("Finding junior/associate SWE · Frontend · Full Stack · AI roles", flush=True)
    print("Fit: React/Next/TS/Python/AI · Remote or Pakistan/Karachi · <3 YOE\n", flush=True)

    boards = [
        ("LinkedIn", find_linkedin),
        ("Remote OK", find_remoteok),
        ("We Work Remotely", find_wwr),
        ("Rozee.pk", find_rozee),
        ("Freehire", find_freehire),
        ("Wellfound", find_wellfound),
        ("Dice", find_dice),
        ("Remotive", find_remotive),
        ("Arbeitnow", find_arbeitnow),
        ("Himalayas", find_himalayas),
        ("Jobicy", find_jobicy),
    ]
    all_jobs: list[dict] = []
    for name, fn in boards:
        print(f"[{name}] searching…", flush=True)
        jobs = fn()
        print(f"  → {len(jobs)} kept", flush=True)
        all_jobs.extend(jobs)

    print("\n[Still-blocked boards]", flush=True)
    blocked = try_blocked_boards()
    for k, v in blocked.items():
        print(f"  {k}: {v}", flush=True)

    seen: set[str] = set()
    uniq: list[dict] = []
    for j in all_jobs:
        key = re.sub(r"[^a-z0-9]+", "", f"{j['company']}|{j['title']}".lower())
        if key in seen:
            continue
        seen.add(key)
        j["score"] = score(j)
        uniq.append(j)
    uniq.sort(key=lambda j: (-j["score"], j["company"].lower()))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "date": date.today().isoformat(),
        "profile": "Muddasir — junior SWE/FE/AI, React/Next/TS/Python, Karachi + remote",
        "count": len(uniq),
        "by_source": {},
        "blocked_boards": blocked,
        "jobs": uniq,
    }
    for j in uniq:
        payload["by_source"][j["source"]] = payload["by_source"].get(j["source"], 0) + 1
    OUT.write_text(json.dumps(payload, indent=2))

    print(f"\n=== TOP MATCHES ({len(uniq)} total) ===", flush=True)
    for i, j in enumerate(uniq[:50], 1):
        print(
            f"{i:2}. [{j['score']:2}] {j['title'][:46]:46} | {j['company'][:20]:20} | "
            f"{(j['location'] or '')[:16]:16} | {j['source']}",
            flush=True,
        )
        if j.get("url"):
            print(f"    {j['url']}", flush=True)
    print(f"\nSaved → {OUT}", flush=True)
    print("Sources:", payload["by_source"], flush=True)


if __name__ == "__main__":
    main()
