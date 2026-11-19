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

## Phase 5: job discovery and storage — next

1. Define and migrate a normalized `Job` model with source, URL, title, company, location, description, remote/work mode, posted date, and extraction status.
2. Support manual job-description/URL entry first, keeping the local-first architecture and no paid APIs.
3. Add source integration only for sources that provide permitted access; one source may be implemented first.
4. Add filtering by skills, location, experience level, work mode, and preferences.
5. Deduplicate jobs by stable source/URL key and add tests for filtering and duplicate prevention.
