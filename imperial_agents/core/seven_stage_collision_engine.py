"""
帝国AI七阶段对撞决策引擎
Phase 4H-H1: 核心功能扩展 - 对撞机制实现

创建时间: 2025-08-16
版本: v1.0
作者: 帝国AI项目团队
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import time
import json
from pathlib import Path

# 导入帝国AI基础组件
from imperial_agents.core.imperial_agent_wrapper import ImperialAgentWrapper
from imperial_agents.core.collaboration_system import CollaborationSystem


class CollisionStage(Enum):
    """七阶段对撞流程枚举"""
    INITIAL_ANALYSIS = "初步分析"
    OPINION_COLLECTION = "意见收集"
    COLLISION_DISCUSSION = "对撞讨论"
    DISSENT_HANDLING = "异议处理"
    DEEP_ANALYSIS = "深度分析"
    COMPREHENSIVE_DECISION = "综合决策"
    EXECUTION_CONFIRMATION = "执行确认"


@dataclass
class CollisionOpinion:
    """对撞意见数据结构"""
    agent_name: str
    stage: CollisionStage
    opinion: str
    confidence: float
    reasoning: str
    supporting_data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class CollisionResult:
    """对撞结果数据结构"""
    final_decision: str
    confidence_score: float
    consensus_level: float
    dissent_points: List[str]
    execution_plan: Dict[str, Any]
    process_log: List[Dict[str, Any]]
    total_duration: float
    stage_durations: Dict[CollisionStage, float]


class SevenStageCollisionEngine:
    """
    七阶段对撞决策引擎
    
    实现帝国特色的智能决策对撞机制，通过七个阶段的深度分析和讨论，
    确保决策的科学性、全面性和可执行性。
    """
    
    def __init__(self, agents: List[ImperialAgentWrapper], config: Optional[Dict] = None):
        """
        初始化对撞引擎
        
        Args:
            agents: 参与对撞的智能体列表
            config: 引擎配置参数
        """
        self.agents = agents
        self.config = config or self._get_default_config()
        self.logger = self._setup_logger()
        self.collaboration_system = CollaborationSystem(agents)
        
        # 对撞过程状态
        self.current_stage = None
        self.opinions_history: List[CollisionOpinion] = []
        self.process_log: List[Dict[str, Any]] = []
        self.start_time = None
        
        self.logger.info(f"七阶段对撞引擎初始化完成，参与智能体: {[a.agent_name for a in agents]}")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "max_stage_duration": 60.0,  # 每阶段最大时间（秒）
            "min_consensus_threshold": 0.7,  # 最小共识阈值
            "max_dissent_rounds": 3,  # 最大异议处理轮数
            "confidence_weight": 0.4,  # 置信度权重
            "consensus_weight": 0.6,  # 共识度权重
            "enable_deep_analysis": True,  # 启用深度分析
            "save_process_log": True,  # 保存过程日志
        }
    
    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器"""
        logger = logging.getLogger("CollisionEngine")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    async def run_collision_process(self, task_data: Dict[str, Any]) -> CollisionResult:
        """
        运行完整的七阶段对撞流程
        
        Args:
            task_data: 任务数据，包含分析目标、数据等
            
        Returns:
            CollisionResult: 对撞决策结果
        """
        self.start_time = time.time()
        self.logger.info(f"开始七阶段对撞流程，任务: {task_data.get('task_name', 'Unknown')}")
        
        try:
            stage_results = {}
            
            # 执行七个阶段
            for stage in CollisionStage:
                self.current_stage = stage
                self.logger.info(f"进入{stage.value}阶段")
                
                stage_start_time = time.time()
                stage_result = await self._execute_stage(stage, task_data, stage_results)
                stage_duration = time.time() - stage_start_time
                
                stage_results[stage] = {
                    "result": stage_result,
                    "duration": stage_duration
                }
                
                self._log_stage_completion(stage, stage_duration, stage_result)
                
                # 检查是否需要提前终止
                if self._should_terminate_early(stage, stage_result):
                    self.logger.warning(f"在{stage.value}阶段提前终止对撞流程")
                    break
            
            # 生成最终结果
            final_result = self._generate_final_result(task_data, stage_results)
            
            total_duration = time.time() - self.start_time
            final_result.total_duration = total_duration
            
            self.logger.info(f"七阶段对撞流程完成，总耗时: {total_duration:.2f}秒")
            return final_result
            
        except Exception as e:
            self.logger.error(f"对撞流程执行失败: {str(e)}")
            raise
    
    async def _execute_stage(self, stage: CollisionStage, task_data: Dict[str, Any], 
                           previous_results: Dict) -> Dict[str, Any]:
        """
        执行单个阶段
        
        Args:
            stage: 当前阶段
            task_data: 任务数据
            previous_results: 之前阶段的结果
            
        Returns:
            Dict: 阶段执行结果
        """
        stage_methods = {
            CollisionStage.INITIAL_ANALYSIS: self._stage_initial_analysis,
            CollisionStage.OPINION_COLLECTION: self._stage_opinion_collection,
            CollisionStage.COLLISION_DISCUSSION: self._stage_collision_discussion,
            CollisionStage.DISSENT_HANDLING: self._stage_dissent_handling,
            CollisionStage.DEEP_ANALYSIS: self._stage_deep_analysis,
            CollisionStage.COMPREHENSIVE_DECISION: self._stage_comprehensive_decision,
            CollisionStage.EXECUTION_CONFIRMATION: self._stage_execution_confirmation,
        }
        
        method = stage_methods.get(stage)
        if not method:
            raise ValueError(f"未知阶段: {stage}")
        
        return await method(task_data, previous_results)
    
    async def _stage_initial_analysis(self, task_data: Dict[str, Any], 
                                    previous_results: Dict) -> Dict[str, Any]:
        """第一阶段：初步分析"""
        self.logger.info("执行初步分析阶段")
        
        # 每个智能体进行独立的初步分析
        analysis_tasks = []
        for agent in self.agents:
            analysis_prompt = self._build_initial_analysis_prompt(task_data, agent)
            task = agent.analyze(analysis_prompt)
            analysis_tasks.append(task)
        
        # 并行执行分析
        initial_analyses = await asyncio.gather(*analysis_tasks, return_exceptions=True)
        
        # 处理分析结果
        valid_analyses = []
        for i, analysis in enumerate(initial_analyses):
            if isinstance(analysis, Exception):
                self.logger.warning(f"{self.agents[i].agent_name}初步分析失败: {analysis}")
                continue
            
            opinion = CollisionOpinion(
                agent_name=self.agents[i].agent_name,
                stage=CollisionStage.INITIAL_ANALYSIS,
                opinion=analysis.get('analysis', ''),
                confidence=analysis.get('confidence', 0.5),
                reasoning=analysis.get('reasoning', ''),
                supporting_data=analysis.get('supporting_data', {})
            )
            
            self.opinions_history.append(opinion)
            valid_analyses.append(analysis)
        
        return {
            "analyses": valid_analyses,
            "participant_count": len(valid_analyses),
            "average_confidence": sum(a.get('confidence', 0.5) for a in valid_analyses) / max(len(valid_analyses), 1)
        }
    
    async def _stage_opinion_collection(self, task_data: Dict[str, Any], 
                                      previous_results: Dict) -> Dict[str, Any]:
        """第二阶段：意见收集"""
        self.logger.info("执行意见收集阶段")
        
        initial_analyses = previous_results.get(CollisionStage.INITIAL_ANALYSIS, {}).get("analyses", [])
        
        # 基于初步分析，收集各智能体的详细意见
        opinion_tasks = []
        for i, agent in enumerate(self.agents):
            if i < len(initial_analyses):
                opinion_prompt = self._build_opinion_collection_prompt(
                    task_data, agent, initial_analyses[i], initial_analyses
                )
                task = agent.analyze(opinion_prompt)
                opinion_tasks.append(task)
        
        detailed_opinions = await asyncio.gather(*opinion_tasks, return_exceptions=True)
        
        # 分析意见分歧程度
        valid_opinions = []
        for i, opinion in enumerate(detailed_opinions):
            if isinstance(opinion, Exception):
                continue
            
            opinion_obj = CollisionOpinion(
                agent_name=self.agents[i].agent_name,
                stage=CollisionStage.OPINION_COLLECTION,
                opinion=opinion.get('detailed_opinion', ''),
                confidence=opinion.get('confidence', 0.5),
                reasoning=opinion.get('reasoning', ''),
                supporting_data=opinion.get('supporting_data', {})
            )
            
            self.opinions_history.append(opinion_obj)
            valid_opinions.append(opinion)
        
        # 计算意见分歧度
        divergence_score = self._calculate_opinion_divergence(valid_opinions)
        
        return {
            "detailed_opinions": valid_opinions,
            "divergence_score": divergence_score,
            "consensus_areas": self._identify_consensus_areas(valid_opinions),
            "conflict_areas": self._identify_conflict_areas(valid_opinions)
        }
    
    async def _stage_collision_discussion(self, task_data: Dict[str, Any], 
                                        previous_results: Dict) -> Dict[str, Any]:
        """第三阶段：对撞讨论"""
        self.logger.info("执行对撞讨论阶段")
        
        opinion_data = previous_results.get(CollisionStage.OPINION_COLLECTION, {})
        conflict_areas = opinion_data.get("conflict_areas", [])
        
        if not conflict_areas:
            self.logger.info("无明显冲突，跳过对撞讨论")
            return {"collision_required": False, "discussions": []}
        
        # 针对每个冲突点进行对撞讨论
        collision_discussions = []
        for conflict in conflict_areas:
            discussion_result = await self._conduct_collision_discussion(
                task_data, conflict, previous_results
            )
            collision_discussions.append(discussion_result)
        
        return {
            "collision_required": True,
            "discussions": collision_discussions,
            "resolution_count": len([d for d in collision_discussions if d.get("resolved", False)])
        }
    
    async def _stage_dissent_handling(self, task_data: Dict[str, Any], 
                                    previous_results: Dict) -> Dict[str, Any]:
        """第四阶段：异议处理"""
        self.logger.info("执行异议处理阶段")
        
        collision_data = previous_results.get(CollisionStage.COLLISION_DISCUSSION, {})
        discussions = collision_data.get("discussions", [])
        
        # 识别未解决的异议
        unresolved_dissents = [d for d in discussions if not d.get("resolved", False)]
        
        if not unresolved_dissents:
            self.logger.info("无未解决异议")
            return {"dissents_handled": True, "resolutions": []}
        
        # 处理每个异议
        dissent_resolutions = []
        for dissent in unresolved_dissents:
            resolution = await self._handle_dissent(task_data, dissent, previous_results)
            dissent_resolutions.append(resolution)
        
        return {
            "dissents_handled": len(dissent_resolutions) > 0,
            "resolutions": dissent_resolutions,
            "remaining_conflicts": len([r for r in dissent_resolutions if not r.get("resolved", False)])
        }
    
    async def _stage_deep_analysis(self, task_data: Dict[str, Any], 
                                 previous_results: Dict) -> Dict[str, Any]:
        """第五阶段：深度分析"""
        self.logger.info("执行深度分析阶段")
        
        if not self.config.get("enable_deep_analysis", True):
            self.logger.info("深度分析已禁用，跳过此阶段")
            return {"deep_analysis_enabled": False}
        
        # 汇总前面阶段的所有信息
        consolidated_info = self._consolidate_previous_stages(previous_results)
        
        # 选择最权威的智能体进行深度分析
        primary_analyst = self._select_primary_analyst(task_data)
        
        # 执行深度分析
        deep_analysis_prompt = self._build_deep_analysis_prompt(
            task_data, consolidated_info, previous_results
        )
        
        deep_analysis_result = await primary_analyst.analyze(deep_analysis_prompt)
        
        return {
            "deep_analysis_enabled": True,
            "primary_analyst": primary_analyst.agent_name,
            "deep_insights": deep_analysis_result.get("insights", []),
            "risk_assessment": deep_analysis_result.get("risk_assessment", {}),
            "opportunity_analysis": deep_analysis_result.get("opportunities", {}),
            "recommendation": deep_analysis_result.get("recommendation", "")
        }
    
    async def _stage_comprehensive_decision(self, task_data: Dict[str, Any], 
                                          previous_results: Dict) -> Dict[str, Any]:
        """第六阶段：综合决策"""
        self.logger.info("执行综合决策阶段")
        
        # 汇总所有阶段的结果
        all_opinions = [op for op in self.opinions_history]
        consensus_level = self._calculate_final_consensus(previous_results)
        
        # 生成综合决策
        decision_data = {
            "all_opinions": all_opinions,
            "consensus_level": consensus_level,
            "previous_results": previous_results,
            "task_data": task_data
        }
        
        # 使用加权投票机制生成最终决策
        final_decision = await self._generate_comprehensive_decision(decision_data)
        
        return {
            "final_decision": final_decision.get("decision", ""),
            "confidence_score": final_decision.get("confidence", 0.0),
            "consensus_level": consensus_level,
            "decision_rationale": final_decision.get("rationale", ""),
            "supporting_evidence": final_decision.get("evidence", [])
        }
    
    async def _stage_execution_confirmation(self, task_data: Dict[str, Any], 
                                          previous_results: Dict) -> Dict[str, Any]:
        """第七阶段：执行确认"""
        self.logger.info("执行执行确认阶段")
        
        decision_data = previous_results.get(CollisionStage.COMPREHENSIVE_DECISION, {})
        final_decision = decision_data.get("final_decision", "")
        
        if not final_decision:
            raise ValueError("缺少综合决策结果")
        
        # 生成执行计划
        execution_plan = await self._generate_execution_plan(
            final_decision, task_data, previous_results
        )
        
        # 执行风险评估
        risk_assessment = await self._conduct_execution_risk_assessment(
            execution_plan, previous_results
        )
        
        # 最终确认
        confirmation_result = await self._final_execution_confirmation(
            execution_plan, risk_assessment
        )
        
        return {
            "execution_plan": execution_plan,
            "risk_assessment": risk_assessment,
            "confirmed": confirmation_result.get("confirmed", False),
            "execution_steps": execution_plan.get("steps", []),
            "timeline": execution_plan.get("timeline", {}),
            "success_metrics": execution_plan.get("metrics", {})
        }
    
    def _build_initial_analysis_prompt(self, task_data: Dict[str, Any], 
                                     agent: ImperialAgentWrapper) -> str:
        """构建初步分析提示"""
        return f"""
请基于你的专业知识对以下任务进行初步分析：

任务信息：
{json.dumps(task_data, ensure_ascii=False, indent=2)}

请从你的专业角度（{agent.agent_name}）提供：
1. 初步分析和观点
2. 关键风险点识别
3. 机会点识别
4. 你的建议方向
5. 分析置信度（0-1）

请以JSON格式返回结果。
"""
    
    def _build_opinion_collection_prompt(self, task_data: Dict[str, Any], 
                                       agent: ImperialAgentWrapper,
                                       own_analysis: Dict[str, Any],
                                       all_analyses: List[Dict[str, Any]]) -> str:
        """构建意见收集提示"""
        return f"""
基于你的初步分析和其他专家的分析，请提供更详细的意见：

你的初步分析：
{json.dumps(own_analysis, ensure_ascii=False, indent=2)}

其他专家分析：
{json.dumps(all_analyses, ensure_ascii=False, indent=2)}

请提供：
1. 详细的专业意见
2. 对其他专家观点的评价
3. 你坚持的核心观点
4. 可能的妥协空间
5. 更新后的置信度

请以JSON格式返回结果。
"""
    
    def _calculate_opinion_divergence(self, opinions: List[Dict[str, Any]]) -> float:
        """计算意见分歧度"""
        if len(opinions) < 2:
            return 0.0
        
        # 简化的分歧度计算逻辑
        confidences = [op.get('confidence', 0.5) for op in opinions]
        variance = sum((c - sum(confidences)/len(confidences))**2 for c in confidences) / len(confidences)
        
        return min(variance * 2, 1.0)  # 标准化到0-1范围
    
    def _identify_consensus_areas(self, opinions: List[Dict[str, Any]]) -> List[str]:
        """识别共识领域"""
        # 简化实现，实际应该用NLP分析意见相似性
        return ["基本面分析重要性", "风险控制必要性"]
    
    def _identify_conflict_areas(self, opinions: List[Dict[str, Any]]) -> List[str]:
        """识别冲突领域"""
        # 简化实现
        return ["市场趋势判断", "时机选择策略"]
    
    async def _conduct_collision_discussion(self, task_data: Dict[str, Any], 
                                          conflict: str, previous_results: Dict) -> Dict[str, Any]:
        """进行对撞讨论"""
        # 组织相关智能体进行针对性讨论
        discussion_prompt = f"""
针对冲突点：{conflict}

请各自阐述观点并尝试寻找共同点或合理妥协。
基于前期分析结果：{json.dumps(previous_results, ensure_ascii=False)}

请提供解决方案建议。
"""
        
        # 简化实现：随机选择一个智能体回答
        if self.agents:
            result = await self.agents[0].analyze(discussion_prompt)
            return {"conflict": conflict, "discussion": result, "resolved": True}
        
        return {"conflict": conflict, "discussion": {}, "resolved": False}
    
    async def _handle_dissent(self, task_data: Dict[str, Any], 
                            dissent: Dict[str, Any], previous_results: Dict) -> Dict[str, Any]:
        """处理异议"""
        # 异议处理逻辑
        return {"dissent": dissent, "resolution": "通过深度分析解决", "resolved": True}
    
    def _consolidate_previous_stages(self, previous_results: Dict) -> Dict[str, Any]:
        """汇总前面阶段的信息"""
        return {
            "stage_summaries": {k.value: v for k, v in previous_results.items()},
            "key_insights": [],
            "unresolved_issues": [],
            "consensus_points": []
        }
    
    def _select_primary_analyst(self, task_data: Dict[str, Any]) -> ImperialAgentWrapper:
        """选择主要分析师"""
        # 简化：选择第一个智能体
        return self.agents[0] if self.agents else None
    
    def _build_deep_analysis_prompt(self, task_data: Dict[str, Any], 
                                  consolidated_info: Dict[str, Any],
                                  previous_results: Dict) -> str:
        """构建深度分析提示"""
        return f"""
请基于前期所有阶段的分析结果，进行深度分析：

汇总信息：
{json.dumps(consolidated_info, ensure_ascii=False, indent=2)}

任务数据：
{json.dumps(task_data, ensure_ascii=False, indent=2)}

请提供：
1. 深层次洞察
2. 风险全面评估
3. 机会深度挖掘
4. 战略建议

以JSON格式返回结果。
"""
    
    def _calculate_final_consensus(self, previous_results: Dict) -> float:
        """计算最终共识度"""
        # 基于各阶段结果计算共识度
        consensus_scores = []
        
        # 从意见收集阶段获取分歧度
        opinion_data = previous_results.get(CollisionStage.OPINION_COLLECTION, {})
        divergence = opinion_data.get("divergence_score", 0.5)
        consensus_scores.append(1.0 - divergence)
        
        # 从对撞讨论阶段获取解决率
        collision_data = previous_results.get(CollisionStage.COLLISION_DISCUSSION, {})
        discussions = collision_data.get("discussions", [])
        if discussions:
            resolution_rate = len([d for d in discussions if d.get("resolved", False)]) / len(discussions)
            consensus_scores.append(resolution_rate)
        
        return sum(consensus_scores) / max(len(consensus_scores), 1)
    
    async def _generate_comprehensive_decision(self, decision_data: Dict[str, Any]) -> Dict[str, Any]:
        """生成综合决策"""
        # 使用第一个智能体生成综合决策
        if not self.agents:
            return {"decision": "无智能体参与", "confidence": 0.0}
        
        decision_prompt = f"""
基于所有阶段的分析和讨论，请生成最终综合决策：

决策数据：
{json.dumps(decision_data, ensure_ascii=False, indent=2)}

请提供：
1. 最终决策
2. 决策置信度
3. 决策理由
4. 支持证据

以JSON格式返回。
"""
        
        result = await self.agents[0].analyze(decision_prompt)
        return result
    
    async def _generate_execution_plan(self, decision: str, task_data: Dict[str, Any],
                                     previous_results: Dict) -> Dict[str, Any]:
        """生成执行计划"""
        return {
            "decision": decision,
            "steps": [
                {"step": 1, "action": "准备执行", "timeline": "立即"},
                {"step": 2, "action": "监控执行", "timeline": "持续"},
                {"step": 3, "action": "评估结果", "timeline": "执行后"}
            ],
            "timeline": {"start": "立即", "duration": "视情况而定"},
            "metrics": {"success_rate": ">80%", "risk_level": "<20%"}
        }
    
    async def _conduct_execution_risk_assessment(self, execution_plan: Dict[str, Any],
                                               previous_results: Dict) -> Dict[str, Any]:
        """执行风险评估"""
        return {
            "overall_risk": "中等",
            "key_risks": ["市场变化", "执行偏差"],
            "mitigation_measures": ["密切监控", "及时调整"],
            "acceptable": True
        }
    
    async def _final_execution_confirmation(self, execution_plan: Dict[str, Any],
                                          risk_assessment: Dict[str, Any]) -> Dict[str, Any]:
        """最终执行确认"""
        acceptable = risk_assessment.get("acceptable", False)
        return {
            "confirmed": acceptable,
            "confirmation_reason": "风险可控，执行计划可行" if acceptable else "风险过高，需要调整"
        }
    
    def _generate_final_result(self, task_data: Dict[str, Any], 
                             stage_results: Dict) -> CollisionResult:
        """生成最终结果"""
        # 从综合决策阶段获取结果
        decision_data = stage_results.get(CollisionStage.COMPREHENSIVE_DECISION, {}).get("result", {})
        execution_data = stage_results.get(CollisionStage.EXECUTION_CONFIRMATION, {}).get("result", {})
        
        # 提取异议点
        dissent_data = stage_results.get(CollisionStage.DISSENT_HANDLING, {}).get("result", {})
        dissent_points = [r.get("dissent", {}) for r in dissent_data.get("resolutions", [])]
        
        return CollisionResult(
            final_decision=decision_data.get("final_decision", ""),
            confidence_score=decision_data.get("confidence_score", 0.0),
            consensus_level=decision_data.get("consensus_level", 0.0),
            dissent_points=[str(d) for d in dissent_points],
            execution_plan=execution_data.get("execution_plan", {}),
            process_log=self.process_log.copy(),
            total_duration=0.0,  # 将在调用处设置
            stage_durations={stage: data["duration"] for stage, data in stage_results.items()}
        )
    
    def _should_terminate_early(self, stage: CollisionStage, stage_result: Dict[str, Any]) -> bool:
        """判断是否应该提前终止"""
        # 如果在异议处理阶段仍有大量未解决冲突，可能需要终止
        if stage == CollisionStage.DISSENT_HANDLING:
            remaining_conflicts = stage_result.get("remaining_conflicts", 0)
            if remaining_conflicts > len(self.agents):
                return True
        
        return False
    
    def _log_stage_completion(self, stage: CollisionStage, duration: float, result: Dict[str, Any]):
        """记录阶段完成日志"""
        log_entry = {
            "stage": stage.value,
            "duration": duration,
            "timestamp": time.time(),
            "result_summary": self._summarize_stage_result(stage, result)
        }
        
        self.process_log.append(log_entry)
        self.logger.info(f"{stage.value}阶段完成，耗时: {duration:.2f}秒")
    
    def _summarize_stage_result(self, stage: CollisionStage, result: Dict[str, Any]) -> str:
        """总结阶段结果"""
        if stage == CollisionStage.INITIAL_ANALYSIS:
            return f"参与者: {result.get('participant_count', 0)}, 平均置信度: {result.get('average_confidence', 0):.2f}"
        elif stage == CollisionStage.OPINION_COLLECTION:
            return f"分歧度: {result.get('divergence_score', 0):.2f}"
        elif stage == CollisionStage.COMPREHENSIVE_DECISION:
            return f"最终决策置信度: {result.get('confidence_score', 0):.2f}"
        else:
            return "阶段完成"


