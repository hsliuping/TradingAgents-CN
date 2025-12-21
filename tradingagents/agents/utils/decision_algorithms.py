#!/usr/bin/env python3
"""
决策算法模块

提供Strategy Advisor使用的各类决策算法
遵循职责分离原则：只处理决策逻辑，不处理信息采集

Version: v2.1.0 (阶段三)
"""

import json
import re
from typing import Dict, Any, Tuple
from tradingagents.utils.logging_manager import get_logger

logger = get_logger("decision_algorithms")


def extract_json_block(text: str) -> Dict[str, Any]:
    """
    从文本中提取JSON块
    支持纯JSON字符串和Markdown代码块中的JSON
    """
    if not text:
        return {}
        
    # 1. 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
        
    # 2. 尝试提取 ```json ... ``` 代码块
    json_block_pattern = r"```json\s*(\{.*?\})\s*```"
    match = re.search(json_block_pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
            
    # 3. 尝试提取第一个 { ... } 块
    try:
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            json_str = text[start_idx:end_idx+1]
            return json.loads(json_str)
    except (json.JSONDecodeError, ValueError):
        pass
        
    logger.warning("⚠️ 无法从文本中提取有效的JSON数据")
    return {}


# ==================== 指标提取函数 ====================

def extract_macro_sentiment_score(macro_report: str) -> float:
    """
    从宏观报告中提取情绪评分
    
    Args:
        macro_report: 宏观分析师的报告（可能是JSON或混合文本）
        
    Returns:
        情绪评分 (0-1)，默认0.5
    """
    try:
        report = extract_json_block(macro_report)
        score = report.get("sentiment_score", 0.5)
        return max(0.0, min(1.0, score))
    except Exception as e:
        logger.warning(f"⚠️ 提取宏观情绪评分失败: {e}")
        return 0.5


def extract_economic_cycle(macro_report: str) -> str:
    """
    从宏观报告中提取经济周期
    
    Returns:
        经济周期 (衰退期/复苏期/繁荣期/滞胀期)，默认"复苏期"
    """
    try:
        report = extract_json_block(macro_report)
        return report.get("economic_cycle", "复苏期")
    except Exception as e:
        logger.warning(f"⚠️ 提取经济周期失败: {e}")
        return "复苏期"


def extract_policy_support_strength(policy_report: str) -> str:
    """
    从政策报告中提取政策支持强度（v2.1新增字段）
    
    Args:
        policy_report: 政策分析师的报告
        
    Returns:
        政策支持强度 (强/中/弱)，默认"中"
    """
    try:
        report = extract_json_block(policy_report)
        strength = report.get("overall_support_strength", "中")
        
        # 向后兼容：如果是旧版报告没有该字段，降级到中性
        if strength not in ["强", "中", "弱"]:
            # logger.warning(f"⚠️ 政策支持强度值异常: {strength}，降级到'中'")
            return "中"
        
        return strength
    except Exception as e:
        logger.warning(f"⚠️ 提取政策支持强度失败: {e}")
        return "中"


def extract_policy_continuity(policy_report: str) -> float:
    """
    从政策报告中提取政策连续性评分（v2.1新增字段）
    
    Args:
        policy_report: 政策分析师的报告
        
    Returns:
        政策连续性评分 (0-1)，默认0.5
    """
    try:
        report = extract_json_block(policy_report)
        
        # v2.1版本：从long_term_confidence字段提取
        continuity = report.get("long_term_confidence", 0.5)
        
        # 向后兼容：如果没有该字段，使用confidence
        if continuity is None:
            continuity = report.get("confidence", 0.5)
        
        return max(0.0, min(1.0, continuity))
    except Exception as e:
        logger.warning(f"⚠️ 提取政策连续性失败: {e}")
        return 0.5


def extract_news_impact_strength(news_report: str) -> str:
    """
    从国际新闻报告中提取影响强度（v2.1新增）
    
    Args:
        news_report: 国际新闻分析师的报告
        
    Returns:
        影响强度 (高/中/低)，默认"低"
    """
    try:
        report = extract_json_block(news_report)
        strength = report.get("impact_strength", "低")
        
        if strength not in ["高", "中", "低"]:
            # logger.warning(f"⚠️ 新闻影响强度值异常: {strength}，降级到'低'")
            return "低"
        
        return strength
    except Exception as e:
        logger.warning(f"⚠️ 提取新闻影响强度失败: {e}")
        return "低"


def extract_news_credibility(news_report: str) -> float:
    """
    从国际新闻报告中提取可信度
    
    Returns:
        可信度 (0-1)，默认0.5
    """
    try:
        report = extract_json_block(news_report)
        credibility = report.get("confidence", 0.5)
        return max(0.0, min(1.0, credibility))
    except Exception as e:
        logger.warning(f"⚠️ 提取新闻可信度失败: {e}")
        return 0.5


def extract_news_duration(news_report: str) -> str:
    """
    从国际新闻报告中提取影响持续期
    
    Returns:
        影响持续期 (短期/中期/长期)，默认"短期"
    """
    try:
        report = extract_json_block(news_report)
        
        # 尝试从overall_impact或impact_duration提取
        duration = report.get("impact_duration", "")
        if not duration:
            impact = report.get("overall_impact", "")
            if "中期" in impact:
                duration = "中期"
            elif "长期" in impact:
                duration = "长期"
            else:
                duration = "短期"
        
        return duration
    except Exception as e:
        logger.warning(f"⚠️ 提取新闻影响持续期失败: {e}")
        return "短期"


def extract_sector_heat_score(sector_report: str) -> float:
    """
    从板块报告中提取热度评分
    
    Returns:
        热度评分 (0-1)，默认0.5
    """
    try:
        report = extract_json_block(sector_report)
        score = report.get("sentiment_score", 0.5)
        return max(0.0, min(1.0, score))
    except Exception as e:
        logger.warning(f"⚠️ 提取板块热度评分失败: {e}")
        return 0.5


# ==================== 决策算法 ====================

def calculate_base_position(
    policy_strength: str,
    policy_continuity: float,
    macro_score: float
) -> float:
    """
    基础仓位决策算法
    
    设计思路：
    - 长期政策支持是核心驱动力
    - 宏观环境是重要调节因素
    - 政策连续性提供稳定性调整
    
    Args:
        policy_strength: 政策支持强度 (强/中/弱)
        policy_continuity: 政策连续性评分 (0-1)
        macro_score: 宏观情绪评分 (0-1)
        
    Returns:
        基础仓位 (0.4-0.8)
    """
    logger.info(f"📊 基础仓位计算: policy={policy_strength}, continuity={policy_continuity:.2f}, macro={macro_score:.2f}")
    
    # 1. 根据政策强度和宏观环境确定基准仓位
    if policy_strength == "强":
        if macro_score > 0.6:
            base = 0.65
        elif macro_score > 0.4:
            base = 0.60
        else:
            base = 0.55
    elif policy_strength == "中":
        if macro_score > 0.5:
            base = 0.50
        else:
            base = 0.45
    else:  # 弱
        if macro_score > 0.5:
            base = 0.45
        else:
            base = 0.40
    
    # 2. 政策连续性调整（±10%）
    continuity_adj = (policy_continuity - 0.5) * 0.1
    
    # 3. 计算最终基础仓位
    final = base + continuity_adj
    final = max(0.40, min(0.80, final))
    
    logger.info(f"💼 基础仓位: {base:.2%} + {continuity_adj:+.2%} = {final:.2%}")
    return final


def calculate_short_term_adjustment(
    news_impact_strength: str,
    news_credibility: float,
    news_duration: str
) -> float:
    """
    短期调整决策算法
    
    设计思路：
    - 新闻影响强度决定调整幅度
    - 持续期影响调整权重
    - 可信度作为折扣因子
    
    Args:
        news_impact_strength: 新闻影响强度 (高/中/低)
        news_credibility: 新闻可信度 (0-1)
        news_duration: 影响持续期 (短期/中期/长期)
        
    Returns:
        短期调整 (-0.2 到 +0.2)
    """
    logger.info(f"📊 短期调整计算: impact={news_impact_strength}, credibility={news_credibility:.2f}, duration={news_duration}")
    
    # 1. 根据影响强度和持续期确定基础调整值
    if news_impact_strength == "高":
        if "长期" in news_duration:
            base_adj = 0.18
        elif "中期" in news_duration:
            base_adj = 0.15
        else:  # 短期
            base_adj = 0.10
    elif news_impact_strength == "中":
        if "中期" in news_duration or "长期" in news_duration:
            base_adj = 0.08
        else:
            base_adj = 0.05
    else:  # 低
        base_adj = 0.0
    
    # 2. 可信度折扣
    credibility_factor = news_credibility
    
    # 3. 计算最终调整值
    final_adj = base_adj * credibility_factor
    final_adj = max(-0.20, min(0.20, final_adj))
    
    logger.info(f"⚡ 短期调整: {base_adj:.2%} × {credibility_factor:.2f} = {final_adj:+.2%}")
    return final_adj


def generate_position_breakdown(
    base_position: float,
    short_term_adjustment: float,
    final_position: float
) -> Dict[str, float]:
    """
    生成分层持仓策略
    
    设计思路：
    - 核心长期仓位：基于政策支持的稳定配置（67%）
    - 战术配置：短期机会的灵活配置（33% + 短期调整）
    - 现金储备：风险管理和流动性保障
    
    规则:
    - 核心长期仓位 = base_position * 0.67
    - 战术配置 = base_position * 0.33 + short_term_adjustment
    - 现金储备 = 1 - final_position
    
    Args:
        base_position: 基础仓位
        short_term_adjustment: 短期调整
        final_position: 最终仓位
        
    Returns:
        分层持仓字典
    """
    core_holding = base_position * 0.67
    tactical = base_position * 0.33 + short_term_adjustment
    cash_reserve = 1.0 - final_position
    
    # 确保各部分非负且合理
    core_holding = max(0.0, core_holding)
    tactical = max(0.0, tactical)
    cash_reserve = max(0.0, cash_reserve)
    
    result = {
        "core_holding": round(core_holding, 2),
        "tactical_allocation": round(tactical, 2),
        "cash_reserve": round(cash_reserve, 2)
    }
    
    logger.info(f"🎯 分层持仓: 核心{result['core_holding']:.2%} + 战术{result['tactical_allocation']:.2%} + 现金{result['cash_reserve']:.2%}")
    return result


def generate_adjustment_triggers(
    policy_report: str,
    news_report: str
) -> Dict[str, Any]:
    """
    生成动态调整触发条件
    
    设计思路：
    - 基于政策传闻和新闻类型设计不同的触发条件
    - 提供明确的加仓/减仓信号
    
    Args:
        policy_report: 政策分析报告
        news_report: 国际新闻报告
        
    Returns:
        触发条件字典
    """
    try:
        # 解析新闻报告
        news_json = json.loads(news_report) if news_report else {}
        
        # 检查是否有政策传闻
        key_news = news_json.get("key_news", [])
        has_policy_rumor = any(
            news.get("category") == "政策传闻" 
            for news in key_news 
            if isinstance(news, dict)
        )
        
        # 检查整体影响描述
        overall_impact = news_json.get("overall_impact", "")
        if "政策传闻" in overall_impact:
            has_policy_rumor = True
        
        if has_policy_rumor:
            triggers = {
                "increase_to": 0.90,
                "increase_condition": "政策正式官宣",
                "decrease_to": 0.40,
                "decrease_condition": "传闻证伪或外部风险加剧"
            }
            logger.info("🔔 检测到政策传闻，生成传闻类触发条件")
        else:
            triggers = {
                "increase_to": 0.80,
                "increase_condition": "政策进一步加码",
                "decrease_to": 0.50,
                "decrease_condition": "宏观环境恶化"
            }
            logger.info("🔔 生成常规触发条件")
        
        return triggers
    
    except Exception as e:
        logger.warning(f"⚠️ 生成触发条件失败: {e}")
        return {
            "increase_to": 0.80,
            "increase_condition": "政策进一步加码",
            "decrease_to": 0.50,
            "decrease_condition": "宏观环境恶化"
        }


# ==================== 综合决策函数 ====================

def make_strategy_decision(
    macro_report: str,
    policy_report: str,
    international_news_report: str,
    sector_report: str
) -> Tuple[float, float, float, Dict[str, float], Dict[str, Any]]:
    """
    综合决策函数（供Strategy Advisor调用）
    
    整合所有决策算法，输出完整的策略决策
    
    Args:
        macro_report: 宏观分析报告
        policy_report: 政策分析报告
        international_news_report: 国际新闻报告
        sector_report: 板块分析报告
        
    Returns:
        (base_position, short_term_adjustment, final_position, 
         position_breakdown, adjustment_triggers)
    """
    logger.info("=" * 60)
    logger.info("🎯 开始综合决策流程")
    logger.info("=" * 60)
    
    # 1. 提取指标
    logger.info("\n📊 阶段1: 提取分析指标")
    macro_score = extract_macro_sentiment_score(macro_report)
    policy_strength = extract_policy_support_strength(policy_report)
    policy_continuity = extract_policy_continuity(policy_report)
    news_impact_strength = extract_news_impact_strength(international_news_report)
    news_credibility = extract_news_credibility(international_news_report)
    news_duration = extract_news_duration(international_news_report)
    
    logger.info(f"  ✓ 宏观情绪: {macro_score:.2f}")
    logger.info(f"  ✓ 政策支持: {policy_strength} (连续性: {policy_continuity:.2f})")
    logger.info(f"  ✓ 新闻影响: {news_impact_strength} (可信度: {news_credibility:.2f}, 持续期: {news_duration})")
    
    # 2. 基础仓位决策
    logger.info("\n💼 阶段2: 基础仓位决策")
    base_position = calculate_base_position(
        policy_strength=policy_strength,
        policy_continuity=policy_continuity,
        macro_score=macro_score
    )
    
    # 3. 短期调整决策
    logger.info("\n⚡ 阶段3: 短期调整决策")
    short_term_adjustment = calculate_short_term_adjustment(
        news_impact_strength=news_impact_strength,
        news_credibility=news_credibility,
        news_duration=news_duration
    )
    
    # 4. 计算最终仓位
    final_position = base_position + short_term_adjustment
    final_position = max(0.0, min(1.0, final_position))
    logger.info(f"\n🎯 最终仓位: {base_position:.2%} + {short_term_adjustment:+.2%} = {final_position:.2%}")
    
    # 5. 生成分层策略
    logger.info("\n📋 阶段4: 生成分层持仓")
    position_breakdown = generate_position_breakdown(
        base_position,
        short_term_adjustment,
        final_position
    )
    
    # 6. 生成触发条件
    logger.info("\n🔔 阶段5: 生成动态触发条件")
    adjustment_triggers = generate_adjustment_triggers(
        policy_report,
        international_news_report
    )
    
    logger.info("=" * 60)
    logger.info("✅ 综合决策完成")
    logger.info("=" * 60)
    
    return (
        base_position,
        short_term_adjustment,
        final_position,
        position_breakdown,
        adjustment_triggers
    )
