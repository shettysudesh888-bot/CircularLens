"""Evidence-bound academic rules, lineage, and deterministic eligibility evaluation."""
import json
import re
import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.document import CircularRelationship, Document, RuleClause, StudentProfile
from ..access import document_query_for_user, require_document
from .accounts import User, admin_user, current_user
from ..services import generate_with_retry
from google.genai import types

router = APIRouter(prefix="/academic", tags=["academic-intelligence"])

class ClauseReview(BaseModel):
    verified: bool
    rule_value: dict | None = None
    conditions: list[dict] | None = None

class RelationshipInput(BaseModel):
    target_document_id: int
    relationship_type: str = Field(pattern="^(AMENDS|SUPERSEDES|EXTENDS|CLARIFIES|CANCELS)$")
    scope_categories: list[str] = Field(default_factory=list)
    evidence: str = Field(min_length=3, max_length=3000)
    verified: bool = False

class RelationshipReview(BaseModel):
    verified: bool

class ProfileInput(BaseModel):
    display_name: str | None = Field(default=None, max_length=160)
    institution: str | None = Field(default=None, max_length=160)
    program: str | None = Field(default=None, max_length=120)
    department: str | None = Field(default=None, max_length=120)
    semester: int | None = Field(default=None, ge=1, le=20)
    attendance_percentage: int | None = Field(default=None, ge=0, le=100)
    backlog_count: int | None = Field(default=None, ge=0, le=50)
    condonation_approved: bool | None = None
    previous_marks_percentage: int | None = Field(default=None, ge=0, le=100)


class GeminiCondition(BaseModel):
    field: str
    operator: str
    value: str
    logic: str = "AND"

class GeminiClause(BaseModel):
    category: str
    rule_key: str
    rule_value: str
    conditions: list[GeminiCondition] = Field(default_factory=list)
    exception_conditions: list[GeminiCondition] = Field(default_factory=list)
    source_passage: str = Field(min_length=8, max_length=1600)
    effective_date_text: str | None = None

class GeminiRelationship(BaseModel):
    target_document_id: int
    relationship_type: str
    scope_categories: list[str] = Field(default_factory=list)
    source_passage: str = Field(min_length=8, max_length=1600)

class GeminiExtraction(BaseModel):
    clauses: list[GeminiClause] = Field(default_factory=list)
    relationships: list[GeminiRelationship] = Field(default_factory=list)

ALLOWED_FIELDS={"semester","attendance_percentage","backlog_count","condonation_approved","program","department"}
ALLOWED_OPERATORS={"in",">=","<=",">","<","==","!="}
ALLOWED_CATEGORIES={"eligibility","attendance","backlog","approval","deadline","fee","required_documents","exception","instruction"}
RELATIONSHIP_TYPES={"AMENDS","SUPERSEDES","EXTENDS","CLARIFIES","CANCELS"}

def clause_payload(item: RuleClause) -> dict:
    return {"id":item.id,"document_id":item.document_id,"category":item.category,"rule_value":item.rule_value,"conditions":item.conditions,"effective_date":item.effective_date,"source_excerpt":item.source_excerpt,"page_number":item.page_number,"verified":item.verified,"review_status":item.review_status,"extraction_model":item.extraction_model}

def source_sentence(text: str, match: re.Match) -> str:
    start=text.rfind('.',0,match.start())+1; end=text.find('.',match.end())
    return text[start: len(text) if end<0 else end+1].strip()[:1200]

