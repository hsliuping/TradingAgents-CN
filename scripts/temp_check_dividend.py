"""临时脚本：检查 stock_financial_data 中 dividend_yield 字段的数据情况"""
import pymongo

uri = 'mongodb://admin:tradingagents123@127.0.0.1:27017/tradingagents?authSource=admin'
client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=5000, socketTimeoutMS=10000)
col = client['tradingagents']['stock_financial_data']

count_with = col.count_documents({'dividend_yield': {'$ne': None}})
count_total = col.estimated_document_count()
print(f'总记录数: {count_total}')
print(f'有 dividend_yield 的记录数: {count_with}')

if count_with > 0:
    print('\n示例数据:')
    for doc in col.find({'dividend_yield': {'$ne': None}},
                        {'code': 1, 'report_period': 1, 'dividend_yield': 1, '_id': 0}).limit(5):
        print(' ', doc)
else:
    print('\n=> 数据库中所有记录的 dividend_yield 均为 None，该字段暂无数据')
    # 检查一下 raw_data 里有没有
    sample = col.find_one({'raw_data': {'$ne': None}}, {'raw_data': 1, '_id': 0})
    if sample and isinstance(sample.get('raw_data'), dict):
        raw_keys = list(sample['raw_data'].keys())
        div_keys = [k for k in raw_keys if 'div' in k.lower() or 'yield' in k.lower()]
        print(f'raw_data 中含 div/yield 的字段: {div_keys}')

