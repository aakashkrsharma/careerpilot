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

Ten tests pass.

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

## After Phase 3

- Gather user feedback and choose the next job-hunting feature before expanding scope.
- Keep account-level isolation out of scope unless multi-user support is requested.
- Paid or remote LLM APIs
- Microservices or a job queue
- Production hosting and multi-user authentication
- Additional job-hunting features beyond the resume pipeline
