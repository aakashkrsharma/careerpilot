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

- `app/main.py` runs a Streamlit application with Dashboard, Upload, and Review pages.
- `app/database/database.py` configures a fixed SQLite URL: `sqlite:///./careerpilot.db`.
- `app/database/models.py` defines Candidate, Resume, ExtractedInfo, and ExtractionHistory tables.
- `app/services/resume_service.py` stores uploaded files in `data/resumes/` and keeps extracted text in SQLite.
- `app/services/llm_service.py` configures an Ollama client from `OLLAMA_BASE_URL` and selects the model with `OLLAMA_MODEL`.
- `app/services/llm_service.py` calls local Ollama and validates its JSON response with the Pydantic extraction schema. Failed or malformed responses are surfaced, not replaced with sample candidate data.
- `app/services/extraction_service.py` stores pending extraction, review state, and approved candidate profile updates transactionally.
- The app is single-user for the current prototype. Candidate IDs scope resume and extraction operations; account-level isolation and authentication are out of scope until multi-user support is requested.
- Upload UI orchestration remains in the page because it coordinates existing services without duplicating core business rules; a separate pipeline abstraction is not currently justified.
- Existing candidate profile values are preserved by default; replacing populated values requires explicit confirmation.
- `requirements.txt` is the canonical pinned runtime dependency list and was verified in the existing Python 3.14.4 environment.

## Remaining gaps

- There is no migration strategy for existing SQLite databases.

Do not treat unimplemented behavior or earlier aspirational documentation as a completed technical decision.
