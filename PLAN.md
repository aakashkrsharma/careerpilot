# CareerPilot Plan

## Goal

A local-first web portal where a candidate uploads a resume once, and CareerPilot
discovers matching jobs, tailors application materials, prepares answers, and
hands off a ready-to-submit application packet — with the candidate performing
only the steps that sites legitimately require (login, CAPTCHA, final submit).

## Non-negotiable constraints

- No automated submission through protected walls (login, CAPTCHA, anti-bot).
- No scraping of prohibited portals (LinkedIn, Naukri, Indeed, Foundit) or
  guessing of Workday endpoints.
- Read-only discovery only, with explicit source registration, terms approval,
  rate limits, and India-first eligibility filtering.
- All candidate data, resumes, and answer banks stay local (Ollama, SQLite).
- Every AI-generated artifact requires explicit human approval before use.
- Original resumes and profile values are never overwritten silently.

## What is already completed

Phases 1-8 plus the multi-source discovery engine are implemented and tested
(64 unittest cases passing).

| Area | Status |
|---|---|
| Resume upload (PDF/DOCX/TXT) and text extraction | Done |
| Local Ollama extraction with Pydantic validation | Done |
| Inline review, correction, approval, profile update | Done |
| Candidate profile + job preferences (roles, locations, work modes, salary) | Done |
| Manual job entry + normalized storage + dedup | Done |
| Explainable deterministic matching (skills/exp/location/mode/role) | Done |
| Job-specific resume tailoring drafts + approval + text export | Done |
| Application history with 15-day exact-job / 0-day company cooldowns | Done |
| Draft batches (up to 20 jobs, progressive relaxation) | Done |
| Clarification queue + reusable approved answer bank | Done |
| Manual-only handoff + explicit `Applied` confirmation | Done |
| 13 read-only connectors (ATS APIs, public APIs, RSS/Atom, mapped XML) | Done |
| Source registry, terms gating, health, rate limits, backoff | Done |
| India-first discovery + INR/LPA normalization | Done |
| On-demand UI runner + one-shot CLI for OS scheduling | Done |

## What remains to reach the goal

The pipeline already removes most manual work up to "ready to submit". The
remaining gaps are about **preparation automation** and **intake ergonomics**,
not about bypassing site restrictions.

### Gap 1 — One-click application preparation (highest value)

Today batch review, tailoring, clarification, and handoff are separate pages.
A candidate still clicks through each job individually.

**Deliverables**
- "Prepare batch" action that, for each approved batch job:
  - generates a tailored resume draft (queued, not auto-approved),
  - resolves screening answers from the answer bank with a confidence score,
  - builds an application packet (tailored resume file + answer sheet + job link
    + handoff steps) in `data/application_packets/<application_id>/`.
- A single review screen listing per-job status: draft ready, answers resolved,
  unresolved questions, packet ready.
- Bulk approve checkboxes with per-item override; nothing is submitted.
- One "Prepare manual handoff" button per job that opens the packet folder and
  prints the step list.

**Manual touchpoint retained:** candidate reviews and approves each AI artifact.

### Gap 2 — Semi-automated form question intake

Questions are currently typed by hand. To reduce friction without reading
protected forms:

**Deliverables**
- Paste/CSV import of screening questions (question text, type, options,
  canonical key).
- Auto-resolution against the answer bank; unresolved items land in the
  clarification queue.
- A "fill sheet" export (question -> suggested answer) for copy/paste on the
  target site.
- Optional: accept a screenshot/HTML snippet locally for OCR/parsing, processed
  by Ollama; never fetch the live form.

**Manual touchpoint retained:** candidate pastes questions and performs final
entry/submission on the site.

### Gap 3 — Respectful public job-page intake

Manual job entry is tedious. Add optional intake from a public job URL:

**Deliverables**
- Fetch a single public URL only when the candidate pastes it and confirms.
- Parse `schema.org/JobPosting` JSON-LD plus basic meta tags.
- Honor `robots.txt` and a per-domain allowlist; no redirects to private hosts;
  HTTPS only; size/time caps.
- Dedup into the canonical `Job` store with source attribution.

**Manual touchpoint retained:** candidate chooses URLs; no crawling.

### Gap 4 — Delivery artifacts

**Deliverables**
- Export tailored resumes as PDF and DOCX (not only TXT) for direct upload.
- Optional cover-letter draft generation (separate approval).
- Application packet zip for offline use.

### Gap 5 — Status and follow-up

**Deliverables**
- Follow-up date per application with a dashboard reminder.
- Lightweight status transitions already exist; add "interview scheduled /
  rejected / offer" with notes.
- Export application history to CSV for the candidate's own records.

### Gap 6 — Hardening and verification

**Deliverables**
- Live-source smoke tests run manually by the candidate (documented checklist).
- End-to-end run with real Ollama on a synthetic resume (already done once;
  repeat after Gap 1-4).
- Backup/restore helper for `careerpilot.db` + `data/`.
- Startup script and `.env.example`.

### Gap 7 — Interview preparation (later)

Only after application flow is solid. Out of scope for the application goal.

## Recommended execution order

1. Gap 1 (one-click preparation) — biggest reduction in manual clicks.
2. Gap 2 (form intake) — removes the last typing-heavy step.
3. Gap 4 (PDF/DOCX export) — needed for real submissions.
4. Gap 3 (URL intake) — convenience, lower priority.
5. Gap 5 (follow-up tracking).
6. Gap 6 (hardening) alongside each phase.

## What stays manual by design (and why)

| Step | Why manual |
|---|---|
| Account login on job sites | Credentials must never be stored or replayed |
| CAPTCHA / anti-bot checks | Legal/ToS and reliability |
| Final "Submit" click | Candidate owns the submission and its accuracy |
| Verifying AI-tailored content | Prevents fabricated experience from being sent |
| Approving sensitive/high-stakes answers | Consent and accuracy |
| Source terms review before enabling a connector | Legal |

## Success metrics

- Time from "batch approved" to "packet ready" < 2 minutes of candidate
  attention (mostly review, not typing).
- Zero automated submissions; every `Applied` row has explicit confirmation.
- No prohibited source is scraped; all connectors remain read-only and
  terms-gated.
- All 64+ tests remain green after each phase.

## Immediate next actions

1. Add `ApplicationPacketService` that assembles per-application folders.
2. Add a "Prepare batch" button on `batch_review_page.py` calling tailoring +
   answer resolution + packet assembly, with per-job status.
3. Add paste/CSV question import to `clarification_queue_page.py`.
4. Add PDF/DOCX export to `tailoring_page.py` (python-docx already available;
   add a PDF library to `requirements.txt` after verifying).
5. Keep `NEXT_STEPS.md` and `DEVELOPMENT_STATUS.md` updated as phases land.
