"""
帝国AI基础协作机制 v4.0
Imperial AI Basic Collaboration System v4.0

基于真实数据的三核心角色协作分析系统，支持结果聚合和冲突检测。
"""

import asyncio
import json
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum

# 导入核心组件
from imperial_agents.core.imperial_agent_wrapper import (
    ImperialAgentWrapper,
    AnalysisResult, 
    AnalysisType, 
    DecisionLevel
)
from imperial_agents.roles.wyckoff_ai import WyckoffAI
from imperial_agents.roles.marenhui_ai import MarenhuiAI
from imperial_agents.roles.crocodile_mentor_ai import CrocodileMentorAI

from tradingagents.utils.logging_init import get_logger
from tradingagents.agents.utils.agent_utils import Toolkit

logger = get_logger("collaboration_system")


class CollaborationMode(Enum):
    """协作模式枚举"""
    SEQUENTIAL = "sequential"      # 顺序协作
    PARALLEL = "parallel"          # 并行协作  
    EMERGENCY = "emergency"        # 紧急协作


class ConflictLevel(Enum):
    """冲突级别枚举"""
    NO_CONFLICT = "无冲突"
    MINOR_CONFLICT = "轻微冲突"
    MAJOR_CONFLICT = "重大冲突"
    CRITICAL_CONFLICT = "严重冲突"


@dataclass
class CollaborationResult:
    """协作分析结果"""
    symbol: str                                    # 股票代码
    collaboration_mode: CollaborationMode         # 协作模式
    individual_results: List[AnalysisResult]     # 个体分析结果
    consensus_decision: DecisionLevel             # 共识决策
    consensus_confidence: float                   # 共识置信度
    conflict_level: ConflictLevel                 # 冲突级别
    conflict_details: List[str]                   # 冲突详情
    final_reasoning: str                          # 最终分析理由
    risk_alerts: List[str]                        # 风险警报
    execution_time: float                         # 执行时间(秒)
    timestamp: datetime                           # 协作时间
    raw_data: Optional[Dict[str, Any]] = None     # 原始数据
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = asdict(self)
        result['collaboration_mode'] = self.collaboration_mode.value
        result['consensus_decision'] = self.consensus_decision.value
        result['conflict_level'] = self.conflict_level.value
        result['timestamp'] = self.timestamp.isoformat()
        result['individual_results'] = [r.to_dict() for r in self.individual_results]
        return result


