"""Create an isolated, reproducible CircularLens AI demonstration workspace.

Run only with CIRCULARLENS_DEMO_MODE=1. Fixture classifications are human
authored expected labels, never Gemini output.
"""
from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path

if os.getenv("CIRCULARLENS_DEMO_MODE", "").lower() not in {"1", "true", "yes"}:
    raise SystemExit("Refusing to seed normal storage. Set CIRCULARLENS_DEMO_MODE=1.")

ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = (ROOT / "backend" / "data" / "demo").resolve()
os.environ.setdefault("CIRCULARLENS_DB_PATH", str(DEMO_DIR / "app.db"))
os.environ.setdefault("CIRCULARLENS_INDEX_DIR", str(DEMO_DIR / "semantic_index"))
os.environ.setdefault("CIRCULARLENS_UPLOAD_DIR", str(DEMO_DIR / "uploads"))
os.environ.setdefault("CIRCULARLENS_EMBEDDING_PROVIDER", "deterministic-demo")

from backend.app.database import Base, SessionLocal, engine, migrate_sqlite
from backend.app.models.document import (ActionItem, Document, InAppNotification,
                                         Organization, StudentProfile, User,
                                         UserPreference)
from backend.app.reminders import schedule_due_reminders
from backend.app.routes.accounts import digest
from backend.app.routes.documents import persist_document
from backend.app.routes.intelligence import _create_action_for_document

REFERENCE_DATE = datetime.now().date()
MAIN_EMAIL = "demo.data.science@demo-university.example"
SECOND_EMAIL = "demo.management@demo-university.example"
PASSWORD = os.getenv("CIRCULARLENS_DEMO_PASSWORD") or secrets.token_urlsafe(18)


