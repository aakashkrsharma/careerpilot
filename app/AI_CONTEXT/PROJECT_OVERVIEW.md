# Project Overview

CareerPilot is intended to be a local-first AI job-hunting assistant. The project handoff targets Python 3.14, Streamlit, SQLite, SQLAlchemy, Pydantic, and Ollama, with no paid external AI APIs.

## Product goal

CareerPilot supports candidates through job discovery, matching, resume tailoring,
application preparation, clarification, and application tracking. Candidate data,
job records, and application history remain local. Profile changes, answer reuse,
batch approval, and application completion require candidate review.

## Current implementation

The resume pipeline and Phases 4–8 application workflow are implemented as an
early local prototype:

- Streamlit provides Dashboard, Upload Resume, and Review Information pages.
- SQLAlchemy models define candidates, resumes, extracted information, and extraction history.
- SQLite is hard-coded as `sqlite:///./careerpilot.db`.
- PDF, DOCX, and TXT files are saved under `data/resumes/`; extracted text is stored in the `resumes` table.
- Successful, Pydantic-validated model output is stored as pending `ExtractedInfo`, with the prompt and raw response.
- Review corrections, review status, and approval timestamps are persisted transactionally.
- Approved profile fields fill empty candidate values; replacing populated values requires explicit reviewer confirmation.
- Candidate profiles include structured experience, skills, education, experience level, and job-search preferences. A dedicated profile page allows direct edits.
- Jobs can be entered manually or pasted with source metadata, and are stored locally with URL normalization and duplicate prevention.
- Jobs can be ranked against a candidate using transparent deterministic matching: skills, experience, location, work mode, and preferred roles.
- Job-specific resume drafts can be generated locally, reviewed and edited by the user, approved, and exported as text without changing the original resume.
- Application batches select up to 20 eligible jobs using progressive match relaxation and exclude active or cooldown-blocked applications.
- Application history is retained in SQLite. Exact-job reapplications use a 15-day cooldown by default; a different role at the same company is immediately eligible by default.
- Candidate-approved screening answers can be saved and reused by question key and scope. Missing, ambiguous, and high-stakes questions pause the application in a clarification queue.
- A manual-only execution adapter provides handoff steps and never bypasses authentication or CAPTCHA walls. Candidates confirm manual completion in the Application Tracker.
- The `JobSourceConnector` and `ApplicationExecutor` protocols define extension points; no automated job collectors or submission adapters are currently included.

## Important constraints

- Ollama is used for local inference; failures and malformed/empty responses are surfaced instead of replaced with sample candidate data. `OLLAMA_BASE_URL` and `OLLAMA_MODEL` configure the Ollama client.
- The app is intentionally single-user for the current prototype. Resume and extraction operations are scoped by candidate ID; there is no account-level authentication or multi-user isolation.
- Legacy `.doc` is not supported; upload accepts PDF, DOCX, and TXT.
- SQLite schema changes use Alembic for Phase 8 tables, with existing candidate-profile columns added during startup. Runtime dependencies are consolidated in `requirements.txt`.
- Screening questions currently enter through the Clarification Queue UI; question extraction from external application forms is not implemented.

## Maturity

Treat the project as an early prototype. Job discovery is manual, application
forms are not automatically filled, and submission is not automated. Add future
connectors and executors only within each source's permitted use and safety
boundaries.