# 使用示例和测试代码
async def demo_collision_engine():
    """七阶段对撞引擎演示"""
    print("🎯 帝国AI七阶段对撞引擎演示")
    print("=" * 50)
    
    try:
        # 模拟智能体（实际使用时应该是真实的ImperialAgentWrapper实例）
        class MockAgent:
            def __init__(self, name):
                self.agent_name = name
            
            async def analyze(self, prompt):
                await asyncio.sleep(0.1)  # 模拟分析时间
                return {
                    "analysis": f"{self.agent_name}的分析结果",
                    "confidence": 0.8,
                    "reasoning": f"{self.agent_name}基于专业经验的判断",
                    "supporting_data": {"data_point": "mock_data"}
                }
        
        # 创建模拟智能体
        agents = [
            MockAgent("威科夫AI"),
            MockAgent("马仁辉AI"),
            MockAgent("鳄鱼导师AI")
        ]
        
        # 初始化对撞引擎
        engine = SevenStageCollisionEngine(agents)
        
        # 准备任务数据
        task_data = {
            "task_name": "股票投资决策",
            "target_stock": "000001.SZ",
            "analysis_period": "短期",
            "market_condition": "震荡",
            "risk_preference": "中等"
        }
        
        print(f"📋 任务信息: {task_data['task_name']}")
        print(f"🎭 参与智能体: {[agent.agent_name for agent in agents]}")
        print("\n开始执行七阶段对撞流程...")
        
        # 执行对撞流程
        start_time = time.time()
        result = await engine.run_collision_process(task_data)
        execution_time = time.time() - start_time
        
        # 输出结果
        print(f"\n🏆 对撞决策结果:")
        print(f"最终决策: {result.final_decision}")
        print(f"置信度评分: {result.confidence_score:.2f}")
        print(f"共识度: {result.consensus_level:.2f}")
        print(f"总执行时间: {execution_time:.2f}秒")
        
        if result.dissent_points:
            print(f"异议点: {len(result.dissent_points)}个")
        
        print(f"\n📊 各阶段耗时:")
        for stage, duration in result.stage_durations.items():
            print(f"  {stage.value}: {duration:.2f}秒")
        
        print(f"\n✅ 执行计划: {result.execution_plan.get('steps', [])}")
        
        return result
        
    except Exception as e:
        print(f"❌ 演示执行失败: {str(e)}")
        raise


if __name__ == "__main__":
    # 运行演示
    asyncio.run(demo_collision_engine())
