"""
帝国AI角色适配层测试脚本
Imperial Agent Wrapper Test Script

测试帝国角色适配层的基本功能
"""

import sys
import os
import asyncio
from pathlib import Path

# 添加项目路径到sys.path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from imperial_agents.core.imperial_agent_wrapper import (
    ImperialAgentFactory, 
    AnalysisType,
    DecisionLevel
)
from imperial_agents.config.role_config_manager import get_config_manager
from tradingagents.utils.logging_init import get_logger

# 配置日志
logger = get_logger("imperial_test")


def test_config_manager():
    """测试配置管理器"""
    print("🧪 [测试] 开始测试配置管理器...")
    
    try:
        # 获取配置管理器
        config_manager = get_config_manager()
        
        # 创建默认配置文件
        success = config_manager.create_default_configs()
        print(f"📝 [测试] 默认配置创建: {'成功' if success else '失败'}")
        
        # 列出可用角色
        roles = config_manager.list_available_roles()
        print(f"🎭 [测试] 可用角色: {roles}")
        
        # 加载威科夫AI配置
        wyckoff_config = config_manager.load_role_config("威科夫AI")
        print(f"⚙️ [测试] 威科夫AI配置加载成功: {wyckoff_config.name}")
        print(f"   - 专业领域: {wyckoff_config.expertise}")
        print(f"   - 决策风格: {wyckoff_config.decision_style}")
        
        return True
        
    except Exception as e:
        print(f"❌ [测试] 配置管理器测试失败: {e}")
        return False


def test_agent_creation():
    """测试角色创建"""
    print("\n🧪 [测试] 开始测试角色创建...")
    
    try:
        # 创建模拟LLM（用于测试）
        class MockLLM:
            def __init__(self):
                self.name = "MockLLM"
            
            async def ainvoke(self, messages):
                # 模拟LLM响应
                class MockResponse:
                    def __init__(self):
                        self.content = """**决策建议**: 买入
**置信度**: 75%
**关键因素**: 
- 技术指标显示上升趋势
- 成交量配合价格上涨
- 突破关键阻力位

**风险提示**:
- 市场整体波动风险
- 个股基本面变化风险

**详细分析**:
基于威科夫分析，当前股票处于累积阶段末期，即将进入上升阶段。
价格和成交量关系良好，显示有聪明资金在积极建仓。
建议在当前价位附近分批买入，止损设在关键支撑位下方。"""
                
                return MockResponse()
            
            def invoke(self, messages):
                # 同步版本
                return asyncio.run(self.ainvoke(messages))
        
        # 创建模拟工具集
        from tradingagents.agents.utils.agent_utils import Toolkit
        toolkit = Toolkit()
        
        # 创建威科夫AI角色
        wyckoff_agent = ImperialAgentFactory.create_agent(
            role_name="威科夫AI",
            llm=MockLLM(),
            toolkit=toolkit
        )
        
        print(f"🎭 [测试] 角色创建成功: {wyckoff_agent.name}")
        print(f"   - 标题: {wyckoff_agent.title}")
        print(f"   - 专业: {', '.join(wyckoff_agent.role_config.expertise)}")
        
        return wyckoff_agent
        
    except Exception as e:
        print(f"❌ [测试] 角色创建测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_analysis_functionality(agent):
    """测试分析功能"""
    print("\n🧪 [测试] 开始测试分析功能...")
    
    if not agent:
        print("❌ [测试] 角色实例为空，跳过分析测试")
        return False
    
    try:
        # 测试股票分析
        test_symbol = "000001"  # 平安银行
        
        print(f"📊 [测试] 开始分析股票: {test_symbol}")
        
        # 进行技术分析
        analysis_result = agent.analyze_stock(
            symbol=test_symbol,
            analysis_type=AnalysisType.TECHNICAL_ANALYSIS,
            start_date="2025-01-01",
            end_date="2025-08-15"
        )
        
        print(f"✅ [测试] 分析完成!")
        print(f"   - 角色: {analysis_result.role_name}")
        print(f"   - 股票: {analysis_result.symbol}")
        print(f"   - 决策: {analysis_result.decision.value}")
        print(f"   - 置信度: {analysis_result.confidence:.2%}")
        print(f"   - 关键因素数量: {len(analysis_result.key_factors)}")
        print(f"   - 风险提示数量: {len(analysis_result.risk_warnings)}")
        
        return True
        
    except Exception as e:
        print(f"❌ [测试] 分析功能测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_multiple_roles():
    """测试多角色创建"""
    print("\n🧪 [测试] 开始测试多角色创建...")
    
    try:
        # 创建模拟LLM
        class MockLLM:
            def __init__(self, name):
                self.name = name
            
            async def ainvoke(self, messages):
                class MockResponse:
                    def __init__(self, role_name):
                        if "威科夫" in role_name:
                            self.content = """**决策建议**: 买入
**置信度**: 80%
**关键因素**: 
- 威科夫四阶段分析显示处于累积期
- 价量关系良好
- 聪明资金流入迹象明显"""
                        elif "马仁辉" in role_name:
                            self.content = """**决策建议**: 持有
**置信度**: 70%
**关键因素**: 
- 222法则验证通过
- 短期技术指标偏强
- 风险可控"""
                        else:
                            self.content = """**决策建议**: 中性
**置信度**: 60%
**关键因素**: 
- 基础分析完成
- 需要更多数据验证"""
                
                return MockResponse(self.name)
        
        from tradingagents.agents.utils.agent_utils import Toolkit
        toolkit = Toolkit()
        
        # 创建多个角色
        roles_to_test = ["威科夫AI", "马仁辉AI", "鳄鱼导师AI"]
        agents = {}
        
        for role_name in roles_to_test:
            try:
                agent = ImperialAgentFactory.create_agent(
                    role_name=role_name,
                    llm=MockLLM(role_name),
                    toolkit=toolkit
                )
                agents[role_name] = agent
                print(f"✅ [测试] {role_name} 创建成功")
            except Exception as e:
                print(f"❌ [测试] {role_name} 创建失败: {e}")
        
        print(f"🎭 [测试] 成功创建 {len(agents)} 个角色")
        
        return agents
        
    except Exception as e:
        print(f"❌ [测试] 多角色测试失败: {e}")
        return {}


def main():
    """主测试函数"""
    print("🚀 [开始] 帝国AI角色适配层测试")
    print("=" * 60)
    
    success_count = 0
    total_tests = 4
    
    # 1. 测试配置管理器
    if test_config_manager():
        success_count += 1
    
    # 2. 测试角色创建
    agent = test_agent_creation()
    if agent:
        success_count += 1
    
    # 3. 测试分析功能
    if test_analysis_functionality(agent):
        success_count += 1
    
    # 4. 测试多角色创建
    agents = test_multiple_roles()
    if len(agents) >= 2:
        success_count += 1
    
    print("\n" + "=" * 60)
    print(f"🏆 [结果] 测试完成: {success_count}/{total_tests} 通过")
    
    if success_count == total_tests:
        print("✅ [成功] 所有测试通过！帝国角色适配层正常工作")
        return True
    else:
        print(f"⚠️ [警告] 部分测试失败，需要检查配置")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
