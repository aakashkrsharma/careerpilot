# CareerPilot Memory

## Current build status
- Phases 1-8 + multi-source discovery implemented and tested (64 tests passing).
- Application packets: `data/application_packets/<id>/` (job, resume, answers, handoff, metadata).
- DOCX export added to tailoring service.
- Public URL job import added (schema.org JobPosting parse, no crawling).
- Bulk screening-question import added to clarification queue.
- Follow-up tracking and CSV export added to application tracker.
- Packet preparation button added to batch review and tracker.

## Key decisions
- Local-first, Ollama, SQLite; no paid APIs.
- Manual submission only; no CAPTCHA/login automation.
- Read-only discovery; terms-gated sources.

## Remaining manual steps by design
- Source registration/terms approval.
- Account login, CAPTCHA, final submit.
- Review/approve AI artifacts.

## External reference: claude-job-skill (mayankjoshii)
- A Claude Skill that searches 12+ Indian/global portals (Naukri, LinkedIn, Instahyre, Cutshort, Hirist, Indeed India, Foundit, Shine, TimesJobs, Glassdoor, AngelList, WeWorkRemotely) via site: web searches, generates tailored resumes/cover letters, tracks applications, Gmail status, nightly automation.
- Not directly installable into this OpenCode agent; useful as a discovery pattern to adapt (search-engine-based job discovery) for portals CareerPilot cannot connect to directly. Could be added later as an optional "search engine discovery" module with the same terms/rate-limit boundaries.
- It does not submit applications; user submits manually.

## Next focus
- Auto-build draft batches from discovered jobs (one-click).
- Form question extraction from pasted HTML (optional).
- PDF export (needs a PDF library).
