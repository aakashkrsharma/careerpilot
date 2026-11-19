# Project Structure

## Overview

CareerPilot is structured as a small Python application with a Streamlit UI, a SQLAlchemy persistence layer, and local file handling. The structure intentionally favors simplicity: fewer moving parts, local data persistence, and easy debugging.

## Directory layout

```text
careerpilot/
├── AGENTS.md
├── requirements.txt
├── app/
│   ├── main.py
│   ├── database/
│   │   ├── database.py
│   │   └── models.py
│   ├── models/
│   │   ├── candidate.py
│   │   ├── extracted_info.py
│   │   └── resume.py
│   ├── services/
│   │   ├── candidate_service.py
│   │   ├── extraction_service.py
│   │   ├── llm_service.py
│   │   └── resume_service.py
│   ├── ui/
│   │   ├── dashboard_page.py
│   │   ├── profile_page.py
│   │   ├── review_page.py
│   │   └── upload_page.py
│   └── AI_CONTEXT/
│       ├── ARCHITECTURE.md
│       ├── DATABASE_SCHEMA.md
│       ├── DEVELOPMENT_STATUS.md
│       ├── INSTALLATION.md
│       ├── NEXT_STEPS.md
│       ├── PROJECT_OVERVIEW.md
│       ├── PROJECT_STRUCTURE.md
│       ├── TECH_STACK.md
│       └── USAGE.md
├── data/
│   └── resumes/
├── tests/
│   └── test_resume_pipeline.py
├── careerpilot.db
└── .env (optional local config)
```

## Core responsibilities

### `app/main.py`

This is the application entry point. It initializes the database and routes the app to Dashboard, Upload, or Review screens via a sidebar radio selector.

### `app/database/`

Contains the persistence layer:

- `database.py`: engine, SessionLocal, `get_db()`, and `init_db()`
- `models.py`: ORM models for candidate/resume/extraction data

### `app/services/`

Contains the business workflow:

- `candidate_service.py`: candidate creation, retrieval, and listing
- `resume_service.py`: file save and text extraction logic
- `llm_service.py`: Ollama prompt generation and response parsing
- `extraction_service.py`: extraction persistence, review, approval, and candidate profile updates

### `app/ui/`

Contains the end-user screens:

- `upload_page.py`: process resume uploads
- `review_page.py`: adjust and approve extracted fields
- `dashboard_page.py`: view summary and details
- `profile_page.py`: edit candidate profile and job preferences

### `data/resumes/`

Holds the uploaded resume files on disk with unique filenames to avoid collision.

### `tests/`

Contains focused service integration tests using a temporary SQLite database and mocked Ollama output.

## Data flow summary

1. UI creates or selects a candidate.
2. The uploaded file is saved under `data/resumes/`.
3. Text is extracted and stored with the resume row.
4. The LLM service validates structured output and the extraction service saves it as pending review.
5. The review page persists corrections and approval state.
6. Approved profile fields are applied only after approval; replacement of populated values requires explicit confirmation.
7. The dashboard reads candidate, resume, and extracted-info rows.

## Notable architectural choice

The project prefers a single-app, local-first model over microservices or external APIs. That keeps the codebase approachable, but it also means the app is not yet designed for multi-user or production deployment scenarios.
