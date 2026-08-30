# Search Queries for Job Scraper

## Installed portal CLIs (primary for `/scrape`)

`/scrape` discovers every portal skill under `.agents/skills/*/SKILL.md` and runs its CLI first. Country-agnostic CLIs: `linkedin-search`, `freehire-search` (enabled). Danish demos (Jobindex, Jobbank, Jobdanmark, Jobnet) stay **disabled** — Pakistan / remote worldwide market.

The `site:` templates below are the **WebSearch fallback**.

**Language scope:** English (primary for international remote + tech postings). Urdu-language ads are rare for these roles; do not auto-exclude English postings.

## Search Sites

Primary:
- **linkedin.com/jobs** - Pakistan + remote worldwide (also `linkedin-search` CLI)
- **rozee.pk** - Pakistan general board
- **mustakbil.com** - Pakistan board (optional)
- **freehire** - covered by `freehire-search` CLI when enabled

Secondary:
- Company career pages via Google `site:` for target SaaS / AI / fintech employers

## Query Categories

### Priority 1: Fullstack product engineering

```
site:linkedin.com/jobs "Full Stack" OR "Fullstack" OR "Software Engineer" Next.js OR React Pakistan OR Remote
site:rozee.pk "Full Stack Developer" OR "Software Engineer" React OR Next.js
site:linkedin.com/jobs "Software Engineer" TypeScript Node.js remote
```

### Priority 2: Frontend engineering

```
site:linkedin.com/jobs "Frontend Engineer" OR "Front End Developer" React OR Next.js Pakistan OR Remote
site:rozee.pk "Frontend Developer" React
site:linkedin.com/jobs "React Developer" TypeScript remote
```

### Priority 3: AI / LLM application engineering

```
site:linkedin.com/jobs "AI Engineer" OR "LLM" OR LangChain OR LangGraph Pakistan OR Remote
site:linkedin.com/jobs "Machine Learning Engineer" Python application OR product remote
site:rozee.pk "AI Engineer" OR "Machine Learning"
```

### Priority 4: Broader / adjacent

```
site:linkedin.com/jobs "Software Engineer" Java OR Node.js fintech OR SaaS Pakistan OR Remote
site:linkedin.com/jobs "Platform Engineer" OR "Developer Tools" TypeScript remote
site:rozee.pk "Backend Developer" Java OR Node
```

## Location Filter

- **Ideal:** Remote worldwide; Karachi hybrid/on-site
- **Acceptable:** Anywhere in Pakistan; remote with rare travel
- **Borderline:** Required relocation outside Pakistan with hybrid — discuss
- **Too far only if:** Hard on-site abroad with no remote and candidate declines when asked

## Language Filter

- English-required roles: PASS (fluent)
- Urdu-required roles: PASS (fluent)
- Other languages as job condition (e.g. German, Arabic only): FAIL Language Gate unless declared later

## Notes for scrape runs

- Target titles: Full Stack Engineer, Frontend Engineer, Software Engineer, AI Engineer, LLM Engineer, React/Next.js Developer
- Distinctive skills: Next.js, TypeScript, LangGraph/LangChain, ReactFlow/Monaco-style tooling, no-code platforms
- Danish portal skills remain `enabled: false` unless market changes
