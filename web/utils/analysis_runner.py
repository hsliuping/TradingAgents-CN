"""
股票分析执行工具
"""

import sys
import os
import uuid
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger, get_logger_manager
logger = get_logger('web')

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 确保环境变量正确加载
load_dotenv(project_root / ".env", override=True)

# 导入统一日志系统
from tradingagents.utils.logging_init import setup_web_logging
logger = setup_web_logging()

# 添加配置管理器
try:
    from tradingagents.config.config_manager import token_tracker
    TOKEN_TRACKING_ENABLED = True
    logger.info("✅ Token跟踪功能已启用")
except ImportError:
    TOKEN_TRACKING_ENABLED = False
    logger.warning("⚠️ Token跟踪功能未启用")

def translate_analyst_labels(text):
    """将分析师的英文标签转换为中文"""
    if not text:
        return text

    # 分析师标签翻译映射
    translations = {
        'Bull Analyst:': '看涨分析师:',
        'Bear Analyst:': '看跌分析师:',
        'Risky Analyst:': '激进风险分析师:',
        'Safe Analyst:': '保守风险分析师:',
        'Neutral Analyst:': '中性风险分析师:',
        'Research Manager:': '研究经理:',
        'Portfolio Manager:': '投资组合经理:',
        'Risk Judge:': '风险管理委员会:',
        'Trader:': '交易员:'
    }

    # 替换所有英文标签
    for english, chinese in translations.items():
        text = text.replace(english, chinese)

    return text

def extract_risk_assessment(state):
    """从分析状态中提取风险评估数据"""
    try:
        risk_debate_state = state.get('risk_debate_state', {})

        if not risk_debate_state:
            return None

        # 提取各个风险分析师的观点并进行中文化
        risky_analysis = translate_analyst_labels(risk_debate_state.get('risky_history', ''))
        safe_analysis = translate_analyst_labels(risk_debate_state.get('safe_history', ''))
        neutral_analysis = translate_analyst_labels(risk_debate_state.get('neutral_history', ''))
        judge_decision = translate_analyst_labels(risk_debate_state.get('judge_decision', ''))

        # 格式化风险评估报告
        risk_assessment = f"""
## ⚠️ 风险评估报告

### 🔴 激进风险分析师观点
{risky_analysis if risky_analysis else '暂无激进风险分析'}

### 🟡 中性风险分析师观点
{neutral_analysis if neutral_analysis else '暂无中性风险分析'}

### 🟢 保守风险分析师观点
{safe_analysis if safe_analysis else '暂无保守风险分析'}

### 🏛️ 风险管理委员会最终决议
{judge_decision if judge_decision else '暂无风险管理决议'}

---
*风险评估基于多角度分析，请结合个人风险承受能力做出投资决策*
        """.strip()

        return risk_assessment

    except Exception as e:
        logger.info(f"提取风险评估数据时出错: {e}")
        return None

