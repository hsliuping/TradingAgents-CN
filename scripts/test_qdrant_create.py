"""测试直接创建 1024 维 Qdrant collection。"""
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qdrant_client import QdrantClient, models

test_path = os.path.abspath("./data/qdrant/test_dim")
if os.path.exists(test_path):
    shutil.rmtree(test_path)

client = QdrantClient(path=test_path)
client.create_collection(
    collection_name="test_1024",
    vectors_config=models.VectorParams(size=1024, distance=models.Distance.COSINE),
)
info = client.get_collection("test_1024")
print(f"Created test_1024: vector_size={info.config.params.vectors.size}")
client.close()

# 现在用 mem0 的方式创建
from mem0.vector_stores.qdrant import Qdrant

q = Qdrant(
    collection_name="mem0_test_1024",
    embedding_model_dims=1024,
    path=test_path,
    on_disk=True,
)
info2 = q.client.get_collection("mem0_test_1024")
print(f"Created mem0_test_1024: vector_size={info2.config.params.vectors.size}")
q.client.close()
