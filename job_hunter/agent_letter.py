"""Write a job-specific cover letter via a Cursor agent (CURSOR_API_KEY)."""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from job_hunter.config import CURSOR_API_KEY, ROOT

CACHE_DIR = ROOT / "output" / "letter_cache"

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
    # Drop a leading Subject: line if the model added one.
    lines = [ln.rstrip() for ln in body.splitlines()]
    if lines and lines[0].lower().startswith("subject:"):
        lines = lines[1:]
        if lines and not lines[0].strip():
            lines = lines[1:]
    return "\n".join(lines).strip() + "\n"


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
    if not CURSOR_API_KEY:
        raise RuntimeError("CURSOR_API_KEY is not set")
    cache = _cache_path(company, role, summary)
    if cache.is_file():
        return cache.read_text(encoding="utf-8")

    from cursor_sdk import Agent, AgentOptions, CursorAgentError, LocalAgentOptions

    loc = f" Location: {location}." if location else ""
    prompt = f"""Write a job-application email body. Output ONLY the email body. Do not edit files. Do not use tools.

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

    try:
        result = Agent.prompt(
            prompt,
            AgentOptions(
                api_key=CURSOR_API_KEY,
                model="composer-2.5",
                name="cover-letter",
                local=LocalAgentOptions(cwd=str(ROOT)),
                tools=[],
            ),
        )
    except CursorAgentError as exc:
        raise RuntimeError(f"Cursor agent failed to start: {exc}") from exc

    if getattr(result, "status", None) == "error":
        raise RuntimeError(f"Cursor agent run error: {getattr(result, 'id', '')}")
    text = _clean(getattr(result, "result", "") or "")
    if len(text) < 80 or "Muddasir" not in text:
        raise RuntimeError("Cursor agent returned an unusable letter")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(text, encoding="utf-8")
    return text


def agent_enabled() -> bool:
    return bool(CURSOR_API_KEY or os.getenv("CURSOR_API_KEY", "").strip())
