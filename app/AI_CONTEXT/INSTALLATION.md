# Installation Guide

## Prerequisites

Before starting CareerPilot, install the following:

- Python 3.14 (project handoff target; supported version range is not formally declared)
- pip
- Ollama (for local LLM extraction)
- optional: Git and a virtual environment tool

## 1. Clone the project

```bash
git clone <repository-url>
cd careerpilot
```

## 2. Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

The runtime packages are pinned in the single canonical manifest. Installation from this manifest was verified in both the existing environment and a clean Python 3.14.4 virtual environment.

## 4. Install and start Ollama

Install Ollama from https://ollama.com and ensure the service is running locally.

The app defaults to `qwen3-coder:30b`, which should appear in `ollama list`.
If it is not installed, pull it:

```bash
ollama pull qwen3-coder:30b
```

## 5. Configure environment variables

Set optional environment variables before starting the app to choose the Ollama endpoint and model:

```bash
export OLLAMA_BASE_URL=http://localhost:11434
export OLLAMA_MODEL=qwen3-coder:30b
```

`OLLAMA_MODEL` defaults to `qwen3-coder:30b`. Set it to another exact model
tag shown by `ollama list` if you prefer a different installed model.
`OLLAMA_BASE_URL` defaults to `http://localhost:11434`.

Job discovery uses outbound HTTPS only when you register, terms-approve, and
enable a source. Most public connectors do not require credentials. Optional
credentials belong in environment variables, never in the SQLite source
configuration:

```bash
export USAJOBS_API_KEY="your-api-key"
export USAJOBS_USER_AGENT="your-contact-user-agent"
export SMARTRECRUITERS_API_TOKEN="your-token"
```

USAJOBS is disabled by default; Remotive is opt-in and rate-limited. See
`USAGE.md` for source registration, privacy boundaries, and local scheduling.

## 6. Run the app

From the project root (the directory containing `app/` and `requirements.txt`), launch the Streamlit UI:

```bash
cd /home/ubuntu/projects/careerpilot
.venv/bin/python -m streamlit run app/main.py
```

If the virtual environment is activated, `python -m streamlit run app/main.py`
also works. The entry point adds the project root to Python's import path, but
starting from the project root ensures the database and local data folders are
created in the expected locations.

The app should open in the default Streamlit browser or be available at:

```text
http://localhost:8501
```

For a one-shot discovery run from the project root, use
`python -m app.discovery_cli --candidate-id <id>`. A local OS scheduler may
invoke it periodically; source-specific rate limits and due times are enforced
by the application.

## 7. First-run behavior

On first launch, the app initializes the SQLite database and creates the required tables automatically. It will also create the `data/resumes/` directory if needed.

## Troubleshooting

### Ollama is not responding

- confirm Ollama is installed and running
- check that Ollama is running at its default local endpoint (`http://localhost:11434`)
- verify that the model exists with `ollama list`

### Resume parsing fails

- confirm that the file is a PDF, DOCX, or TXT file
- inspect the console output for formatting or parser exceptions
- some PDFs may produce noisy extraction without a full OCR pipeline

### Database is not created

- ensure the app starts from the project root
- confirm the `careerpilot.db` file can be created in the repo root
- check that `init_db()` runs from `app/main.py`

### `ModuleNotFoundError: No module named 'app'`

- From the repository root, run `.venv/bin/python -m streamlit run app/main.py`.
- Confirm `.venv` exists and dependencies were installed with `.venv/bin/python -m pip install -r requirements.txt`.
- Avoid running `python app/main.py`; start it through Streamlit as shown above.

## Current installation assumption

The project handoff targets Python 3.14 and the assessed local virtual environment uses Python 3.14.4, but the project does not formally declare a supported Python range. This app is designed for a local developer workflow and is not packaged for production deployment or multi-user hosting.