def run_stock_analysis(stock_symbol, analysis_date, analysts, research_depth, llm_provider, llm_model, market_type="美股", progress_callback=None):
    """执行股票分析

    Args:
        stock_symbol: 股票代码
        analysis_date: 分析日期
        analysts: 分析师列表
        research_depth: 研究深度
        llm_provider: LLM提供商 (dashscope/deepseek/google)
        llm_model: 大模型名称
        progress_callback: 进度回调函数，用于更新UI状态
    """

    def update_progress(message, step=None, total_steps=None):
        """更新进度"""
        if progress_callback:
            progress_callback(message, step, total_steps)
        logger.info(f"[进度] {message}")

    # 生成会话ID用于Token跟踪和日志关联
    session_id = f"analysis_{uuid.uuid4().hex[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # 1. 数据预获取和验证阶段
    update_progress("🔍 验证股票代码并预获取数据...", 1, 10)

    try:
        from tradingagents.utils.stock_validator import prepare_stock_data

        # 预获取股票数据（默认30天历史数据）
        preparation_result = prepare_stock_data(
            stock_code=stock_symbol,
            market_type=market_type,
            period_days=30,  # 可以根据research_depth调整
            analysis_date=analysis_date
        )

        if not preparation_result.is_valid:
            error_msg = f"❌ 股票数据验证失败: {preparation_result.error_message}"
            update_progress(error_msg)
            logger.error(f"[{session_id}] {error_msg}")

            return {
                'success': False,
                'error': preparation_result.error_message,
                'suggestion': preparation_result.suggestion,
                'stock_symbol': stock_symbol,
                'analysis_date': analysis_date,
                'session_id': session_id
            }

        # 数据预获取成功
        success_msg = f"✅ 数据准备完成: {preparation_result.stock_name} ({preparation_result.market_type})"
        update_progress(success_msg)  # 使用智能检测，不再硬编码步骤
        logger.info(f"[{session_id}] {success_msg}")
        logger.info(f"[{session_id}] 缓存状态: {preparation_result.cache_status}")

    except Exception as e:
        error_msg = f"❌ 数据预获取过程中发生错误: {str(e)}"
        update_progress(error_msg)
        logger.error(f"[{session_id}] {error_msg}")

        return {
            'success': False,
            'error': error_msg,
            'suggestion': "请检查网络连接或稍后重试",
            'stock_symbol': stock_symbol,
            'analysis_date': analysis_date,
            'session_id': session_id
        }

    # 记录分析开始的详细日志
    logger_manager = get_logger_manager()
    import time
    analysis_start_time = time.time()

    logger_manager.log_analysis_start(
        logger, stock_symbol, "comprehensive_analysis", session_id
    )

    logger.info(f"🚀 [分析开始] 股票分析启动",
               extra={
                   'stock_symbol': stock_symbol,
                   'analysis_date': analysis_date,
                   'analysts': analysts,
                   'research_depth': research_depth,
                   'llm_provider': llm_provider,
                   'llm_model': llm_model,
                   'market_type': market_type,
                   'session_id': session_id,
                   'event_type': 'web_analysis_start'
               })

    update_progress("🚀 开始股票分析...")

    # 估算Token使用（用于成本预估）
    if TOKEN_TRACKING_ENABLED:
        estimated_input = 2000 * len(analysts)  # 估算每个分析师2000个输入token
        estimated_output = 1000 * len(analysts)  # 估算每个分析师1000个输出token
        estimated_cost_result = token_tracker.estimate_cost(llm_provider, llm_model, estimated_input, estimated_output)

        # estimate_cost 返回 tuple (cost, currency)
        if isinstance(estimated_cost_result, tuple):
            estimated_cost, currency = estimated_cost_result
        else:
            estimated_cost = estimated_cost_result
            currency = "CNY"

        update_progress(f"💰 预估分析成本: ¥{estimated_cost:.4f}")

    # 验证环境变量
    update_progress("检查环境变量配置...")
    dashscope_key = os.getenv("DASHSCOPE_API_KEY")
    finnhub_key = os.getenv("FINNHUB_API_KEY")

    logger.info(f"环境变量检查:")
    logger.info(f"  DASHSCOPE_API_KEY: {'已设置' if dashscope_key else '未设置'}")
    logger.info(f"  FINNHUB_API_KEY: {'已设置' if finnhub_key else '未设置'}")

    if not dashscope_key:
        raise ValueError("DASHSCOPE_API_KEY 环境变量未设置")
    if not finnhub_key:
        raise ValueError("FINNHUB_API_KEY 环境变量未设置")

    update_progress("环境变量验证通过")

    try:
        # 导入必要的模块
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        from tradingagents.default_config import DEFAULT_CONFIG

        # 创建配置
        update_progress("配置分析参数...")
        config = DEFAULT_CONFIG.copy()
        config["llm_provider"] = llm_provider
        config["deep_think_llm"] = llm_model
        config["quick_think_llm"] = llm_model
        # 根据研究深度调整配置
        if research_depth == 1:  # 1级 - 快速分析
            config["max_debate_rounds"] = 1
            config["max_risk_discuss_rounds"] = 1
            # 禁用记忆以加速
            config["memory_enabled"] = False

            # 统一使用在线工具，避免离线工具的各种问题
            config["online_tools"] = True  # 所有市场都使用统一工具
            logger.info(f"🔧 [快速分析] {market_type}使用统一工具，确保数据源正确和稳定性")
            if llm_provider == "dashscope":
                config["quick_think_llm"] = "qwen-turbo"  # 使用最快模型
                config["deep_think_llm"] = "qwen-plus"
            elif llm_provider == "deepseek":
                config["quick_think_llm"] = "deepseek-chat"  # DeepSeek只有一个模型
                config["deep_think_llm"] = "deepseek-chat"
        elif research_depth == 2:  # 2级 - 基础分析
            config["max_debate_rounds"] = 1
            config["max_risk_discuss_rounds"] = 1
            config["memory_enabled"] = True
            config["online_tools"] = True
            if llm_provider == "dashscope":
                config["quick_think_llm"] = "qwen-plus"
                config["deep_think_llm"] = "qwen-plus"
            elif llm_provider == "deepseek":
                config["quick_think_llm"] = "deepseek-chat"
                config["deep_think_llm"] = "deepseek-chat"
            elif llm_provider == "openai":
                config["quick_think_llm"] = llm_model
                config["deep_think_llm"] = llm_model
            elif llm_provider == "openai":
                config["quick_think_llm"] = llm_model
                config["deep_think_llm"] = llm_model
            elif llm_provider == "openai":
                config["quick_think_llm"] = llm_model
                config["deep_think_llm"] = llm_model
            elif llm_provider == "openai":
                config["quick_think_llm"] = llm_model
                config["deep_think_llm"] = llm_model
            elif llm_provider == "openai":
                config["quick_think_llm"] = llm_model
                config["deep_think_llm"] = llm_model
        elif research_depth == 3:  # 3级 - 标准分析 (默认)
            config["max_debate_rounds"] = 1
            config["max_risk_discuss_rounds"] = 2
            config["memory_enabled"] = True
            config["online_tools"] = True
            if llm_provider == "dashscope":
                config["quick_think_llm"] = "qwen-plus"
                config["deep_think_llm"] = "qwen3-max"
            elif llm_provider == "deepseek":
                config["quick_think_llm"] = "deepseek-chat"
                config["deep_think_llm"] = "deepseek-chat"
        elif research_depth == 4:  # 4级 - 深度分析
            config["max_debate_rounds"] = 2
            config["max_risk_discuss_rounds"] = 2
            config["memory_enabled"] = True
            config["online_tools"] = True
            if llm_provider == "dashscope":
                config["quick_think_llm"] = "qwen-plus"
                config["deep_think_llm"] = "qwen3-max"
            elif llm_provider == "deepseek":
                config["quick_think_llm"] = "deepseek-chat"
                config["deep_think_llm"] = "deepseek-chat"
        else:  # 5级 - 全面分析
            config["max_debate_rounds"] = 3
            config["max_risk_discuss_rounds"] = 3
            config["memory_enabled"] = True
            config["online_tools"] = True
            if llm_provider == "dashscope":
                config["quick_think_llm"] = "qwen3-max"
                config["deep_think_llm"] = "qwen3-max"
            elif llm_provider == "deepseek":
                config["quick_think_llm"] = "deepseek-chat"
                config["deep_think_llm"] = "deepseek-chat"

        # 根据LLM提供商设置不同的配置
        if llm_provider == "dashscope":
            config["backend_url"] = "https://dashscope.aliyuncs.com/api/v1"
        elif llm_provider == "deepseek":
            config["backend_url"] = "https://api.deepseek.com"
        elif llm_provider == "qianfan":
            # 千帆（文心一言）配置
            config["backend_url"] = "https://aip.baidubce.com"
            # 根据研究深度设置千帆模型
            if research_depth <= 2:  # 快速和基础分析
                config["quick_think_llm"] = "ernie-3.5-8k"
                config["deep_think_llm"] = "ernie-3.5-8k"
            elif research_depth <= 4:  # 标准和深度分析
                config["quick_think_llm"] = "ernie-3.5-8k"
                config["deep_think_llm"] = "ernie-4.0-turbo-8k"
            else:  # 全面分析
                config["quick_think_llm"] = "ernie-4.0-turbo-8k"
                config["deep_think_llm"] = "ernie-4.0-turbo-8k"
            
            logger.info(f"🤖 [千帆] 快速模型: {config['quick_think_llm']}")
            logger.info(f"🤖 [千帆] 深度模型: {config['deep_think_llm']}")
        elif llm_provider == "google":
            # Google AI不需要backend_url，使用默认的OpenAI格式
            config["backend_url"] = "https://api.openai.com/v1"
            
            # 根据研究深度优化Google模型选择
            if research_depth == 1:  # 快速分析 - 使用最快模型
                config["quick_think_llm"] = "gemini-2.5-flash-lite-preview-06-17"  # 1.45s
                config["deep_think_llm"] = "gemini-2.0-flash"  # 1.87s
            elif research_depth == 2:  # 基础分析 - 使用快速模型
                config["quick_think_llm"] = "gemini-2.0-flash"  # 1.87s
                config["deep_think_llm"] = "gemini-1.5-pro"  # 2.25s
            elif research_depth == 3:  # 标准分析 - 平衡性能
                config["quick_think_llm"] = "gemini-1.5-pro"  # 2.25s
                config["deep_think_llm"] = "gemini-2.5-flash"  # 2.73s
            elif research_depth == 4:  # 深度分析 - 使用强大模型
                config["quick_think_llm"] = "gemini-2.5-flash"  # 2.73s
                config["deep_think_llm"] = "gemini-2.5-pro"  # 16.68s
            else:  # 全面分析 - 使用最强模型
                config["quick_think_llm"] = "gemini-2.5-pro"  # 16.68s
                config["deep_think_llm"] = "gemini-2.5-pro"  # 16.68s
            
            logger.info(f"🤖 [Google AI] 快速模型: {config['quick_think_llm']}")
            logger.info(f"🤖 [Google AI] 深度模型: {config['deep_think_llm']}")
        elif llm_provider == "openai":
            # OpenAI官方API
            config["backend_url"] = "https://api.openai.com/v1"
            logger.info(f"🤖 [OpenAI] 使用模型: {llm_model}")
            logger.info(f"🤖 [OpenAI] API端点: https://api.openai.com/v1")
        elif llm_provider == "openrouter":
            # OpenRouter使用OpenAI兼容API
            config["backend_url"] = "https://openrouter.ai/api/v1"
            logger.info(f"🌐 [OpenRouter] 使用模型: {llm_model}")
            logger.info(f"🌐 [OpenRouter] API端点: https://openrouter.ai/api/v1")
        elif llm_provider == "siliconflow":
            config["backend_url"] = "https://api.siliconflow.cn/v1"
            logger.info(f"🌐 [SiliconFlow] 使用模型: {llm_model}")
            logger.info(f"🌐 [SiliconFlow] API端点: https://api.siliconflow.cn/v1")
        elif llm_provider == "custom_openai":
            # 自定义OpenAI端点
            custom_base_url = st.session_state.get("custom_openai_base_url", "https://api.openai.com/v1")
            config["backend_url"] = custom_base_url
            config["custom_openai_base_url"] = custom_base_url
            logger.info(f"🔧 [自定义OpenAI] 使用模型: {llm_model}")
            logger.info(f"🔧 [自定义OpenAI] API端点: {custom_base_url}")

        # 修复路径问题 - 优先使用环境变量配置
        # 数据目录：优先使用环境变量，否则使用默认路径
        if not config.get("data_dir") or config["data_dir"] == "./data":
            env_data_dir = os.getenv("TRADINGAGENTS_DATA_DIR")
            if env_data_dir:
                # 如果环境变量是相对路径，相对于项目根目录解析
                if not os.path.isabs(env_data_dir):
                    config["data_dir"] = str(project_root / env_data_dir)
                else:
                    config["data_dir"] = env_data_dir
            else:
                config["data_dir"] = str(project_root / "data")

        # 结果目录：优先使用环境变量，否则使用默认路径
        if not config.get("results_dir") or config["results_dir"] == "./results":
            env_results_dir = os.getenv("TRADINGAGENTS_RESULTS_DIR")
            if env_results_dir:
                # 如果环境变量是相对路径，相对于项目根目录解析
                if not os.path.isabs(env_results_dir):
                    config["results_dir"] = str(project_root / env_results_dir)
                else:
                    config["results_dir"] = env_results_dir
            else:
                config["results_dir"] = str(project_root / "results")

        # 缓存目录：优先使用环境变量，否则使用默认路径
        if not config.get("data_cache_dir"):
            env_cache_dir = os.getenv("TRADINGAGENTS_CACHE_DIR")
            if env_cache_dir:
                # 如果环境变量是相对路径，相对于项目根目录解析
                if not os.path.isabs(env_cache_dir):
                    config["data_cache_dir"] = str(project_root / env_cache_dir)
                else:
                    config["data_cache_dir"] = env_cache_dir
            else:
                config["data_cache_dir"] = str(project_root / "tradingagents" / "dataflows" / "data_cache")

        # 确保目录存在
        update_progress("📁 创建必要的目录...")
        os.makedirs(config["data_dir"], exist_ok=True)
        os.makedirs(config["results_dir"], exist_ok=True)
        os.makedirs(config["data_cache_dir"], exist_ok=True)

        logger.info(f"📁 目录配置:")
        logger.info(f"  - 数据目录: {config['data_dir']}")
        logger.info(f"  - 结果目录: {config['results_dir']}")
        logger.info(f"  - 缓存目录: {config['data_cache_dir']}")
        logger.info(f"  - 环境变量 TRADINGAGENTS_RESULTS_DIR: {os.getenv('TRADINGAGENTS_RESULTS_DIR', '未设置')}")

        logger.info(f"使用配置: {config}")
        logger.info(f"分析师列表: {analysts}")
        logger.info(f"股票代码: {stock_symbol}")
        logger.info(f"分析日期: {analysis_date}")

        # 根据市场类型调整股票代码格式
        logger.debug(f"🔍 [RUNNER DEBUG] ===== 股票代码格式化 =====")
        logger.debug(f"🔍 [RUNNER DEBUG] 原始股票代码: '{stock_symbol}'")
        logger.debug(f"🔍 [RUNNER DEBUG] 市场类型: '{market_type}'")

        if market_type == "A股":
            # A股代码不需要特殊处理，保持原样
            formatted_symbol = stock_symbol
            logger.debug(f"🔍 [RUNNER DEBUG] A股代码保持原样: '{formatted_symbol}'")
            update_progress(f"🇨🇳 准备分析A股: {formatted_symbol}")
        elif market_type == "港股":
            # 港股代码转为大写，确保.HK后缀
            formatted_symbol = stock_symbol.upper()
            if not formatted_symbol.endswith('.HK'):
                # 如果是纯数字，添加.HK后缀
                if formatted_symbol.isdigit():
                    formatted_symbol = f"{formatted_symbol.zfill(4)}.HK"
            update_progress(f"🇭🇰 准备分析港股: {formatted_symbol}")
        else:
            # 美股代码转为大写
            formatted_symbol = stock_symbol.upper()
            logger.debug(f"🔍 [RUNNER DEBUG] 美股代码转大写: '{stock_symbol}' -> '{formatted_symbol}'")
            update_progress(f"🇺🇸 准备分析美股: {formatted_symbol}")

        logger.debug(f"🔍 [RUNNER DEBUG] 最终传递给分析引擎的股票代码: '{formatted_symbol}'")

        # 初始化交易图
        update_progress("🔧 初始化分析引擎...")
        graph = TradingAgentsGraph(analysts, config=config, debug=False)

        # 执行分析
        update_progress(f"📊 开始分析 {formatted_symbol} 股票，这可能需要几分钟时间...")
        logger.debug(f"🔍 [RUNNER DEBUG] ===== 调用graph.propagate =====")
        logger.debug(f"🔍 [RUNNER DEBUG] 传递给graph.propagate的参数:")
        logger.debug(f"🔍 [RUNNER DEBUG]   symbol: '{formatted_symbol}'")
        logger.debug(f"🔍 [RUNNER DEBUG]   date: '{analysis_date}'")

        state, decision = graph.propagate(formatted_symbol, analysis_date)

        # 调试信息
        logger.debug(f"🔍 [DEBUG] 分析完成，decision类型: {type(decision)}")
        logger.debug(f"🔍 [DEBUG] decision内容: {decision}")

        # 格式化结果
        update_progress("📋 分析完成，正在整理结果...")

        # 提取风险评估数据
        risk_assessment = extract_risk_assessment(state)

        # 将风险评估添加到状态中
        if risk_assessment:
            state['risk_assessment'] = risk_assessment

        # 记录Token使用（实际使用量，这里使用估算值）
        if TOKEN_TRACKING_ENABLED:
            # 在实际应用中，这些值应该从LLM响应中获取
            # 这里使用基于分析师数量和研究深度的估算
            actual_input_tokens = len(analysts) * (1500 if research_depth == "快速" else 2500 if research_depth == "标准" else 4000)
            actual_output_tokens = len(analysts) * (800 if research_depth == "快速" else 1200 if research_depth == "标准" else 2000)

            usage_record = token_tracker.track_usage(
                provider=llm_provider,
                model_name=llm_model,
                input_tokens=actual_input_tokens,
                output_tokens=actual_output_tokens,
                session_id=session_id,
                analysis_type=f"{market_type}_analysis"
            )

            if usage_record:
                update_progress(f"💰 记录使用成本: ¥{usage_record.cost:.4f}")

        # 从决策中提取模型信息
        model_info = decision.get('model_info', 'Unknown') if isinstance(decision, dict) else 'Unknown'

        results = {
            'stock_symbol': stock_symbol,
            'analysis_date': analysis_date,
            'analysts': analysts,
            'research_depth': research_depth,
            'llm_provider': llm_provider,
            'llm_model': llm_model,
            'model_info': model_info,  # 🔥 添加模型信息字段
            'state': state,
            'decision': decision,
            'success': True,
            'error': None,
            'session_id': session_id if TOKEN_TRACKING_ENABLED else None
        }

        # 记录分析完成的详细日志
        analysis_duration = time.time() - analysis_start_time

        # 计算总成本（如果有Token跟踪）
        total_cost = 0.0
        if TOKEN_TRACKING_ENABLED:
            try:
                total_cost = token_tracker.get_session_cost(session_id)
            except:
                pass

        logger_manager.log_analysis_complete(
            logger, stock_symbol, "comprehensive_analysis", session_id,
            analysis_duration, total_cost
        )

        logger.info(f"✅ [分析完成] 股票分析成功完成",
                   extra={
                       'stock_symbol': stock_symbol,
                       'session_id': session_id,
                       'duration': analysis_duration,
                       'total_cost': total_cost,
                       'analysts_used': analysts,
                       'success': True,
                       'event_type': 'web_analysis_complete'
                   })

        # 保存分析报告到本地和MongoDB
        try:
            update_progress("💾 正在保存分析报告...")
            from .report_exporter import save_analysis_report, save_modular_reports_to_results_dir
            
            # 1. 保存分模块报告到本地目录
            logger.info(f"📁 [本地保存] 开始保存分模块报告到本地目录")
            local_files = save_modular_reports_to_results_dir(results, stock_symbol)
            if local_files:
                logger.info(f"✅ [本地保存] 已保存 {len(local_files)} 个本地报告文件")
                for module, path in local_files.items():
                    logger.info(f"  - {module}: {path}")
            else:
                logger.warning(f"⚠️ [本地保存] 本地报告文件保存失败")
            
            # 2. 保存分析报告到MongoDB
            logger.info(f"🗄️ [MongoDB保存] 开始保存分析报告到MongoDB")
            save_success = save_analysis_report(
                stock_symbol=stock_symbol,
                analysis_results=results
            )
            
            if save_success:
                logger.info(f"✅ [MongoDB保存] 分析报告已成功保存到MongoDB")
                update_progress("✅ 分析报告已保存到数据库和本地文件")
            else:
                logger.warning(f"⚠️ [MongoDB保存] MongoDB报告保存失败")
                if local_files:
                    update_progress("✅ 本地报告已保存，但数据库保存失败")
                else:
                    update_progress("⚠️ 报告保存失败，但分析已完成")
                
        except Exception as save_error:
            logger.error(f"❌ [报告保存] 保存分析报告时发生错误: {str(save_error)}")
            update_progress("⚠️ 报告保存出错，但分析已完成")

        update_progress("✅ 分析成功完成！")
        return results

    except Exception as e:
        # 记录分析失败的详细日志
        analysis_duration = time.time() - analysis_start_time

        logger_manager.log_module_error(
            logger, "comprehensive_analysis", stock_symbol, session_id,
            analysis_duration, str(e)
        )

        logger.error(f"❌ [分析失败] 股票分析执行失败",
                    extra={
                        'stock_symbol': stock_symbol,
                        'session_id': session_id,
                        'duration': analysis_duration,
                        'error': str(e),
                        'error_type': type(e).__name__,
                        'analysts_used': analysts,
                        'success': False,
                        'event_type': 'web_analysis_error'
                    }, exc_info=True)

        # 如果真实分析失败，返回错误信息而不是误导性演示数据
        return {
            'stock_symbol': stock_symbol,
            'analysis_date': analysis_date,
            'analysts': analysts,
            'research_depth': research_depth,
            'llm_provider': llm_provider,
            'llm_model': llm_model,
            'state': {},  # 空状态，将显示占位符
            'decision': {},  # 空决策
            'success': False,
            'error': str(e),
            'is_demo': False,
            'error_reason': f"分析失败: {str(e)}"
        }

