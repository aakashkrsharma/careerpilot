# Development Status

## Current status

The initial source/dependency audit and Phase 1 of the Resume Processing Pipeline were completed on 2026-11-18. The first end-to-end service workflow is implemented and covered by focused tests.

## Implemented

- Streamlit entry point and Dashboard, Upload Resume, and Review Information pages.
- SQLAlchemy models for candidates, resumes, extracted information, and extraction history.
- Local SQLite storage and candidate/resume management services.
- Resume upload and text extraction for PDF, DOCX, and TXT. Unsupported, unreadable, or empty resumes fail explicitly.
- Local Ollama extraction with Pydantic response validation. Connection, malformed-response, and empty-result failures are surfaced; sample candidate data is no longer returned.
- Pending extraction persistence, including candidate/resume IDs, prompt, and raw response. A resume is marked processed only after extraction persistence succeeds.
- Transactional review save, review/approval timestamps, and approved candidate-profile updates.
- Empty candidate profile fields are filled after approval. Replacing populated values requires a separate explicit choice.
- Focused service integration tests with temporary SQLite and mocked Ollama.

## Remaining limitations

- `OLLAMA_BASE_URL` is read but not used to configure the Ollama client; `OLLAMA_MODEL` is honored.
- Legacy `.doc` files are unsupported; upload accepts PDF, DOCX, and TXT.
- No user/account model or user-level isolation exists. Candidate IDs scope the candidate/resume/extraction workflow only.
- Upload and LLM processing run synchronously in Streamlit.
- Existing SQLite databases are not migrated automatically; `create_all()` only creates missing tables.
- Clean-virtualenv installation and a live Ollama/browser workflow have not been verified.

## Tests and dependencies

- Eight `unittest` cases cover PDF/DOCX/TXT extraction, invalid input, mocked Ollama success/failure, pending persistence, review/approval, no-overwrite behavior, candidate scoping, and unique-email rollback.
- `requirements.txt` is the sole pinned runtime manifest. It includes Streamlit, SQLAlchemy, Pydantic, pandas, Ollama, HTTPX, PyPDF2, python-docx, and email-validator.
- Dependency installation, UI imports, and `pip check` pass in the existing Python 3.14.4 virtual environment.
- Existing SQLAlchemy and PyPDF2 deprecation warnings remain.

## Project principles to preserve

- Keep data local and use Ollama rather than paid external model APIs.
- Keep business logic independent of Streamlit.
- Preserve original resume files on disk.
- Require human approval before applying extracted fields to a candidate profile.
- Do not overwrite populated profile fields without explicit replacement approval.
- Keep the implementation incremental and avoid unnecessary abstractions.

## Phase 1 conclusion

The upload → extraction → pending review → correction/approval → candidate profile flow is implemented and service-tested. Complete the remaining configuration/isolation decisions and a live local smoke test before broadening product scope.
