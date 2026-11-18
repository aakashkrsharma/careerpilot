# Project Overview

CareerPilot is intended to be a local-first AI job-hunting assistant. The project handoff targets Python 3.14, Streamlit, SQLite, SQLAlchemy, Pydantic, and Ollama, with no paid external AI APIs.

## Product goal

The planned first feature is a reliable resume-processing pipeline:

1. Upload a PDF or DOCX resume.
2. Preserve the original file locally and extract its text.
3. Use a local LLM to produce structured candidate information.
4. Let the candidate review and correct the proposed information.
5. Apply information to the candidate profile only after explicit approval.

Candidate information must not be overwritten by unreviewed extraction results. Keep business logic independent of Streamlit and avoid unnecessary infrastructure or abstractions.

## Current implementation

The codebase is an early prototype, not yet an end-to-end implementation of the planned pipeline:

- Streamlit provides Dashboard, Upload Resume, and Review Information pages.
- SQLAlchemy models define candidates, resumes, extracted information, and extraction history.
- SQLite is hard-coded as `sqlite:///./careerpilot.db`.
- Resume files are written under `data/resumes/`; extracted text is stored in the `resumes` table.
- The upload page calls the LLM service and displays returned fields, but does not persist them as `ExtractedInfo`.
- The review page reads `ExtractedInfo`, so a new upload cannot reach a working review flow through the current UI.
- Candidate profile fields are not updated from reviewed/approved extraction data.

## Important constraints

- Ollama is intended for local inference, but current LLM failures are converted to fabricated sample data; `OLLAMA_BASE_URL` is read but not used to configure the Ollama client.
- The app has no user/authentication model. Candidate-to-resume relationships are implemented, but this is not multi-user or per-user data isolation.
- Pydantic schemas exist under `app/models/` but are not used in the active UI/service workflow.
- The upload widget accepts `.doc`, but the parser uses `python-docx`, which handles DOCX rather than legacy binary DOC files.
- The test directory is empty. The dependency manifests are inconsistent and do not provide a verified clean installation for the active parser/LLM imports.

## Maturity

Treat the project as an implementation skeleton/prototype. The immediate goal is to establish a tested, trustworthy resume-processing and human-approval pipeline before adding broader job-hunting features or production deployment concerns.
