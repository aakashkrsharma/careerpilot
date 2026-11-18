# Next Steps

The initial implementation assessment is complete. Do not expand product scope until the resume-processing pipeline is working, human-reviewed, and tested.

## Phase 1: make the pipeline reliable

1. Reconcile the dependency manifests with the actual Python 3.14 environment and choose supported PDF/DOCX parsers and Ollama client dependencies.
2. Add focused tests for candidate/resume services, text extraction, LLM response parsing, and persistence. Use a temporary SQLite database and mock Ollama; tests must not require a live model.
3. Implement a complete extraction persistence path: save proposed fields, source resume, prompt/response, and pending-review status.
4. Fix review updates to load and persist records in one valid database session; record review/approval state and timestamps.
5. Apply approved fields to the candidate profile only after explicit approval, preserving existing non-empty values unless the user approves the replacement.
6. Validate file types and parsing results; stop with a clear error rather than proceeding with empty text or sample extraction data.
7. Verify upload → extraction → pending review → edits → approval → candidate profile persistence with focused integration tests.

## Phase 2: align configuration and boundaries

1. Configure the Ollama client with `OLLAMA_BASE_URL` and `OLLAMA_MODEL`.
2. Use Pydantic schemas at the extraction boundary to validate the expected output shape, or remove unused schemas if they are not needed.
3. Keep service/business logic independent of Streamlit and reduce direct database access from UI pages.
4. Confirm the intended meaning of candidate isolation. The current schema has candidate relationships but no user/account isolation.

## Phase 3: document and stabilize

1. Run the focused tests and a local Streamlit smoke test.
2. Update the AI_CONTEXT documents to reflect verified behavior and operational requirements.
3. Consider broader features (job tracking, exports, search, authentication) only after the pipeline is stable and requirements are explicit.

## Out of scope for the immediate phase

- Paid or remote LLM APIs
- Microservices or a job queue
- Production hosting and multi-user authentication
- Additional job-hunting features beyond the resume pipeline
