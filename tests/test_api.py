from fastapi.testclient import TestClient
from app import banking, monitoring_client
from app.main import app
from monitoring import database, main as monitoring_module
from monitoring.main import app as monitoring_app
from pathlib import Path
import json

def test_load_supplied_bundle_and_integrity():
    b=banking.load_bundle()
    assert len(b.customers)==5000 and len(b.snapshots)==70575 and len(b.outcomes)==5000
    assert b.snapshots.duplicated(['customer_id','snapshot_date']).sum()==0
    assert b.snapshots.customer_id.nunique()==5000
    assert b.snapshots.label_observed_90d.sum()==62066

def test_rule_assessment_is_points_not_probability_and_ignores_labels():
    row={'transaction_count_change_3m_pct':-42.5,'unresolved_tickets':2,'nps_score':3,'missed_salary_inflow_30d':1,'churn_within_30d':1,'churn_within_90d':1,'synthetic_scenario':'stable','synthetic_churn_reason':'x'}
    result=banking.assess(row)
    assert result['assessment_type']=='transparent_rule_based_indicator_score'
    assert result['risk_category']=='High' and result['risk_score_unit']=='points (not probability)'
    assert all('churn' not in x['feature'] and 'scenario' not in x['feature'] for x in result['risk_factors'])
    assert not any('probability' in key for key in result)

def test_retrospective_horizon_eligibility():
    b=banking.load_bundle(); e30=banking.evaluate_horizon(b.snapshots,'30d'); e90=banking.evaluate_horizon(b.snapshots,'90d')
    assert e30['eligible_snapshots']==70575 and e90['eligible_snapshots']==62066
    assert e30['evaluation_type']=='synthetic_retrospective_snapshot_level'
    assert 'not fitted or calibrated' in e30['limitations'][2]

def test_dashboard_and_customer_endpoints():
    with TestClient(app) as client:
        health=client.get('/api/health').json()
        assert health['dataset']=='available' and 'Synthetic' in health['data_notice']
        dash=client.get('/api/dashboard').json()
        assert dash['total_customers']==5000 and dash['historical_churn_count']==912
        assert set(dash['risk_distribution'])=={'Low','Medium','High'}
        assert dash['retrospective_evaluation']['90d']['eligible_snapshots']==62066
        page=client.get('/api/customers?page=1&page_size=3&risk_category=High').json()
        assert len(page['customers'])==3 and page['total']>=3
        cid=page['customers'][0]['customer_id']; detail=client.get(f'/api/customers/{cid}').json()
        assert detail['risk_assessment']['assessment_type']=='transparent_rule_based_indicator_score'
        assert 'synthetic_scenario' not in detail['snapshot']
        assert detail['current_snapshot']==detail['snapshot']
        assert client.get('/api/customers/UNKNOWN').status_code==404

def test_analyze_response_and_monitoring_failure_isolated(monkeypatch):
    answer={'executive_summary':'Two risk indicators were observed in this synthetic snapshot.','customer_insights':['Transaction activity declined.'],'retention_recommendations':[{'action':'Resolve open case','rationale':'An unresolved issue was observed.','priority':'high','suggested_owner':'customer_support','success_indicator':'case_resolution'}],'limitations':['Synthetic data; not a probability.']}
    meta={'provider':'groq','model':'test-model','status':'available','latency_ms':12.5,'token_usage':{'prompt_tokens':1,'completion_tokens':2,'total_tokens':3},'request_id':'test-request-0001','error_category':None}
    monkeypatch.setattr(banking,'groq_analysis',lambda **kwargs:{'metadata':meta,'answer':answer})
    monkeypatch.setattr(monitoring_client,'emit',lambda event:{'delivery_status':'unavailable','error_category':'unavailable'})
    with TestClient(app) as client:
        result=client.post('/api/customers/CUST_00001/analyze?snapshot_date=2025-09-01')
        assert result.status_code==200; data=result.json()
        assert data['llm_metadata']['token_usage']['total_tokens']==3
        assert data['monitoring']['delivery_status']=='unavailable'
        assert data['monitoring']['llm_correctness_status']=='not_evaluated'
        assert data['historical_outcome']['label_observed_30d'] is True
        assert 'synthetic_churn_reason' not in str(data)