def _specs() -> list[dict]:
    """A varied, entirely fictional 60-circular corpus with exact distribution."""
    rows = [
        ("DU-SCH-301", "Merit Research Scholarship — MSc Data Science", "Scholarship applications", "Research Office", "MSc Data Science", 3, 7, None, True, "Application form, transcript, supervisor note"), ("DU-SCH-302", "Women in Analytics Grant Applications", "Scholarship applications", "Equity Cell", "All postgraduate programmes", None, 14, None, True, "Statement of purpose, income declaration"), ("DU-SCH-303", "Industry Capstone Bursary Call", "Scholarship applications", "Career Development", "MSc Data Science", 3, 3, None, True, "Capstone abstract, employer consent"), ("DU-SCH-304", "Need-Based Learning Support Window", "Scholarship applications", "Student Welfare", "All programmes", None, -2, None, True, "Financial need form, bank details"), ("DU-SCH-305", "Open Source Contribution Fellowship", "Scholarship applications", "Innovation Hub", "MSc Data Science", None, 21, None, True, "Portfolio, repository links"), ("DU-SCH-306", "Rural Leadership Scholarship", "Scholarship applications", "Student Welfare", "MBA", 1, 10, None, True, "Leadership essay, residence proof"), ("DU-SCH-307", "Conference Travel Support Round Two", "Scholarship applications", "Research Office", "All postgraduate programmes", None, 1, None, True, "Accepted paper, cost estimate"), ("DU-SCH-308", "Alumni Academic Excellence Award", "Scholarship applications", "Alumni Relations", "All programmes", None, 30, None, True, "Transcript, faculty recommendation"),
        ("DU-EXM-401", "Semester Three Examination Registration", "Examination notices", "Controller of Examinations", "MSc Data Science", 3, 7, "₹2,400", True, "Registration form, ID card"), ("DU-EXM-402", "MBA Foundation Assessment Timetable", "Examination notices", "Controller of Examinations", "MBA", 1, 18, None, False, ""), ("DU-EXM-403", "Attendance Condonation for End-Semester Exams", "Examination notices", "Academic Affairs", "All programmes", None, 3, "₹750", True, "Condonation request, attendance record"), ("DU-EXM-404", "Supplementary Examination Application", "Examination notices", "Controller of Examinations", "All programmes", None, 14, "₹1,200 per paper", True, "Supplementary form, grade report"), ("DU-EXM-405", "Practical Examination Lab Allocation", "Examination notices", "Data Science Department", "MSc Data Science", 3, 9, None, False, ""), ("DU-EXM-406", "Revaluation Application Notice", "Examination notices", "Controller of Examinations", "All programmes", None, -1, "₹500 per course", True, "Marked-answer request"), ("DU-EXM-407", "Examination Hall Ticket Collection", "Examination notices", "Examinations Section", "All programmes", None, 4, None, True, "University ID"), ("DU-EXM-408", "Academic Integrity Declaration Before Examinations", "Examination notices", "Academic Affairs", "All programmes", None, 20, None, True, "Signed declaration"),
        ("DU-FEE-501", "Semester Three Tuition Instalment", "Payment and fee circulars", "Finance Office", "MSc Data Science", 3, 7, "₹48,000", True, "Payment reference"), ("DU-FEE-502", "Laboratory Computing Fee — Data Science", "Payment and fee circulars", "Finance Office", "MSc Data Science", 3, 3, "₹3,250", True, "Payment receipt"), ("DU-FEE-503", "MBA Orientation Resource Fee", "Payment and fee circulars", "Finance Office", "MBA", 1, 12, "₹1,800", True, "Payment receipt"), ("DU-FEE-504", "Late Fee Waiver Request Window", "Payment and fee circulars", "Finance Office", "All programmes", None, 1, None, True, "Reasoned request, payment proof"), ("DU-FEE-505", "Hostel Deposit Adjustment Advisory", "Payment and fee circulars", "Campus Services", "Resident students", None, 25, None, False, ""), ("DU-FEE-506", "Field Visit Contribution", "Payment and fee circulars", "Data Science Department", "MSc Data Science", 3, -3, "₹600", True, "Consent form"), ("DU-FEE-507", "Digital Library Renewal Charge", "Payment and fee circulars", "Library Services", "All programmes", None, 15, "₹350", True, "Student ID"), ("DU-FEE-508", "Conditional International Transcript Verification Fee", "Payment and fee circulars", "Registry", "International applicants", None, 28, None, True, "Transcript copy"),
        ("DU-SUB-601", "Capstone Proposal Submission", "Academic submissions", "Data Science Department", "MSc Data Science", 3, 7, None, True, "Proposal PDF, supervisor approval"), ("DU-SUB-602", "MBA Case Reflection Submission", "Academic submissions", "Management Department", "MBA", 1, 5, None, True, "Reflection document"), ("DU-SUB-603", "Research Ethics Declaration", "Academic submissions", "Research Office", "All postgraduate programmes", None, 3, None, True, "Ethics form"), ("DU-SUB-604", "Dataset Documentation Checkpoint", "Academic submissions", "Data Science Department", "MSc Data Science", 3, 14, None, True, "Data dictionary, README"), ("DU-SUB-605", "Peer Review Portfolio Upload", "Academic submissions", "Learning Office", "All programmes", None, 21, None, True, "Portfolio link"), ("DU-SUB-606", "Dissertation Intent Form", "Academic submissions", "Graduate School", "All postgraduate programmes", None, -1, None, True, "Intent form"), ("DU-SUB-607", "Semester Project Demonstration Slots", "Academic submissions", "Data Science Department", "MSc Data Science", 3, 10, None, True, "Demo repository"),
        ("DU-PLC-701", "Applied AI Internship Registration", "Placement/internship opportunities", "Career Development", "MSc Data Science", 3, 14, None, True, "Resume, project portfolio"), ("DU-PLC-702", "FinTech Analyst Internship Briefing", "Placement/internship opportunities", "Career Development", "MSc Data Science", 3, 9, None, True, "Resume"), ("DU-PLC-703", "MBA Consulting Sprint Opportunity", "Placement/internship opportunities", "Career Development", "MBA", 1, 16, None, True, "Resume, statement of interest"), ("DU-PLC-704", "Research Assistant Talent Pool", "Placement/internship opportunities", "Research Office", "All postgraduate programmes", None, 30, None, True, "CV, research interests"), ("DU-PLC-705", "Career Fair Employer Preference Form", "Placement/internship opportunities", "Career Development", "All programmes", None, 4, None, True, "Preference form"), ("DU-PLC-706", "Campus Ambassador Role Announcement", "Placement/internship opportunities", "Student Engagement", "All programmes", None, 22, None, False, ""),
        ("DU-EVT-801", "Responsible AI Workshop", "Events and workshops", "Innovation Hub", "MSc Data Science", 3, 7, None, False, ""), ("DU-EVT-802", "Design Thinking Weekend Lab", "Events and workshops", "Innovation Hub", "All programmes", None, 20, "₹300 optional materials", False, ""), ("DU-EVT-803", "Graduate Research Poster Day", "Events and workshops", "Research Office", "All postgraduate programmes", None, 11, None, True, "Poster abstract"), ("DU-EVT-804", "Data Visualisation Masterclass", "Events and workshops", "Data Science Department", "MSc Data Science", 3, 2, None, False, ""), ("DU-EVT-805", "Leadership Dialogue Series", "Events and workshops", "Management Department", "MBA", 1, 26, None, False, ""),
        ("DU-INF-901", "Library Extended Study Hours", "Informational notices", "Library Services", "All programmes", None, 0, None, False, ""), ("DU-INF-902", "Campus Network Maintenance Notice", "Informational notices", "IT Services", "All programmes", None, 0, None, False, ""), ("DU-INF-903", "Wellbeing Counselling Hours", "Informational notices", "Student Welfare", "All programmes", None, 0, None, False, ""), ("DU-INF-904", "Research Repository Service Update", "Informational notices", "Library Services", "All postgraduate programmes", None, 0, None, False, ""), ("DU-INF-905", "Learning Commons Seating Update", "Informational notices", "Campus Services", "All programmes", None, 0, None, False, ""),
        ("DU-AMD-1001", "Extension: Semester Three Tuition Instalment", "Policy amendments and deadline extensions", "Finance Office", "MSc Data Science", 3, 14, "₹48,000", True, "Payment reference"), ("DU-AMD-1002", "Amendment: Supplementary Examination Fee", "Policy amendments and deadline extensions", "Controller of Examinations", "All programmes", None, 11, "₹1,050 per paper", True, "Supplementary form"), ("DU-AMD-1003", "Clarification: Attendance Condonation Evidence", "Policy amendments and deadline extensions", "Academic Affairs", "All programmes", None, 5, "₹750", True, "Condonation request, medical evidence when applicable"), ("DU-AMD-1004", "Extension: Capstone Proposal Submission", "Policy amendments and deadline extensions", "Data Science Department", "MSc Data Science", 3, 12, None, True, "Proposal PDF, supervisor approval"), ("DU-AMD-1005", "Revised Internship Registration Eligibility", "Policy amendments and deadline extensions", "Career Development", "MSc Data Science", 3, 17, None, True, "Resume, project portfolio"), ("DU-AMD-1006", "Extension: Scholarship Travel Support", "Policy amendments and deadline extensions", "Research Office", "All postgraduate programmes", None, 8, None, True, "Accepted paper, cost estimate"), ("DU-AMD-1007", "Clarification: International Transcript Verification", "Policy amendments and deadline extensions", "Registry", "International applicants", None, 28, None, True, "Transcript copy"),
        ("DU-CAN-1101", "Cancellation: Campus Ambassador Registration", "Cancelled/superseded notices", "Student Engagement", "All programmes", None, 0, None, False, ""), ("DU-CAN-1102", "Superseded: Original Supplementary Examination Fee", "Cancelled/superseded notices", "Controller of Examinations", "All programmes", None, 0, None, False, ""), ("DU-CAN-1103", "Withdrawal: Field Visit Contribution", "Cancelled/superseded notices", "Data Science Department", "MSc Data Science", 3, 0, None, False, ""),
        ("DU-AMB-1201", "Provisional Research Grant Intimation", "Ambiguous/incomplete notices", "Research Office", "All postgraduate programmes", None, 6, None, True, "Supporting details to be announced"), ("DU-AMB-1202", "Tentative Examination Support Charge", "Ambiguous/incomplete notices", "Finance Office", "All programmes", None, 13, None, True, "Amount awaiting approval"), ("DU-AMB-1203", "Conditional Placement Registration Advisory", "Ambiguous/incomplete notices", "Career Development", "All programmes", None, 19, None, True, "Eligibility confirmation requested")]
    assert len(rows) == 60, len(rows)
    return [dict(number=a, title=b, label=c, department=d, program=e, semester=f, due=g, fee=h, actionable=i, documents=j) for a, b, c, d, e, f, g, h, i, j in rows]


