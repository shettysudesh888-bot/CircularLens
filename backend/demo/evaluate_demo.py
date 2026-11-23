"""Repeatable verification for the isolated CircularLens demo dataset.

This reports only checks that actually run. It explicitly does not turn local
fixture labels into claims about live Gemini accuracy.
"""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("CIRCULARLENS_DEMO_MODE", "1")
if os.environ["CIRCULARLENS_DEMO_MODE"].lower() not in {"1", "true", "yes"}:
    raise SystemExit("Set CIRCULARLENS_DEMO_MODE=1 before evaluating demo data.")
ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = ROOT / "backend" / "data" / "demo"
os.environ.setdefault("CIRCULARLENS_DB_PATH", str(DEMO_DIR / "app.db"))
os.environ.setdefault("CIRCULARLENS_INDEX_DIR", str(DEMO_DIR / "semantic_index"))
os.environ.setdefault("CIRCULARLENS_UPLOAD_DIR", str(DEMO_DIR / "uploads"))
os.environ.setdefault("CIRCULARLENS_EMBEDDING_PROVIDER", "deterministic-demo")
os.environ.setdefault("CIRCULARLENS_ENABLE_REMINDER_SCHEDULER", "false")

from fastapi.testclient import TestClient
from backend.app.database import SessionLocal
from backend.app.main import app
from backend.app.models.document import ActionItem, Document, InAppNotification
from backend.app.services import INDEX_PATH, semantic_search

MAIN_EMAIL = "demo.data.science@demo-university.example"
SECOND_EMAIL = "demo.management@demo-university.example"
PASSWORD = os.getenv("CIRCULARLENS_DEMO_PASSWORD")


def run() -> str:
    if not PASSWORD:
        raise RuntimeError("Set CIRCULARLENS_DEMO_PASSWORD locally before evaluating demo credentials.")
    results: list[tuple[str, str, str]] = []
    with TestClient(app) as client:
        main_login = client.post("/accounts/login", json={"email": MAIN_EMAIL, "password": PASSWORD})
        second_login = client.post("/accounts/login", json={"email": SECOND_EMAIL, "password": PASSWORD})
        assert main_login.status_code == 200, main_login.text
        assert second_login.status_code == 200, second_login.text
        main_h = {"Authorization": f"Bearer {main_login.json()['token']}"}; second_h = {"Authorization": f"Bearer {second_login.json()['token']}"}
        dashboard = client.get("/analytics/dashboard", headers=main_h); assert dashboard.status_code == 200, dashboard.text
        dashboard_data = dashboard.json(); assert dashboard_data["metrics"]["active_circulars"] == 60, dashboard_data
        results.append(("Demo authentication and dashboard", "PASS", "Both demo members logged in; main dashboard reports 60 circulars."))
        documents = client.get("/documents/list", headers=main_h); assert documents.status_code == 200 and len(documents.json()) == 60
        results.append(("Circular Library data", "PASS", "Main demo workspace lists 60 fictional circulars from SQLite."))
        protected_id = documents.json()[0]["id"]
        assert client.get(f"/documents/{protected_id}", headers=second_h).status_code == 404
        assert client.get("/documents/list", headers=second_h).json() == []
        results.append(("Workspace isolation", "PASS", "Second demo workspace cannot enumerate or open main demo documents."))
        with SessionLocal() as db:
            found = semantic_search(db, "tuition instalment payment deadline", limit=3)
            assert found and INDEX_PATH.exists(), "FAISS returned no source"
            action_counts = {status: db.query(ActionItem).filter(ActionItem.status == status).count() for status in ("pending", "in_progress", "completed", "dismissed")}
            notification_count = db.query(InAppNotification).filter(InAppNotification.user_id == int(main_login.json()["user"]["id"])).count()
            document_count = db.query(Document).count()
        results.append(("FAISS persistence and retrieval", "PASS", f"Index exists and semantic query returned {len(found)} grounded chunk(s): {found[0]['source_name']} p.{found[0]['page_number']}."))
        results.append(("Action and notification fixtures", "PASS", f"Actions: {action_counts}; in-app notifications: {notification_count}."))
    results += [
        ("Live Gemini classification/summaries/drafts", "BLOCKED", "No live Gemini request was made by the demo seeder. Fixture labels are human-authored and explicitly not model predictions."),
        ("Gemini accuracy, precision, recall and F1", "NOT TESTED", "A live labeled evaluation requires Gemini network access and a separately recorded prediction run."),
        ("Browser click-through automation", "BLOCKED", "The available automation surface cannot reach the host loopback server; API integration checks ran in-process."),
    ]
    lines = ["# CircularLens AI full system demo report", "", "## Executive summary", "", "The isolated demo seed and API/FAISS verification completed. Live Gemini quality and browser automation were not claimed.", "", "## Environment", "", "- Demo-only storage: `backend/data/demo/`", "- Embeddings: `deterministic-demo` (offline fixture, not Gemini)", "- Dataset: 60 fully fictional Demo University circulars", "- Accounts: two member accounts; no administrator created because no supported admin-provisioning workflow exists.", "", "## Verification results", "", "| Component | Status | Actual result |", "|---|---|---|"]
    lines += [f"| {name} | **{status}** | {detail} |" for name, status, detail in results]
    lines += ["", "## Dataset distribution", "", "| Category | Count |", "|---|---:|", "| Scholarship applications | 8 |", "| Examination notices | 8 |", "| Payment and fee circulars | 8 |", "| Academic submissions | 7 |", "| Placement/internship opportunities | 6 |", "| Events and workshops | 5 |", "| Informational notices | 5 |", "| Policy amendments and deadline extensions | 7 |", "| Cancelled/superseded notices | 3 |", "| Ambiguous/incomplete notices | 3 |", "| **Total** | **60** |", "", "## Safety and limitations", "", "- Demo storage is rejected at startup if any configured database, index, or upload path lies outside `backend/data/demo`.", "- Fixture analysis is clearly tagged `human_authored_demo_fixture_not_gemini` and remains unverified.", "- The app's live Gemini endpoints were not run because network availability was not established in this execution environment.", "- The existing frontend is built separately; browser click-through must be manually checked using the commands in `backend/demo/README.md`.", "", "## Reproduce", "", "```powershell", "$env:CIRCULARLENS_DEMO_MODE='1'", "$env:CIRCULARLENS_EMBEDDING_PROVIDER='deterministic-demo'", ".\\backend\\venv\\Scripts\\python.exe -m backend.demo.seed_demo", ".\\backend\\venv\\Scripts\\python.exe -m backend.demo.evaluate_demo", "```", ""]
    report = "\n".join(lines)
    output = ROOT / "evaluation" / "CIRCULARLENS_FULL_SYSTEM_TEST_REPORT.md"; output.parent.mkdir(exist_ok=True); output.write_text(report, encoding="utf-8")
    return report


if __name__ == "__main__": print(run())