def test_groq_structured_validation_and_no_future_labels(monkeypatch):
    captured={}
    answer={'executive_summary':'Risk indicators are present in this synthetic snapshot.','customer_insights':'- Activity declined.\n- Digital engagement fell.','retention_recommendations':[{'action':'Follow up','rationale':'An open case exists.','priority':'high','suggested_owner':'support','success_indicator':'resolved_cases'},{'action':'Review access','rationale':'Failed logins were observed.','priority':'medium','suggested_owner':'digital','success_indicator':'login_success'},{'action':'Check activity','rationale':'Engagement declined.','priority':'low','suggested_owner':'service','success_indicator':'A measurable follow up success indicator that is deliberately longer than the previous one hundred twenty character response schema limit for this documented regression test'}],'limitations':['Synthetic retrospective data only.']}
    class FakeResponse:
        status_code=200
        def raise_for_status(self): pass
        def json(self): return {'choices':[{'message':{'content':json.dumps(answer)}}],'usage':{'prompt_tokens':8,'completion_tokens':9,'total_tokens':17}}
    def fake_post(url,**kwargs): captured.update(kwargs['json']); return FakeResponse()
    monkeypatch.setenv('GROQ_API_KEY','test-key'); monkeypatch.setattr(banking.httpx,'post',fake_post)
    b=banking.load_bundle(); row=banking.latest_snapshot(b,'CUST_00001','2025-09-01'); safe=banking.snapshot_dict(row)
    assert 'churn_within_30d' not in safe
    result=banking.groq_analysis(profile=banking.profile_dict(b,'CUST_00001'),snapshot=safe,assessment=banking.assess(row.to_dict()),segment=banking.segment_comparison(b,'Mass'),request_id='req-test-123456')
    assert result['metadata']['status']=='available' and result['metadata']['token_usage']['total_tokens']==17
    assert result['answer']['customer_insights']==['Activity declined.','Digital engagement fell.']
    assert len(result['answer']['retention_recommendations'][2]['success_indicator'])>120
    user=json.loads(captured['messages'][1]['content'])
    assert 'historical_outcome' not in user and 'churn_within_30d' not in str(user)
    assert 'customer_id' not in str(user) and 'synthetic_churn_reason' not in str(user) and 'synthetic_scenario' not in str(user)
    assert 'age' not in user['customer_profile'] and 'monthly_income_sar' not in user['customer_profile']

def test_postgres_migration_and_record_event_mocked(monkeypatch):
    migration=Path('monitoring/migrations/001_initial.sql').read_text(encoding='utf-8-sig')
    for table in ('monitoring_requests','llm_responses','llm_request_metrics','monitoring_errors','churn_evaluations'): assert f'CREATE TABLE IF NOT EXISTS {table}' in migration
    class Cursor:
        def __init__(self): self.sql=[]
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def execute(self,sql,params=None): self.sql.append(sql)
        def fetchone(self): return ('00000000-0000-0000-0000-000000000001',)
    class Conn:
        def __init__(self): self.cur=Cursor()
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def cursor(self): return self.cur
    conn=Conn(); monkeypatch.setattr(database,'connect',lambda:conn)
    event={'request_id':'request-id-123456','timestamp':'2026-10-22T00:00:00+00:00','provider':'groq','model':'model','request_status':'available','assessment_type':'rules','risk_category':'Medium','customer_id':'CUST_00001','snapshot_date':'2025-09-01','evaluation_status':'eligible','latency_ms':12.0,'token_usage':{'total_tokens':10},'error_category':None,'llm_response':{'executive_summary':'ok'},'actual_outcomes':[{'horizon_days':30,'label_eligible':True,'actual_churn':0,'rule_alert_match':False}]}
    result=database.record_event(event)
    assert result.endswith('0001') and len(conn.cur.sql)==4

def test_monitoring_client_does_not_break_when_down(monkeypatch):
    def fail(*args,**kwargs): raise __import__('httpx').ConnectError('not available')
    monkeypatch.setattr(monitoring_client.httpx,'post',fail)
    assert monitoring_client.emit({'request_id':'request-id-123'})['delivery_status']=='unavailable'


