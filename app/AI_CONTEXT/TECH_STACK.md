# Technology Stack

## Planned stack

The project handoff targets Python 3.14, Streamlit, SQLite, SQLAlchemy, Pydantic, and Ollama. The local virtual environment inspected during the assessment runs Python 3.14.4; source/package metadata does not declare a supported Python range.

## AI development environment from the handoff

- VS Code is the development IDE.
- Claude Code is preferred for more demanding development tasks.
- Local Qwen3 30B via Ollama, with a 16K context window, is intended for smaller coding, review, and documentation tasks.
- These are development-assistant preferences; the app's own `OLLAMA_MODEL` currently defaults to `llama3`.

## Current implementation

- **Streamlit** - UI framework for the upload, review, and dashboard screens
- **SQLAlchemy** - ORM layer for the database models
- **SQLite** - default local database engine
- **Pydantic** - validates the structured LLM extraction response against the extracted-info schema

## AI and document processing

- **Ollama** - local LLM used to extract structured features from resumes
- **HTTPX** - handles Ollama client HTTP requests and explicit connection error reporting
- **PyPDF2** - PDF parsing for resume text extraction
- **python-docx** - DOCX file parsing for resume text extraction
- **pandas** - simple tabular display and dashboard summaries

## Local storage

- **filesystem** - uploaded resumes are saved under `data/resumes/`
- **database file** - the app creates `careerpilot.db` in the project root

## Dependency assumptions

The project currently assumes a local, single-user setup rather than a hosted backend or cloud service. The stack is intentionally lightweight to simplify local experimentation.

## Notes

- the default LLM model is configured with `OLLAMA_MODEL`, which defaults to `llama3`
- `OLLAMA_BASE_URL` defaults to `http://localhost:11434`, but the current Ollama call does not use it to configure the client
- the project does not currently implement a separate frontend framework or remote API layer
- `requirements.txt` is the canonical pinned runtime dependency list; tests use Python's built-in `unittest`, so no separate test dependency is required
