# Usage Guide

## Run locally

Start the app from the project root:

```bash
streamlit run app/main.py
```

The app currently provides Dashboard, Upload Resume, and Review Information pages.

## Current UI behavior

### Upload Resume

1. Select an existing candidate or create one with a name and email.
2. Select a PDF, DOCX, DOC, or TXT file.
3. Process the resume.

The app saves the original file under `data/resumes/`, extracts text, stores the resume record/text in SQLite, calls the LLM service, and displays the returned fields. The extraction fields are not currently saved as an `ExtractedInfo` row. The displayed `.doc` option is not reliably supported by the DOCX parser.

### Review Information

This page searches for an existing `ExtractedInfo` row and provides editable fields and an approval checkbox. The upload page does not create that row, so the normal upload flow does not populate this page. In addition, the current save path does not reliably persist edits because it mutates an object detached from the session used to commit.

Do not rely on review approval or profile updates as persisted functionality yet.

### Dashboard

The dashboard lists candidate rows, resume counts, and any `ExtractedInfo` rows already in the database. It displays candidate profile values but does not apply LLM extraction results to candidate profiles.

## Data locations

- SQLite database: `careerpilot.db` relative to the app's working directory
- Original resume files: `data/resumes/`
- Extracted resume text: `resumes.extracted_text` in SQLite

## LLM behavior

The default model name is `llama3`, configurable with `OLLAMA_MODEL`. The code reads `OLLAMA_BASE_URL` but does not currently use it in the Ollama call. If Ollama is unavailable or output parsing fails, the service may return fabricated sample fields; treat such output as development fallback, not valid resume extraction.

## Not currently available

- REST/API endpoints
- reliable persistence of extraction review edits
- applying approved extraction data to candidate profiles
- export, authentication, user-level data separation, or automated tests
