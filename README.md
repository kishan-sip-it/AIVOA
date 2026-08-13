# AIVOA
# AIVOA — AI-Powered Customer Complaint Management System

An AI-assisted intake and triage system for pharmaceutical customer complaints (API & FDF quality assurance). A QA analyst pastes a raw complaint (email, call transcript) or uploads a document, and an AI agent extracts structured intake fields, runs an initial risk assessment, and lets the analyst correct any field conversationally before committing the record to a QMS ledger.
Live Link : https://aivoa1.netlify.app/
## Table of contents
- [Overview](#overview)
- [Tech stack](#tech-stack)
- [Features](#features)
- [Architecture](#architecture)
- [LangGraph workflow](#langgraph-workflow)
- [Setup](#setup)
- [API reference](#api-reference)
- [Key design decisions & adaptations](#key-design-decisions--adaptations)
- [Bonus AI features](#bonus-ai-features)
  

## Overview

In a pharmaceutical Quality Management System (QMS), every customer complaint about a product (discoloration, contamination, packaging defect, adverse event, etc.) must be logged with full traceability — product, batch, site, and a documented initial risk assessment — before it enters formal investigation (CAPA). This project automates the *intake* step: an AI agent reads the raw complaint, fills in the structured QMS fields, flags an initial severity/risk assessment, and the analyst reviews, corrects, and commits the record.

**Two-pane UI:**
- **Left (60%):** the structured "Log Customer Complaint" form (origin/customer, product/batch, facility/material, defect analysis, AI risk assessment).
- **Right (40%):** the "AIVOA Copilot" — paste text, drag-and-drop a document, or chat to correct fields.

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Redux Toolkit, Tailwind CSS, Vite |
| Backend | Python, FastAPI |
| AI agent framework | LangGraph (stateful multi-node workflow) |
| LLM | Groq API — `openai/gpt-oss-20b` (see [adaptation note](#key-design-decisions--adaptations) on the originally-specified `gemma2-9b-it`) |
| Database | PostgreSQL via SQLAlchemy |
| Document parsing | pdfplumber (PDF), python-docx (DOCX), stdlib `email` (EML), plain text |
| Font | Google Inter |

## Features

- **AI extraction** from free-typed text, or an uploaded **PDF / DOCX / TXT / EML** document.
- **AI risk assessment**: suggested severity (Critical/Major/Minor), suggested next action, and a written risk narrative.
- **Completeness checker**: status badge auto-flips **Pending Triage → Ready to Commit** once all mandatory fields are present.
- **Conversational corrections**: "change batch number to XYZ-123" updates the form live, and re-runs the risk assessment since a correction can change severity.
- **Field-level highlighting**: any field the AI just changed flashes green for ~2 seconds.
- **Drag-and-drop** document upload with a simulated extraction-progress indicator.
- **QMS ledger commit**: writes the final, reviewed record to PostgreSQL.

## Architecture

```
┌─────────────────────┐        HTTP/JSON         ┌──────────────────────────┐
│   React + Redux UI   │ ───────────────────────▶ │        FastAPI            │
│  (ComplaintForm,     │ ◀─────────────────────── │  routers/complaint.py     │
│   CopilotChat)       │                          │  /process /chat /commit   │
└─────────────────────┘                          └───────────┬──────────────┘
                                                               │
                                                               ▼
                                                     ┌─────────────────────┐
                                                     │   LangGraph agent    │
                                                     │   (graph.py)         │
                                                     │  parse → risk →      │
                                                     │  completeness        │
                                                     └───────────┬─────────┘
                                                                 │
                                                                 ▼
                                                     ┌─────────────────────┐
                                                     │   Groq LLM API       │
                                                     │  (structured output) │
                                                     └─────────────────────┘
                                                                 
                                                     ┌─────────────────────┐
                                                     │   PostgreSQL          │
                                                     │  (complaints table)   │
                                                     └─────────────────────┘
```

The backend is **stateless between requests** — no LangGraph checkpointer is attached. The full workflow state (`extracted_data`, `risk_assessment`, `chat_history`, `is_complete`, `status`) lives in Redux on the client and is sent back with every `/chat` call. This keeps the backend simple and horizontally scalable, at the cost of the client needing to echo state back — a deliberate trade-off for this scope.

## LangGraph workflow

Two compiled graphs share the same three nodes:

**Intake graph** (`POST /api/complaint/process` — new complaint):
```
START → parse_input_node → risk_assessment_node → completeness_checker → END
```

**Correction graph** (`POST /api/complaint/chat` — follow-up edit):
```
START → correction_node → risk_assessment_node → completeness_checker → END
```

| Node | Responsibility |
|---|---|
| `parse_input_node` | Extracts structured fields from raw text or document text, using a Groq LLM bound to a Pydantic schema (`ExtractedComplaintData`) via `with_structured_output`. Merges new fields into existing state rather than overwriting. |
| `risk_assessment_node` | Given the current extracted data, asks the LLM for `severity_suggested`, `suggested_next_action`, and `initial_risk_assessment`. Re-run after every correction, since a changed field (e.g. category) can change the severity call. |
| `correction_node` | Given a natural-language instruction ("change X to Y"), the LLM returns which field(s) to update and a confirmation message. Handles corrections, questions, and casual chit-chat distinctly. |
| `completeness_checker` | Checks all mandatory fields are non-empty and sets `status` to `pending` or `ready` accordingly — this drives the status badge and the Commit button's disabled state. |

## Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 14+
- A Groq API key ([console.groq.com](https://console.groq.com))

### Backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

python -m pip install -r requirements.txt
```

Create `.env` in the backend root:
```
GROQ_API_KEY=your_groq_api_key_here
DATABASE_URL=postgresql://<user>:<password>@localhost:5432/aivoa_db
```

Create the database once:
```bash
createdb aivoa_db
```

Run the API (tables are created automatically on startup):
```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
Swagger docs: http://127.0.0.1:8000/docs

### Frontend
```bash
cd frontend
npm install
```

Create `.env`:
```
VITE_API_BASE_URL=http://127.0.0.1:8000
```

```bash
npm run dev
```
App: http://localhost:5173

## API reference

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/complaint/process` | POST | Accepts `raw_text` and/or a document file. Runs the intake graph, returns extracted data + risk assessment + status. |
| `/api/complaint/chat` | POST | Accepts a follow-up `message` + the current graph state. Runs the correction graph. |
| `/api/complaint/commit` | POST | Persists the final, reviewed complaint to PostgreSQL. |
| `/api/health` | GET | Health check. |

## Key design decisions & adaptations

- **Model substitution:** the assignment specifies `gemma2-9b-it` on Groq. That model was deprecated and decommissioned by Groq (Aug–Oct 2025) and is no longer callable. After confirming this via Groq's live model list and deprecation notices, the LLM was switched to `openai/gpt-oss-20b`, which also supports structured/JSON output reliably. This is documented here rather than silently swapped, since it's exactly the kind of "assume you'll create a new token, model landscape shifts" judgment call the assignment brief invites.
- **`json_mode` over tool-calling:** LangChain's default `with_structured_output` (function/tool-calling) was unreliable on this model — it sometimes omitted required schema fields or refused to call the tool at all on sparse input. Switching to `method="json_mode"` (with the schema spelled out explicitly in the system prompt) was materially more reliable.
- **Defensive parsing:** structured-output results are normalized through a small `_to_dict()` helper, since `with_structured_output`'s beta implementation inconsistently returns either a Pydantic model or a raw dict depending on the call.
- **Client-held workflow state:** no LangGraph checkpointer/persistence layer — the frontend Redux store is the single source of truth for in-progress state, sent back on every correction call. Simpler infra, explicit trade-off for this project's scope.

## Bonus AI features

| Feature | Status |
|---|---|
| AI Risk Classification | ✅ Implemented — `risk_assessment_node` (severity, next action, risk narrative) |
| Complaint Completeness Checker | ✅ Implemented — `completeness_checker` node drives the status badge |
| Complaint Summary | ✅ Implemented |
| Root Cause Recommendation | ✅ Implemented |
| Duplicate Complaint Detection | ✅ Implemented |
| CAPA Recommendation | ✅ Implemented |

