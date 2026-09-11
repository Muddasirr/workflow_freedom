"""Find public company emails via local theHarvester checkout.

Uses `uv run theHarvester` under ./harvester. Results are cached per domain.
Also runs a light Bing @{domain} scrape when search engines inside theHarvester
return empty (Yahoo/DDG often fail with captcha/500).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path

from job_hunter.textutil import extract_emails, html_to_text

ROOT = Path(__file__).resolve().parents[1]
HARVESTER_DIR = ROOT / "harvester"
UV = Path(os.environ.get("UV_BIN", Path.home() / ".local/bin/uv"))
CACHE = ROOT / "output" / "harvester_cache"
CACHE_TTL_SEC = 7 * 24 * 3600

# Prefer free/no-key + hunter (key in ~/.theHarvester/api-keys.yaml)
DEFAULT_SOURCES = (
    "hunter,duckduckgo,yahoo,baidu,hudsonrock,gitlab,urlscan,mojeek"
)


def _safe_domain(domain: str) -> str:
    d = (domain or "").strip().lower().removeprefix("www.")
    if not d or "." not in d or " " in d:
        return ""
    if not re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", d):
        return ""
    return d


def _cache_path(domain: str) -> Path:
    return CACHE / f"{domain.replace('/', '_')}.json"


def _load_cache(domain: str) -> list[str] | None:
    path = _cache_path(domain)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if time.time() - float(data.get("ts") or 0) > CACHE_TTL_SEC:
            return None
        emails = data.get("emails") or []
        return [e.lower() for e in emails if isinstance(e, str) and "@" in e]
    except Exception:
        return None


def _save_cache(domain: str, emails: list[str], meta: dict | None = None) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    payload = {"ts": time.time(), "domain": domain, "emails": emails, "meta": meta or {}}
    _cache_path(domain).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _parse_harvester_out(prefix: Path) -> list[str]:
    emails: list[str] = []
    jsonl = Path(f"{prefix}.jsonl")
    if jsonl.exists():
        for line in jsonl.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if obj.get("type") == "email" and obj.get("value"):
                emails.append(str(obj["value"]).lower())
    compat = Path(f"{prefix}.json")
    if compat.exists():
        try:
            data = json.loads(compat.read_text(encoding="utf-8"))
            for e in data.get("emails") or []:
                if isinstance(e, str):
                    emails.append(e.lower())
        except Exception:
            pass
    return list(dict.fromkeys(emails))


def _bing_at_domain(domain: str, limit: int = 30) -> list[str]:
    """Fallback when theHarvester search engines are blocked — same @{domain} dork."""
    try:
        import httpx
    except Exception:
        return []
    q = f"%40{domain}"
    url = f"https://www.bing.com/search?q={q}&count={min(limit, 50)}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    }
    try:
        r = httpx.get(url, headers=headers, timeout=25.0, follow_redirects=True)
        if r.status_code != 200:
            return []
        blob = html_to_text(r.text) + " " + r.text
        return [e.lower() for e in extract_emails(blob) if e.lower().endswith("@" + domain)]
    except Exception:
        return []


def harvester_available() -> bool:
    return HARVESTER_DIR.is_dir() and (UV.exists() or bool(os.environ.get("UV_BIN")))


def harvest_emails(
    domain: str,
    *,
    sources: str = DEFAULT_SOURCES,
    limit: int = 40,
    timeout_sec: int = 90,
    use_cache: bool = True,
    bing_fallback: bool = True,
) -> list[str]:
    """Return emails discovered for a company domain via theHarvester (+ optional Bing)."""
    domain = _safe_domain(domain)
    if not domain:
        return []
    if use_cache:
        cached = _load_cache(domain)
        if cached is not None:
            return cached

    emails: list[str] = []
    meta: dict = {"sources": sources}
    if harvester_available():
        CACHE.mkdir(parents=True, exist_ok=True)
        out_prefix = CACHE / f"run_{domain.replace('.', '_')}"
        uv_bin = str(UV if UV.exists() else "uv")
        cmd = [
            uv_bin,
            "run",
            "theHarvester",
            "-d",
            domain,
            "-b",
            sources,
            "-l",
            str(limit),
            "-f",
            str(out_prefix),
            "--quiet",
        ]
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(HARVESTER_DIR),
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                env={**os.environ, "PATH": f"{Path.home() / '.local/bin'}:{os.environ.get('PATH', '')}"},
            )
            meta["returncode"] = proc.returncode
            emails.extend(_parse_harvester_out(out_prefix))
        except subprocess.TimeoutExpired:
            meta["error"] = "timeout"
            emails.extend(_parse_harvester_out(out_prefix))
        except Exception as exc:  # noqa: BLE001
            meta["error"] = str(exc)[:200]

    if bing_fallback and not emails:
        bing = _bing_at_domain(domain)
        if bing:
            meta["bing_fallback"] = len(bing)
            emails.extend(bing)

    emails = list(dict.fromkeys(e for e in emails if "@" in e))
    # Prefer same-domain
    same = [e for e in emails if e.endswith("@" + domain)]
    other = [e for e in emails if e not in same]
    ordered = same + other
    if use_cache:
        _save_cache(domain, ordered, meta)
    return ordered
