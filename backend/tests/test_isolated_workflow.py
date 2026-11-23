"""Isolated integration tests for authenticated Action Center workflow."""
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
import numpy as np

_TEMP_PATH = Path(tempfile.mkdtemp(prefix="circularlens-workflow-"))
os.environ["CIRCULARLENS_DB_PATH"] = str(_TEMP_PATH / "workflow.db")
os.environ["CIRCULARLENS_INDEX_DIR"] = str(_TEMP_PATH / "faiss")
os.environ["CIRCULARLENS_AUTH_SECRET"] = "isolated-test-" + "secret-not-for-production"
os.environ["CIRCULARLENS_ENABLE_REMINDER_SCHEDULER"] = "false"

from fastapi.testclient import TestClient  # noqa: E402
from backend.app.database import SessionLocal  # noqa: E402
from backend.app.main import app  # noqa: E402
from backend.app.models.document import ActionItem, Document, ReminderDelivery  # noqa: E402
from backend.app.reminders import acquire_scheduler_lease, schedule_due_reminders  # noqa: E402
from backend.app.routes.guest import store as guest_store  # noqa: E402
from backend.app import services  # noqa: E402
from backend.app.services import EmbeddingError  # noqa: E402


class _FakeModels:
    def generate_content(self, **_kwargs):
        return type("Response", (), {"text": "Dear Sir/Madam,\n\nI request consideration under the circular."})()


class _FakeGemini:
    models = _FakeModels()


class _DeterministicEmbeddingService:
    """Offline test double that keeps the actual FAISS code path intact."""
    provider = "test"
    model = "test-embedding"
    dimension = 3

    def __init__(self, _provider=None):
        pass

    @property
    def metadata(self):
        return {"provider": self.provider, "model": self.model, "dimension": self.dimension,
                "normalization": "l2", "index_version": "semantic-v1"}

    @staticmethod
    def _vectors(texts):
        # Stable normalized vectors are sufficient to verify persistence/search
        # without a real Gemini network request.
        return np.asarray([[1.0, 0.0, 0.0] for _ in texts], dtype="float32")

    def document_vectors(self, texts):
        return self._vectors(texts)

    def query_vector(self, text):
        return self._vectors([text])


def _classification(text: str) -> dict:
    if "INFORMATIONAL" in text:
        return {"category": "informational", "summary": "Information only", "actions": []}
    return {
        "category": "application", "summary": "Scholarship application is open.",
        "purpose": "Scholarship", "eligibility": "Enrolled students",
        "deadlines": ["2030-01-01"], "fees": None, "required_documents": ["ID"],
        "actions": ["Submit application"],
    }


def _payment_classification(_text: str) -> dict:
    return {"category": "payment", "summary": "Exam fee payment.", "fees": "₹1,250", "actions": ["Pay examination fee"], "required_documents": []}


class IsolatedWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.reindex = patch("backend.app.routes.documents.rebuild_semantic_index", lambda _db: None)
        self.classify = patch("backend.app.routes.intelligence.classify_circular", _classification)
        self.gemini = patch("backend.app.routes.intelligence.gemini_client", lambda: _FakeGemini())
        self.reindex.start(); self.classify.start(); self.gemini.start()
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        self.gemini.stop(); self.classify.stop(); self.reindex.stop()

    def register(self, email: str, org: str) -> str:
        response = self.client.post("/accounts/register", json={"email": email, "organization": org, "password": "correct-horse-battery"})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["token"]

    @staticmethod
    def headers(token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    def test_authenticated_action_lifecycle_and_tenant_isolation(self):
        alice = self.register("alice@example.test", "Alice Workspace")
        bob = self.register("bob@example.test", "Bob Workspace")

        created = self.client.post("/documents/text", headers=self.headers(alice), json={
            "title": "Scholarship Notice", "text": "Scholarship applications close on 1 January 2030. Submit an application.",
            "category": "Scholarship", "tags": ["funding"],
        })
        self.assertEqual(created.status_code, 201, created.text)
        document_id = created.json()["id"]
        self.assertEqual(self.client.get(f"/documents/{document_id}", headers=self.headers(bob)).status_code, 404)
        calendar = self.client.get("/documents/export/deadlines.ics", headers=self.headers(alice))
        self.assertEqual(calendar.status_code, 200, calendar.text)
        self.assertTrue(calendar.text.startswith("BEGIN:VCALENDAR"))

        classified = self.client.post(f"/intelligence/classify/{document_id}", headers=self.headers(alice))
        self.assertEqual(classified.status_code, 200, classified.text)
        self.assertFalse(classified.json()["deadline_confirmed"])
        self.assertTrue(classified.json()["action_created"])

        with SessionLocal() as db:
            document = db.get(Document, document_id)
            document.deadline = datetime.utcnow()
            db.query(ActionItem).filter(ActionItem.document_id == document_id).update({ActionItem.deadline: document.deadline})
            db.commit()

        actions = self.client.get("/intelligence/actions", headers=self.headers(alice))
        self.assertEqual(actions.status_code, 200)
        self.assertEqual(len(actions.json()), 1)
        action_id = actions.json()[0]["id"]
        self.assertEqual(self.client.get("/intelligence/actions", headers=self.headers(bob)).json(), [])

        drafted = self.client.post(f"/intelligence/draft/{document_id}", headers=self.headers(alice))
        self.assertEqual(drafted.status_code, 200, drafted.text)
        self.assertIn("Dear", drafted.json()["draft"])

        reminders = self.client.post("/intelligence/notifications/generate", headers=self.headers(alice))
        self.assertEqual(reminders.status_code, 200)
        self.assertEqual(reminders.json()["created"], 1)
        self.assertEqual(self.client.post("/intelligence/notifications/generate", headers=self.headers(alice)).json()["created"], 0)

        completed = self.client.patch(f"/intelligence/actions/{action_id}", headers=self.headers(alice), json={"status": "completed"})
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(self.client.get("/intelligence/notifications", headers=self.headers(alice)).json(), [])
        completed_history = self.client.get("/intelligence/actions?status=completed", headers=self.headers(alice))
        self.assertEqual(len(completed_history.json()), 1)

        self.assertEqual(self.client.post("/accounts/logout", headers=self.headers(alice)).status_code, 204)
        self.assertEqual(self.client.get("/accounts/me", headers=self.headers(alice)).status_code, 401)

    def test_informational_circular_creates_no_action(self):
        token = self.register("info@example.test", "Info Workspace")
        created = self.client.post("/documents/text", headers=self.headers(token), json={
            "title": "Library hours", "text": "INFORMATIONAL: The library will open at 8am next week.",
        })
        self.assertEqual(created.status_code, 201, created.text)
        result = self.client.post(f"/intelligence/classify/{created.json()['id']}", headers=self.headers(token))
        self.assertEqual(result.status_code, 200, result.text)
        self.assertFalse(result.json()["action_created"])
        self.assertEqual(self.client.get("/intelligence/actions", headers=self.headers(token)).json(), [])

    def test_guest_workspace_is_temporary_and_cannot_reach_private_data(self):
        with patch("backend.app.routes.guest.classify_circular", _classification), patch("backend.app.routes.guest.gemini_answer", lambda _question, _sources: "Grounded guest answer [Guest circular, p.1]."):
            session = self.client.post("/guest/sessions")
            self.assertEqual(session.status_code, 201, session.text)
            guest_headers = {"X-Guest-Session": session.json()["guest_session"]}
            analyzed = self.client.post("/guest/text/analyze", headers=guest_headers, json={"title": "Guest notice", "text": "Scholarship applications close on 1 January 2030. Submit an application."})
            self.assertEqual(analyzed.status_code, 200, analyzed.text)
            self.assertEqual(analyzed.json()["analysis"]["category"], "application")
            uploaded = self.client.post("/guest/upload/analyze", headers=guest_headers, files={"file": ("guest.txt", b"Scholarship applications close on 1 January 2030. Submit an application.", "text/plain")})
            self.assertEqual(uploaded.status_code, 200, uploaded.text)
            chat = self.client.post("/guest/chat", headers=guest_headers, json={"question": "When is the deadline?"})
            self.assertEqual(chat.status_code, 200, chat.text)
            self.assertIn("Grounded guest answer", chat.json()["answer"])
            guest_store.get(guest_headers["X-Guest-Session"]).expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            expired = self.client.post("/guest/chat", headers=guest_headers, json={"question": "Is this still available?"})
            self.assertEqual(expired.status_code, 401)
        # Guest session headers are never accepted as authenticated access.
        self.assertEqual(self.client.get("/documents/list", headers=guest_headers).status_code, 401)
        self.assertEqual(self.client.get("/intelligence/actions", headers=guest_headers).status_code, 401)

    def test_duplicate_registration_has_readable_backend_error(self):
        self.register("duplicate@example.test", "Duplicate Workspace")
        response = self.client.post("/accounts/register", json={"email": "duplicate@example.test", "organization": "Other Workspace", "password": "correct-horse-battery"})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"], "An account with this email already exists.")

    def test_role_restriction_payment_and_scheduler_persistence(self):
        token = self.register("payment@example.test", "Payment Workspace")
        created = self.client.post("/documents/text", headers=self.headers(token), json={
            "title": "Exam payment", "text": "Pay the examination fee.",
        })
        document_id = created.json()["id"]
        with patch("backend.app.routes.intelligence.classify_circular", _payment_classification):
            classified = self.client.post(f"/intelligence/classify/{document_id}", headers=self.headers(token))
        self.assertEqual(classified.status_code, 200, classified.text)
        actions = self.client.get("/intelligence/actions", headers=self.headers(token)).json()
        self.assertEqual(actions[0]["action_type"], "payment")
        self.assertEqual(actions[0]["amount"], "₹1,250")
        # Members cannot make an AI-proposed deadline officially confirmed.
        self.assertEqual(self.client.patch(f"/documents/{document_id}/deadline", headers=self.headers(token), json={"deadline": "2030-01-01T00:00:00", "confirmed": True}).status_code, 403)
        action_id = actions[0]["id"]
        with SessionLocal() as db:
            action = db.get(ActionItem, action_id)
            action.deadline = datetime.utcnow()
            db.commit()
            self.assertTrue(acquire_scheduler_lease(db, "worker-one"))
            self.assertFalse(acquire_scheduler_lease(db, "worker-two"))
        with SessionLocal() as db:
            self.assertEqual(schedule_due_reminders(db), 1)
        with SessionLocal() as db:
            self.assertEqual(schedule_due_reminders(db), 0)
            self.assertEqual(db.query(ReminderDelivery).filter(ReminderDelivery.action_id == action_id).count(), 1)
        self.client.patch(f"/intelligence/actions/{action_id}", headers=self.headers(token), json={"status": "completed"})
        with SessionLocal() as db:
            self.assertEqual(schedule_due_reminders(db), 0)
            delivery = db.query(ReminderDelivery).filter(ReminderDelivery.action_id == action_id).one()
            self.assertIsNotNone(delivery.cancelled_at)
        # Academic privacy regression: each user starts with only their own profile state.
        impact = self.client.get("/academic/eligibility", headers=self.headers(token))
        self.assertEqual(impact.status_code, 200)
        self.assertEqual(impact.json()["outcome"], "NEEDS VERIFICATION")

    def test_dashboard_is_user_scoped_and_in_progress_actions_remain_remindable(self):
        alice = self.register("dashboard-alice@example.test", "Dashboard Alice")
        bob = self.register("dashboard-bob@example.test", "Dashboard Bob")
        created = self.client.post("/documents/text", headers=self.headers(alice), json={
            "title": "Scholarship dashboard notice", "text": "Submit a scholarship application.",
        })
        self.assertEqual(created.status_code, 201, created.text)
        document_id = created.json()["id"]
        self.assertEqual(self.client.post(f"/intelligence/classify/{document_id}", headers=self.headers(alice)).status_code, 200)
        action = self.client.get("/intelligence/actions", headers=self.headers(alice)).json()[0]
        with SessionLocal() as db:
            db.get(ActionItem, action["id"]).deadline = datetime.utcnow()
            db.commit()
        started = self.client.patch(f"/intelligence/actions/{action['id']}", headers=self.headers(alice), json={"status": "in_progress"})
        self.assertEqual(started.status_code, 200, started.text)
        self.assertEqual(started.json()["status"], "in_progress")
        self.assertEqual(self.client.post("/intelligence/notifications/generate", headers=self.headers(alice)).json()["created"], 1)
        dashboard = self.client.get("/analytics/dashboard", headers=self.headers(alice))
        self.assertEqual(dashboard.status_code, 200, dashboard.text)
        self.assertEqual(dashboard.json()["metrics"]["active_circulars"], 1)
        self.assertEqual(dashboard.json()["metrics"]["pending_applications"], 1)
        self.assertEqual(len(dashboard.json()["actions"]), 1)
        other_dashboard = self.client.get("/analytics/dashboard", headers=self.headers(bob))
        self.assertEqual(other_dashboard.status_code, 200)
        self.assertEqual(other_dashboard.json()["metrics"]["active_circulars"], 0)
        self.assertEqual(other_dashboard.json()["actions"], [])

    def test_preferences_and_private_profile_persist(self):
        token = self.register("preferences@example.test", "Preferences Workspace")
        updated_preferences = self.client.put("/intelligence/preferences", headers=self.headers(token), json={
            "departments": ["Computer Science"], "programs": ["MSc AI"], "semesters": ["2"],
            "categories": ["Scholarship"], "bookmarks": [], "timezone": "Asia/Kolkata",
        })
        self.assertEqual(updated_preferences.status_code, 200, updated_preferences.text)
        self.assertEqual(updated_preferences.json()["timezone"], "Asia/Kolkata")
        profile = self.client.put("/academic/profile", headers=self.headers(token), json={
            "program": "MSc AI", "department": "Computer Science", "semester": 2,
            "attendance_percentage": 82, "backlog_count": 0, "condonation_approved": None,
        })
        self.assertEqual(profile.status_code, 200, profile.text)
        self.assertEqual(self.client.get("/academic/profile", headers=self.headers(token)).json()["department"], "Computer Science")

    def test_text_and_pdf_ingestion_builds_and_searches_a_real_faiss_index(self):
        """Exercise text/PDF -> chunks -> vectors -> FAISS -> protected retrieval."""
        token = self.register("faiss@example.test", "FAISS Workspace")
        other = self.register("faiss-other@example.test", "FAISS Other Workspace")
        self.reindex.stop()
        try:
            with patch("backend.app.services.EmbeddingService", _DeterministicEmbeddingService):
                text_created = self.client.post("/documents/text", headers=self.headers(token), json={
                    "title": "Research scholarship circular",
                    "text": "The research scholarship application requires a proposal and closes on 1 January 2030.",
                })
                self.assertEqual(text_created.status_code, 201, text_created.text)
                text_id = text_created.json()["id"]
                with SessionLocal() as db:
                    document = db.get(Document, text_id)
                    self.assertIsNotNone(document)
                    self.assertTrue(document.chunks)
                    self.assertEqual(document.chunks[0].embedding_provider, "test")
                    results = services.semantic_search(db, "scholarship proposal", limit=3, document_ids=[text_id])
                    self.assertTrue(results)
                    self.assertEqual(results[0]["document_id"], text_id)

                import fitz
                pdf = fitz.open(); page = pdf.new_page(); page.insert_text((72, 72), "Exam form submission deadline is 2 February 2030.")
                pdf_created = self.client.post("/documents/upload", headers=self.headers(token), files={
                    "file": ("exam-notice.pdf", pdf.tobytes(), "application/pdf"),
                })
                pdf.close()
                self.assertEqual(pdf_created.status_code, 201, pdf_created.text)
                pdf_id = pdf_created.json()["id"]
                self.assertEqual(self.client.get(f"/documents/{pdf_id}/preview", headers=self.headers(token)).status_code, 200)
                self.assertEqual(self.client.get(f"/documents/{pdf_id}", headers=self.headers(other)).status_code, 404)
                # Re-open the database/index after the second ingestion to prove persistence.
                with SessionLocal() as db:
                    self.assertEqual(db.get(Document, pdf_id).page_count, 1)
                    self.assertGreaterEqual(len(services.semantic_search(db, "exam form deadline", limit=5)), 2)
        finally:
            self.reindex.start()

    def test_indexing_failure_returns_explicit_503_without_leaving_a_document(self):
        token = self.register("index-failure@example.test", "Index Failure Workspace")
        with patch("backend.app.routes.documents.rebuild_semantic_index", side_effect=EmbeddingError("FAISS native import failed: test diagnostic")):
            response = self.client.post("/documents/text", headers=self.headers(token), json={
                "title": "Unavailable index circular", "text": "This record must not persist when indexing is unavailable.",
            })
        self.assertEqual(response.status_code, 503, response.text)
        self.assertIn("semantic embeddings are unavailable", response.json()["detail"])
        self.assertEqual(self.client.get("/documents/list", headers=self.headers(token)).json(), [])


if __name__ == "__main__":
    unittest.main()
