# TurnB Autonomous PPT Agent

A full-stack application that turns case-study material into branded PowerPoint presentations. A Next.js chat interface talks to a FastAPI service, which structures and reviews content with a configured LLM, generates the deck, and stores artifacts in Azure Blob Storage.

## Features

- Guided chat workflow for collecting and refining case-study content
- DOCX, PDF, PPTX, XLSX, and text-oriented input processing
- Configurable Azure Anthropic, Azure OpenAI, or OpenAI generation
- Automated slide planning, text fitting, and template-aware rendering
- Azure Blob Storage for templates, uploads, and generated decks
- Single-container deployment with a same-origin gateway

## How to use

1. Start the app, then open `http://localhost:3000`.
2. In the chat, describe the case study or upload the source material.
3. Answer the agent's follow-up questions and review the proposed slide content.
4. Generate the presentation, then download the finished PowerPoint from the chat.

## Prerequisites

- Python 3.11
- Node.js 20 and npm
- An Azure Blob Storage container
- Credentials for one supported LLM provider
- Docker Desktop (optional)

## Local setup

1. Create and activate a Python environment, then install the backend dependencies:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

2. Create the backend configuration and replace the blank values with real credentials:

   ```powershell
   Copy-Item .env.example .env
   ```

3. Install the frontend dependencies:

   ```powershell
   Set-Location frontend
   npm ci
   Set-Location ..
   ```

4. Start both services:

   ```powershell
   .\run-dev.ps1
   ```

The UI runs at `http://localhost:3000` and the API at `http://localhost:8000`. API documentation is available at `http://localhost:8000/docs`.

For shells other than PowerShell, start the processes separately:

```bash
python -m uvicorn api_server:app --reload --host 0.0.0.0 --port 8000
cd frontend && npm run dev
```

The frontend defaults to `http://localhost:8000` during development. Set `NEXT_PUBLIC_API_URL` in `frontend/.env.local` only when the API is hosted elsewhere; see `frontend/.env.example`.

## Configuration

Never commit `.env` or `frontend/.env.local`. Both are ignored by Git.

| Setting | Purpose |
| --- | --- |
| `LLM_PROVIDER` | `azure_anthropic`, `azure_openai`, or `openai` |
| `AZURE_ANTHROPIC_*` | Azure Anthropic endpoint, key, model, API version, and token limit |
| `AZURE_OPENAI_*` | Azure OpenAI endpoint, key, deployment, and API version |
| `OPENAI_*` | OpenAI API key and model |
| `AZURE_STORAGE_CONNECTION_STRING` | Connection string for the artifact store |
| `AZURE_STORAGE_CONTAINER` | Blob container name; defaults to `turnb-ppt` |
| `AZURE_STORAGE_TEMPLATE_BLOB` | Template blob path inside the container |
| `NEXT_PUBLIC_API_URL` | Optional browser-visible API base URL |

Only the variables for the selected LLM provider are required. Azure Blob Storage configuration is always required by the current storage implementation.

## Tests and checks

```powershell
# Backend tests (no LLM requests are made)
.\.venv\Scripts\python.exe test_pipeline.py

# Frontend checks
Set-Location frontend
npm run lint
npm run build
```

The same backend and frontend checks run in GitHub Actions for pushes and pull requests.

## Docker

After configuring `.env`, build and run the combined application:

```powershell
docker compose up --build
```

Open `http://localhost:8501`. The image builds the Next.js frontend and serves it with the FastAPI service behind the bundled gateway.

## Repository layout

```text
.
|-- api_server.py        # FastAPI entry point
|-- src/                 # Agent, content, layout, storage, and PPT logic
|-- frontend/            # Next.js user interface
|-- prompts/             # LLM prompt templates
|-- templates/           # Versioned sample PowerPoint template
|-- deploy/              # Gateway and process-manager configuration
|-- docs/                # Technical and deployment documentation
|-- test_pipeline.py     # Non-LLM backend validation suite
`-- Dockerfile           # Combined production image
```

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request. Report security issues using the private process in [SECURITY.md](SECURITY.md), not a public issue.

This repository does not currently include an open-source license. Add an organization-approved license before publishing it as open source.
