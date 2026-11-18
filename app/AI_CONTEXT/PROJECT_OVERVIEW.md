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

The first resume-processing pipeline is implemented as an early local prototype:

- Streamlit provides Dashboard, Upload Resume, and Review Information pages.
- SQLAlchemy models define candidates, resumes, extracted information, and extraction history.
- SQLite is hard-coded as `sqlite:///./careerpilot.db`.
- PDF, DOCX, and TXT files are saved under `data/resumes/`; extracted text is stored in the `resumes` table.
- Successful, Pydantic-validated model output is stored as pending `ExtractedInfo`, with the prompt and raw response.
- Review corrections, review status, and approval timestamps are persisted transactionally.
- Approved profile fields fill empty candidate values; replacing populated values requires explicit reviewer confirmation.

## Important constraints

- Ollama is used for local inference; failures and malformed/empty responses are surfaced instead of replaced with sample candidate data. `OLLAMA_BASE_URL` is read but not yet used to configure the client.
- The app has no user/authentication model. Candidate-to-resume relationships are implemented, but this is not multi-user or per-user data isolation.
- Legacy `.doc` is not supported; upload accepts PDF, DOCX, and TXT.
- Focused pipeline tests exist. Runtime dependencies are consolidated in `requirements.txt` and verified in the existing Python 3.14.4 environment; a clean-virtualenv install has not yet been verified.

## Maturity

Treat the project as an early prototype. The next goal is to complete the remaining configuration/isolation decisions and validate the flow against a live local Ollama instance before adding broader job-hunting features or production deployment concerns.
