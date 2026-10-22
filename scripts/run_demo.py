from __future__ import annotations
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from app import config, banking

def main():
    b=banking.load_bundle(); d=banking.dashboard(b)
    print(json.dumps({'data_notice':d['data_notice'],'total_customers':d['total_customers'],'historical_churn_count':d['historical_churn_count'],'historical_churn_rate':d['historical_churn_rate'],'risk_distribution':d['risk_distribution'],'retrospective_evaluation':d['retrospective_evaluation']},indent=2))
    cid='CUST_00042'; row=banking.latest_snapshot(b,cid); profile=banking.profile_dict(b,cid); snapshot=banking.snapshot_dict(row); risk=banking.assess(row.to_dict())
    llm=banking.groq_analysis(profile=profile,snapshot=snapshot,assessment=risk,segment=banking.segment_comparison(b,str(profile['customer_segment'])),request_id='demo-'+cid)
    print('sample_customer_id:',cid,'snapshot_date:',row.snapshot_date.date().isoformat())
    print('rule_assessment:',json.dumps(risk,indent=2,default=str)); print('llm_metadata:',json.dumps(llm['metadata'],indent=2,default=str)); print('llm_answer:',json.dumps(llm['answer'],indent=2,default=str))
if __name__=='__main__': main()
