from __future__ import annotations
import json, logging, time, uuid
from collections import Counter, deque
from contextlib import asynccontextmanager
from typing import Any
import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, ConfigDict
from . import config, core

logging.basicConfig(level=logging.INFO, format='%(message)s')
log = logging.getLogger('churnwatch')
DATA: pd.DataFrame | None = None
MODEL = None
FEATURES: list[str] = []
METRICS: dict[str, Any] = {}
SUMMARY: dict[str, Any] = {}
COUNTS: Counter = Counter()
LATENCIES: deque = deque(maxlen=10000)
RISK_COUNTS: Counter = Counter()
MODEL_FAILURES = 0
MODEL_LATENCIES: deque = deque(maxlen=10000)
TOKEN_COUNTS: Counter = Counter()
LLM_COUNTS: Counter = Counter()

@asynccontextmanager
async def lifespan(_app: FastAPI):
    initialize()
    yield

app = FastAPI(title='ChurnWatch AI Banking API', version='2.0.0', description='Synthetic banking churn intelligence backend. Scores and metrics are computed in Python; Groq interprets structured results.', lifespan=lifespan)

def initialize() -> None:
    global DATA, MODEL, FEATURES, METRICS, SUMMARY
    DATA = core.load_data()
    MODEL, METRICS = core.build_model(DATA)
    FEATURES = core.feature_columns(DATA)
    SUMMARY = core.analytics(DATA)
    # Persist the deployable full-data pipeline and held-out evaluation metadata.
    core.ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    import joblib
    joblib.dump({'model': MODEL, 'features': FEATURES, 'metrics': METRICS, 'rows': len(DATA), 'seed': core.SEED, 'version': core.MODEL_VERSION, 'trained_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}, core.ARTIFACT_PATH)

def ready() -> None:
    if DATA is None or MODEL is None: initialize()

class CustomerRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    customer: dict[str, Any]

class BatchRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    customers: list[dict[str, Any]] = Field(min_length=1, max_length=500)


def validate_customer(customer: dict[str, Any]) -> pd.DataFrame:
    missing = [c for c in FEATURES if c not in customer]
    extra = [c for c in customer if c not in FEATURES]
    if missing or extra:
        raise HTTPException(422, {'code':'invalid_customer_features','missing_fields':missing,'unsupported_fields':extra})
    row = pd.DataFrame([{c: customer[c] for c in FEATURES}])
    if row.isna().any().any():
        raise HTTPException(422, {'code':'null_feature_value'})
    try:
        for c in row.select_dtypes(include=['object','str']).columns: row[c] = row[c].astype(str)
        for c in row.columns:
            if c not in row.select_dtypes(include=['object','str']).columns: row[c] = pd.to_numeric(row[c], errors='raise')
    except (ValueError, TypeError):
        raise HTTPException(422, {'code':'invalid_feature_type'})
    return row

@app.middleware('http')
async def observe(request: Request, call_next):
    rid = request.headers.get('X-Request-ID') or str(uuid.uuid4())
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        COUNTS[(request.method, request.url.path, 500)] += 1
        log.exception('request_failed request_id=%s path=%s', rid, request.url.path)
        response = JSONResponse(status_code=500, content={'detail':{'code':'internal_error','message':'The request could not be completed.'}})
    elapsed = time.perf_counter()-start
    LATENCIES.append(elapsed)
    COUNTS[(request.method, request.url.path, response.status_code)] += 1
    response.headers['X-Request-ID'] = rid
    log.info(json.dumps({'event':'request','request_id':rid,'method':request.method,'path':request.url.path,'status':response.status_code,'latency_ms':round(elapsed*1000,3)}))
    return response

@app.get('/health')
def health():
    model_ok = MODEL is not None
    return {'status':'ok' if model_ok else 'degraded','application':'ok','model':{'status':'available' if model_ok else 'unavailable'},'llm':{'status':'available' if core.llm_status()['configured'] else 'unconfigured','model':core.llm_status()['model']}}

@app.get('/model/info')
def model_info():
    ready()
    return {'model_version':core.MODEL_VERSION,'algorithm':'class-weighted logistic regression','training_rows':len(DATA),'random_seed':core.SEED,'evaluation':METRICS,'features':FEATURES,'excluded_features':sorted(core.EXCLUDED),'risk_thresholds':{'low':'p < 0.35','medium':'0.35 <= p < 0.65','high':'p >= 0.65'},'threshold_basis':'Fixed, transparent MVP display bands; not optimized against business costs.'}

@app.get('/analytics/overview')
def overview():
    ready()
    scored = MODEL.predict_proba(DATA[FEATURES])[:,1]
    dist = {name:int(sum(core.risk_category(float(p))==name for p in scored)) for name in ('Low','Medium','High')}
    return {**SUMMARY,'risk_distribution':dist,'model_metrics':METRICS,'data_notice':'Synthetic development and demonstration data; not real banking data.'}

@app.post('/predict')
def predict(request: CustomerRequest):
    ready(); row=validate_customer(request.customer)
    global MODEL_FAILURES
    try: result=core.score(MODEL,row,FEATURES); MODEL_LATENCIES.append(result['model_latency_ms'])
    except Exception:
        MODEL_FAILURES += 1
        COUNTS[('prediction_failure',)] += 1
        log.exception('prediction_failed')
        raise HTTPException(500, {'code':'prediction_failed','message':'The prediction could not be computed.'})
    RISK_COUNTS[result['risk_category']] += 1
    return {'status':'success','prediction':result}

@app.post('/predict/batch')
def predict_batch(request: BatchRequest):
    ready(); outputs=[]
    for customer in request.customers:
        row=validate_customer(customer); result=core.score(MODEL,row,FEATURES); MODEL_LATENCIES.append(result['model_latency_ms']); RISK_COUNTS[result['risk_category']] += 1; outputs.append(result)
    return {'status':'success','count':len(outputs),'predictions':outputs}

@app.post('/analyze')
def analyze(request: CustomerRequest):
    ready(); row=validate_customer(request.customer)
    global MODEL_FAILURES
    try: prediction=core.score(MODEL,row,FEATURES); MODEL_LATENCIES.append(prediction['model_latency_ms'])
    except Exception:
        MODEL_FAILURES += 1
        COUNTS[('prediction_failure',)] += 1
        raise HTTPException(500, {'code':'prediction_failed','message':'The prediction could not be computed.'})
    started=time.perf_counter()
    llm=core.groq_explanation({k:v for k,v in prediction.items() if k!='model_latency_ms'},request.customer)
    llm_ms=round((time.perf_counter()-started)*1000,3)
    LLM_COUNTS[llm.get('status','unavailable')] += 1
    if llm.get('error_category'): LLM_COUNTS[llm['error_category']] += 1
    usage=llm.get('token_usage') or {}
    for token_name, token_count in usage.items():
        if token_name in {'prompt_tokens','completion_tokens','total_tokens'} and isinstance(token_count,int): TOKEN_COUNTS[token_name] += token_count
    result={'status':'success','prediction':prediction,'llm':{**llm,'latency_ms':llm_ms}}
    if llm['status']!='available': result['fallback_explanation']={'source':'model_contributions','explanation':prediction['explanation'],'recommended_actions':prediction['recommended_actions']}
    return result

@app.get('/metrics')
def metrics():
    values=sorted(LATENCIES)
    def pct(q): return round(values[min(len(values)-1,int((len(values)-1)*q))]*1000,3) if values else None
    lines=['# HELP churnwatch_http_requests_total Requests by method, path, and status.','# TYPE churnwatch_http_requests_total counter']
    for (method,path,status),count in COUNTS.items():
        if isinstance(method,str): lines.append(f'churnwatch_http_requests_total{{method="{method}",path="{path}",status="{status}"}} {count}')
    lines += ['# HELP churnwatch_request_latency_ms Quantiles over the retained request latency window.','# TYPE churnwatch_request_latency_ms gauge']
    for q,label in ((.5,'p50'),(.95,'p95'),(.99,'p99')):
        if pct(q) is not None: lines.append(f'churnwatch_request_latency_ms{{quantile="{label}"}} {pct(q)}')
    for category,count in RISK_COUNTS.items(): lines.append(f'churnwatch_predictions_total{{risk="{category}"}} {count}')
    for status,count in LLM_COUNTS.items(): lines.append(f'churnwatch_llm_events_total{{category="{status}"}} {count}')
    for name,count in TOKEN_COUNTS.items(): lines.append(f'churnwatch_llm_tokens_total{{type="{name}"}} {count}')
    lines.append(f'churnwatch_model_inference_failures_total {MODEL_FAILURES}')
    mvals=sorted(MODEL_LATENCIES)
    if mvals:
        for q,label in ((.5,'p50'),(.95,'p95'),(.99,'p99')): lines.append(f'churnwatch_model_inference_latency_ms{{quantile="{label}"}} {mvals[min(len(mvals)-1,int((len(mvals)-1)*q))]}')
    return Response('\n'.join(lines)+'\n',media_type='text/plain; version=0.0.4')

@app.get('/')
def root(): return {'name':'ChurnWatch AI','docs':'/docs','health':'/health'}