def suggested_rules(document: Document) -> list[tuple[str,dict,list[dict],str]]:
    """Bounded extractors: only store a rule when the exact source span is present."""
    text=document.extracted_text
    results=[]
    semester=re.search(r"(?:semester[s]?|sem\.?)[^\.]{0,90}?((?:\d+\s*(?:,|and|or)?\s*)+)",text,re.I)
    if semester:
        sentence=source_sentence(text,semester)
        values=[int(v) for v in re.findall(r"\bsemester\s*(\d+)",sentence,re.I)] or [int(v) for v in re.findall(r"\d+",semester.group(1))]
        values=list(dict.fromkeys(values))
        if values: results.append(("eligibility",{"semester_in":values},[{"field":"semester","operator":"in","value":values}],source_sentence(text,semester)))
    attendance=re.search(r"(\d{2,3})\s*%[^\.]{0,60}?(?:attendance|attend)",text,re.I) or re.search(r"attendance[^\.]{0,60}?(\d{2,3})\s*%",text,re.I)
    if attendance:
        value=int(attendance.group(1)); results.append(("attendance",{"minimum_attendance":value},[{"field":"attendance_percentage","operator":">=","value":value}],source_sentence(text,attendance)))
    fee=re.search(r"(?:fee|payment)[^₹\d]{0,30}(?:₹|Rs\.?\s*)([\d,]+)",text,re.I)
    if fee:
        value=int(fee.group(1).replace(',','')); results.append(("fee",{"amount_inr":value},[],source_sentence(text,fee)))
    deadline=re.search(r"(?:last date|deadline|submit[^\.]{0,30}by)[^\.]{0,40}?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+[A-Za-z]+\s+\d{4})",text,re.I)
    if deadline: results.append(("deadline",{"date_text":deadline.group(1)},[],source_sentence(text,deadline)))
    documents=re.search(r"(?:required documents?|submit)[^\.]{0,180}",text,re.I)
    if documents: results.append(("required_documents",{"instruction":source_sentence(text,documents)},[],source_sentence(text,documents)))
    return results


def suggested_complex_rules(document: Document) -> list[tuple[str,dict,list[dict],str]]:
    """Conservative complex suggestions. They encode scope and always require review."""
    text=document.extracted_text; results=[]
    condonation=re.search(r"attendance\s+below\s+(\d{2,3})\s*%[^.]{0,140}?(?:approved\s+condonation|condonation\s+approval)",text,re.I)
    if condonation:
        threshold=int(condonation.group(1)); evidence=source_sentence(text,condonation)
        group=[{"field":"attendance_percentage","operator":"<","value":threshold,"logic":"AND"},{"field":"condonation_approved","operator":"==","value":True,"logic":"AND"}]
        value={"kind":"attendance_condonation","review_required":True,"condition_groups":[{"logic":"AND","conditions":group}]}
        results.append(("exception",value,group,evidence))
        results.append(("approval",{"approval_type":"condonation","review_required":True,"condition_groups":[{"logic":"AND","conditions":group}]},[],evidence))
    backlog=re.search(r"(?:more\s+than|over)\s+(\d+|one|two|three|four|five)\s+backlogs?[^.]{0,100}?(?:not\s+eligible|ineligible|cannot\s+register)",text,re.I)
    if backlog:
        words={"one":1,"two":2,"three":3,"four":4,"five":5}; raw=backlog.group(1).lower(); threshold=words[raw] if raw in words else int(raw); evidence=source_sentence(text,backlog)
        results.append(("backlog",{"effect":"disqualify_if","threshold":threshold,"review_required":True},[{"field":"backlog_count","operator":">","value":threshold,"logic":"AND"}],evidence))
    approval_letter=re.search(r"(?:approval|condonation)\s+letter[^.]{0,100}?(?:attach|submit)",text,re.I)
    if approval_letter:
        evidence=source_sentence(text,approval_letter)
        results.append(("approval",{"approval_type":"letter","review_required":True},[],evidence))
        results.append(("required_documents",{"items":["approval letter"],"review_required":True},[],evidence))
    return results


def _page_for_passage(document_id:int, passage:str, db:Session)->int|None:
    from ..models.document import Chunk
    normal=" ".join(passage.split()).lower()
    for chunk in db.query(Chunk).filter(Chunk.document_id==document_id).all():
        if normal in " ".join(chunk.text.split()).lower() or " ".join(chunk.text.split()).lower() in normal:
            return chunk.page_number
    return None


def _safe_conditions(items:list[GeminiCondition])->list[dict]:
    output=[]
    for item in items:
        if item.field in ALLOWED_FIELDS and item.operator in ALLOWED_OPERATORS and item.logic in {"AND","OR"}:
            value=item.value
            try: value=json.loads(value)
            except json.JSONDecodeError: pass
            if item.operator=="in" and not isinstance(value,list): continue
            if item.operator in {">=","<=",">","<"}:
                try: value=float(value) if "." in str(value) else int(value)
                except ValueError: continue
            if item.operator in {"==","!="} and str(value).lower() in {"true","false"}: value=str(value).lower()=="true"
            output.append({"field":item.field,"operator":item.operator,"value":value,"logic":item.logic})
    return output


