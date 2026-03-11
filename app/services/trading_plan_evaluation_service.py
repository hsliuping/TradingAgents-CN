"""
交易计划AI评估服务
使用AI评估用户制定的交易计划的优缺点
"""

import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime

from app.core.database import get_mongo_db
from app.models.trading_system import TradingSystem
from app.services.unified_analysis_engine import UnifiedAnalysisEngine

logger = logging.getLogger(__name__)


class TradingPlanEvaluationService:
    """交易计划评估服务"""

    def __init__(self):
        self.db = get_mongo_db()
        self.analysis_engine = UnifiedAnalysisEngine()

    async def evaluate_trading_plan(
        self,
        trading_system: TradingSystem,
        user_id: str,
        system_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """评估交易计划（从TradingSystem对象）
        
        Args:
            trading_system: 交易计划对象
            user_id: 用户ID
            system_id: 交易计划ID（如果已保存）
            
        Returns:
            评估结果
        """
        return await self._evaluate_trading_plan_data(trading_system, user_id, system_id)
    
    async def evaluate_trading_plan_data(
        self,
        trading_plan_data: Dict[str, Any],
        user_id: str
    ) -> Dict[str, Any]:
        """评估交易计划（从字典数据，支持未保存的计划）
        
        Args:
            trading_plan_data: 交易计划数据字典
            user_id: 用户ID
            
        Returns:
            评估结果
        """
        try:
            # 将字典转换为TradingSystem对象
            trading_system = TradingSystem(**trading_plan_data)
            return await self._evaluate_trading_plan_data(trading_system, user_id)
        except Exception as e:
            logger.error(f"评估交易计划数据失败: {e}", exc_info=True)
            raise
    
    async def _evaluate_trading_plan_data(
        self,
        trading_system: TradingSystem,
        user_id: str,
        system_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """评估交易计划
        
        Args:
            trading_system: 交易计划对象
            user_id: 用户ID
            system_id: 交易计划ID（如果已保存）
            
        Returns:
            评估结果：
            {
                "overall_score": float,  # 总体评分 (0-100)
                "strengths": List[str],  # 优点
                "weaknesses": List[str],  # 缺点
                "suggestions": List[str],  # 改进建议
                "detailed_analysis": str,  # 详细分析
                "evaluation_date": str,  # 评估日期
                "evaluation_id": str,  # 评估记录ID
            }
        """
        try:
            plan_name = getattr(trading_system, 'name', '未命名交易计划')
            logger.info(f"开始评估交易计划: {plan_name}, user_id={user_id}, system_id={system_id}")
            
            # 构建评估提示词
            prompt = self._build_evaluation_prompt(trading_system)
            
            # 调用LLM进行评估
            evaluation_result = await self._call_llm_evaluation(prompt, user_id)
            
            # 解析和格式化结果
            formatted_result = self._format_evaluation_result(evaluation_result)
            
            # 保存评估历史记录（如果有system_id）
            if system_id:
                evaluation_id = await self._save_evaluation_history(
                    system_id=system_id,
                    user_id=user_id,
                    trading_system=trading_system,
                    evaluation_result=formatted_result
                )
                formatted_result["evaluation_id"] = evaluation_id
            
            logger.info(f"交易计划评估完成: {plan_name}, 评分: {formatted_result.get('overall_score', 0)}")
            
            return formatted_result
            
        except Exception as e:
            logger.error(f"评估交易计划失败: {e}", exc_info=True)
            raise

    def _build_evaluation_prompt(self, trading_system: TradingSystem) -> str:
        """构建评估提示词"""
        
        # 格式化交易计划内容
        plan_text = self._format_trading_plan_for_evaluation(trading_system)
        
        prompt = f"""你是一位资深的交易系统评估专家，擅长分析交易计划的完整性和可执行性。

请对以下交易计划进行全面评估，从以下维度进行分析：

## 评估维度

1. **完整性**：各个模块（选股、择时、执行、持仓、风控、复盘、纪律）是否都有明确的规则
2. **一致性**：各模块规则之间是否相互协调，是否存在矛盾
3. **可执行性**：规则是否具体、可操作，是否过于模糊或抽象
4. **风险控制**：风险管理规则是否完善，是否能有效控制风险
5. **适应性**：规则是否适合其交易风格和风险偏好
6. **可进化性**：是否有复盘机制，能否持续优化

## 交易计划内容

**系统名称**：{trading_system.name}
**交易风格**：{trading_system.style.value}
**风险偏好**：{trading_system.risk_profile.value}
**系统描述**：{trading_system.description or '无'}

{plan_text}

## 输出要求

请以JSON格式输出评估结果，格式如下：

```json
{{
    "overall_score": 85,
    "strengths": [
        "优点1：...",
        "优点2：..."
    ],
    "weaknesses": [
        "缺点1：...",
        "缺点2：..."
    ],
    "suggestions": [
        "建议1：...",
        "建议2：..."
    ],
    "detailed_analysis": "详细的评估分析，包括各个维度的评分和说明..."
}}
```

**评分标准**：
- 90-100分：优秀，规则完善，可直接使用
- 80-89分：良好，规则基本完善，有少量改进空间
- 70-79分：中等，规则基本完整，但需要较多改进
- 60-69分：及格，规则不够完善，需要大量改进
- 0-59分：不及格，规则严重缺失或不合理

请确保：
1. 评分客观公正，基于实际规则内容
2. 优点和缺点都要具体，不要泛泛而谈
3. 建议要可操作，不要过于抽象
4. 详细分析要覆盖所有评估维度
"""
        
        return prompt

    def _format_trading_plan_for_evaluation(self, trading_system: TradingSystem) -> str:
        """格式化交易计划内容供评估使用"""
        
        lines = []
        
        # 选股规则
        lines.append("### 1. 选股规则")
        stock_selection = trading_system.stock_selection
        if stock_selection.analysis_config:
            lines.append(f"- 分析配置：{json.dumps(stock_selection.analysis_config, ensure_ascii=False, indent=2)}")
        if stock_selection.must_have:
            lines.append(f"- 必备条件：{len(stock_selection.must_have)}条")
            for i, rule in enumerate(stock_selection.must_have[:3], 1):
                lines.append(f"  {i}. {rule.get('rule', '')}: {rule.get('description', '')}")
        if stock_selection.exclude:
            lines.append(f"- 排除条件：{len(stock_selection.exclude)}条")
        if stock_selection.bonus:
            lines.append(f"- 加分条件：{len(stock_selection.bonus)}条")
        
        # 择时规则
        lines.append("\n### 2. 择时规则")
        timing = trading_system.timing
        if timing.market_condition:
            lines.append(f"- 大盘条件：{json.dumps(timing.market_condition, ensure_ascii=False)}")
        if timing.sector_condition:
            lines.append(f"- 行业条件：{json.dumps(timing.sector_condition, ensure_ascii=False)}")
        if timing.entry_signals:
            lines.append(f"- 买入信号：{len(timing.entry_signals)}条")
            for i, signal in enumerate(timing.entry_signals[:3], 1):
                lines.append(f"  {i}. {signal.get('signal', '')}: {signal.get('description', '')}")
        if timing.confirmation:
            lines.append(f"- 确认条件：{len(timing.confirmation)}条")
        
        # 仓位规则
        lines.append("\n### 3. 仓位规则")
        position = trading_system.position
        lines.append(f"- 总仓位控制：牛市 {position.total_position.get('bull', 0)*100:.0f}%，震荡 {position.total_position.get('range', 0)*100:.0f}%，熊市 {position.total_position.get('bear', 0)*100:.0f}%")
        lines.append(f"- 单只股票上限：{position.max_per_stock*100:.0f}%")
        lines.append(f"- 持股数量：{position.min_holdings}-{position.max_holdings}只")
        if position.scaling:
            lines.append(f"- 分批策略：{json.dumps(position.scaling, ensure_ascii=False)}")
        
        # 持仓规则
        lines.append("\n### 4. 持仓规则")
        holding = trading_system.holding
        lines.append(f"- 检视频率：{holding.review_frequency}")
        if holding.add_conditions:
            lines.append(f"- 加仓条件：{len(holding.add_conditions)}条")
        if holding.reduce_conditions:
            lines.append(f"- 减仓条件：{len(holding.reduce_conditions)}条")
        if holding.switch_conditions:
            lines.append(f"- 换股条件：{len(holding.switch_conditions)}条")
        
        # 风险管理规则
        lines.append("\n### 5. 风险管理规则")
        risk_mgmt = trading_system.risk_management
        if risk_mgmt.stop_loss:
            lines.append(f"- 止损设置：{json.dumps(risk_mgmt.stop_loss, ensure_ascii=False)}")
        if risk_mgmt.take_profit:
            lines.append(f"- 止盈设置：{json.dumps(risk_mgmt.take_profit, ensure_ascii=False)}")
        if risk_mgmt.time_stop:
            lines.append(f"- 时间止损：{json.dumps(risk_mgmt.time_stop, ensure_ascii=False)}")
        if risk_mgmt.logical_stop:
            lines.append(f"- 逻辑止损：{json.dumps(risk_mgmt.logical_stop, ensure_ascii=False)}")
        
        # 复盘规则
        lines.append("\n### 6. 复盘规则")
        review = trading_system.review
        lines.append(f"- 复盘频率：{review.frequency}")
        if review.checklist:
            lines.append(f"- 复盘内容：{len(review.checklist)}项")
            for i, item in enumerate(review.checklist[:5], 1):
                lines.append(f"  {i}. {item}")
        
        # 纪律规则
        lines.append("\n### 7. 纪律规则")
        discipline = trading_system.discipline
        if discipline.must_do:
            lines.append(f"- 必须做到：{len(discipline.must_do)}条")
            for i, rule in enumerate(discipline.must_do[:3], 1):
                lines.append(f"  {i}. {rule.get('rule', '')}: {rule.get('description', '')}")
        if discipline.must_not:
            lines.append(f"- 绝对禁止：{len(discipline.must_not)}条")
            for i, rule in enumerate(discipline.must_not[:3], 1):
                lines.append(f"  {i}. {rule.get('rule', '')}: {rule.get('description', '')}")
        if discipline.violation_actions:
            lines.append(f"- 违规处理：{len(discipline.violation_actions)}条")
        
        return "\n".join(lines)

    async def _call_llm_evaluation(self, prompt: str, user_id: str) -> str:
        """调用LLM进行评估（参考单股分析流程的调用方式）"""
        try:
            from app.services.config_provider import ConfigProvider
            from app.services.simple_analysis_service import get_provider_and_url_by_model_sync
            from tradingagents.graph.trading_graph import create_llm_by_provider
            
            # 从数据库获取系统默认的深度分析模型配置
            config_provider = ConfigProvider()
            system_settings = await config_provider.get_effective_system_settings()
            
            # 使用深度分析模型进行评估（与单股分析保持一致）
            deep_model = system_settings.get("deep_analysis_model") or system_settings.get("default_model", "qwen-plus")
            
            logger.info(f"🤖 [交易计划评估] 从数据库获取深度分析模型: {deep_model}")
            
            # 从数据库获取provider信息
            provider_info = get_provider_and_url_by_model_sync(deep_model)
            
            logger.info(f"🏭 [交易计划评估] 模型供应商: {provider_info.get('provider', '未知')}")
            logger.info(f"🔗 [交易计划评估] API地址: {provider_info.get('backend_url', '未配置')}")
            logger.info(f"🔑 [交易计划评估] API Key: {'已配置' if provider_info.get('api_key') else '未配置'}")
            
            if not provider_info.get("backend_url"):
                raise ValueError(f"模型 {deep_model} 的API地址未配置，请在设置页面配置")
            
            # 使用统一的 LLM 适配器创建实例（与单股分析保持一致）
            provider_name = provider_info.get("provider", "dashscope")
            api_key = provider_info.get("api_key")
            logger.info(f"🔧 [交易计划评估] 准备创建 LLM: provider={provider_name}, model={deep_model}, temperature=0.7")
            if api_key:
                logger.info(f"🔑 [交易计划评估] API Key 前3位: {api_key[:3] if len(api_key) >= 3 else 'N/A'}")
            llm = create_llm_by_provider(
                provider=provider_name,
                model=deep_model,
                backend_url=provider_info.get("backend_url"),
                temperature=0.7,
                max_tokens=4000,
                timeout=120,
                api_key=api_key
            )
            
            logger.info(f"✅ [交易计划评估] LLM 实例创建成功: {type(llm).__name__}")
            
            # 构建完整的提示词（包含系统提示）
            full_prompt = f"""你是一位资深的交易系统评估专家，擅长分析交易计划的完整性和可执行性。

请根据以下交易计划，从以下维度进行全面评估：
1. 完整性：是否涵盖了选股、择时、仓位、风险、纪律等关键环节
2. 一致性：各环节规则之间是否协调一致
3. 可执行性：规则是否清晰明确，便于执行
4. 风险控制：风险控制措施是否充分
5. 适应性：是否考虑了不同市场环境
6. 可进化性：是否具备持续优化的机制

请以JSON格式输出评估结果，包含以下字段：
- overall_score: 总体评分（0-100）
- grade: 等级（优秀/良好/中等/及格/不及格）
- strengths: 优点列表（数组）
- weaknesses: 缺点列表（数组）
- suggestions: 改进建议列表（数组）
- detailed_analysis: 详细分析（字符串，300-500字）

交易计划内容：
{prompt}
"""
            
            # 异步调用 LLM
            logger.info(f"📝 [交易计划评估] 开始调用LLM，Prompt长度: {len(full_prompt)} 字符")
            response = await llm.ainvoke(full_prompt)
            
            # 提取内容
            if hasattr(response, 'content'):
                content = response.content
            elif isinstance(response, str):
                content = response
            else:
                content = str(response)
            
            logger.info(f"✅ [交易计划评估] LLM响应长度: {len(content)} 字符")
            return content
            
        except Exception as e:
            logger.error(f"调用LLM评估失败: {e}", exc_info=True)
            raise

    def _format_evaluation_result(self, llm_response: str) -> Dict[str, Any]:
        """解析和格式化LLM返回的评估结果"""
        
        try:
            # 尝试提取JSON
            import re
            
            # 查找JSON代码块
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', llm_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 查找纯JSON对象
                json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    raise ValueError("未找到JSON格式的评估结果")
            
            result = json.loads(json_str)
            
            # 确保所有必需字段存在
            # 如果模型返回了分数，转换为等级；否则直接使用等级
            overall_score = result.get("overall_score", 0)
            grade = result.get("grade", "")
            
            # 如果没有等级但有分数，根据分数计算等级
            if not grade and overall_score > 0:
                if overall_score >= 90:
                    grade = "优秀"
                elif overall_score >= 80:
                    grade = "良好"
                elif overall_score >= 70:
                    grade = "中等"
                elif overall_score >= 60:
                    grade = "及格"
                else:
                    grade = "不及格"
            
            # 如果没有分数但有等级，根据等级设置一个参考分数（用于排序等）
            if overall_score == 0 and grade:
                score_map = {
                    "优秀": 92,
                    "良好": 85,
                    "中等": 75,
                    "及格": 65,
                    "不及格": 50
                }
                overall_score = score_map.get(grade, 0)

            formatted_result = {
                "overall_score": overall_score,
                "grade": grade,
                "strengths": result.get("strengths", []),
                "weaknesses": result.get("weaknesses", []),
                "suggestions": result.get("suggestions", []),
                "detailed_analysis": result.get("detailed_analysis", ""),
                "evaluation_date": datetime.utcnow().isoformat()
            }

            return formatted_result
            
        except Exception as e:
            logger.warning(f"解析LLM响应失败，使用默认格式: {e}")
            # 如果解析失败，返回一个基于文本的评估结果
            return {
                "overall_score": 0,
                "strengths": [],
                "weaknesses": [],
                "suggestions": [],
                "detailed_analysis": llm_response,
                "evaluation_date": datetime.utcnow().isoformat(),
                "parse_error": str(e)
            }
    
    async def _save_evaluation_history(
        self,
        system_id: str,
        user_id: str,
        trading_system: TradingSystem,
        evaluation_result: Dict[str, Any]
    ) -> str:
        """保存评估历史记录
        
        Args:
            system_id: 交易计划ID
            user_id: 用户ID
            trading_system: 交易计划对象
            evaluation_result: 评估结果
            
        Returns:
            评估记录ID
        """
        try:
            from bson import ObjectId
            from app.utils.timezone import now_tz
            
            evaluation_record = {
                "evaluation_id": str(ObjectId()),
                "system_id": system_id,
                "user_id": user_id,
                "system_name": trading_system.name,
                "system_version": getattr(trading_system, 'version', '1.0.0'),
                "evaluation_result": evaluation_result,
                "created_at": now_tz(),
                "updated_at": now_tz()
            }
            
            await self.db.trading_system_evaluations.insert_one(evaluation_record)
            logger.info(f"评估历史记录已保存: evaluation_id={evaluation_record['evaluation_id']}")
            
            return evaluation_record["evaluation_id"]
            
        except Exception as e:
            logger.error(f"保存评估历史记录失败: {e}", exc_info=True)
            # 不抛出异常，评估仍然可以继续
            return ""
    
    async def get_evaluation_history(
        self,
        system_id: str,
        user_id: str,
        page: int = 1,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """获取评估历史记录列表
        
        Args:
            system_id: 交易计划ID
            user_id: 用户ID
            page: 页码
            page_size: 每页数量
            
        Returns:
            {
                "items": List[Dict],  # 评估记录列表
                "total": int,  # 总记录数
                "page": int,  # 当前页码
                "page_size": int  # 每页数量
            }
        """
        try:
            skip = (page - 1) * page_size
            
            # 查询评估记录
            query = {
                "system_id": system_id,
                "user_id": user_id
            }
            
            # 获取总数
            total = await self.db.trading_system_evaluations.count_documents(query)
            
            # 获取列表
            cursor = self.db.trading_system_evaluations.find(query).sort("created_at", -1).skip(skip).limit(page_size)
            records = await cursor.to_list(None)
            
            # 格式化结果
            items = []
            for record in records:
                eval_result = record.get("evaluation_result", {})
                overall_score = eval_result.get("overall_score", 0)
                
                # 如果没有grade字段，根据分数计算
                grade = eval_result.get("grade", "")
                if not grade:
                    if overall_score >= 90:
                        grade = "优秀"
                    elif overall_score >= 80:
                        grade = "良好"
                    elif overall_score >= 70:
                        grade = "中等"
                    elif overall_score >= 60:
                        grade = "及格"
                    else:
                        grade = "不及格"
                
                items.append({
                    "evaluation_id": record.get("evaluation_id"),
                    "system_id": record.get("system_id"),
                    "system_name": record.get("system_name"),
                    "system_version": record.get("system_version"),
                    "overall_score": overall_score,
                    "grade": grade,
                    "created_at": record.get("created_at").isoformat() if record.get("created_at") else None,
                    "summary": eval_result.get("detailed_analysis", "")[:200] + "..." if len(eval_result.get("detailed_analysis", "")) > 200 else eval_result.get("detailed_analysis", "")
                })
            
            return {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size
            }
            
        except Exception as e:
            logger.error(f"获取评估历史记录失败: {e}", exc_info=True)
            return {
                "items": [],
                "total": 0,
                "page": page,
                "page_size": page_size
            }
    
    async def get_evaluation_detail(
        self,
        evaluation_id: str,
        user_id: str
    ) -> Optional[Dict[str, Any]]:
        """获取评估详情
        
        Args:
            evaluation_id: 评估记录ID
            user_id: 用户ID
            
        Returns:
            评估详情，如果不存在返回None
        """
        try:
            record = await self.db.trading_system_evaluations.find_one({
                "evaluation_id": evaluation_id,
                "user_id": user_id
            })
            
            if not record:
                return None
            
            return {
                "evaluation_id": record.get("evaluation_id"),
                "system_id": record.get("system_id"),
                "system_name": record.get("system_name"),
                "system_version": record.get("system_version"),
                "evaluation_result": record.get("evaluation_result", {}),
                "created_at": record.get("created_at").isoformat() if record.get("created_at") else None
            }
            
        except Exception as e:
            logger.error(f"获取评估详情失败: {e}", exc_info=True)
            return None


# 全局服务实例
_trading_plan_evaluation_service = None


def get_trading_plan_evaluation_service() -> TradingPlanEvaluationService:
    """获取交易计划评估服务实例"""
    global _trading_plan_evaluation_service
    if _trading_plan_evaluation_service is None:
        _trading_plan_evaluation_service = TradingPlanEvaluationService()
    return _trading_plan_evaluation_service

