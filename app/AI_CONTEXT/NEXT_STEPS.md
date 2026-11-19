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

## Phase 8: application management — first slice complete

Implemented and verified:

1. Versioned SQLite migrations for applications, answer bank, batches, clarification requests, and status events.
2. Permanent application and answer-bank models with the approved scoped uniqueness constraint.
3. Answer resolution, scope precedence, sensitivity, expiry, and explicit approval.
4. Permanent duplicate detection using normalized URLs and candidate/source/title/company/location identity.
5. ApplicationService and transition validation for the core status machine.
6. AnswerBankService and integration tests for reuse and scoped coexistence.
7. Tests for duplicate prevention across source labels, manual and URL representations, status events, and migration constraints.

Second slice:

1. Add batch selection snapshots and progressive relaxed matching up to 20 jobs.
2. Add clarification requests and a clarification queue.
3. Add application preparation and manual-safe execution adapters.
4. Add source connector protocol and normalized discovery contract.

Later slices:

1. Integrate permitted source collectors.
2. Add safe automatic executors only after source-specific approval.
3. Extend dashboard and interview/application tracking.
