"""
统一的分析报告格式化工具

提供统一的报告提取和格式化函数，供 SimpleAnalysisService 和 UnifiedAnalysisService 使用。
确保报告格式一致，包含所有必要字段：
- 宏观报告：index_report（大盘分析）, sector_report（行业板块分析）
- 基础报告：market_report, sentiment_report, news_report, fundamentals_report
- 交易计划：investment_plan, trader_investment_plan, final_trade_decision
- 研究团队：bull_researcher, bear_researcher, research_team_decision
- 风险团队：risky_analyst, safe_analyst, neutral_analyst, risk_management_decision
"""

import logging
import uuid
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


# 所有标准报告字段
STANDARD_REPORT_FIELDS = [
    # 🆕 宏观分析报告（优先展示）
    'index_report',           # 大盘/指数分析
    'sector_report',          # 行业/板块分析
    # 个股分析报告
    'market_report',          # 市场技术分析
    'sentiment_report',       # 社交媒体情绪分析
    'news_report',            # 新闻事件分析
    'fundamentals_report',    # 基本面分析
    # 决策报告
    'investment_plan',        # 投资建议
    'trader_investment_plan', # 交易员计划
    'final_trade_decision'    # 最终交易决策
]


def extract_reports_from_state(state: Any) -> Dict[str, str]:
    """
    从 state 中提取所有报告内容

    Args:
        state: 分析状态对象（可以是字典或对象）

    Returns:
        包含所有报告的字典
    """
    reports = {}

    if state is None:
        return reports

    # 🔥 调试日志：显示 state 的顶层字段
    if isinstance(state, dict):
        logger.info(f"🔍 [ReportFormatter] state 顶层字段: {list(state.keys())}")
        # 🔥 检查 index_report 和 sector_report 是否存在
        if "index_report" in state:
            logger.info(f"🔍 [ReportFormatter] index_report 存在，长度: {len(str(state.get('index_report', '')))}")
        else:
            logger.warning(f"⚠️ [ReportFormatter] index_report 字段不存在于 state 中")
        if "sector_report" in state:
            logger.info(f"🔍 [ReportFormatter] sector_report 存在，长度: {len(str(state.get('sector_report', '')))}")
        else:
            logger.warning(f"⚠️ [ReportFormatter] sector_report 字段不存在于 state 中")

    # 1. 提取标准报告字段
    for field in STANDARD_REPORT_FIELDS:
        value = _get_field_value(state, field)
        if value and isinstance(value, str) and len(value.strip()) > 10:
            reports[field] = value.strip()
            logger.info(f"📊 [ReportFormatter] 提取报告: {field} - 长度: {len(value.strip())}")
        elif field in ['index_report', 'sector_report']:
            # 特别记录宏观报告的提取失败
            logger.warning(f"⚠️ [ReportFormatter] 宏观报告 {field} 未能提取: value={type(value)}, 内容长度={len(str(value)) if value else 0}")

    # 2. 提取研究团队辩论状态报告（investment_debate_state）
    debate_state = _get_field_value(state, 'investment_debate_state')
    if debate_state:
        _extract_investment_debate_reports(debate_state, reports)
    else:
        logger.warning("⚠️ [ReportFormatter] investment_debate_state 不存在或为空")

    # 3. 提取风险管理团队辩论状态报告（risk_debate_state）
    risk_state = _get_field_value(state, 'risk_debate_state')
    if risk_state:
        _extract_risk_debate_reports(risk_state, reports)
    else:
        logger.warning("⚠️ [ReportFormatter] risk_debate_state 不存在或为空")

    # 🔥 备选方案：直接从顶层 state 查找 bull_report, bear_report 等字段
    # 新工作流可能将报告存储在不同位置
    _extract_alternative_reports(state, reports)

    logger.info(f"📊 [ReportFormatter] 提取到 {len(reports)} 个报告: {list(reports.keys())}")
    return reports


