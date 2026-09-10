"""
统一的研究报告格式化工具

提供统一的报告提取和格式化函数，供 SimpleAnalysisService 和 UnifiedAnalysisService 使用。
确保报告格式一致，包含所有必要字段：
- 宏观报告：index_report（大盘研究）, sector_report（行业板块研究）
- 基础报告：market_report, sentiment_report, news_report, fundamentals_report
- 研究结论：investment_plan, trader_investment_plan, final_trade_decision
- 研究团队：bull_researcher, bear_researcher, research_team_decision
- 风险团队：risky_analyst, safe_analyst, neutral_analyst, risk_management_decision
"""

import logging
import uuid
import json
import re
from typing import Dict, Any, Optional, Tuple

from app.utils.compliance import normalize_research_brief_lists, sanitize_display_report_text, sanitize_report_artifacts

logger = logging.getLogger(__name__)
_ERROR_RESULT_PATTERNS = (
    re.compile(r'^\{[\s\S]*["\']error["\']\s*:\s*["\'][\s\S]*["\']\s*,\s*["\']success["\']\s*:\s*False[\s\S]*\}$'),
    re.compile(r'^执行失败[:：].*$', re.IGNORECASE),
)

def _build_report_failure_fallback(report_type: str) -> str:
    fallback_map = {
        "risk": "风险审阅模块执行未完成，当前风险结论仍待验证。",
        "investment": "综合研究结论模块执行未完成，当前结论仍待验证。",
        "final_decision": "综合研究结论模块执行未完成，当前结论仍待验证。",
    }
    return fallback_map.get(report_type, "工具执行或模型生成未完成，当前结论仍待验证。")


def _is_error_payload_text(content: str) -> bool:
    stripped = (content or "").strip()
    if not stripped:
        return False
    return any(pattern.match(stripped) for pattern in _ERROR_RESULT_PATTERNS)
    logger.info(f"🔄 [JSON转换] 开始转换，报告类型: {report_type}, 内容长度: {len(content) if content else 0}")

    if _is_error_payload_text(content):
        logger.warning(f"⚠️ [JSON转换] 检测到错误载荷文本，按降级文案返回，报告类型: {report_type}")
        return _build_report_failure_fallback(report_type)


DISPLAY_SANITIZED_REPORT_KEYS = {
    'bull_researcher',
    'bull_report',
    'bear_researcher',
    'bear_report',
    'research_team_decision',
    'investment_plan',
    'trader_investment_plan',
    'risky_analyst',
    'risky_opinion',
    'safe_analyst',
    'safe_opinion',
    'neutral_analyst',
    'neutral_opinion',
    'risk_management_decision',
}


# 所有标准报告字段
STANDARD_REPORT_FIELDS = [
    # 🆕 宏观研究报告（优先展示）
    'index_report',           # 大盘/指数分析
    'sector_report',          # 行业/板块分析
    # 个股研究报告
    'market_report',          # 市场技术分析
    'sentiment_report',       # 社交媒体情绪分析
    'news_report',            # 新闻研究
    'fundamentals_report',    # 基本面分析
    'chip_report',            # 筹码分布分析
    # 研究结论报告
    # 'investment_plan',        # 研究经理结论（作为 research_team_decision 的备选）
    'trader_investment_plan', # 研究整合意见
    'research_team_decision', # 研究团队结论
    'risk_management_decision', # 风险审阅结论
    'final_trade_decision'    # 综合研究结论
]


def _failure_shape_message(value: dict) -> Optional[str]:
    """🛡️ Q1: 识别失败/空响应包装 dict，返回用户友好提示（非失败形态返回 None）。

    覆盖 {'success': False, 'error': ...}（节点异常）与
    {'content': '', 'success': True}（空响应被包装成成功）两类。
    """
    if not isinstance(value, dict):
        return None
    content_val = value.get("content")
    if value.get("success") is False or (
        value.get("success") is True
        and not (isinstance(content_val, str) and content_val.strip())
    ):
        err = value.get("error") or "模型响应异常（空内容）"
        return f"> ⚠️ **本节生成失败**：{err}。建议重新分析以获取完整报告。"
    return None


def _extract_report_text(report_key: str, value: Any) -> Optional[str]:
    text_value = None

    if isinstance(value, str):
        text_value = value.strip()
    elif isinstance(value, dict):
        # 🛡️ Q1: 失败/空响应形态 → 渲染友好提示而非跳过（裸 dict 严禁进报告）
        _failure_msg = _failure_shape_message(value)
        if _failure_msg:
            logger.warning(f"⚠️ [ReportFormatter] {report_key} 为失败/空响应形态，渲染提示")
            return _failure_msg
        for key in ("content", "markdown", "text", "message", "report"):
            nested_value = value.get(key)
            if isinstance(nested_value, str) and nested_value.strip():
                text_value = nested_value.strip()
                break
    elif value is not None:
        raw_text = str(value).strip()
        if raw_text:
            text_value = raw_text

    if not text_value or len(text_value) <= 10:
        return None

    if report_key == 'final_trade_decision':
        return _convert_json_to_markdown(text_value, "final_decision")
    if report_key == 'research_team_decision':
        return _convert_json_to_markdown(text_value, "final_decision")
    if report_key == 'risk_management_decision':
        return _convert_json_to_markdown(text_value, "risk")
    return _clean_report_for_display(report_key, text_value)