def gemini_extract(document:Document, db:Session)->tuple[list[RuleClause],list[CircularRelationship]]:
    prompt=f"""Extract atomic university-policy rules from the circular below. Return JSON only matching the provided schema. Copy each source_passage exactly from the circular (no paraphrase). Use only these categories: {sorted(ALLOWED_CATEGORIES)}. Use conditions only for profile fields {sorted(ALLOWED_FIELDS)} and safe operators {sorted(ALLOWED_OPERATORS)}. Put every condition value in a JSON-encoded string (for example "[2,3]" or "75"). Express AND/OR using logic. Do not infer missing facts.

ABSTENTION RULES: Return no clause for vague language such as “special cases will be decided” or “contact the department”; the word eligibility alone is not an eligibility rule. Emit required_documents only when a specific item is explicitly requested to be submitted or attached. Emit backlog only for an explicit backlog threshold/restriction. Emit approval/exception only when the text explicitly describes approval or an exception. Do not duplicate the same source passage/category. Only include a relationship if source_passage explicitly supports it and target_document_id is one of the known circular IDs supplied.

CURRENT DOCUMENT ID: {document.id}\nKNOWN CIRCULAR IDS: {[d.id for d in db.query(Document).filter(Document.id != document.id).all()]}\n\nCIRCULAR:\n{document.extracted_text[:50000]}"""
    response, generation_model = generate_with_retry(
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=GeminiExtraction),
    )
    parsed=response.parsed
    data=parsed if isinstance(parsed,GeminiExtraction) else GeminiExtraction.model_validate_json(response.text or "{}")
    clauses=[]; relationships=[]; normalized_doc=" ".join(document.extracted_text.split()).lower()
    for candidate in data.clauses:
        passage=" ".join(candidate.source_passage.split())
        if candidate.category not in ALLOWED_CATEGORIES or passage.lower() not in normalized_doc: continue
        conditions=_safe_conditions(candidate.conditions); exceptions=_safe_conditions(candidate.exception_conditions)
        if len(conditions)!=len(candidate.conditions) or len(exceptions)!=len(candidate.exception_conditions): continue
        value={candidate.rule_key:candidate.rule_value,"exceptions":exceptions} if exceptions else {candidate.rule_key:candidate.rule_value}
        exists=db.query(RuleClause).filter(RuleClause.document_id==document.id,RuleClause.category==candidate.category,RuleClause.source_excerpt==candidate.source_passage).first()
        if not exists:
            item=RuleClause(document_id=document.id,category=candidate.category,rule_value=value,conditions=conditions,source_excerpt=candidate.source_passage,page_number=_page_for_passage(document.id,candidate.source_passage,db),verified=False,review_status="suggested",extraction_model=generation_model,extraction_version="gemini-structured-v1")
            db.add(item);clauses.append(item)
    for candidate in data.relationships:
        if candidate.relationship_type not in RELATIONSHIP_TYPES or candidate.target_document_id==document.id or not db.get(Document,candidate.target_document_id): continue
        if " ".join(candidate.source_passage.split()).lower() not in normalized_doc: continue
        exists=db.query(CircularRelationship).filter(CircularRelationship.source_document_id==document.id,CircularRelationship.target_document_id==candidate.target_document_id,CircularRelationship.relationship_type==candidate.relationship_type,CircularRelationship.evidence==candidate.source_passage).first()
        if not exists:
            item=CircularRelationship(source_document_id=document.id,target_document_id=candidate.target_document_id,relationship_type=candidate.relationship_type,scope={"categories":candidate.scope_categories},evidence=candidate.source_passage,verified=False)
            db.add(item);relationships.append(item)
    db.commit();return clauses,relationships


