"""
回测结果评估器
分析回测结果是否符合用户预期，识别问题并提出优化建议
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

from core.llm import UnifiedLLMClient
from core.llm.models import Message, MessageRole

logger = logging.getLogger(__name__)

EVALUATE_SYSTEM = """你是一个专业的量化策略评估师。你的任务是分析回测结果，判断策略是否符合用户的原始需求，识别问题并提出优化建议。

【评估维度】
1. **需求匹配度**：策略逻辑是否符合用户描述的投资思路
2. **结果合理性**：收益、胜率、回撤等指标是否在合理范围内
3. **交易行为**：买卖时机、持仓分布是否符合预期
4. **数据质量**：是否存在数据缺失、异常值等问题
5. **代码逻辑**：策略实现是否有明显缺陷

【输出格式】
请按以下JSON格式输出评估结果：
{
  "overall_score": 85,  // 总体评分 0-100
  "is_satisfactory": true,  // 是否满意（>= 70分为满意）
  "issues": [
    {
      "type": "logic_error",  // 问题类型：logic_error/data_issue/performance_poor/requirement_mismatch
      "severity": "high",     // 严重程度：high/medium/low
      "description": "具体问题描述",
      "suggestion": "优化建议"
    }
  ],
  "strengths": ["策略优点1", "策略优点2"],
  "optimization_priority": "high",  // 优化优先级：high/medium/low/none
  "next_steps": "下一步优化方向的具体建议"
}

【评估标准】
- 总体评分：综合考虑需求匹配度、结果合理性、交易行为等
- 满意阈值：>= 70分认为基本满意，< 70分需要优化
- 问题严重程度：
  * high: 严重影响策略有效性，必须修复
  * medium: 影响策略表现，建议修复  
  * low: 轻微问题，可选修复

【常见问题类型】
- logic_error: 策略逻辑错误（如买卖条件错误、持仓管理问题）
- data_issue: 数据问题（如股票池为空、数据缺失）
- performance_poor: 表现不佳（如收益过低、回撤过大）
- requirement_mismatch: 与用户需求不符（如预期高分红但选了成长股）
"""

OPTIMIZE_SYSTEM = """你是一个策略优化专家。根据回测结果评估报告，对现有策略进行针对性优化。

【优化原则】
1. **针对性修复**：重点解决评估报告中识别的高优先级问题
2. **保持核心逻辑**：在用户原始需求框架内优化，不改变基本投资思路
3. **渐进式改进**：每次只解决1-2个主要问题，避免大幅修改
4. **数据驱动**：基于回测数据和交易明细进行优化

【重要：避免生存者偏差】
⚠️ 不要用现在的龙头股回测过去10-20年！这会导致严重的生存者偏差。

**正确做法（优先级从高到低）**：

1. **🆕 使用行业分类 + 历史市值**：universe.type = "industry"
   - 系统会自动获取回测开始日期时该行业市值最大的股票
   - 例如回测2010-2020年白酒策略，会用2010年时的白酒龙头
   - 这是最佳选择，能真正避免生存者偏差

2. **使用行业指数**：universe.type = "index"
   - 使用指数历史成分股（部分指数历史数据有限）

3. **缩短回测周期**：静态股票池仅用于近3-5年回测

【行业分类配置】⭐ 推荐
支持的行业：白酒、食品、家电、消费、银行、保险、券商、金融、半导体、软件、科技、光伏、锂电、新能源、医药等

示例：
"universe": {"type": "industry", "industry": "白酒", "max_symbols": 10}
"universe": {"type": "industry", "industry": "消费", "max_symbols": 15}
"universe": {"type": "industry", "industry": "金融", "max_symbols": 12}

【行业指数代码参考】（备选）
- 消费类：000932.SH（中证消费）、399997.SZ（中证白酒）
- 金融类：399986.SZ（中证银行）、000914.SH（300金融）
- 科技类：000993.SH（全指信息）、399006.SZ（创业板指）

【静态股票池配置】（仅建议回测近3-5年，不推荐长期回测）
消费类：600519、000858、000568、603288、000651、000333、600887

【输出格式】
必须输出纯JSON，格式如下：
{
  "code": "优化后的完整Python代码字符串",
  "config": {
    "start_year": 2016,
    "end_year": 2025,
    "initial_capital": 1000000,
    "max_positions": 10,
    "benchmark": "000300",
    "market": "CN",
    "data_source": "tushare",
    "universe": {"type": "static", "symbols": ["600519", "000858", "000568", "002304", "000596", "603288", "000651", "000333", "600887", "601888"]}
  },
  "optimization_summary": "本次优化的主要改进点说明"
}

【优化策略】
- 逻辑错误：修正买卖条件、持仓管理逻辑
- 数据问题：调整股票池（增加股票数量、选择更合适的标的）
- 性能问题：优化参数、调整仓位管理
- 需求不符：重新理解用户意图，调整策略方向
- 交易次数不足：扩大股票池、放宽入场条件、缩短持仓周期