def _extract_reports_from_mapping(mapping: Dict[str, Any], reports: Dict[str, str], source_name: str) -> None:
    if not isinstance(mapping, dict):
        return

    logger.info(f"🔍 [ReportFormatter] {source_name} 字段: {list(mapping.keys())}")

    for field in STANDARD_REPORT_FIELDS:
        if field in reports:
            continue
        extracted = _extract_report_text(field, mapping.get(field))
        if extracted:
            reports[field] = extracted
            logger.info(f"📊 [ReportFormatter] 提取报告: {field} <- {source_name} - 长度: {len(extracted)}")

    for report_key in DISPLAY_SANITIZED_REPORT_KEYS:
        if report_key in reports:
            continue
        extracted = _extract_report_text(report_key, mapping.get(report_key))
        if extracted:
            reports[report_key] = extracted
            logger.info(f"📊 [ReportFormatter] 提取报告: {report_key} <- {source_name} - 长度: {len(extracted)}")


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

    nested_reports = _get_field_value(state, 'reports')
    has_nested_reports = isinstance(nested_reports, dict) and bool(nested_reports)

    if has_nested_reports:
        _extract_reports_from_mapping(nested_reports, reports, 'state.reports')

    # 🔥 调试日志：显示 state 的顶层字段
    if isinstance(state, dict):
        logger.info(f"🔍 [ReportFormatter] state 顶层字段: {list(state.keys())}")
        # 🔥 检查 index_report 和 sector_report 是否存在
        if "index_report" in state:
            logger.info(f"🔍 [ReportFormatter] index_report 存在，长度: {len(str(state.get('index_report', '')))}")
        elif not has_nested_reports:
            logger.warning(f"⚠️ [ReportFormatter] index_report 字段不存在于 state 中")
        if "sector_report" in state:
            logger.info(f"🔍 [ReportFormatter] sector_report 存在，长度: {len(str(state.get('sector_report', '')))}")
        elif not has_nested_reports:
            logger.warning(f"⚠️ [ReportFormatter] sector_report 字段不存在于 state 中")

    # 1. 提取报告字段（优先从引擎产出的 structured_reports 读取，自动包含新 agent 输出）
    structured_reports = _get_field_value(state, 'structured_reports')
    if isinstance(structured_reports, dict) and structured_reports:
        for field, entry in structured_reports.items():
            if field in reports:
                continue
            if isinstance(entry, dict) and entry.get("success") and entry.get("content"):
                content = entry["content"]
                if isinstance(content, str) and len(content.strip()) > 10:
                    reports[field] = content.strip()
                    logger.info(f"📊 [ReportFormatter] 从 structured_reports 提取: {field} - 长度: {len(content.strip())}")
    else:
        # 回退：从 report_manifest 推导
        manifest = _get_field_value(state, 'report_manifest')
        if isinstance(manifest, list) and manifest:
            for m in manifest:
                field = m.get("field")
                if field and field not in reports:
                    value = _get_field_value(state, field)
                    extracted = _extract_report_text(field, value)
                    if extracted:
                        reports[field] = extracted
                        logger.info(f"📊 [ReportFormatter] 从 manifest 提取: {field} - 长度: {len(extracted)}")
        else:
            # 最后回退：旧版硬编码列表
            for field in STANDARD_REPORT_FIELDS:
                if field in reports:
                    continue
                value = _get_field_value(state, field)
                extracted = _extract_report_text(field, value)
                if extracted:
                    reports[field] = extracted
                    logger.info(f"📊 [ReportFormatter] 从硬编码列表提取: {field} - 长度: {len(extracted)}")

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


def _clean_report_for_display(report_key: str, text: str) -> str:
    cleaned_text = _remove_author_signature(text.strip())
    artifact_cleaned_text = sanitize_report_artifacts(cleaned_text)
    if artifact_cleaned_text:
        cleaned_text = artifact_cleaned_text
    elif any(token in cleaned_text for token in ("</tool_call>", "<tool_call", '"name": "get_')):
        if report_key == 'news_report':
            return "工具结果未成功展开为新闻报告，当前新闻结论仍待验证。"
        return "工具结果未成功展开为正文，当前结论仍待验证。"

    if report_key in DISPLAY_SANITIZED_REPORT_KEYS:
        cleaned_text = sanitize_display_report_text(cleaned_text, fallback=cleaned_text)
    return cleaned_text


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
        # 🔥 research_team_decision 可以从 investment_plan 字段读取（某些工作流存储在此）
        'research_team_decision': ['research_team_decision', 'investment_plan', 'investment_advice', 'judge_decision'],
        'risk_management_decision': ['risk_management_decision', 'risk_assessment', 'judge_decision'],
        'final_trade_decision': ['final_trade_decision'],
        # 🔥 移除 investment_plan 作为独立字段（避免与 trader_investment_plan 混淆）
        # 'investment_plan': ['investment_plan', 'investment_advice'],
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
                # 🛡️ Q1: 失败/空响应形态 → 渲染友好提示（裸 dict 严禁进报告）
                _failure_msg = _failure_shape_message(value)
                if _failure_msg:
                    logger.warning(
                        f"⚠️ [ReportFormatter] 备选提取 {report_key} <- {alt_field} 为失败/空响应形态，渲染提示"
                    )
                    reports[report_key] = _failure_msg
                    break
                for k in ("content", "markdown", "text", "message", "report"):
                    v = value.get(k)
                    if isinstance(v, str) and v.strip():
                        text_value = v.strip()
                        break
            if text_value and len(text_value) > 10:
                # 🔥 对于可能包含 JSON 的字段，转换为 Markdown
                if report_key == 'final_trade_decision':
                    markdown_value = _convert_json_to_markdown(text_value, "final_decision")
                    reports[report_key] = markdown_value
                    logger.info(f"📊 [ReportFormatter] 备选提取: {report_key} <- {alt_field} (已转换JSON->Markdown)")
                elif report_key == 'research_team_decision':
                    # 研究团队结论也可能是 JSON 格式
                    logger.info(f"🔍 [ReportFormatter] 备选提取检测到 research_team_decision，准备转换 JSON")
                    logger.info(f"🔍 [ReportFormatter] 原始内容前500字符: {text_value[:500]}")
                    markdown_value = _convert_json_to_markdown(text_value, "final_decision")
                    reports[report_key] = markdown_value
                    logger.info(f"📊 [ReportFormatter] 备选提取: {report_key} <- {alt_field} (已转换JSON->Markdown)")
                    logger.info(f"📊 [ReportFormatter] 转换后内容前500字符: {markdown_value[:500]}")
                elif report_key == 'risk_management_decision':
                    # 风险管理决策也可能是 JSON 格式
                    markdown_value = _convert_json_to_markdown(text_value, "risk")
                    reports[report_key] = markdown_value
                    logger.info(f"📊 [ReportFormatter] 备选提取: {report_key} <- {alt_field} (已转换JSON->Markdown)")
                else:
                    # 🔥 清理AI生成的署名信息
                    cleaned_value = _clean_report_for_display(report_key, text_value)
                    reports[report_key] = cleaned_value
                    logger.info(f"📊 [ReportFormatter] 备选提取: {report_key} <- {alt_field} (已清理署名)")
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