def _add_pattern_clauses(document: Document, db: Session, include_complex: bool = False) -> list[RuleClause]:
    created=[]
    candidates=suggested_rules(document)
    if include_complex: candidates += suggested_complex_rules(document)
    for category,value,conditions,evidence in candidates:
        exists=db.query(RuleClause).filter(RuleClause.document_id==document.id,RuleClause.category==category,RuleClause.source_excerpt==evidence).first()
        if not exists:
            item=RuleClause(document_id=document.id,category=category,rule_value=value,conditions=conditions,source_excerpt=evidence,page_number=_page_for_passage(document.id,evidence,db),verified=False,review_status="suggested",extraction_model="bounded-regex-with-source-verification")
            db.add(item);created.append(item)
    db.commit();return created


def _normalize_conditions(conditions: list[dict]) -> tuple:
    return tuple(sorted((str(x.get("field")),str(x.get("operator")),json.dumps(x.get("value"),sort_keys=True)) for x in conditions or []))


def _merge_hybrid(document: Document, db: Session) -> tuple[list[RuleClause], list[RuleClause]]:
    """Merge simple deterministic facts with Gemini complex interpretation; flag conflicts."""
    pattern=_add_pattern_clauses(document,db,include_complex=True)
    complex_language=bool(re.search(r"\b(exception|condonation|approval|backlog|unless|provided that|either| or | and )\b",document.extracted_text,re.I))
    gemini=[]
    if complex_language:
        gemini,_=gemini_extract(document,db)
    all_new=pattern+gemini
    rows=db.query(RuleClause).filter(RuleClause.document_id==document.id,RuleClause.review_status=="suggested").all()
    kept=[]; conflicts=[]
    seen={}
    for item in rows:
        key=(item.category,_normalize_conditions(item.conditions)," ".join(item.source_excerpt.lower().split()))
        if key not in seen:
            seen[key]=item; kept.append(item);continue
        prior=seen[key]
        if item.rule_value==prior.rule_value:
            db.delete(item)
        else:
            prior.review_status=item.review_status="conflict"; conflicts.extend([prior,item])
    db.commit()
    return kept, conflicts

@router.post("/documents/{document_id}/extract")
def extract_rules(document_id:int, user:User=Depends(admin_user), db:Session=Depends(get_db)):
    document=require_document(db,document_id,user)
    created=_add_pattern_clauses(document,db)
    return {"created":len(created),"clauses":[clause_payload(x) for x in created],"note":"Suggestions require administrator verification before authoritative use."}


@router.post("/documents/{document_id}/extract-gemini")
def extract_rules_gemini(document_id:int,user:User=Depends(admin_user),db:Session=Depends(get_db)):
    document=require_document(db,document_id,user)
    try:
        clauses,relationships=gemini_extract(document,db)
    except Exception as exc:
        raise HTTPException(502,f"Gemini structured extraction failed: {exc}") from exc
    return {"created_clauses":len(clauses),"created_relationship_candidates":len(relationships),"clauses":[clause_payload(x) for x in clauses],"relationships":[{"id":x.id,"type":x.relationship_type,"target_document_id":x.target_document_id,"verified":False} for x in relationships],"note":"All Gemini findings remain unverified until an administrator reviews them."}


@router.post("/documents/{document_id}/extract-hybrid")
def extract_rules_hybrid(document_id:int,user:User=Depends(admin_user),db:Session=Depends(get_db)):
    document=require_document(db,document_id,user)
    try:
        clauses,conflicts=_merge_hybrid(document,db)
    except Exception as exc:
        raise HTTPException(502,f"Hybrid extraction failed: {exc}") from exc
    return {"created_or_retained":len(clauses),"conflicts":[clause_payload(x) for x in conflicts],"clauses":[clause_payload(x) for x in clauses],"note":"Hybrid outputs are suggestions only; conflicts and all other clauses require administrator review."}

@router.get("/documents/{document_id}/clauses")
def list_clauses(document_id:int, user:User=Depends(current_user), db:Session=Depends(get_db)):
    require_document(db,document_id,user)
    return [clause_payload(item) for item in db.query(RuleClause).filter(RuleClause.document_id==document_id).order_by(RuleClause.id).all()]