class RealDataCollaborationSystem:
    """
    基于真实数据的协作系统
    
    整合威科夫AI、马仁辉AI、鳄鱼导师AI三个核心角色，
    实现基于真实市场数据的智能协作分析。
    """
    
    def __init__(self, llm: Any, toolkit: Optional[Toolkit] = None):
        """
        初始化协作系统
        
        Args:
            llm: 语言模型实例
            toolkit: TradingAgents工具集
        """
        self.llm = llm
        self.toolkit = toolkit or Toolkit()
        
        # 初始化三个核心角色
        self.agents = {
            "威科夫AI": WyckoffAI(llm, toolkit),
            "马仁辉AI": MarenhuiAI(llm, toolkit), 
            "鳄鱼导师AI": CrocodileMentorAI(llm, toolkit)
        }
        
        # 协作系统配置
        self.decision_weights = {
            "威科夫AI": 0.35,      # 技术分析权重
            "马仁辉AI": 0.30,      # 短线验证权重
            "鳄鱼导师AI": 0.35     # 风险控制权重
        }
        
        # 风险控制阈值
        self.risk_thresholds = {
            'confidence_threshold': 0.6,    # 最低置信度阈值
            'conflict_threshold': 0.7,      # 冲突检测阈值
            'emergency_timeout': 30.0       # 紧急模式超时(秒)
        }
        
        # 协作历史
        self.collaboration_history: List[CollaborationResult] = []
        
        logger.info("🤝 [协作系统] v4.0 初始化完成")
        logger.info(f"📊 [协作配置] 权重分配: {self.decision_weights}")
        logger.info(f"🛡️ [风险控制] 阈值设置: {self.risk_thresholds}")
    
    async def analyze_stock_collaboration(
        self,
        symbol: str,
        mode: CollaborationMode = CollaborationMode.PARALLEL,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        additional_context: Optional[str] = None
    ) -> CollaborationResult:
        """
        执行协作股票分析
        
        Args:
            symbol: 股票代码
            mode: 协作模式
            start_date: 开始日期
            end_date: 结束日期
            additional_context: 额外上下文
            
        Returns:
            CollaborationResult: 协作分析结果
        """
        start_time = datetime.now()
        
        try:
            logger.info(f"🚀 [协作系统] 开始协作分析: {symbol} (模式: {mode.value})")
            
            # 获取市场数据上下文
            market_context = await self._prepare_market_context(symbol, start_date, end_date)
            
            # 根据模式执行协作分析
            if mode == CollaborationMode.SEQUENTIAL:
                individual_results = await self._sequential_analysis(
                    symbol, market_context, additional_context
                )
            elif mode == CollaborationMode.PARALLEL:
                individual_results = await self._parallel_analysis(
                    symbol, market_context, additional_context
                )
            elif mode == CollaborationMode.EMERGENCY:
                individual_results = await self._emergency_analysis(
                    symbol, market_context, additional_context
                )
            else:
                raise ValueError(f"不支持的协作模式: {mode}")
            
            # 执行结果聚合和冲突检测
            collaboration_result = await self._aggregate_results(
                symbol, mode, individual_results, start_time
            )
            
            # 保存协作历史
            self.collaboration_history.append(collaboration_result)
            
            # 记录成功日志
            execution_time = collaboration_result.execution_time
            logger.info(f"✅ [协作系统] 分析完成: {symbol}")
            logger.info(f"📊 [协作结果] 决策: {collaboration_result.consensus_decision.value}")
            logger.info(f"🎯 [协作质量] 置信度: {collaboration_result.consensus_confidence:.2%}")
            logger.info(f"⚡ [协作性能] 执行时间: {execution_time:.2f}秒")
            logger.info(f"🔍 [冲突检测] 冲突级别: {collaboration_result.conflict_level.value}")
            
            return collaboration_result
            
        except Exception as e:
            logger.error(f"❌ [协作系统] 分析失败: {symbol} - {e}")
            traceback.print_exc()
            
            # 返回错误结果
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return CollaborationResult(
                symbol=symbol,
                collaboration_mode=mode,
                individual_results=[],
                consensus_decision=DecisionLevel.NEUTRAL,
                consensus_confidence=0.0,
                conflict_level=ConflictLevel.CRITICAL_CONFLICT,
                conflict_details=[f"协作分析失败: {str(e)}"],
                final_reasoning=f"协作过程中出现系统错误: {str(e)}",
                risk_alerts=[f"系统错误: {str(e)}", "建议暂停交易，等待系统恢复"],
                execution_time=execution_time,
                timestamp=datetime.now()
            )
    
    async def _prepare_market_context(
        self, 
        symbol: str, 
        start_date: Optional[str], 
        end_date: Optional[str]
    ) -> str:
        """
        准备市场数据上下文
        
        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            str: 市场数据上下文
        """
        try:
            logger.info(f"📊 [协作系统] 准备市场数据: {symbol}")
            
            # 设置默认日期
            if not end_date:
                end_date = datetime.now().strftime('%Y-%m-%d')
            if not start_date:
                start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            
            # 获取统一市场数据
            market_data = self.toolkit.get_stock_market_data_unified.invoke({
                'ticker': symbol,
                'start_date': start_date,
                'end_date': end_date
            })
            
            # 格式化为上下文
            context = f"""
## 市场数据上下文 ({symbol})
- 数据期间: {start_date} 至 {end_date}
- 数据长度: {len(market_data)} 条记录
- 数据获取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{market_data}
"""
            
            logger.info(f"✅ [协作系统] 市场数据准备完成: {len(market_data)} 条记录")
            return context
            
        except Exception as e:
            logger.warning(f"⚠️ [协作系统] 市场数据获取失败: {e}")
            return f"市场数据获取失败: {str(e)}"
    
    async def _sequential_analysis(
        self, 
        symbol: str, 
        market_context: str, 
        additional_context: Optional[str]
    ) -> List[AnalysisResult]:
        """
        顺序协作分析
        
        Args:
            symbol: 股票代码
            market_context: 市场数据上下文
            additional_context: 额外上下文
            
        Returns:
            List[AnalysisResult]: 分析结果列表
        """
        logger.info(f"🔄 [顺序协作] 开始顺序分析: {symbol}")
        
        results = []
        analysis_chain = [
            ("威科夫AI", AnalysisType.TECHNICAL_ANALYSIS),
            ("马仁辉AI", AnalysisType.RISK_ANALYSIS),
            ("鳄鱼导师AI", AnalysisType.RISK_ANALYSIS)
        ]
        
        accumulated_context = market_context or ""
        if additional_context:
            accumulated_context += f"\n\n{additional_context}"
        
        for agent_name, analysis_type in analysis_chain:
            try:
                logger.info(f"🎯 [顺序协作] {agent_name} 开始分析")
                
                agent = self.agents[agent_name]
                
                # 为后续角色添加前面的分析结果
                if results:
                    previous_results = "\n\n## 前序分析结果\n"
                    for prev_result in results:
                        previous_results += f"\n**{prev_result.role_name}**: {prev_result.decision.value} (置信度: {prev_result.confidence:.2%})\n"
                        previous_results += f"关键观点: {prev_result.reasoning[:200]}...\n"
                    accumulated_context += previous_results
                
                result = await agent.analyze_stock_async(
                    symbol=symbol,
                    analysis_type=analysis_type,
                    additional_context=accumulated_context
                )
                
                results.append(result)
                logger.info(f"✅ [顺序协作] {agent_name} 分析完成: {result.decision.value}")
                
            except Exception as e:
                logger.error(f"❌ [顺序协作] {agent_name} 分析失败: {e}")
                # 创建错误结果，但继续执行
                error_result = AnalysisResult(
                    role_name=agent_name,
                    analysis_type=analysis_type,
                    symbol=symbol,
                    decision=DecisionLevel.NEUTRAL,
                    confidence=0.0,
                    reasoning=f"分析失败: {str(e)}",
                    key_factors=[],
                    risk_warnings=[f"分析失败: {str(e)}"],
                    timestamp=datetime.now()
                )
                results.append(error_result)
        
        logger.info(f"🏁 [顺序协作] 完成，共获得 {len(results)} 个分析结果")
        return results
    
    async def _parallel_analysis(
        self, 
        symbol: str, 
        market_context: str, 
        additional_context: Optional[str]
    ) -> List[AnalysisResult]:
        """
        并行协作分析
        
        Args:
            symbol: 股票代码
            market_context: 市场数据上下文
            additional_context: 额外上下文
            
        Returns:
            List[AnalysisResult]: 分析结果列表
        """
        logger.info(f"⚡ [并行协作] 开始并行分析: {symbol}")
        
        # 准备分析上下文
        full_context = market_context or ""
        if additional_context:
            full_context += f"\n\n{additional_context}"
        
        # 创建并行任务
        tasks = []
        analysis_configs = [
            ("威科夫AI", AnalysisType.TECHNICAL_ANALYSIS),
            ("马仁辉AI", AnalysisType.RISK_ANALYSIS),
            ("鳄鱼导师AI", AnalysisType.RISK_ANALYSIS)
        ]
        
        for agent_name, analysis_type in analysis_configs:
            agent = self.agents[agent_name]
            task = asyncio.create_task(
                agent.analyze_stock_async(
                    symbol=symbol,
                    analysis_type=analysis_type,
                    additional_context=full_context
                )
            )
            tasks.append((agent_name, task))
        
        # 等待所有任务完成
        results = []
        for agent_name, task in tasks:
            try:
                result = await task
                results.append(result)
                logger.info(f"✅ [并行协作] {agent_name} 分析完成: {result.decision.value}")
            except Exception as e:
                logger.error(f"❌ [并行协作] {agent_name} 分析失败: {e}")
                # 创建错误结果
                error_result = AnalysisResult(
                    role_name=agent_name,
                    analysis_type=AnalysisType.RISK_ANALYSIS,
                    symbol=symbol,
                    decision=DecisionLevel.NEUTRAL,
                    confidence=0.0,
                    reasoning=f"并行分析失败: {str(e)}",
                    key_factors=[],
                    risk_warnings=[f"分析失败: {str(e)}"],
                    timestamp=datetime.now()
                )
                results.append(error_result)
        
        logger.info(f"🏁 [并行协作] 完成，共获得 {len(results)} 个分析结果")
        return results
    
    async def _emergency_analysis(
        self, 
        symbol: str, 
        market_context: str, 
        additional_context: Optional[str]
    ) -> List[AnalysisResult]:
        """
        紧急协作分析（快速模式）
        
        Args:
            symbol: 股票代码
            market_context: 市场数据上下文
            additional_context: 额外上下文
            
        Returns:
            List[AnalysisResult]: 分析结果列表
        """
        logger.info(f"🚨 [紧急协作] 开始紧急分析: {symbol}")
        
        # 准备紧急分析上下文
        emergency_context = f"""
{market_context}

## 紧急分析模式
当前为紧急分析模式，要求快速给出核心判断：
1. 快速识别主要风险
2. 给出明确的操作建议
3. 重点关注止损和风险控制

{additional_context or ""}
"""
        
        # 创建并行任务（但设置超时）
        tasks = []
        for agent_name in ["鳄鱼导师AI", "马仁辉AI"]:  # 紧急模式只用风险控制角色
            agent = self.agents[agent_name]
            task = asyncio.create_task(
                agent.analyze_stock_async(
                    symbol=symbol,
                    analysis_type=AnalysisType.RISK_ANALYSIS,
                    additional_context=emergency_context
                )
            )
            tasks.append((agent_name, task))
        
        # 等待任务完成（带超时）
        results = []
        timeout = self.risk_thresholds['emergency_timeout']
        
        try:
            for agent_name, task in tasks:
                try:
                    result = await asyncio.wait_for(task, timeout=timeout)
                    results.append(result)
                    logger.info(f"🚨 [紧急协作] {agent_name} 快速分析完成")
                except asyncio.TimeoutError:
                    logger.warning(f"⏰ [紧急协作] {agent_name} 分析超时")
                    # 创建超时结果
                    timeout_result = AnalysisResult(
                        role_name=agent_name,
                        analysis_type=AnalysisType.RISK_ANALYSIS,
                        symbol=symbol,
                        decision=DecisionLevel.NEUTRAL,
                        confidence=0.0,
                        reasoning="紧急分析超时，建议谨慎操作",
                        key_factors=["分析超时"],
                        risk_warnings=["分析超时", "建议暂停操作"],
                        timestamp=datetime.now()
                    )
                    results.append(timeout_result)
                except Exception as e:
                    logger.error(f"❌ [紧急协作] {agent_name} 分析失败: {e}")
                    error_result = AnalysisResult(
                        role_name=agent_name,
                        analysis_type=AnalysisType.RISK_ANALYSIS,
                        symbol=symbol,
                        decision=DecisionLevel.NEUTRAL,
                        confidence=0.0,
                        reasoning=f"紧急分析失败: {str(e)}",
                        key_factors=[],
                        risk_warnings=[f"分析失败: {str(e)}"],
                        timestamp=datetime.now()
                    )
                    results.append(error_result)
        
        except Exception as e:
            logger.error(f"❌ [紧急协作] 整体失败: {e}")
        
        logger.info(f"🚨 [紧急协作] 完成，共获得 {len(results)} 个分析结果")
        return results
    
    async def _aggregate_results(
        self, 
        symbol: str, 
        mode: CollaborationMode,
        individual_results: List[AnalysisResult],
        start_time: datetime
    ) -> CollaborationResult:
        """
        聚合分析结果并检测冲突
        
        Args:
            symbol: 股票代码
            mode: 协作模式
            individual_results: 个体分析结果
            start_time: 开始时间
            
        Returns:
            CollaborationResult: 聚合后的协作结果
        """
        logger.info(f"🔄 [结果聚合] 开始聚合 {len(individual_results)} 个分析结果")
        
        # 计算执行时间
        execution_time = (datetime.now() - start_time).total_seconds()
        
        # 如果没有有效结果，返回错误
        if not individual_results:
            return CollaborationResult(
                symbol=symbol,
                collaboration_mode=mode,
                individual_results=[],
                consensus_decision=DecisionLevel.NEUTRAL,
                consensus_confidence=0.0,
                conflict_level=ConflictLevel.CRITICAL_CONFLICT,
                conflict_details=["无有效分析结果"],
                final_reasoning="协作分析未获得有效结果",
                risk_alerts=["无法进行有效分析", "建议暂停操作"],
                execution_time=execution_time,
                timestamp=datetime.now()
            )
        
        # 计算加权共识决策
        consensus_decision, consensus_confidence = self._calculate_weighted_consensus(individual_results)
        
        # 检测冲突
        conflict_level, conflict_details = self._detect_conflicts(individual_results)
        
        # 聚合风险警报
        risk_alerts = self._aggregate_risk_alerts(individual_results)
        
        # 生成最终分析理由
        final_reasoning = self._generate_final_reasoning(individual_results, consensus_decision, conflict_level)
        
        result = CollaborationResult(
            symbol=symbol,
            collaboration_mode=mode,
            individual_results=individual_results,
            consensus_decision=consensus_decision,
            consensus_confidence=consensus_confidence,
            conflict_level=conflict_level,
            conflict_details=conflict_details,
            final_reasoning=final_reasoning,
            risk_alerts=risk_alerts,
            execution_time=execution_time,
            timestamp=datetime.now()
        )
        
        logger.info(f"✅ [结果聚合] 聚合完成")
        logger.info(f"📊 [共识结果] 决策: {consensus_decision.value}, 置信度: {consensus_confidence:.2%}")
        logger.info(f"🔍 [冲突检测] 级别: {conflict_level.value}")
        
        return result
    
    def _calculate_weighted_consensus(self, results: List[AnalysisResult]) -> Tuple[DecisionLevel, float]:
        """
        计算加权共识决策
        
        Args:
            results: 分析结果列表
            
        Returns:
            Tuple[DecisionLevel, float]: 共识决策和置信度
        """
        if not results:
            return DecisionLevel.NEUTRAL, 0.0
        
        # 决策映射到数值
        decision_values = {
            DecisionLevel.STRONG_SELL: -2,
            DecisionLevel.SELL: -1,
            DecisionLevel.NEUTRAL: 0,
            DecisionLevel.HOLD: 0,
            DecisionLevel.BUY: 1,
            DecisionLevel.STRONG_BUY: 2
        }
        
        # 计算加权决策值
        weighted_sum = 0.0
        weight_sum = 0.0
        confidence_sum = 0.0
        
        for result in results:
            agent_name = result.role_name
            weight = self.decision_weights.get(agent_name, 0.33)  # 默认权重
            decision_value = decision_values.get(result.decision, 0)
            
            weighted_sum += decision_value * weight * result.confidence
            weight_sum += weight
            confidence_sum += result.confidence * weight
        
        # 计算平均值
        if weight_sum > 0:
            avg_decision_value = weighted_sum / weight_sum
            avg_confidence = confidence_sum / weight_sum
        else:
            avg_decision_value = 0.0
            avg_confidence = 0.0
        
        # 将数值映射回决策级别
        if avg_decision_value >= 1.5:
            consensus_decision = DecisionLevel.STRONG_BUY
        elif avg_decision_value >= 0.5:
            consensus_decision = DecisionLevel.BUY
        elif avg_decision_value <= -1.5:
            consensus_decision = DecisionLevel.STRONG_SELL
        elif avg_decision_value <= -0.5:
            consensus_decision = DecisionLevel.SELL
        elif abs(avg_decision_value) <= 0.2:
            consensus_decision = DecisionLevel.NEUTRAL
        else:
            consensus_decision = DecisionLevel.HOLD
        
        return consensus_decision, avg_confidence
    
    def _detect_conflicts(self, results: List[AnalysisResult]) -> Tuple[ConflictLevel, List[str]]:
        """
        检测分析结果冲突
        
        Args:
            results: 分析结果列表
            
        Returns:
            Tuple[ConflictLevel, List[str]]: 冲突级别和详情
        """
        if len(results) < 2:
            return ConflictLevel.NO_CONFLICT, []
        
        # 提取决策方向
        decisions = [r.decision for r in results]
        confidence_levels = [r.confidence for r in results]
        
        # 检查决策一致性
        buy_decisions = [d for d in decisions if d in [DecisionLevel.BUY, DecisionLevel.STRONG_BUY]]
        sell_decisions = [d for d in decisions if d in [DecisionLevel.SELL, DecisionLevel.STRONG_SELL]]
        neutral_decisions = [d for d in decisions if d in [DecisionLevel.NEUTRAL, DecisionLevel.HOLD]]
        
        conflict_details = []
        
        # 严重冲突：同时有强烈买入和强烈卖出
        if DecisionLevel.STRONG_BUY in decisions and DecisionLevel.STRONG_SELL in decisions:
            conflict_details.append("存在强烈买入与强烈卖出的直接冲突")
            return ConflictLevel.CRITICAL_CONFLICT, conflict_details
        
        # 重大冲突：买入和卖出同时存在
        if buy_decisions and sell_decisions:
            conflict_details.append(f"买入建议({len(buy_decisions)}个)与卖出建议({len(sell_decisions)}个)存在冲突")
            return ConflictLevel.MAJOR_CONFLICT, conflict_details
        
        # 轻微冲突：置信度差异很大
        if confidence_levels:
            max_confidence = max(confidence_levels)
            min_confidence = min(confidence_levels)
            confidence_spread = max_confidence - min_confidence
            
            if confidence_spread > 0.4:
                conflict_details.append(f"置信度差异较大: {min_confidence:.2%} - {max_confidence:.2%}")
                return ConflictLevel.MINOR_CONFLICT, conflict_details
        
        # 轻微冲突：风险提示差异
        risk_warnings_count = sum(len(r.risk_warnings) for r in results)
        if risk_warnings_count > len(results) * 2:  # 平均每个角色超过2个风险提示
            conflict_details.append("风险提示存在较大差异")
            return ConflictLevel.MINOR_CONFLICT, conflict_details
        
        return ConflictLevel.NO_CONFLICT, []
    
    def _aggregate_risk_alerts(self, results: List[AnalysisResult]) -> List[str]:
        """
        聚合风险警报
        
        Args:
            results: 分析结果列表
            
        Returns:
            List[str]: 聚合后的风险警报
        """
        all_risks = []
        
        for result in results:
            for warning in result.risk_warnings:
                if warning not in all_risks:  # 去重
                    all_risks.append(f"[{result.role_name}] {warning}")
        
        # 添加协作系统级别的风险警报
        avg_confidence = sum(r.confidence for r in results) / len(results) if results else 0.0
        
        if avg_confidence < self.risk_thresholds['confidence_threshold']:
            all_risks.insert(0, f"⚠️ 整体置信度偏低 ({avg_confidence:.2%})，建议谨慎操作")
        
        return all_risks
    
    def _generate_final_reasoning(
        self, 
        results: List[AnalysisResult], 
        consensus_decision: DecisionLevel,
        conflict_level: ConflictLevel
    ) -> str:
        """
        生成最终分析理由
        
        Args:
            results: 分析结果列表
            consensus_decision: 共识决策
            conflict_level: 冲突级别
            
        Returns:
            str: 最终分析理由
        """
        reasoning = "## 帝国AI三角色协作分析报告\n\n"
        
        # 各角色观点摘要
        reasoning += "### 🎭 各角色分析观点\n\n"
        for result in results:
            reasoning += f"**{result.role_name}**: {result.decision.value} (置信度: {result.confidence:.2%})\n"
            reasoning += f"核心观点: {result.reasoning[:150]}...\n\n"
        
        # 共识决策说明
        reasoning += f"### 🤝 协作共识决策\n\n"
        reasoning += f"经过三角色协作分析，形成共识决策: **{consensus_decision.value}**\n\n"
        
        # 冲突情况说明
        if conflict_level != ConflictLevel.NO_CONFLICT:
            reasoning += f"### ⚠️ 冲突分析\n\n"
            reasoning += f"检测到 {conflict_level.value}，请注意:\n"
            reasoning += "- 不同角色在某些判断上存在分歧\n"
            reasoning += "- 建议综合考虑各方观点\n"
            reasoning += "- 重点关注风险控制\n\n"
        
        # 操作建议
        reasoning += "### 💡 操作建议\n\n"
        reasoning += f"基于三角色协作分析，建议采取 **{consensus_decision.value}** 策略。\n"
        reasoning += "具体操作请结合个人风险承受能力和资金管理原则。\n\n"
        
        reasoning += "---\n"
        reasoning += "*本分析由帝国AI三角色协作系统生成，仅供参考，投资有风险，决策需谨慎。*"
        
        return reasoning
    
    def get_collaboration_summary(self, limit: int = 10) -> Dict[str, Any]:
        """
        获取协作历史摘要
        
        Args:
            limit: 返回记录数量限制
            
        Returns:
            Dict[str, Any]: 协作摘要
        """
        recent_collaborations = self.collaboration_history[-limit:] if self.collaboration_history else []
        
        if not recent_collaborations:
            return {
                'total_collaborations': 0,
                'recent_collaborations': [],
                'avg_execution_time': 0.0,
                'avg_confidence': 0.0,
                'conflict_distribution': {},
                'decision_distribution': {}
            }
        
        # 计算统计信息
        total_execution_time = sum(c.execution_time for c in recent_collaborations)
        avg_execution_time = total_execution_time / len(recent_collaborations)
        
        total_confidence = sum(c.consensus_confidence for c in recent_collaborations)
        avg_confidence = total_confidence / len(recent_collaborations)
        
        # 冲突分布
        conflict_dist = {}
        for collab in recent_collaborations:
            conflict_name = collab.conflict_level.value
            conflict_dist[conflict_name] = conflict_dist.get(conflict_name, 0) + 1
        
        # 决策分布
        decision_dist = {}
        for collab in recent_collaborations:
            decision_name = collab.consensus_decision.value
            decision_dist[decision_name] = decision_dist.get(decision_name, 0) + 1
        
        return {
            'total_collaborations': len(self.collaboration_history),
            'recent_collaborations': [c.to_dict() for c in recent_collaborations],
            'avg_execution_time': avg_execution_time,
            'avg_confidence': avg_confidence,
            'conflict_distribution': conflict_dist,
            'decision_distribution': decision_dist
        }


# 导出主要类
__all__ = [
    'RealDataCollaborationSystem',
    'CollaborationResult',
    'CollaborationMode',
    'ConflictLevel'
]
