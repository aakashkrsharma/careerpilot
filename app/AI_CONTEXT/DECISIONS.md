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
- `app/services/llm_service.py` calls `ollama.generate()` with a model name. Although `OLLAMA_BASE_URL` is read, it is not used to configure the call.
- Pydantic schemas are defined in `app/models/`, but are not used in the active service/UI workflow.

## Gaps, not settled decisions

- The intended approval boundary is not implemented: extraction output is shown but not saved, and approved data is not applied to candidate profiles.
- There is no account/user table or user-level isolation; candidate relationships alone do not provide multi-user isolation.
- Dependency manifests conflict and do not yet define a reproducible installation.
- There is no test suite or migration strategy.

Do not treat unimplemented behavior or earlier aspirational documentation as a completed technical decision.
