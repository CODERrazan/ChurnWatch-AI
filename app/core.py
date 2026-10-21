from __future__ import annotations
import json, logging, os, time
from pathlib import Path
from typing import Any
import httpx, joblib, numpy as np, pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (roc_auc_score, average_precision_score, precision_score, recall_score, f1_score, confusion_matrix, accuracy_score)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / 'Data' / 'churnwatch_synthetic_banking_customers.csv'
ARTIFACT_PATH = ROOT / 'artifacts' / 'churn_model.joblib'
TARGET = 'churn_within_30d'
EXCLUDED = {'customer_id', 'snapshot_date', 'churn_reason_after_exit', TARGET}
SEED = 42
MODEL_VERSION = 'banking-logistic-v1'
logger = logging.getLogger(__name__)


def load_data(path: Path = DATA_PATH) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f'Banking dataset not found: {path}')
    data = pd.read_csv(path)
    required = {'customer_id', 'snapshot_date', TARGET, 'churn_reason_after_exit'}
    missing = required - set(data.columns)
    if missing:
        raise ValueError(f'Dataset is missing required columns: {sorted(missing)}')
    if data['customer_id'].duplicated().any():
        raise ValueError('Dataset contains duplicate customer_id values')
    if data[TARGET].isna().any() or not set(data[TARGET].unique()).issubset({0, 1}):
        raise ValueError('Target must contain only non-missing binary 0/1 values')
    return data


def feature_columns(data: pd.DataFrame) -> list[str]:
    return [c for c in data.columns if c not in EXCLUDED]


def build_pipeline(features: pd.DataFrame) -> Pipeline:
    cats = features.select_dtypes(include=['object', 'string', 'category']).columns.tolist()
    nums = [c for c in features.columns if c not in cats]
    prep = ColumnTransformer([
        ('numeric', Pipeline([('impute', SimpleImputer(strategy='median')), ('scale', StandardScaler())]), nums),
        ('categorical', Pipeline([('impute', SimpleImputer(strategy='most_frequent')), ('encode', OneHotEncoder(handle_unknown='ignore'))]), cats),
    ])
    return Pipeline([('prep', prep), ('classifier', LogisticRegression(max_iter=2000, class_weight='balanced', random_state=SEED))])


def build_model(data: pd.DataFrame) -> tuple[Pipeline, dict[str, Any]]:
    cols = feature_columns(data)
    x = data[cols].copy()
    y = data[TARGET].astype(int)
    if y.nunique() != 2 or y.value_counts().min() < 2:
        raise ValueError('Both target classes need at least two examples')
    x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=.2, random_state=SEED, stratify=y)
    model = build_pipeline(x_train)
    model.fit(x_train, y_train)
    probs = model.predict_proba(x_test)[:, 1]
    pred = (probs >= .5).astype(int)
    metrics = {'roc_auc': float(roc_auc_score(y_test, probs)), 'pr_auc': float(average_precision_score(y_test, probs)),
      'precision': float(precision_score(y_test, pred, zero_division=0)), 'recall': float(recall_score(y_test, pred, zero_division=0)),
      'f1': float(f1_score(y_test, pred, zero_division=0)), 'accuracy': float(accuracy_score(y_test, pred)),
      'confusion_matrix': confusion_matrix(y_test, pred).tolist(), 'test_rows': int(len(y_test)),
      'train_rows': int(len(y_train)), 'seed': SEED, 'split': 'stratified 80/20', 'threshold': .5}
    # Refit the deployable pipeline on all available development data only after held-out evaluation.
    model.fit(x, y)
    return model, metrics