def format_analysis_results(results):
    """格式化分析结果用于显示"""
    
    if not results['success']:
        return {
            'error': results['error'],
            'success': False
        }
    
    state = results['state']
    decision = results['decision']

    # 提取关键信息
    # decision 可能是字符串（如 "BUY", "SELL", "HOLD"）或字典
    if isinstance(decision, str):
        # 将英文投资建议转换为中文
        action_translation = {
            'BUY': '买入',
            'SELL': '卖出',
            'HOLD': '持有',
            'buy': '买入',
            'sell': '卖出',
            'hold': '持有'
        }
        action = action_translation.get(decision.strip(), decision.strip())

        formatted_decision = {
            'action': action,
            'confidence': 0.7,  # 默认置信度
            'risk_score': 0.3,  # 默认风险分数
            'target_price': None,  # 字符串格式没有目标价格
            'reasoning': f'基于AI分析，建议{decision.strip().upper()}'
        }
    elif isinstance(decision, dict):
        # 处理目标价格 - 确保正确提取数值
        target_price = decision.get('target_price')
        if target_price is not None and target_price != 'N/A':
            try:
                # 尝试转换为浮点数
                if isinstance(target_price, str):
                    # 移除货币符号和空格
                    clean_price = target_price.replace('$', '').replace('¥', '').replace('￥', '').strip()
                    target_price = float(clean_price) if clean_price and clean_price != 'None' else None
                elif isinstance(target_price, (int, float)):
                    target_price = float(target_price)
                else:
                    target_price = None
            except (ValueError, TypeError):
                target_price = None
        else:
            target_price = None

        # 将英文投资建议转换为中文
        action_translation = {
            'BUY': '买入',
            'SELL': '卖出',
            'HOLD': '持有',
            'buy': '买入',
            'sell': '卖出',
            'hold': '持有'
        }
        action = decision.get('action', '持有')
        chinese_action = action_translation.get(action, action)

        formatted_decision = {
            'action': chinese_action,
            'confidence': decision.get('confidence', 0.5),
            'risk_score': decision.get('risk_score', 0.3),
            'target_price': target_price,
            'reasoning': decision.get('reasoning', '暂无分析推理')
        }
    else:
        # 处理其他类型
        formatted_decision = {
            'action': '持有',
            'confidence': 0.5,
            'risk_score': 0.3,
            'target_price': None,
            'reasoning': f'分析结果: {str(decision)}'
        }
    
    # 格式化状态信息
    formatted_state = {}
    
    # 处理各个分析模块的结果 - 包含完整的智能体团队分析
    analysis_keys = [
        'market_report',
        'fundamentals_report',
        'sentiment_report',
        'news_report',
        'risk_assessment',
        'investment_plan',
        # 添加缺失的团队决策数据，确保与CLI端一致
        'investment_debate_state',  # 研究团队辩论（多头/空头研究员）
        'trader_investment_plan',   # 交易团队计划
        'risk_debate_state',        # 风险管理团队决策
        'final_trade_decision'      # 最终交易决策
    ]
    
    # 添加调试信息
    logger.debug(f"🔍 [格式化调试] 原始state中的键: {list(state.keys())}")
    for key in state.keys():
        if isinstance(state[key], str):
            logger.debug(f"🔍 [格式化调试] {key}: 字符串长度 {len(state[key])}")
        elif isinstance(state[key], dict):
            logger.debug(f"🔍 [格式化调试] {key}: 字典，包含键 {list(state[key].keys())}")
        else:
            logger.debug(f"🔍 [格式化调试] {key}: {type(state[key])}")

    for key in analysis_keys:
        if key in state:
            # 对文本内容进行中文化处理
            content = state[key]
            if isinstance(content, str):
                content = translate_analyst_labels(content)
                logger.debug(f"🔍 [格式化调试] 处理字符串字段 {key}: 长度 {len(content)}")
            elif isinstance(content, dict):
                logger.debug(f"🔍 [格式化调试] 处理字典字段 {key}: 包含键 {list(content.keys())}")
            formatted_state[key] = content
        elif key == 'risk_assessment':
            # 特殊处理：从 risk_debate_state 生成 risk_assessment
            risk_assessment = extract_risk_assessment(state)
            if risk_assessment:
                formatted_state[key] = risk_assessment
        else:
            logger.debug(f"🔍 [格式化调试] 缺失字段: {key}")
    
    return {
        'stock_symbol': results['stock_symbol'],
        'decision': formatted_decision,
        'state': formatted_state,
        'success': True,
        # 将配置信息放在顶层，供前端直接访问
        'analysis_date': results['analysis_date'],
        'analysts': results['analysts'],
        'research_depth': results['research_depth'],
        'llm_provider': results.get('llm_provider', 'dashscope'),
        'llm_model': results['llm_model'],
        'metadata': {
            'analysis_date': results['analysis_date'],
            'analysts': results['analysts'],
            'research_depth': results['research_depth'],
            'llm_provider': results.get('llm_provider', 'dashscope'),
            'llm_model': results['llm_model']
        }
    }