【技术要求】
- code中只import backtrader（as bt）
- datetime、date、timedelta已注入，可直接使用
- 必须输出纯JSON，不要markdown代码块包裹
- config必须包含完整的配置参数
- 股票池symbols建议包含8-15只股票，确保有足够的交易机会
"""


async def evaluate_backtest_result(
    user_description: str,
    strategy: Dict[str, Any],
    backtest_result: Dict[str, Any],
    llm_client: Optional[UnifiedLLMClient] = None,
) -> Dict[str, Any]:
    """
    评估回测结果是否符合用户预期
    
    Args:
        user_description: 用户原始需求描述
        strategy: 策略定义（code + config）
        backtest_result: 回测结果（summary + trades等）
        llm_client: LLM客户端
        
    Returns:
        评估结果JSON
    """
    client = llm_client
    if not client:
        from app.services.intelligent_assistant_service import get_coding_llm_config
        
        cfg = await get_coding_llm_config()
        if not cfg:
            raise ValueError("未配置 LLM，无法进行结果评估")
        client = UnifiedLLMClient.from_config(cfg)
    
    # 构建评估上下文
    context = _build_evaluation_context(user_description, strategy, backtest_result)
    
    messages = [
        Message(role=MessageRole.SYSTEM, content=EVALUATE_SYSTEM),
        Message(role=MessageRole.USER, content=context),
    ]
    
    try:
        response = await client.achat(messages)
        result_text = (response.content or "").strip()
        
        # 解析JSON结果
        import json
        evaluation = json.loads(result_text)
        
        # 验证必要字段
        required_fields = ["overall_score", "is_satisfactory", "issues", "optimization_priority"]
        for field in required_fields:
            if field not in evaluation:
                raise ValueError(f"评估结果缺少必要字段: {field}")
                
        return evaluation
        
    except json.JSONDecodeError as e:
        logger.warning("评估结果JSON解析失败: %s", e)
        # 返回默认评估结果
        return {
            "overall_score": 50,
            "is_satisfactory": False,
            "issues": [{"type": "logic_error", "severity": "high", 
                       "description": "评估过程出错", "suggestion": "请检查策略逻辑"}],
            "optimization_priority": "high",
            "next_steps": "需要人工检查策略实现"
        }
    except Exception as e:
        logger.exception("回测结果评估失败")
        raise ValueError(f"评估失败: {e}")


def _build_evaluation_context(
    user_description: str,
    strategy: Dict[str, Any],
    backtest_result: Dict[str, Any]
) -> str:
    """构建评估上下文"""

    # 调试日志
    logger.info(
        "[_build_evaluation_context] 收到 backtest_result keys=%s",
        list(backtest_result.keys()) if backtest_result else "None"
    )

    # 提取关键信息
    # 支持两种数据结构：1) 直接 summary 2) 嵌套在 result 下
    if "summary" in backtest_result:
        summary = backtest_result.get("summary", {})
    else:
        summary = backtest_result  # 直接就是 summary

    logger.info(
        "[_build_evaluation_context] summary: total_return=%s, win_rate=%s, trade_count=%s, final_value=%s",
        summary.get("total_return"),
        summary.get("win_rate"),
        summary.get("trade_count"),
        summary.get("final_value"),
    )

    # 提取运行日志和警告
    logs = backtest_result.get("logs", [])
    warnings = backtest_result.get("warnings", [])
    trades = backtest_result.get("trades", [])
    
    # 格式化回测结果摘要
    result_summary = f"""
【回测结果摘要】
- 总收益: {summary.get('total_return', 0):.1f}%
- 胜率: {summary.get('win_rate', 0):.1f}%
- 最大回撤: {summary.get('max_drawdown_pct', 0):.1f}%
- 交易次数: {summary.get('trade_count', 0)}
- 最终价值: {summary.get('final_value', 0):,.0f}
"""
    
    # 交易明细摘要（取前5笔）
    trade_summary = ""
    if trades:
        trade_summary = "\n【交易明细样本】\n"
        for i, trade in enumerate(trades[:5]):
            trade_summary += f"- 交易{i+1}: {trade.get('symbol', 'N/A')} "
            trade_summary += f"{trade.get('entry_date', 'N/A')} -> {trade.get('exit_date', 'N/A')} "
            trade_summary += f"收益: {trade.get('return_pct', 0):.1f}%\n"

    # 运行日志和警告信息（重要！帮助识别问题根源）
    logs_section = ""
    if logs:
        logs_section = "\n【回测运行日志】\n"
        for log in logs:
            logs_section += f"- {log}\n"

    warnings_section = ""
    if warnings:
        warnings_section = "\n【⚠️ 系统警告（重点关注）】\n"
        for warn in warnings:
            warnings_section += f"- {warn}\n"

    # 策略代码摘要（截取关键部分）
    code = strategy.get("code", "")
    code_summary = code[:500] + "..." if len(code) > 500 else code

    context = f"""
