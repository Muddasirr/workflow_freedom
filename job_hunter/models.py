from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Job:
    source: str
    source_id: str
    title: str
    company: str
    url: str
    location: str = ""
    work_mode: str = "unknown"  # remote | hybrid | onsite | unknown
    job_type: str = ""
    salary: str = ""
    posted_at: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    location_restrictions: list[str] = field(default_factory=list)
    company_domain: str = ""

    score: int = 0
    matched_skills: list[str] = field(default_factory=list)
    role_fit: list[str] = field(default_factory=list)
    location_fit: str = ""
    pakistan_friendly: str = ""  # Yes | Maybe | No
    emails: list[str] = field(default_factory=list)
    hr_email: str = ""
    email_source: str = ""
    excerpt: str = ""
    notes: str = ""
    seniority: str = ""  # junior | unspecified | mid-senior | senior
    experience_fit: str = ""  # Yes | Maybe | No
    experience_note: str = ""

    @property
    def dedupe_key(self) -> str:
        title = " ".join(self.title.lower().split())
        company = " ".join(self.company.lower().split())
        return f"{company}::{title}"
