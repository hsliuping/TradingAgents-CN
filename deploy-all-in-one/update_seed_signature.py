"""构建时更新种子数据中的用户手册签名。

签名算法与 core/knowledge/user_manual_manager.py 中 _compute_manuals_signature() 一致：
基于文件名 + 文件内容 hash，不依赖路径和 mtime，
确保不同部署环境（开发/Docker/京东云）产生相同签名。
"""
import hashlib
import os
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

MANUALS_DIR = "/app/docs/02-user-guide"
SEED_DIR = "/app/qdrant-seed"
COLLECTION = "user_manual_v3"
EMBEDDING_DIM = 1024

sig_parts = []
for name, mtype in [
    ("user-manual-v3.0.md", "standard"),
    ("jdyun-user-manual-v3.0.md", "jdyun"),
]:
    path = os.path.join(MANUALS_DIR, name)
    if os.path.exists(path):
        with open(path, "rb") as f:
            content_hash = hashlib.md5(f.read()).hexdigest()
        sig_parts.append(f"{mtype}:{name}:{content_hash}")

signature = hashlib.md5("|".join(sig_parts).encode("utf-8")).hexdigest()

client = QdrantClient(path=SEED_DIR)
sig_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "user_manual_index_signature"))
client.upsert(
    collection_name=COLLECTION,
    points=[
        PointStruct(
            id=sig_id,
            vector=[0.0] * EMBEDDING_DIM,
            payload={
                "doc_id": "__INDEX_SIGNATURE__",
                "title": "__INDEX_SIGNATURE__",
                "manual_type": "meta",
                "manuals_signature": signature,
                "document": "__INDEX_SIGNATURE__",
            },
        )
    ],
)
client.close()
print(f"Seed signature updated: {signature[:8]}...")
