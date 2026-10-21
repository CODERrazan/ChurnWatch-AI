from fastapi.testclient import TestClient
from app.main import app
from app import core
import pandas as pd


def customer():
    return core.load_data().iloc[0][core.feature_columns(core.load_data())].to_dict()

def test_data_and_model_metrics():
    df=core.load_data(); model, metrics=core.build_model(df)
    assert 'customer_id' not in core.feature_columns(df)
    assert 'snapshot_date' not in core.feature_columns(df)
    assert 'churn_reason_after_exit' not in core.feature_columns(df)
    assert core.TARGET not in core.feature_columns(df)
    assert metrics['test_rows'] == 300
    assert 0 <= metrics['roc_auc'] <= 1 and 0 <= metrics['pr_auc'] <= 1
    assert len(metrics['confusion_matrix']) == 2

def test_endpoints_prediction_and_info():
    with TestClient(app) as client:
        assert client.get('/health').json()['model']['status']=='available'
        info=client.get('/model/info').json(); assert info['random_seed']==42
        result=client.post('/predict',json={'customer':customer()})
        assert result.status_code==200
        assert 0<=result.json()['prediction']['churn_probability']<=1
        assert result.json()['prediction']['risk_category'] in {'Low','Medium','High'}
        assert result.json()['prediction']['risk_signals']
        overview=client.get('/analytics/overview').json()
        assert overview['dataset']['customers']==1500
        assert 'customer_id' not in overview

def test_batch_invalid_and_metrics():
    with TestClient(app) as client:
        c=customer()
        assert client.post('/predict/batch',json={'customers':[c,c]}).json()['count']==2
        assert client.post('/predict',json={'customer':{}}).status_code==422
        assert client.post('/predict',json={'customer':{**c,'customer_id':'private'}}).status_code==422
        assert 'X-Request-ID' in client.get('/health').headers
        assert client.get('/metrics').status_code==200

def test_groq_fallback_and_error(monkeypatch):
    from app.core import groq_explanation
    monkeypatch.delenv('GROQ_API_KEY',raising=False)
    fallback=groq_explanation({'churn_probability':.8},{'age':40})
    assert fallback['status']=='unavailable' and fallback['error_category']=='missing_credentials'
    monkeypatch.setenv('GROQ_API_KEY','test-only')
    def fail(*args,**kwargs):
        import httpx
        request=httpx.Request('POST','https://api.groq.com')
        response=httpx.Response(429,request=request)
        raise httpx.HTTPStatusError('secret provider text',request=request,response=response)
    monkeypatch.setattr('app.core.httpx.post',fail)
    failed=groq_explanation({'churn_probability':.8},{'age':40})
    assert failed['status']=='unavailable'
    assert 'secret provider text' not in str(failed)

def test_llm_fallback_analyze(monkeypatch):
    monkeypatch.delenv('GROQ_API_KEY',raising=False)
    with TestClient(app) as client:
        response=client.post('/analyze',json={'customer':customer()})
        assert response.status_code==200
        body=response.json()
        assert body['prediction']['churn_probability']>=0
        assert body['llm']['error_category']=='missing_credentials'
        assert body['fallback_explanation']['source']=='model_contributions'


def test_groq_success_and_invalid_credentials(monkeypatch):
    from types import SimpleNamespace
    from app.core import groq_explanation
    monkeypatch.setenv('GROQ_API_KEY','test-only')
    monkeypatch.setattr('app.core.httpx.post', lambda *a, **k: SimpleNamespace(status_code=200, raise_for_status=lambda: None, json=lambda: {'choices':[{'message':{'content':'{"explanation":"Signals are correlated, not causal.","recommendations":["Offer support."]}'}}], 'usage':{'prompt_tokens':12,'completion_tokens':8,'total_tokens':20}}))
    ok=groq_explanation({'churn_probability':.8},{'age':40})
    assert ok['status']=='available' and ok['token_usage']['total_tokens']==20
    def unauthorized(*a,**k):
        import httpx
        request=httpx.Request('POST','https://api.groq.com')
        response=httpx.Response(401,request=request)
        response.raise_for_status=lambda: (_ for _ in ()).throw(httpx.HTTPStatusError('secret',request=request,response=response))
        return response
    monkeypatch.setattr('app.core.httpx.post',unauthorized)
    bad=groq_explanation({'churn_probability':.8},{'age':40})
    assert bad['error_category']=='invalid_credentials' and 'secret' not in str(bad)
