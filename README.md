# CircularLens AI — Intelligent University Circular Management Using Generative AI

CircularLens AI is an MSc project that helps university communities turn circulars into searchable, source-grounded information and student-owned actions. It combines FastAPI, React, Gemini, and FAISS while keeping document access, academic evidence, and reminder data scoped to the appropriate workspace.

## Problem statement

University circulars often arrive as long PDFs or notices containing deadlines, fees, eligibility rules, required documents, amendments, and exceptions. Important details can be missed, while generic task lists fail to preserve the original evidence. CircularLens AI keeps the source document alongside retrieval, review, and action workflows.

## Key features

- PDF, TXT, Markdown, and pasted-text circular ingestion.
- Source extraction, chunking, persistent Gemini embeddings, and FAISS semantic retrieval.
- Gemini-assisted classification, short summaries, source-grounded RAG answers, and editable application drafts.
- Private Action Center for applications, payments, deadlines, notifications, completion history, and calendar export.
- Circular Library, Evidence Viewer, Change Intelligence, Analytics, profile, and settings workspaces.
- Academic rule suggestions, source passages, amendment relationships, deterministic eligibility guidance, and explicit administrator review gates.
- Guest analysis isolation, JWT-style session handling, workspace document access control, and CLI-only administrator provisioning.

## Architecture

```text
React + TypeScript + Vite
        │ /api
FastAPI routes ── SQLite (documents, actions, reviews, profiles, reminders)
        │
Gemini embeddings / generation ── FAISS persistent semantic index
        │
Evidence, RAG, Action Center, academic rule review
```

## Technology stack

- Frontend: React, TypeScript, Vite, Tailwind-related styling, Lucide icons.
- Backend: Python, FastAPI, SQLAlchemy, SQLite, Pydantic, Uvicorn.
- AI: `google-genai`, Gemini embeddings, configurable Gemini generation primary/fallback models.
- Retrieval: FAISS, PyMuPDF, persistent chunk metadata.

## Gemini, FAISS, and RAG

Documents are extracted into chunks, embedded with Gemini, normalized, and stored in FAISS with chunk IDs. Query-time retrieval is constrained to documents the authenticated workspace may access. Gemini answers receive only retrieved excerpts and are instructed to cite source evidence. If generation is temporarily unavailable, the API returns an error rather than fabricating an answer.

Generation defaults to `gemini-3.1-flash-lite` with the verified fallback `gemini-3.5-flash-lite`. Fallback and retries are bounded by configuration. Embedding and generation credentials remain server-side.

## Personalized Action Center and academic intelligence

The Action Center uses database-backed circulars, actions, payments, deadlines, completion history, and in-app reminders. Information-only notices do not automatically become compulsory tasks. Completed/dismissed actions retain history and cancel pending reminders.

Academic clauses and circular relationships are suggestions until an authorized administrator reviews them. Unverified AI output does not drive operational eligibility. The deterministic eligibility engine returns `ELIGIBLE`, `NOT ELIGIBLE`, or `NEEDS VERIFICATION` with evidence-aware reasons.

## Permissions

- Members can access their workspace documents, actions, profiles, and notifications.
- Guest sessions are isolated from authenticated workspace data.
- Administrators can review clause suggestions, deadlines, and relationships only in their workspace.
- Administrator creation is CLI-only; public registration always creates a member.

## Clean checkout installation

Prerequisites: Python 3.12+, Node.js 20+, npm, and a Gemini API key with access to the configured models.

```powershell
git clone https://github.com/shettysudesh888-bot/CircularLens.git
cd CircularLens

py -3.12 -m venv backend\venv
.\backend\venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt

Copy-Item backend\.env.example backend\.env
# Set GEMINI_API_KEY and a high-entropy CIRCULARLENS_AUTH_SECRET in backend\.env

cd frontend
npm ci
Copy-Item .env.example .env
cd ..
```

The backend reads environment variables. Load `backend/.env` with your preferred local environment tool, or set its variables in the terminal before startup. Do not commit populated `.env` files.

## Run locally

Backend, from the repository root:

```powershell
$env:GEMINI_API_KEY = '<your-key>'
$env:CIRCULARLENS_AUTH_SECRET = '<long-random-secret>'
.\backend\venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Frontend, in a second terminal:

```powershell
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Open `http://127.0.0.1:5173`. During development, Vite proxies `/api` to port 8000.

## Testing

```powershell
# Backend
.\backend\venv\Scripts\python.exe -m py_compile backend\app\main.py backend\app\services.py
.\backend\venv\Scripts\python.exe -m unittest backend.tests.test_isolated_workflow -v

# Frontend
cd frontend
npm run lint
npm run build
```

The repository includes safe demo-generation/import tools under `backend/demo/`. They require locally supplied credentials or generate local-only credentials; runtime databases, vectors, uploads, and generated credentials are intentionally excluded from Git.

## Administrator provisioning

Use the documented CLI only; no HTTP admin-registration route exists.

```powershell
$env:CIRCULARLENS_ADMIN_BOOTSTRAP_SECRET = '<operator-controlled-secret>'
.\backend\venv\Scripts\python.exe -m backend.tools.provision_admin --bootstrap --email admin@example.test --workspace 'Existing Workspace'
Remove-Item Env:CIRCULARLENS_ADMIN_BOOTSTRAP_SECRET
```

The CLI refuses to elevate an existing member and records an audit event. Subsequent provisioning can use an existing administrator bearer token.

## Verified limitations

- Gemini generation capacity can return transient provider 503 responses; bounded retry/fallback is implemented but cannot guarantee provider availability.
- Administrator review is intentionally manual; generated clauses and relationships remain unverified by default.
- Live model quality metrics should be measured on a complete labelled evaluation run; this repository does not claim an unmeasured aggregate accuracy.
- SQLite and the local FAISS index are suitable for local/project demonstration. A multi-user deployment needs managed storage, secret management, external notification delivery, and operational monitoring.

## Future improvements

- Durable external email/push notification delivery.
- Managed database/vector infrastructure and background job orchestration.
- Larger independently annotated university-circular evaluation corpus.
- Role-managed institutional invitations and SSO.
- Production observability, rate-limit dashboards, and CI security scanning.

## Author

- **Author:** Sudesh S Shetty
- **Programme:** MSc Data Science
- **Institution:** Dayananda Sagar University
- **Academic Year:** 2026–2027