def _extract_alternative_reports(state: Any, reports: Dict[str, str]):
    """
    备选方案：从 state 顶层或其他位置提取报告

    新工作流可能将报告存储在不同位置，如：
    - bull_report（而不是 investment_debate_state.bull_history）
    - bear_report（而不是 investment_debate_state.bear_history）
    """
    # 备选字段映射（包含v2.0 agent字段）
    alternative_mappings = {
        'bull_researcher': ['bull_report', 'bull_history', 'bull_analysis'],
        'bear_researcher': ['bear_report', 'bear_history', 'bear_analysis'],
        'neutral_analyst': ['neutral_report', 'neutral_history', 'neutral_analysis'],
        'trader_investment_plan': ['trader_investment_plan', 'trading_plan', 'trade_plan'],
        'research_team_decision': ['research_team_decision', 'investment_plan', 'investment_advice', 'judge_decision'],
        'risk_management_decision': ['risk_management_decision', 'risk_assessment', 'judge_decision'],
        'final_trade_decision': ['final_trade_decision', 'risk_assessment', 'investment_advice'],
        'investment_plan': ['investment_plan', 'investment_advice'],
        # v2.0 风险分析师字段映射
        'risky_analyst': ['risky_analyst', 'risky_opinion', 'risky_history'],
        'safe_analyst': ['safe_analyst', 'safe_opinion', 'safe_history'],
        'neutral_analyst': ['neutral_analyst', 'neutral_opinion', 'neutral_history'],
    }

    for report_key, alt_fields in alternative_mappings.items():
        if report_key in reports:
            continue  # 已经提取到了

        for alt_field in alt_fields:
            value = _get_field_value(state, alt_field)
            text_value = None
            if isinstance(value, str):
                text_value = value.strip()
            elif isinstance(value, dict):
                for k in ("content", "markdown", "text", "message", "report"):
                    v = value.get(k)
                    if isinstance(v, str) and v.strip():
                        text_value = v.strip()
                        break
            if text_value and len(text_value) > 10:
                reports[report_key] = text_value
                logger.info(f"📊 [ReportFormatter] 备选提取: {report_key} <- {alt_field}")
                break


def _get_field_value(obj: Any, field: str) -> Any:
    """安全获取字段值"""
    if obj is None:
        return None
    if hasattr(obj, field):
        return getattr(obj, field, None)
    elif isinstance(obj, dict) and field in obj:
        return obj[field]
    return None


def _extract_investment_debate_reports(debate_state: Any, reports: Dict[str, str]):
    """提取研究团队辩论报告"""
    # 🔥 调试日志：显示 investment_debate_state 的内容
    logger.info(f"🔍 [ReportFormatter] investment_debate_state 类型: {type(debate_state)}")
    if isinstance(debate_state, dict):
        logger.info(f"🔍 [ReportFormatter] investment_debate_state 字段: {list(debate_state.keys())}")

    # 多头研究员
    bull_content = _get_field_value(debate_state, 'bull_history')
    logger.info(f"🔍 [ReportFormatter] bull_history 类型: {type(bull_content)}, 值: {str(bull_content)[:100] if bull_content else None}")
    if bull_content and isinstance(bull_content, str) and len(bull_content.strip()) > 10:
        reports['bull_researcher'] = bull_content.strip()
        logger.info(f"📊 [ReportFormatter] 提取: bull_researcher - 长度: {len(bull_content.strip())}")

    # 空头研究员
    bear_content = _get_field_value(debate_state, 'bear_history')
    logger.info(f"🔍 [ReportFormatter] bear_history 类型: {type(bear_content)}, 值: {str(bear_content)[:100] if bear_content else None}")
    if bear_content and isinstance(bear_content, str) and len(bear_content.strip()) > 10:
        reports['bear_researcher'] = bear_content.strip()
        logger.info(f"📊 [ReportFormatter] 提取: bear_researcher - 长度: {len(bear_content.strip())}")

    # 研究经理决策
    decision_content = _get_field_value(debate_state, 'judge_decision')
    logger.info(f"🔍 [ReportFormatter] judge_decision 类型: {type(decision_content)}, 值: {str(decision_content)[:100] if decision_content else None}")

    # ✅ 修复：只在 judge_decision 有实际内容时才使用
    # 不要在空字符串时使用 str(debate_state) 作为备选
    if decision_content and isinstance(decision_content, str) and len(decision_content.strip()) > 10:
        reports['research_team_decision'] = decision_content.strip()
        logger.info(f"📊 [ReportFormatter] 提取: research_team_decision - 长度: {len(decision_content.strip())}")
    else:
        logger.warning(f"⚠️ [ReportFormatter] research_team_decision 为空或过短，跳过")


