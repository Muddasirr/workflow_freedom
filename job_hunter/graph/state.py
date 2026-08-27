"""Shared state for the apply graph."""
from __future__ import annotations

from typing import Any, TypedDict


class JobCard(TypedDict, total=False):
    title: str
    company: str
    url: str
    location: str
    description: str
    excerpt: str
    skills: str
    domain: str
    email: str
    email_source: str
    smtp: str
    letter: str
    letter_kind: str
    status: str
    reason: str


class GraphState(TypedDict, total=False):
    send: bool
    limit: int
    delay: float
    daily_cap: int
    no_agent: bool
    jobs: list[JobCard]
    index: int
    current: JobCard
    sent_count: int
    skipped: list[str]
    results: list[JobCard]
    log: list[str]
    done: bool
    extra: dict[str, Any]
    lookups: int
