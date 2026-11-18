# Architecture

## Overview

CareerPilot uses a simple layered architecture centered on a Streamlit frontend and a local SQLite database. The project is intentionally compact: UI pages call service objects that orchestrate persistence, file handling, and LLM extraction. The design prioritizes local use and ease of debugging over distributed or production-grade infrastructure.

## High-level component model

```text
┌──────────────────────────────┐
│ Streamlit UI                 │
│  - Upload page              │
│  - Review page              │
│  - Dashboard page           │
└──────────────┬───────────────┘
               │ calls
               ▼
┌──────────────────────────────┐
│ Service layer                │
│ - CandidateService           │
│ - ResumeService              │
│ - LLMService                 │
└──────────────┬───────────────┘
               │ reads/writes
               ▼
┌──────────────────────────────┐
│ Persistence layer            │
│ - SQLAlchemy ORM             │
│ - SQLite database           │
│ - local resume files        │
└──────────────────────────────┘
```

## Database layer

Location: `app/database/`

### Files

- `database.py`: creates the engine, session factory, and `init_db()`
- `models.py`: defines the ORM models

### Models

- `Candidate`: stores candidate identity and profile fields
- `Resume`: stores file metadata, file path, extracted text, and process state
- `ExtractedInfo`: stores structured fields reviewed/approved by the user
- `ExtractionHistory`: tracks prompts, responses, and extraction attempts

### Storage characteristics

- database is SQLite by default (`careerpilot.db`)
- data is stored locally in a single file
- SQLAlchemy sessions are opened per method invocation and closed in `finally` blocks

## Service layer

Location: `app/services/`

### `CandidateService`

Responsibilities:

- create new candidates
- fetch candidates by ID or email
- list all candidates
- update candidate fields
- retrieve a candidate's resumes and extracted info

### `ResumeService`

Responsibilities:

- create a local storage directory at `data/resumes/`
- save an uploaded file under a UUID-based filename
- extract text from PDF/DOCX/TXT files
- create a `Resume` row in the database

### `LLMService`

Responsibilities:

- build a structured extraction prompt
- call the local Ollama server using `ollama.generate(...)`
- parse the JSON output or use a fallback sample payload when extraction fails

## UI layer

Location: `app/ui/`

### `upload_page.py`

- lets the user select or create a candidate
- accepts a resume file
- saves the file, extracts text, creates a resume record, and calls the LLM extraction flow
- shows extraction output as JSON in the UI

### `review_page.py`

- loads the candidate's resumes and queries an extraction row for the selected resume
- exposes editable text fields for core profile attributes
- allows the user to approve or reject the extracted data
- attempts to save updated field values, but the current detached-instance/session handling does not reliably persist them

### `dashboard_page.py`

- lists all candidates in a Streamlit dataframe
- displays candidate summary details
- shows count of resumes and extracted info records
- renders a profile detail section for a selected candidate

## Current data flow and gaps

1. The upload page saves the original resume under `data/resumes/`.
2. `ResumeService` extracts text and stores it with a `Resume` row.
3. The upload page calls `LLMService`, which returns extracted fields for display.
4. The extraction result is not saved to `ExtractedInfo`; the review page therefore cannot review results produced through this upload path.
5. The review page currently edits a detached ORM instance and commits a separate session, so updates are not reliably persisted.
6. Candidate profile data is not updated from approved extraction data.

The intended pipeline must persist extraction as pending review, persist corrections and approval, then apply approved fields to the candidate profile without silently overwriting existing values.

## Runtime assumptions

- the app is designed to run locally on one machine
- the Ollama server is expected to be running at `http://localhost:11434`
- environment variables are optional but supported via `OLLAMA_BASE_URL` and `OLLAMA_MODEL`
- no asynchronous queue or worker processes are used at this time

## Operational constraints

This architecture is intentionally lightweight and therefore has tradeoffs:

- no multi-user session handling
- no service isolation or horizontal scaling
- no background retries or rate limiting
- no formal API boundary between the UI and backend

## Security and robustness notes

The app is currently a local prototype. It has no authentication or user-level isolation, and uploaded files contain potentially sensitive personal information. It should not be exposed as a multi-user service without explicit access control and data-protection work. LLM/parser fallback behavior also needs to distinguish real extraction from failure.
