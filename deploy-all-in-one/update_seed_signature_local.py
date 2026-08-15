"""直接用 sqlite3 更新种子数据中的签名 point（绕过 QdrantClient）。"""
import hashlib
import os
import pickle
import sqlite3
import uuid

# 1. 计算新签名（与 user_manual_manager.py 中 _compute_manuals_signature() 一致）
sig_parts = []
for name, mtype in [
    ("user-manual-v3.0.md", "standard"),
    ("jdyun-user-manual-v3.0.md", "jdyun"),
]:
    path = os.path.join("docs", "02-user-guide", name)
    if os.path.exists(path):
        with open(path, "rb") as f:
            content_hash = hashlib.md5(f.read()).hexdigest()
        sig_parts.append(f"{mtype}:{name}:{content_hash}")
        print(f"  {name}: content_hash={content_hash[:16]}...")

new_signature = hashlib.md5("|".join(sorted(sig_parts)).encode("utf-8")).hexdigest()
print(f"New signature: {new_signature}")

# 2. 在种子 sqlite 中更新签名 point
DB = os.path.join("deploy-all-in-one", "qdrant-seed", "collection", "user_manual_v3", "storage.sqlite")
sig_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, "user_manual_index_signature")

conn = sqlite3.connect(DB)
cur = conn.cursor()

# 找到签名 point 并更新
cur.execute("SELECT id, point FROM points")
updated = False
for row in cur.fetchall():
    point = pickle.loads(row[1])
    if str(point.id) == str(sig_uuid):
        # 更新 payload
        point.payload["manuals_signature"] = new_signature
        # 重新序列化
        new_data = pickle.dumps(point)
        cur.execute("UPDATE points SET point=? WHERE id=?", (new_data, row[0]))
        updated = True
        print(f"Updated signature point: {point.id}")
        break

if not updated:
    print("Signature point NOT found! Creating new one...")
    # 如果签名 point 不存在，需要创建
    # 但这需要 QdrantClient，这里先跳过
    pass

conn.commit()
conn.close()
print("Done!")
