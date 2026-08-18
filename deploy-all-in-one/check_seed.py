import sqlite3, pickle, uuid, json

DB = r'c:\TradingAgentsCN\deploy-all-in-one\qdrant-seed\collection\user_manual_v3\storage.sqlite'
sig_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, 'user_manual_index_signature')

conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM points')
print(f'Total points: {cur.fetchone()[0]}')

# 扫描所有 point，查找签名 point
cur.execute('SELECT id, point FROM points')
found = False
for row in cur.fetchall():
    try:
        point = pickle.loads(row[1])
        pid = point.id
        if str(pid) == str(sig_uuid):
            payload = point.payload or {}
            sig = payload.get('manuals_signature', 'NOT SET')
            print(f'Signature point found!')
            print(f'  ID: {pid}')
            print(f'  Signature: {sig}')
            print(f'  Title: {payload.get("title")}')
            found = True
            break
    except Exception as e:
        print(f'Error parsing point: {e}')

if not found:
    print('Signature point NOT found in seed data!')
    # 打印前5个point的ID
    cur.execute('SELECT id, point FROM points LIMIT 5')
    for row in cur.fetchall():
        try:
            point = pickle.loads(row[1])
            print(f'  Point ID: {point.id}, payload title: {(point.payload or {}).get("title", "")}')
        except:
            pass

conn.close()