def _category(label: str) -> str:
    return {"Scholarship applications":"scholarship", "Examination notices":"examination", "Payment and fee circulars":"payment", "Academic submissions":"submission", "Placement/internship opportunities":"application", "Events and workshops":"event", "Informational notices":"informational", "Policy amendments and deadline extensions":"policy", "Cancelled/superseded notices":"policy", "Ambiguous/incomplete notices":"application"}[label]


def _text(spec: dict, issue: datetime) -> str:
    deadline = (REFERENCE_DATE + timedelta(days=spec["due"])).strftime("%d %B %Y") if spec["due"] else None
    lines = [f"DEMO UNIVERSITY | {spec['number']}", f"Issued: {issue.strftime('%d %B %Y')}", f"From: {spec['department']}", f"Subject: {spec['title']}", "This is a fully fictional training circular created for the CircularLens AI demonstration environment.", f"Applicability: {spec['program']}" + (f", Semester {spec['semester']}." if spec['semester'] else ".")]
    if "Attendance Condonation" in spec["title"]: lines.append("Students below 75% attendance may apply only when condonation is approved; this does not waive examination registration.")
    elif "Supplementary" in spec["title"]: lines.append("Students with no more than two active backlogs may apply. Three or more backlogs require written examination-section approval.")
    elif "Internship" in spec["title"] or "Placement" in spec["title"]: lines.append("Applicants need 75% attendance and either no active backlogs or documented departmental clearance.")
    elif spec["actionable"]: lines.append("Eligible students should complete the stated requirement before the deadline.")
    else: lines.append("This notice is informational and does not require a student task.")
    if spec["fee"]: lines.append(f"Fee information: {spec['fee']}.")
    if spec["documents"]: lines.append(f"Required documents: {spec['documents']}.")
    if deadline: lines.append(f"Deadline: {deadline}.")
    if spec["label"] == "Policy amendments and deadline extensions": lines.append("This amendment supersedes only the referenced deadline or fee; unrelated original conditions remain in effect.")
    if spec["label"] == "Cancelled/superseded notices": lines.append("This notice cancels the referenced earlier registration. No new action should be created.")
    if spec["label"] == "Ambiguous/incomplete notices": lines.append("Final fee and eligibility conditions are not approved. Seek verification before acting.")
    return "\n".join(lines)