def validate_analysis_params(stock_symbol, analysis_date, analysts, research_depth, market_type="美股"):
    """验证分析参数"""

    errors = []

    # 验证股票代码
    if not stock_symbol or len(stock_symbol.strip()) == 0:
        errors.append("股票代码不能为空")
    elif len(stock_symbol.strip()) > 10:
        errors.append("股票代码长度不能超过10个字符")
    else:
        # 根据市场类型验证代码格式
        symbol = stock_symbol.strip()
        if market_type == "A股":
            # A股：6位数字
            import re
            if not re.match(r'^\d{6}$', symbol):
                errors.append("A股代码格式错误，应为6位数字（如：000001）")
        elif market_type == "港股":
            # 港股：4-5位数字.HK 或 纯4-5位数字
            import re
            symbol_upper = symbol.upper()
            # 检查是否为 XXXX.HK 或 XXXXX.HK 格式
            hk_format = re.match(r'^\d{4,5}\.HK$', symbol_upper)
            # 检查是否为纯4-5位数字格式
            digit_format = re.match(r'^\d{4,5}$', symbol)

            if not (hk_format or digit_format):
                errors.append("港股代码格式错误，应为4位数字.HK（如：0700.HK）或4位数字（如：0700）")
        elif market_type == "美股":
            # 美股：1-5位字母
            import re
            if not re.match(r'^[A-Z]{1,5}$', symbol.upper()):
                errors.append("美股代码格式错误，应为1-5位字母（如：AAPL）")
    
    # 验证分析师列表
    if not analysts or len(analysts) == 0:
        errors.append("必须至少选择一个分析师")
    
    valid_analysts = ['market', 'social', 'news', 'fundamentals']
    invalid_analysts = [a for a in analysts if a not in valid_analysts]
    if invalid_analysts:
        errors.append(f"无效的分析师类型: {', '.join(invalid_analysts)}")
    
    # 验证研究深度
    if not isinstance(research_depth, int) or research_depth < 1 or research_depth > 5:
        errors.append("研究深度必须是1-5之间的整数")
    
    # 验证分析日期
    try:
        from datetime import datetime
        datetime.strptime(analysis_date, '%Y-%m-%d')
    except ValueError:
        errors.append("分析日期格式无效，应为YYYY-MM-DD格式")
    
    return len(errors) == 0, errors

