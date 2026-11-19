# Technical Decisions and Current State

This document distinguishes the project handoff's intended principles from choices verified in the current source.

## Intended principles from the project handoff

- Local-first processing with Ollama; no paid external AI APIs.
- Streamlit UI with business logic kept independent from the UI.
- SQLite persistence through SQLAlchemy.
- Original resume files stored on disk.
- Human approval before extracted information changes a candidate profile.
- Do not overwrite existing candidate data without explicit approval.
- Prefer a simple modular application over microservices or unnecessary abstractions.

## Choices currently present in source

- `app/main.py` runs a Streamlit application with Dashboard, Candidate Profile, Jobs, Discover Jobs, Resume Tailoring, and Phase 8 application-workflow pages.
- `app/database/database.py` configures a fixed SQLite URL: `sqlite:///./careerpilot.db`.
- `app/database/models.py` defines candidate/resume/extraction, job, source-registry, source-listing, and application-workflow tables.
- `app/services/resume_service.py` stores uploaded files in `data/resumes/` and keeps extracted text in SQLite.
- `app/services/llm_service.py` configures an Ollama client from `OLLAMA_BASE_URL` and selects the model with `OLLAMA_MODEL`.
- `app/services/llm_service.py` calls local Ollama and validates its JSON response with the Pydantic extraction schema. Failed or malformed responses are surfaced, not replaced with sample candidate data.
- `app/services/extraction_service.py` stores pending extraction, review state, and approved candidate profile updates transactionally.
- The app is single-user for the current prototype. Candidate IDs scope resume and extraction operations; account-level isolation and authentication are out of scope until multi-user support is requested.
- Upload UI orchestration remains in the page because it coordinates existing services without duplicating core business rules; a separate pipeline abstraction is not currently justified.
- Candidate experience, skills, education, and job preferences are stored as candidate profile columns. Text fields are used for roles, locations, skills, and work modes instead of normalized related tables for this MVP foundation.
- Manual jobs and read-only connector jobs share the canonical `Job` store. `JobService.upsert_normalized_job` deduplicates normalized URLs and title/company/location identities across providers while `JobSourceListing` retains each provider's ID and URL.
- Thirteen connector types are implemented: Greenhouse, Lever, Ashby, Arbeitnow, Jobicy, Remote OK, Himalayas, We Work Remotely RSS, generic RSS/Atom, mapped XML, SmartRecruiters, Remotive, and USAJOBS. Multiple employer ATS boards can be registered independently.
- Connector use is opt-in and terms-gated. USAJOBS is disabled by default; Remotive requires explicit opt-in, is limited to one registered source, and has a six-hour minimum interval. Workday URLs are not guessed; only an authorized employer-provided XML-compatible feed may be configured.
- The default discovery filter is India-first and accepts explicit India, India-city, APAC, or worldwide eligibility; ambiguous `Remote` listings are excluded. INR/LPA compensation is retained with currency/period metadata, with LPA normalized to annual INR rupees and no currency conversion.
- The runner is on-demand in Streamlit and also has a one-shot CLI entry point for local OS scheduling. Source intervals, 1-second in-run request spacing, bounded HTTP requests, failure isolation, and exponential backoff are enforced locally.
- Only user-selected search terms and locations are sent to enabled sources; candidate identity, resume content, and answer-bank data remain local. Credentials are environment-variable references and are not stored in SQLite.
- Job duplicates use normalized source URLs or a stable hash of title, company, and location for manual entries without URLs.
- Phase 6 compatibility scores are deterministic and explainable. Matching does not infer or fabricate candidate information.
- Resume tailoring uses the verified candidate profile and optional original resume text. It generates separate drafts and does not modify originals or candidate profile values. Export requires explicit approval.
- Phase 8 application records are retained permanently. Discovery and batching never purge application history.
- Exact-job reapplications are blocked for 15 days by default, using `applied_at` or (when unavailable) `submitted_at`; after the cooldown, a new history row is allowed.
- Same-company/different-role reapplications have a zero-day cooldown by default. Both cooldowns are configurable in `ApplicationService` and batch selection.
- A partial unique SQLite index prevents multiple active rows for the same candidate/dedup key. Time-based cooldowns remain service checks because they cannot be represented by a time-relative SQLite index.
- Duplicate identity uses candidate ID plus a normalized source URL, external identity, or a stable title/company/location hash, with a compatibility check for manual and URL representations.
- Answer-bank uniqueness is `(candidate_id, canonical_key, scope, scope_value)` so global and company-specific answers coexist.
- Sensitive and high-stakes answers require explicit candidate approval, and high-stakes role-specific values may require a new approval even for a matching key.
- CAPTCHA solving, authentication credential collection, and submission through protected walls are prohibited.
- The current `ManualApplicationExecutor` always provides candidate-controlled handoff instructions. Candidate confirmation is required before `Applied`.
- Startup creates baseline tables, adds missing legacy candidate-profile columns, then runs Alembic migrations through `0003_job_discovery`. The partial active-duplicate index replaces lifetime uniqueness without deleting historical rows; the discovery migration adds provider provenance and salary metadata while preserving old jobs.
- Existing candidate profile values are preserved by default; replacing populated values requires explicit confirmation.
- `requirements.txt` is the canonical pinned runtime dependency list and was verified in the existing Python 3.14.4 environment.

## Remaining gaps

- Each external source still needs candidate configuration, terms verification, and live behavior validation before use. Tests use fixtures and do not call production feeds.
- Workday has no guessed endpoint adapter; use only a documented employer-provided feed through mapped XML.
- Screening questions are entered manually; external form extraction and automatic answer filling are not implemented.
- Automatic application submission remains disabled.
- The single-user local prototype has no account authentication or user-level isolation.

Do not treat unimplemented behavior or earlier aspirational documentation as a completed technical decision.
