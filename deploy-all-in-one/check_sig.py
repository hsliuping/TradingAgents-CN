import sqlite3, pickle, uuid

DB = '/app/data/qdrant/collection/user_manual_v3/storage.sqlite'
sig_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, 'user_manual_index_signature')

# 用只读模式打开（不锁文件）
conn = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM points')
print(f'Total points: {cur.fetchone()[0]}')

cur.execute('SELECT id, point FROM points')
found = False
for row in cur.fetchall():
    point = pickle.loads(row[1])
    if str(point.id) == str(sig_uuid):
        sig = (point.payload or {}).get('manuals_signature', 'NOT SET')
        print(f'Signature point found! Value: {sig}')
        found = True
        break
if not found:
    print('Signature point NOT found')
    cur.execute('SELECT id, point FROM points LIMIT 3')
    for row in cur.fetchall():
        point = pickle.loads(row[1])
        print(f'  ID: {point.id}, title: {(point.payload or {}).get("title", "")}')
conn.close()
