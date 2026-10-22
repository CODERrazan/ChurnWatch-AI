from __future__ import annotations
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from app.banking import DATA_FILES, DATA_DIR, dashboard, load_bundle

def main():
    missing=[f for f in DATA_FILES if not (DATA_DIR/f).is_file()]
    if missing: raise SystemExit('Missing supplied package files: '+', '.join(missing))
    b=load_bundle()
    quality={'profiles':len(b.customers),'snapshots':len(b.snapshots),'outcomes':len(b.outcomes),'snapshot_missing_cells':int(b.snapshots.isna().sum().sum()),'duplicate_snapshot_customer_dates':int(b.snapshots.duplicated(['customer_id','snapshot_date']).sum()),'observed_30d':int(b.snapshots.label_observed_30d.sum()),'observed_90d':int(b.snapshots.label_observed_90d.sum())}
    d=dashboard(b)
    print(json.dumps({'data_quality':quality,'retrospective_evaluation':d['retrospective_evaluation']},indent=2))
if __name__=='__main__':main()
