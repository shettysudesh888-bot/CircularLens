# Isolated demo environment

The demo is fenced into `backend/data/demo`; it never shares normal SQLite,
uploads, or FAISS files. It uses deterministic local demo vectors so the full
FAISS workflow can run without Gemini. These fixture summaries are not Gemini.

```powershell
$env:CIRCULARLENS_DEMO_MODE='1'
$env:CIRCULARLENS_EMBEDDING_PROVIDER='deterministic-demo'
.\backend\venv\Scripts\python.exe backend\demo\seed_demo.py
.\backend\venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8001
```

In a second terminal:

```powershell
cd frontend
$env:VITE_API_URL='http://127.0.0.1:8001'
npm run dev -- --host 127.0.0.1 --port 5173
```

Credentials live only at `backend/data/demo/.demo-credentials.txt`. Re-running
the seed is idempotent.