def _extract_risk_debate_reports(risk_state: Any, reports: Dict[str, str]):
    """提取风险管理团队辩论报告"""
    # 🔥 调试日志：显示 risk_debate_state 的内容
    logger.info(f"🔍 [ReportFormatter] risk_debate_state 类型: {type(risk_state)}")
    if isinstance(risk_state, dict):
        logger.info(f"🔍 [ReportFormatter] risk_debate_state 字段: {list(risk_state.keys())}")

    # 激进分析师
    risky_content = _get_field_value(risk_state, 'risky_history')
    logger.info(f"🔍 [ReportFormatter] risky_history: {str(risky_content)[:100] if risky_content else None}")
    if risky_content and isinstance(risky_content, str) and len(risky_content.strip()) > 10:
        reports['risky_analyst'] = risky_content.strip()
        logger.info(f"📊 [ReportFormatter] 提取: risky_analyst - 长度: {len(risky_content.strip())}")

    # 保守分析师
    safe_content = _get_field_value(risk_state, 'safe_history')
    logger.info(f"🔍 [ReportFormatter] safe_history: {str(safe_content)[:100] if safe_content else None}")
    if safe_content and isinstance(safe_content, str) and len(safe_content.strip()) > 10:
        reports['safe_analyst'] = safe_content.strip()
        logger.info(f"📊 [ReportFormatter] 提取: safe_analyst - 长度: {len(safe_content.strip())}")

    # 中性分析师
    neutral_content = _get_field_value(risk_state, 'neutral_history')
    logger.info(f"🔍 [ReportFormatter] neutral_history: {str(neutral_content)[:100] if neutral_content else None}")
    if neutral_content and isinstance(neutral_content, str) and len(neutral_content.strip()) > 10:
        reports['neutral_analyst'] = neutral_content.strip()
        logger.info(f"📊 [ReportFormatter] 提取: neutral_analyst - 长度: {len(neutral_content.strip())}")

    # 风险管理决策
    risk_decision = _get_field_value(risk_state, 'judge_decision')
    logger.info(f"🔍 [ReportFormatter] risk judge_decision 类型: {type(risk_decision)}, 值: {str(risk_decision)[:100] if risk_decision else None}")

    # ✅ 修复：只在 judge_decision 有实际内容时才使用
    # 不要在空字符串时使用 str(risk_state) 作为备选
    if risk_decision and isinstance(risk_decision, str) and len(risk_decision.strip()) > 10:
        reports['risk_management_decision'] = risk_decision.strip()
        logger.info(f"📊 [ReportFormatter] 提取: risk_management_decision - 长度: {len(risk_decision.strip())}")
    else:
        logger.warning(f"⚠️ [ReportFormatter] risk_management_decision 为空或过短，跳过")


# 投资建议英文到中文的映射
ACTION_TRANSLATION = {
    'BUY': '买入', 'SELL': '卖出', 'HOLD': '持有',
    'buy': '买入', 'sell': '卖出', 'hold': '持有',
}


