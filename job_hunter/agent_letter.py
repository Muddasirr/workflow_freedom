"""Write a job-specific cover letter via a Cursor cloud agent (CURSOR_API_KEY)."""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path

import httpx

from job_hunter.config import CURSOR_API_KEY, ROOT

CACHE_DIR = ROOT / "output" / "letter_cache"
API_BASE = "https://api.cursor.com/v1"
POLL_SECONDS = 4
POLL_ATTEMPTS = 90  # ~6 minutes; VM boot can be slow

PROFILE = """
Muhammad Muddasir, software engineer at Codet.ai, Karachi, Pakistan, open to remote.
Phone +92-3249867842. Email muddasirrizwan9@gmail.com. Site muddasirrizwan.com.

Shipped work:
- Product UI at Codet.ai: no-code builder (drag-and-drop canvas, trigger → condition → action) and an in-app AI assistant, in Next.js, React, TypeScript.
- Workflow automation / LLM features: n8n-style canvas plus an assistant that helps compose and debug flows.
- AutoCloudEngineerAgent on LangGraph: LLM control plane that proposes infra configs, deploys only to a Kubernetes canary, benches, then rejects / rolls back / recommends promotion. GP optimizer beside a BO-ICL LLM surrogate that cannot override hard safety constraints.
- Euronet: Java payment APIs (ISO 8583, JWT, PostgreSQL). Go for backend services when needed.

Target roles: software engineer, AI/LLM engineer, product engineer, frontend (React/Next), Python/backend. 0–2 years.
""".strip()

VOICE = """
Write like the existing letters: short, specific, first person, no filler.
Banned: "I hope this email finds you well", "passionate about", "leverage", "excited to", "I am writing to", em dashes, markdown, bullet lists, subject line.
Keep the facts true. Do not invent employers, degrees, or years of experience.
3 short paragraphs + sign-off. About 140–190 words.
""".strip()


def _cache_path(company: str, role: str, summary: str) -> Path:
    key = f"{company.lower()}|{role.lower()}|{summary[:400]}"
    digest = hashlib.sha1(key.encode()).hexdigest()[:16]
    return CACHE_DIR / f"{digest}.txt"


def _clean(text: str) -> str:
    body = (text or "").strip()
    body = re.sub(r"^```(?:text|markdown)?\s*", "", body)
    body = re.sub(r"\s*```$", "", body)
    lines = [ln.rstrip() for ln in body.splitlines()]
    if lines and lines[0].lower().startswith("subject:"):
        lines = lines[1:]
        if lines and not lines[0].strip():
            lines = lines[1:]
    return "\n".join(lines).strip() + "\n"


def _api_error(resp: httpx.Response) -> str:
    try:
        payload = resp.json()
        err = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(err, dict):
            return f"{resp.status_code} {err.get('code') or ''} {err.get('message') or ''}".strip()
        if isinstance(err, str):
            return f"{resp.status_code} {err}"
    except Exception:  # noqa: BLE001
        pass
    return f"{resp.status_code} {resp.reason_phrase}"


def _client(api_key: str) -> httpx.Client:
    return httpx.Client(
        base_url=API_BASE,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=httpx.Timeout(180.0, connect=20.0),
    )


def _archive(client: httpx.Client, agent_id: str) -> None:
    try:
        client.post(f"/agents/{agent_id}/archive")
    except Exception:  # noqa: BLE001
        pass


def _parse_sse(resp: httpx.Response) -> str:
    event = "message"
    chunks: list[str] = []
    assistant: list[str] = []
    final = ""
    status = ""
    for raw_line in resp.iter_lines():
        line = raw_line.decode("utf-8", errors="replace") if isinstance(raw_line, bytes) else raw_line
        if line.startswith("event:"):
            event = line[6:].strip()
            continue
        if line.startswith("data:"):
            chunks.append(line[5:].lstrip())
            continue
        if line.strip():
            continue
        if not chunks:
            event = "message"
            continue
        try:
            payload = json.loads("\n".join(chunks))
        except json.JSONDecodeError:
            payload = {}
        chunks = []
        if event == "assistant":
            assistant.append(str(payload.get("text") or ""))
        elif event == "result":
            final = str(payload.get("text") or "")
            status = str(payload.get("status") or "").upper()
        event = "message"
    if status and status != "FINISHED":
        raise RuntimeError(f"Cursor agent run {status.lower()}")
    return final or "".join(assistant)


def _stream_letter(client: httpx.Client, agent_id: str, run_id: str) -> str:
    with client.stream("GET", f"/agents/{agent_id}/runs/{run_id}/stream", timeout=180.0) as resp:
        if resp.status_code >= 400:
            resp.read()
            raise RuntimeError(f"Cursor agent stream failed: {_api_error(resp)}")
        return _parse_sse(resp)


