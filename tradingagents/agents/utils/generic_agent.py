import json
import os
import yaml
from datetime import datetime
from typing import List, Dict, Any, Optional

from langchain_core.messages import AIMessage, ToolMessage, BaseMessage, SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable

from tradingagents.utils.logging_init import get_logger
from tradingagents.utils.stock_utils import StockUtils

logger = get_logger("agents.generic")

def load_agent_config(slug: str) -> str:
    """从YAML配置加载智能体角色定义"""
    try:
        # 优先读取 phase1_agents_config.yaml
        current_dir = os.path.dirname(os.path.abspath(__file__))
        agents_dir = os.path.dirname(current_dir)
        
        # 定义可能的配置文件列表
        config_files = ["phase1_agents_config.yaml", "stock_analysis_agents_config.yaml"]
        
        for config_file in config_files:
            yaml_path = os.path.join(agents_dir, config_file)
            if not os.path.exists(yaml_path):
                continue
                
            with open(yaml_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # 检查 customModes
            for agent in config.get('customModes', []):
                if agent.get('slug') == slug:
                    return agent.get('roleDefinition', '')
                    
            # 检查 agents (如果配置结构不同)
            for agent in config.get('agents', []):
                if agent.get('slug') == slug:
                    return agent.get('roleDefinition', '')
        
        logger.warning(f"在配置中未找到智能体: {slug}")
        return ""
    except Exception as e:
        logger.error(f"加载配置文件失败: {e}")
        return ""

class GenericAgent:
    """
    通用智能体类，基于 LangChain 官方 ReAct Agent 架构。
    """
    def __init__(
        self,
        name: str,
        slug: str,
        llm: Any,
        tools: List[Any],
        system_message_template: str,
        use_tool_node: bool = False
    ):
        self.name = name
        self.slug = slug
        self.llm = llm
        self.tools = tools
        self.system_message_template = system_message_template
        
        # 初始化 Agent Executor
        self.agent_executor = None
        if tools:
            try:
                from langgraph.prebuilt import create_react_agent
                
                # 使用官方 create_react_agent 创建标准执行器
                # 不在此处传递 state_modifier，而在 run 中通过 messages 传递动态系统提示词
                self.agent_executor = create_react_agent(
                    model=llm, 
                    tools=tools
                )
                logger.info(f"[{name}] ✅ 官方 ReAct Agent Executor 初始化成功")
            except Exception as e:
                logger.error(f"[{name}] ❌ Agent Executor 初始化失败: {e}")
                self.agent_executor = None
        else:
            logger.warning(f"[{name}] ⚠️ 未提供工具，Agent 将仅具备基础对话能力")

    def _get_company_name(self, ticker: str, market_info: dict) -> str:
        """根据股票代码获取公司名称"""
        try:
            if market_info["is_china"]:
                from tradingagents.dataflows.interface import get_china_stock_info_unified

                stock_info = get_china_stock_info_unified(ticker)
                if "股票名称:" in stock_info:
                    company_name = stock_info.split("股票名称:")[1].split("\n")[0].strip()
                    logger.debug(f"📊 [DEBUG] 从统一接口获取中国股票名称: {ticker} -> {company_name}")
                    return company_name
                return f"股票代码{ticker}"

            if market_info["is_hk"]:
                try:
                    from tradingagents.dataflows.providers.hk.improved_hk import get_hk_company_name_improved
                    company_name = get_hk_company_name_improved(ticker)
                    return company_name
                except Exception:
                    clean_ticker = ticker.replace(".HK", "").replace(".hk", "")
                    return f"港股{clean_ticker}"

            if market_info["is_us"]:
                us_stock_names = {
                    "AAPL": "苹果公司", "TSLA": "特斯拉", "NVDA": "英伟达",
                    "MSFT": "微软", "GOOGL": "谷歌", "AMZN": "亚马逊",
                    "META": "Meta", "NFLX": "奈飞",
                }
                return us_stock_names.get(ticker.upper(), f"美股{ticker}")

            return f"股票{ticker}"

        except Exception as exc:
            logger.error(f"❌ [DEBUG] 获取公司名称失败: {exc}")
            return f"股票{ticker}"

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        start_time = datetime.now()
        
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        session_id = state.get("session_id", "未知会话")

        logger.info(f"[{self.name}] 开始分析 {ticker}，日期: {current_date}，会话: {session_id}")

        # 获取市场信息和公司名称
        market_info = StockUtils.get_market_info(ticker)
        company_name = self._get_company_name(ticker, market_info)
        logger.info(f"[{self.name}] 公司名称: {company_name}")

        final_report = ""
        executed_tool_calls = 0

        # 动态构建系统提示词
        system_msg_content = self.system_message_template or "您是一位专业的金融分析师。"
        # 简单替换常用占位符
        system_msg_content = system_msg_content.replace("{current_date}", str(current_date))
        system_msg_content = system_msg_content.replace("{ticker}", str(ticker))
        system_msg_content = system_msg_content.replace("{company_name}", str(company_name))
        
        # 补充上下文
        context_info = (
            f"\n\n当前上下文信息:\n"
            f"当前日期: {current_date}\n"
            f"股票代码: {ticker}\n"
            f"公司名称: {company_name}\n"
            f"请用中文回答。"
        )
        system_msg_content += context_info

        # 构造输入消息列表
        input_messages = []
        # 1. 添加系统消息
        input_messages.append(SystemMessage(content=system_msg_content))
        
        # 2. 添加历史消息
        history_messages = list(state.get("messages", []))
        if history_messages:
            input_messages.extend(history_messages)
        else:
            # 如果没有历史消息，添加初始指令
            input_messages.append(HumanMessage(content=f"请分析 {company_name} ({ticker})，日期 {current_date}"))

        # 3. 执行 Agent
        if self.agent_executor:
            try:
                logger.info(f"[{self.name}] 🚀 启动 LangGraph ReAct Agent...")
                
                result_state = self.agent_executor.invoke({
                    "messages": input_messages,
                })
                
                result_messages = result_state.get("messages", [])
                
                # 统计工具调用次数 (估算)
                executed_tool_calls = sum(1 for msg in result_messages if isinstance(msg, ToolMessage))
                
                if result_messages and isinstance(result_messages[-1], AIMessage):
                    final_report = result_messages[-1].content
                    logger.info(f"[{self.name}] ✅ Agent 执行完成，报告长度: {len(final_report)}")
                else:
                    logger.warning(f"[{self.name}] ⚠️ Agent 未返回 AIMessage，结果状态: {result_state.keys()}")
                    # 尝试从最后一条消息获取内容，即使它不是 AIMessage (虽然不太可能)
                    if result_messages:
                        final_report = str(result_messages[-1].content)
                    else:
                        final_report = "分析未生成有效内容。"

            except Exception as e:
                import traceback
                logger.error(f"[{self.name}] ❌ Agent 执行崩溃: {e}\n{traceback.format_exc()}")
                final_report = f"分析过程中发生错误: {str(e)}"
        else:
             # 无工具模式：直接调用 LLM
             try:
                 logger.info(f"[{self.name}] ⚠️ 无工具/Agent初始化失败，直接调用 LLM")
                 response = self.llm.invoke(input_messages)
                 final_report = response.content
             except Exception as e:
                 logger.error(f"[{self.name}] ❌ LLM 直接调用失败: {e}")
                 final_report = "无法进行分析。"

        total_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"[{self.name}] 完成，耗时 {total_time:.2f}s")
        
        # 构造返回字典
        internal_key = self.slug.replace("-analyst", "").replace("-", "_")
        
        result = {
            "messages": [AIMessage(content=final_report)],
            f"{internal_key}_tool_call_count": executed_tool_calls,
            "report": final_report
        }
        
        report_key = f"{internal_key}_report"
        result[report_key] = final_report
        logger.info(f"[{self.name}] 📝 报告已写入 state['{report_key}']")
        
        compatibility_mappings = {
            "social_media": "sentiment_report",
            "financial_news": "news_report",
        }
        
        if internal_key in compatibility_mappings:
            compat_key = compatibility_mappings[internal_key]
            result[compat_key] = final_report
            logger.info(f"[{self.name}] 📝 兼容性映射: {report_key} -> {compat_key}")
            
        return result
