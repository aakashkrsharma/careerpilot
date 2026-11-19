# Development Status

## Current status

Phases 1–8 are implemented in the local prototype. Phase 8 now includes permanent application history with configurable cooldowns, progressive batching, candidate clarification, extensible contracts, and manual-safe execution.

## Implemented

- Streamlit entry point and Dashboard, Upload Resume, and Review Information pages.
- SQLAlchemy models for candidates, resumes, extracted information, and extraction history.
- Local SQLite storage and candidate/resume management services.
- Resume upload and text extraction for PDF, DOCX, and TXT. Unsupported, unreadable, or empty resumes fail explicitly.
- Local Ollama extraction with Pydantic response validation. Connection, malformed-response, and empty-result failures are surfaced; sample candidate data is no longer returned.
- Ollama client host and model are configurable with `OLLAMA_BASE_URL` and `OLLAMA_MODEL`.
- Pending extraction persistence, including candidate/resume IDs, prompt, and raw response. A resume is marked processed only after extraction persistence succeeds.
- Transactional review save, review/approval timestamps, and approved candidate-profile updates.
- Empty candidate profile fields are filled after approval. Replacing populated values requires a separate explicit choice.
- Dashboard resume lookup uses `CandidateService`, and successful upload directs users to the review/approval page.
- Focused service integration tests with temporary SQLite and mocked Ollama, including configured Ollama host/model behavior.
- Candidate profiles now store experience, skills, education, years of experience, preferred roles, preferred locations, work modes, and minimum salary.
- A dedicated Candidate Profile page allows direct profile and job-preference edits.
- SQLite startup adds the Phase 4 candidate columns to databases created by earlier versions.
- Local job records support manual entry or pasted source metadata, normalized URLs, source-key deduplication, candidate/profile preference filters, and job detail display.
- Phase 8 stores permanent application history and scoped approved screening answers. The default exact-job cooldown is 15 days; the default same-company/different-role cooldown is zero days.
- A partial SQLite unique index blocks duplicate active applications without preventing a new record after the reapply cooldown.
- Batch selection snapshots up to 20 available jobs across strict, adjacent-role, location/work-mode, experience, and fallback-score stages, using existing deterministic match facts only.
- The Clarification Queue reuses eligible approved answers, pauses missing, ambiguous, and high-stakes questions, and saves candidate-approved answers transactionally to the selected answer-bank scope.
- `JobSourceConnector` and `ApplicationExecutor` protocols define future extension points. The current executor is manual-only and explicitly hands off authentication, CAPTCHA, and submission steps to the candidate.
- Batch Review, Clarification Queue, Application Tracker, and Dashboard application status summaries are available in Streamlit. Manual applications are marked `Applied` only after explicit candidate confirmation.

## Remaining limitations

- Legacy `.doc` files are unsupported; upload accepts PDF, DOCX, and TXT.
- The prototype is single-user. Candidate IDs scope candidate/resume/extraction operations; no account-level isolation exists.
- Upload and LLM processing run synchronously in Streamlit.
- Screening questions must currently be entered by the candidate; external application-form parsing and automatic answer filling are not implemented.
- No automated job-source collectors or automatic submission executors are enabled.

## Tests and dependencies

- Forty-six `unittest` cases cover resume processing, profile/preferences, SQLite and Alembic migrations, local jobs, explainable matching, resume tailoring, cooldowns, progressive batches, clarification reuse, approval boundaries, and Streamlit UI smoke checks.
- `requirements.txt` is the sole pinned runtime manifest. It includes Streamlit, SQLAlchemy, Pydantic, pandas, Ollama, HTTPX, PyPDF2, python-docx, and email-validator.
- Existing-environment checks and a clean Python 3.14.4 virtualenv install from `requirements.txt` pass; `pip check` and imports pass in both.
- The resume workflow was previously verified with local Ollama (`qwen3-coder:30b`) and a synthetic TXT resume in an isolated temporary database. Phase 8 UI routes are smoke-tested with Streamlit `AppTest`; live portal behavior is intentionally not exercised.
- Existing SQLAlchemy and PyPDF2 deprecation warnings remain.

## Project principles to preserve

- Keep data local and use Ollama rather than paid external model APIs.
- Keep business logic independent of Streamlit.
- Preserve original resume files on disk.
- Require human approval before applying extracted fields to a candidate profile.
- Do not overwrite populated profile fields without explicit replacement approval.
- Keep the implementation incremental and avoid unnecessary abstractions.

## Phase 1 conclusion

The upload → extraction → pending review → correction/approval → candidate profile flow is implemented and service-tested.

## Phase 2 conclusion

The Ollama client uses the configured local host and model. The current product scope is a single-user local application with candidate-ID scoping; account-level isolation is out of scope until multi-user support is requested. The UI continues to orchestrate existing services because a separate upload-pipeline abstraction is not currently justified.

## Phase 3 conclusion

The pinned dependencies install in a clean Python 3.14.4 virtual environment. The live synthetic resume flow was verified through Streamlit and local Ollama, including approval and Dashboard display. The user's existing database was not used or modified during this verification.

## Phase 4 conclusion

Candidate profiles now include structured experience, skills, education, years of experience, preferred roles, preferred locations, work modes, and minimum salary. A dedicated Candidate Profile page supports direct editing, and approved extraction data fills those profile fields. SQLite startup safely adds missing Phase 4 columns to existing databases. Profile update validation and migration behavior are covered by tests.

## Phase 5 conclusion

The app now provides local job storage and filtering. Users can manually add jobs or paste source metadata and descriptions. Source URLs are normalized, tracking parameters are removed, duplicate URLs or manual title/company/location combinations are rejected, and stored jobs can be filtered by title/company, location, work mode, skills, and experience. No external job source is scraped automatically.

## Phase 6 conclusion

The Jobs page ranks locally stored jobs for the selected candidate and explains the result. Compatibility uses deterministic components: skills up to 50 points, experience up to 20, location up to 15, work mode up to 10, and preferred role up to 5. The result lists matched and missing skills and exposes each component reason. Matching uses stored profile and job facts only.

## Phase 7 conclusion

The app now generates local, job-specific resume drafts for a candidate and target job. Drafts use candidate profile facts and optional original resume text, retain the prompt and raw Ollama response, and remain pending until human review and approval. User-edited drafts can be approved and exported as plain text under `data/tailored_resumes/`; original resume files and candidate profile values are not overwritten by tailoring.

## Phase 8 conclusion

The core application-management workflow is implemented: versioned Alembic schema changes, permanent application rows, a configurable exact-job cooldown (15 days by default), zero-day same-company/different-role cooldown, and a partial unique index for active duplicates. Draft batches select up to 20 jobs through progressive relaxation and require candidate approval. Screening questions can reuse approved scoped answers or pause for clarification; saved answers are approved explicitly. The tracker supports manual handoff and requires candidate confirmation before recording `Applied`.

The `JobSourceConnector` and `ApplicationExecutor` contracts are implemented, but no automated collectors or submission executors are enabled. Questions and job listings are currently supplied manually.
