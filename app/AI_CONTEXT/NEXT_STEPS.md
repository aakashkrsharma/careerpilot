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

Eight tests pass. A live Ollama/browser workflow and clean-virtualenv install remain unverified.

## Phase 2: configuration and isolation — next

1. Configure the Ollama client with both `OLLAMA_BASE_URL` and `OLLAMA_MODEL`; add a mocked test for host configuration.
2. Resolve the meaning of “candidate data isolation” for this single-user local app. Candidate/resume/extraction operations are candidate-scoped, but there is no account/user isolation.
3. Keep business logic independent of Streamlit; consider moving upload orchestration into a service only if it reduces UI responsibilities without adding unnecessary abstraction.

## Phase 3: verify and stabilize

1. Run a clean-virtualenv dependency installation using `requirements.txt`.
2. Run the application with the configured local Ollama model and verify upload → review → approval in the UI.
3. Update all affected AI_CONTEXT documents from verified behavior before declaring the next phase complete.
4. Consider broader job-hunting features only after the pipeline and isolation expectations are stable.

## Out of scope for the immediate phase

- Paid or remote LLM APIs
- Microservices or a job queue
- Production hosting and multi-user authentication
- Additional job-hunting features beyond the resume pipeline
