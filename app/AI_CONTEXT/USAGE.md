# Usage Guide

## Run locally

Start the app from the project root (the directory containing `app/` and `requirements.txt`):

```bash
python -m streamlit run app/main.py
```

The app has Dashboard, Candidate Profile, Jobs, Discover Jobs, Resume Tailoring, Batch Review,
Clarification Queue, Application Tracker, Upload Resume, and Review Information
pages.

## Jobs

1. Open Jobs from the sidebar.
2. Expand Add a Job and enter a title, company, source, optional URL, location, work mode, description, skills, experience, and salary range.
3. Save the job. Duplicate URLs and duplicate manual title/company/location combinations are rejected.
4. Use the filters to narrow local jobs by title/company, location, work mode, skills, and candidate experience.

Jobs can be entered manually or discovered through configured, terms-approved
connectors; CareerPilot does not automatically submit applications. Source URLs
are manually supplied or retained from provider listings and only open when
you choose.

## Multi-source job discovery

1. Open Discover Jobs and expand Register a source.
2. Select an adapter: Greenhouse, Lever, Ashby, Arbeitnow, Jobicy, Remote OK,
   Himalayas, We Work Remotely RSS, authorized RSS/Atom, mapped XML,
   SmartRecruiters, Remotive, or USAJOBS.
3. Configure the board token/site, authorized HTTPS feed, or required
   environment-variable names. Never paste API keys or tokens into source
   configuration.
4. Review the source documentation/terms, confirm permission and attribution,
   then enable it. Sources without terms approval do not run. USAJOBS and
   Remotive are opt-in; USAJOBS starts disabled and Remotive has one source
   registration with at least six hours between requests.
5. Review and edit the role/search terms and locations before clicking Discover
   Jobs. India-first filtering is enabled by default for Indian hubs and jobs
   explicitly eligible in India/APAC or worldwide. Ambiguous `Remote` listings
   are excluded unless the source identifies eligible regions.
6. Review source health and run counts. A failing source does not stop other
   sources. The app preserves each provider listing while deduplicating the
   canonical job and reports active/application-cooldown blocks without
   deleting history.

The connector catalog includes multiple employer ATS boards; register separate
Greenhouse, Lever, and Ashby board tokens to monitor multiple companies.
Workday endpoints are not guessed. Use mapped XML only when an employer
provides an authorized feed and field mapping.

The search terms and locations you enter are sent to the selected source APIs.
Candidate name, email, resume content, and answer-bank data are not sent.
Source requests are HTTPS-only, rate-limited, time-bounded, size-capped, and do
not follow redirects. No LinkedIn, Naukri, Indeed, or Foundit scraping is
included.

### Scheduled local discovery

For a one-shot run of enabled sources that are due, invoke this from the project
root:

```bash
python -m app.discovery_cli --candidate-id 1
```

The command can be called by cron, systemd timers, or Task Scheduler. It uses
the candidate's preferred roles/locations unless `--query` or `--locations` is
provided. Use `--all-regions` only when you want to disable India/APAC
eligibility filtering. The CLI respects source cooldown intervals and does not
run a background scheduler inside Streamlit.

USAJOBS requires `USAJOBS_API_KEY` and `USAJOBS_USER_AGENT` environment
variables. SmartRecruiters requires `SMARTRECRUITERS_API_TOKEN`. Secret values
remain in the environment and are never written to SQLite.

Salary parsing retains original text and source currency/period. INR LPA values
are stored as annual INR amounts and displayed as LPA; CareerPilot does not
convert between currencies or assume an unspecified pay period.

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

## Batch review and job selection

1. Add job listings on the Jobs page and ensure the candidate profile has accurate skills and preferences.
2. Open Batch Review, select a candidate, choose a maximum of 20 jobs, and set the strict and fallback score thresholds.
3. Build the batch. Jobs are shown by selection stage and explainable match score; jobs with an active application or inside the exact-job cooldown are excluded.
4. Review the listed opportunities and approve the batch before advancing its applications. Cancel a draft batch to release its active job identities; its history is retained.

The selection stages relax criteria in order: strict match, adjacent role,
location/work-mode, experience, then fallback score. The matcher uses stored
candidate facts and never adds skills to the profile.

## Clarification queue and answer reuse

1. Open Clarification Queue and select an application from an approved batch.
2. Enter each screening question and a stable canonical key when possible.
3. The app reuses an approved answer when safe. Missing, ambiguous, and high-stakes questions are queued; high-stakes answers always require fresh confirmation.
4. Enter the candidate's answer, confirm it is accurate, and optionally save it to the answer bank.
5. Choose a scope for reuse. Company-, role-, source-, and job-specific answers can coexist with global answers.

Questions are currently entered manually. CareerPilot does not read or fill
external application forms.

## Application tracker and manual handoff

1. Open Application Tracker to review permanent application history and status.
2. Link an approved tailored resume if one is available, then mark the application ready after reviewing its preparation.
3. Choose Prepare Manual Handoff. CareerPilot provides steps but does not sign in, solve CAPTCHAs, or submit forms.
4. Complete the application directly on the source site. Return to the tracker, check the completion confirmation, and mark Applied only after successful submission.

Exact-job reapplication is blocked for 15 days by default. A different role at
the same company is immediately eligible by default. Historical records are
retained; a permitted reapplication creates a new application record.

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
- Jobs, applications, status events, clarification requests, and answer-bank entries: SQLite
- Connector configuration, source health, and provider listing provenance: SQLite

## Current limitations

- The model defaults to `llama3`; use `OLLAMA_MODEL` to select another installed model.
- `OLLAMA_BASE_URL` configures the Ollama client and defaults to `http://localhost:11434`.
- The app is local and single-user; candidate relationships do not provide account-level isolation.
- External connectors run only after registration, terms approval, enablement, and their rate-limit interval. Application-form question extraction, automatic answer filling, and automatic submission are not enabled.
- No REST API or export feature is implemented.