def format_decision(
    decision_raw: Dict[str, Any],
    fallback_text: str = "",
    quick_model: str = None,
    stock_code: str = None
) -> Dict[str, Any]:
    """
    格式化决策为标准格式

    🔥 核心修复：如果 decision_raw 缺少关键字段（target_price, reasoning），
    使用 SignalProcessor 从 fallback_text 中提取结构化信息。

    Args:
        decision_raw: 原始决策字典
        fallback_text: 备用文本（通常是 final_trade_decision 或 risk_management_decision）
        quick_model: 用户选择的快速分析模型名称
        stock_code: 股票代码（用于 SignalProcessor 判断货币类型）

    Returns:
        格式化后的决策字典，包含 action, confidence, risk_score, target_price, reasoning
    """
    import re

    if not decision_raw:
        decision_raw = {}

    # 🔥 如果 decision_raw 缺少关键字段且有 fallback_text，使用 SignalProcessor 处理
    needs_signal_processing = (
        fallback_text and
        len(fallback_text) > 50 and
        (decision_raw.get('target_price') is None or not decision_raw.get('reasoning'))
    )

    if needs_signal_processing:
        try:
            from tradingagents.graph.signal_processing import SignalProcessor
            from tradingagents.graph.trading_graph import create_llm_by_provider

            # 根据传入的 quick_model 从数据库查找对应配置
            quick_llm = None
            target_model = quick_model  # 使用用户选择的模型

            try:
                from pymongo import MongoClient
                from app.core.config import settings

                client = MongoClient(settings.MONGO_URI)
                db = client[settings.MONGO_DB]
                doc = db.system_configs.find_one({"is_active": True}, sort=[("version", -1)])

                if doc and "llm_configs" in doc:
                    selected_cfg = None

                    # 🔥 优先根据传入的 quick_model 查找对应配置
                    if target_model and target_model != "Unknown":
                        for cfg in doc["llm_configs"]:
                            if cfg.get("model_name") == target_model:
                                selected_cfg = cfg
                                logger.info(f"📊 [ReportFormatter] 找到用户指定的模型配置: {target_model}")
                                break

                    # 如果没找到指定模型，使用国产 LLM 备选
                    if not selected_cfg:
                        preferred_providers = ["dashscope", "deepseek", "zhipu", "siliconflow"]
                        for cfg in doc["llm_configs"]:
                            if cfg.get("enabled", True):
                                provider = cfg.get("provider", "").lower()
                                if provider in preferred_providers:
                                    selected_cfg = cfg
                                    logger.info(f"📊 [ReportFormatter] 使用备选国产模型: {cfg.get('model_name')}")
                                    break

                    if selected_cfg:
                        quick_llm = create_llm_by_provider(
                            provider=selected_cfg.get("provider", "dashscope"),
                            model=selected_cfg.get("model_name", "qwen-turbo"),
                            backend_url=selected_cfg.get("default_base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
                            temperature=0.1,
                            max_tokens=2000,
                            timeout=60,
                            api_key=selected_cfg.get("api_key")
                        )
                        logger.info(f"📊 [ReportFormatter] 使用模型创建 LLM: {selected_cfg.get('model_name')}")
                client.close()
            except Exception as db_err:
                logger.warning(f"⚠️ [ReportFormatter] 从数据库获取LLM配置失败: {db_err}")

            # 如果数据库配置失败，使用默认配置
            if quick_llm is None:
                quick_llm = create_llm_by_provider(
                    provider="dashscope",
                    model="qwen-turbo",
                    backend_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                    temperature=0.1,
                    max_tokens=2000,
                    timeout=60
                )
                logger.info("📊 [ReportFormatter] 使用默认配置创建 LLM: qwen-turbo")

            signal_processor = SignalProcessor(quick_llm)
            processed = signal_processor.process_signal(fallback_text, stock_code)
            logger.info(f"📊 [ReportFormatter] 使用 SignalProcessor 处理文本，结果: action={processed.get('action')}, target_price={processed.get('target_price')}")

            # 合并处理结果（优先使用 decision_raw 中的值，如果有的话）
            if decision_raw.get('target_price') is None and processed.get('target_price') is not None:
                decision_raw['target_price'] = processed['target_price']
            if not decision_raw.get('reasoning') and processed.get('reasoning'):
                decision_raw['reasoning'] = processed['reasoning']
            if not decision_raw.get('action') and processed.get('action'):
                decision_raw['action'] = processed['action']
            if not decision_raw.get('confidence') and processed.get('confidence'):
                decision_raw['confidence'] = processed['confidence']
            if not decision_raw.get('risk_score') and processed.get('risk_score'):
                decision_raw['risk_score'] = processed['risk_score']

        except Exception as e:
            logger.warning(f"⚠️ [ReportFormatter] SignalProcessor 处理失败: {e}")

    # 获取 action
    action = decision_raw.get('action', '持有')
    chinese_action = ACTION_TRANSLATION.get(action, action) if action else '持有'

    # 获取 target_price
    target_price = decision_raw.get('target_price')
    if target_price is not None and target_price != 'N/A':
        try:
            if isinstance(target_price, str):
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

    # 如果 target_price 仍然为空，尝试从 fallback_text 中提取（备用方案）
    if target_price is None and fallback_text:
        price_patterns = [
            r'目标价[格]?[：:]\s*([0-9.]+)',
            r'target_price[：:]\s*([0-9.]+)',
            r'价格[：:]\s*([0-9.]+)',
        ]
        for pattern in price_patterns:
            match = re.search(pattern, fallback_text, re.IGNORECASE)
            if match:
                try:
                    target_price = float(match.group(1))
                    logger.debug(f"📊 [ReportFormatter] 从文本中提取目标价格: {target_price}")
                    break
                except ValueError:
                    pass

    # 获取 reasoning - 清理 Markdown 格式
    # 🔥 兼容新旧版本：reasoning 或 rationale
    reasoning = decision_raw.get('reasoning', '') or decision_raw.get('rationale', '')
    if not reasoning and fallback_text:
        # 清理 Markdown 格式标记
        cleaned_text = _clean_markdown(fallback_text)
        reasoning = cleaned_text[:300] + "..." if len(cleaned_text) > 300 else cleaned_text
    elif reasoning:
        # 清理已有的 reasoning 中的 Markdown 格式
        reasoning = _clean_markdown(reasoning)

    return {
        'action': chinese_action,
        'confidence': float(decision_raw.get('confidence', 0.5)),
        'risk_score': float(decision_raw.get('risk_score', 0.3)),
        'target_price': target_price,
        'reasoning': reasoning or '暂无分析推理'
    }


def _clean_markdown(text: str) -> str:
    """
    清理 Markdown 格式标记

    Args:
        text: 原始文本

    Returns:
        清理后的文本
    """
    import re

    if not text:
        return text

    # 🔥 先处理转义字符（处理 \\n 等）
    text = text.replace('\\n', '\n')
    text = text.replace('\\t', ' ')
    text = text.replace('\\r', '')

    # 移除 Markdown 分隔线 (--- 或 ___ 或 ***)
    text = re.sub(r'^[\-_\*]{3,}\s*$', '', text, flags=re.MULTILINE)

    # 移除 Markdown 标题标记 (###, ##, #)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

    # 移除引用标记 (>)
    text = re.sub(r'^>\s*', '', text, flags=re.MULTILINE)

    # 移除粗体标记 (**text** 或 __text__)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)

    # 移除斜体标记 (*text* 或 _text_)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'_(.+?)_', r'\1', text)

    # 移除代码块标记 (```code```)
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)

    # 移除行内代码标记 (`code`)
    text = re.sub(r'`(.+?)`', r'\1', text)

    # 移除链接标记 ([text](url))
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)

    # 移除列表标记 (-, *, +, 数字.)
    text = re.sub(r'^[\-\*\+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\d+\.\s+', '', text, flags=re.MULTILINE)

    # 移除中文数字列表标记（一、二、三、）
    text = re.sub(r'^[一二三四五六七八九十]+[、\.]\s*', '', text, flags=re.MULTILINE)

    # 移除多余的空行
    text = re.sub(r'\n{3,}', '\n\n', text)

    # 移除行首的空白
    text = re.sub(r'^\s+', '', text, flags=re.MULTILINE)

    return text.strip()


