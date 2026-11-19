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
│ - ExtractionService          │
│ - JobService                 │
│ - MatchingService            │
│ - TailoringService           │
│ - ApplicationService         │
│ - AnswerBankService          │
│ - SourceConnector interface  │
│ - ExecutionEngine interface  │
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
- SQLAlchemy sessions are scoped to service operations and closed after the transaction completes

## Service layer

Location: `app/services/`

### `CandidateService`

Responsibilities:

- create new candidates
- fetch candidates by ID or email
- list all candidates
- update candidate fields
- retrieve a candidate's resumes and extracted info
- update structured profile and job-preference fields

### `ResumeService`

Responsibilities:

- create a local storage directory at `data/resumes/`
- save an uploaded file under a UUID-based filename
- extract text from PDF/DOCX/TXT files
- create a `Resume` row in the database

### `LLMService`

Responsibilities:

- build a structured extraction prompt
- call the configured Ollama server using an `ollama.Client`
- select the Ollama host and model from `OLLAMA_BASE_URL` and `OLLAMA_MODEL`
- validate JSON output against the Pydantic extraction schema
- surface Ollama and response-validation failures without fabricating candidate data

### `ExtractionService`

- verify candidate/resume relationships and extracted field types
- save model output, prompt, and raw response as pending review
- save reviewer corrections and approval state transactionally
- update candidate profile fields only after approval, preserving populated values unless replacement is explicitly selected

### `JobService`

- normalize and validate source URLs
- create local job records and stable source keys
- prevent duplicate jobs
- filter jobs by title/company, location, work mode, skills, and experience

### `MatchingService`

- compare candidate skills with required job skills
- calculate skill, experience, location, work-mode, and role scores
- list matched and missing skills
- rank jobs and provide human-readable explanations

### `TailoringService`

- builds an Ollama prompt from approved candidate facts and target-job facts
- generates and validates a JSON resume draft
- persists review state, prompt, and raw response separately
- allows human editing and explicit approval
- exports only approved drafts to local text files

### `ApplicationService`

- creates permanent application records and permanent deduplication keys
- validates and records application status transitions
- records every status change as an immutable event
- prepares applications only after candidate, job, tailored resume, and answer-bank approvals
- keeps external submission separate from local preparation and history

### `AnswerBankService`

- stores approved reusable answers with scope and sensitivity metadata
- resolves candidate profile facts, job/company/source-scoped answers, and global answers
- requires explicit approval for sensitive and high-stakes answers
- never stores passwords, OTPs, cookies, authentication tokens, or identity-document secrets

### Future source and execution contracts

- `JobSourceConnector` discovers and normalizes jobs without owning application history or browser execution
- `ApplicationExecutor` declares whether a source can safely prepare or submit
- `ApplicationExecutor` must detect authentication walls and CAPTCHAs and fall back to manual guidance
- automatic submission requires source capability, complete approved preparation, clarification resolution, and explicit candidate submission approval

## UI layer

Location: `app/ui/`

### `upload_page.py`

- lets the user select or create a candidate
- validates and saves the file, extracts text, creates a resume record, and calls the LLM extraction flow
- persists valid output as pending review before showing it
- reports parsing, LLM, and persistence failures instead of continuing with empty text or sample data

### `review_page.py`

- loads the candidate's resumes and queries an extraction row for the selected resume
- exposes editable text fields for core profile attributes
- allows the user to correct and approve extracted data
- persists review edits and timestamps through `ExtractionService`
- applies approved values to empty candidate fields; replacing populated values requires explicit confirmation

### `dashboard_page.py`

- lists all candidates in a Streamlit dataframe
- displays candidate summary details
- shows count of resumes and extracted info records
- renders a profile detail section for a selected candidate

### `profile_page.py`

- lets the user select a candidate
- edits contact, summary, experience, skills, education, and experience level
- edits preferred roles, locations, work modes, and minimum salary
- saves validated profile and preference changes through `CandidateService`

### `jobs_page.py`

- manually adds a job or pastes source metadata and a description
- displays and filters locally stored jobs
- links to a source URL when provided
- ranks jobs for the selected candidate and explains compatibility

### `tailoring_page.py`

- selects a candidate, target job, and optional source resume
- generates a local Ollama draft
- lets the user edit draft text, suggestions, and limitations
- requires explicit approval before disk export or download

### Planned Phase 8 UI

- batch review and up-to-20-job selection
- clarification queue for missing or high-stakes screening questions
- application tracker with permanent status and audit history
- manual application guidance and candidate completion confirmation
- answer-bank review with scope and sensitivity markers

## Current data flow

1. The upload page saves the original resume under `data/resumes/`.
2. `ResumeService` extracts text and stores it with a `Resume` row, initially unprocessed.
3. `LLMService` calls Ollama and validates its JSON output.
4. `ExtractionService` persists valid output as pending review and marks the resume processed.
5. The review page saves corrections and approval status in one database transaction.
6. Approved fields update empty profile values; replacing populated values requires explicit reviewer confirmation.

## Runtime assumptions

- the app is designed to run locally on one machine
- the Ollama server defaults to `http://localhost:11434`; `OLLAMA_BASE_URL` can override it
- `OLLAMA_MODEL` selects the local model and defaults to `llama3`
- no asynchronous queue or worker processes are used at this time

## Operational constraints

This architecture is intentionally lightweight and assumes a single local user. Candidate IDs scope candidate/resume/extraction operations, but there is no account-level isolation. Other tradeoffs include:

- no service isolation or horizontal scaling
- no background retries or rate limiting
- no formal API boundary between the UI and backend

## Security and robustness notes

The app is currently a local prototype. It has no authentication or user-level isolation, and uploaded files contain potentially sensitive personal information. It should not be exposed as a multi-user service without explicit access control and data-protection work. Extraction and parsing failures are surfaced to the user rather than converted to sample data.
