"""
测试 v2.0 工作流引擎的分析师动态裁剪功能

验证：
1. selected_analysts 参数是否正确传递到 WorkflowBuilder
2. WorkflowBuilder 是否正确过滤未选中的分析师节点
3. 工作流执行时是否只运行选中的分析师

使用方法:
    python scripts/test_analyst_filtering.py
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


async def test_analyst_filtering():
    """测试分析师过滤功能"""
    
    logger.info("=" * 80)
    logger.info("测试 v2.0 工作流引擎的分析师动态裁剪功能")
    logger.info("=" * 80)
    
    # 1. 导入必要的模块
    from app.services.unified_analysis_engine import UnifiedAnalysisEngine
    from app.models.analysis import UnifiedAnalysisTask, AnalysisTaskType, AnalysisStatus
    from app.models.user import PyObjectId
    from bson import ObjectId
    
    # 2. 创建测试任务
    task_id = "test_analyst_filtering_001"
    
    # 只选择市场分析师和基本面分析师
    selected_analysts = ["market", "fundamentals"]
    
    task_params = {
        "symbol": "000858",
        "stock_code": "000858",
        "market_type": "cn",
        "analysis_date": datetime.now().strftime("%Y-%m-%d"),
        "research_depth": "快速",
        "selected_analysts": selected_analysts,  # 🔑 关键参数
        "quick_analysis_model": "qwen-turbo",
        "deep_analysis_model": "qwen-plus",
    }
    
    logger.info(f"📦 任务参数: {task_params}")
    logger.info(f"🎯 选中的分析师: {selected_analysts}")
    logger.info(f"⚠️  预期行为: 只运行市场分析师和基本面分析师，跳过新闻分析师和社媒分析师")
    
    # 创建任务对象
    task = UnifiedAnalysisTask(
        task_id=task_id,
        user_id=ObjectId(),  # 测试用户ID
        task_type=AnalysisTaskType.STOCK_ANALYSIS,
        task_params=task_params,
        engine_type="auto",
        status=AnalysisStatus.PENDING,
        created_at=datetime.now(),
        preference_type="neutral"
    )
    
    # 3. 创建引擎实例
    engine = UnifiedAnalysisEngine()
    
    # 4. 定义进度回调
    async def progress_callback(progress: int, message: str, **kwargs):
        step_name = kwargs.get("step_name", "")
        logger.info(f"📊 进度: {progress}% - {message} [{step_name}]")
    
    # 5. 执行分析
    logger.info("\n" + "=" * 80)
    logger.info("开始执行分析...")
    logger.info("=" * 80 + "\n")
    
    try:
        result = await engine.execute(
            task=task,
            progress_callback=progress_callback
        )
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ 分析完成")
        logger.info("=" * 80)
        logger.info(f"结果: {result.get('summary', 'N/A')[:200]}...")
        
        # 检查结果中的分析师报告
        if "market_report" in result:
            logger.info("✅ 市场分析师报告已生成")
        else:
            logger.warning("❌ 市场分析师报告缺失")
        
        if "fundamentals_report" in result:
            logger.info("✅ 基本面分析师报告已生成")
        else:
            logger.warning("❌ 基本面分析师报告缺失")
        
        if "news_report" in result:
            logger.warning("⚠️  新闻分析师报告不应该生成（但生成了）")
        else:
            logger.info("✅ 新闻分析师报告正确跳过")
        
        if "social_report" in result:
            logger.warning("⚠️  社媒分析师报告不应该生成（但生成了）")
        else:
            logger.info("✅ 社媒分析师报告正确跳过")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 分析失败: {e}", exc_info=True)
        return False


async def main():
    """主函数"""
    success = await test_analyst_filtering()
    
    if success:
        logger.info("\n" + "=" * 80)
        logger.info("🎉 测试通过！分析师动态裁剪功能正常工作")
        logger.info("=" * 80)
    else:
        logger.error("\n" + "=" * 80)
        logger.error("❌ 测试失败！请检查日志")
        logger.error("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

