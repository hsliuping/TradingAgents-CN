"""
ChromaDB 诊断脚本

用于诊断和修复 ChromaDB 初始化问题
"""

import os
import sys
import shutil
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def diagnose_chromadb():
    """诊断 ChromaDB 问题"""
    print("=" * 80)
    print("ChromaDB 诊断工具")
    print("=" * 80)
    
    # 1. 检查 ChromaDB 版本
    print("\n1. 检查 ChromaDB 版本...")
    try:
        import chromadb
        print(f"   ✅ ChromaDB 版本: {chromadb.__version__}")
    except ImportError:
        print("   ❌ ChromaDB 未安装")
        print("   建议: pip install chromadb")
        return
    except Exception as e:
        print(f"   ⚠️ 检查版本失败: {e}")
    
    # 2. 检查数据库目录
    print("\n2. 检查数据库目录...")
    persist_dir = os.path.normpath(os.path.join(os.getcwd(), "data", "chromadb"))
    print(f"   目录路径: {persist_dir}")
    
    if os.path.exists(persist_dir):
        print(f"   ✅ 目录存在")
        # 检查目录大小
        try:
            total_size = sum(
                os.path.getsize(os.path.join(dirpath, filename))
                for dirpath, dirnames, filenames in os.walk(persist_dir)
                for filename in filenames
            )
            print(f"   目录大小: {total_size / 1024 / 1024:.2f} MB")
            
            # 列出文件
            files = []
            for root, dirs, filenames in os.walk(persist_dir):
                for filename in filenames:
                    files.append(os.path.join(root, filename))
            
            if files:
                print(f"   文件数量: {len(files)}")
                print(f"   前5个文件:")
                for f in files[:5]:
                    print(f"     - {os.path.relpath(f, persist_dir)}")
        except Exception as e:
            print(f"   ⚠️ 检查目录信息失败: {e}")
    else:
        print(f"   ℹ️ 目录不存在（首次使用）")
    
    # 3. 尝试初始化 ChromaDB
    print("\n3. 尝试初始化 ChromaDB...")
    
    # 尝试1: 持久化模式
    print("   尝试1: 持久化模式...")
    try:
        from chromadb.config import Settings
        settings = Settings(
            allow_reset=True,
            anonymized_telemetry=False,
            is_persistent=True,
            persist_directory=persist_dir
        )
        client = chromadb.Client(settings)
        print("   ✅ 持久化模式初始化成功")
        client.heartbeat()  # 测试连接
        print("   ✅ 连接测试成功")
        return True
    except Exception as e:
        error_msg = str(e)
        print(f"   ❌ 持久化模式失败: {error_msg}")
        
        # 检查是否是 Rust panic
        if "PanicException" in error_msg or "panicked" in error_msg:
            print("   ⚠️ 检测到 Rust panic 错误")
            print("   可能原因:")
            print("     1. 数据库文件损坏")
            print("     2. ChromaDB 版本不兼容")
            print("     3. Windows 路径问题")
    
    # 尝试2: 清理后重试
    print("\n   尝试2: 清理数据库目录后重试...")
    try:
        backup_dir = f"{persist_dir}.backup"
        if os.path.exists(persist_dir):
            if os.path.exists(backup_dir):
                shutil.rmtree(backup_dir)
            shutil.move(persist_dir, backup_dir)
            print(f"   ✅ 已备份到: {backup_dir}")
        
        os.makedirs(persist_dir, exist_ok=True)
        
        settings = Settings(
            allow_reset=True,
            anonymized_telemetry=False,
            is_persistent=True,
            persist_directory=persist_dir
        )
        client = chromadb.Client(settings)
        print("   ✅ 清理后初始化成功")
        return True
    except Exception as e:
        print(f"   ❌ 清理后仍然失败: {e}")
    
    # 尝试3: 内存模式
    print("\n   尝试3: 内存模式（不持久化）...")
    try:
        settings = Settings(
            allow_reset=True,
            anonymized_telemetry=False,
            is_persistent=False
        )
        client = chromadb.Client(settings)
        print("   ✅ 内存模式初始化成功")
        print("   ⚠️ 注意: 内存模式下数据不会持久化")
        return True
    except Exception as e:
        print(f"   ❌ 内存模式也失败: {e}")
        return False


def fix_chromadb():
    """修复 ChromaDB 问题"""
    print("\n" + "=" * 80)
    print("ChromaDB 修复工具")
    print("=" * 80)
    
    persist_dir = os.path.normpath(os.path.join(os.getcwd(), "data", "chromadb"))
    backup_dir = f"{persist_dir}.backup"
    
    if os.path.exists(persist_dir):
        response = input(f"\n是否要清理数据库目录 ({persist_dir})? [y/N]: ")
        if response.lower() == 'y':
            try:
                if os.path.exists(backup_dir):
                    shutil.rmtree(backup_dir)
                shutil.move(persist_dir, backup_dir)
                print(f"✅ 已备份到: {backup_dir}")
                print("✅ 数据库目录已清理")
                return True
            except Exception as e:
                print(f"❌ 清理失败: {e}")
                return False
        else:
            print("ℹ️ 跳过清理")
    else:
        print("ℹ️ 数据库目录不存在，无需清理")
    
    return True


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "fix":
        fix_chromadb()
    else:
        success = diagnose_chromadb()
        if not success:
            print("\n" + "=" * 80)
            print("建议的修复步骤:")
            print("=" * 80)
            print("1. 升级 ChromaDB:")
            print("   pip install --upgrade chromadb")
            print("\n2. 清理数据库目录:")
            print("   python scripts/diagnose_chromadb.py fix")
            print("\n3. 如果问题仍然存在，使用内存模式（数据不会持久化）")
