"""
测试持仓分析工作流集成
"""

import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 设置环境变量
os.environ["USE_WORKFLOW_ENGINE"] = "true"

from app.core.database import init_database
from app.services.portfolio_service import PortfolioService
from app.models.portfolio import PositionAnalysisRequest, PositionSnapshot


async def test_position_analysis_workflow():
    """测试持仓分析工作流"""
    print("🚀 测试持仓分析工作流集成...")

    # 初始化数据库连接
    print("🔄 初始化数据库连接...")
    await init_database()
    print("✅ 数据库连接初始化完成")

    # 创建测试数据
    snapshot = PositionSnapshot(
        code="000001",
        name="平安银行",
        market="CN",
        industry="银行",
        quantity=1000,
        cost_price=12.50,
        current_price=13.20,
        market_value=13200,
        unrealized_pnl=700,
        unrealized_pnl_pct=5.6,
        holding_days=30,
        total_capital=100000,
        position_pct=13.2
    )
    
    params = PositionAnalysisRequest(
        research_depth="标准",
        include_add_position=True,
        target_profit_pct=20.0,
        total_capital=100000,
        max_position_pct=30.0,
        max_loss_pct=10.0,
        # 新增字段
        risk_tolerance="medium",           # 风险偏好: low/medium/high
        investment_horizon="medium",       # 投资期限: short/medium/long
        analysis_focus="comprehensive",    # 分析重点: technical/fundamental/comprehensive
        position_type="real"               # 持仓类型: real/simulated
    )
    
    # 模拟单股分析报告
    stock_analysis_report = {
        "task_id": "test_task_123",
        "technical_analysis": "技术面分析：股价突破重要阻力位，MACD金叉，RSI处于强势区间",
        "fundamental_analysis": "基本面分析：ROE稳定，估值合理，行业地位稳固",
        "news_analysis": "新闻面分析：近期政策利好，市场情绪积极",
        "recommendation": "综合建议：适度看好，建议持有"
    }
    
    # 创建服务实例
    service = PortfolioService()
    
    try:
        # 测试工作流分析
        print("📊 开始执行工作流分析...")
        result = await service._call_position_ai_analysis_workflow(
            snapshot=snapshot,
            params=params,
            stock_analysis_report=stock_analysis_report,
            user_id="test_user"
        )
        
        print("✅ 工作流分析完成!")
        print(f"   操作建议: {result.action}")
        print(f"   操作理由: {result.action_reason}")
        print(f"   置信度: {result.confidence}")
        print(f"   分析来源: {result.source}")

        if result.summary:
            print(f"   分析摘要: {result.summary[:300]}...")

        if result.recommendation:
            print(f"   操作建议详情: {result.recommendation[:200]}...")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_position_analysis_workflow())
