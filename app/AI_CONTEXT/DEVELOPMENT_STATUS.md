# Development Status

## Assessment scope

Read-only inspection of the application source, dependency manifests, and test directory was completed on 2026-11-18. No application code or tests were changed in this assessment.

## Current state

CareerPilot is an early prototype. The UI and individual components exist, but the resume-processing workflow is not complete end to end.

### Implemented

- Streamlit entry point and three screens: upload, review, and dashboard.
- SQLAlchemy models for `Candidate`, `Resume`, `ExtractedInfo`, and `ExtractionHistory`.
- SQLite engine configured as `sqlite:///./careerpilot.db`; `init_db()` creates model tables.
- Candidate service operations for create, fetch, list, update, and related resume/extraction lookup.
- Resume service saves files under `data/resumes/`, extracts PDF/DOCX/TXT text when the required parser is installed, and stores the resume record and text in SQLite.
- LLM service builds an extraction prompt, attempts JSON parsing, and returns a structured result to the upload UI.
- Pydantic schema files exist under `app/models/`, but active services/UI do not use them.
- The project virtual environment is Python 3.14.4. This is the observed environment, not a declared compatibility guarantee.

### Incomplete or broken against the planned pipeline

- The upload page displays extraction output but does not create an `ExtractedInfo` row or persist the prompt/response.
- The review page depends on an `ExtractedInfo` row, so the upload path does not currently feed the review path.
- The review page updates a detached ORM object and then commits a different session; its edits are therefore not reliably persisted.
- Approval/review timestamps are not maintained, and approved data is not applied to `Candidate`.
- The LLM service substitutes sample candidate data when Ollama is missing/unavailable or output is malformed. This can make a failed extraction appear successful.
- `OLLAMA_BASE_URL` is assigned but is not passed to Ollama; only the model name is used.
- The UI allows `.doc`, but the parser uses `python-docx` for both `.doc` and `.docx`; legacy `.doc` is not supported by that parser.
- If PDF/DOCX dependencies are missing, parsing returns an empty string; the upload workflow does not stop before creating/processing the resume.
- No user/account model or user-level isolation exists. Candidate IDs only associate resumes and extracted information with a candidate.

### Tests and dependencies

- `tests/` contains no test files; no automated tests are currently available.
- `requirements.txt` does not declare Ollama, PyPDF2, or python-docx, all of which are imported optionally by the active LLM/parser code.
- `requirements_new.txt` includes `sqlite3` (part of Python’s standard library) and a different parser/dependency set. The two manifests do not define one verified installation path.
- The inspected `.venv` has Python 3.14.4, Streamlit, SQLAlchemy, and Pydantic, but not Ollama, PyPDF2, python-docx, or pytest.
- No implementation, test, or clean-install validation was performed as part of this read-only assessment.

## Project principles to preserve

- Keep data local and use Ollama rather than paid external model APIs.
- Keep business logic independent of Streamlit.
- Preserve original resume files on disk.
- Require human review/approval before applying extracted fields to an existing candidate profile.
- Do not overwrite existing candidate values from unapproved model output.
- Keep the implementation incremental and avoid unnecessary abstractions.

## Assessment conclusion

The project has useful scaffolding, but the first planned feature—resume upload through approved candidate-profile update—is not complete. Implement and test that pipeline before treating review/approval or profile persistence as available functionality.
