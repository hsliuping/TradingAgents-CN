"""
预构建能力索引脚本

在发布前执行，用 DashScope embedding 构建全量工具索引，
写入 data/chromadb/ 目录，随安装包分发。

用法:
    python scripts/build_capability_index.py

环境要求:
    - DashScope embedding 模型已配置
    - 数据库连接可用（用于读取 skills 数据）
"""

import asyncio
import logging
import os
import sys
import time
from pathlib import Path

# 确保项目根路径可导入
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("build_capability_index")


async def main():
    logger.info("=" * 60)
    logger.info("开始构建预置能力索引")
    logger.info("=" * 60)

    start = time.time()

    from app.core.database import get_database, init_database
    from app.services.capability_index_service import CapabilityIndexService

    # 初始化 MongoDB 连接（独立脚本需显式初始化）
    await init_database()
    db = get_database()
    service = CapabilityIndexService(db)

    # 检查 embedding 模型
    config = service._embedding_manager.get_config()
    if not config.get("has_provider"):
        logger.error("❌ 未检测到可用的 embedding 提供商")
        logger.error("   请确保已配置 DashScope embedding 模型")
        logger.error("   设置方法: 在系统设置中配置 DashScope 的 API Key 和 embedding_model")
        sys.exit(1)

    primary = config.get("primary_provider", {})
    logger.info(f"📋 Embedding 提供商: {primary.get('display_name', 'unknown')}")
    logger.info(f"📋 Embedding 模型: {primary.get('model', 'unknown')}")

    # 强制重建索引
    logger.info("🔄 强制重建索引...")
    result = await service.ensure_index(force=True)

    elapsed = time.time() - start
    logger.info(f"✅ 索引构建完成 ({elapsed:.1f}s)")
    logger.info(f"   - 集合: {result.collection_name}")
    logger.info(f"   - 文档数: {result.total_documents}")
    logger.info(f"   - 已索引: {result.indexed_documents}")
    logger.info(f"   - 向量后端: {result.vector_backend}")
    logger.info(f"   - 指纹: {result.fingerprint[:16]}...")
    logger.info(f"   - 模式: {result.sync_mode}")

    # 验证索引
    logger.info("🔍 验证索引...")
    test_queries = [
        "DCF估值",
        "财务风险分析",
        "技术指标MACD",
        "投资组合优化",
        "宏观经济周期",
    ]
    for q in test_queries:
        hits = await service.search_capabilities(q, top_k=3, source_types=["builtin_tool"])
        top_names = [h.capability.name for h in hits[:3]]
        logger.info(f"   '{q}' → {top_names}")

    # 确认数据目录
    chroma_dir = os.path.join(os.getcwd(), "data", "chromadb")
    if os.path.isdir(chroma_dir):
        total_size = sum(
            os.path.getsize(os.path.join(root, f))
            for root, _, files in os.walk(chroma_dir)
            for f in files
        )
        logger.info(f"📁 ChromaDB 数据目录: {chroma_dir}")
        logger.info(f"📁 磁盘占用: {total_size / 1024:.1f} KB")
    else:
        logger.warning(f"⚠️ ChromaDB 数据目录不存在: {chroma_dir}")

    logger.info("=" * 60)
    logger.info("🎉 预置索引构建完成，可以随安装包分发 data/chromadb/ 目录")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())