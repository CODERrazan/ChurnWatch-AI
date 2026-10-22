from __future__ import annotations
import logging, os
from datetime import datetime, timezone
from typing import Any
import httpx

log=logging.getLogger('churnwatch.monitoring')

def emit(event:dict[str,Any])->dict[str,Any]:
    base=os.getenv('MONITORING_URL','http://127.0.0.1:8010').rstrip('/')
    try:
        response=httpx.post(base+'/api/monitoring/events',json=event,timeout=float(os.getenv('MONITORING_TIMEOUT_SECONDS','0.5')))
        response.raise_for_status()
        stored=response.json() if response.content else {}
        return {'delivery_status':'recorded','prediction_id':stored.get('prediction_id')}
    except Exception as exc:
        category='timeout' if isinstance(exc,httpx.TimeoutException) else 'unavailable'
        log.info('monitoring_delivery_failed category=%s request_id=%s',category,event.get('request_id'))
        return {'delivery_status':'unavailable','error_category':category}

def build_event(*,request_id:str,metadata:dict[str,Any],assessment_type:str,risk_category:str,customer_id:str,snapshot_date:str,evaluation:dict[str,Any],answer:dict[str,Any]|None)->dict[str,Any]:
    outcomes=[]
    for horizon in (30,90):
        label=f'label_{horizon}d'; observed=bool(evaluation.get(f'label_observed_{horizon}d')); actual=evaluation.get(label)
        eligible=observed and actual is not None
        outcomes.append({'horizon_days':horizon,'label_eligible':eligible,'actual_churn':int(actual) if eligible else None,'rule_alert_match':(risk_category in {'Medium','High'}) == bool(actual) if eligible and horizon==30 else None})
    return {'request_id':request_id,'timestamp':datetime.now(timezone.utc).isoformat(),'provider':metadata.get('provider','groq'),'model':metadata.get('model','unknown'),'request_status':metadata.get('status','unavailable'),'assessment_type':assessment_type,'risk_category':risk_category,'customer_id':customer_id,'snapshot_date':snapshot_date,'evaluation_status':'eligible_retrospective_outcome' if any(x['label_eligible'] for x in outcomes) else 'outcome_not_eligible','latency_ms':metadata.get('latency_ms'),'token_usage':metadata.get('token_usage'),'error_category':metadata.get('error_category'),'safe_error_detail':metadata.get('error_category'),'llm_response':answer,'actual_outcomes':outcomes}