def _fixture_analysis(spec: dict) -> dict:
    deadline = (REFERENCE_DATE + timedelta(days=spec["due"])).isoformat() if spec["due"] else None
    return {"category": _category(spec["label"]), "summary": f"Fixture-derived summary: {spec['title']} for {spec['program']}. " + (f"Deadline {deadline}." if deadline else "Information only."), "purpose": spec["label"], "eligibility": f"{spec['program']}" + (f", semester {spec['semester']}" if spec['semester'] else ""), "deadlines": [deadline] if deadline else [], "fees": spec["fee"], "required_documents": [x.strip() for x in spec["documents"].split(",") if x.strip()], "actions": ["Review and complete the stated requirement"] if spec["actionable"] else [], "analysis_source": "human_authored_demo_fixture_not_gemini", "verified": False}


def _user(db, email: str, workspace: str, profile: dict) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        org = Organization(name=workspace); db.add(org); db.flush()
        user = User(email=email, password_hash=digest(PASSWORD), organization_id=org.id, role="member"); db.add(user); db.flush()
    item = db.query(StudentProfile).filter(StudentProfile.user_id == user.id).first() or StudentProfile(user_id=user.id)
    for key, value in profile.items(): setattr(item, key, value)
    db.add(item)
    preference = db.query(UserPreference).filter(UserPreference.user_id == user.id).first() or UserPreference(user_id=user.id)
    preference.departments, preference.programs, preference.semesters, preference.timezone = [profile["department"]], [profile["program"]], [str(profile["semester"])], "Asia/Kolkata"; db.add(preference)
    db.commit(); db.refresh(user); return user