@router.patch("/clauses/{clause_id}/review")
def review_clause(clause_id:int,payload:ClauseReview,user:User=Depends(admin_user),db:Session=Depends(get_db)):
    item=db.get(RuleClause,clause_id)
    if not item: raise HTTPException(404,"Clause not found.")
    require_document(db,item.document_id,user)
    if payload.rule_value is not None: item.rule_value=payload.rule_value
    if payload.conditions is not None: item.conditions=payload.conditions
    item.verified=payload.verified; item.review_status="verified" if payload.verified else "rejected";db.commit();return clause_payload(item)

@router.post("/documents/{document_id}/relationships",status_code=201)
def add_relationship(document_id:int,payload:RelationshipInput,user:User=Depends(admin_user),db:Session=Depends(get_db)):
    require_document(db,document_id,user); require_document(db,payload.target_document_id,user)
    item=CircularRelationship(source_document_id=document_id,target_document_id=payload.target_document_id,relationship_type=payload.relationship_type,scope={"categories":payload.scope_categories},evidence=payload.evidence,verified=payload.verified)
    db.add(item);db.commit();return {"id":item.id,"verified":item.verified}

@router.patch("/relationships/{relationship_id}/review")
def review_relationship(relationship_id:int,payload:RelationshipReview,user:User=Depends(admin_user),db:Session=Depends(get_db)):
    """Explicit administrator gate; generated lineage never self-activates."""
    item=db.get(CircularRelationship,relationship_id)
    if not item: raise HTTPException(404,"Relationship not found.")
    require_document(db,item.source_document_id,user); require_document(db,item.target_document_id,user)
    item.verified=payload.verified
    db.commit()
    return {"id":item.id,"verified":item.verified}

