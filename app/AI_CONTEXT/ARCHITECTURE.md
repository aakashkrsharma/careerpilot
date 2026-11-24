# Architecture

## Overview

CareerPilot uses a simple layered architecture centered on a Streamlit frontend and a local SQLite database. The project is intentionally compact: UI pages call service objects that orchestrate persistence, file handling, and LLM extraction. The design prioritizes local use and ease of debugging over distributed or production-grade infrastructure.

## High-level component model

```text
┌──────────────────────────────┐
│ Streamlit UI                 │
│  - Dashboard                │
│  - Candidate Profile        │
│  - Jobs & Discovery         │
│  - Apply Workflow           │
│  - Application Tracker      │
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
│ - BatchSelectionService      │
│ - ClarificationQueueService  │
│ - JobSourceRegistryService   │
│ - JobDiscoveryService       │
│ - source connector adapters  │
│ - JobSourceConnector protocol│
│ - ApplicationExecutor protocol│
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
- `Job`: canonical local job opportunity and salary currency/period metadata
- `JobSource`: configured connector instance and persistent health/rate-limit state
- `JobSourceListing`: provider-specific listing identity and URL mapped to a canonical job

### Storage characteristics

- database is SQLite by default (`careerpilot.db`)
- data is stored locally in a single file
- SQLAlchemy sessions are scoped to service operations and closed after the transaction completes
- baseline tables are created first; Alembic owns Phase 8 application and discovery schema changes and startup upgrades to `head`

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
- create manual local job records and stable source keys
- idempotently upsert normalized connector records across providers
- retain provider-specific listing links while deduplicating canonical jobs
- filter jobs by title/company, location, work mode, skills, and experience

### `JobSourceRegistryService`

- registers and manages connector instances, configuration, source groups, and terms approval
- rejects stored credentials; connectors reference environment variables for required secrets
- records source health and next-allowed timestamps in `JobSource`

### `JobDiscoveryService`

- runs enabled and terms-approved connectors on demand and skips sources that are not due
- spaces requests by at least one second within a run, applies bounded HTTP timeouts/response sizes, and backs off after failures
- isolates individual source failures and reports per-source counts and status
- filters for explicit India/APAC/global-remote eligibility by default, upserts jobs, and counts active/cooldown-blocked application history without deleting listings
- never sends candidate identity, resume content, or answer-bank data; only user-selected search criteria are passed to sources

### Connector adapters

The registry provides read-only adapters for Greenhouse, Lever, Ashby,
Arbeitnow, Jobicy, Remote OK, Himalayas, We Work Remotely RSS, generic RSS/Atom,
mapped XML, SmartRecruiters, Remotive (opt-in), and USAJOBS (disabled by
default). Multiple employer boards can be registered for ATS connectors.
Workday is supported only through an employer-provided authorized XML-compatible
feed; guessed or scraped endpoints are not used. Remotive is limited to one
registered source and a six-hour minimum interval.

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

- retains all application records and enforces a configurable 15-day exact-job reapply cooldown by default
- uses a configurable company cooldown of zero days by default, allowing a different role at the same company immediately
- prevents duplicate active applications with a SQLite partial unique index; cooldown checks remain service-level because SQLite indexes cannot express a time-relative rule
- validates and records application status transitions
- records every status change as an immutable event
- requires batch approval before progressing a batched application
- requires explicit candidate confirmation before setting an application to `applied`
- keeps external submission separate from local preparation and history

### `AnswerBankService`

- stores approved reusable answers with scope and sensitivity metadata
- resolves candidate profile facts, job/company/source-scoped answers, and global answers
- requires explicit approval for sensitive and high-stakes answers
- never stores passwords, OTPs, cookies, authentication tokens, or identity-document secrets

### `BatchSelectionService`

- selects and snapshots up to 20 available jobs by strict match, adjacent role, location/work-mode relaxation, experience relaxation, then a configurable fallback score
- ranks within each stage by the existing deterministic match score and matched-skill count
- excludes active applications and exact-job or company cooldown matches using `ApplicationService`
- creates draft batches that require explicit candidate approval before application preparation; cancelling a draft releases active identities without deleting history

### `ClarificationQueueService`

- assesses supplied screening questions against approved answer-bank entries
- reuses approved non-high-stakes answers when the question is not marked ambiguous
- queues missing, ambiguous, and high-stakes answers; high-stakes entries always require fresh candidate review
- stores candidate-approved answers and their selected scope in the answer bank in the same transaction as resolving the question
- moves applications to `needs_clarification` and allows `ready` only after all requests are resolved

### Extension contracts and safe execution

- `JobSourceConnector` returns normalized `SourceJob` records from a `JobDiscoveryCriteria`; it does not persist jobs or application history
- `ApplicationExecutor` receives an application, job, and explicit candidate approval and returns a typed execution result
- `ManualApplicationExecutor` always hands off to the candidate; it never signs in, solves CAPTCHAs, or submits forms
- discovery connectors are concrete and read-only; no automated application submission adapter is enabled
## UI layer

Location: `app/ui/`

`app/main.py` provides five top-level horizontal navigation sections:
Dashboard, Candidate Profile, Jobs & Discovery, Apply Workflow, and Application
Tracker. The Dashboard includes quick-action buttons. Jobs & Discovery nests
source management/discovery and ranked matches/manual entry; Apply Workflow
nests batch review, resume tailoring, and clarification. The nested workspaces
reuse the existing page modules and service logic.

### `upload_page.py`

- provides the reusable `process_uploaded_resume()` flow used by Candidate Profile
- validates and saves the file, extracts text, creates a resume record, and calls the LLM extraction flow
- persists valid output as pending review before showing it
- reports parsing, LLM, and persistence failures instead of continuing with empty text or sample data

### `review_page.py`

- provides `show_inline_extraction_review()` for review inside Candidate Profile; the legacy standalone page is not in the primary navigation
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
- the main navigation adds quick actions to the other four sections

### `profile_page.py`

- lets the user select a candidate and upload a resume from the page header
- creates a candidate when none exists, then retains that candidate selection across reruns
- processes new resumes and renders extracted fields for inline review
- clears pending review state only after the candidate confirms and saves
- edits contact, summary, experience, skills, education, and experience level
- edits preferred roles, locations, work modes, and minimum salary
- saves validated profile and preference changes through `CandidateService`

### `jobs_page.py`

- manually adds a job or pastes source metadata and a description
- displays and filters locally stored jobs
- links to provider-specific listings when available, preserving source attribution
- ranks jobs for the selected candidate and explains compatibility

### `job_discovery_page.py`

- registers and manages source connectors with explicit terms approval
- lets the candidate review and edit role/location search terms before a run
- triggers on-demand discovery and displays per-source health, rate limits, counts, and errors
- filters India-first results and leaves USAJOBS disabled unless explicitly enabled

### `tailoring_page.py`

- selects a candidate, target job, and optional source resume
- generates a local Ollama draft
- lets the user edit draft text, suggestions, and limitations
- requires explicit approval before disk export or download

### Phase 8 UI

- `batch_review_page.py`: reviews match stage, score, and job details; requires approval of draft batches
- `clarification_queue_page.py`: accepts screening questions, displays reused answers, and records explicitly approved clarifications
- `application_tracker_page.py`: displays permanent history, links approved tailored resumes, prepares manual handoffs, and confirms completion
- `dashboard_page.py`: summarizes application, clarification, ready, and applied counts

## Current data flow

1. Candidate Profile saves the original resume under `data/resumes/`.
2. `ResumeService` extracts text and stores it with a `Resume` row, initially unprocessed.
3. `LLMService` calls Ollama and validates its JSON output.
4. `ExtractionService` persists valid output as pending review and marks the resume processed.
5. Candidate Profile renders the pending extraction inline; `ExtractionService` saves corrections and approval status in one database transaction.
6. Approved fields update empty profile values; replacing populated values requires explicit reviewer confirmation.
7. Discover Jobs sends only reviewed search terms/locations to enabled, terms-approved connectors. The runner normalizes and upserts records, retains provider listings, applies India/APAC eligibility, and checks active/cooldown application history.
8. Batch Review stores up to 20 selected application records as a draft snapshot; application status progression requires batch approval.
9. The Clarification Queue reuses eligible approved answers or pauses on unresolved questions; a resolved answer can be saved atomically to the answer bank.
10. The Application Tracker moves prepared work to a manual handoff; only an explicit candidate confirmation records `applied`.

## Runtime assumptions

- the app is designed to run locally on one machine
- the Ollama server defaults to `http://localhost:11434`; `OLLAMA_BASE_URL` can override it
- `OLLAMA_MODEL` selects the local model and defaults to `qwen3-coder:30b`
- no asynchronous queue or in-process scheduler is used; the one-shot CLI can be invoked by the local OS scheduler

## Operational constraints

This architecture is intentionally lightweight and assumes a single local user. Candidate IDs scope candidate/resume/extraction operations, but there is no account-level isolation. Other tradeoffs include:

- no service isolation or horizontal scaling
- connector retries are not automatic; source-level rate limits and failure backoff are persisted and subsequent runs are operator/scheduler-triggered
- no formal API boundary between the UI and backend
- screening questions must be supplied manually; form extraction and automatic filling are not implemented
- source connectors are read-only and opt-in; no portal scraping is included
- application execution is manual-only; no automated submission adapter is enabled

## Security and robustness notes

The app is currently a local prototype. It has no authentication or user-level isolation, and uploaded files contain potentially sensitive personal information. It should not be exposed as a multi-user service without explicit access control and data-protection work. Discovery requests are HTTPS-only, reject local/private-network hosts and redirects, and cap response size. Search terms and locations are the only candidate-derived values sent to sources; credentials remain in environment variables. Connectors require explicit source registration and terms approval. Extraction, parsing, and source failures are surfaced rather than converted to sample data.