def test_monitoring_health_and_write_endpoints_mocked(monkeypatch):
    class Cur:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def execute(self,*args,**kwargs): pass
    class Conn:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def cursor(self): return Cur()
    monkeypatch.setattr(database,'connect',lambda:Conn())
    monkeypatch.setattr(monitoring_module,'connect',lambda:Conn())
    monkeypatch.setattr(database,'record_event',lambda event:'00000000-0000-0000-0000-000000000099')
    monkeypatch.setattr(monitoring_module,'record_event',lambda event:'00000000-0000-0000-0000-000000000099')
    monkeypatch.setattr(monitoring_module,'recent_events',lambda limit,status:[{'request_id':'request-id-123456','request_status':'available'}])
    monkeypatch.setattr(monitoring_module,'summary',lambda:{'request_count':1,'success_count':1,'failure_count':0,'mean_latency_ms':10.0,'errors_by_category':{}})
    with TestClient(monitoring_app) as client:
        assert client.get('/api/monitoring/health').json()['database']=='connected'
        result=client.post('/api/monitoring/events',json={'request_id':'request-id-123456','timestamp':'2026-10-22T00:00:00Z','provider':'groq','model':'test','request_status':'available','assessment_type':'rules','risk_category':'Low','evaluation_status':'not_evaluated','latency_ms':10,'token_usage':{'total_tokens':5}})
        assert result.status_code==201 and result.json()['status']=='recorded'
        assert client.get('/api/monitoring/requests?limit=1&status=available').json()['requests'][0]['request_id']=='request-id-123456'
        summary=client.get('/api/monitoring/summary').json()
        assert summary['request_count']==1 and summary['correctness_note'].startswith('LLM availability')
        assert client.get('/api/monitoring/requests?limit=0').status_code==422
        assert client.post('/api/monitoring/events',json={'request_id':'x'}).status_code==422


def test_loader_reports_missing_package_files(tmp_path):
    with __import__('pytest').raises(FileNotFoundError) as err:
        banking.load_bundle(tmp_path)
    for name in banking.DATA_FILES:
        assert name in str(err.value)

def test_groq_rate_limit_and_malformed_response_fallback(monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY','test-key')
    class Response:
        def __init__(self,status,body=None): self.status_code=status; self.body=body or {}
        def raise_for_status(self):
            if self.status_code>=400:
                raise __import__('httpx').HTTPStatusError('private provider text',request=__import__('httpx').Request('POST','https://api.groq.com'),response=__import__('httpx').Response(self.status_code,request=__import__('httpx').Request('POST','https://api.groq.com')))
        def json(self): return self.body
    monkeypatch.setattr(banking.httpx,'post',lambda *a,**k:Response(429))
    kwargs={'profile':{},'snapshot':{},'assessment':{'risk_factors':[],'risk_category':'Low','assessment_type':'rules'},'segment':{},'request_id':'request-id-123456'}
    limited=banking.groq_analysis(**kwargs)
    assert limited['metadata']['error_category']=='rate_limited'
    monkeypatch.setattr(banking.httpx,'post',lambda *a,**k:Response(200,{'choices':[{'message':{'content':'not json'}}]}))
    bad=banking.groq_analysis(**kwargs)
    assert bad['metadata']['error_category']=='malformed_response' and bad['answer'] is None
    assert 'private provider text' not in str(limited)


def test_groq_timeout_and_invalid_credentials_are_categorized(monkeypatch):
    import httpx
    monkeypatch.setenv('GROQ_API_KEY','test-key')
    kwargs={'profile':{},'snapshot':{},'assessment':{'risk_factors':[],'risk_category':'Low','assessment_type':'rules'},'segment':{},'request_id':'request-id-123456'}
    monkeypatch.setattr(banking.httpx,'post',lambda *a,**k: (_ for _ in ()).throw(httpx.ReadTimeout('private timeout details')))
    timeout=banking.groq_analysis(**kwargs)
    assert timeout['metadata']['error_category']=='timeout' and timeout['answer'] is None
    class Unauthorized:
        status_code=401
        def raise_for_status(self): pass
    monkeypatch.setattr(banking.httpx,'post',lambda *a,**k:Unauthorized())
    denied=banking.groq_analysis(**kwargs)
    assert denied['metadata']['error_category']=='invalid_credentials' and denied['answer'] is None


def test_groq_missing_credentials_returns_fallback_status(monkeypatch):
    monkeypatch.delenv('GROQ_API_KEY',raising=False)
    result=banking.groq_analysis(profile={},snapshot={},assessment={'risk_factors':[],'risk_category':'Low','assessment_type':'rules'},segment={},request_id='request-id-123456')
    assert result['metadata']['status']=='unavailable'
    assert result['metadata']['error_category']=='missing_credentials'
    assert result['answer'] is None


def test_frontend_cors_preflight():
    with TestClient(app) as client:
        allowed=client.options('/api/dashboard',headers={'Origin':'http://localhost:5173','Access-Control-Request-Method':'GET'})
        assert allowed.status_code==200
        assert allowed.headers['access-control-allow-origin']=='http://localhost:5173'
        rejected=client.options('/api/dashboard',headers={'Origin':'https://unconfigured.example','Access-Control-Request-Method':'GET'})
        assert rejected.status_code==400