@router.get("/documents/{document_id}/lineage")
def lineage(document_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    require_document(db,document_id,user)
    rows=db.query(CircularRelationship).filter((CircularRelationship.source_document_id==document_id)|(CircularRelationship.target_document_id==document_id)).all()
    return [{"id":r.id,"source_document_id":r.source_document_id,"target_document_id":r.target_document_id,"type":r.relationship_type,"scope":r.scope,"evidence":r.evidence,"verified":r.verified} for r in rows]

@router.get("/profile")
def get_profile(user:User=Depends(current_user),db:Session=Depends(get_db)):
    profile=db.query(StudentProfile).filter(StudentProfile.user_id==user.id).first()
    return ProfileInput(**{k:getattr(profile,k) for k in ProfileInput.model_fields}).model_dump() if profile else ProfileInput().model_dump()

@router.put("/profile")
def put_profile(payload:ProfileInput,user:User=Depends(current_user),db:Session=Depends(get_db)):
    profile=db.query(StudentProfile).filter(StudentProfile.user_id==user.id).first() or StudentProfile(user_id=user.id)
    for key,value in payload.model_dump().items(): setattr(profile,key,value)
    db.add(profile);db.commit();return payload.model_dump()

def active_verified_clauses(db:Session,as_of:datetime|None=None,document_ids:list[int]|None=None)->list[RuleClause]:
    query=db.query(RuleClause).filter(RuleClause.verified==True)
    if document_ids is not None: query=query.filter(RuleClause.document_id.in_(document_ids))
    clauses=query.all()
    invalid=set()
    for rel in db.query(CircularRelationship).filter(CircularRelationship.verified==True).all():
        if rel.relationship_type in {"SUPERSEDES","CANCELS"}: invalid.update(c.id for c in clauses if c.document_id==rel.target_document_id)
        elif rel.relationship_type=="AMENDS":
            categories=set((rel.scope or {}).get("categories",[])); invalid.update(c.id for c in clauses if c.document_id==rel.target_document_id and c.category in categories)
    return [c for c in clauses if c.id not in invalid and (not as_of or not c.effective_date or c.effective_date<=as_of)]


def _condition_matches(actual, operator, value) -> bool:
    if actual is None: return False
    if operator=="in": return actual in value
    if operator==">=": return actual>=value
    if operator==">": return actual>value
    if operator=="<=": return actual<=value
    if operator=="<": return actual<value
    if operator=="==": return actual==value
    if operator=="!=": return actual!=value
    return False

@router.get("/eligibility")
def eligibility(document_id:int|None=None,user:User=Depends(current_user),db:Session=Depends(get_db)):
    profile=db.query(StudentProfile).filter(StudentProfile.user_id==user.id).first()
    if not profile: return {"outcome":"NEEDS VERIFICATION","reasons":["Create a student profile before eligibility is assessed."],"evidence":[]}
    allowed_ids=[document.id for document in document_query_for_user(db,user).all()]
    if document_id: require_document(db,document_id,user); allowed_ids=[document_id]
    clauses=active_verified_clauses(db,document_ids=allowed_ids)
    predicate_sets={}
    for clause in clauses:
        for condition in clause.conditions or []:
            if condition.get("operator")!="in": continue
            key=(clause.category,condition.get("field"),condition.get("operator")); values=set(condition.get("value") or [])
            if key in predicate_sets and values and predicate_sets[key].isdisjoint(values):
                return {"outcome":"NEEDS VERIFICATION","informational_notice":"This is evidence-grounded guidance, not official university authorization.","reasons":["Verified circulars contain conflicting applicable rule predicates; administrator review is required."],"evidence":[]}
            predicate_sets[key]=predicate_sets.get(key,values)
    reasons=[]; evidence=[]; unmet=False; missing=False
    attendance_overrides=set()
    for clause in clauses:
        if clause.category != "exception" or (clause.rule_value or {}).get("kind") != "attendance_condonation": continue
        conditions=clause.conditions or []
        if conditions and all(_condition_matches(getattr(profile,c.get("field"),None),c.get("operator"),c.get("value")) for c in conditions):
            for condition in conditions:
                if condition.get("field")=="attendance_percentage" and condition.get("operator")=="<":
                    attendance_overrides.add(condition.get("value")); evidence.append({"clause_id":clause.id,"document_id":clause.document_id,"excerpt":clause.source_excerpt,"condition":condition,"exception_applied":True})
    for clause in clauses:
        if clause.category in {"exception","approval","required_documents","fee","deadline","instruction"}:
            continue
        if clause.category=="backlog" and (clause.rule_value or {}).get("effect")=="disqualify_if":
            applicable=True
            for cond in clause.conditions or []:
                actual=getattr(profile,cond.get("field"),None); evidence.append({"clause_id":clause.id,"document_id":clause.document_id,"excerpt":clause.source_excerpt,"condition":cond})
                if actual is None: missing=True; reasons.append(f"Missing profile information: {cond.get('field')}."); applicable=False
                elif not _condition_matches(actual,cond.get("operator"),cond.get("value")): applicable=False
            if applicable: unmet=True; reasons.append("Profile meets a verified backlog disqualification condition.")
            continue
        for cond in clause.conditions or []:
            field,operator,value=cond.get("field"),cond.get("operator"),cond.get("value"); actual=getattr(profile,field,None)
            evidence.append({"clause_id":clause.id,"document_id":clause.document_id,"excerpt":clause.source_excerpt,"condition":cond})
            if actual is None: missing=True;reasons.append(f"Missing profile information: {field}.");continue
            if operator=="in" and actual not in value: unmet=True;reasons.append(f"{field} must be one of {value}; profile has {actual}.")
            if operator in {">=",">","<=","<"}:
                fails={">=":actual<value,">":actual<=value,"<=":actual>value,"<":actual>=value}[operator]
                if not fails: continue
                if field=="attendance_percentage" and operator==">=" and value in attendance_overrides:
                    reasons.append("A verified attendance-condonation exception applies to this threshold."); continue
                if field=="attendance_percentage" and profile.condonation_approved is None: missing=True;reasons.append("Attendance is below the stated threshold; condonation approval is unknown.")
                elif field=="attendance_percentage" and profile.condonation_approved: reasons.append("Attendance is below the threshold; approved condonation requires administrator confirmation.");missing=True
                else: unmet=True;reasons.append(f"{field} does not satisfy {operator} {value}; profile has {actual}.")
    outcome="NOT ELIGIBLE" if unmet else "NEEDS VERIFICATION" if missing or not clauses else "ELIGIBLE"
    return {"outcome":outcome,"informational_notice":"This is evidence-grounded guidance, not official university authorization.","reasons":reasons or ["All verified applicable conditions are satisfied."],"evidence":evidence}
