import os
from pathlib import Path
from dotenv import dotenv_values, load_dotenv
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env', override=False)
# Backward-compatible local IDE config: never print or rewrite this secret.
local_values = dotenv_values(ROOT / '.vscode' / '.env')
# Root .env / process environment take precedence; IDE config is a local fallback.
if not os.getenv('DATABASE_URL') and local_values.get('DATABASE_URL'):
    os.environ['DATABASE_URL'] = local_values['DATABASE_URL']
if not os.getenv('GROQ_API_KEY'):
    local_key = local_values.get('GROQ_API_KEY') or local_values.get('API-KEY')
    if local_key:
        os.environ['GROQ_API_KEY'] = local_key
        os.environ.setdefault('GROQ_MODEL', 'openai/gpt-oss-120b')