def generate_summary_recommendation(
    reports: Dict[str, str],
    decision: Dict[str, Any],
    stock_code: str
) -> Tuple[str, str]:
    """
    生成 summary 和 recommendation

    Args:
        reports: 报告字典
        decision: 格式化后的决策
        stock_code: 股票代码

    Returns:
        (summary, recommendation) 元组
    """
    summary = ""
    recommendation = ""

    # 1. 从 final_trade_decision 提取 summary
    if 'final_trade_decision' in reports:
        content = reports['final_trade_decision']
        if len(content) > 50:
            summary = content[:200].replace('#', '').replace('*', '').strip()
            if len(content) > 200:
                summary += "..."

    # 2. 如果没有，从其他报告提取
    if not summary:
        for report_name in ['investment_plan', 'trader_investment_plan', 'market_report']:
            if report_name in reports:
                content = reports[report_name]
                if len(content) > 100:
                    summary = content[:200].replace('#', '').replace('*', '').strip()
                    if len(content) > 200:
                        summary += "..."
                    break

    # 3. 最后的备用方案
    if not summary:
        summary = f"对{stock_code}的分析已完成，请查看详细报告。"

    # 4. 生成 recommendation
    action = decision.get('action', '持有')
    target_price = decision.get('target_price')
    reasoning = decision.get('reasoning', '')

    recommendation = f"投资建议：{action}。"
    if target_price:
        recommendation += f"目标价格：{target_price}元。"
    if reasoning and len(reasoning) < 200:
        recommendation += f"决策依据：{reasoning}"

    if not recommendation:
        recommendation = "请参考详细分析报告做出投资决策。"

    return summary, recommendation


