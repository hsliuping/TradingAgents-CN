"""
Memory 模块 v2.0 / v3.0

v2.0: 多后端向量记忆系统（Qdrant / ChromaDB）— 用于 Agent 历史经验
v3.0: mem0 统一记忆层 — 跨子系统的智能记忆存储与召回
"""

from .memory_manager import MemoryManager, AgentMemory, Mem0AgentMemory, VectorStoreManager
from .chromadb_config import get_optimal_chromadb_client, is_windows_11

# v3.0 统一记忆层
from .models import MemoryItem, MemoryScope, StoreResult
from .service import MemoryService, get_memory_service

# 向后兼容：ChromaDBManager 已重命名为 VectorStoreManager
ChromaDBManager = VectorStoreManager

__all__ = [
    # v2.0
    'MemoryManager',
    'AgentMemory',
    'Mem0AgentMemory',
    'VectorStoreManager',
    'ChromaDBManager',
    'get_optimal_chromadb_client',
    'is_windows_11',
    # v3.0 mem0 统一记忆层
    'MemoryService',
    'get_memory_service',
    'MemoryItem',
    'MemoryScope',
    'StoreResult',
]

