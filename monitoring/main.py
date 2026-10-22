from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Literal
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from app import config as _config
from .database import connect, record_event, recent_events, summary
from .evaluation import prediction_evaluation

app=FastAPI(title='ChurnWatch Monitoring Service',version='1.0.0',description='Separate Supabase PostgreSQL telemetry service. Apply monitoring/migrations/001_initial.sql before use.')

class MonitoringEvent(BaseModel):
    request_id:str=Field(min_length=8,max_length=100)
    timestamp:datetime
    provider:str='groq'
    model:str=Field(min_length=1,max_length=120)
    request_status:str=Field(pattern='^(available|unavailable)$')
    assessment_type:str
    risk_category:str=Field(pattern='^(Low|Medium|High)$')
    customer_id:str|None=None
    snapshot_date:str|None=None
    evaluation_status:str='not_evaluated'
    latency_ms:float|None=Field(default=None,ge=0)
    token_usage:dict[str,int]|None=None
    error_category:str|None=None
    safe_error_detail:str|None=None
    llm_response:dict[str,Any]|None=None
    actual_outcomes:list[dict[str,Any]]=Field(default_factory=list)

@app.get('/api/monitoring/health')
def health():
    try:
        with connect() as conn:
            with conn.cursor() as cur: cur.execute('SELECT 1')
        return {'status':'ok','service':'monitoring','database':'connected','storage':'supabase_postgresql'}
    except Exception as exc:
        code='database_url_missing' if 'DATABASE_URL' in str(exc) else 'database_unavailable'
        raise HTTPException(503,{'status':'degraded','service':'monitoring','database':'unavailable','code':code})

@app.post('/api/monitoring/events',status_code=201)
def create_event(event:MonitoringEvent):
    try: prediction_id=record_event(event.model_dump())
    except Exception:
        raise HTTPException(503,{'code':'monitoring_write_failed','message':'Monitoring storage is unavailable.'})
    return {'status':'recorded','prediction_id':prediction_id,'request_id':event.request_id}

@app.get('/api/monitoring/requests')
def list_requests(limit:int=Query(100,ge=1,le=1000),status:str|None=None):
    try: return {'service':'monitoring','requests':recent_events(limit,status)}
    except Exception: raise HTTPException(503,{'code':'monitoring_read_failed'})

@app.get('/api/monitoring/summary')
def get_summary():
    try: return {'service':'monitoring',**summary(),'correctness_note':'LLM availability is not correctness. LLM correctness remains not_evaluated unless independently reviewed.'}
    except Exception: raise HTTPException(503,{'code':'monitoring_summary_failed'})

@app.get('/api/monitoring/prediction-evaluation')
def get_prediction_evaluation(horizon:Literal['30d','90d']=Query('30d')):
    try: return {'service':'monitoring',**prediction_evaluation(horizon)}
    except Exception: raise HTTPException(503,{'code':'prediction_evaluation_unavailable'})
