from __future__ import annotations
import json, os
from typing import Any


def database_url() -> str:
    return os.getenv('DATABASE_URL','').strip()


def connect():
    url=database_url()
    if not url:
        raise RuntimeError('DATABASE_URL is not configured')
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError('Install psycopg[binary] to enable Supabase Monitoring') from exc
    return psycopg.connect(url,connect_timeout=4)


def record_event(event: dict[str,Any]) -> str:
    token=event.get('token_usage') or {}
    outcome=event.get('actual_outcomes') or []
    answer=event.get('llm_response')
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute('''INSERT INTO monitoring_requests
              (request_id,created_at,provider,model,request_status,assessment_type,risk_category,customer_id,snapshot_date,evaluation_status)
              VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING prediction_id''',
              (event['request_id'],event['timestamp'],event['provider'],event['model'],event['request_status'],event['assessment_type'],event['risk_category'],event.get('customer_id'),event.get('snapshot_date'),event.get('evaluation_status','not_evaluated')))
            prediction_id=cur.fetchone()[0]
            cur.execute('''INSERT INTO llm_responses(prediction_id,executive_summary,response_json,response_status)
              VALUES (%s,%s,%s::jsonb,%s)''',(prediction_id,(answer or {}).get('executive_summary'),json.dumps(answer) if answer is not None else None,event['request_status']))
            cur.execute('''INSERT INTO llm_request_metrics(prediction_id,latency_ms,prompt_tokens,completion_tokens,reasoning_tokens,total_tokens)
              VALUES (%s,%s,%s,%s,%s,%s)''',(prediction_id,event.get('latency_ms'),token.get('prompt_tokens'),token.get('completion_tokens'),token.get('reasoning_tokens'),token.get('total_tokens')))
            if event.get('error_category'):
                cur.execute('INSERT INTO monitoring_errors(prediction_id,error_category,safe_detail) VALUES (%s,%s,%s)',(prediction_id,event['error_category'],event.get('safe_error_detail')))
            for result in outcome:
                cur.execute('''INSERT INTO churn_evaluations(prediction_id,horizon_days,label_eligible,actual_churn,rule_alert_match,llm_correctness_status)
                  VALUES (%s,%s,%s,%s,%s,'not_evaluated')''',(prediction_id,result['horizon_days'],result['label_eligible'],result.get('actual_churn'),result.get('rule_alert_match')))
    return str(prediction_id)


def recent_events(limit:int=100,status:str|None=None)->list[dict[str,Any]]:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute('''SELECT r.prediction_id,r.request_id,r.created_at,r.provider,r.model,r.request_status,r.assessment_type,r.risk_category,r.customer_id,r.snapshot_date,r.evaluation_status,
                 m.latency_ms,m.prompt_tokens,m.completion_tokens,m.reasoning_tokens,m.total_tokens,l.executive_summary,l.response_status,
                 e.error_category,e.safe_detail,
                 c.horizon_days,c.label_eligible,c.actual_churn,c.rule_alert_match,c.llm_correctness_status
              FROM monitoring_requests r LEFT JOIN llm_request_metrics m USING(prediction_id)
              LEFT JOIN llm_responses l USING(prediction_id) LEFT JOIN monitoring_errors e USING(prediction_id)
              LEFT JOIN churn_evaluations c ON c.prediction_id=r.prediction_id AND c.horizon_days=30
              WHERE (%s::text IS NULL OR r.request_status=%s) ORDER BY r.created_at DESC LIMIT %s''',(status,status,limit))
            cols=[x.name for x in cur.description]
            return [dict(zip(cols,row)) for row in cur.fetchall()]


def summary()->dict[str,Any]:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute('''SELECT count(*)::int request_count,
               count(*) FILTER (WHERE request_status='available')::int success_count,
               count(*) FILTER (WHERE request_status='unavailable')::int failure_count,
               avg(latency_ms) mean_latency_ms,sum(prompt_tokens)::bigint prompt_tokens,
               sum(completion_tokens)::bigint completion_tokens,sum(total_tokens)::bigint total_tokens
               FROM monitoring_requests r LEFT JOIN llm_request_metrics m USING(prediction_id)''')
            names=[x.name for x in cur.description]; row=dict(zip(names,cur.fetchone()))
            cur.execute('SELECT error_category,count(*)::int count FROM monitoring_errors GROUP BY error_category')
            row['errors_by_category']={category:count for category,count in cur.fetchall()}
            return row
