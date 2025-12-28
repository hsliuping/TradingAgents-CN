#!/usr/bin/env python3
"""
板块轮动分析师 (Sector Analyst)

职责:
- 分析板块资金流向和涨跌幅
- 识别领涨/领跌板块
- 判断板块轮动特征
- 结合政策分析识别热点主题
"""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import json

from tradingagents.utils.logging_manager import get_logger

logger = get_logger("agents")


def create_sector_analyst(llm, toolkit):
    """
    创建板块轮动分析师节点
    
    Args:
        llm: 语言模型实例
        toolkit: 工具包，包含fetch_sector_rotation等工具
        
    Returns:
        板块分析师节点函数
    """
    
    def sector_analyst_node(state):
        """板块轮动分析师节点"""
        logger.info("💰 [板块分析师] 节点开始")
        
        # 1. 工具调用计数器
        tool_call_count = state.get("sector_tool_call_count", 0)
        max_tool_calls = 5
        logger.info(f"🔧 [死循环修复] 板块分析师工具调用次数: {tool_call_count}/{max_tool_calls}")
        
        # 2. 检查是否已有报告
        existing_report = state.get("sector_report", "")
        if existing_report and len(existing_report) > 100:
            logger.info(f"✅ [板块分析师] 已有报告，跳过分析")
            return {
                "messages": state["messages"],
                "sector_report": existing_report,
                "sector_tool_call_count": tool_call_count
            }
        
        # 3. 降级方案
        if tool_call_count >= max_tool_calls:
            logger.warning(f"⚠️ [板块分析师] 达到最大工具调用次数，返回降级报告")
            fallback_report = json.dumps({
                "top_sectors": ["数据获取受限"],
                "bottom_sectors": ["数据获取受限"],
                "rotation_trend": "无法判断",
                "hot_themes": ["数据获取受限"],
                "analysis_summary": "由于数据获取限制，无法进行完整的板块分析。建议稍后重试。",
                "confidence": 0.3,
                "sentiment_score": 0.0
            }, ensure_ascii=False)
            
            return {
                "messages": state["messages"],
                "sector_report": fallback_report,
                "sector_tool_call_count": tool_call_count
            }
        
        # 4. 读取上游政策报告（用于交叉验证）
        policy_report = state.get("policy_report", "")
        session_type = state.get("session_type", "post")  # 获取会话类型: morning, closing, post
        
        # 获取当前关注的公司/指数（已解析）
        index_info = state.get("index_info", {})
        index_name = index_info.get("name", state.get("company_of_interest", "未知指数"))
        index_symbol = index_info.get("symbol", state.get("company_of_interest", "000001.SH"))
        
        logger.info(f"💰 [板块分析师] 上游政策报告长度: {len(policy_report)} 字符, 会话类型: {session_type}, 关注目标: {index_name} ({index_symbol})")
        
        # 5. 构建Prompt
        system_prompt_base = (
            "你是一位专业的板块轮动分析师，专注于板块资金流向和市场热点分析。\n"
            "\n"
            "⚠️ **核心规则 - 违反将导致系统错误**\n"
            "1. **必须调用工具**：必须调用 `fetch_sector_rotation` 获取资金流向数据，严禁在没有工具数据的情况下编造报告。\n"
            "2. **禁止闲聊**：绝对禁止输出'我理解您希望...'、'我很抱歉...'等任何解释性文字。\n"
            "3. **强制JSON**：如果因为任何原因（如数据缺失、工具失败）无法生成分析，必须直接输出预定义的JSON降级报告（格式见下文）。\n"
            "4. **语言要求**：报告内容必须使用简体中文。\n"
            "\n"
            "📋 **分析任务**\n"
            "- 获取板块资金流向数据\n"
            "- 识别领涨/领跌板块\n"
            "- 判断板块轮动特征\n"
            "- 结合政策方向识别热点主题\n"
            "- **处理指定板块/指数查询**: \n"
            f"  - 系统已将用户查询的目标解析为：**{index_name}** ({index_symbol})。\n"
            f"  - 请直接调用 `fetch_sector_rotation(sector_name='{index_name}')` 获取该目标的详细数据。\n"
            f"  - **严禁**尝试重新解析原始代码（如 '{index_symbol}'），直接使用上述已解析的名称。\n"
            "  - 这样做是为了避免重复的解析工作，并确保与其他分析师使用一致的目标。\n"
            "- **处理个股查询**: 如果输入是具体的个股代码（如 '600519'），请先使用 `fetch_stock_sector_info` 工具查询其所属板块，然后使用 `fetch_sector_rotation` 获取该板块的详细资金流向。\n"
        )
        
        # 根据会话类型注入特定上下文
        time_context = ""
        if session_type == "morning":
            time_context = (
                "\n🕒 **当前是早盘阶段 (09:45)**\n"
                "请重点分析集合竞价成交额前三的板块，以及开盘 15 分钟内资金净流入最快的板块。\n"
                "忽略昨日的旧新闻，专注于当下的资金攻击方向。\n"
            )
        elif session_type == "closing":
            time_context = (
                "\n🕒 **当前是尾盘阶段 (14:45)**\n"
                "请检查是否有板块出现尾盘抢筹现象（最后30分钟量能放大且价格拉升）。\n"
                "这通常预示着明日的主线。\n"
            )
        else:
            time_context = (
                "\n🕒 **当前是盘后复盘阶段**\n"
                "请分析全天的主力资金流向和板块轮动规律，总结今日热点。\n"
            )

        prompt_template = (
            f"{system_prompt_base}"
            f"{time_context}"
            "\n"
            "📊 **分析维度**\n"
            "1. **领涨/领跌板块**\n"
            "   - Top 3-5 涨幅板块\n"
            "   - Bottom 3-5 跌幅板块\n"
            "   - 分析资金流向方向\n"
            "\n"
            "2. **轮动特征判断**\n"
            "   - 成长→价值: 科技板块流出，金融地产流入\n"
            "   - 价值→成长: 传统行业流出，新兴产业流入\n"
            "   - 大盘→小盘: 权重股弱，题材股强\n"
            "   - 防御→进攻: 消费医药流出，周期股流入\n"
            "\n"
            "3. **热点主题挖掘**\n"
            "   - 结合政策报告中的industry_policy\n"
            "   - 如果政策提到\"新能源\" → 关注光伏、储能、新能源车\n"
            "   - 如果政策提到\"自主可控\" → 关注半导体、国防军工\n"
            "   - 如果政策提到\"AI\" → 关注算力、应用、数据\n"
            "\n"
            "4. **个股所属板块分析** (如果是针对个股的查询)\n"
            "   - 指出个股所属的行业板块\n"
            "   - 分析该板块今日的整体表现（涨跌幅、资金流向、排名）\n"
            "   - 判断板块处于强势、弱势还是轮动中\n"
            "\n"
            "5. **情绪评分规则**\n"
            "   - 普涨（多板块上涨）: 0.5 ~ 0.8\n"
            "   - 结构性行情（部分板块涨）: 0.2 ~ 0.5\n"
            "   - 震荡（涨跌平衡）: -0.1 ~ 0.1\n"
            "   - 普跌（多板块下跌）: -0.8 ~ -0.5\n"
            "\n"
            "🔗 **上游政策报告**\n"
            "{policy_report}\n"
            "\n"
            "🎯 **输出要求**\n"
            "请输出两部分内容：\n"
            "\n"
            "### 第一部分：深度板块分析报告（Markdown格式）\n"
            "请撰写一份不少于400字的专业板块轮动分析报告，包含：\n"
            "1. **市场热点复盘**：详细复盘当日领涨板块，分析上涨逻辑（政策驱动/事件驱动/资金推动）。\n"
            "2. **资金流向分析**：深入分析主力资金的流入流出方向，识别机构调仓迹象。\n"
            "3. **板块轮动特征**：判断当前市场风格（如成长vs价值、大盘vs小盘），并预测轮动方向。\n"
            "4. **主题投资机会**：结合上游政策分析，挖掘潜在的热点主题和细分赛道。\n"
            "5. **(可选) 个股板块定位**：如果用户查询了个股，请专门一段分析其所属板块的表现。\n"
            "\n"
            "### 第二部分：结构化数据总结（JSON格式）\n"
            "请在报告末尾，将核心指标提取为JSON格式，包裹在 ```json 代码块中。字段要求如下：\n"
            "```json\n"
            "{{\n"
            "  \"top_sectors\": [\"新能源车\", \"半导体\", \"消费电子\"],\n"
            "  \"bottom_sectors\": [\"房地产\", \"煤炭\", \"钢铁\"],\n"
            "  \"rotation_trend\": \"成长→价值|价值→成长|大盘→小盘等\",\n"
            "  \"hot_themes\": [\"AI\", \"新能源\", \"自主可控\"],\n"
            "  \"analysis_summary\": \"100字以内的精炼总结\",\n"
            "  \"confidence\": 0.0-1.0,\n"
            "  \"sentiment_score\": -1.0到1.0\n"
            "}}\n"
            "```\n"
            "\n"
            "⚠️ **注意事项**\n"
            "- 务必先进行深度分析，展现你的思考过程，供人类投资者参考。\n"
            "- 必须调用fetch_index_constituents获取权重股数据\n"
            "- 结合上游政策报告进行交叉验证\n"
            "- hot_themes必须与政策方向一致\n"
            "- JSON格式必须严格\n"
            "- ❌ **禁止向用户提问**：你是专业的分析师，如果不知道股票的板块，请使用工具查询；如果查询失败，请进行全市场分析，不要反问用户。\n"
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", prompt_template),
            MessagesPlaceholder(variable_name="messages"),
        ])
        
        # 6. 设置prompt变量
        prompt = prompt.partial(
            policy_report=policy_report if policy_report else "暂无政策报告",
            company_of_interest=index_name  # 使用 index_name 作为 company_of_interest 传入
        )
        
        # 7. 绑定工具
        from tradingagents.tools.index_tools import fetch_sector_rotation, fetch_index_constituents, fetch_sector_news, fetch_stock_sector_info
        tools = [fetch_sector_rotation, fetch_index_constituents, fetch_sector_news, fetch_stock_sector_info]
        
        logger.info(f"💰 [板块分析师] 绑定工具: fetch_sector_rotation, fetch_index_constituents, fetch_sector_news, fetch_stock_sector_info")
        
        chain = prompt | llm.bind_tools(tools)
        
        # 8. 调用LLM
        logger.info(f"💰 [板块分析师] 开始调用LLM...")
        result = chain.invoke({"messages": state["messages"]})
        logger.info(f"💰 [板块分析师] LLM调用完成")
        
        # 9. 处理结果
        has_tool_calls = hasattr(result, 'tool_calls') and result.tool_calls and len(result.tool_calls) > 0
        
        if has_tool_calls:
            logger.info(f"💰 [板块分析师] 检测到工具调用，返回等待工具执行")
            return {
                "messages": [result],
                "sector_tool_call_count": tool_call_count + 1
            }
        
        # 10. 直接使用完整回复作为报告（包含Markdown分析和JSON总结）
        # 下游的 Strategy Advisor 会使用 extract_json_block 自动提取 JSON 部分
        # 前端的 Report Exporter 会自动识别混合内容并进行展示
        report = result.content
        
        logger.info(f"✅ [板块分析师] 生成完整分析报告: {len(report)} 字符")
        
        # 11. 返回状态更新
        return {
            "messages": [result],
            "sector_report": report,
            "sector_tool_call_count": tool_call_count + 1
        }
    
    return sector_analyst_node


def _extract_json_report(content: str) -> str:
    """从LLM回复中提取JSON报告"""
    try:
        if '{' in content and '}' in content:
            start_idx = content.index('{')
            end_idx = content.rindex('}') + 1
            json_str = content[start_idx:end_idx]
            
            # 验证JSON有效性
            json.loads(json_str)
            
            logger.info(f"✅ [板块分析师] JSON提取成功")
            return json_str
        else:
            logger.warning(f"⚠️ [板块分析师] 内容中未找到JSON标记")
            return ""
    
    except json.JSONDecodeError as e:
        logger.warning(f"⚠️ [板块分析师] JSON解析失败: {e}")
        return ""
    except Exception as e:
        logger.error(f"❌ [板块分析师] JSON提取异常: {e}")
        return ""