def calculate_risk_level(risk_score: float) -> str:
    """
    根据风险评分计算风险等级

    Args:
        risk_score: 风险评分 (0-1)

    Returns:
        风险等级字符串
    """
    if risk_score >= 0.7:
        return "高"
    elif risk_score >= 0.4:
        return "中等"
    else:
        return "低"


def format_analysis_result(
    raw_result: Dict[str, Any],
    stock_code: str,
    stock_name: str,
    analysis_date: str,
    task_id: str,
    analysts: list = None,
    research_depth: str = "标准",
    quick_model: str = "Unknown",
    deep_model: str = "Unknown",
    execution_time: float = 0,
) -> Dict[str, Any]:
    """
    统一的分析结果格式化函数

    Args:
        raw_result: 原始分析结果（通常是 LangGraph state）
        stock_code: 股票代码
        stock_name: 股票名称
        analysis_date: 分析日期
        task_id: 任务 ID
        analysts: 选中的分析师列表
        research_depth: 研究深度
        quick_model: 快速分析模型
        deep_model: 深度分析模型
        execution_time: 执行时间（秒）

    Returns:
        格式化后的完整分析结果
    """
    # 1. 从 raw_result 中提取报告
    reports = extract_reports_from_state(raw_result)

    # 2. 解析并格式化决策
    final_decision = raw_result.get("final_decision", {})
    final_trade_decision = raw_result.get("final_trade_decision", "")

    # 🔥 调试日志：检查 final_decision 的内容
    logger.info(f"🔍 [ReportFormatter] final_decision 类型: {type(final_decision)}")
    if isinstance(final_decision, dict):
        logger.info(f"🔍 [ReportFormatter] final_decision 字段: {list(final_decision.keys())}")
        logger.info(f"🔍 [ReportFormatter] final_decision.target_price: {final_decision.get('target_price')}")
        logger.info(f"🔍 [ReportFormatter] final_decision.reasoning: {str(final_decision.get('reasoning', ''))[:100]}...")
    logger.info(f"🔍 [ReportFormatter] final_trade_decision 长度: {len(final_trade_decision) if final_trade_decision else 0}")

    # 🔥 传入 quick_model 和 stock_code，使用用户选择的模型
    formatted_decision = format_decision(
        final_decision,
        final_trade_decision,
        quick_model=quick_model,
        stock_code=stock_code
    )
    logger.info(f"🔍 [ReportFormatter] formatted_decision: action={formatted_decision.get('action')}, target_price={formatted_decision.get('target_price')}")

    # 3. 生成 summary 和 recommendation
    summary, recommendation = generate_summary_recommendation(
        reports, formatted_decision, stock_code
    )

    # 4. 计算风险等级
    risk_level = calculate_risk_level(formatted_decision.get('risk_score', 0.3))

    # 5. 构建完整结果
    result = {
        "success": True,
        "analysis_id": str(uuid.uuid4()),
        "task_id": task_id,
        "stock_code": stock_code,
        "stock_symbol": stock_code,
        "stock_name": stock_name,
        "analysis_date": analysis_date,

        # 核心字段 - 前端依赖这些
        "summary": summary,
        "recommendation": recommendation,
        "confidence_score": formatted_decision.get("confidence", 0.5),
        "risk_level": risk_level,
        "key_points": [],

        # decision 字段 - 前端显示分析倾向、分析依据等
        "decision": formatted_decision,

        # 报告内容 - 包含多头、空头、激进、保守、中性等
        "reports": reports,

        # 原始状态（供调试）
        "state": raw_result,
        "detailed_analysis": final_decision,

        # 分析师和模型信息
        "analysts": analysts or [],
        "research_depth": research_depth,
        "model_info": f"{quick_model}/{deep_model}",
        "quick_model": quick_model,
        "deep_model": deep_model,

        # 性能指标
        "execution_time": execution_time,
        "tokens_used": raw_result.get("tokens_used", 0),
        "performance_metrics": raw_result.get("performance_metrics", {}),
    }

    logger.info(f"✅ [ReportFormatter] 格式化完成: decision.action={formatted_decision.get('action')}, reports={len(reports)}个")
    return result
