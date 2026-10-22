from __future__ import annotations
import json, logging, time, uuid
from collections import Counter, deque
from contextlib import asynccontextmanager
from typing import Any
import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from . import banking, config, monitoring_client

logging.basicConfig(level=logging.INFO,format='%(message)s')
log=logging.getLogger('churnwatch.api')
BUNDLE:banking.DataBundle|None=None
DASHBOARD:dict[str,Any]={}
LATEST:pd.DataFrame|None=None
RECENT:deque=deque(maxlen=100)
HISTORY:dict[str,list[dict[str,Any]]]={}
COUNTS:Counter=Counter(); LATENCIES:deque=deque(maxlen=10000)

@asynccontextmanager
async def lifespan(_app:FastAPI):
    initialize(); yield

app=FastAPI(title='ChurnWatch AI Banking Analytics API',version='3.0.0',description='Synthetic-data demo API. Transparent rule indicators assess risk; Groq explains supplied evidence.',lifespan=lifespan)
_default_frontend_origins='http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173'
_frontend_origins=[origin.strip() for origin in __import__('os').getenv('FRONTEND_ORIGINS',_default_frontend_origins).split(',') if origin.strip()]
app.add_middleware(CORSMiddleware,allow_origins=_frontend_origins,allow_credentials=True,allow_methods=['*'],allow_headers=['*'])

def initialize():
    global BUNDLE,DASHBOARD,LATEST
    BUNDLE=banking.load_bundle()
    DASHBOARD=banking.dashboard(BUNDLE)
    LATEST=BUNDLE.snapshots.sort_values('snapshot_date').groupby('customer_id',sort=False).tail(1).copy()
    LATEST['assessment']=LATEST.apply(lambda r:banking.assess(r.to_dict()),axis=1)

def ready():
    if BUNDLE is None: initialize()

def fallback_answer(assessment:dict[str,Any])->dict[str,Any]:
    factors=assessment['risk_factors']
    summary=(f"Rule-based screening found {len(factors)} documented risk indicators ({assessment['risk_category']} category)." if factors else 'No configured risk indicators crossed their review thresholds in this snapshot.')
    insights=[f['interpretation'] for f in factors[:5]] or ['No configured risk threshold was crossed; this does not guarantee that churn will not occur.']
    return {'executive_summary':summary,'customer_insights':insights,'retention_recommendations':banking.recommendations_for(assessment),'limitations':assessment['limitations']}

@app.middleware('http')
async def observe(request:Request,call_next):
    request.state.request_id=str(uuid.uuid4())
    start=time.perf_counter()
    try: response=await call_next(request)
    except Exception:
        log.exception('request_failed request_id=%s path=%s',request.state.request_id,request.url.path)
        response=JSONResponse(status_code=500,content={'detail':{'code':'internal_error','message':'Request failed.'}})
    elapsed=(time.perf_counter()-start)*1000
    LATENCIES.append(elapsed); COUNTS[(request.method,request.url.path,response.status_code)]+=1
    response.headers['X-Request-ID']=request.state.request_id
    log.info(json.dumps({'event':'api_request','request_id':request.state.request_id,'method':request.method,'path':request.url.path,'status':response.status_code,'latency_ms':round(elapsed,3)}))
    return response

@app.get('/api/health')
def health():
    ready()
    return {'status':'ok','application':'available','dataset':'available','data_notice':banking.SYNTHETIC_NOTICE,'groq':{'configured':bool(__import__('os').getenv('GROQ_API_KEY')),'model':__import__('os').getenv('GROQ_MODEL','openai/gpt-oss-120b')},'monitoring':{'url':__import__('os').getenv('MONITORING_URL','http://127.0.0.1:8010'),'database_connection':'not_checked_by_main_api'}}

@app.get('/api/dashboard')
def get_dashboard():
    ready()
    result=dict(DASHBOARD); result['recent_analysis_activity']=list(RECENT)[:20]
    return result

@app.get('/api/customers')
def customers(page:int=Query(1,ge=1),page_size:int=Query(50,ge=1,le=200),risk_category:str|None=None,customer_segment:str|None=None,search:str|None=None):
    ready()
    if risk_category and risk_category not in {'Low','Medium','High'}: raise HTTPException(422,{'code':'invalid_risk_category'})
    frame=LATEST.copy()
    frame['risk_category']=frame.assessment.map(lambda a:a['risk_category'])
    if risk_category: frame=frame[frame.risk_category==risk_category]
    if customer_segment: frame=frame[frame.customer_segment==customer_segment]
    if search: frame=frame[frame.customer_id.str.contains(search,case=False,regex=False)]
    frame['_risk_order']=frame.risk_category.map({'High':3,'Medium':2,'Low':1})
    frame=frame.sort_values(['_risk_order','customer_id'],ascending=[False,True])
    total=len(frame); start=(page-1)*page_size; selected=frame.iloc[start:start+page_size]
    items=[]
    for _,row in selected.iterrows():
        a=row.assessment
        items.append({'customer_id':row.customer_id,'customer_segment':row.customer_segment,'snapshot_date':row.snapshot_date.date().isoformat(),'risk_category':a['risk_category'],'risk_score':a['risk_score'],'risk_score_unit':a['risk_score_unit'],'risk_factor_count':len(a['risk_factors'])})
    return {'data_notice':banking.SYNTHETIC_NOTICE,'page':page,'page_size':page_size,'total':total,'customers':items}

