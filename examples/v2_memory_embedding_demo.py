"""
v2.0 Memory 和 Embedding 系统演示

展示如何在 v2.0 中使用：
1. EmbeddingManager - Text Embedding API 管理
2. MemoryManager - ChromaDB 向量记忆系统
3. 在 ResearcherAgent 中集成记忆功能
"""

import asyncio
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def demo_embedding_manager():
    """演示 EmbeddingManager 的使用"""
    print("\n" + "="*60)
    print("📊 演示 1: EmbeddingManager - Text Embedding API")
    print("="*60 + "\n")
    
    from core.llm import EmbeddingManager
    from app.core.database import init_database, get_mongo_db
    
    # 初始化数据库
    await init_database()
    db = get_mongo_db()
    
    # 创建 EmbeddingManager（从数据库读取配置）
    embedding_mgr = EmbeddingManager(db=db)
    
    # 测试文本
    test_text = "苹果公司Q3财报超预期，营收同比增长15%，iPhone销量创新高"
    
    # 获取 embedding
    embedding, provider = embedding_mgr.get_embedding(test_text)
    
    if embedding:
        print(f"✅ Embedding 成功")
        print(f"   提供商: {provider}")
        print(f"   向量维度: {len(embedding)}")
        print(f"   前5个值: {embedding[:5]}")
    else:
        print(f"❌ Embedding 失败: {provider}")


async def demo_memory_manager():
    """演示 MemoryManager 的使用"""
    print("\n" + "="*60)
    print("🧠 演示 2: MemoryManager - ChromaDB 向量记忆系统")
    print("="*60 + "\n")
    
    from core.llm import EmbeddingManager
    from core.memory import MemoryManager
    from app.core.database import init_database, get_mongo_db
    
    # 初始化数据库
    await init_database()
    db = get_mongo_db()
    
    # 创建 EmbeddingManager 和 MemoryManager
    embedding_mgr = EmbeddingManager(db=db)
    memory_mgr = MemoryManager(embedding_mgr)
    
    # 获取 bull_analyst 的记忆实例
    bull_memory = memory_mgr.get_agent_memory("bull_analyst")
    
    # 添加一些历史记忆
    print("📝 添加历史记忆...")
    
    memories = [
        {
            "content": "苹果公司Q3财报超预期，营收同比增长15%，建议买入",
            "metadata": {"ticker": "AAPL", "stance": "bull", "date": "2024-01-15"}
        },
        {
            "content": "特斯拉交付量创新高，市场份额持续扩大，强烈看好",
            "metadata": {"ticker": "TSLA", "stance": "bull", "date": "2024-01-20"}
        },
        {
            "content": "微软云业务增长强劲，AI产品受市场欢迎，推荐增持",
            "metadata": {"ticker": "MSFT", "stance": "bull", "date": "2024-01-25"}
        }
    ]
    
    for mem in memories:
        success = bull_memory.add_memory(
            content=mem["content"],
            metadata=mem["metadata"]
        )
        if success:
            print(f"   ✅ {mem['metadata']['ticker']}: {mem['content'][:30]}...")
    
    # 查询相似记忆
    print("\n🔍 查询相似记忆...")
    query = "苹果公司最新财报表现如何？"
    
    results = bull_memory.search_memories(query, n_results=2)
    
    print(f"\n查询: {query}")
    print(f"找到 {len(results)} 条相似记忆:\n")
    
    for i, result in enumerate(results, 1):
        print(f"{i}. [相似度: {result['similarity']:.3f}]")
        print(f"   内容: {result['content'][:50]}...")
        print(f"   元数据: {result['metadata']}")
        print()
    
    # 显示记忆统计
    count = bull_memory.get_memory_count()
    print(f"📊 当前记忆总数: {count}")


async def demo_researcher_with_memory():
    """演示 ResearcherAgent 集成记忆系统"""
    print("\n" + "="*60)
    print("🤖 演示 3: ResearcherAgent 集成记忆系统")
    print("="*60 + "\n")
    
    from core.llm import EmbeddingManager
    from core.memory import MemoryManager
    from app.core.database import init_database, get_mongo_db
    
    # 初始化数据库
    await init_database()
    db = get_mongo_db()
    
    # 创建 EmbeddingManager 和 MemoryManager
    embedding_mgr = EmbeddingManager(db=db)
    memory_mgr = MemoryManager(embedding_mgr)
    
    # 获取 bull_analyst 的记忆
    bull_memory = memory_mgr.get_agent_memory("bull_analyst")
    
    print("📝 模拟 ResearcherAgent 使用记忆系统...\n")
    
    # 模拟当前分析报告
    current_reports = {
        "market_report": "市场整体上涨，科技股表现强劲",
        "news_report": "苹果发布新产品，市场反应积极",
        "fundamentals_report": "苹果Q3营收增长15%，利润率提升"
    }
    
    # 1. 检索历史经验
    print("🔍 步骤 1: 检索历史经验")
    curr_situation = "\n\n".join([str(v) for v in current_reports.values()])
    past_memories = bull_memory.search_memories(curr_situation, n_results=2)
    
    if past_memories:
        print(f"   找到 {len(past_memories)} 条相关历史经验")
        for mem in past_memories:
            print(f"   - [相似度: {mem['similarity']:.3f}] {mem['content'][:40]}...")
    else:
        print("   未找到相关历史经验")
    
    # 2. 生成新的分析报告（模拟）
    print("\n📊 步骤 2: 生成新的分析报告")
    new_report = {
        "content": "基于当前市场和财报数据，苹果公司表现优异，建议买入",
        "stance": "bull",
        "confidence": 0.85
    }
    print(f"   {new_report['content']}")
    
    # 3. 保存到记忆系统
    print("\n💾 步骤 3: 保存到记忆系统")
    success = bull_memory.add_memory(
        content=new_report["content"],
        metadata={
            "ticker": "AAPL",
            "stance": "bull",
            "confidence": new_report["confidence"],
            "timestamp": datetime.now().isoformat()
        }
    )
    
    if success:
        print("   ✅ 记忆保存成功")
    else:
        print("   ❌ 记忆保存失败")


async def main():
    """主函数"""
    print("\n" + "🚀 " * 20)
    print("v2.0 Memory 和 Embedding 系统演示")
    print("🚀 " * 20)
    
    try:
        # 演示 1: EmbeddingManager
        await demo_embedding_manager()
        
        # 演示 2: MemoryManager
        await demo_memory_manager()
        
        # 演示 3: ResearcherAgent 集成
        await demo_researcher_with_memory()
        
        print("\n" + "✅ " * 20)
        print("所有演示完成！")
        print("✅ " * 20 + "\n")
    
    except Exception as e:
        logger.error(f"演示失败: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())

