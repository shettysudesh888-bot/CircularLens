"""Isolated end-to-end academic intelligence validation matrix."""
import os
from pathlib import Path

os.environ.setdefault("CIRCULARLENS_DB_PATH", str(Path(__file__).resolve().parent / "integrated-validation.db"))
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, SessionLocal, engine, migrate_sqlite
from app.models.document import CircularRelationship, Document, RuleClause

def clause(document_id, category, value, conditions, text):
    return RuleClause(document_id=document_id,category=category,rule_value=value,conditions=conditions,source_excerpt=text,page_number=1,verified=True,review_status="verified",extraction_model="integration-label")

def main():
    Base.metadata.create_all(bind=engine);migrate_sqlite();db=SessionLocal()
    with TestClient(app) as client:
        registered=client.post('/accounts/register',json={'organization':'Integrated QA','email':'integrated@example.test','password':'safe-password-123'});assert registered.status_code==201,registered.text
        headers={'Authorization':'Bearer '+registered.json()['token']}
        text='Semester 2 or Semester 4 students may register. Minimum attendance is 75%. Students with attendance below 75% may register only through approved condonation. Students with more than two backlogs are not eligible.'
        doc=Document(filename='rules.txt',path='',content_type='text/plain',extracted_text=text,page_count=1);db.add(doc);db.flush()
        db.add_all([
          clause(doc.id,'eligibility',{'semester_in':[2,4]},[{'field':'semester','operator':'in','value':[2,4]}],'Semester 2 or Semester 4 students may register.'),
          clause(doc.id,'attendance',{'minimum_attendance':75},[{'field':'attendance_percentage','operator':'>=','value':75}],'Minimum attendance is 75%.'),
          clause(doc.id,'exception',{'kind':'attendance_condonation','condition_groups':[]},[{'field':'attendance_percentage','operator':'<','value':75,'logic':'AND'},{'field':'condonation_approved','operator':'==','value':True,'logic':'AND'}],'Students with attendance below 75% may register only through approved condonation.'),
          clause(doc.id,'backlog',{'effect':'disqualify_if','threshold':2},[{'field':'backlog_count','operator':'>','value':2}],'Students with more than two backlogs are not eligible.'),
        ]);db.commit()
        cases=[
          ({'semester':2,'attendance_percentage':80,'condonation_approved':False,'backlog_count':1},'ELIGIBLE','attendance above / backlog below'),
          ({'semester':4,'attendance_percentage':72,'condonation_approved':True,'backlog_count':2},'ELIGIBLE','approved condonation / backlog equal threshold'),
          ({'semester':4,'attendance_percentage':72,'condonation_approved':False,'backlog_count':1},'NOT ELIGIBLE','condonation denied'),
          ({'semester':4,'attendance_percentage':72,'condonation_approved':None,'backlog_count':1},'NEEDS VERIFICATION','condonation unknown'),
          ({'semester':2,'attendance_percentage':80,'condonation_approved':False,'backlog_count':3},'NOT ELIGIBLE','independent backlog disqualifier'),
          ({'semester':2,'attendance_percentage':80,'condonation_approved':False,'backlog_count':None},'NEEDS VERIFICATION','backlog missing'),
          ({'semester':3,'attendance_percentage':80,'condonation_approved':False,'backlog_count':1},'NOT ELIGIBLE','OR group not matched'),
        ]
        matrix=[]
        for profile,expected,name in cases:
            assert client.put('/academic/profile',headers=headers,json=profile).status_code==200
            actual=client.get('/academic/eligibility',headers=headers).json()['outcome']; matrix.append((name,expected,actual));assert actual==expected,matrix
        # Unverified rule cannot affect outcome.
        unverified=RuleClause(document_id=doc.id,category='backlog',rule_value={'effect':'disqualify_if'},conditions=[{'field':'backlog_count','operator':'>','value':0}],source_excerpt='Unreviewed',page_number=1,verified=False,review_status='suggested',extraction_model='test');db.add(unverified);db.commit()
        client.put('/academic/profile',headers=headers,json={'semester':2,'attendance_percentage':80,'condonation_approved':False,'backlog_count':1});assert client.get('/academic/eligibility',headers=headers).json()['outcome']=='ELIGIBLE'
        # Separate no-rules profile.
        db.query(RuleClause).filter(RuleClause.document_id==doc.id).delete(synchronize_session=False);db.commit();assert client.get('/academic/eligibility',headers=headers).json()['outcome']=='NEEDS VERIFICATION'
        # Conflicting verified predicates must abstain.
        conflict=Document(filename='conflict.txt',path='',content_type='text/plain',extracted_text='Conflicting eligibility notices.',page_count=1);db.add(conflict);db.flush();db.add_all([clause(conflict.id,'eligibility',{'semester_in':[2]},[{'field':'semester','operator':'in','value':[2]}],'Semester 2.'),clause(conflict.id,'eligibility',{'semester_in':[3]},[{'field':'semester','operator':'in','value':[3]}],'Semester 3.')]);db.commit();assert client.get('/academic/eligibility',headers=headers).json()['outcome']=='NEEDS VERIFICATION'
    print('INTEGRATED_ELIGIBILITY_MATRIX_OK',len(cases),'cases')

if __name__=='__main__':main()
