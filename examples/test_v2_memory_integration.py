"""
测试 v2.0 Memory 和 Embedding 集成

验证：
1. EmbeddingManager 正确初始化
2. MemoryManager 正确初始化
3. ResearcherAgent 正确接收 memory 参数
4. 辩论 Agent 可以使用记忆系统
"""

import asyncio
import logging
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_embedding_manager():
    """测试 EmbeddingManager"""
    print("\n" + "="*80)
    print("测试 1: EmbeddingManager 初始化")
    print("="*80)
    
    from core.llm import EmbeddingManager
    from app.core.database import init_database, get_mongo_db
    
    await init_database()
    db = get_mongo_db()
    
    embedding_mgr = EmbeddingManager(db=db)
    
    # 测试 embedding
    test_text = "苹果公司Q3财报超预期"
    embedding, provider = embedding_mgr.get_embedding(test_text)
    
    if embedding:
        print(f"✅ Embedding 成功")
        print(f"   提供商: {provider}")
        print(f"   维度: {len(embedding)}")
        return True
    else:
        print(f"❌ Embedding 失败: {provider}")
        return False


async def test_memory_manager():
    """测试 MemoryManager"""
    print("\n" + "="*80)
    print("测试 2: MemoryManager 初始化")
    print("="*80)
    
    from core.llm import EmbeddingManager
    from core.memory import MemoryManager
    from app.core.database import init_database, get_mongo_db
    
    await init_database()
    db = get_mongo_db()
    
    embedding_mgr = EmbeddingManager(db=db)
    memory_mgr = MemoryManager(embedding_mgr)
    
    # 获取 Agent 记忆
    bull_memory = memory_mgr.get_agent_memory("bull_researcher_v2")
    
    # 添加测试记忆
    success = bull_memory.add_memory(
        content="苹果公司Q3财报超预期，营收同比增长15%，建议买入",
        metadata={"ticker": "AAPL", "stance": "bull"}
    )
    
    if success:
        print(f"✅ 记忆添加成功")
        count = bull_memory.get_memory_count()
        print(f"   记忆总数: {count}")
        return True
    else:
        print(f"❌ 记忆添加失败")
        return False


async def test_agent_with_memory():
    """测试 Agent 集成 Memory"""
    print("\n" + "="*80)
    print("测试 3: ResearcherAgent 集成 Memory")
    print("="*80)
    
    from core.llm import EmbeddingManager
    from core.memory import MemoryManager
    from core.agents import create_agent
    from app.core.database import init_database, get_mongo_db
    from langchain_openai import ChatOpenAI
    
    await init_database()
    db = get_mongo_db()
    
    # 创建 EmbeddingManager 和 MemoryManager
    embedding_mgr = EmbeddingManager(db=db)
    memory_mgr = MemoryManager(embedding_mgr)
    
    # 获取记忆实例
    bull_memory = memory_mgr.get_agent_memory("bull_researcher_v2")
    
    # 创建 LLM
    try:
        llm = ChatOpenAI(
            model="qwen-turbo",
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
    except Exception as e:
        print(f"⚠️ LLM 创建失败: {e}")
        llm = None
    
    # 创建 Agent（传入 memory）
    try:
        agent = create_agent(
            "bull_researcher_v2",
            llm=llm,
            memory=bull_memory
        )
        
        print(f"✅ Agent 创建成功: {type(agent).__name__}")
        print(f"   Agent ID: {agent.agent_id}")
        print(f"   Memory: {type(agent.memory).__name__ if hasattr(agent, 'memory') and agent.memory else 'None'}")
        
        if hasattr(agent, 'memory') and agent.memory:
            print(f"   ✅ Agent 成功接收 memory 参数")
            return True
        else:
            print(f"   ❌ Agent 未接收 memory 参数")
            return False
    
    except Exception as e:
        print(f"❌ Agent 创建失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_workflow_builder_memory():
    """测试 WorkflowBuilder 集成 Memory"""
    print("\n" + "="*80)
    print("测试 4: WorkflowBuilder 集成 Memory")
    print("="*80)
    
    from core.workflow.builder import WorkflowBuilder
    from app.core.database import init_database
    
    await init_database()
    
    # 创建 WorkflowBuilder
    builder = WorkflowBuilder()
    
    print(f"✅ WorkflowBuilder 创建成功")
    print(f"   EmbeddingManager: {type(builder.embedding_manager).__name__ if builder.embedding_manager else 'None'}")
    print(f"   MemoryManager: {type(builder.memory_manager).__name__ if builder.memory_manager else 'None'}")
    
    if builder.embedding_manager and builder.memory_manager:
        print(f"   ✅ WorkflowBuilder 成功初始化记忆系统")
        return True
    else:
        print(f"   ❌ WorkflowBuilder 未初始化记忆系统")
        return False


async def main():
    """主测试函数"""
    print("\n" + "🚀 "*30)
    print("v2.0 Memory 和 Embedding 集成测试")
    print("🚀 "*30)
    
    results = []
    
    # 测试 1: EmbeddingManager
    try:
        result = await test_embedding_manager()
        results.append(("EmbeddingManager", result))
    except Exception as e:
        logger.error(f"测试 1 失败: {e}", exc_info=True)
        results.append(("EmbeddingManager", False))
    
    # 测试 2: MemoryManager
    try:
        result = await test_memory_manager()
        results.append(("MemoryManager", result))
    except Exception as e:
        logger.error(f"测试 2 失败: {e}", exc_info=True)
        results.append(("MemoryManager", False))
    
    # 测试 3: Agent 集成
    try:
        result = await test_agent_with_memory()
        results.append(("Agent Integration", result))
    except Exception as e:
        logger.error(f"测试 3 失败: {e}", exc_info=True)
        results.append(("Agent Integration", False))
    
    # 测试 4: WorkflowBuilder 集成
    try:
        result = await test_workflow_builder_memory()
        results.append(("WorkflowBuilder Integration", result))
    except Exception as e:
        logger.error(f"测试 4 失败: {e}", exc_info=True)
        results.append(("WorkflowBuilder Integration", False))
    
    # 汇总结果
    print("\n" + "="*80)
    print("测试结果汇总")
    print("="*80)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name:30s} {status}")
    
    total = len(results)
    passed = sum(1 for _, r in results if r)
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！")
    else:
        print(f"\n⚠️ {total - passed} 个测试失败")


if __name__ == "__main__":
    asyncio.run(main())