def _convert_json_to_markdown(content: str, report_type: str = "investment") -> str:
    """
    将 JSON 格式的报告转换为 Markdown 格式

    Args:
        content: 报告内容（可能是 JSON 字符串或普通文本）
        report_type: 报告类型（"investment"、"risk" 或 "final_decision"）

    Returns:
        Markdown 格式的报告内容
    """
    logger.info(f"🔄 [JSON转换] ========== 开始转换 ==========")
    logger.info(f"🔄 [JSON转换] 报告类型: {report_type}")
    logger.info(f"🔄 [JSON转换] 内容长度: {len(content) if content else 0}")
    logger.info(f"🔄 [JSON转换] 内容类型: {type(content)}")

    if not content or not isinstance(content, str):
        logger.warning(f"⚠️ [JSON转换] 内容为空或不是字符串，直接返回")
        return content

    content = content.strip()
    logger.info(f"🔄 [JSON转换] 内容前500字符: {content[:500]}")
    logger.info(f"🔄 [JSON转换] 是否包含 '```json': {'```json' in content}")
    logger.info(f"🔄 [JSON转换] 是否以 {{ 开头: {content.startswith('{')}")

    if _is_error_payload_text(content):
        logger.warning(f"⚠️ [JSON转换] 检测到错误载荷文本，按降级文案返回，报告类型: {report_type}")
        return _build_report_failure_fallback(report_type)

    # 检查是否是 JSON 格式
    json_obj = None

    # 1. 尝试提取 JSON 代码块
    if "```json" in content:
        logger.info(f"🔄 [JSON转换] 检测到 JSON 代码块")
        json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1).strip()
            logger.info(f"🔄 [JSON转换] 提取的 JSON 字符串长度: {len(json_str)}, 前200字符: {json_str[:200]}")
            
            # 🔥 修复常见的 JSON 格式问题
            # 1. 修复 price_analysis_range: 295.29-442.93 -> [295.29, 442.93]
            # 匹配模式: "price_analysis_range": 数字-数字
            json_str = re.sub(
                r'"price_analysis_range"\s*:\s*(\d+\.?\d*)\s*-\s*(\d+\.?\d*)',
                r'"price_analysis_range": [\1, \2]',
                json_str
            )
            
            try:
                json_obj = json.loads(json_str)
                logger.info(f"✅ [JSON转换] JSON 代码块解析成功，字段: {list(json_obj.keys()) if isinstance(json_obj, dict) else 'N/A'}")
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️ [JSON转换] JSON 代码块解析失败: {e}")
                # 如果修复后仍然失败，记录修复后的内容用于调试
                logger.debug(f"🔍 [JSON转换] 修复后的 JSON 字符串前500字符: {json_str[:500]}")

    # 2. 尝试直接解析 JSON
    if json_obj is None and content.startswith("{"):
        logger.info(f"🔄 [JSON转换] 检测到以 {{ 开头，尝试直接解析 JSON")
        # 🔥 修复常见的 JSON 格式问题
        fixed_content = re.sub(
            r'"price_analysis_range"\s*:\s*(\d+\.?\d*)\s*-\s*(\d+\.?\d*)',
            r'"price_analysis_range": [\1, \2]',
            content
        )
        try:
            json_obj = json.loads(fixed_content)
            logger.info(f"✅ [JSON转换] 直接 JSON 解析成功，字段: {list(json_obj.keys()) if isinstance(json_obj, dict) else 'N/A'}")
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ [JSON转换] 直接 JSON 解析失败: {e}")

    # 如果不是 JSON，直接返回原内容
    if json_obj is None:
        logger.warning(f"⚠️ [JSON转换] 不是 JSON 格式，直接返回原内容")
        logger.warning(f"⚠️ [JSON转换] 原内容前1000字符: {content[:1000]}")
        return content

    # 根据报告类型转换为 Markdown
    logger.info(f"🔄 [JSON转换] 开始转换为 Markdown，报告类型: {report_type}")
    logger.info(f"🔄 [JSON转换] JSON 对象字段: {list(json_obj.keys()) if isinstance(json_obj, dict) else 'N/A'}")

    if report_type == "investment":
        result = _convert_investment_json_to_markdown(json_obj)
        logger.info(f"✅ [JSON转换] 研究结论转换完成，Markdown 长度: {len(result)}")
        logger.info(f"✅ [JSON转换] Markdown 前500字符: {result[:500]}")
        return result
    elif report_type == "risk":
        result = _convert_risk_json_to_markdown(json_obj)
        logger.info(f"✅ [JSON转换] 风险评估转换完成，Markdown 长度: {len(result)}")
        logger.info(f"✅ [JSON转换] Markdown 前500字符: {result[:500]}")
        return result
    elif report_type == "final_decision":
        result = _convert_final_decision_json_to_markdown(json_obj)
        logger.info(f"✅ [JSON转换] 最终研究结论转换完成，Markdown 长度: {len(result)}")
        logger.info(f"✅ [JSON转换] Markdown 前500字符: {result[:500]}")
        return result
    else:
        logger.warning(f"⚠️ [JSON转换] 未知的报告类型: {report_type}，直接返回原内容")
        return content


def _convert_investment_json_to_markdown(json_obj: Dict[str, Any]) -> str:
    """将研究结论 JSON 转换为 Markdown"""
    logger.info(f"🔄 [研究结论转换] JSON 字段: {list(json_obj.keys())}")
    lines = []
    
    # 研究观点摘要
    action = json_obj.get("analysis_view") or json_obj.get("action", "")
    logger.info(f"🔄 [研究结论转换] action: {action}")
    if action:
        action_map = {
            # 新合规术语（乐观/审慎/中性）优先
            "乐观": "🟢 乐观",
            "审慎": "🟡 审慎",
            "中性": "⚪ 中性",
            # 旧市场观点术语 + 旧交易指令（兼容存量数据，映射为新合规表述）
            "买入": "🟢 乐观",
            "持有": "⚪ 中性",
            "卖出": "🟡 审慎",
            "看涨": "🟢 乐观",
            "看跌": "🟡 审慎",
        }
        action_display = action_map.get(action, action)
        lines.append(f"## 💡 研究观点\n\n**观点**: {action_display}\n\n")
    
    # 信心度
    confidence = json_obj.get("confidence")
    logger.info(f"🔄 [研究结论转换] confidence: {confidence}")
    if confidence is not None:
        # 🔥 修复：处理 0-1 小数和 0-100 整数两种情况
        try:
            conf_value = float(confidence)
            # 如果是 0-1 的小数，转换为百分比
            if conf_value <= 1:
                conf_display = int(conf_value * 100)
            else:
                conf_display = int(conf_value)
            lines.append(f"**信心度**: {conf_display}/100\n\n")
        except (ValueError, TypeError):
            lines.append(f"**信心度**: {confidence}/100\n\n")
    
    # 风险评分
    risk_score = json_obj.get("risk_score")
    logger.info(f"🔄 [研究结论转换] risk_score: {risk_score}")
    if risk_score is not None:
        risk_level = "低" if risk_score < 0.3 else "中" if risk_score < 0.7 else "高"
        lines.append(f"**风险评分**: {risk_score:.2f} ({risk_level}风险)\n\n")
    
    # 研究依据（核心内容）
    reasoning = json_obj.get("reasoning", "")
    logger.info(f"🔄 [研究结论转换] reasoning 长度: {len(reasoning) if reasoning else 0}")
    if reasoning:
        lines.append(f"## 📊 研究依据\n\n{reasoning}\n\n")
    
    # 投资计划摘要
    summary = json_obj.get("summary", "")
    logger.info(f"🔄 [研究结论转换] summary 长度: {len(summary) if summary else 0}")
    if summary:
        lines.append(f"## 📋 研究摘要\n\n{summary}\n\n")
    
    # 风险提示
    risk_warning = json_obj.get("risk_warning", "")
    logger.info(f"🔄 [研究结论转换] risk_warning 长度: {len(risk_warning) if risk_warning else 0}")
    if risk_warning:
        lines.append(f"## ⚠️ 风险提示\n\n{risk_warning}\n\n")

    for title, field_name in (
        ("## 🔍 核心依据", "core_evidence"),
        ("## ❓ 关键不确定性", "uncertainties"),
        ("## 🔄 判断调整条件", "invalidation_conditions"),
        ("## 👀 后续观察事项", "watch_items"),
    ):
        items = [item for item in json_obj.get(field_name, []) if item] if isinstance(json_obj.get(field_name, []), list) else []
        if items:
            lines.append(f"{title}\n\n")
            for idx, item in enumerate(items, 1):
                lines.append(f"{idx}. {item}\n")
            lines.append("\n")
    
    result = "\n".join(lines).strip()
    logger.info(f"✅ [研究结论转换] 转换完成，Markdown 行数: {len(lines)}, 总长度: {len(result)}")
    return result


