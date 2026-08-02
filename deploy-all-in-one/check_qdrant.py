import sqlite3

conn = sqlite3.connect('/app/data/qdrant/collection/user_manual_v3/storage.sqlite')
cur = conn.cursor()
# 查看表结构
cur.execute("PRAGMA table_info(points)")
print("Columns:", [(r[1], r[2]) for r in cur.fetchall()])
# 查看前 3 行数据
cur.execute("SELECT * FROM points LIMIT 3")
for row in cur.fetchall():
    print("Row:", [str(v)[:80] for v in row])
conn.close()
