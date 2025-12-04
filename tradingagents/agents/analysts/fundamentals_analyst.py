"""
基本面分析师 - 统一工具架构版本
使用统一工具自动识别股票类型并调用相应数据源
"""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage, ToolMessage

# 导入分析模块日志装饰器
from tradingagents.utils.tool_logging import log_analyst_module

# 导入统一日志系统
from tradingagents.utils.logging_init import get_logger
logger = get_logger("default")

# 导入Google工具调用处理器
from tradingagents.agents.utils.google_tool_handler import GoogleToolCallHandler


def _get_company_name_for_fundamentals(ticker: str, market_info: dict) -> str:
    """
    为基本面分析师获取公司名称

    Args:
        ticker: 股票代码
        market_info: 市场信息字典

    Returns:
        str: 公司名称
    """
    try:
        if market_info['is_china']:
            # 中国A股：使用统一接口获取股票信息
            from tradingagents.dataflows.interface import get_china_stock_info_unified
            stock_info = get_china_stock_info_unified(ticker)

            logger.debug(f"📊 [基本面分析师] 获取股票信息返回: {stock_info[:200] if stock_info else 'None'}...")

            # 解析股票名称
            if stock_info and "股票名称:" in stock_info:
                company_name = stock_info.split("股票名称:")[1].split("\n")[0].strip()
                logger.info(f"✅ [基本面分析师] 成功获取中国股票名称: {ticker} -> {company_name}")
                return company_name
            else:
                # 降级方案：尝试直接从数据源管理器获取
                logger.warning(f"⚠️ [基本面分析师] 无法从统一接口解析股票名称: {ticker}，尝试降级方案")
                try:
                    from tradingagents.dataflows.data_source_manager import get_china_stock_info_unified as get_info_dict
                    info_dict = get_info_dict(ticker)
                    if info_dict and info_dict.get('name'):
                        company_name = info_dict['name']
                        logger.info(f"✅ [基本面分析师] 降级方案成功获取股票名称: {ticker} -> {company_name}")
                        return company_name
                except Exception as e:
                    logger.error(f"❌ [基本面分析师] 降级方案也失败: {e}")

                logger.error(f"❌ [基本面分析师] 所有方案都无法获取股票名称: {ticker}")
                return f"股票代码{ticker}"

        elif market_info['is_hk']:
            # 港股：使用改进的港股工具
            try:
                from tradingagents.dataflows.providers.hk.improved_hk import get_hk_company_name_improved
                company_name = get_hk_company_name_improved(ticker)
                logger.debug(f"📊 [基本面分析师] 使用改进港股工具获取名称: {ticker} -> {company_name}")
                return company_name
            except Exception as e:
                logger.debug(f"📊 [基本面分析师] 改进港股工具获取名称失败: {e}")
                # 降级方案：生成友好的默认名称
                clean_ticker = ticker.replace('.HK', '').replace('.hk', '')
                return f"港股{clean_ticker}"

        elif market_info['is_us']:
            # 美股：使用简单映射或返回代码
            us_stock_names = {
                'AAPL': '苹果公司',
                'TSLA': '特斯拉',
                'NVDA': '英伟达',
                'MSFT': '微软',
                'GOOGL': '谷歌',
                'AMZN': '亚马逊',
                'META': 'Meta',
                'NFLX': '奈飞'
            }

            company_name = us_stock_names.get(ticker.upper(), f"美股{ticker}")
            logger.debug(f"📊 [基本面分析师] 美股名称映射: {ticker} -> {company_name}")
            return company_name

        else:
            return f"股票{ticker}"

    except Exception as e:
        logger.error(f"❌ [基本面分析师] 获取公司名称失败: {e}")
        return f"股票{ticker}"


