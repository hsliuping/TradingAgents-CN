"""检查 Qdrant collection 实际维度。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qdrant_client import QdrantClient

path = os.path.abspath("./data/qdrant/mem0")
client = QdrantClient(path=path)

collections = client.get_collections()
print("Collections:")
for col in collections.collections:
    info = client.get_collection(col.name)
    size = info.config.params.vectors.size
    print(f"  - {col.name}: vector_size={size}")
