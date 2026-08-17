from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from job_hunter.config import GREENHOUSE_BOARDS
from job_hunter.http import HttpClient
from job_hunter.models import Job

CORE_TITLE_HINTS = (
    "react",
    "next.js",
    "nextjs",
    "python",
    "fastapi",
    "django",
    "flask",
    "typescript",
    "frontend",
    "front-end",
    "front end",
    "full stack",
    "fullstack",
    "full-stack",
    "backend",
    "back-end",
    "back end",
    "ai engineer",
    "ai/ml",
    "machine learning",
    "llm",
    "genai",
    "generative ai",
    "langchain",
    "software engineer",
    "product engineer",
    "frontend engineer",
    "front-end engineer",
)


def _title_worth_fetching(title: str) -> bool:
    t = title.lower()
    return any(hint in t for hint in CORE_TITLE_HINTS)


def _company_name(board: str) -> str:
    if board == "togetherai":
        return "Together AI"
    if board == "turing":
        return "Turing"
    if board == "careem":
        return "Careem"
    return board.replace("-", " ").title()


def fetch_greenhouse(_client: HttpClient | None = None) -> list[Job]:
    jobs: list[Job] = []

    def one(board: str) -> list[Job]:
        local = HttpClient()
        try:
            data = local.get_json(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs")
        except Exception:
            return []
        finally:
            local.close()
        company_name = _company_name(board)
        batch: list[Job] = []
        for item in data.get("jobs") or []:
            title = item.get("title") or ""
            location_name = ((item.get("location") or {}).get("name") or "").strip()
            loc_l = location_name.lower()
            interesting_location = any(
                token in loc_l
                for token in (
                    "karachi",
                    "lahore",
                    "islamabad",
                    "pakistan",
                    "remote",
                    "anywhere",
                    "worldwide",
                    "dubai",
                    "uae",
                    "riyadh",
                    "saudi",
                    "kuwait",
                    "qatar",
                    "doha",
                    "bahrain",
                    "cairo",
                    "egypt",
                    "sydney",
                    "melbourne",
                    "australia",
                    "london",
                    "berlin",
                    "amsterdam",
                    "europe",
                    "emea",
                )
            )
            if not _title_worth_fetching(title) and not interesting_location:
                continue
            work_mode = "remote" if "remote" in loc_l or "anywhere" in loc_l else "unknown"
            if "hybrid" in loc_l:
                work_mode = "hybrid"
            elif any(x in loc_l for x in ("on-site", "onsite", "office")):
                work_mode = "onsite"
            batch.append(
                Job(
                    source=f"Greenhouse/{company_name}",
                    source_id=str(item.get("id") or item.get("absolute_url") or ""),
                    title=title,
                    company=company_name,
                    url=item.get("absolute_url") or "",
                    location=location_name,
                    work_mode=work_mode,
                    posted_at=(item.get("updated_at") or "")[:10],
                    description=f"{title} {location_name} {company_name}",
                    location_restrictions=[location_name] if location_name else [],
                )
            )
        return batch

    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = [pool.submit(one, board) for board in GREENHOUSE_BOARDS]
        for fut in as_completed(futs):
            jobs.extend(fut.result())
    return jobs
