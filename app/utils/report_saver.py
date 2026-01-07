"""
报告保存工具模块

提供统一的报告保存逻辑，供单股分析和工作流执行共用
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


def extract_reports_from_state(state: Any) -> Dict[str, str]:
    """
    从分析状态中提取所有报告
    
    Args:
        state: 分析状态对象（可以是 AgentState 对象或字典）
        
    Returns:
        报告字典，键为报告字段名，值为报告内容
    """
    reports = {}
    
    # 定义所有可能的报告字段
    report_fields = [
        # 🆕 宏观分析报告（优先提取）
        'index_report',
        'sector_report',
        # 个股分析报告
        'market_report',
        'sentiment_report',
        'news_report',
        'fundamentals_report',
        'investment_plan',
        'trader_investment_plan',
        'final_trade_decision'
    ]
    
    # 从state中提取报告内容
    for field in report_fields:
        value = ""
        if hasattr(state, field):
            value = getattr(state, field, "")
        elif isinstance(state, dict) and field in state:
            value = state[field]
        
        if isinstance(value, str) and len(value.strip()) > 10:
            reports[field] = value.strip()
    
    # 处理研究团队辩论状态报告
    debate_state = None
    if hasattr(state, 'investment_debate_state'):
        debate_state = getattr(state, 'investment_debate_state', None)
    elif isinstance(state, dict) and 'investment_debate_state' in state:
        debate_state = state.get('investment_debate_state')
    
    if debate_state:
        # 提取多头研究员历史
        bull_content = _extract_field(debate_state, 'bull_history')
        if bull_content and len(bull_content.strip()) > 10:
            reports['bull_researcher'] = bull_content.strip()
        
        # 提取空头研究员历史
        bear_content = _extract_field(debate_state, 'bear_history')
        if bear_content and len(bear_content.strip()) > 10:
            reports['bear_researcher'] = bear_content.strip()
        
        # 提取研究经理决策
        decision_content = _extract_field(debate_state, 'judge_decision')
        if not decision_content:
            decision_content = str(debate_state) if debate_state else ""
        if decision_content and len(decision_content.strip()) > 10:
            reports['research_team_decision'] = decision_content.strip()
    
    # 处理风险管理团队辩论状态报告
    risk_state = None
    if hasattr(state, 'risk_debate_state'):
        risk_state = getattr(state, 'risk_debate_state', None)
    elif isinstance(state, dict) and 'risk_debate_state' in state:
        risk_state = state.get('risk_debate_state')
    
    if risk_state:
        # 提取激进分析师历史
        risky_content = _extract_field(risk_state, 'risky_history')
        if risky_content and len(risky_content.strip()) > 10:
            reports['risky_analyst'] = risky_content.strip()
        
        # 提取保守分析师历史
        safe_content = _extract_field(risk_state, 'safe_history')
        if safe_content and len(safe_content.strip()) > 10:
            reports['safe_analyst'] = safe_content.strip()
        
        # 提取中性分析师历史
        neutral_content = _extract_field(risk_state, 'neutral_history')
        if neutral_content and len(neutral_content.strip()) > 10:
            reports['neutral_analyst'] = neutral_content.strip()
        
        # 提取投资组合经理决策
        risk_decision = _extract_field(risk_state, 'judge_decision')
        if not risk_decision:
            risk_decision = str(risk_state) if risk_state else ""
        if risk_decision and len(risk_decision.strip()) > 10:
            reports['risk_management_decision'] = risk_decision.strip()
    
    logger.info(f"📊 从state中提取到 {len(reports)} 个报告: {list(reports.keys())}")
    return reports


def _extract_field(obj: Any, field_name: str) -> str:
    """
    从对象中提取字段值
    
    Args:
        obj: 对象（可以是类实例或字典）
        field_name: 字段名
        
    Returns:
        字段值（字符串）
    """
    if hasattr(obj, field_name):
        return getattr(obj, field_name, "")
    elif isinstance(obj, dict) and field_name in obj:
        return obj[field_name]
    return ""


async def save_analysis_report(
    db,
    stock_symbol: str,
    stock_name: str,
    market_type: str,
    model_info: str,
    reports: Dict[str, str],
    decision: Dict[str, Any],
    recommendation: str,
    confidence_score: float,
    risk_level: str,
    summary: str = "",
    key_points: list = None,
    task_id: str = "",
    execution_time: float = 0.0,
    tokens_used: int = 0,
    analysts: list = None,
    research_depth: str = "标准",
    analysis_date: Optional[str] = None,
    source: str = "api",
    engine: str = "v2",
    user_id: Optional[str] = None,
    performance_metrics: Dict[str, Any] = None
) -> str:
    """
    保存分析报告到 analysis_reports 集合（统一方法）
    
    Args:
        db: MongoDB 数据库连接
        stock_symbol: 股票代码
        stock_name: 股票名称
        market_type: 市场类型（A股/港股/美股）
        model_info: 模型信息
        reports: 报告字典
        decision: 决策字典
        recommendation: 投资建议
        confidence_score: 置信度
        risk_level: 风险等级
        ... (其他参数)
        
    Returns:
        analysis_id: 分析报告ID
    """
    # 生成分析ID
    timestamp = datetime.now()
    analysis_id = f"{stock_symbol}_{timestamp.strftime('%Y%m%d_%H%M%S')}"
    
    # 构建文档（与单股分析和工作流执行完全一致）
    document = {
        "analysis_id": analysis_id,
        "stock_symbol": stock_symbol,
        "stock_code": stock_symbol,
        "stock_name": stock_name,
        "market_type": market_type,
        "model_info": model_info,
        "analysis_date": analysis_date or timestamp.strftime('%Y-%m-%d'),
        "timestamp": timestamp,
        "status": "completed",
        "source": source,
        "engine": engine,

        # 分析结果摘要
        "summary": summary or "分析完成",
        "analysts": analysts or [],
        "research_depth": research_depth,

        # 报告内容（16个报告）
        "reports": reports,

        # 🔥 关键字段：decision
        "decision": decision,

        # 元数据
        "created_at": timestamp,
        "updated_at": timestamp,

        # API特有字段
        "task_id": task_id,
        "recommendation": recommendation,
        "confidence_score": confidence_score,
        "risk_level": risk_level,
        "key_points": key_points or [],
        "execution_time": execution_time,
        "tokens_used": tokens_used,

        # 🆕 性能指标数据
        "performance_metrics": performance_metrics or {}
    }

    # 如果有 user_id，添加到文档
    if user_id:
        document["user_id"] = user_id

    # 保存到 MongoDB
    result = await db.analysis_reports.insert_one(document)

    if result.inserted_id:
        logger.info(f"✅ 分析报告已保存到MongoDB: {analysis_id}, 共 {len(reports)} 个报告模块")
    else:
        logger.error("❌ MongoDB插入失败")

    return analysis_id

