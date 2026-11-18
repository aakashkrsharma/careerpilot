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

The dependency manifests are currently inconsistent: `requirements.txt` does not include the Ollama client, PyPDF2, or python-docx used by the active code paths, and `requirements_new.txt` includes `sqlite3`, which is part of Python's standard library. A clean installation is not yet verified; reconcile the manifests before relying on either as a reproducible setup.

```bash
pip install -r requirements.txt
```

## 4. Install and start Ollama

Install Ollama from https://ollama.com and ensure the service is running locally.

Then pull a model matching the app default:

```bash
ollama pull llama3
```

## 5. Configure environment variables

The app reads optional environment variables for LLM configuration:

```bash
export OLLAMA_BASE_URL=http://localhost:11434
export OLLAMA_MODEL=llama3
```

These values default to the local Ollama endpoint and `llama3` if not set.

## 6. Run the app

Launch the Streamlit UI:

```bash
streamlit run app/main.py
```

The app should open in the default Streamlit browser or be available at:

```text
http://localhost:8501
```

## 7. First-run behavior

On first launch, the app initializes the SQLite database and creates the required tables automatically. It will also create the `data/resumes/` directory if needed.

## Troubleshooting

### Ollama is not responding

- confirm Ollama is installed and running
- check the endpoint in `OLLAMA_BASE_URL`
- verify that the model exists with `ollama list`

### Resume parsing fails

- confirm that the file is a PDF, DOCX/DOC, or TXT file
- inspect the console output for formatting or parser exceptions
- some PDFs may produce noisy extraction without a full OCR pipeline

### Database is not created

- ensure the app starts from the project root
- confirm the `careerpilot.db` file can be created in the repo root
- check that `init_db()` runs from `app/main.py`

## Current installation assumption

The assessed local virtual environment uses Python 3.14.4, but the project does not declare a supported Python version. This app is designed for a local developer workflow and is not packaged for production deployment or multi-user hosting.
