"""
检查当前使用的向量数据库后端

用法：
    python scripts/check_vector_store_backend.py
"""

import os
import sys

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

def check_vector_store_backend():
    """检查向量数据库后端配置"""
    
    print("=" * 80)
    print("🔍 向量数据库后端检查")
    print("=" * 80)
    print()
    
    # 1. 检查环境变量
    backend = os.getenv("VECTOR_STORE_BACKEND", "qdrant").lower()
    print(f"📋 环境变量 VECTOR_STORE_BACKEND: {backend}")
    
    if backend == "qdrant":
        print("   ✅ 配置为 Qdrant（推荐，线程安全）")
        qdrant_dir = os.getenv("QDRANT_DATA_DIR", "./data/qdrant")
        print(f"   📁 Qdrant 数据目录: {qdrant_dir}")
    elif backend == "chromadb":
        print("   ⚠️  配置为 ChromaDB（有线程安全问题，不推荐）")
    else:
        print(f"   ❌ 未知后端: {backend}（将使用默认 Qdrant）")
    
    print()
    
    # 2. 检查依赖包是否安装
    print("📦 依赖包检查:")
    print()
    
    # 检查 Qdrant
    try:
        import qdrant_client
        version = getattr(qdrant_client, '__version__', 'unknown')
        print(f"   ✅ qdrant-client 已安装 (版本: {version})")
    except ImportError:
        print(f"   ❌ qdrant-client 未安装")
        if backend == "qdrant":
            print(f"      ⚠️  当前配置需要 Qdrant，请运行: pip install qdrant-client>=1.7.0")
    
    # 检查 ChromaDB
    try:
        import chromadb
        version = getattr(chromadb, '__version__', 'unknown')
        print(f"   ✅ chromadb 已安装 (版本: {version})")
    except ImportError:
        print(f"   ❌ chromadb 未安装")
        if backend == "chromadb":
            print(f"      ⚠️  当前配置需要 ChromaDB，请运行: pip install chromadb")
    
    print()
    
    # 3. 尝试初始化向量数据库管理器
    print("🔧 初始化测试:")
    print()
    
    try:
        from core.memory.memory_manager import VectorStoreManager
        
        manager = VectorStoreManager()
        actual_backend = manager.backend
        
        print(f"   ✅ VectorStoreManager 初始化成功")
        print(f"   📊 实际使用的后端: {actual_backend}")
        
        if actual_backend == "qdrant":
            print(f"   ✅ 正在使用 Qdrant（线程安全）")
        elif actual_backend == "chromadb":
            print(f"   ⚠️  正在使用 ChromaDB（有线程安全问题）")
        
        # 检查适配器类型
        adapter_class = manager._adapter.__class__.__name__
        print(f"   🔌 适配器类型: {adapter_class}")
        
    except Exception as e:
        print(f"   ❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 80)
    print("✅ 检查完成")
    print("=" * 80)
    print()
    
    # 4. 给出建议
    if backend == "chromadb":
        print("💡 建议:")
        print("   为了避免多线程崩溃问题，建议切换到 Qdrant：")
        print("   1. 在 .env 文件中设置: VECTOR_STORE_BACKEND=qdrant")
        print("   2. 安装依赖: pip install qdrant-client>=1.7.0")
        print("   3. 重启应用")
        print()


if __name__ == "__main__":
    check_vector_store_backend()