【用户原始需求】
{user_description}

【策略实现】
```python
{code_summary}
```

【策略配置】
{strategy.get('config', {})}

{result_summary}
{trade_summary}
{logs_section}
{warnings_section}

请根据以上信息，评估策略是否符合用户需求，识别存在的问题，并给出优化建议。
特别注意【系统警告】部分，这些是回测引擎自动检测到的潜在问题。
"""
    
    return context


async def optimize_strategy_based_on_evaluation(
    user_description: str,
    current_strategy: Dict[str, Any],
    evaluation_result: Dict[str, Any],
    backtest_result: Dict[str, Any],
    llm_client: Optional[UnifiedLLMClient] = None,
) -> Dict[str, Any]:
    """
    基于评估结果优化策略

    Args:
        user_description: 用户原始需求
        current_strategy: 当前策略（code + config）
        evaluation_result: 评估结果
        backtest_result: 回测结果
        llm_client: LLM客户端

    Returns:
        优化后的策略（code + config + optimization_summary）
    """
    client = llm_client
    if not client:
        from app.services.intelligent_assistant_service import get_coding_llm_config

        cfg = await get_coding_llm_config()
        if not cfg:
            raise ValueError("未配置 LLM，无法进行策略优化")
        client = UnifiedLLMClient.from_config(cfg)

    # 构建优化上下文
    context = _build_optimization_context(
        user_description, current_strategy, evaluation_result, backtest_result
    )

    messages = [
        Message(role=MessageRole.SYSTEM, content=OPTIMIZE_SYSTEM),
        Message(role=MessageRole.USER, content=context),
    ]

    try:
        response = await client.achat(messages)
        result_text = (response.content or "").strip()

        # 解析JSON结果
        import json
        optimized = json.loads(result_text)

        # 验证必要字段
        required_fields = ["code", "config"]
        for field in required_fields:
            if field not in optimized:
                raise ValueError(f"优化结果缺少必要字段: {field}")

        return optimized

    except json.JSONDecodeError as e:
        logger.warning("优化结果JSON解析失败: %s", e)
        raise ValueError(f"优化结果格式错误: {e}")
    except Exception as e:
        logger.exception("策略优化失败")
        raise ValueError(f"优化失败: {e}")


def _build_optimization_context(
    user_description: str,
    current_strategy: Dict[str, Any],
    evaluation_result: Dict[str, Any],
    backtest_result: Dict[str, Any]
) -> str:
    """构建优化上下文"""

    # 提取评估结果中的问题
    issues = evaluation_result.get("issues", [])
    high_priority_issues = [issue for issue in issues if issue.get("severity") == "high"]

    issues_summary = ""
    if high_priority_issues:
        issues_summary = "\n【需要优先解决的问题】\n"
        for i, issue in enumerate(high_priority_issues):
            issues_summary += f"{i+1}. {issue.get('description', '')}\n"
            issues_summary += f"   建议: {issue.get('suggestion', '')}\n"

    # 回测结果关键指标
    summary = backtest_result.get("summary", {}) if "summary" in backtest_result else backtest_result
    performance_summary = f"""
【当前表现】
- 总收益: {summary.get('total_return', 0):.1f}%
- 胜率: {summary.get('win_rate', 0):.1f}%
- 最大回撤: {summary.get('max_drawdown_pct', 0):.1f}%
- 交易次数: {summary.get('trade_count', 0)}
"""

    # 提取系统警告（重要的问题诊断信息）
    warnings = backtest_result.get("warnings", [])
    warnings_section = ""
    if warnings:
        warnings_section = "\n【⚠️ 回测引擎警告（重点关注）】\n"
        for warn in warnings:
            warnings_section += f"- {warn}\n"

    context = f"""
【用户原始需求】
{user_description}

【当前策略代码】
```python
{current_strategy.get('code', '')}
```

【当前策略配置】
{current_strategy.get('config', {})}

{performance_summary}
{warnings_section}

【评估结果】
- 总体评分: {evaluation_result.get('overall_score', 0)}/100
- 是否满意: {'是' if evaluation_result.get('is_satisfactory') else '否'}
- 优化优先级: {evaluation_result.get('optimization_priority', 'medium')}

{issues_summary}

【优化目标】
{evaluation_result.get('next_steps', '改进策略表现')}

请基于以上分析，对策略进行针对性优化，重点解决高优先级问题和系统警告。
"""

    return context


def should_optimize_strategy(evaluation_result: Dict[str, Any]) -> bool:
    """
    判断是否需要优化策略

    Args:
        evaluation_result: 评估结果

    Returns:
        是否需要优化
    """
    # 评分低于70分或有高优先级问题时需要优化
    score = evaluation_result.get("overall_score", 0)
    is_satisfactory = evaluation_result.get("is_satisfactory", False)
    optimization_priority = evaluation_result.get("optimization_priority", "none")

    return (
        score < 70 or
        not is_satisfactory or
        optimization_priority in ["high", "medium"]
    )
