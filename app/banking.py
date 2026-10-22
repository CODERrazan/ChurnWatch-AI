from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
from pydantic import BaseModel, Field, ValidationError

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / 'Data' / 'churnwatch_v1_mock_data'
DATA_FILES = ('customers.csv', 'monthly_snapshots.csv', 'churn_outcomes.csv', 'data_dictionary.csv', 'frontend_field_contract.csv', 'expected_llm_response.json', 'README.md')
SYNTHETIC_NOTICE = 'Synthetic demonstration data only; not real banking data and not evidence of real-world performance.'
logger = logging.getLogger('churnwatch')

PROFILE_REQUIRED = {'customer_id','customer_segment','age','monthly_income_sar','tenure_months_at_start','active_products_count_at_start','regular_salary_inflow','autopay_enabled','loan_active','debit_card_active','digital_banking_enrolled','synthetic_data'}
SNAPSHOT_REQUIRED = {'customer_id','snapshot_date','months_since_start','customer_segment','tenure_months','active_products_count','transaction_count_change_3m_pct','active_digital_days_30d','digital_days_change_3m_pct','average_monthly_balance_sar','balance_change_3m_pct','failed_transaction_rate_pct','card_declines_30d','app_crashes_30d','failed_login_attempts_30d','support_tickets_90d','unresolved_tickets','repeat_contact_same_issue_90d','complaints_90d','median_resolution_hours','nps_score','external_transfer_count_30d','external_transfer_count_change_3m_pct','missed_salary_inflow_30d','bank_fee_charges_90d','overdraft_days_90d','recurring_payments_count','branch_visits_90d','snapshot_data_is_synthetic','churn_within_30d','churn_within_90d','label_observed_30d','label_observed_90d'}
OUTCOME_REQUIRED = {'customer_id','churned_during_followup','synthetic_churn_date','synthetic_churn_reason','synthetic_scenario','synthetic_data'}
OUTCOME_SIDE = {'churn_within_30d','churn_within_90d','label_observed_30d','label_observed_90d','synthetic_churn_date','synthetic_churn_reason','synthetic_scenario','churned_during_followup'}
IDENTIFIERS = {'customer_id','snapshot_date'}

@dataclass
class DataBundle:
    customers: pd.DataFrame
    snapshots: pd.DataFrame
    outcomes: pd.DataFrame
    dictionary: pd.DataFrame
    contract: pd.DataFrame


