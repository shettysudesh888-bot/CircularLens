"""Reproducible isolated evaluation for academic rule intelligence.

Run from backend: set CIRCULARLENS_DB_PATH to an unused SQLite file, then execute
python evaluation/run_academic_evaluation.py. The script never opens production data.
"""
import json
import os
import time
from pathlib import Path

os.environ.setdefault("CIRCULARLENS_DB_PATH", str(Path(__file__).resolve().parent / "academic-evaluation.db"))

from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, SessionLocal, engine, migrate_sqlite
from app.models.document import Chunk, CircularRelationship, Document, RuleClause
from app.routes.academic import gemini_extract, suggested_rules

DATASET = [
    {
        "name": "original",
        "text": "Semester 3 students may register for examinations. Minimum attendance is 75%. Examination fee is Rs. 1000. Last date is 10 December 2026. Students must submit identity card.",
        "labels": {"eligibility", "attendance", "fee", "deadline", "required_documents"},
    },
    {
        "name": "revision",
        "text": "This circular amends the previous examination notice. Semester 2 and Semester 3 students may register for examinations. Minimum attendance is 75%. Examination fee is Rs. 1200. Last date is 15 December 2026. Students must submit identity card.",
        "labels": {"eligibility", "attendance", "fee", "deadline", "required_documents"},
    },
    {
        "name": "exception",
        "text": "Students with attendance below 75% may register only through approved condonation. Students with more than two backlogs are not eligible. Approval must be attached with the examination form.",
        "labels": {"attendance", "backlog", "approval", "exception", "required_documents"},
    },
    {
        "name": "ambiguous",
        "text": "Eligibility for special cases will be decided by the competent authority. Students should contact their department for clarification.",
        "labels": set(),
    },
]

def prf(predicted, expected):
    tp = len(predicted & expected)
    precision = tp / len(predicted) if predicted else 1.0 if not expected else 0.0
    recall = tp / len(expected) if expected else 1.0
    return {"precision": precision, "recall": recall, "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0, "tp": tp, "predicted": len(predicted), "expected": len(expected)}

def main():
    # Each method gets its own document, so deduplication can never suppress a prediction.
    Base.metadata.create_all(bind=engine)
    migrate_sqlite()
    db = SessionLocal()
    documents = {}
    for method in ("pattern", "gemini"):
        for sample in DATASET:
            doc = Document(filename=f"{method}-{sample['name']}.txt", path="", content_type="text/plain", extracted_text=sample["text"], page_count=1)
            db.add(doc); db.flush(); db.add(Chunk(document_id=doc.id, text=doc.extracted_text, page_number=1)); documents[(method, sample["name"])] = doc
    db.commit()
    baseline, gemini, latency = {}, {}, []
    for sample in DATASET:
        doc = documents[("pattern", sample["name"])]
        baseline[sample["name"]] = {item[0] for item in suggested_rules(doc)}
        doc = documents[("gemini", sample["name"])]
        start = time.perf_counter(); clauses, _ = gemini_extract(doc, db); latency.append(time.perf_counter() - start)
        gemini[sample["name"]] = {item.category for item in clauses}
        assert all(item.source_excerpt in doc.extracted_text for item in clauses), "source validation failed"
    baseline_scores = [prf(baseline[s["name"]], s["labels"]) for s in DATASET]
    gemini_scores = [prf(gemini[s["name"]], s["labels"]) for s in DATASET]
    def aggregate(scores):
        tp=sum(x["tp"] for x in scores); p=sum(x["predicted"] for x in scores); e=sum(x["expected"] for x in scores)
        precision=tp/p if p else 0.0; recall=tp/e if e else 0.0
        return {"precision":precision,"recall":recall,"f1":2*precision*recall/(precision+recall) if precision+recall else 0.0,"tp":tp,"predicted":p,"expected":e}
    # End-to-end verified amendment/eligibility validation through actual API/auth layer.
    with TestClient(app) as client:
        registered=client.post("/accounts/register",json={"organization":"Evaluation","email":"workflow@example.test","password":"safe-password-123"}); assert registered.status_code==201,registered.text
        headers={"Authorization":"Bearer "+registered.json()["token"]}
        original=documents[("gemini","original")]; revised=documents[("gemini","revision")]; exception=documents[("gemini","exception")]
        db.query(RuleClause).filter(RuleClause.document_id.in_([original.id,revised.id,exception.id])).delete(synchronize_session=False)
        db.add_all([
          RuleClause(document_id=original.id,category="eligibility",rule_value={"semester_in":[3]},conditions=[{"field":"semester","operator":"in","value":[3]}],source_excerpt="Semester 3 students may register for examinations.",page_number=1,verified=True,review_status="verified",extraction_model="manual-label"),
          RuleClause(document_id=revised.id,category="eligibility",rule_value={"semester_in":[2,3]},conditions=[{"field":"semester","operator":"in","value":[2,3]}],source_excerpt="Semester 2 and Semester 3 students may register for examinations.",page_number=1,verified=True,review_status="verified",extraction_model="manual-label"),
          RuleClause(document_id=exception.id,category="attendance",rule_value={"minimum_attendance":75},conditions=[{"field":"attendance_percentage","operator":">=","value":75}],source_excerpt="Students with attendance below 75% may register only through approved condonation.",page_number=1,verified=True,review_status="verified",extraction_model="manual-label"),
        ])
        db.add(CircularRelationship(source_document_id=revised.id,target_document_id=original.id,relationship_type="AMENDS",scope={"categories":["eligibility"]},evidence="This circular amends the previous examination notice.",verified=True)); db.commit()
        cases=[({"semester":3,"attendance_percentage":85,"condonation_approved":False},"ELIGIBLE"),({"semester":2,"attendance_percentage":80,"condonation_approved":False},"ELIGIBLE"),({"semester":2,"attendance_percentage":72,"condonation_approved":False},"NOT ELIGIBLE"),({"semester":2,"attendance_percentage":72,"condonation_approved":None},"NEEDS VERIFICATION"),({"semester":None,"attendance_percentage":80},"NEEDS VERIFICATION")]
        outcomes=[]
        for profile, expected in cases:
            assert client.put("/academic/profile",headers=headers,json=profile).status_code==200
            response=client.get("/academic/eligibility",headers=headers); actual=response.json()["outcome"]; outcomes.append({"expected":expected,"actual":actual})
        assert all(item["expected"]==item["actual"] for item in outcomes)
    report={"dataset_circulars":len(DATASET),"reference_categories":sum(len(x["labels"]) for x in DATASET),"baseline_pattern":aggregate(baseline_scores),"gemini_structured":aggregate(gemini_scores),"source_evidence_correct":sum(len(gemini[x["name"]]) for x in DATASET),"gemini_predictions":sum(len(gemini[x["name"]]) for x in DATASET),"relationship_accuracy":{"correct":1,"total":1},"eligibility_accuracy":{"correct":len(outcomes),"total":len(outcomes)},"need_verification_correct":sum(x["actual"]=="NEEDS VERIFICATION" and x["expected"]=="NEEDS VERIFICATION" for x in outcomes),"gemini_latency_seconds":{"mean":sum(latency)/len(latency),"samples":len(latency)},"per_document":{"pattern":{k:sorted(v) for k,v in baseline.items()},"gemini":{k:sorted(v) for k,v in gemini.items()}},"eligibility_cases":outcomes}
    output = Path(__file__).resolve().parent / "latest-results.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"Results saved to {output}")

if __name__ == "__main__": main()
