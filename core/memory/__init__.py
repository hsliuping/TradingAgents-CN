"""
Memory 模块 v2.0

提供多后端向量记忆系统（支持 Qdrant 和 ChromaDB）
"""

from .memory_manager import MemoryManager, AgentMemory, VectorStoreManager
from .chromadb_config import get_optimal_chromadb_client, is_windows_11

# 向后兼容：ChromaDBManager 已重命名为 VectorStoreManager
ChromaDBManager = VectorStoreManager

__all__ = [
    'MemoryManager',
    'AgentMemory',
    'VectorStoreManager',
    'ChromaDBManager',  # 向后兼容
    'get_optimal_chromadb_client',
    'is_windows_11',
]

