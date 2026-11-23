"""Held-out, isolated three-way comparison: pattern vs Gemini vs hybrid.

This script creates its own SQLite DB (CIRCULARLENS_DB_PATH) and never uses
production documents. Labels are authored below before methods run.
"""
import json
import os
import time
from pathlib import Path

os.environ.setdefault("CIRCULARLENS_DB_PATH", str(Path(__file__).resolve().parent / "hybrid-evaluation.db"))
from app.database import Base, SessionLocal, engine, migrate_sqlite
from app.models.document import Chunk, Document, RuleClause
from app.routes.academic import _add_pattern_clauses, _merge_hybrid, gemini_extract

# DEV is retained for prompt/extractor iteration. Only HELD_OUT is scored below.
DEV = [
    {"name":"dev-simple","text":"Semester 1 students may register. Fee is Rs. 500. Last date is 01 December 2026.","labels":{"eligibility","fee","deadline"}},
    {"name":"dev-exception","text":"Attendance below 75% requires approved condonation.","labels":{"attendance","approval","exception"}},
]
HELD_OUT = [
    {"name":"simple","kind":"simple","text":"Semester 2 and Semester 4 students may register. Minimum attendance is 75%. Examination fee is Rs. 1250. Last date is 20 December 2026. Submit identity card.","labels":{"eligibility","attendance","fee","deadline","required_documents"},"conditions":{("eligibility","semester","in","[2, 4]"),("attendance","attendance_percentage",">=","75")}},
    {"name":"complex","kind":"complex","text":"Students with attendance below 75% may register only through approved condonation. Students with more than two backlogs are not eligible. Approval letter must be attached with the examination form.","labels":{"attendance","backlog","approval","exception","required_documents"},"conditions":set()},
    {"name":"or_conditions","kind":"complex","text":"Semester 2 or Semester 4 students may apply provided they have attendance of at least 75% and no more than one backlog.","labels":{"eligibility","attendance","backlog"},"conditions":set()},
    {"name":"ambiguous","kind":"complex","text":"Special cases may be considered by the competent authority. Contact the department for further clarification.","labels":set(),"conditions":set()},
]

def score(predicted, expected):
    tp=len(predicted & expected); fp=len(predicted-expected); fn=len(expected-predicted)
    return tp,fp,fn

def aggregate(rows):
    tp=sum(x[0] for x in rows);fp=sum(x[1] for x in rows);fn=sum(x[2] for x in rows)
    p=tp/(tp+fp) if tp+fp else 1.0; r=tp/(tp+fn) if tp+fn else 1.0
    return {"precision":p,"recall":r,"f1":2*p*r/(p+r) if p+r else 0.0,"true_positive":tp,"false_positive":fp,"false_negative":fn}

def make_doc(db, method, sample):
    doc=Document(filename=f"{method}-{sample['name']}.txt",path="",content_type="text/plain",extracted_text=sample["text"],page_count=1)
    db.add(doc);db.flush();db.add(Chunk(document_id=doc.id,text=doc.extracted_text,page_number=1));db.commit();return doc

def categories(rows): return {row.category for row in rows if row.review_status != "conflict"}

def condition_signatures(rows):
    return {(row.category, c.get("field"), c.get("operator"), json.dumps(c.get("value"), sort_keys=True)) for row in rows for c in (row.conditions or []) if row.review_status != "conflict"}

def run_method(db, method, sample):
    doc=make_doc(db,method,sample);started=time.perf_counter()
    if method=="pattern": rows=_add_pattern_clauses(doc,db)
    elif method=="gemini": rows,_=gemini_extract(doc,db)
    else: rows,_=_merge_hybrid(doc,db)
    return categories(rows), time.perf_counter()-started, rows

def main():
    Base.metadata.create_all(bind=engine);migrate_sqlite();db=SessionLocal()
    # Execute development samples but never include them in scores.
    dev_runs={}
    for sample in (DEV if os.getenv("EVAL_RUN_DEV") == "1" else []):
        dev_runs[sample["name"]]={}
        for method in ("pattern","gemini","hybrid"):
            found,elapsed,_=run_method(db,method,sample);dev_runs[sample["name"]][method]=sorted(found)
    outcomes={method:[] for method in ("pattern","gemini","hybrid")};condition_outcomes={method:[] for method in outcomes};latencies={method:[] for method in outcomes};details={}
    source_correct={"gemini":0,"hybrid":0};source_total={"gemini":0,"hybrid":0}
    held_out = HELD_OUT[:int(os.getenv("EVAL_HELD_OUT_LIMIT", str(len(HELD_OUT))))]
    for sample in held_out:
        details[sample["name"]]={}
        for method in outcomes:
            found,elapsed,rows=run_method(db,method,sample);outcomes[method].append(score(found,sample["labels"]));
            if sample.get("conditions"): condition_outcomes[method].append(score(condition_signatures(rows),sample["conditions"]))
            latencies[method].append(elapsed)
            details[sample["name"]][method]=sorted(found)
            if method in source_total:
                source_total[method]+=len(rows);source_correct[method]+=sum(row.source_excerpt in sample["text"] for row in rows)
    report={"held_out_circulars":len(held_out),"held_out_reference_categories":sum(len(x["labels"]) for x in held_out),"development_circulars_executed":len(dev_runs),"methods":{method:{**aggregate(outcomes[method]),"condition_interpretation":aggregate(condition_outcomes[method]),"mean_latency_seconds":sum(latencies[method])/len(latencies[method])} for method in outcomes},"source_evidence":{"gemini":{"correct":source_correct['gemini'],"total":source_total['gemini']},"hybrid":{"correct":source_correct['hybrid'],"total":source_total['hybrid']}},"held_out_predictions":details,"development_predictions":dev_runs}
    output=Path(__file__).resolve().parent/"hybrid-results.json";output.write_text(json.dumps(report,indent=2),encoding="utf-8");print(json.dumps(report,indent=2))

if __name__=="__main__":main()