def load_bundle(data_dir: Path = DATA_DIR) -> DataBundle:
    missing = [name for name in DATA_FILES if not (data_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(f'Missing required banking package files in {data_dir}: {", ".join(missing)}')
    customers = pd.read_csv(data_dir / 'customers.csv')
    snapshots = pd.read_csv(data_dir / 'monthly_snapshots.csv')
    outcomes = pd.read_csv(data_dir / 'churn_outcomes.csv')
    dictionary = pd.read_csv(data_dir / 'data_dictionary.csv')
    contract = pd.read_csv(data_dir / 'frontend_field_contract.csv')
    if not {'column','dtype','description'}.issubset(dictionary.columns):
        raise ValueError('data_dictionary.csv schema must include column, dtype, description')
    if not {'frontend_section','field','purpose','source'}.issubset(contract.columns):
        raise ValueError('frontend_field_contract.csv schema must include frontend_section, field, purpose, source')
    try:
        expected=json.loads((data_dir/'expected_llm_response.json').read_text(encoding='utf-8-sig'))
    except (json.JSONDecodeError,OSError) as exc:
        raise ValueError('expected_llm_response.json must contain valid JSON') from exc
    if not isinstance(expected,dict):
        raise ValueError('expected_llm_response.json must contain a JSON object')
    required_sets = ((customers, PROFILE_REQUIRED, 'customers.csv'), (snapshots, SNAPSHOT_REQUIRED, 'monthly_snapshots.csv'), (outcomes, OUTCOME_REQUIRED, 'churn_outcomes.csv'))
    for frame, required, name in required_sets:
        absent = sorted(required - set(frame.columns))
        if absent:
            raise ValueError(f'{name} schema missing required columns: {absent}')
    if customers.customer_id.isna().any() or customers.customer_id.duplicated().any():
        raise ValueError('customers.csv customer_id must be present and unique')
    if outcomes.customer_id.isna().any() or outcomes.customer_id.duplicated().any():
        raise ValueError('churn_outcomes.csv customer_id must be present and unique')
    if snapshots[['customer_id','snapshot_date']].isna().any().any() or snapshots.duplicated(['customer_id','snapshot_date']).any():
        raise ValueError('monthly_snapshots.csv must have unique, non-null customer_id/snapshot_date pairs')
    snapshots['snapshot_date'] = pd.to_datetime(snapshots.snapshot_date, errors='coerce')
    outcomes['synthetic_churn_date'] = pd.to_datetime(outcomes.synthetic_churn_date, errors='coerce')
    if snapshots.snapshot_date.isna().any():
        raise ValueError('monthly_snapshots.csv contains invalid snapshot_date values')
    ids = set(customers.customer_id)
    if ids != set(snapshots.customer_id) or ids != set(outcomes.customer_id):
        raise ValueError('Customer IDs must match across profiles, snapshots, and outcomes')
    for horizon in ('30d','90d'):
        label, flag = 'churn_within_' + horizon, 'label_observed_' + horizon
        if not set(snapshots[flag].dropna().unique()).issubset({0,1}):
            raise ValueError(f'{flag} must be binary')
        if snapshots.loc[snapshots[flag] == 1, label].isna().any():
            raise ValueError(f'{label} must be present when {flag}=1')
        if not snapshots.loc[snapshots[flag] == 0, label].isna().all():
            raise ValueError(f'{label} must be null when {flag}=0')
    for frame,name,columns in ((customers,'customers.csv',['age','monthly_income_sar','tenure_months_at_start','active_products_count_at_start']), (snapshots,'monthly_snapshots.csv',['months_since_start','tenure_months','active_products_count','transaction_count_change_3m_pct','active_digital_days_30d','digital_days_change_3m_pct','average_monthly_balance_sar','balance_change_3m_pct','failed_transaction_rate_pct','card_declines_30d','app_crashes_30d','failed_login_attempts_30d','support_tickets_90d','unresolved_tickets','repeat_contact_same_issue_90d','complaints_90d','median_resolution_hours','nps_score','external_transfer_count_30d','external_transfer_count_change_3m_pct','missed_salary_inflow_30d','bank_fee_charges_90d','overdraft_days_90d','recurring_payments_count','branch_visits_90d']), (outcomes,'churn_outcomes.csv',['churned_during_followup'])):
        for col in columns:
            if not pd.api.types.is_numeric_dtype(frame[col]):
                raise ValueError(f'{name} column {col} must be numeric')
    if not set(outcomes.churned_during_followup.unique()).issubset({0,1}):
        raise ValueError('churn_outcomes.csv churned_during_followup must be binary')
    if (outcomes.loc[outcomes.churned_during_followup==1,'synthetic_churn_date'].isna().any() or outcomes.loc[outcomes.churned_during_followup==0,'synthetic_churn_date'].notna().any()):
        raise ValueError('Synthetic outcome dates must be present only for churned records')
    return DataBundle(customers, snapshots, outcomes, dictionary, contract)

# Point-based transparent indicators. This is an ordinal heuristic, never a probability.
RULES = [
    ('transaction_count_change_3m_pct', lambda v: v <= -20, 2, 'Transaction activity declined by at least 20% over the recent three-month window.'),
    ('digital_days_change_3m_pct', lambda v: v <= -20, 1, 'Digital activity days declined by at least 20%.'),
    ('active_digital_days_30d', lambda v: v <= 7, 1, 'Digital activity was observed on 7 or fewer days in the last 30 days.'),
    ('balance_change_3m_pct', lambda v: v <= -20, 1, 'Average balance declined by at least 20%; this alone does not establish intent to leave.'),
    ('failed_transaction_rate_pct', lambda v: v >= 10, 1, 'Failed transaction rate is at least 10%.'),
    ('card_declines_30d', lambda v: v >= 3, 1, 'Three or more card declines occurred in the last 30 days.'),
    ('app_crashes_30d', lambda v: v >= 5, 1, 'Five or more app crashes occurred in the last 30 days.'),
    ('failed_login_attempts_30d', lambda v: v >= 5, 1, 'Five or more failed login attempts occurred in the last 30 days.'),
    ('support_tickets_90d', lambda v: v >= 3, 1, 'Three or more support tickets were recorded in the last 90 days.'),
    ('unresolved_tickets', lambda v: v > 0, 2, 'At least one support ticket is currently unresolved.'),
    ('repeat_contact_same_issue_90d', lambda v: v > 0, 1, 'The customer contacted support repeatedly about the same issue.'),
    ('complaints_90d', lambda v: v >= 2, 1, 'Two or more complaints were recorded in the last 90 days.'),
    ('median_resolution_hours', lambda v: v >= 72, 1, 'Median issue resolution time is at least 72 hours.'),
    ('missed_salary_inflow_30d', lambda v: v == 1, 2, 'An expected salary inflow was missed; cause is unknown.'),
    ('bank_fee_charges_90d', lambda v: v >= 3, 1, 'Three or more bank fee charges were recorded in the last 90 days.'),
    ('overdraft_days_90d', lambda v: v >= 5, 1, 'Five or more overdraft days were recorded in the last 90 days.'),
    ('external_transfer_count_change_3m_pct', lambda v: v >= 50, 1, 'External transfers increased by at least 50%; this does not prove competitor use.'),
    ('nps_score', lambda v: v <= 4, 1, 'The recorded satisfaction score is 4 or lower.'),
]
RISK_INPUTS = {r[0] for r in RULES} | {'customer_segment','tenure_months','active_products_count','snapshot_data_is_synthetic'}


def assess(snapshot: dict[str, Any]) -> dict[str, Any]:
    factors=[]; points=0
    for feature, condition, weight, text in RULES:
        value=snapshot.get(feature)
        if value is None or pd.isna(value):
            continue
        try: hit=bool(condition(float(value)))
        except (ValueError,TypeError): hit=False
        if hit:
            points += weight
            factors.append({'feature':feature,'observed_value':value.item() if hasattr(value,'item') else value,'direction':'risk_indicator','points':weight,'interpretation':text})
    tenure=snapshot.get('tenure_months'); products=snapshot.get('active_products_count')
    if tenure is not None and products is not None and not pd.isna(tenure) and not pd.isna(products) and float(tenure)<12 and float(products)<=1:
        points+=1; factors.append({'feature':'tenure_months + active_products_count','observed_value':{'tenure_months':tenure,'active_products_count':products},'direction':'risk_indicator','points':1,'interpretation':'Short relationship tenure with one or fewer active products may indicate a less established relationship.'})
    category='High' if points>=6 else 'Medium' if points>=3 else 'Low'
    return {'assessment_type':'transparent_rule_based_indicator_score','risk_category':category,'risk_score':points,'risk_score_unit':'points (not probability)','thresholds':{'Low':'0-2 points','Medium':'3-5 points','High':'6+ points'},'risk_factors':factors,'limitations':['Heuristic indicators are not a trained model or calibrated churn probability.','Indicators describe associations and do not establish causes or customer intent.','Synthetic demo data does not establish real-world banking performance.']}


def recommendations_for(assessment: dict[str, Any]) -> list[dict[str, Any]]:
    features={x['feature'] for x in assessment['risk_factors']}; out=[]
    def add(action,reason,priority,owner,metric):
        out.append({'action':action,'rationale':reason,'priority':priority,'suggested_owner':owner,'success_indicator':metric})
    if features & {'unresolved_tickets','repeat_contact_same_issue_90d','complaints_90d','median_resolution_hours','support_tickets_90d'}:
        add('Review unresolved cases and contact the customer about the reported service issues.','Support friction indicators were present; confirm the issue before offering a remedy.','high','customer_support','ticket_resolution_and_repeat_contact_rate')
    if features & {'transaction_count_change_3m_pct','active_digital_days_30d','digital_days_change_3m_pct','app_crashes_30d','failed_login_attempts_30d','failed_transaction_rate_pct','card_declines_30d'}:
        add('Check digital and payment experience for avoidable friction, then offer targeted assistance.','Recent activity or reliability indicators crossed documented review thresholds.','high','digital_banking','30d_digital_activity_and_failure_rate')
    if features & {'missed_salary_inflow_30d','overdraft_days_90d','bank_fee_charges_90d','balance_change_3m_pct'}:
        add('Offer a consent-based financial check-in and explain relevant account options or fee support.','A cash-flow or fee indicator was observed; its cause is not known.','medium','relationship_manager','30d_salary_inflow_and_fee_complaints')
    if 'external_transfer_count_change_3m_pct' in features:
        add('Ask whether account needs have changed and review suitable services without assuming competitor use.','External transfer activity increased; it is only a proxy signal.','medium','relationship_manager','customer_confirmed_needs_and_30d_primary_activity')
    if 'nps_score' in features:
        add('Invite brief feedback and close the loop on the customer’s stated concerns.','The recorded satisfaction score crossed the review threshold.','medium','customer_experience','follow_up_satisfaction_score')
    if len(out)<3 and assessment['risk_category']!='Low':
        add('Confirm the customer’s preferred contact channel and ask whether support is needed.','Use a low-friction check-in; the rule score is only a screening signal.','low','relationship_manager','customer_response_and_30d_engagement')
    return out[:6]


def latest_snapshot(bundle: DataBundle, customer_id: str, snapshot_date: str | None = None) -> pd.Series:
    rows=bundle.snapshots[bundle.snapshots.customer_id == customer_id]
    if snapshot_date:
        date=pd.to_datetime(snapshot_date,errors='coerce')
        if pd.isna(date): raise ValueError('snapshot_date must be an ISO date')
        rows=rows[rows.snapshot_date == date]
    else:
        rows=rows.sort_values('snapshot_date').tail(1)
    if rows.empty: raise KeyError('customer or snapshot not found')
    return rows.iloc[-1]


def profile_dict(bundle: DataBundle, customer_id: str) -> dict[str, Any]:
    row=bundle.customers.loc[bundle.customers.customer_id==customer_id]
    if row.empty: raise KeyError('customer not found')
    return clean_record(row.iloc[0].drop(labels=['synthetic_data','customer_id'],errors='ignore').to_dict())


def clean_record(value: Any) -> Any:
    if isinstance(value,dict): return {str(k):clean_record(v) for k,v in value.items()}
    if isinstance(value,list): return [clean_record(v) for v in value]
    if pd.isna(value): return None
    if hasattr(value,'isoformat'): return value.isoformat()
    if hasattr(value,'item'): return value.item()
    return value


def snapshot_dict(row: pd.Series) -> dict[str, Any]:
    return clean_record({k:v for k,v in row.to_dict().items() if k not in OUTCOME_SIDE and k not in IDENTIFIERS and k != 'snapshot_data_is_synthetic'})


def eligible_outcome(bundle: DataBundle, row: pd.Series) -> dict[str, Any]:
    result={'label_30d':None,'label_90d':None,'label_observed_30d':bool(row.label_observed_30d),'label_observed_90d':bool(row.label_observed_90d),'outcome_source':'monthly_snapshots.csv','retrospective_only':True}
    if int(row.label_observed_30d)==1: result['label_30d']=int(row.churn_within_30d)
    if int(row.label_observed_90d)==1 and not pd.isna(row.churn_within_90d): result['label_90d']=int(row.churn_within_90d)
    # Final outcome file contains synthetic scenario/reason, which are deliberately not returned to assessment/LLM.
    return result


def evaluate_horizon(snapshots: pd.DataFrame, horizon: str) -> dict[str, Any]:
    label=f'churn_within_{horizon}'; flag=f'label_observed_{horizon}'
    eligible=snapshots[(snapshots[flag]==1) & snapshots[label].notna()]
    if eligible.empty: return {'status':'insufficient_eligible_labels','eligible_snapshots':0,'metrics':None}
    # Vectorized rule calculation keeps startup/evaluation responsive on the full snapshot history.
    points=pd.Series(0,index=snapshots.index,dtype='int64')
    for feature,condition,weight,_ in RULES:
        values=pd.to_numeric(snapshots[feature],errors='coerce')
        points=points+condition(values).fillna(False).astype('int64')*weight
    short=(pd.to_numeric(snapshots.tenure_months,errors='coerce')<12)&(pd.to_numeric(snapshots.active_products_count,errors='coerce')<=1)
    points=points+short.fillna(False).astype('int64')
    categories=pd.Series('Low',index=snapshots.index,dtype='object')
    categories.loc[points.between(3,5)]='Medium'; categories.loc[points>=6]='High'
    predicted=categories.loc[eligible.index].isin({'Medium','High'})
    actual=eligible[label].astype(int)==1
    tp=int((predicted&actual).sum()); fp=int((predicted&~actual).sum())
    tn=int((~predicted&~actual).sum()); fn=int((~predicted&actual).sum())
    precision=tp/(tp+fp) if tp+fp else 0.0; recall=tp/(tp+fn) if tp+fn else 0.0
    return {'status':'available','evaluation_type':'synthetic_retrospective_snapshot_level','horizon':horizon,'eligible_snapshots':len(eligible),'unique_customers':int(eligible.customer_id.nunique()),'positive_outcomes':int(eligible[label].sum()),'risk_distribution':{k:int((categories.loc[eligible.index]==k).sum()) for k in ('Low','Medium','High')},'alert_rule':'Medium or High risk is an alert; Low is no alert.','confusion_matrix':{'true_positive':tp,'false_positive':fp,'true_negative':tn,'false_negative':fn},'precision':precision,'recall':recall,'f1':(2*precision*recall/(precision+recall) if precision+recall else 0.0),'limitations':['Synthetic retrospective results only.','Snapshots from the same customer are repeated and not independent observations.','Rule thresholds are heuristic, not fitted or calibrated; no probability metrics are reported.']}


def dashboard(bundle: DataBundle) -> dict[str, Any]:
    latest=bundle.snapshots.sort_values('snapshot_date').groupby('customer_id',sort=False).tail(1).copy()
    latest['risk_category']=latest.apply(lambda r:assess(r.to_dict())['risk_category'],axis=1)
    risk_counts={c:int((latest.risk_category==c).sum()) for c in ('Low','Medium','High')}
    merged=bundle.outcomes[['customer_id','churned_during_followup']].merge(bundle.customers[['customer_id','customer_segment']],on='customer_id')
    segment_rates=merged.groupby('customer_segment').churned_during_followup.agg(['count','sum','mean']).reset_index()
    seg=[{'customer_segment':r.customer_segment,'customers':int(r['count']),'historical_churned':int(r['sum']),'historical_churn_rate':float(r['mean'])} for _,r in segment_rates.iterrows()]
    eval30=evaluate_horizon(bundle.snapshots,'30d'); eval90=evaluate_horizon(bundle.snapshots,'90d')
    eligible=bundle.snapshots[bundle.snapshots.label_observed_30d==1]
    factors=[]
    for f in ['transaction_count_change_3m_pct','balance_change_3m_pct','failed_transaction_rate_pct','unresolved_tickets','missed_salary_inflow_30d','external_transfer_count_change_3m_pct']:
        churn=eligible.loc[eligible.churn_within_30d==1,f].dropna(); retain=eligible.loc[eligible.churn_within_30d==0,f].dropna()
        factors.append({'feature':f,'churn_mean':float(churn.mean()) if len(churn) else None,'retained_mean':float(retain.mean()) if len(retain) else None,'churn_sample_size':len(churn),'retained_sample_size':len(retain),'interpretation':'Descriptive association in synthetic observed labels; not causal.'})
    trend=eligible.groupby(eligible.snapshot_date.dt.strftime('%Y-%m')).churn_within_30d.agg(['count','sum','mean']).reset_index()
    return {'data_notice':SYNTHETIC_NOTICE,'total_customers':int(bundle.customers.customer_id.nunique()),'historical_churn_count':int(bundle.outcomes.churned_during_followup.sum()),'historical_churn_rate':float(bundle.outcomes.churned_during_followup.mean()),'risk_distribution':risk_counts,'risk_distribution_chart':[{'category':k,'count':v} for k,v in risk_counts.items()],'churn_rate_by_segment':seg,'key_churn_associated_factors':factors,'churn_within_30d_trend':[{'snapshot_month':r.snapshot_date,'eligible_snapshots':int(r['count']),'churned':int(r['sum']),'rate':float(r['mean'])} for _,r in trend.iterrows()],'retrospective_evaluation':{'30d':eval30,'90d':eval90},'data_quality':{'profile_rows':int(len(bundle.customers)),'snapshot_rows':int(len(bundle.snapshots)),'outcome_rows':int(len(bundle.outcomes)),'duplicate_customer_date_pairs':int(bundle.snapshots.duplicated(['customer_id','snapshot_date']).sum()),'missing_values_by_table':{'customers':{str(k):int(v) for k,v in bundle.customers.isna().sum().items() if int(v)>0},'monthly_snapshots':{str(k):int(v) for k,v in bundle.snapshots.isna().sum().items() if int(v)>0},'churn_outcomes':{str(k):int(v) for k,v in bundle.outcomes.isna().sum().items() if int(v)>0}}},'recent_analysis_activity':[]}


def segment_comparison(bundle: DataBundle, segment: str) -> dict[str, Any]:
    group=bundle.customers[bundle.customers.customer_segment==segment].customer_id
    rows=bundle.outcomes[bundle.outcomes.customer_id.isin(group)]
    all_rate=float(bundle.outcomes.churned_during_followup.mean())
    seg_rate=float(rows.churned_during_followup.mean()) if not rows.empty else None
    return {'customer_segment':segment,'segment_historical_churn_rate':seg_rate,'overall_historical_churn_rate':all_rate,'customers_in_segment':int(len(rows)),'interpretation':'Historical synthetic association only; not causal.'}


class Recommendation(BaseModel):
    action: str = Field(min_length=4,max_length=500)
    rationale: str = Field(min_length=4,max_length=500)
    priority: str
    suggested_owner: str = Field(min_length=2,max_length=80)
    success_indicator: str = Field(min_length=2,max_length=500)

class LLMAnswer(BaseModel):
    executive_summary: str = Field(min_length=8,max_length=1800)
    customer_insights: list[str] = Field(min_length=1,max_length=8)
    retention_recommendations: list[Recommendation] = Field(min_length=1,max_length=8)
    limitations: list[str] = Field(min_length=1,max_length=8)

    @classmethod
    def validate_response(cls, value: Any, factor_count: int) -> 'LLMAnswer':
        # Groq's JSON mode guarantees valid JSON, not that every field follows
        # the requested type. GPT-OSS sometimes returns a bullet-form string
        # for customer_insights; normalize that harmless representation before
        # applying the response schema.
        if isinstance(value, dict) and isinstance(value.get('customer_insights'), str):
            raw = value['customer_insights']
            insights = [line.strip().lstrip('-*• ').strip() for line in raw.splitlines()]
            value = {**value, 'customer_insights': [line for line in insights if line]}
        result=cls.model_validate(value)
        if factor_count >= 2 and len(result.retention_recommendations)<3:
            raise ValueError('At least three recommendations are required when multiple indicators are present')
        if any(x.priority.lower() not in {'high','medium','low'} for x in result.retention_recommendations):
            raise ValueError('Invalid recommendation priority')
        return result


def groq_analysis(*, profile: dict[str,Any], snapshot: dict[str,Any], assessment: dict[str,Any], segment: dict[str,Any], request_id: str) -> dict[str,Any]:
    key=os.getenv('GROQ_API_KEY','').strip(); model=os.getenv('GROQ_MODEL','openai/gpt-oss-120b').strip()
    meta={'provider':'groq','model':model,'status':'unavailable','latency_ms':None,'token_usage':None,'request_id':request_id,'error_category':None}
    if not key: meta['error_category']='missing_credentials'; return {'metadata':meta,'answer':None}
    safe_profile={k:v for k,v in profile.items() if k not in {'customer_id','age','monthly_income_sar'}}
    safe={'customer_profile':safe_profile,'current_snapshot':snapshot,'rule_assessment':assessment,'segment_comparison':segment,'data_notice':SYNTHETIC_NOTICE}
    sysmsg=('You explain only the supplied synthetic customer profile, current snapshot, rule assessment and segment statistics. '
      'Do not calculate/claim churn probabilities, invent facts, imply causation, or use future outcome labels. '
      'Return JSON keys executive_summary, customer_insights, retention_recommendations, limitations. '
      'Each recommendation must have action, rationale, priority (high/medium/low), suggested_owner, success_indicator. '
      'Provide at least three evidence-linked recommendations when multiple risk factors are supplied; otherwise only supported actions.')
    started=time.perf_counter()
    try:
        response=httpx.post('https://api.groq.com/openai/v1/chat/completions',headers={'Authorization':'Bearer '+key},json={'model':model,'messages':[{'role':'system','content':sysmsg},{'role':'user','content':json.dumps(safe,allow_nan=False,default=lambda x:x.item() if hasattr(x,'item') else str(x))}],'temperature':0.2,'response_format':{'type':'json_object'}},timeout=float(os.getenv('GROQ_TIMEOUT_SECONDS','20')))
        meta['latency_ms']=round((time.perf_counter()-started)*1000,3)
        if response.status_code in (401,403): meta['error_category']='invalid_credentials'; return {'metadata':meta,'answer':None}
        if response.status_code==404: meta['error_category']='model_unavailable'; return {'metadata':meta,'answer':None}
        if response.status_code==429: meta['error_category']='rate_limited'; return {'metadata':meta,'answer':None}
        response.raise_for_status()
        body=response.json(); content=body['choices'][0]['message']['content']; parsed=json.loads(content)
        answer=LLMAnswer.validate_response(parsed,len(assessment['risk_factors']))
        usage=body.get('usage') if isinstance(body.get('usage'),dict) else None
        if usage:
            meta['token_usage']={k:usage[k] for k in ('prompt_tokens','completion_tokens','total_tokens') if isinstance(usage.get(k),int)}
            details=usage.get('completion_tokens_details') or {}
            if isinstance(details.get('reasoning_tokens'),int): meta['token_usage']['reasoning_tokens']=details['reasoning_tokens']
        meta['status']='available'
        return {'metadata':meta,'answer':answer.model_dump()}
    except httpx.TimeoutException: category='timeout'
    except httpx.HTTPStatusError as exc: category='provider_unavailable' if exc.response.status_code>=500 else 'provider_error'
    except (json.JSONDecodeError,KeyError,TypeError,ValidationError,ValueError): category='malformed_response'
    except httpx.HTTPError: category='network_error'
    except Exception: category='provider_error'
    meta['latency_ms']=round((time.perf_counter()-started)*1000,3); meta['error_category']=category
    logger.warning('groq_analysis_failed request_id=%s category=%s',request_id,category)
    return {'metadata':meta,'answer':None}
