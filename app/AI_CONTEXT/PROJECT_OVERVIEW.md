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

- Ollama is used for local inference; failures and malformed/empty responses are surfaced instead of replaced with sample candidate data. `OLLAMA_BASE_URL` and `OLLAMA_MODEL` configure the Ollama client.
- The app is intentionally single-user for the current prototype. Resume and extraction operations are scoped by candidate ID; there is no account-level authentication or multi-user isolation.
- Legacy `.doc` is not supported; upload accepts PDF, DOCX, and TXT.
- Focused pipeline tests exist. Runtime dependencies are consolidated in `requirements.txt`; installation was verified in a clean Python 3.14.4 environment, and the synthetic resume workflow was verified with local Ollama.

## Maturity

Treat the project as an early prototype. The configured resume flow is verified against local Ollama. Choose any broader job-hunting feature based on user feedback before expanding product scope.
