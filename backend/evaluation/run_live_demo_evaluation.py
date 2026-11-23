"""Small balanced live-Gemini evaluation for existing demo documents.

Predictions are generated live and written separately; no document analysis is
updated. Reference labels below are manually fixed for this evaluation slice.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from backend.app.database import SessionLocal
from backend.app.models.document import Document, User
from backend.app.services import classify_circular, semantic_search

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "evaluation" / "live-demo-evaluation-results.json"
EMAIL = "demo.data.science@demo-university.example"

# Independently fixed from the fictional source text, before predictions run.
REFERENCE = {
    "DU-SCH-301.txt": {"category": "scholarship", "deadline": "30 November 2026", "fee": None, "documents": ["Application form", "transcript", "supervisor note"]},
    "DU-FEE-501.txt": {"category": "payment", "deadline": "30 November 2026", "fee": "₹48,000", "documents": ["Payment reference"]},
    "DU-AMD-1001.txt": {"category": "policy", "deadline": "07 December 2026", "fee": "₹48,000", "documents": ["Payment reference"]},
    "DU-EXM-401.txt": {"category": "examination", "deadline": "30 November 2026", "fee": "₹2,400", "documents": ["Registration form", "ID card"]},
    "DU-SUB-601.txt": {"category": "submission", "deadline": "30 November 2026", "fee": None, "documents": ["Proposal PDF", "supervisor approval"]},
    "DU-INF-901.txt": {"category": "informational", "deadline": None, "fee": None, "documents": []},
    "DU-CAN-1101.txt": {"category": "policy", "deadline": None, "fee": None, "documents": []},
}
QUERY_REFERENCES = {
    "What is the Semester Three tuition instalment fee and deadline?": "DU-FEE-501.txt",
    "Which circular extends the Semester Three tuition instalment?": "DU-AMD-1001.txt",
    "What documents are required for the capstone proposal?": "DU-SUB-601.txt",
}


def normal(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def date_match(prediction: dict, expected: str | None) -> bool:
    values = prediction.get("deadlines") or []
    if expected is None: return not values
    target = datetime.strptime(expected, "%d %B %Y").date()
    for value in values:
        try:
            if datetime.fromisoformat(str(value).replace("Z", "+00:00")).date() == target: return True
        except ValueError:
            if normal(value) == normal(expected): return True
    return False


def run() -> dict:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == EMAIL).one()
        documents = {item.filename: item for item in db.query(Document).filter(Document.organization_id == user.organization_id, Document.filename.in_(REFERENCE)).all()}
        if set(documents) != set(REFERENCE): raise RuntimeError("Evaluation documents are missing.")
        predictions = []
        for filename, reference in REFERENCE.items():
            try:
                value = classify_circular(documents[filename].extracted_text)
            except Exception as exc:
                predictions.append({"filename": filename, "reference": reference, "generation_error": str(exc), "classification_correct": None, "deadline_correct": None, "fee_correct": None, "required_documents_correct": None})
                continue
            predicted_documents = [normal(item) for item in value.get("required_documents") or []]
            expected_documents = [normal(item) for item in reference["documents"]]
            predictions.append({"filename": filename, "reference": reference, "prediction": value,
                                "classification_correct": normal(value.get("category")) == normal(reference["category"]),
                                "deadline_correct": date_match(value, reference["deadline"]),
                                "fee_correct": normal(value.get("fees")) == normal(reference["fee"]),
                                "required_documents_correct": set(predicted_documents) == set(expected_documents)})
        completed = [item for item in predictions if "prediction" in item]
        labels = sorted({item["reference"]["category"] for item in completed})
        per_category = {}
        for label in labels:
            tp = sum(normal(row["prediction"].get("category")) == label and row["reference"]["category"] == label for row in completed)
            fp = sum(normal(row["prediction"].get("category")) == label and row["reference"]["category"] != label for row in completed)
            fn = sum(normal(row["prediction"].get("category")) != label and row["reference"]["category"] == label for row in completed)
            precision = tp / (tp + fp) if tp + fp else 0.0; recall = tp / (tp + fn) if tp + fn else 0.0
            per_category[label] = {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0}
        retrieved = []
        ids = [item.id for item in documents.values()]
        for query, expected in QUERY_REFERENCES.items():
            rows = semantic_search(db, query, limit=3, document_ids=ids)
            retrieved.append({"query": query, "expected": expected, "returned": [row["source_name"] for row in rows], "top_3_relevant": expected in [row["source_name"] for row in rows]})
        result = {"sample_size": len(predictions), "completed_generation_samples": len(completed), "generation_failures": len(predictions) - len(completed), "predictions": predictions,
                  "classification_accuracy": (sum(row["classification_correct"] for row in completed) / len(completed)) if completed else None, "per_category": per_category,
                  "deadline_accuracy": (sum(row["deadline_correct"] for row in completed) / len(completed)) if completed else None, "fee_accuracy": (sum(row["fee_correct"] for row in completed) / len(completed)) if completed else None, "required_documents_exact_accuracy": (sum(row["required_documents_correct"] for row in completed) / len(completed)) if completed else None, "rag_retrieval": retrieved, "rag_top_3_relevance": sum(row["top_3_relevant"] for row in retrieved) / len(retrieved)}
        OUT.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        return result
    finally:
        db.close()


if __name__ == "__main__": print(json.dumps(run(), indent=2, default=str))