def _convert_risk_json_to_markdown(json_obj: Dict[str, Any]) -> str:
    """将风险评估 JSON 转换为 Markdown"""
    logger.info(f"🔄 [风险评估转换] JSON 字段: {list(json_obj.keys())}")
    lines = []

    # 风险等级
    risk_level = json_obj.get("risk_level", "")
    logger.info(f"🔄 [风险评估转换] risk_level: {risk_level}")
    if risk_level:
        level_map = {"低": "🟢", "中": "🟡", "高": "🔴"}
        level_icon = level_map.get(risk_level, "⚪")
        lines.append(f"## ⚠️ 风险等级\n\n{level_icon} **{risk_level}风险**\n\n")

    # 风险评分
    risk_score = json_obj.get("risk_score")
    logger.info(f"🔄 [风险评估转换] risk_score: {risk_score}")
    if risk_score is not None:
        lines.append(f"**风险评分**: {risk_score:.2f}\n\n")

    # 风险评估理由（核心内容）
    reasoning = json_obj.get("reasoning", "")
    logger.info(f"🔄 [风险评估转换] reasoning 长度: {len(reasoning) if reasoning else 0}")
    if reasoning:
        lines.append(f"## 📊 风险评估理由\n\n{reasoning}\n\n")

    # 主要风险点
    key_risks = json_obj.get("key_risks", [])
    logger.info(f"🔄 [风险评估转换] key_risks 数量: {len(key_risks) if isinstance(key_risks, list) else 0}")
    if isinstance(key_risks, list) and key_risks:
        lines.append("## 🔍 主要风险点\n\n")
        for idx, risk in enumerate(key_risks, 1):
            if risk:
                lines.append(f"{idx}. {risk}\n")
        lines.append("\n")

    # 研究使用边界
    risk_control = json_obj.get("risk_control", "")
    logger.info(f"🔄 [风险评估转换] risk_control 长度: {len(risk_control) if risk_control else 0}")
    if risk_control:
        lines.append(f"## 🛡️ 研究使用边界\n\n{risk_control}\n\n")

    # 研究跟踪建议调整
    investment_adjustment = json_obj.get("investment_adjustment", "")
    logger.info(f"🔄 [风险评估转换] investment_adjustment 长度: {len(investment_adjustment) if investment_adjustment else 0}")
    if investment_adjustment:
        lines.append(f"## 📈 研究跟踪建议\n\n{investment_adjustment}\n\n")

    result = "\n".join(lines).strip()
    logger.info(f"✅ [风险评估转换] 转换完成，Markdown 行数: {len(lines)}, 总长度: {len(result)}")
    return result


