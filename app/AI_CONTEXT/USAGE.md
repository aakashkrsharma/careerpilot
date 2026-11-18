# Usage Guide

## Run locally

Start the app from the project root:

```bash
streamlit run app/main.py
```

The app has Dashboard, Upload Resume, and Review Information pages.

## Resume processing

1. Select an existing candidate or create one with a name and email.
2. Upload a PDF, DOCX, or TXT resume.
3. Process the resume. The original file is saved under `data/resumes/`; extracted text and resume metadata are stored in SQLite.
4. CareerPilot sends the text to local Ollama. A valid structured response is saved as pending `ExtractedInfo`, together with the prompt and raw model response.
5. Open Review Information, select the candidate and resume, correct the fields, and save.
6. To apply the reviewed data to the candidate profile, check “Approve this information” before saving.

Approved values fill empty candidate profile fields by default. To replace existing values, also check “Replace existing candidate profile values with approved values.” Experience, skills, and education remain in the extraction record; the candidate profile currently has no corresponding columns for them.

## Errors and supported files

- Supported upload formats are PDF, DOCX, and TXT. Legacy `.doc` is not supported.
- Unsupported, corrupt, undecodable, or empty-text files stop processing with an error.
- Ollama connection errors, malformed JSON, invalid field values, or empty extraction results are surfaced. No sample candidate data is substituted.
- If LLM extraction fails after file parsing, the original and resume record remain stored; the resume stays unprocessed and no pending extraction is created.

## Data locations

- SQLite database: `careerpilot.db` relative to the app's working directory
- Original resume files: `data/resumes/`
- Extracted resume text and review data: SQLite (`resumes` and `extracted_info`)

## Current limitations

- The model defaults to `llama3`, configurable with `OLLAMA_MODEL`.
- The app reads `OLLAMA_BASE_URL` but does not yet configure the Ollama client with it.
- The app is local and single-user; candidate relationships do not provide account-level isolation.
- No REST API or export feature is implemented.
