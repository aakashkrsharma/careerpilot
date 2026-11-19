# Usage Guide

## Run locally

Start the app from the project root (the directory containing `app/` and `requirements.txt`):

```bash
python -m streamlit run app/main.py
```

The app has Dashboard, Candidate Profile, Jobs, Upload Resume, and Review Information pages.

## Jobs

1. Open Jobs from the sidebar.
2. Expand Add a Job and enter a title, company, source, optional URL, location, work mode, description, skills, experience, and salary range.
3. Save the job. Duplicate URLs and duplicate manual title/company/location combinations are rejected.
4. Use the filters to narrow local jobs by title/company, location, work mode, skills, and candidate experience.

CareerPilot does not scrape or submit applications. Source URLs are manually supplied and only open when you choose.

## Job matching

When a candidate is selected on the Jobs page, stored jobs are ranked by a compatibility score out of 100.

- Skills: up to 50 points.
- Experience: up to 20 points.
- Location: up to 15 points.
- Work mode: up to 10 points.
- Preferred role: up to 5 points.

Open “Why this score” for a job to see the component explanations and matched/missing skills.

## Resume tailoring

1. Open Resume Tailoring.
2. Select a candidate, target job, and optional original resume.
3. Click Generate Draft.
4. Review and edit the generated draft, suggestions, and limitations.
5. Check “Approve this tailored resume,” then save the review.
6. Download or save the approved draft as text.

Original resumes and candidate profile values are not changed by tailoring. The model is instructed not to invent experience or skills, but every generated draft still requires human approval.

## Candidate profile

1. Open Candidate Profile from the sidebar.
2. Select a candidate.
3. Edit contact details, summary, experience, skills, education, and years of experience.
4. Set preferred roles, locations, work modes, and an optional minimum salary.
5. Click Save Profile.

## Resume processing

1. Select an existing candidate or create one with a name and email.
2. Upload a PDF, DOCX, or TXT resume.
3. Process the resume. The original file is saved under `data/resumes/`; extracted text and resume metadata are stored in SQLite.
4. CareerPilot sends the text to local Ollama. A valid structured response is saved as pending `ExtractedInfo`, together with the prompt and raw model response.
5. After processing, open Review Information from the sidebar, select the candidate and resume, correct the fields, and save. Approval is on this page, not the upload results page.
6. To apply the reviewed data to the candidate profile, check “Approve this information” before saving.

Approved values fill empty candidate profile fields by default. To replace existing values, also check “Replace existing candidate profile values with approved values.” Approved experience, skills, and education also update the candidate profile.

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

- The model defaults to `llama3`; use `OLLAMA_MODEL` to select another installed model.
- `OLLAMA_BASE_URL` configures the Ollama client and defaults to `http://localhost:11434`.
- The app is local and single-user; candidate relationships do not provide account-level isolation.
- No REST API or export feature is implemented.
