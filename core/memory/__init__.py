"""
Memory 模块 v2.0

提供基于 ChromaDB 的向量记忆系统
"""

from .memory_manager import MemoryManager, AgentMemory, ChromaDBManager
from .chromadb_config import get_optimal_chromadb_client, is_windows_11

__all__ = [
    'MemoryManager',
    'AgentMemory',
    'ChromaDBManager',
    'get_optimal_chromadb_client',
    'is_windows_11',
]

