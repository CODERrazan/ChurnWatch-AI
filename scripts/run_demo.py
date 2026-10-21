"""Print one synthetic banking row, its ML prediction, Groq request, and response."""
from __future__ import annotations
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from app import config, core

def main():
    data=core.load_data()
    features=core.feature_columns(data)
    row=data.iloc[[0]]
    customer={name:(value.item() if hasattr(value,'item') else value) for name,value in row.iloc[0][features].items()}
    model,metrics=core.build_model(data)
    prediction=core.score(model,row[features],features)
    llm_input={k:v for k,v in prediction.items() if k!='model_latency_ms'}
    print('=== CUSTOMER FEATURES FROM SYNTHETIC DATASET ===')
    print(json.dumps(customer,indent=2,ensure_ascii=True))
    print('\n=== PYTHON MODEL PREDICTION ===')
    print(json.dumps(llm_input,indent=2,ensure_ascii=True))
    original_post=core.httpx.post
    def visible_post(url,*,headers=None,json=None,timeout=None,**kwargs):
        print('\n=== OUTBOUND GROQ REQUEST ===')
        print('POST '+url)
        safe_headers=dict(headers or {})
        if 'Authorization' in safe_headers: safe_headers['Authorization']='Bearer [REDACTED]'
        print('headers='+__import__('json').dumps(safe_headers,ensure_ascii=True))
        print('json='+__import__('json').dumps(json,indent=2,ensure_ascii=True,default=str))
        response=original_post(url,headers=headers,json=json,timeout=timeout,**kwargs)
        print('Groq HTTP status='+str(response.status_code))
        return response
    core.httpx.post=visible_post
    result=core.groq_explanation(llm_input,customer)
    print('\n=== GROQ RESULT ===')
    print(json.dumps(result,indent=2,ensure_ascii=True,default=str))
if __name__=='__main__': main()
