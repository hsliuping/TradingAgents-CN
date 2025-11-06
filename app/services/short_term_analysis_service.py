"""
超短行情分析服务
专门用于分析A股股票的超短期行情，预测明日涨停、上涨、下跌的概率
"""

import asyncio
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
import sys

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 初始化TradingAgents日志系统
from tradingagents.utils.logging_init import init_logging
init_logging()

from tradingagents.graph.trading_graph import create_llm_by_provider
from tradingagents.agents.analysts.short_term_analyst import create_short_term_analyst
from tradingagents.agents.utils.agent_utils import Toolkit
from tradingagents.agents.utils.agent_states import AgentState
from tradingagents.default_config import DEFAULT_CONFIG
from app.services.config_service import ConfigService
from app.core.database import get_mongo_db
from bson import ObjectId

# 设置日志
logger = logging.getLogger("app.services.short_term_analysis_service")

# 配置服务实例
config_service = ConfigService()


class ShortTermAnalysisService:
    """超短行情分析服务类"""

    def __init__(self):
        self._toolkit_cache = None
        logger.info(f"🔧 [服务初始化] ShortTermAnalysisService 实例ID: {id(self)}")

    def _get_toolkit(self, config: Dict[str, Any]) -> Toolkit:
        """获取或创建Toolkit实例"""
        if self._toolkit_cache is None:
            self._toolkit_cache = Toolkit(config)
            logger.info(f"✅ Toolkit实例创建成功")
        return self._toolkit_cache

    async def analyze_short_term(
        self,
        ticker: str,
        analysis_date: str,
        llm_provider: str = "dashscope",
        llm_model: str = "qwen-max",
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        执行超短行情分析
        
        Args:
            ticker: 股票代码（A股6位数字）
            analysis_date: 分析日期（格式：YYYY-MM-DD）
            llm_provider: LLM提供商
            llm_model: LLM模型名称
            user_id: 用户ID（可选）
            
        Returns:
            Dict包含分析结果
        """
        logger.info(f"🚀 [超短行情分析] 开始分析: ticker={ticker}, date={analysis_date}")
        
        try:
            # 1. 获取LLM配置（使用与正常分析相同的逻辑）
            # 使用 get_provider_and_url_by_model_sync 获取完整的配置信息（包括API Key、backend_url等）
            from app.services.simple_analysis_service import get_provider_and_url_by_model_sync
            
            provider_info = get_provider_and_url_by_model_sync(llm_model)
            
            provider = provider_info["provider"]
            backend_url = provider_info.get("backend_url") or ""
            api_key = provider_info.get("api_key")  # 已经经过验证的API Key（优先级：模型配置 > 厂家配置 > 环境变量）
            
            logger.info(f"🔍 [超短行情分析] 模型 {llm_model} 对应的供应商: {provider}")
            logger.info(f"🔍 [超短行情分析] backend_url: {backend_url}")
            logger.info(f"🔑 [超短行情分析] API Key: {'已配置' if api_key else '未配置（将使用环境变量）'}")
            if api_key:
                logger.info(f"🔑 [超短行情分析] API Key 长度: {len(api_key)}, 前10位: {api_key[:10]}...")
            else:
                # 如果 api_key 为 None，尝试从环境变量获取
                import os
                env_key_map = {
                    "dashscope": "DASHSCOPE_API_KEY",
                    "openai": "OPENAI_API_KEY",
                    "deepseek": "DEEPSEEK_API_KEY",
                    "google": "GOOGLE_API_KEY",
                }
                env_key_name = env_key_map.get(provider.lower())
                if env_key_name:
                    env_api_key = os.getenv(env_key_name)
                    if env_api_key:
                        logger.info(f"🔑 [超短行情分析] 从环境变量 {env_key_name} 获取 API Key")
                        api_key = env_api_key
            
            # 2. 创建LLM实例
            llm = create_llm_by_provider(
                provider=provider,
                model=llm_model,
                backend_url=backend_url,
                temperature=0.7,
                max_tokens=4000,
                timeout=180,
                api_key=api_key
            )
            
            logger.info(f"✅ [超短行情分析] LLM创建成功: {provider}/{llm_model}")
            
            # 3. 创建配置
            config = DEFAULT_CONFIG.copy()
            config.update({
                "llm_provider": provider,
                "quick_think_llm": llm_model,
                "deep_think_llm": llm_model,
                "research_depth": "标准",
                "online_tools": True,
            })
            
            # 4. 创建Toolkit
            toolkit = self._get_toolkit(config)
            
            # 5. 创建超短行情分析师
            short_term_analyst = create_short_term_analyst(llm, toolkit)
            
            # 6. 创建初始状态
            initial_state = {
                "company_of_interest": ticker,
                "trade_date": analysis_date,
                "messages": [],
                "short_term_report": None
            }
            
            # 7. 执行分析（可能需要多轮工具调用）
            current_state = initial_state
            max_iterations = 10  # 最多10轮迭代
            iteration = 0
            
            while iteration < max_iterations:
                iteration += 1
                logger.info(f"🔄 [超短行情分析] 第 {iteration} 轮迭代")
                
                # 调用分析师
                result = short_term_analyst(current_state)
                
                # 更新状态：合并消息列表（而不是直接覆盖）
                if "messages" in result:
                    # 将新消息添加到现有消息列表
                    if "messages" not in current_state:
                        current_state["messages"] = []
                    current_state["messages"].extend(result["messages"])
                
                # 更新其他字段
                if "short_term_report" in result:
                    current_state["short_term_report"] = result["short_term_report"]
                
                # 检查是否有工具调用
                has_tool_calls = False
                if current_state.get("messages"):
                    last_message = current_state["messages"][-1]
                    if last_message and hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                        has_tool_calls = True
                        logger.info(f"🔧 [超短行情分析] 检测到工具调用，需要执行工具")
                        
                        # 执行工具调用
                        from langgraph.prebuilt import ToolNode
                        tools = [
                            toolkit.get_stock_market_data_unified,
                            toolkit.get_stock_fundamentals_unified,
                            toolkit.get_realtime_stock_news,
                            toolkit.get_short_term_board_data
                        ]
                        tool_node = ToolNode(tools)
                        
                        # 执行工具调用（ToolNode会自动处理消息格式）
                        tool_result = tool_node.invoke(current_state)
                        
                        # 更新状态：合并工具执行结果的消息
                        if "messages" in tool_result:
                            if "messages" not in current_state:
                                current_state["messages"] = []
                            current_state["messages"].extend(tool_result["messages"])
                        
                        logger.info(f"✅ [超短行情分析] 工具执行完成")
                
                # 如果没有工具调用，说明分析完成
                if not has_tool_calls:
                    logger.info(f"✅ [超短行情分析] 分析完成，共 {iteration} 轮迭代")
                    break
            
            # 8. 提取分析结果
            report = current_state.get("short_term_report", "")
            if not report and current_state.get("messages"):
                # 从最后一条消息中提取内容
                last_message = current_state["messages"][-1]
                if hasattr(last_message, 'content'):
                    report = last_message.content
                else:
                    report = str(last_message)
            
            # 9. 解析概率值（从报告中提取）
            probabilities = self._parse_probabilities(report)
            
            # 10. 构建返回结果
            result = {
                "success": True,
                "ticker": ticker,
                "analysis_date": analysis_date,
                "report": report,
                "probabilities": probabilities,
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"✅ [超短行情分析] 分析完成: {ticker}")
            return result
            
        except Exception as e:
            logger.error(f"❌ [超短行情分析] 分析失败: {e}", exc_info=True)
            return {
                "success": False,
                "ticker": ticker,
                "analysis_date": analysis_date,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    def _parse_probabilities(self, report: str) -> Dict[str, float]:
        """
        从分析报告中解析概率值
        
        Returns:
            Dict包含三个概率值
        """
        probabilities = {
            "limit_up": None,  # 涨停概率
            "up": None,        # 上涨概率
            "down": None       # 下跌概率
        }
        
        try:
            # 尝试从报告中提取概率值
            import re
            
            # 匹配模式：明日涨停概率: XX%
            limit_up_match = re.search(r'明日涨停概率[：:]\s*(\d+(?:\.\d+)?)%', report)
            if limit_up_match:
                probabilities["limit_up"] = float(limit_up_match.group(1))
            
            # 匹配模式：明日上涨概率: XX%
            up_match = re.search(r'明日上涨概率[：:]\s*(\d+(?:\.\d+)?)%', report)
            if up_match:
                probabilities["up"] = float(up_match.group(1))
            
            # 匹配模式：明日下跌概率: XX%
            down_match = re.search(r'明日下跌概率[：:]\s*(\d+(?:\.\d+)?)%', report)
            if down_match:
                probabilities["down"] = float(down_match.group(1))
                
        except Exception as e:
            logger.warning(f"⚠️ [超短行情分析] 解析概率值失败: {e}")
        
        return probabilities


# 全局服务实例
_short_term_analysis_service = None


def get_short_term_analysis_service() -> ShortTermAnalysisService:
    """获取超短行情分析服务实例（单例模式）"""
    global _short_term_analysis_service
    if _short_term_analysis_service is None:
        _short_term_analysis_service = ShortTermAnalysisService()
    return _short_term_analysis_service