def seed() -> dict:
    DEMO_DIR.mkdir(parents=True, exist_ok=True); Base.metadata.create_all(bind=engine); migrate_sqlite(); db = SessionLocal()
    try:
        main = _user(db, MAIN_EMAIL, "Demo University — Data Science", {"display_name":"Demo Data Science Student", "institution":"Demo University", "program":"MSc Data Science", "department":"Data Science", "semester":3, "attendance_percentage":86, "backlog_count":0, "previous_marks_percentage":82, "condonation_approved":None})
        _user(db, SECOND_EMAIL, "Demo University — Management", {"display_name":"Demo Management Student", "institution":"Demo University", "program":"MBA", "department":"Management", "semester":1, "attendance_percentage":72, "backlog_count":3, "previous_marks_percentage":None, "condonation_approved":None})
        created = 0; specs = _specs()
        for offset, spec in enumerate(specs):
            filename = f"{spec['number']}.txt"; document = db.query(Document).filter(Document.organization_id == main.organization_id, Document.filename == filename).first()
            if document is None:
                document = persist_document(db, filename, _text(spec, datetime.combine(REFERENCE_DATE - timedelta(days=45-offset), datetime.min.time())), user=main, path="", content_type="text/plain", pages=1, category=spec["label"], tags=[spec["department"], spec["program"], "demo"]); created += 1
            document.category, document.analysis, document.deadline, document.deadline_confirmed = spec["label"], _fixture_analysis(spec), (datetime.combine(REFERENCE_DATE + timedelta(days=spec["due"]), datetime.min.time()) if spec["due"] else None), False
            db.commit(); db.refresh(document)
            if spec["actionable"] and spec["label"] not in {"Cancelled/superseded notices", "Informational notices"}: _create_action_for_document(main, document, db); db.commit()
        actions = db.query(ActionItem).filter(ActionItem.user_id == main.id).order_by(ActionItem.id).all()
        for index, action in enumerate(actions):
            if index < 3: action.status = "completed"
            elif index < 5: action.status = "in_progress"
            elif index == 5: action.status = "dismissed"
        db.commit(); schedule_due_reminders(db, user_id=main.id)
        if not db.query(InAppNotification).filter(InAppNotification.user_id == main.id).first(): db.add(InAppNotification(user_id=main.id, kind="demo", title="Welcome to the demo workspace", body="All notices are fictional demo data. Fixture summaries are not Gemini predictions.")); db.commit()
        manifest = {"reference_date":REFERENCE_DATE.isoformat(), "total_circulars":len(specs), "records":[{k:v for k,v in spec.items() if k != "documents"} for spec in specs], "classification_source":"human-authored expected fixture labels; not Gemini predictions"}; (DEMO_DIR / "expected-results.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        credential_path = DEMO_DIR / ".demo-credentials.txt"; credential_path.write_text(f"CircularLens AI DEMO ONLY — do not use in production\n\nFrontend: http://127.0.0.1:5173\nWorkspace: Demo University — Data Science\nStudent: demo.data.science@demo-university.example\nPassword: {PASSWORD}\nRole: member\n\nIsolation account\nWorkspace: Demo University — Management\nStudent: demo.management@demo-university.example\nPassword: {PASSWORD}\nRole: member\n\nNo demo administrator is provisioned: no supported admin-provisioning workflow exists.\n", encoding="utf-8")
        try: os.chmod(credential_path, 0o600)
        except OSError: pass
        return {"created_documents":created, "documents":db.query(Document).filter(Document.organization_id == main.organization_id).count(), "actions":len(actions), "demo_dir":str(DEMO_DIR)}
    finally: db.close()


if __name__ == "__main__": print(json.dumps(seed(), indent=2))
