# Database Schema

## Overview

CareerPilot defines four SQLAlchemy tables in a local SQLite database: candidates, resumes, extracted information, and extraction history. The `ExtractedInfo` and `ExtractionHistory` tables are defined in the schema, but the current upload workflow does not write to them.

## Database location

The default database file is:

```text
careerpilot.db
```

This file is created in the project root when the app initializes the database.

## Tables

### 1. `candidates`

Represents the user/candidate profile being reviewed.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer (PK) | primary key |
| `full_name` | String | indexed |
| `email` | String | unique and indexed |
| `phone` | String | optional |
| `location` | String | optional |
| `linkedin` | String | optional |
| `github` | String | optional |
| `summary` | Text | optional |
| `created_at` | DateTime | default UTC now |
| `updated_at` | DateTime | auto-updated |

### 2. `resumes`

Stores the uploaded file and the extracted raw text for a candidate.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer (PK) | primary key |
| `candidate_id` | Integer (FK) | references `candidates.id` |
| `file_name` | String | indexed |
| `file_path` | String | unique path on disk |
| `extracted_text` | Text | full text extracted from the file |
| `is_processed` | Boolean | default `False` |
| `created_at` | DateTime | default UTC now |
| `updated_at` | DateTime | auto-updated |

### 3. `extracted_info`

Stores structured resume data and review state.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer (PK) | primary key |
| `candidate_id` | Integer (FK) | references `candidates.id` |
| `resume_id` | Integer (FK) | references `resumes.id` |
| `full_name` | String | extracted full name |
| `email` | String | extracted email |
| `phone` | String | extracted phone |
| `location` | String | extracted location |
| `linkedin` | String | extracted LinkedIn URL |
| `github` | String | extracted GitHub URL |
| `summary` | Text | extracted summary |
| `experience` | Text | extracted work history |
| `skills` | Text | extracted skills |
| `education` | Text | extracted education |
| `is_reviewed` | Boolean | default `False` |
| `is_approved` | Boolean | default `False` |
| `reviewed_at` | DateTime | optional |
| `approved_at` | DateTime | optional |
| `prompt_used` | Text | prompt text sent to the model |
| `llm_response` | Text | raw LLM output |
| `created_at` | DateTime | default UTC now |
| `updated_at` | DateTime | auto-updated |

### 4. `extraction_history`

Tracks extraction attempts and metadata for debugging and auditing.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer (PK) | primary key |
| `candidate_id` | Integer (FK) | references `candidates.id` |
| `resume_id` | Integer (FK) | references `resumes.id` |
| `extraction_type` | String | e.g. `full_resume` |
| `prompt_used` | Text | prompt text |
| `llm_response` | Text | raw LLM output |
| `is_successful` | Boolean | default `True` |
| `error_message` | Text | optional |
| `started_at` | DateTime | default UTC now |
| `completed_at` | DateTime | optional |
| `created_at` | DateTime | default UTC now |

## Relationships

- `Candidate` has many `Resume` rows
- `Candidate` has many `ExtractedInfo` rows
- each `Resume` can have one or more corresponding `ExtractedInfo` records
- `ExtractionHistory` links attempts back to a candidate and resume

## Notes

- the database is intentionally simple and local-first
- there are no complex indexes or migration scripts yet
- the schema is designed for a prototype workflow rather than enterprise-scale data processing
- `Resume.is_processed` is set to `True` when the resume record is created, before successful LLM extraction is established.
- ORM foreign keys do not declare cascade-delete behavior.
- no schema migration mechanism is present; `create_all()` creates missing tables but does not migrate existing ones.
