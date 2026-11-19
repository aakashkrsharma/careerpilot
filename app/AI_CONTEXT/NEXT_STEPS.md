# Next Steps

## Phase 1: resume processing pipeline — complete

Implemented and verified:

- focused service tests using temporary SQLite and mocked Ollama
- PDF/DOCX/TXT extraction with explicit errors for unsupported, unreadable, or empty files
- strict Pydantic validation of LLM output; failed or malformed responses are not replaced with sample candidate data
- persistence of successful extraction output, prompt, and raw response as pending review
- transactional reviewer edits and approval timestamps
- application of approved profile values, filling empty fields by default and replacing existing values only after a separate explicit choice
- integration coverage for the full service workflow, candidate scoping, and unique-email rollback

Twelve tests pass.

## Phase 2: configuration and isolation — complete

Implemented and decided:

- The Ollama client uses `OLLAMA_BASE_URL` and `OLLAMA_MODEL`; tests verify both the configured host and selected model.
- The current prototype is explicitly single-user. Candidate IDs scope candidate/resume/extraction operations; account-level isolation and authentication are out of scope until multi-user support is requested.
- Upload-page orchestration remains in the UI because it coordinates existing services without duplicating core business rules; no additional abstraction is needed now.

## Phase 3: verify and stabilize — complete

Verified:

- Installed `requirements.txt` in a clean Python 3.14.4 virtual environment; imports and `pip check` passed.
- Used local Ollama (`qwen3-coder:30b`) and a synthetic TXT resume to verify upload → extraction → review/approval → Dashboard display in the live Streamlit UI.
- Used a temporary database and test workspace; the user's existing database and resume files were not used or changed.
- Updated AI_CONTEXT documentation to reflect the verified behavior.

## Phase 4: profile and preferences — complete

Implemented and verified:

- structured candidate experience, skills, education, and years of experience
- preferred roles, locations, work modes, and minimum salary
- direct candidate profile editing through Streamlit
- approved resume extraction updating structured profile fields
- additive SQLite startup migration for existing databases
- profile update validation and migration tests

## Phase 5: job discovery and storage — complete

Implemented and verified:

- normalized `Job` model and local SQLite storage
- manual job entry and pasted descriptions/source URLs
- URL normalization and tracking-parameter removal
- duplicate prevention by normalized URL or manual title/company/location hash
- filters for title/company, location, work mode, skills, and experience

## Phase 6: explainable job matching — complete

Implemented and verified:

- deterministic candidate-to-job compatibility scores
- skill, experience, location, work-mode, and preferred-role components
- matched and missing skill lists
- ranked Jobs page results with expandable explanations
- exact and boundary tests for scoring, missing profile data, fallback skills, and ranking

## Phase 7: AI resume tailoring — complete

Implemented and verified:

- local Ollama job-specific draft generation
- strict JSON parsing and placeholder rejection
- candidate/job/resume scoping
- separate draft persistence with prompt and raw response
- editable suggestions, limitations, and draft text
- explicit review and approval timestamps
- text download and local export only after approval
- tests for malformed output, placeholders, scoping, approval, and export

## Phase 8: application management — core workflow complete

Implemented:

1. Alembic migrations for application history and the active-only duplicate index; startup creates baseline tables before applying versioned Phase 8 migrations.
2. Permanent application rows with a default 15-day exact-job cooldown and configurable same-company/different-role cooldown (zero days by default).
3. Up-to-20-job batch snapshots with strict, adjacent-role, location/work-mode, experience, and fallback-score relaxation.
4. Candidate-approved answer reuse and a clarification queue for missing, ambiguous, and high-stakes questions.
5. Candidate-approved, scoped answer-bank persistence and explicit `Applied` confirmation.
6. `JobSourceConnector` and `ApplicationExecutor` protocols, plus a manual-only adapter that hands off login, CAPTCHA, and submission steps.
7. Batch Review, Clarification Queue, Application Tracker, and Dashboard status summaries.
8. Integration tests for 14/16-day cooldown behavior, company cooldown configuration, progressive batch size/stages, clarification reuse, approval boundaries, migration preservation, and UI smoke behavior.

Current Phase 8 boundaries:

- The executor is manual-only; no automatic submission is enabled.
- Screening questions are still entered manually; external-form extraction and automatic answer filling are not enabled.

## Multi-source discovery engine — implemented

- Thirteen read-only connector types cover public ATS APIs, public job APIs, RSS/Atom, and mapped XML.
- Sources require local registration, explicit terms approval, and enablement. USAJOBS is disabled by default; Remotive is opt-in and limited to one registration with a six-hour minimum interval.
- The runner normalizes/upserts jobs, retains provider listing URLs, applies India/APAC eligibility, checks active applications and the 15-day cooldown, persists source health, rate-limits requests, and isolates source failures.
- Discover Jobs provides the on-demand UI. `python -m app.discovery_cli --candidate-id <id>` can be run by an OS scheduler.
- Source URLs and terms need candidate verification before enablement; tests use mocked responses and do not call live portals.

## Recommended next steps

1. Register and terms-check the initial permitted sources, starting with employer ATS boards hiring in India and authorized RSS/XML feeds. Add multiple Greenhouse, Lever, or Ashby boards as needed.
2. Verify real-source behavior, attribution, India/APAC filtering, currency parsing, cooldown reporting, and source-health recovery in the local UI. Keep USAJOBS disabled unless deliberately configured with its API key and contact User-Agent environment variables.
3. Use a local OS scheduler to call the CLI only after source intervals and search criteria are configured; no in-process scheduler is needed.
4. After discovery is exercised with candidate-managed sources, proceed to interview preparation. Consider form-question intake only where permitted, keeping candidate review and manual-only submission boundaries intact.
