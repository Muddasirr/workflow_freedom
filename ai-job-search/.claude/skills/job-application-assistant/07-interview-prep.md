---
framework_version: 1.0.0
---

# Interview Preparation Guide

## STAR Format

Structure answers as: **Situation** (context), **Task** (your responsibility), **Action** (what you did), **Result** (outcome).

Keep answers to 1-2 minutes. Be specific. End with what you learned or would do differently.

## Ready-Made STAR Examples

### 1. AutoCloudEngineerAgent (AI agents + safety)
**S:** At Codet.ai we needed infra config suggestions from an LLM-style agent without letting bad proposals hit production unchecked.
**T:** Design a control plane that could propose configs, validate them, and only promote after canary evidence.
**A:** Built AutoCloudEngineerAgent on LangGraph: proposals deploy only to a Kubernetes canary cell, run invariant benches, then reject, roll back, or recommend promotion. Optimizer used a GP-UCB / trust-region ensemble with BO-ICL as an advisory LLM surrogate that cannot override hard safety/isolation constraints.
**R:** Shipped a production-shaped agent loop where the model advises but hard rails decide. Shows applied AI judgment, not prompt demos.
**Use for:** "Tell me about an AI project you owned", "How do you handle LLM risk?", "Describe a complex system you designed"

### 2. No-code platform + dynamic database (fullstack ownership)
**S:** Codet.ai needed a no-code surface so users could create apps without writing code.
**T:** Own core platform pieces: data model configuration and workflow/UI composition.
**A:** Built the dynamic database module (tables, fields, relationships, records) and drag-and-drop interfaces for workflows and UI components on Next.js.
**R:** Users can configure data and compose flows without engineering tickets for every schema change; setup time reduced for end users.
**Use for:** "Describe a product you shipped end-to-end", "How do you handle complex UI state?", "Ownership examples"

### 3. Euronet payment APIs (backend / fintech)
**S:** Fintech services needed reliable payment-facing APIs with auth and third-party integrations.
**T:** Implement REST APIs and harden auth/data access on Java / Java EE.
**A:** Built REST endpoints, implemented ISO 8583 for payment APIs, JWT + RBAC, PostgreSQL query work, and third-party payment integrations; also debugged legacy code for efficiency.
**R:** Delivered authenticated payment-capable APIs and improved legacy performance in a regulated domain.
**Use for:** "Backend experience?", "Working with legacy systems", "Security/auth experience"

### 4. Rulr visual workflow builder (frontend craft)
**S:** Users needed to compose API logic visually rather than hand-edit brittle configs.
**T:** Build an interactive rule/workflow editor with strong typing and validation.
**A:** Used React-DnD and ReactFlow for composition, Monaco for JSON/rule editing with schema validation, and reusable MUI components with advanced TypeScript typings.
**R:** Operators could visually assemble logic with live editing and validation instead of opaque config files.
**Use for:** "Hardest frontend problem", "Design system / component work", "DX tooling"

## Common Tough Questions

### "Why are you open to leaving Codet.ai / switching?"
> I'm employed and shipping meaningful AI + platform work. I'm looking for the next step where I can deepen fullstack/AI product ownership at similar or greater scope. Not running from something; choosing growth.

### "You don't have [specific skill/experience]."
> Acknowledge the gap honestly. Bridge to adjacent shipped work (e.g. FastAPI project for Python backend depth; LangGraph agent for MLOps-adjacent claims). Show a concrete learning plan, never invent tenure.

### "Where do you see yourself in 5 years?"
> Senior product engineer owning AI-augmented platforms or developer tools, still hands-on, shaping architecture and UX for complex workflows.

### "What's your biggest weakness?"
> Early-career breadth vs depth: I ship across frontend, backend, and agents, so I sometimes over-own. Mitigation: explicit scoping with stakeholders and documenting handoff boundaries.

### "Why this company specifically?"
> Customize per company. Must reference: specific products, stack, or market. Never generic.

## Questions You Should Ask Interviewers

### About the Role
- "What does a typical week look like in this role?"
- "What would success look like in the first 6 months?"
- "What's the biggest challenge the team is facing right now?"

### About the Team
- "How big is the team, and how do you divide work?"
- "What does the development lifecycle look like, from idea to production?"
- "How do you onboard new team members?"

### About Tech & Growth
- "What's your current tech stack for [relevant area]?"
- "Is there room to grow into more architectural or strategic decisions?"
- "How does the team stay current with new tools and methods?"

### About Culture (use these to prevent disappointment)
- "How would you describe the team culture?"
- "What does professional development look like here?"
- "Is there flexibility for remote/hybrid work?"
- "What's the balance between new projects and maintenance work?"
- "How would you describe the leadership style in this team?"
- "What do people who thrive here have in common?"

## Phone/Video Interview Tips
- Have STAR examples written out (use this file)
- Keep a glass of water nearby
- Smile when speaking (it changes your tone)
- Ask for clarification if a question is vague
- It's OK to take 5 seconds to think before answering
- End with: "Is there anything else you'd like to know about my background?"

## After the Application (Best Practice)

### Follow-Up Etiquette
- **Don't call to "stand out"** or to learn more about the role post-submission - this risks a negative impression
- If the employer specified a timeline, respect it and wait
- If no timeline was given and significant time has passed (2+ weeks), a brief call to ask about status is acceptable
- If you have genuinely new, relevant information to share, a short follow-up is fine

### Thank-You Notes
- When you receive any update (interview invitation, rejection, or status update), send a brief thank-you message
- Express appreciation for their time and the process
- Keep it short (2-3 sentences)

## Roleplay Guidelines
When the user asks for interview practice:
1. Ask which role/company to simulate
2. Start with easy warm-up questions ("Tell me about yourself")
3. Progress to role-specific technical questions
4. Include 1-2 behavioral questions using the competencies from the job posting
5. End with a tough question or curveball
6. After each answer, give brief feedback: what worked, what to sharpen
7. Suggest which STAR example would work best for each question
