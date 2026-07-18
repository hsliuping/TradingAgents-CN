import sys; sys.path.insert(0,'.')
from pymongo import MongoClient
from app.core.config import settings
c=MongoClient(settings.MONGO_URI)
db=c[settings.MONGO_DB]

# Check the document without raw_data
doc = db.stock_financial_data.find_one(
    {'$or': [{'symbol': '000001'}, {'code': '000001'}], 'raw_data': {'$exists': False}},
    sort=[('updated_at', -1)]
)
if doc:
    print(f'无 raw_data 文档的字段: {list(doc.keys())}')
    # Check root-level fields
    for k in ['balance_sheet', 'income_statement', 'cash_flow', 'main_indicators', 'financial_data']:
        v = doc.get(k)
        if v is not None:
            print(f'  {k}: exist, type={type(v).__name__}, bool={bool(v)}')
        else:
            print(f'  {k}: None')
c.close()