def _poll_letter(client: httpx.Client, agent_id: str, run_id: str) -> str:
    run: dict = {}
    status = ""
    for _ in range(POLL_ATTEMPTS):
        polled = client.get(f"/agents/{agent_id}/runs/{run_id}")
        if polled.status_code >= 400:
            raise RuntimeError(f"Cursor agent poll failed: {_api_error(polled)}")
        run = polled.json()
        status = (run.get("status") or "").upper()
        if status in {"FINISHED", "ERROR", "CANCELLED", "EXPIRED"}:
            break
        time.sleep(POLL_SECONDS)
    else:
        raise RuntimeError("Cursor agent timed out waiting for the letter")
    if status != "FINISHED":
        raise RuntimeError(f"Cursor agent run {status.lower()}: {run.get('id', '')}")
    return run.get("result") or ""


def _artifact_letter(client: httpx.Client, agent_id: str) -> str:
    listed = client.get(f"/agents/{agent_id}/artifacts")
    if listed.status_code >= 400:
        return ""
    items = listed.json()
    if isinstance(items, dict):
        items = items.get("items") or items.get("artifacts") or []
    for item in items or []:
        path = item.get("path") if isinstance(item, dict) else str(item)
        if not path:
            continue
        if not str(path).endswith((".txt", ".md", ".email")):
            continue
        got = client.get(f"/agents/{agent_id}/artifacts/download", params={"path": path})
        if got.status_code < 400:
            return got.text
    return ""


def _run_agent(prompt: str, *, company: str) -> str:
    api_key = CURSOR_API_KEY or os.getenv("CURSOR_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("CURSOR_API_KEY is not set")

    name = f"cover-letter {company}"[:100]
    payload = {
        "prompt": {"text": prompt},
        "name": name,
        "model": {"id": "composer-2.5"},
    }

    with _client(api_key) as client:
        created = None
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                created = client.post("/agents", json=payload)
                if created.status_code >= 400 and "model" in payload:
                    payload.pop("model", None)
                    created = client.post("/agents", json=payload)
                break
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exc = exc
                time.sleep(2 * (attempt + 1))
        if created is None:
            raise RuntimeError(f"Cursor agent create failed: {last_exc}") from last_exc
        if created.status_code >= 400:
            raise RuntimeError(f"Cursor agent create failed: {_api_error(created)}")

        data = created.json()
        agent = data.get("agent") or {}
        run = data.get("run") or {}
        agent_id = agent.get("id") or ""
        run_id = run.get("id") or agent.get("latestRunId") or ""
        if not agent_id or not run_id:
            raise RuntimeError("Cursor agent create returned no agent/run id")

        try:
            raw = ""
            try:
                raw = _stream_letter(client, agent_id, run_id)
            except Exception:  # noqa: BLE001
                raw = ""
            if len((raw or "").strip()) < 80:
                raw = _poll_letter(client, agent_id, run_id) or raw
            if len((raw or "").strip()) < 80:
                raw = _artifact_letter(client, agent_id) or raw
            text = _clean(raw)
            if len(text) < 80 or "Muddasir" not in text:
                preview = (text or raw or "").replace("\n", " ")[:240]
                raise RuntimeError(
                    f"Cursor agent returned an unusable letter ({len(text)} chars): {preview}"
                )
            return text
        finally:
            _archive(client, agent_id)


def write_cover_letter(
    *,
    company: str,
    role: str,
    location: str = "",
    summary: str = "",
    skills: str = "",
    apply_url: str = "",
) -> str:
    """Return a plain-text email body. Raises if the agent cannot run."""
    if not (CURSOR_API_KEY or os.getenv("CURSOR_API_KEY", "").strip()):
        raise RuntimeError("CURSOR_API_KEY is not set")
    cache = _cache_path(company, role, summary)
    if cache.is_file():
        return cache.read_text(encoding="utf-8")

    loc = f" Location: {location}." if location else ""
    prompt = f"""Reply with ONLY the email body in your final assistant message. Do not create or edit files. Do not use tools. Do not write a summary.

{VOICE}

Candidate:
{PROFILE}

Job:
- Company: {company}
- Role: {role}{loc}
- Skills mentioned: {skills or "n/a"}
- Posting notes: {(summary or "none")[:900]}
- Apply URL: {apply_url or "n/a"}

Start with "Hi {company} team," then mention this exact role in the first sentence.
Close with:
Thanks,
Muhammad Muddasir
+92-3249867842 · muddasirrizwan9@gmail.com
"""

    text = _run_agent(prompt, company=company)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(text, encoding="utf-8")
    return text


def agent_enabled() -> bool:
    return bool(CURSOR_API_KEY or os.getenv("CURSOR_API_KEY", "").strip())
