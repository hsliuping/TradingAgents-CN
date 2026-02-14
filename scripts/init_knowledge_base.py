"""
初始化金融知识库

将预定义的知识文档灌入向量数据库（Qdrant），供 RAG 动态检索使用。

用法：
    python scripts/init_knowledge_base.py          # 增量模式（跳过已有）
    python scripts/init_knowledge_base.py --reset   # 重置模式（清空后重灌）
    python scripts/init_knowledge_base.py --stats   # 仅查看统计信息
"""

import argparse
import logging
import sys
import os

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 🔥 必须在导入 core 模块之前加载 .env，否则 EmbeddingManager 找不到 API Key
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="初始化金融知识库")
    parser.add_argument("--reset", action="store_true", help="清空后重新灌入所有知识")
    parser.add_argument("--stats", action="store_true", help="仅查看统计信息")
    args = parser.parse_args()

    from core.knowledge import FinancialKnowledgeManager
    from core.knowledge.financial_knowledge_manager import KnowledgeDocument
    from core.knowledge.knowledge_data import get_all_knowledge_documents

    # 注意：FinancialKnowledgeManager 是单例，第一次创建后后续获取相同实例
    km = FinancialKnowledgeManager()

    if not km.available:
        logger.error("❌ 知识管理器不可用，请检查向量数据库和 Embedding 配置")
        logger.error("   提示：确保 DASHSCOPE_API_KEY 等 Embedding 提供商配置正确")
        sys.exit(1)

    # 仅查看统计
    if args.stats:
        stats = km.get_stats()
        print("\n📊 知识库统计信息:")
        for k, v in stats.items():
            print(f"  {k}: {v}")
        return

    # 重置模式
    if args.reset:
        logger.info("🔄 重置模式：清空现有知识库...")
        km.clear_all()
        logger.info("✅ 知识库已清空")

    # 加载知识文档
    all_docs_raw = get_all_knowledge_documents()
    logger.info(f"📚 待灌入知识文档: {len(all_docs_raw)} 条")

    # 按分类统计
    from collections import Counter
    categories = Counter(d["category"] for d in all_docs_raw)
    for cat, count in sorted(categories.items()):
        logger.info(f"  - {cat}: {count} 条")

    # 转换为 KnowledgeDocument 对象
    docs = [KnowledgeDocument.from_dict(d) for d in all_docs_raw]

    # 批量灌入
    success = km.add_knowledge_batch(docs)

    # 输出结果
    print(f"\n{'='*50}")
    print(f"✅ 知识库初始化完成")
    print(f"  成功: {success}/{len(docs)}")
    print(f"  总文档数: {km.get_count()}")
    print(f"{'='*50}")

    # 测试检索
    test_queries = [
        "小米汽车概念股有哪些",
        "大盘今天怎么样",
        "光伏板块投资机会",
        "北向资金最近动向",
        "茅台营收利润增长怎么样",
        "高分红股票什么时候进场好",
        "经营现金流好不好",
        "主营业务构成是什么",
    ]

    print(f"\n🔍 检索测试:")
    for q in test_queries:
        snippets = km.search(q, top_k=2)
        titles = [s.title for s in snippets]
        print(f"  Q: {q}")
        print(f"  → {titles}")
        print()


if __name__ == "__main__":
    main()