def _convert_final_decision_json_to_markdown(json_obj: Dict[str, Any]) -> str:
    """
    将包含 final_trade_decision 的 JSON 转换为 Markdown

    这个函数处理 RiskManager 输出的完整 JSON，包括：
    - 风险评估部分（risk_level, risk_score, reasoning, key_risks, risk_control, investment_adjustment）
    - 最终研究结论部分（final_trade_decision 嵌套对象）
    """
    logger.info(f"🔄 [最终研究结论转换] JSON 字段: {list(json_obj.keys())}")
    lines = []

    # 🔥 关键：提取 final_trade_decision 嵌套对象
    final_trade_decision = json_obj.get("final_trade_decision", {})
    logger.info(f"🔄 [最终研究结论转换] final_trade_decision 类型: {type(final_trade_decision)}")

    if isinstance(final_trade_decision, dict) and final_trade_decision:
        logger.info(f"🔄 [最终研究结论转换] final_trade_decision 字段: {list(final_trade_decision.keys())}")

        # 决策摘要
        lines.append("# 🎯 综合研究结论\n\n")
        lines.append("## 当前判断\n\n")

        # 研究判断
        action = final_trade_decision.get("analysis_view") or final_trade_decision.get("action", "")
        logger.info(f"🔄 [最终研究结论转换] action: {action}")
        if action:
            action_map = {
                # 新合规术语（乐观/审慎/中性）优先
                "乐观": "🟢 乐观",
                "审慎": "🟡 审慎",
                "中性": "⚪ 中性",
                # 旧市场观点术语 + 旧交易指令（兼容存量数据，映射为新合规表述）
                "买入": "🟢 乐观",
                "持有": "⚪ 中性",
                "卖出": "🟡 审慎",
                "看涨": "🟢 乐观",
                "看跌": "🟡 审慎",
            }
            action_display = action_map.get(action, action)
            lines.append(f"- **研究观点**: {action_display}\n")

        # 信心度
        confidence = final_trade_decision.get("confidence")
        logger.info(f"🔄 [最终研究结论转换] confidence: {confidence}")
        if confidence is not None:
            # 🔥 修复：处理 0-1 小数和 0-100 整数两种情况
            try:
                conf_value = float(confidence)
                # 如果是 0-1 的小数，转换为百分比
                if conf_value <= 1:
                    conf_display = int(conf_value * 100)
                else:
                    conf_display = int(conf_value)
                lines.append(f"- **信心度**: {conf_display}%\n")
            except (ValueError, TypeError):
                lines.append(f"- **信心度**: {confidence}%\n")

        lines.append("\n")

        # 研究依据（核心内容）
        reasoning = final_trade_decision.get("reasoning", "")
        logger.info(f"🔄 [最终研究结论转换] reasoning 长度: {len(reasoning) if reasoning else 0}")
        if reasoning:
            lines.append(f"## 📊 研究依据\n\n{reasoning}\n\n")

        # 一句话总结
        summary = final_trade_decision.get("summary", "")
        logger.info(f"🔄 [最终研究结论转换] summary 长度: {len(summary) if summary else 0}")
        if summary:
            lines.append(f"## 💡 研究摘要\n\n{summary}\n\n")

        # 风险提示
        risk_warning = final_trade_decision.get("risk_warning", "")
        logger.info(f"🔄 [最终研究结论转换] risk_warning 长度: {len(risk_warning) if risk_warning else 0}")
        if risk_warning:
            lines.append(f"## ⚠️ 风险提示\n\n{risk_warning}\n\n")

        for title, field_name in (
            ("## 🔍 核心依据", "core_evidence"),
            ("## ❓ 关键不确定性", "uncertainties"),
            ("## 🔄 判断调整条件", "invalidation_conditions"),
            ("## 👀 后续观察事项", "watch_items"),
        ):
            items = [item for item in final_trade_decision.get(field_name, []) if item] if isinstance(final_trade_decision.get(field_name, []), list) else []
            if items:
                lines.append(f"{title}\n\n")
                for idx, item in enumerate(items, 1):
                    lines.append(f"{idx}. {item}\n")
                lines.append("\n")
    else:
        logger.warning(f"⚠️ [最终研究结论转换] final_trade_decision 不存在或为空，回退到风险评估格式")
        # 如果没有 final_trade_decision，回退到风险评估格式
        return _convert_risk_json_to_markdown(json_obj)

    result = "\n".join(lines).strip()
    logger.info(f"✅ [最终研究结论转换] 转换完成，Markdown 行数: {len(lines)}, 总长度: {len(result)}")
    return result


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
        # 🔥 清理AI生成的署名信息
        cleaned_content = _clean_report_for_display('bull_researcher', bull_content.strip())
        reports['bull_researcher'] = cleaned_content
        logger.info(f"📊 [ReportFormatter] 提取: bull_researcher - 长度: {len(cleaned_content)} (已清理署名)")

    # 空头研究员
    bear_content = _get_field_value(debate_state, 'bear_history')
    logger.info(f"🔍 [ReportFormatter] bear_history 类型: {type(bear_content)}, 值: {str(bear_content)[:100] if bear_content else None}")
    if bear_content and isinstance(bear_content, str) and len(bear_content.strip()) > 10:
        # 🔥 清理AI生成的署名信息
        cleaned_content = _clean_report_for_display('bear_researcher', bear_content.strip())
        reports['bear_researcher'] = cleaned_content
        logger.info(f"📊 [ReportFormatter] 提取: bear_researcher - 长度: {len(cleaned_content)} (已清理署名)")

    # 研究经理分析
    decision_content = _get_field_value(debate_state, 'judge_decision')
    logger.info(f"🔍 [ReportFormatter] judge_decision 类型: {type(decision_content)}, 值: {str(decision_content)[:100] if decision_content else None}")

    # ✅ 修复：只在 judge_decision 有实际内容时才使用
    # 不要在空字符串时使用 str(debate_state) 作为备选
    if decision_content and isinstance(decision_content, str) and len(decision_content.strip()) > 10:
        # 🔥 新增：如果是 JSON 格式，转换为 Markdown
        markdown_content = _clean_report_for_display(
            'research_team_decision',
            _convert_json_to_markdown(decision_content.strip(), "investment"),
        )
        reports['research_team_decision'] = markdown_content
        logger.info(f"📊 [ReportFormatter] 提取: research_team_decision - 长度: {len(markdown_content)}")
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
        # 🔥 清理AI生成的署名信息
        cleaned_content = _clean_report_for_display('risky_analyst', risky_content.strip())
        reports['risky_analyst'] = cleaned_content
        logger.info(f"📊 [ReportFormatter] 提取: risky_analyst - 长度: {len(cleaned_content)} (已清理署名)")

    # 保守分析师
    safe_content = _get_field_value(risk_state, 'safe_history')
    logger.info(f"🔍 [ReportFormatter] safe_history: {str(safe_content)[:100] if safe_content else None}")
    if safe_content and isinstance(safe_content, str) and len(safe_content.strip()) > 10:
        # 🔥 清理AI生成的署名信息
        cleaned_content = _clean_report_for_display('safe_analyst', safe_content.strip())
        reports['safe_analyst'] = cleaned_content
        logger.info(f"📊 [ReportFormatter] 提取: safe_analyst - 长度: {len(cleaned_content)} (已清理署名)")

    # 中性分析师
    neutral_content = _get_field_value(risk_state, 'neutral_history')
    logger.info(f"🔍 [ReportFormatter] neutral_history: {str(neutral_content)[:100] if neutral_content else None}")
    if neutral_content and isinstance(neutral_content, str) and len(neutral_content.strip()) > 10:
        # 🔥 清理AI生成的署名信息
        cleaned_content = _clean_report_for_display('neutral_analyst', neutral_content.strip())
        reports['neutral_analyst'] = cleaned_content
        logger.info(f"📊 [ReportFormatter] 提取: neutral_analyst - 长度: {len(cleaned_content)} (已清理署名)")

    # 风险管理决策
    risk_decision = _get_field_value(risk_state, 'judge_decision')
    logger.info(f"🔍 [ReportFormatter] risk judge_decision 类型: {type(risk_decision)}, 值: {str(risk_decision)[:100] if risk_decision else None}")

    # ✅ 修复：只在 judge_decision 有实际内容时才使用
    # 不要在空字符串时使用 str(risk_state) 作为备选
    if risk_decision and isinstance(risk_decision, str) and len(risk_decision.strip()) > 10:
        # 🔥 新增：如果是 JSON 格式，转换为 Markdown
        markdown_content = _clean_report_for_display(
            'risk_management_decision',
            _convert_json_to_markdown(risk_decision.strip(), "risk"),
        )
        reports['risk_management_decision'] = markdown_content
        logger.info(f"📊 [ReportFormatter] 提取: risk_management_decision - 长度: {len(markdown_content)}")
    else:
        logger.warning(f"⚠️ [ReportFormatter] risk_management_decision 为空或过短，跳过")


