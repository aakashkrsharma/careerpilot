# Database Schema

## Overview

CareerPilot defines core candidate, resume, job, tailoring, application, and answer-bank tables in a local SQLite database. Phase 8 adds permanent application and clarification history.

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

## Phase 8 tables

### 7. `applications`

Permanent candidate/job application history; rows are never purged as part of discovery or batching.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer (PK) | primary key |
| `candidate_id` | Integer (FK) | candidate owner |
| `job_id` | Integer (FK) | discovered or manually stored job |
| `tailored_resume_id` | Integer (FK) | optional approved tailored resume |
| `application_batch_id` | Integer (FK) | optional batch selection |
| `dedup_key` | String | permanent candidate/job/source identity |
| `source` | String | discovery source |
| `source_url` | String | normalized canonical URL |
| `source_external_id` | String | optional source-specific ID |
| `status` | String | discovered, tailored, needs clarification, ready, submitted, applied, or terminal status |
| `execution_mode` | String | automatic, manual, or not started |
| `match_score` | Integer | optional ranking snapshot |
| `match_stage` | String | strict or progressive-relaxation stage |
| `selected_rank` | Integer | rank inside a batch |
| `discovered_at` | DateTime | discovery or manual-entry timestamp |
| `tailored_at` | DateTime | tailoring completion timestamp |
| `clarification_at` | DateTime | clarification pause timestamp |
| `ready_at` | DateTime | approved preparation timestamp |
| `submitted_at` | DateTime | successful or attempted submission timestamp |
| `applied_at` | DateTime | candidate-confirmed permanent application timestamp |
| `follow_up_at` | DateTime | optional follow-up timestamp |
| `external_application_id` | String | optional source confirmation ID |
| `manual_instructions` | Text | CAPTCHA/manual guidance |
| `notes` | Text | candidate notes |
| `error_message` | Text | safe final execution error |
| `created_at` | DateTime | permanent creation time |
| `updated_at` | DateTime | status-update time |

Unique constraint: `(candidate_id, dedup_key)`.

### 8. `candidate_answer_bank`

Approved reusable answers for application screening questions.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer (PK) | primary key |
| `candidate_id` | Integer (FK) | candidate owner |
| `canonical_key` | String | normalized answer key |
| `aliases` | Text | optional comma/newline-separated question aliases |
| `answer_text` | Text | approved answer |
| `scope` | String | global, role, company, source, or job |
| `scope_value` | String | scope identifier; global uses a stable empty value |
| `sensitivity` | String | normal, sensitive, or high_stakes |
| `is_approved` | Boolean | explicit human approval |
| `source_application_id` | Integer (FK) | optional origin application |
| `approved_at` | DateTime | approval timestamp |
| `expires_at` | DateTime | optional expiry |
| `created_at` | DateTime | creation timestamp |
| `updated_at` | DateTime | update timestamp |

Unique constraint: `(candidate_id, canonical_key, scope, scope_value)`.

### 9. `application_batches`

A snapshot of progressive batch selection.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer (PK) | primary key |
| `candidate_id` | Integer (FK) | candidate owner |
| `requested_count` | Integer | requested maximum, capped at 20 |
| `selected_count` | Integer | actual selected count |
| `matching_threshold` | Integer | initial strict threshold |
| `relaxation_stages` | Text | ordered relaxation stages |
| `status` | String | draft, approved, processing, completed, or cancelled |
| `approved_at` | DateTime | candidate batch approval |
| `created_at` | DateTime | creation timestamp |
| `updated_at` | DateTime | update timestamp |

### 10. `clarification_requests`

Captures missing or high-stakes screening questions.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer (PK) | primary key |
| `application_id` | Integer (FK) | application requiring clarification |
| `canonical_key` | String | normalized question key |
| `question_text` | Text | original question |
| `proposed_answer` | Text | inferred draft, never silently approved |
| `candidate_answer` | Text | approved candidate response |
| `category` | String | salary, work authorization, notice period, and others |
| `sensitivity` | String | normal, sensitive, or high_stakes |
| `save_to_answer_bank` | Boolean | requested reusable-answer preference |
| `is_resolved` | Boolean | resolution state |
| `resolved_at` | DateTime | resolution timestamp |
| `created_at` | DateTime | creation timestamp |

### 11. `application_status_events`

Immutable audit history for application transitions.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer (PK) | primary key |
| `application_id` | Integer (FK) | related application |
| `from_status` | String | previous status |
| `to_status` | String | new status |
| `actor` | String | system, candidate, or connector |
| `reason` | Text | human-readable transition reason |
| `metadata_json` | Text | safe structured details |
| `created_at` | DateTime | event timestamp |

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

### 6. `tailored_resumes`

Stores generated, reviewed, and approved job-specific resume drafts.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer (PK) | primary key |
| `candidate_id` | Integer (FK) | references `candidates.id` |
| `job_id` | Integer (FK) | references `jobs.id` |
| `resume_id` | Integer (FK) | optional source resume |
| `draft_text` | Text | editable generated resume text |
| `suggestions` | Text | review suggestions |
| `limitations` | Text | missing or uncertain areas |
| `prompt_used` | Text | local Ollama prompt |
| `llm_response` | Text | raw model response |
| `is_reviewed` | Boolean | default `False` |
| `is_approved` | Boolean | default `False` |
| `exported_path` | String | optional local export path |
| `reviewed_at` | DateTime | optional |
| `approved_at` | DateTime | optional |
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
