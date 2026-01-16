"""
ChromaDB 配置模块

提供针对不同操作系统优化的 ChromaDB 配置
"""

import platform
import logging
import os
import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)


def is_windows_11() -> bool:
    """检测是否为 Windows 11"""
    if platform.system() != "Windows":
        return False
    
    try:
        version = platform.version()
        # Windows 11 的构建号 >= 22000
        build_number = int(version.split('.')[-1])
        return build_number >= 22000
    except Exception:
        return False


def get_optimal_chromadb_client():
    """
    获取针对当前操作系统优化的 ChromaDB 客户端
    
    Returns:
        chromadb.Client 实例
        
    Raises:
        Exception: 如果所有初始化方式都失败
    """
    import os
    import shutil
    
    system = platform.system()
    # 🔥 规范化路径，避免 Windows 路径问题
    persist_dir = os.path.normpath(os.path.join(os.getcwd(), "data", "chromadb"))
    
    # 🔥 确保目录存在
    try:
        os.makedirs(persist_dir, exist_ok=True)
    except Exception as e:
        logger.warning(f"⚠️ 创建 ChromaDB 目录失败: {e}")
    
    # 🔥 优先使用持久化模式，添加多个持久化配置尝试
    configs_to_try = []
    
    # 1. 首先尝试持久化模式（根据操作系统优化）
    if system == "Windows":
        if is_windows_11():
            # Windows 11 优化配置（持久化）
            configs_to_try.append({
                "name": "Windows 11 持久化配置",
                "settings": Settings(
                    allow_reset=True,
                    anonymized_telemetry=False,
                    is_persistent=True,
                    persist_directory=persist_dir
                )
            })
        else:
            # Windows 10 兼容配置（持久化）
            configs_to_try.append({
                "name": "Windows 10 持久化配置",
                "settings": Settings(
                    allow_reset=True,
                    anonymized_telemetry=False,
                    is_persistent=True,
                    persist_directory=persist_dir
                )
            })
    elif system == "Linux":
        configs_to_try.append({
            "name": "Linux 持久化配置",
            "settings": Settings(
                allow_reset=True,
                anonymized_telemetry=False,
                is_persistent=True,
                persist_directory=persist_dir
            )
        })
    elif system == "Darwin":
        configs_to_try.append({
            "name": "macOS 持久化配置",
            "settings": Settings(
                allow_reset=True,
                anonymized_telemetry=False,
                is_persistent=True,
                persist_directory=persist_dir
            )
        })
    else:
        configs_to_try.append({
            "name": f"默认持久化配置 ({system})",
            "settings": Settings(
                allow_reset=True,
                anonymized_telemetry=False,
                is_persistent=True,
                persist_directory=persist_dir
            )
        })
    
    # 🔥 添加内存模式作为最后的备用方案（只有在所有持久化方案都失败时才使用）
    configs_to_try.append({
        "name": "内存模式（最后备用）",
        "settings": Settings(
            allow_reset=True,
            anonymized_telemetry=False,
            is_persistent=False
        )
    })
    
    # 🔥 优先尝试持久化模式，自动清理损坏的数据库
    last_error = None
    persistent_cleaned = False  # 标记是否已经清理过数据库
    
    for i, config in enumerate(configs_to_try):
        try:
            config_name = config['name']
            is_persistent = config['settings'].is_persistent
            
            logger.info(f"📚 尝试配置 {i+1}/{len(configs_to_try)}: {config_name}")
            
            # 🔥 如果是持久化模式且之前失败过（且还没清理过），先清理数据库目录
            if is_persistent and last_error and not persistent_cleaned:
                error_msg = str(last_error)
                # 检查是否是数据库损坏相关的错误
                if any(keyword in error_msg.lower() for keyword in [
                    "panic", "panicked", "panicException",
                    "range start index", "out of range", 
                    "corrupt", "损坏", "sqlite", "index"
                ]):
                    logger.warning(f"⚠️ 检测到可能的数据库损坏，自动清理目录: {persist_dir}")
                    try:
                        # 备份旧数据
                        backup_dir = f"{persist_dir}.backup"
                        if os.path.exists(backup_dir):
                            shutil.rmtree(backup_dir)
                        if os.path.exists(persist_dir):
                            shutil.move(persist_dir, backup_dir)
                            logger.info(f"✅ 已备份旧数据库到: {backup_dir}")
                        # 重新创建目录
                        os.makedirs(persist_dir, exist_ok=True)
                        logger.info(f"✅ 数据库目录已清理，准备重新初始化")
                        persistent_cleaned = True
                    except Exception as cleanup_error:
                        logger.warning(f"⚠️ 清理数据库目录失败: {cleanup_error}")
                        # 如果清理失败，尝试强制删除后重建
                        try:
                            if os.path.exists(persist_dir):
                                shutil.rmtree(persist_dir)
                            os.makedirs(persist_dir, exist_ok=True)
                            logger.info(f"✅ 强制清理数据库目录成功")
                            persistent_cleaned = True
                        except Exception as force_cleanup_error:
                            logger.error(f"❌ 强制清理也失败: {force_cleanup_error}")
            
            # 🔥 创建 ChromaDB 客户端
            client = chromadb.Client(config['settings'])
            
            # 🔥 测试连接（验证客户端是否正常工作）
            try:
                client.heartbeat()
            except Exception as heartbeat_error:
                # 如果是持久化模式且还没清理过，尝试清理后重试
                if is_persistent and not persistent_cleaned:
                    logger.warning(f"⚠️ ChromaDB 心跳测试失败，尝试清理后重试...")
                    try:
                        # 备份并清理
                        backup_dir = f"{persist_dir}.backup"
                        if os.path.exists(backup_dir):
                            shutil.rmtree(backup_dir)
                        if os.path.exists(persist_dir):
                            shutil.move(persist_dir, backup_dir)
                        os.makedirs(persist_dir, exist_ok=True)
                        logger.info(f"✅ 已清理数据库目录")
                        persistent_cleaned = True
                        
                        # 重新创建客户端
                        client = chromadb.Client(config['settings'])
                        client.heartbeat()
                        logger.info(f"✅ 清理后重新初始化成功")
                    except Exception as retry_error:
                        logger.warning(f"⚠️ 清理后重试也失败: {retry_error}")
                        raise heartbeat_error
                else:
                    raise heartbeat_error
            
            # 🔥 初始化成功，记录运行模式
            if is_persistent:
                logger.info(f"✅ ChromaDB 客户端初始化成功: {config_name}")
                logger.info(f"   📁 运行模式: 持久化模式")
                logger.info(f"   📂 数据目录: {persist_dir}")
            else:
                logger.info(f"✅ ChromaDB 客户端初始化成功: {config_name}")
                logger.warning(f"   ⚠️ 运行模式: 内存模式（数据不会持久化）")
            
            return client
            
        except Exception as e:
            last_error = e
            error_msg = str(e)
            logger.warning(f"⚠️ 配置 {config['name']} 失败: {error_msg}")
            
            # 🔥 如果是 Rust panic 错误，记录详细信息
            if "PanicException" in error_msg or "panicked" in error_msg:
                logger.error(f"❌ ChromaDB Rust panic 错误，可能是版本不兼容或数据库损坏")
                if config['settings'].is_persistent and not persistent_cleaned:
                    logger.info(f"   🔄 下次尝试时将自动清理数据库目录")
            
            # 继续尝试下一个配置
            continue
    
    # 🔥 所有配置都失败，抛出最后一个错误
    raise Exception(f"所有 ChromaDB 配置都失败，最后一个错误: {last_error}")

