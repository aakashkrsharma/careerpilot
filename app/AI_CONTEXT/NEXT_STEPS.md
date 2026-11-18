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

Ten tests pass. A complete live Ollama/review/approval workflow and clean-virtualenv install remain unverified.

## Phase 2: configuration and isolation — complete

Implemented and decided:

- The Ollama client uses `OLLAMA_BASE_URL` and `OLLAMA_MODEL`; tests verify both the configured host and selected model.
- The current prototype is explicitly single-user. Candidate IDs scope candidate/resume/extraction operations; account-level isolation and authentication are out of scope until multi-user support is requested.
- Upload-page orchestration remains in the UI because it coordinates existing services without duplicating core business rules; no additional abstraction is needed now.

## Phase 3: verify and stabilize — next

1. Run a clean-virtualenv dependency installation using `requirements.txt`.
2. Run the application with the configured local Ollama model and verify upload → review → approval and dashboard display in the UI.
3. Update all affected AI_CONTEXT documents from verified behavior before declaring the next phase complete.
4. Consider broader job-hunting features only after the pipeline and isolation expectations are stable.

## Out of scope for the immediate phase

- Paid or remote LLM APIs
- Microservices or a job queue
- Production hosting and multi-user authentication
- Additional job-hunting features beyond the resume pipeline