def train_and_save(path: Path = DATA_PATH, artifact: Path = ARTIFACT_PATH) -> dict[str, Any]:
    data = load_data(path)
    model, metrics = build_model(data)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({'model': model, 'features': feature_columns(data), 'metrics': metrics,
      'rows': len(data), 'target_distribution': data[TARGET].value_counts().sort_index().to_dict(),
      'seed': SEED, 'version': MODEL_VERSION, 'trained_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}, artifact)
    return metrics


def analytics(data: pd.DataFrame) -> dict[str, Any]:
    y = data[TARGET].astype(int)
    numeric = data[feature_columns(data)].select_dtypes(include='number')
    return {'dataset': {'customers': int(len(data)), 'churned': int(y.sum()), 'retained': int(len(y)-y.sum()),
       'churn_rate': float(y.mean()), 'target_distribution': {str(k): int(v) for k,v in y.value_counts().sort_index().items()}},
       'key_statistics': {c: {'mean': float(numeric[c].mean()), 'median': float(numeric[c].median())} for c in numeric.columns}}


def risk_category(probability: float) -> str:
    # Fixed display thresholds: high >= .65, low < .35; middle values are medium.
    if probability >= .65: return 'High'
    if probability >= .35: return 'Medium'
    return 'Low'


def explain(model: Pipeline, row: pd.DataFrame, features: list[str], top_n: int = 3) -> dict[str, Any]:
    transformed = model.named_steps['prep'].transform(row)
    vals = transformed.toarray()[0] if hasattr(transformed, 'toarray') else np.asarray(transformed)[0]
    names = model.named_steps['prep'].get_feature_names_out()
    coef = model.named_steps['classifier'].coef_[0]
    contributions = sorted(zip(names, vals * coef), key=lambda pair: pair[1], reverse=True)
    signals = []
    for name, value in contributions:
        if value <= 0 or len(signals) >= top_n: break
        signals.append({'signal': str(name).replace('numeric__','').replace('categorical__',''), 'direction': 'increases estimated risk', 'contribution': round(float(value), 4)})
    if not signals:
        signals = [{'signal': 'No strong positive feature contribution identified', 'direction': 'neutral', 'contribution': 0.0}]
    explanation = 'The model associates this profile with elevated risk based on the listed feature contributions. These are statistical associations, not causes or proof of future churn.'
    actions = ['Review recent service or transaction friction with the customer.', 'Offer relevant support or product guidance and measure outcomes against a holdout group.']
    return {'risk_signals': signals, 'explanation': explanation, 'recommended_actions': actions}


def score(model: Pipeline, row: pd.DataFrame, features: list[str]) -> dict[str, Any]:
    started = time.perf_counter()
    p = float(model.predict_proba(row[features])[:, 1][0])
    out = {'churn_probability': p, 'risk_category': risk_category(p)}
    out.update(explain(model, row[features], features))
    out['model_latency_ms'] = round((time.perf_counter()-started)*1000, 3)
    return out


def llm_status() -> dict[str, Any]:
    return {'configured': bool(os.getenv('GROQ_API_KEY')), 'model': os.getenv('GROQ_MODEL', 'openai/gpt-oss-120b')}


def groq_explanation(prediction: dict[str, Any], customer: dict[str, Any]) -> dict[str, Any]:
    key = os.getenv('GROQ_API_KEY', '').strip()
    model = os.getenv('GROQ_MODEL', 'openai/gpt-oss-120b').strip()
    if not key:
        return {'status': 'unavailable', 'error_category': 'missing_credentials', 'explanation': 'Groq explanation unavailable because GROQ_API_KEY is not configured.'}
    prompt_data = {'prediction': {k:v for k,v in prediction.items() if k != 'model_latency_ms'}, 'customer_features': customer}
    try:
        response = httpx.post('https://api.groq.com/openai/v1/chat/completions', headers={'Authorization': f'Bearer {key}'},
            json={'model': model, 'messages':[{'role':'system','content':'Explain this model prediction carefully. Treat feature associations as correlations, never causes. Do not repeat personal identifiers. Return concise, practical retention recommendations as JSON with explanation and recommendations.'},{'role':'user','content':json.dumps(prompt_data, allow_nan=False, default=lambda value: value.item() if hasattr(value, 'item') else str(value))}], 'temperature':0.2, 'response_format':{'type':'json_object'}}, timeout=20.0)
        if response.status_code in (401,403): return {'status':'unavailable','error_category':'invalid_credentials'}
        if response.status_code == 404: return {'status':'unavailable','error_category':'model_unavailable'}
        if response.status_code == 429: return {'status':'unavailable','error_category':'rate_limited'}
        response.raise_for_status()
        body = response.json()
        content = body['choices'][0]['message']['content']
        parsed = json.loads(content)
        if not isinstance(parsed.get('explanation'), str) or not isinstance(parsed.get('recommendations'), list): raise ValueError('malformed')
        usage = body.get('usage') if isinstance(body.get('usage'), dict) else None
        return {'status':'available','model':model,'explanation':parsed['explanation'][:1500], 'recommended_actions':[str(x)[:300] for x in parsed['recommendations'][:6]], 'token_usage':usage}
    except httpx.TimeoutException: category='timeout'
    except httpx.HTTPStatusError as exc: category='provider_error' if exc.response.status_code < 500 else 'provider_unavailable'
    except (ValueError, KeyError, TypeError): category='malformed_response'
    except httpx.HTTPError: category='network_error'
    except Exception: category='provider_error'
    logger.warning('groq_request_failed category=%s', category)
    return {'status':'unavailable','error_category':category}