@app.get('/api/customers/{customer_id}')
def customer_detail(customer_id:str,snapshot_date:str|None=None):
    ready()
    if customer_id not in set(BUNDLE.customers.customer_id): raise HTTPException(404,{'code':'customer_not_found'})
    try: row=banking.latest_snapshot(BUNDLE,customer_id,snapshot_date)
    except ValueError as exc: raise HTTPException(422,{'code':'invalid_snapshot_date','message':str(exc)})
    except KeyError: raise HTTPException(404,{'code':'snapshot_not_found'})
    profile=banking.profile_dict(BUNDLE,customer_id); snap=banking.snapshot_dict(row); assessment=banking.assess(row.to_dict())
    return {'data_notice':banking.SYNTHETIC_NOTICE,'customer_id':customer_id,'profile':profile,'snapshot_date':row.snapshot_date.date().isoformat(),'current_snapshot':snap,'snapshot':snap,'risk_assessment':assessment,'historical_outcome':banking.eligible_outcome(BUNDLE,row),'analysis_history':HISTORY.get(customer_id,[])}

@app.post('/api/customers/{customer_id}/analyze')
def analyze_customer(customer_id:str,request:Request,snapshot_date:str|None=None):
    ready()
    if customer_id not in set(BUNDLE.customers.customer_id): raise HTTPException(404,{'code':'customer_not_found'})
    try: row=banking.latest_snapshot(BUNDLE,customer_id,snapshot_date)
    except ValueError as exc: raise HTTPException(422,{'code':'invalid_snapshot_date','message':str(exc)})
    except KeyError: raise HTTPException(404,{'code':'snapshot_not_found'})
    rid=request.state.request_id; profile=banking.profile_dict(BUNDLE,customer_id); snap=banking.snapshot_dict(row)
    assessment=banking.assess(row.to_dict()); segment=banking.segment_comparison(BUNDLE,str(profile.get('customer_segment','')))
    llm=banking.groq_analysis(profile=profile,snapshot=snap,assessment=assessment,segment=segment,request_id=rid)
    # Preserve the measured provider-call latency; assessment latency is independent.
    meta=llm['metadata']; answer=llm['answer'] or fallback_answer(assessment)
    evaluation=banking.eligible_outcome(BUNDLE,row)
    event=monitoring_client.build_event(request_id=rid,metadata=meta,assessment_type=assessment['assessment_type'],risk_category=assessment['risk_category'],customer_id=customer_id,snapshot_date=row.snapshot_date.date().isoformat(),evaluation=evaluation,answer=llm['answer'])
    monitoring=monitoring_client.emit(event)
    response={'data_notice':banking.SYNTHETIC_NOTICE,'request_id':rid,'customer_id':customer_id,'profile':profile,'snapshot_date':row.snapshot_date.date().isoformat(),'current_snapshot':snap,'risk_assessment':assessment,'executive_summary':answer['executive_summary'],'customer_insights':answer['customer_insights'],'retention_recommendations':answer['retention_recommendations'],'historical_outcome':evaluation,'limitations':answer['limitations'],'segment_comparison':segment,'llm_metadata':meta,'monitoring':{'prediction_id':rid,**monitoring,'evaluation_status':event['evaluation_status'],'rule_alert_match_30d':next((x['rule_alert_match'] for x in event['actual_outcomes'] if x['horizon_days']==30),None),'llm_correctness_status':'not_evaluated'}}
    RECENT.appendleft({'request_id':rid,'customer_id':customer_id,'snapshot_date':response['snapshot_date'],'risk_category':assessment['risk_category'],'llm_status':meta['status'],'monitoring_delivery':monitoring['delivery_status']})
    HISTORY.setdefault(customer_id,[]).insert(0,{'request_id':rid,'snapshot_date':response['snapshot_date'],'llm_status':meta['status'],'risk_category':assessment['risk_category']})
    HISTORY[customer_id]=HISTORY[customer_id][:20]
    return response

@app.get('/api/metrics')
def metrics():
    vals=sorted(LATENCIES)
    lines=['# TYPE churnwatch_api_requests_total counter']
    for (method,path,status),count in COUNTS.items(): lines.append(f'churnwatch_api_requests_total{{method="{method}",path="{path}",status="{status}"}} {count}')
    for q,name in ((.5,'p50'),(.95,'p95'),(.99,'p99')):
        if vals: lines.append(f'churnwatch_api_latency_ms{{quantile="{name}"}} {vals[min(len(vals)-1,int((len(vals)-1)*q))]:.3f}')
    return Response('\n'.join(lines)+'\n',media_type='text/plain; version=0.0.4')