def get_supported_stocks():
    """获取支持的股票列表"""
    
    # 常见的美股股票代码
    popular_stocks = [
        {'symbol': 'AAPL', 'name': '苹果公司', 'sector': '科技'},
        {'symbol': 'MSFT', 'name': '微软', 'sector': '科技'},
        {'symbol': 'GOOGL', 'name': '谷歌', 'sector': '科技'},
        {'symbol': 'AMZN', 'name': '亚马逊', 'sector': '消费'},
        {'symbol': 'TSLA', 'name': '特斯拉', 'sector': '汽车'},
        {'symbol': 'NVDA', 'name': '英伟达', 'sector': '科技'},
        {'symbol': 'META', 'name': 'Meta', 'sector': '科技'},
        {'symbol': 'NFLX', 'name': '奈飞', 'sector': '媒体'},
        {'symbol': 'AMD', 'name': 'AMD', 'sector': '科技'},
        {'symbol': 'INTC', 'name': '英特尔', 'sector': '科技'},
        {'symbol': 'SPY', 'name': 'S&P 500 ETF', 'sector': 'ETF'},
        {'symbol': 'QQQ', 'name': '纳斯达克100 ETF', 'sector': 'ETF'},
    ]
    
    return popular_stocks

def generate_demo_results_deprecated(stock_symbol, analysis_date, analysts, research_depth, llm_provider, llm_model, error_msg, market_type="美股"):
    """
    已弃用：生成演示分析结果

    注意：此函数已弃用，因为演示数据会误导用户。
    现在我们使用占位符来代替演示数据。
    """

    import random

    # 根据市场类型设置货币符号和价格范围
    if market_type == "港股":
        currency_symbol = "HK$"
        price_range = (50, 500)  # 港股价格范围
        market_name = "港股"
    elif market_type == "A股":
        currency_symbol = "¥"
        price_range = (5, 100)   # A股价格范围
        market_name = "A股"
    else:  # 美股
        currency_symbol = "$"
        price_range = (50, 300)  # 美股价格范围
        market_name = "美股"

    # 生成模拟决策
    actions = ['买入', '持有', '卖出']
    action = random.choice(actions)

    demo_decision = {
        'action': action,
        'confidence': round(random.uniform(0.6, 0.9), 2),
        'risk_score': round(random.uniform(0.2, 0.7), 2),
        'target_price': round(random.uniform(*price_range), 2),
        'reasoning': f"""
基于对{market_name}{stock_symbol}的综合分析，我们的AI分析团队得出以下结论：

**投资建议**: {action}
**目标价格**: {currency_symbol}{round(random.uniform(*price_range), 2)}

**主要分析要点**:
1. **技术面分析**: 当前价格趋势显示{'上涨' if action == '买入' else '下跌' if action == '卖出' else '横盘'}信号
2. **基本面评估**: 公司财务状况{'良好' if action == '买入' else '一般' if action == '持有' else '需关注'}
3. **市场情绪**: 投资者情绪{'乐观' if action == '买入' else '中性' if action == '持有' else '谨慎'}
4. **风险评估**: 当前风险水平为{'中等' if action == '持有' else '较低' if action == '买入' else '较高'}

**注意**: 这是演示数据，实际分析需要配置正确的API密钥。
        """
    }

    # 生成模拟状态数据
    demo_state = {}

    if 'market' in analysts:
        current_price = round(random.uniform(*price_range), 2)
        high_price = round(current_price * random.uniform(1.2, 1.8), 2)
        low_price = round(current_price * random.uniform(0.5, 0.8), 2)

        demo_state['market_report'] = f"""
## 📈 {market_name}{stock_symbol} 技术面分析报告

### 价格趋势分析
- **当前价格**: {currency_symbol}{current_price}
- **日内变化**: {random.choice(['+', '-'])}{round(random.uniform(0.5, 5), 2)}%
- **52周高点**: {currency_symbol}{high_price}
- **52周低点**: {currency_symbol}{low_price}

### 技术指标
- **RSI (14日)**: {round(random.uniform(30, 70), 1)}
- **MACD**: {'看涨' if action == 'BUY' else '看跌' if action == 'SELL' else '中性'}
- **移动平均线**: 价格{'高于' if action == 'BUY' else '低于' if action == 'SELL' else '接近'}20日均线

### 支撑阻力位
- **支撑位**: ${round(random.uniform(80, 120), 2)}
- **阻力位**: ${round(random.uniform(250, 350), 2)}

*注意: 这是演示数据，实际分析需要配置API密钥*
        """

    if 'fundamentals' in analysts:
        demo_state['fundamentals_report'] = f"""
## 💰 {stock_symbol} 基本面分析报告

### 财务指标
- **市盈率 (P/E)**: {round(random.uniform(15, 35), 1)}
- **市净率 (P/B)**: {round(random.uniform(1, 5), 1)}
- **净资产收益率 (ROE)**: {round(random.uniform(10, 25), 1)}%
- **毛利率**: {round(random.uniform(20, 60), 1)}%

### 盈利能力
- **营收增长**: {random.choice(['+', '-'])}{round(random.uniform(5, 20), 1)}%
- **净利润增长**: {random.choice(['+', '-'])}{round(random.uniform(10, 30), 1)}%
- **每股收益**: ${round(random.uniform(2, 15), 2)}

### 财务健康度
- **负债率**: {round(random.uniform(20, 60), 1)}%
- **流动比率**: {round(random.uniform(1, 3), 1)}
- **现金流**: {'正向' if action != 'SELL' else '需关注'}

*注意: 这是演示数据，实际分析需要配置API密钥*
        """

    if 'social' in analysts:
        demo_state['sentiment_report'] = f"""
## 💭 {stock_symbol} 市场情绪分析报告

### 社交媒体情绪
- **整体情绪**: {'积极' if action == 'BUY' else '消极' if action == 'SELL' else '中性'}
- **情绪强度**: {round(random.uniform(0.5, 0.9), 2)}
- **讨论热度**: {'高' if random.random() > 0.5 else '中等'}

### 投资者情绪指标
- **恐慌贪婪指数**: {round(random.uniform(20, 80), 0)}
- **看涨看跌比**: {round(random.uniform(0.8, 1.5), 2)}
- **期权Put/Call比**: {round(random.uniform(0.5, 1.2), 2)}

### 机构投资者动向
- **机构持仓变化**: {random.choice(['增持', '减持', '维持'])}
- **分析师评级**: {'买入' if action == 'BUY' else '卖出' if action == 'SELL' else '持有'}

*注意: 这是演示数据，实际分析需要配置API密钥*
        """

    if 'news' in analysts:
        demo_state['news_report'] = f"""
## 📰 {stock_symbol} 新闻事件分析报告

### 近期重要新闻
1. **财报发布**: 公司发布{'超预期' if action == 'BUY' else '低于预期' if action == 'SELL' else '符合预期'}的季度财报
2. **行业动态**: 所在行业面临{'利好' if action == 'BUY' else '挑战' if action == 'SELL' else '稳定'}政策环境
3. **公司公告**: 管理层{'乐观' if action == 'BUY' else '谨慎' if action == 'SELL' else '稳健'}展望未来

### 新闻情绪分析
- **正面新闻占比**: {round(random.uniform(40, 80), 0)}%
- **负面新闻占比**: {round(random.uniform(10, 40), 0)}%
- **中性新闻占比**: {round(random.uniform(20, 50), 0)}%

### 市场影响评估
- **短期影响**: {'正面' if action == 'BUY' else '负面' if action == 'SELL' else '中性'}
- **长期影响**: {'积极' if action != 'SELL' else '需观察'}

*注意: 这是演示数据，实际分析需要配置API密钥*
        """

    # 添加风险评估和投资建议
    demo_state['risk_assessment'] = f"""
## ⚠️ {stock_symbol} 风险评估报告

### 主要风险因素
1. **市场风险**: {'低' if action == 'BUY' else '高' if action == 'SELL' else '中等'}
2. **行业风险**: {'可控' if action != 'SELL' else '需关注'}
3. **公司特定风险**: {'较低' if action == 'BUY' else '中等'}

### 风险等级评估
- **总体风险等级**: {'低风险' if action == 'BUY' else '高风险' if action == 'SELL' else '中等风险'}
- **建议仓位**: {random.choice(['轻仓', '标准仓位', '重仓']) if action != 'SELL' else '建议减仓'}

*注意: 这是演示数据，实际分析需要配置API密钥*
    """

    demo_state['investment_plan'] = f"""
## 📋 {stock_symbol} 投资建议

### 具体操作建议
- **操作方向**: {action}
- **建议价位**: ${round(random.uniform(90, 310), 2)}
- **止损位**: ${round(random.uniform(80, 200), 2)}
- **目标价位**: ${round(random.uniform(150, 400), 2)}

### 投资策略
- **投资期限**: {'短期' if research_depth <= 2 else '中长期'}
- **仓位管理**: {'分批建仓' if action == 'BUY' else '分批减仓' if action == 'SELL' else '维持现状'}

*注意: 这是演示数据，实际分析需要配置API密钥*
    """

    # 添加团队决策演示数据，确保与CLI端一致
    demo_state['investment_debate_state'] = {
        'bull_history': f"""
## 📈 多头研究员分析

作为多头研究员，我对{stock_symbol}持乐观态度：

### 🚀 投资亮点
1. **技术面突破**: 股价突破关键阻力位，技术形态良好
2. **基本面支撑**: 公司业绩稳健增长，财务状况健康
3. **市场机会**: 当前估值合理，具备上涨空间

### 📊 数据支持
- 近期成交量放大，资金流入明显
- 行业景气度提升，政策环境有利
- 机构投资者增持，市场信心增强

**建议**: 积极买入，目标价位上调15-20%

*注意: 这是演示数据*
        """.strip(),

        'bear_history': f"""
## 📉 空头研究员分析

作为空头研究员，我对{stock_symbol}持谨慎态度：

### ⚠️ 风险因素
1. **估值偏高**: 当前市盈率超过行业平均水平
2. **技术风险**: 短期涨幅过大，存在回调压力
3. **宏观环境**: 市场整体波动加大，不确定性增加

### 📉 担忧点
- 成交量虽然放大，但可能是获利盘出货
- 行业竞争加剧，公司市场份额面临挑战
- 政策变化可能对行业产生负面影响

**建议**: 谨慎观望，等待更好的入场时机

*注意: 这是演示数据*
        """.strip(),

        'judge_decision': f"""
## 🎯 研究经理综合决策

经过多头和空头研究员的充分辩论，我的综合判断如下：

### 📊 综合评估
- **多头观点**: 技术面和基本面都显示积极信号
- **空头观点**: 估值和短期风险需要关注
- **平衡考虑**: 机会与风险并存，需要策略性操作

### 🎯 最终建议
基于当前市场环境和{stock_symbol}的具体情况，建议采取**{action}**策略：

1. **操作建议**: {action}
2. **仓位控制**: {'分批建仓' if action == '买入' else '分批减仓' if action == '卖出' else '维持现状'}
3. **风险管理**: 设置止损位，控制单只股票仓位不超过10%

**决策依据**: 综合技术面、基本面和市场情绪分析

*注意: 这是演示数据*
        """.strip()
    }

    demo_state['trader_investment_plan'] = f"""
## 💼 交易团队执行计划

基于研究团队的分析结果，制定如下交易执行计划：

### 🎯 交易策略
- **交易方向**: {action}
- **目标价位**: {currency_symbol}{round(random.uniform(*price_range) * 1.1, 2)}
- **止损价位**: {currency_symbol}{round(random.uniform(*price_range) * 0.9, 2)}

### 📊 仓位管理
- **建议仓位**: {'30-50%' if action == '买入' else '减仓至20%' if action == '卖出' else '维持现有仓位'}
- **分批操作**: {'分3次建仓' if action == '买入' else '分2次减仓' if action == '卖出' else '暂不操作'}
- **时间安排**: {'1-2周内完成' if action != '持有' else '持续观察'}

### ⚠️ 风险控制
- **止损设置**: 跌破支撑位立即止损
- **止盈策略**: 达到目标价位分批止盈
- **监控要点**: 密切关注成交量和技术指标变化

*注意: 这是演示数据，实际交易需要配置API密钥*
    """

    demo_state['risk_debate_state'] = {
        'risky_history': f"""
## 🚀 激进分析师风险评估

从激进投资角度分析{stock_symbol}：

### 💪 风险承受能力
- **高收益机会**: 当前市场提供了难得的投资机会
- **风险可控**: 虽然存在波动，但长期趋势向好
- **时机把握**: 现在是积极布局的最佳时机

### 🎯 激进策略
- **加大仓位**: 建议将仓位提升至60-80%
- **杠杆使用**: 可适度使用杠杆放大收益
- **快速行动**: 机会稍纵即逝，需要果断决策

**风险评级**: 中等风险，高收益潜力

*注意: 这是演示数据*
        """.strip(),

        'safe_history': f"""
## 🛡️ 保守分析师风险评估

从风险控制角度分析{stock_symbol}：

### ⚠️ 风险识别
- **市场波动**: 当前市场不确定性较高
- **估值风险**: 部分股票估值已经偏高
- **流动性风险**: 需要关注市场流动性变化

### 🔒 保守策略
- **控制仓位**: 建议仓位不超过30%
- **分散投资**: 避免过度集中于单一标的
- **安全边际**: 确保有足够的安全边际

**风险评级**: 中高风险，需要谨慎操作

*注意: 这是演示数据*
        """.strip(),

        'neutral_history': f"""
## ⚖️ 中性分析师风险评估

从平衡角度分析{stock_symbol}：

### 📊 客观评估
- **机会与风险并存**: 当前市场既有机会也有风险
- **适度参与**: 建议采取适度参与的策略
- **灵活调整**: 根据市场变化及时调整策略

### ⚖️ 平衡策略
- **中等仓位**: 建议仓位控制在40-50%
- **动态调整**: 根据市场情况动态调整仓位
- **风险监控**: 持续监控风险指标变化

**风险评级**: 中等风险，平衡收益

*注意: 这是演示数据*
        """.strip(),

        'judge_decision': f"""
## 🎯 投资组合经理最终风险决策

综合三位风险分析师的意见，最终风险管理决策如下：

### 📊 风险综合评估
- **激进观点**: 高收益机会，建议积极参与
- **保守观点**: 风险较高，建议谨慎操作
- **中性观点**: 机会与风险并存，适度参与

### 🎯 最终风险决策
基于当前市场环境和{stock_symbol}的风险特征：

1. **风险等级**: 中等风险
2. **建议仓位**: 40%（平衡收益与风险）
3. **风险控制**: 严格执行止损策略
4. **监控频率**: 每日监控，及时调整

**决策理由**: 在控制风险的前提下，适度参与市场机会

*注意: 这是演示数据*
        """.strip()
    }

    demo_state['final_trade_decision'] = f"""
## 🎯 最终投资决策

经过分析师团队、研究团队、交易团队和风险管理团队的全面分析，最终投资决策如下：

### 📊 决策摘要
- **投资建议**: **{action}**
- **置信度**: {confidence:.1%}
- **风险评级**: 中等风险
- **预期收益**: {'10-20%' if action == '买入' else '规避损失' if action == '卖出' else '稳健持有'}

### 🎯 执行计划
1. **操作方向**: {action}
2. **目标仓位**: {'40%' if action == '买入' else '20%' if action == '卖出' else '维持现状'}
3. **执行时间**: {'1-2周内分批执行' if action != '持有' else '持续观察'}
4. **风险控制**: 严格执行止损止盈策略

### 📈 预期目标
- **目标价位**: {currency_symbol}{round(random.uniform(*price_range) * 1.15, 2)}
- **止损价位**: {currency_symbol}{round(random.uniform(*price_range) * 0.85, 2)}
- **投资期限**: {'3-6个月' if research_depth >= 3 else '1-3个月'}

### ⚠️ 重要提醒
这是基于当前市场环境和{stock_symbol}基本面的综合判断。投资有风险，请根据个人风险承受能力谨慎决策。

**免责声明**: 本分析仅供参考，不构成投资建议。

*注意: 这是演示数据，实际分析需要配置正确的API密钥*
    """

    return {
        'stock_symbol': stock_symbol,
        'analysis_date': analysis_date,
        'analysts': analysts,
        'research_depth': research_depth,
        'llm_provider': llm_provider,
        'llm_model': llm_model,
        'state': demo_state,
        'decision': demo_decision,
        'success': True,
        'error': None,
        'is_demo': True,
        'demo_reason': f"API调用失败，显示演示数据。错误信息: {error_msg}"
    }
