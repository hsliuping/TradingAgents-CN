# Windows 11 ChromaDB 优化配置
import os
import platform
import chromadb
from chromadb.config import Settings

def is_windows_11():
    '''检测是否为Windows 11'''
    if platform.system() != "Windows":
        return False
    
    # Windows 11的版本号通常是10.0.22000或更高
    version = platform.version()
    try:
        # 提取版本号，格式通常是 "10.0.26100"
        version_parts = version.split('.')
        if len(version_parts) >= 3:
            build_number = int(version_parts[2])
            # Windows 11的构建号从22000开始
            return build_number >= 22000
    except (ValueError, IndexError):
        pass
    
    return False

def get_win11_chromadb_client():
    '''获取Windows 11优化的ChromaDB客户端'''
    # Windows 11 对 ChromaDB 支持更好，可以使用更现代的配置
    settings = Settings(
        allow_reset=True,
        anonymized_telemetry=False,  # 禁用遥测避免posthog错误
        is_persistent=False,
        # Windows 11 可以使用默认实现，性能更好
        chroma_db_impl="duckdb+parquet",
        chroma_api_impl="chromadb.api.segment.SegmentAPI"
        # 移除persist_directory=None，让它使用默认值
    )
    
    try:
        client = chromadb.Client(settings)
        return client
    except Exception as e:
        # 如果还有问题，使用最简配置
        minimal_settings = Settings(
            allow_reset=True,
            anonymized_telemetry=False,  # 关键：禁用遥测
            is_persistent=False
        )
        return chromadb.Client(minimal_settings)

def get_optimal_chromadb_client():
    '''根据Windows版本自动选择最优ChromaDB配置'''
    system = platform.system()
    
    if system == "Windows":
        # 使用更准确的Windows 11检测
        if is_windows_11():
            # Windows 11 或更新版本
            return get_win11_chromadb_client()
        else:
            # Windows 10 或更老版本，使用兼容配置
            from .chromadb_win10_config import get_win10_chromadb_client
            return get_win10_chromadb_client()
    else:
        # 非Windows系统，使用标准配置
        settings = Settings(
            allow_reset=True,
            anonymized_telemetry=False,
            is_persistent=False
        )
        return chromadb.Client(settings)

# 导出配置
__all__ = ['get_win11_chromadb_client', 'get_optimal_chromadb_client', 'is_windows_11']