# 🔥 合规修改：研究结论映射（英文 -> 中文合规术语）
ACTION_TRANSLATION = {
    'BUY': '乐观', 'SELL': '审慎', 'HOLD': '中性',
    'buy': '乐观', 'sell': '审慎', 'hold': '中性',
    '买入': '乐观', '卖出': '审慎', '持有': '中性',  # 兼容旧数据
    '看涨': '乐观', '看跌': '审慎', '中性': '中性',  # 兼容旧数据
}


def format_decision(
    decision_raw: Dict[str, Any],
    fallback_text: str = "",
    quick_model: str = None,
    stock_code: str = None
) -> Dict[str, Any]:
    """
    格式化决策为标准格式

    🔥 核心修复：如果 decision_raw 缺少关键字段（reasoning），
    使用 SignalProcessor 从 fallback_text 中提取结构化信息。

    Args:
        decision_raw: 原始决策字典
        fallback_text: 备用文本（通常是 final_trade_decision 或 risk_management_decision）
        quick_model: 用户选择的快速分析模型名称
        stock_code: 股票代码（用于 SignalProcessor 判断货币类型）

    Returns:
        格式化后的决策字典，包含 action, confidence, risk_score, reasoning
    """
    import re

    if not decision_raw:
        decision_raw = {}

    # 🔥 如果 decision_raw 缺少关键字段且有 fallback_text，使用 SignalProcessor 处理
    needs_signal_processing = (
        fallback_text and
        len(fallback_text) > 50 and
        (not decision_raw.get('reasoning') and not decision_raw.get('rationale'))
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
            logger.info(f"📊 [ReportFormatter] 使用 SignalProcessor 处理文本，结果: action={processed.get('action')}")

            # 合并处理结果（优先使用 decision_raw 中的值，如果有的话）
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
    action = decision_raw.get('action', '中性')
    chinese_action = ACTION_TRANSLATION.get(action, action) if action else '中性'

    # 获取 reasoning - 清理 Markdown 格式
    # 🔥 兼容新旧版本：reasoning 或 rationale
    # 🔥 重要：reasoning 应该从 decision_raw 中提取，如果 decision_raw 没有 reasoning，使用默认值
    # 不应该从 fallback_text（通常是 final_trade_decision）中提取，因为 final_trade_decision 会被用于生成 summary
    # 这与旧引擎的处理方式保持一致：旧引擎中，如果 decision 没有 reasoning，使用默认值 '暂无分析推理'
    logger.info(f"🔍 [format_decision] ========== 提取 reasoning ==========")
    logger.info(f"🔍 [format_decision] decision_raw 类型: {type(decision_raw)}")
    if isinstance(decision_raw, dict):
        logger.info(f"🔍 [format_decision] decision_raw 字段: {list(decision_raw.keys())}")
        logger.info(f"🔍 [format_decision] decision_raw.get('reasoning'): {decision_raw.get('reasoning', 'None')}")
        logger.info(f"🔍 [format_decision] decision_raw.get('rationale'): {decision_raw.get('rationale', 'None')}")
    
    reasoning = decision_raw.get('reasoning', '') or decision_raw.get('rationale', '')
    logger.info(f"🔍 [format_decision] 初始 reasoning 值: {reasoning[:200] if reasoning else 'None'}")
    
    if reasoning:
        # 清理已有的 reasoning 中的 Markdown 格式
        reasoning = _clean_markdown(reasoning)
        logger.info(f"🔍 [format_decision] ✅ 从 decision_raw 提取到 reasoning，清理后长度: {len(reasoning)}")
        logger.info(f"🔍 [format_decision] reasoning 清理后内容: {reasoning[:300]}")
    else:
        # 🔥 如果 decision_raw 中没有 reasoning，使用默认值（与旧引擎保持一致）
        # 注意：不应该从 fallback_text 中提取，避免与 summary 重复
        reasoning = '暂无分析推理'
        logger.info(f"🔍 [format_decision] ⚠️ decision_raw 中没有 reasoning，使用默认值: {reasoning}")
        logger.info(f"🔍 [format_decision] fallback_text 长度: {len(fallback_text) if fallback_text else 0}")
        if fallback_text:
            logger.info(f"🔍 [format_decision] fallback_text 前200字符: {fallback_text[:200]}")
            logger.info(f"🔍 [format_decision] ⚠️ 注意：不会从 fallback_text 中提取 reasoning，避免与 summary 重复")

    normalized_lists = normalize_research_brief_lists(
        decision_raw.get('core_evidence'),
        decision_raw.get('uncertainties'),
        decision_raw.get('invalidation_conditions'),
        decision_raw.get('watch_items'),
    )

    return {
        'action': chinese_action,
        'analysis_view': chinese_action,
        'confidence': float(decision_raw.get('confidence', 0.5)),
        'risk_score': float(decision_raw.get('risk_score', 0.3)),
        'reasoning': reasoning or '暂无分析推理',
        'summary': decision_raw.get('summary', '') or '',
        'risk_warning': decision_raw.get('risk_warning', '') or '',
        'core_evidence': normalized_lists['core_evidence'],
        'uncertainties': normalized_lists['uncertainties'],
        'invalidation_conditions': normalized_lists['invalidation_conditions'],
        'watch_items': normalized_lists['watch_items'],
    }


def _remove_author_signature(text: str) -> str:
    """
    移除AI生成的署名信息（撰写人、日期、声明等）
    
    Args:
        text: 原始文本
        
    Returns:
        清理后的文本
    """
    import re
    
    if not text:
        return text
    
    # 移除"撰写人：XXX"格式的署名
    text = re.sub(r'撰写人[：:]\s*[^\n]+\n?', '', text, flags=re.MULTILINE)
    # 移除"日期：XXX"格式的日期署名
    text = re.sub(r'日期[：:]\s*\d{4}年\d{1,2}月\d{1,2}日\s*\n?', '', text, flags=re.MULTILINE)
    # 移除"声明：XXX"格式的声明（通常在署名附近）
    text = re.sub(r'声明[：:]\s*[^\n]+本报告[^\n]+\n?', '', text, flags=re.MULTILINE)
    # 移除包含"撰写人"、"日期"、"声明"的完整署名块（多行）
    text = re.sub(
        r'撰写人[：:][^\n]+\n日期[：:][^\n]+\n声明[：:][^\n]+',
        '',
        text,
        flags=re.MULTILINE | re.DOTALL
    )
    # 移除常见的署名格式（如"撰写人：XXX·YYY"）
    text = re.sub(r'撰写人[：:]\s*[^·\n]+[··][^\n]+\n?', '', text, flags=re.MULTILINE)
    # 移除"分析师·XXX"格式的署名（如"看跌分析师·李岩"）
    text = re.sub(r'[^：:\n]+分析师[··][^\n]+\n?', '', text, flags=re.MULTILINE)
    
    # 移除多余的空行
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()


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

    # 🔥 移除AI生成的署名信息
    text = _remove_author_signature(text)

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

    🔥 重要：summary 和 decision.reasoning 应该有不同的来源和内容
    - summary：从 final_trade_decision 或其他报告中提取分析摘要（前200字符）
    - decision.reasoning：从 final_decision.reasoning 中提取推理过程（简短摘要，前150字符）
    - recommendation：统一收口为研究辅助提示，不生成交易建议

    Args:
        reports: 报告字典
        decision: 格式化后的决策
        stock_code: 股票代码

    Returns:
        (summary, recommendation) 元组
    """
    summary = ""
    recommendation = ""

    logger.info(f"🔍 [generate_summary_recommendation] ========== 生成 summary ==========")
    logger.info(f"🔍 [generate_summary_recommendation] reports 中的字段: {list(reports.keys())}")
    for report_name in reports.keys():
        if isinstance(reports[report_name], str):
            logger.info(f"🔍 [generate_summary_recommendation] reports['{report_name}'] 长度: {len(reports[report_name])}, 前100字符: {reports[report_name][:100]}")

    # 🔥 重要：与旧引擎保持一致，summary（分析摘要）优先从 final_trade_decision 提取
    # 旧引擎的处理方式：优先从 reports 中的 final_trade_decision 提取 summary（前200字符）
    # 1. 优先从 final_trade_decision 提取 summary（与旧引擎保持一致）
    logger.info(f"🔍 [generate_summary_recommendation] 检查 'final_trade_decision' 是否在 reports 中: {'final_trade_decision' in reports}")
    if 'final_trade_decision' in reports:
        content = reports['final_trade_decision']
        logger.info(f"🔍 [generate_summary_recommendation] final_trade_decision 内容长度: {len(content)}")
        logger.info(f"🔍 [generate_summary_recommendation] final_trade_decision 前300字符: {content[:300]}")
        if len(content) > 50:
            # 清理 Markdown 格式，提取前200字符作为摘要（与旧引擎保持一致）
            cleaned_content = _clean_markdown(content)
            summary = cleaned_content[:200].strip()
            if len(cleaned_content) > 200:
                summary += "..."
            logger.info(f"🔍 [generate_summary_recommendation] ✅ 从 final_trade_decision 提取摘要: {len(summary)}字符")
            logger.info(f"🔍 [generate_summary_recommendation] summary 内容: {summary[:300]}")

    # 2. 如果没有 final_trade_decision，从其他报告中提取摘要
    if not summary:
        logger.info(f"🔍 [generate_summary_recommendation] final_trade_decision 不存在或为空，尝试从其他报告提取")
        for report_name in ['investment_plan', 'trader_investment_plan', 'research_team_decision', 'market_report']:
            logger.info(f"🔍 [generate_summary_recommendation] 检查 '{report_name}': {'存在' if report_name in reports else '不存在'}")
            if report_name in reports:
                content = reports[report_name]
                logger.info(f"🔍 [generate_summary_recommendation] {report_name} 内容长度: {len(content)}")
                if len(content) > 100:
                    cleaned_content = _clean_markdown(content)
                    summary = cleaned_content[:200].strip()
                    if len(cleaned_content) > 200:
                        summary += "..."
                    logger.info(f"🔍 [generate_summary_recommendation] ✅ 从 {report_name} 提取摘要: {len(summary)}字符")
                    logger.info(f"🔍 [generate_summary_recommendation] summary 内容: {summary[:300]}")
                    break

    # 3. 最后的备用方案
    if not summary:
        summary = f"对{stock_code}的分析已完成，请查看详细报告。"
        logger.warning(f"⚠️ [Summary] 使用备用摘要")

    # 4. 生成 recommendation（统一研究辅助提示）
    logger.info(f"🔍 [generate_summary_recommendation] ========== 生成 recommendation ==========")
    logger.info(f"🔍 [generate_summary_recommendation] decision 字段: {list(decision.keys())}")
    # 🔥 recommendation 应该基于 decision 的 action、target_price 和简短的推理摘要
    # 注意：这里不使用完整的 reasoning，避免与"研究依据"重复
    action = decision.get('action') or decision.get('analysis_view') or '中性'
    reasoning = decision.get('reasoning', '')
    
    logger.info(f"🔍 [generate_summary_recommendation] decision.action: {action}")
    logger.info(f"🔍 [generate_summary_recommendation] decision.reasoning 长度: {len(reasoning)}, 内容: {reasoning[:200]}")

    recommendation = f"研究观点：{action}。请结合详细报告重点关注证据变化、风险因素与后续披露。"
    if reasoning:
        short_reasoning = reasoning[:60] + "..." if len(reasoning) > 60 else reasoning
        recommendation += f" 核心依据：{short_reasoning}"

    if not recommendation:
        recommendation = "请参考详细研究报告，重点关注基本面变化、市场环境与风险因素。"
        logger.warning(f"⚠️ [Recommendation] 使用备用研究提示")
    
    logger.info(f"🔍 [generate_summary_recommendation] recommendation 最终内容: {recommendation[:300]}")

    logger.info(f"✅ [Summary/Recommendation] summary={len(summary)}字符, recommendation={len(recommendation)}字符")
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
    logger.info(f"🔍 [ReportFormatter] ========== 开始格式化分析结果 ==========")
    logger.info(f"🔍 [ReportFormatter] stock_code={stock_code}, stock_name={stock_name}")
    
    reports = extract_reports_from_state(raw_result)
    logger.info(f"🔍 [ReportFormatter] 提取到 {len(reports)} 个报告: {list(reports.keys())}")
    for report_name, report_content in reports.items():
        if isinstance(report_content, str):
            logger.info(f"🔍 [ReportFormatter] reports['{report_name}'] 长度: {len(report_content)}, 前100字符: {report_content[:100]}")

    # 2. 解析并格式化决策
    # 🔥 v2.0 引擎的特殊处理：
    # - final_decision: 可能不存在或为空
    # - action_advice: ActionAdvisorV2 的输出，包含研究观察和 reasoning
    # - final_trade_decision: RiskManagerV2 的输出，包含完整的风险评估报告（不应该用于 reasoning）
    final_decision = raw_result.get("final_decision", {})
    action_advice = raw_result.get("action_advice", "")
    final_trade_decision = raw_result.get("final_trade_decision", "")

    # 🔥 详细日志：检查各个字段的内容
    logger.info(f"🔍 [ReportFormatter] ========== 检查原始数据字段 ==========")
    logger.info(f"🔍 [ReportFormatter] final_decision 类型: {type(final_decision)}")
    if isinstance(final_decision, dict):
        logger.info(f"🔍 [ReportFormatter] final_decision 字段: {list(final_decision.keys())}")
        logger.info(f"🔍 [ReportFormatter] final_decision.target_price: {final_decision.get('target_price')}")
        logger.info(f"🔍 [ReportFormatter] final_decision.reasoning: {str(final_decision.get('reasoning', ''))[:200] if final_decision.get('reasoning') else 'None'}")
    else:
        logger.info(f"🔍 [ReportFormatter] final_decision 值: {str(final_decision)[:200]}")
    
    # 🔥 检查 action_advice（v2.0 引擎的研究观察）
    logger.info(f"🔍 [ReportFormatter] action_advice 类型: {type(action_advice)}")
    if action_advice:
        if isinstance(action_advice, dict):
            action_advice_content = action_advice.get("content", str(action_advice))
            logger.info(f"🔍 [ReportFormatter] action_advice 是字典，字段: {list(action_advice.keys())}")
        else:
            action_advice_content = str(action_advice)
        logger.info(f"🔍 [ReportFormatter] action_advice 存在，长度: {len(action_advice_content)}")
        logger.info(f"🔍 [ReportFormatter] action_advice 前300字符: {action_advice_content[:300]}")
    else:
        logger.info(f"🔍 [ReportFormatter] action_advice 不存在或为空")
    
    logger.info(f"🔍 [ReportFormatter] final_trade_decision 类型: {type(final_trade_decision)}")
    logger.info(f"🔍 [ReportFormatter] final_trade_decision 长度: {len(final_trade_decision) if final_trade_decision else 0}")
    if final_trade_decision:
        final_trade_decision_str = str(final_trade_decision)
        logger.info(f"🔍 [ReportFormatter] final_trade_decision 前300字符: {final_trade_decision_str[:300]}")
        logger.info(f"🔍 [ReportFormatter] final_trade_decision 是否在 reports 中: {'final_trade_decision' in reports}")
        if 'final_trade_decision' in reports:
            logger.info(f"🔍 [ReportFormatter] reports['final_trade_decision'] 长度: {len(reports['final_trade_decision'])}, 前300字符: {reports['final_trade_decision'][:300]}")

    # 🔥 v2.0 引擎的特殊处理：优先从 action_advice 中提取 reasoning
    # 如果 final_decision 没有 reasoning，且 action_advice 存在，尝试从 action_advice 中提取
    if isinstance(final_decision, dict) and not final_decision.get('reasoning'):
        if action_advice:
            # 尝试从 action_advice 中提取 reasoning
            if isinstance(action_advice, dict):
                action_advice_content = action_advice.get("content", str(action_advice))
            else:
                action_advice_content = str(action_advice)
            
            # 尝试解析 JSON 格式的 action_advice
            import json
            try:
                if isinstance(action_advice_content, str) and ("{" in action_advice_content or "```json" in action_advice_content):
                    # 提取 JSON 部分
                    json_str = action_advice_content
                    if "```json" in json_str:
                        json_start = json_str.find("```json") + 7
                        json_end = json_str.find("```", json_start)
                        if json_end > json_start:
                            json_str = json_str[json_start:json_end].strip()
                    
                    if json_str.strip().startswith("{"):
                        action_advice_json = json.loads(json_str)
                        # 从 JSON 中提取 reasoning
                        if isinstance(action_advice_json, dict):
                            reasoning_from_advice = action_advice_json.get("reasoning") or action_advice_json.get("detailed_analysis", "")
                            if reasoning_from_advice:
                                final_decision['reasoning'] = reasoning_from_advice
                                logger.info(f"✅ [ReportFormatter] 从 action_advice 提取 reasoning: {len(reasoning_from_advice)}字符")
            except Exception as e:
                logger.warning(f"⚠️ [ReportFormatter] 解析 action_advice JSON 失败: {e}")

    # 🔥 传入 quick_model 和 stock_code，使用用户选择的模型
    # 🔥 重要：对于 v2.0 引擎，如果 final_decision 没有 reasoning，尝试从 action_advice 中提取
    # 如果 action_advice 也没有，format_decision 会使用默认值 '暂无分析推理'（与旧引擎保持一致）
    # 不应该使用 final_trade_decision 作为 reasoning 的 fallback，因为 final_trade_decision 会被用于生成 summary
    fallback_for_reasoning = ""
    if action_advice:
        # 优先使用 action_advice 作为 reasoning 的 fallback（尝试从 action_advice 中提取 reasoning）
        if isinstance(action_advice, dict):
            fallback_for_reasoning = action_advice.get("content", str(action_advice))
        else:
            fallback_for_reasoning = str(action_advice)
    
    formatted_decision = format_decision(
        final_decision,
        fallback_for_reasoning,  # 使用 action_advice（如果存在），否则 format_decision 会使用默认值
        quick_model=quick_model,
        stock_code=stock_code
    )
    logger.info(f"🔍 [ReportFormatter] formatted_decision: action={formatted_decision.get('action')}, target_price={formatted_decision.get('target_price')}, reasoning长度={len(formatted_decision.get('reasoning', ''))}")

    # 3. 生成 summary 和 recommendation
    # 🔥 重要：summary 应该从 investment_plan 或其他综合报告中提取，而不是从 final_trade_decision 提取
    # final_trade_decision 是风险评估报告，不应该作为 summary
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

        # decision 字段 - 前端显示研究倾向、研究依据等
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

    # 🔥 最终结果日志
    logger.info(f"🔍 [ReportFormatter] ========== 最终格式化结果 ==========")
    logger.info(f"🔍 [ReportFormatter] result.decision.reasoning 长度: {len(formatted_decision.get('reasoning', ''))}, 内容: {formatted_decision.get('reasoning', '')[:300]}")
    logger.info(f"🔍 [ReportFormatter] result.summary 长度: {len(summary)}, 内容: {summary[:300]}")
    logger.info(f"🔍 [ReportFormatter] result.recommendation 长度: {len(recommendation)}, 内容: {recommendation[:300]}")
    logger.info(f"🔍 [ReportFormatter] ========== 格式化完成 ==========")
    logger.info(f"✅ [ReportFormatter] 格式化完成: decision.action={formatted_decision.get('action')}, reports={len(reports)}个")
    return result
