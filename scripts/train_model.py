from __future__ import annotations
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from app import core
from app.core import DATA_PATH, ARTIFACT_PATH, load_data, train_and_save

def main():
    data=load_data(DATA_PATH)
    print('Rows:',len(data),'Columns:',len(data.columns))
    print('Missing cells:',int(data.isna().sum().sum()))
    print('Duplicate rows:',int(data.duplicated().sum()))
    print('Duplicate customer IDs:',int(data.customer_id.duplicated().sum()))
    print('Target counts:',data.churn_within_30d.value_counts().sort_index().to_dict())
    print('Data types:',data.dtypes.astype(str).to_dict())
    print('Numeric feature distributions (min/median/max):',data[core.feature_columns(data)].select_dtypes(include='number').describe().loc[['min','50%','max']].round(2).to_dict())
    metrics=train_and_save()
    print('Saved model:',ARTIFACT_PATH)
    print('Held-out evaluation:',metrics)
if __name__=='__main__': main()
