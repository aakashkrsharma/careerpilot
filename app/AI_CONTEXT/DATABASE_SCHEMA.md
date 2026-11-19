# Database Schema

## Overview

CareerPilot defines five SQLAlchemy tables in a local SQLite database: candidates, resumes, extracted information, extraction history, and jobs.

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
| `experience` | Text | approved or manually maintained work history |
| `skills` | Text | approved or manually maintained skill list |
| `education` | Text | approved or manually maintained education |
| `years_of_experience` | Integer | optional experience level |
| `preferred_roles` | Text | comma-separated preferred job titles |
| `preferred_locations` | Text | comma-separated preferred locations |
| `work_modes` | Text | comma-separated work mode preferences |
| `minimum_salary` | Integer | optional minimum desired salary |
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

### 5. `jobs`

Stores locally entered or imported job opportunities.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer (PK) | primary key |
| `source` | String | source label; defaults to `manual` |
| `source_url` | String | optional normalized source URL |
| `source_job_key` | String | unique normalized URL or stable manual-job hash |
| `title` | String | required job title |
| `company` | String | required company name |
| `location` | String | optional location |
| `work_mode` | String | Remote, Hybrid, or On-site |
| `description` | Text | optional pasted job description |
| `required_skills` | Text | comma-separated required skills |
| `minimum_experience` | Integer | optional minimum years |
| `salary_min` | Integer | optional minimum salary |
| `salary_max` | Integer | optional maximum salary |
| `posted_at` | DateTime | optional source posting date |
| `created_at` | DateTime | default UTC now |
| `updated_at` | DateTime | auto-updated |

## Relationships

- `Candidate` has many `Resume` rows
- `Candidate` has many `ExtractedInfo` rows
- each `Resume` can have one or more corresponding `ExtractedInfo` records
- `ExtractionHistory` links attempts back to a candidate and resume
- `Job` records are local opportunities and are not currently linked to a candidate

## Notes

- the database is intentionally simple and local-first
- there are no complex indexes or migration scripts yet
- the schema is designed for a prototype workflow rather than enterprise-scale data processing
- `Resume.is_processed` remains `False` until valid extraction data is persisted for review.
- `ExtractedInfo` rows are initially pending (`is_reviewed=False`, `is_approved=False`) and store the prompt and raw model response.
- ORM foreign keys do not declare cascade-delete behavior.
- startup performs a small SQLite migration that adds missing Phase 4 candidate profile columns; it does not yet provide versioned migration history.
- Phase 6 matching results are calculated on demand and are not currently persisted.