def create_fundamentals_analyst(llm, toolkit):
    @log_analyst_module("fundamentals")
    def fundamentals_analyst_node(state):
        logger.debug(f"📊 [DEBUG] ===== 基本面分析师节点开始 =====")

        # 🔧 工具调用计数器 - 防止无限循环
        # 检查消息历史中是否有 ToolMessage，如果有则说明工具已执行过
        messages = state.get("messages", [])
        tool_message_count = sum(1 for msg in messages if isinstance(msg, ToolMessage))

        tool_call_count = state.get("fundamentals_tool_call_count", 0)
        max_tool_calls = 1  # 最大工具调用次数：一次工具调用就能获取所有数据

        # 如果有新的 ToolMessage，更新计数器
        if tool_message_count > tool_call_count:
            tool_call_count = tool_message_count
            logger.info(f"🔧 [工具调用计数] 检测到新的工具结果，更新计数器: {tool_call_count}")

        logger.info(f"🔧 [工具调用计数] 当前工具调用次数: {tool_call_count}/{max_tool_calls}")

        current_date = state["trade_date"]
        ticker = state["company_of_interest"]

        # 🔧 基本面分析数据范围：固定获取10天数据（处理周末/节假日/数据延迟）
        # 参考文档：docs/ANALYST_DATA_CONFIGURATION.md
        # 基本面分析主要依赖财务数据（PE、PB、ROE等），只需要当前股价
        # 获取10天数据是为了保证能拿到数据，但实际分析只使用最近2天
        from datetime import datetime, timedelta
        try:
            end_date_dt = datetime.strptime(current_date, "%Y-%m-%d")
            start_date_dt = end_date_dt - timedelta(days=10)
            start_date = start_date_dt.strftime("%Y-%m-%d")
            logger.info(f"📅 [基本面分析师] 数据范围: {start_date} 至 {current_date} (固定10天)")
        except Exception as e:
            # 如果日期解析失败，使用默认10天前
            logger.warning(f"⚠️ [基本面分析师] 日期解析失败，使用默认范围: {e}")
            start_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")

        logger.debug(f"📊 [DEBUG] 输入参数: ticker={ticker}, date={current_date}")
        logger.debug(f"📊 [DEBUG] 当前状态中的消息数量: {len(state.get('messages', []))}")
        logger.debug(f"📊 [DEBUG] 现有基本面报告: {state.get('fundamentals_report', 'None')}")

        # 获取股票市场信息
        from tradingagents.utils.stock_utils import StockUtils
        logger.info(f"📊 [基本面分析师] 正在分析股票: {ticker}")

        # 添加详细的股票代码追踪日志
        logger.info(f"🔍 [股票代码追踪] 基本面分析师接收到的原始股票代码: '{ticker}' (类型: {type(ticker)})")
        logger.info(f"🔍 [股票代码追踪] 股票代码长度: {len(str(ticker))}")
        logger.info(f"🔍 [股票代码追踪] 股票代码字符: {list(str(ticker))}")

        market_info = StockUtils.get_market_info(ticker)
        logger.info(f"🔍 [股票代码追踪] StockUtils.get_market_info 返回的市场信息: {market_info}")

        logger.debug(f"📊 [DEBUG] 股票类型检查: {ticker} -> {market_info['market_name']} ({market_info['currency_name']}")
        logger.debug(f"📊 [DEBUG] 详细市场信息: is_china={market_info['is_china']}, is_hk={market_info['is_hk']}, is_us={market_info['is_us']}")
        logger.debug(f"📊 [DEBUG] 工具配置检查: online_tools={toolkit.config['online_tools']}")

        # 获取公司名称
        company_name = _get_company_name_for_fundamentals(ticker, market_info)
        logger.debug(f"📊 [DEBUG] 公司名称: {ticker} -> {company_name}")

        # 统一使用 get_stock_fundamentals_unified 工具
        # 该工具内部会自动识别股票类型（A股/港股/美股）并调用相应的数据源
        # 对于A股，它会自动获取价格数据和基本面数据，无需LLM调用多个工具
        logger.info(f"📊 [基本面分析师] 使用统一基本面分析工具，自动识别股票类型")
        tools = [toolkit.get_stock_fundamentals_unified]

        # 安全地获取工具名称用于调试
        tool_names_debug = []
        for tool in tools:
            if hasattr(tool, 'name'):
                tool_names_debug.append(tool.name)
            elif hasattr(tool, '__name__'):
                tool_names_debug.append(tool.__name__)
            else:
                tool_names_debug.append(str(tool))
        logger.info(f"📊 [基本面分析师] 绑定的工具: {tool_names_debug}")
        logger.info(f"📊 [基本面分析师] 目标市场: {market_info['market_name']}")

        # 统一的系统提示，适用于所有股票类型
        system_message = (
            f"你是一位专业的股票基本面分析师。"
            f"⚠️ 绝对强制要求：你必须调用工具获取真实数据！不允许任何假设或编造！"
            f"任务：分析{company_name}（股票代码：{ticker}，{market_info['market_name']}）"
            f"🔴 立即调用 get_stock_fundamentals_unified 工具"
            f"参数：ticker='{ticker}', start_date='{start_date}', end_date='{current_date}', curr_date='{current_date}'"
            "📊 分析要求："
            "- 基于真实数据进行深度基本面分析"
            f"- 计算并提供合理价位区间（使用{market_info['currency_name']}{market_info['currency_symbol']}）"
            "- 分析当前股价是否被低估或高估"
            "- 提供基于基本面的目标价位建议"
            "- 包含PE、PB、PEG等估值指标分析"
            "- 结合市场特点进行分析"
            "🌍 语言和货币要求："
            "- 所有分析内容必须使用中文"
            "- 投资建议必须使用中文：买入、持有、卖出"
            "- 绝对不允许使用英文：buy、hold、sell"
            f"- 货币单位使用：{market_info['currency_name']}（{market_info['currency_symbol']}）"
            "🚫 严格禁止："
            "- 不允许说'我将调用工具'"
            "- 不允许假设任何数据"
            "- 不允许编造公司信息"
            "- 不允许直接回答而不调用工具"
            "- 不允许回复'无法确定价位'或'需要更多信息'"
            "- 不允许使用英文投资建议（buy/hold/sell）"
            "✅ 你必须："
            "- 立即调用统一基本面分析工具"
            "- 等待工具返回真实数据"
            "- 基于真实数据进行分析"
            "- 提供具体的价位区间和目标价"
            "- 使用中文投资建议（买入/持有/卖出）"
            "现在立即开始调用工具！不要说任何其他话！"
        )

        # 系统提示模板
        system_prompt = (
            "🔴 强制要求：你必须调用工具获取真实数据！"
            "🚫 绝对禁止：不允许假设、编造或直接回答任何问题！"
            "✅ 工作流程："
            "1. 【第一次调用】如果消息历史中没有工具结果（ToolMessage），立即调用 get_stock_fundamentals_unified 工具"
            "2. 【收到数据后】如果消息历史中已经有工具结果（ToolMessage），🚨 绝对禁止再次调用工具！🚨"
            "3. 【生成报告】收到工具数据后，必须立即生成完整的基本面分析报告，包含："
            "   - 公司基本信息和财务数据分析"
            "   - PE、PB、PEG等估值指标分析"
            "   - 当前股价是否被低估或高估的判断"
            "   - 合理价位区间和目标价位建议"
            "   - 基于基本面的投资建议（买入/持有/卖出）"
            "4. 🚨 重要：工具只需调用一次！一次调用返回所有需要的数据！不要重复调用！🚨"
            "5. 🚨 如果你已经看到ToolMessage，说明工具已经返回数据，直接生成报告，不要再调用工具！🚨"
            "可用工具：{tool_names}。\n{system_message}"
            "当前日期：{current_date}。"
            "分析目标：{company_name}（股票代码：{ticker}）。"
            "请确保在分析中正确区分公司名称和股票代码。"
        )

        # 创建提示模板
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="messages"),
        ])

        prompt = prompt.partial(system_message=system_message)
        # 安全地获取工具名称，处理函数和工具对象
        tool_names = []
        for tool in tools:
            if hasattr(tool, 'name'):
                tool_names.append(tool.name)
            elif hasattr(tool, '__name__'):
                tool_names.append(tool.__name__)
            else:
                tool_names.append(str(tool))

        prompt = prompt.partial(tool_names=", ".join(tool_names))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(ticker=ticker)
        prompt = prompt.partial(company_name=company_name)

        # 检测阿里百炼模型并创建新实例
        if hasattr(llm, '__class__') and 'DashScope' in llm.__class__.__name__:
            logger.debug(f"📊 [DEBUG] 检测到阿里百炼模型，创建新实例以避免工具缓存")
            from tradingagents.llm_adapters import ChatDashScopeOpenAI

            # 获取原始 LLM 的 base_url 和 api_key
            original_base_url = getattr(llm, 'openai_api_base', None)
            original_api_key = getattr(llm, 'openai_api_key', None)

            fresh_llm = ChatDashScopeOpenAI(
                model=llm.model_name,
                api_key=original_api_key,  # 🔥 传递原始 LLM 的 API Key
                base_url=original_base_url if original_base_url else None,  # 传递 base_url
                temperature=llm.temperature,
                max_tokens=getattr(llm, 'max_tokens', 2000)
            )

            if original_base_url:
                logger.debug(f"📊 [DEBUG] 新实例使用原始 base_url: {original_base_url}")
            if original_api_key:
                logger.debug(f"📊 [DEBUG] 新实例使用原始 API Key（来自数据库配置）")
        else:
            fresh_llm = llm

        logger.debug(f"📊 [DEBUG] 创建LLM链，工具数量: {len(tools)}")
        # 安全地获取工具名称用于调试
        debug_tool_names = []
        for tool in tools:
            if hasattr(tool, 'name'):
                debug_tool_names.append(tool.name)
            elif hasattr(tool, '__name__'):
                debug_tool_names.append(tool.__name__)
            else:
                debug_tool_names.append(str(tool))
        logger.debug(f"📊 [DEBUG] 绑定的工具列表: {debug_tool_names}")
        logger.debug(f"📊 [DEBUG] 创建工具链，让模型自主决定是否调用工具")

        # 添加详细日志
        logger.info(f"📊 [基本面分析师] LLM类型: {fresh_llm.__class__.__name__}")
        logger.info(f"📊 [基本面分析师] LLM模型: {getattr(fresh_llm, 'model_name', 'unknown')}")
        logger.info(f"📊 [基本面分析师] 消息历史数量: {len(state['messages'])}")

        try:
            chain = prompt | fresh_llm.bind_tools(tools)
            logger.info(f"📊 [基本面分析师] ✅ 工具绑定成功，绑定了 {len(tools)} 个工具")
        except Exception as e:
            logger.error(f"📊 [基本面分析师] ❌ 工具绑定失败: {e}")
            raise e

        logger.info(f"📊 [基本面分析师] 开始调用LLM...")

        # 添加详细的股票代码追踪日志
        logger.info(f"🔍 [股票代码追踪] LLM调用前，ticker参数: '{ticker}'")
        logger.info(f"🔍 [股票代码追踪] 传递给LLM的消息数量: {len(state['messages'])}")

        # 🔥 打印提交给大模型的完整内容
        logger.info("=" * 80)
        logger.info("📝 [提示词调试] 开始打印提交给大模型的完整内容")
        logger.info("=" * 80)

        # 1. 打印系统提示词
        logger.info("📋 [提示词调试] 1️⃣ 系统提示词 (System Message):")
        logger.info("-" * 80)
        logger.info(system_message)
        logger.info("-" * 80)

        # 2. 打印完整的提示模板
        logger.info("📋 [提示词调试] 2️⃣ 完整提示模板 (Prompt Template):")
        logger.info("-" * 80)
        logger.info(f"工具名称: {', '.join(tool_names)}")
        logger.info(f"当前日期: {current_date}")
        logger.info(f"股票代码: {ticker}")
        logger.info(f"公司名称: {company_name}")
        logger.info("-" * 80)

        # 3. 打印消息历史
        logger.info("📋 [提示词调试] 3️⃣ 消息历史 (Message History):")
        logger.info("-" * 80)
        for i, msg in enumerate(state['messages']):
            msg_type = type(msg).__name__
            if hasattr(msg, 'content'):
                # 🔥 调试模式：打印完整内容，不截断
                content_full = str(msg.content)
                logger.info(f"消息 {i+1} [{msg_type}]:")
                logger.info(f"  内容长度: {len(content_full)} 字符")
                logger.info(f"  内容: {content_full}")
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                logger.info(f"  工具调用: {[tc.get('name', 'unknown') for tc in msg.tool_calls]}")
            if hasattr(msg, 'name'):
                logger.info(f"  工具名称: {msg.name}")
            logger.info("-" * 40)
        logger.info("-" * 80)

        # 4. 打印绑定的工具信息
        logger.info("📋 [提示词调试] 4️⃣ 绑定的工具 (Bound Tools):")
        logger.info("-" * 80)
        for i, tool in enumerate(tools):
            tool_name = getattr(tool, 'name', None) or getattr(tool, '__name__', 'unknown')
            tool_desc = getattr(tool, 'description', 'No description')
            logger.info(f"工具 {i+1}: {tool_name}")
            logger.info(f"  描述: {tool_desc}")
            if hasattr(tool, 'args_schema'):
                logger.info(f"  参数: {tool.args_schema}")
            logger.info("-" * 40)
        logger.info("-" * 80)

        logger.info("=" * 80)
        logger.info("📝 [提示词调试] 完整内容打印结束，开始调用LLM")
        logger.info("=" * 80)

        # 修复：传递字典而不是直接传递消息列表，以便 ChatPromptTemplate 能正确处理所有变量
        result = chain.invoke({"messages": state["messages"]})
        logger.info(f"📊 [基本面分析师] LLM调用完成")
        
        # 🔍 [调试日志] 打印AIMessage的详细内容
        logger.info(f"🤖 [基本面分析师] AIMessage详细内容:")
        logger.info(f"🤖 [基本面分析师] - 消息类型: {type(result).__name__}")
        logger.info(f"🤖 [基本面分析师] - 内容长度: {len(result.content) if hasattr(result, 'content') else 0}")
        if hasattr(result, 'content') and result.content:
            # 🔥 调试模式：打印完整内容，不截断
            logger.info(f"🤖 [基本面分析师] - 完整内容:")
            logger.info(f"{result.content}")
        
        # 🔍 [调试日志] 打印tool_calls的详细信息
        # 详细记录 LLM 返回结果
        logger.info(f"📊 [基本面分析师] ===== LLM返回结果分析 =====")
        logger.info(f"📊 [基本面分析师] - 结果类型: {type(result).__name__}")
        logger.info(f"📊 [基本面分析师] - 是否有tool_calls属性: {hasattr(result, 'tool_calls')}")

        if hasattr(result, 'content'):
            content_preview = str(result.content)[:200] if result.content else "None"
            logger.info(f"📊 [基本面分析师] - 内容长度: {len(str(result.content)) if result.content else 0}")
            logger.info(f"📊 [基本面分析师] - 内容预览: {content_preview}...")

        if hasattr(result, 'tool_calls'):
            logger.info(f"📊 [基本面分析师] - tool_calls数量: {len(result.tool_calls)}")
            if result.tool_calls:
                logger.info(f"🔧 [基本面分析师] 检测到 {len(result.tool_calls)} 个工具调用:")
                for i, tc in enumerate(result.tool_calls):
                    logger.info(f"🔧 [基本面分析师] - 工具调用 {i+1}: {tc.get('name', 'unknown')} (ID: {tc.get('id', 'unknown')})")
                    if 'args' in tc:
                        logger.info(f"🔧 [基本面分析师] - 参数: {tc['args']}")
            else:
                logger.info(f"🔧 [基本面分析师] tool_calls为空列表")
        else:
            logger.info(f"🔧 [基本面分析师] 无tool_calls属性")

        logger.info(f"📊 [基本面分析师] ===== LLM返回结果分析结束 =====")

        # 使用统一的Google工具调用处理器
        if GoogleToolCallHandler.is_google_model(fresh_llm):
            logger.info(f"📊 [基本面分析师] 检测到Google模型，使用统一工具调用处理器")
            
            # 创建分析提示词
            analysis_prompt_template = GoogleToolCallHandler.create_analysis_prompt(
                ticker=ticker,
                company_name=company_name,
                analyst_type="基本面分析",
                specific_requirements="重点关注财务数据、盈利能力、估值指标、行业地位等基本面因素。"
            )
            
            # 处理Google模型工具调用
            report, messages = GoogleToolCallHandler.handle_google_tool_calls(
                result=result,
                llm=fresh_llm,
                tools=tools,
                state=state,
                analysis_prompt_template=analysis_prompt_template,
                analyst_name="基本面分析师"
            )

            return {"fundamentals_report": report}
        else:
            # 非Google模型的处理逻辑
            logger.debug(f"📊 [DEBUG] 非Google模型 ({fresh_llm.__class__.__name__})，使用标准处理逻辑")
            
            # 检查工具调用情况
            current_tool_calls = len(result.tool_calls) if hasattr(result, 'tool_calls') else 0
            logger.debug(f"📊 [DEBUG] 当前消息的工具调用数量: {current_tool_calls}")
            logger.debug(f"📊 [DEBUG] 累计工具调用次数: {tool_call_count}/{max_tool_calls}")

            if current_tool_calls > 0:
                # 🔧 检查是否已经调用过工具（消息历史中有 ToolMessage）
                messages = state.get("messages", [])
                has_tool_result = any(isinstance(msg, ToolMessage) for msg in messages)

                if has_tool_result:
                    # 已经有工具结果了，LLM 不应该再调用工具，强制生成报告
                    logger.warning(f"⚠️ [强制生成报告] 工具已返回数据，但LLM仍尝试调用工具，强制基于现有数据生成报告")

                    # 创建专门的强制报告提示词（不提及工具）
                    force_system_prompt = (
                        f"你是专业的股票基本面分析师。"
                        f"你已经收到了股票 {company_name}（代码：{ticker}）的基本面数据。"
                        f"🚨 现在你必须基于这些数据生成完整的基本面分析报告！🚨\n\n"
                        f"报告必须包含以下内容：\n"
                        f"1. 公司基本信息和财务数据分析\n"
                        f"2. PE、PB、PEG等估值指标分析\n"
                        f"3. 当前股价是否被低估或高估的判断\n"
                        f"4. 合理价位区间和目标价位建议\n"
                        f"5. 基于基本面的投资建议（买入/持有/卖出）\n\n"
                        f"要求：\n"
                        f"- 使用中文撰写报告\n"
                        f"- 基于消息历史中的真实数据进行分析\n"
                        f"- 分析要详细且专业\n"
                        f"- 投资建议必须明确（买入/持有/卖出）"
                    )

                    # 创建专门的提示模板（不绑定工具）
                    force_prompt = ChatPromptTemplate.from_messages([
                        ("system", force_system_prompt),
                        MessagesPlaceholder(variable_name="messages"),
                    ])

                    # 不绑定工具，强制LLM生成文本
                    force_chain = force_prompt | fresh_llm

                    logger.info(f"🔧 [强制生成报告] 使用专门的提示词重新调用LLM...")
                    force_result = force_chain.invoke({"messages": messages})

                    report = str(force_result.content) if hasattr(force_result, 'content') else "基本面分析完成"
                    logger.info(f"✅ [强制生成报告] 成功生成报告，长度: {len(report)}字符")

                    return {
                        "fundamentals_report": report,
                        "messages": [force_result],
                        "fundamentals_tool_call_count": tool_call_count
                    }

                elif tool_call_count >= max_tool_calls:
                    # 达到最大调用次数，但还没有工具结果（不应该发生）
                    logger.warning(f"🔧 [异常情况] 达到最大工具调用次数 {max_tool_calls}，但没有工具结果")
                    fallback_report = f"基本面分析（股票代码：{ticker}）\n\n由于达到最大工具调用次数限制，使用简化分析模式。建议检查数据源连接或降低分析复杂度。"
                    return {
                        "messages": [result],
                        "fundamentals_report": fallback_report,
                        "fundamentals_tool_call_count": tool_call_count
                    }
                else:
                    # 第一次调用工具，正常流程
                    logger.info(f"✅ [正常流程] ===== LLM第一次调用工具 =====")
                    tool_calls_info = []
                    for tc in result.tool_calls:
                        tool_calls_info.append(tc['name'])
                        logger.debug(f"📊 [DEBUG] 工具调用 {len(tool_calls_info)}: {tc}")

                    logger.info(f"📊 [正常流程] LLM请求调用工具: {tool_calls_info}")
                    logger.info(f"📊 [正常流程] 工具调用数量: {len(tool_calls_info)}")
                    logger.info(f"📊 [正常流程] 返回状态，等待工具执行")
                    # ⚠️ 注意：不要在这里增加计数器！
                    # 计数器应该在工具执行完成后（下一次进入分析师节点时）才增加
                    return {
                        "messages": [result]
                    }
            else:
                # 没有工具调用，检查是否需要强制调用工具
                logger.info(f"📊 [基本面分析师] ===== 强制工具调用检查开始 =====")
                logger.debug(f"📊 [DEBUG] 检测到模型未调用工具，检查是否需要强制调用")

                # 方案1：检查消息历史中是否已经有工具返回的数据
                messages = state.get("messages", [])
                logger.info(f"🔍 [消息历史] 当前消息总数: {len(messages)}")

                # 统计各类消息数量
                ai_message_count = sum(1 for msg in messages if isinstance(msg, AIMessage))
                tool_message_count = sum(1 for msg in messages if isinstance(msg, ToolMessage))
                logger.info(f"🔍 [消息历史] AIMessage数量: {ai_message_count}, ToolMessage数量: {tool_message_count}")

                # 记录最近几条消息的类型
                recent_messages = messages[-5:] if len(messages) >= 5 else messages
                logger.info(f"🔍 [消息历史] 最近{len(recent_messages)}条消息类型: {[type(msg).__name__ for msg in recent_messages]}")

                has_tool_result = any(isinstance(msg, ToolMessage) for msg in messages)
                logger.info(f"🔍 [检查结果] 是否有工具返回结果: {has_tool_result}")

                # 方案2：检查 AIMessage 是否已有分析内容
                has_analysis_content = False
                if hasattr(result, 'content') and result.content:
                    content_length = len(str(result.content))
                    logger.info(f"🔍 [内容检查] LLM返回内容长度: {content_length}字符")
                    # 如果内容长度超过500字符，认为是有效的分析内容
                    if content_length > 500:
                        has_analysis_content = True
                        logger.info(f"✅ [内容检查] LLM已返回有效分析内容 (长度: {content_length}字符 > 500字符阈值)")
                    else:
                        logger.info(f"⚠️ [内容检查] LLM返回内容较短 (长度: {content_length}字符 < 500字符阈值)")
                else:
                    logger.info(f"⚠️ [内容检查] LLM未返回内容或内容为空")

                # 方案3：统计工具调用次数
                tool_call_count = sum(1 for msg in messages if isinstance(msg, ToolMessage))
                logger.info(f"🔍 [统计] 历史工具调用次数: {tool_call_count}")

                logger.info(f"🔍 [重复调用检查] 汇总 - 工具结果数: {tool_call_count}, 已有工具结果: {has_tool_result}, 已有分析内容: {has_analysis_content}")
                logger.info(f"📊 [基本面分析师] ===== 强制工具调用检查结束 =====")

                # 如果已经有工具结果或已有分析内容，跳过强制调用
                if has_tool_result or has_analysis_content:
                    logger.info(f"🚫 [决策] ===== 跳过强制工具调用 =====")
                    if has_tool_result:
                        logger.info(f"⚠️ [决策原因] 检测到已有 {tool_call_count} 次工具调用结果，避免重复调用")
                    if has_analysis_content:
                        logger.info(f"⚠️ [决策原因] LLM已返回有效分析内容，无需强制工具调用")

                    # 直接使用 LLM 返回的内容作为报告
                    report = str(result.content) if hasattr(result, 'content') else "基本面分析完成"
                    logger.info(f"📊 [返回结果] 使用LLM返回的分析内容，报告长度: {len(report)}字符")
                    logger.info(f"📊 [返回结果] 报告预览(前200字符): {report[:200]}...")
                    logger.info(f"✅ [决策] 基本面分析完成，跳过重复调用成功")

                    # 🔧 保持工具调用计数器不变（已在开始时根据ToolMessage更新）
                    return {
                        "fundamentals_report": report,
                        "messages": [result],
                        "fundamentals_tool_call_count": tool_call_count
                    }

                # 如果没有工具结果且没有分析内容，才进行强制调用
                logger.info(f"🔧 [决策] ===== 执行强制工具调用 =====")
                logger.info(f"🔧 [决策原因] 未检测到工具结果或分析内容，需要获取基本面数据")
                logger.info(f"🔧 [决策] 启用强制工具调用模式")

                # 强制调用统一基本面分析工具
                try:
                    logger.debug(f"📊 [DEBUG] 强制调用 get_stock_fundamentals_unified...")
                    # 安全地查找统一基本面分析工具
                    unified_tool = None
                    for tool in tools:
                        tool_name = None
                        if hasattr(tool, 'name'):
                            tool_name = tool.name
                        elif hasattr(tool, '__name__'):
                            tool_name = tool.__name__

                        if tool_name == 'get_stock_fundamentals_unified':
                            unified_tool = tool
                            break
                    if unified_tool:
                        logger.info(f"🔍 [工具调用] 找到统一工具，准备强制调用")
                        logger.info(f"🔍 [工具调用] 传入参数 - ticker: '{ticker}', start_date: {start_date}, end_date: {current_date}")

                        combined_data = unified_tool.invoke({
                            'ticker': ticker,
                            'start_date': start_date,
                            'end_date': current_date,
                            'curr_date': current_date
                        })

                        logger.info(f"✅ [工具调用] 统一工具调用成功")
                        logger.info(f"📊 [工具调用] 返回数据长度: {len(combined_data)}字符")
                        logger.debug(f"📊 [DEBUG] 统一工具数据获取成功，长度: {len(combined_data)}字符")
                        # 将统一工具返回的数据写入日志，便于排查与分析
                        try:
                            if isinstance(combined_data, (dict, list)):
                                import json
                                _preview = json.dumps(combined_data, ensure_ascii=False, default=str)
                                _full = _preview
                            else:
                                _preview = str(combined_data)
                                _full = _preview

                            # 预览信息控制长度，避免日志过长
                            _preview_truncated = (_preview[:6000] + ("..." if len(_preview) > 2000 else ""))
                            logger.info(f"📦 [基本面分析师] 统一工具返回数据预览(前6000字符):\n{_preview_truncated}")
                            # 完整数据写入DEBUG级别
                            logger.debug(f"🧾 [基本面分析师] 统一工具返回完整数据:\n{_full}")
                        except Exception as _log_err:
                            logger.warning(f"⚠️ [基本面分析师] 记录统一工具数据时出错: {_log_err}")
                    else:
                        combined_data = "统一基本面分析工具不可用"
                        logger.debug(f"📊 [DEBUG] 统一工具未找到")
                except Exception as e:
                    combined_data = f"统一基本面分析工具调用失败: {e}"
                    logger.debug(f"📊 [DEBUG] 统一工具调用异常: {e}")
                
                currency_info = f"{market_info['currency_name']}（{market_info['currency_symbol']}）"
                
                # 生成基于真实数据的分析报告
                analysis_prompt = f"""基于以下真实数据，对{company_name}（股票代码：{ticker}）进行详细的基本面分析：

{combined_data}

请提供：
1. 公司基本信息分析（{company_name}，股票代码：{ticker}）
2. 财务状况评估
3. 盈利能力分析
4. 估值分析（使用{currency_info}）
5. 投资建议（买入/持有/卖出）

要求：
- 基于提供的真实数据进行分析
- 正确使用公司名称"{company_name}"和股票代码"{ticker}"
- 价格使用{currency_info}
- 投资建议使用中文
- 分析要详细且专业"""

                try:
                    # 创建简单的分析链
                    analysis_prompt_template = ChatPromptTemplate.from_messages([
                        ("system", "你是专业的股票基本面分析师，基于提供的真实数据进行分析。"),
                        ("human", "{analysis_request}")
                    ])
                    
                    analysis_chain = analysis_prompt_template | fresh_llm
                    analysis_result = analysis_chain.invoke({"analysis_request": analysis_prompt})
                    
                    if hasattr(analysis_result, 'content'):
                        report = analysis_result.content
                    else:
                        report = str(analysis_result)

                    logger.info(f"📊 [基本面分析师] 强制工具调用完成，报告长度: {len(report)}")

                except Exception as e:
                    logger.error(f"❌ [DEBUG] 强制工具调用分析失败: {e}")
                    report = f"基本面分析失败：{str(e)}"

                # 🔧 保持工具调用计数器不变（已在开始时根据ToolMessage更新）
                return {
                    "fundamentals_report": report,
                    "fundamentals_tool_call_count": tool_call_count
                }

        # 这里不应该到达，但作为备用
        logger.debug(f"📊 [DEBUG] 返回状态: fundamentals_report长度={len(result.content) if hasattr(result, 'content') else 0}")
        # 🔧 保持工具调用计数器不变（已在开始时根据ToolMessage更新）
        return {
            "messages": [result],
            "fundamentals_report": result.content if hasattr(result, 'content') else str(result),
            "fundamentals_tool_call_count": tool_call_count
        }

    return fundamentals_analyst_node
