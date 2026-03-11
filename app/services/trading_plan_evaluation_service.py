"""
交易计划AI评估服务
使用AI评估用户制定的交易计划的优缺点
"""

import logging
import json
import re
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.core.database import get_mongo_db
from app.models.trading_system import TradingSystem
from app.services.unified_analysis_engine import UnifiedAnalysisEngine
from app.utils.api_key_utils import truncate_api_key

logger = logging.getLogger(__name__)


class TradingPlanEvaluationService:
    """交易计划评估服务"""

    def __init__(self):
        self.db = get_mongo_db()
        self.analysis_engine = UnifiedAnalysisEngine()

    def _dump_trading_system_for_log(self, trading_system: TradingSystem) -> str:
        """生成评估输入快照，便于核对实际送审内容。"""
        try:
            if hasattr(trading_system, "dict"):
                payload = trading_system.dict()
            else:
                payload = dict(trading_system)
            return json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.warning(f"生成交易计划日志快照失败: {e}")
            return str(trading_system)

    def _log_evaluation_prompt(
        self,
        *,
        stage: str,
        user_id: str,
        system_id: Optional[str],
        trading_system: Optional[TradingSystem] = None,
        prompt: Optional[str] = None,
    ) -> None:
        """打印评估输入与提示词，便于排查前端内容和最终送给 LLM 的文本。"""
        logger.info(
            "\n===== [交易计划评估调试][%s] user_id=%s system_id=%s =====",
            stage,
            user_id,
            system_id or "draft",
        )
        if trading_system is not None:
            logger.info(
                "[交易计划评估调试][%s] 输入快照:\n%s",
                stage,
                self._dump_trading_system_for_log(trading_system),
            )
        if prompt is not None:
            logger.info("[交易计划评估调试][%s] Prompt全文:\n%s", stage, prompt)
        logger.info("===== [交易计划评估调试][%s] 结束 =====", stage)

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

    async def generate_risk_management_rules(
        self,
        user_id: str,
        style: str,
        risk_profile: str,
        description: str = "",
        current_rules: Optional[Dict[str, Any]] = None,
        risk_style: str = "balanced"
    ) -> Dict[str, Any]:
        """AI生成风险管理规则（止损/止盈/时间止损/逻辑止损）"""
        try:
            risk_style_map = {
                "conservative": "稳健风格：优先控制回撤，止损更严格，分批止盈更早落袋。",
                "balanced": "平衡风格：收益与风险并重，止损止盈参数居中。",
                "aggressive": "激进风格：允许更大波动，止损较宽，止盈更注重趋势延伸。"
            }

            prompt = f"""你是一位交易风控专家。请根据用户交易风格与风险偏好，生成可执行的风险管理规则。

输出必须是JSON对象，且仅包含以下字段：
{{
  "stop_loss": {{
    "type": "percentage|technical|atr",
    "percentage": 0.08,
    "description": "可选，技术位止损说明",
    "atr_multiplier": 2.0
  }},
  "take_profit": {{
    "type": "percentage|trailing|scaled",
    "percentage": 0.2,
    "trailing_pullback_pct": 0.08,
    "activation_profit_pct": 0.1,
    "reference": "highest_price|ma5|ma10|atr",
    "levels": [
      {{"target_profit_pct": 0.2, "sell_ratio": 0.3}},
      {{"target_profit_pct": 0.35, "sell_ratio": 0.3}},
      {{"target_profit_pct": 0.5, "sell_ratio": 0.4}}
    ]
  }},
  "time_stop": {{
    "enabled": true,
    "max_holding_days": 30
  }},
  "logical_stop": {{
    "conditions": ["条件1", "条件2"]
  }}
}}

约束：
1. 所有百分比字段使用0-1小数（例如8%写0.08）。
2. 如果take_profit.type是scaled，levels里sell_ratio总和必须<=1。
3. 数值务实可执行，避免极端值。

风格偏好：{risk_style_map.get(risk_style, risk_style_map['balanced'])}

用户输入：
- 交易风格: {style}
- 风险偏好: {risk_profile}
- 系统描述: {description or '无'}
- 当前风险规则: {json.dumps(current_rules or {}, ensure_ascii=False)}
"""

            content = await self._call_llm_json_generation(prompt, user_id, temperature=0.2)
            result = self._extract_json_object(content)
            return self._normalize_risk_management_rules(result)
        except Exception as e:
            logger.error(f"生成风险管理规则失败: {e}", exc_info=True)
            return self._normalize_risk_management_rules(current_rules or {})

    async def generate_module_rules(
        self,
        user_id: str,
        module: str,
        style: str,
        risk_profile: str,
        description: str = "",
        current_rules: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """AI生成结构化模块规则。"""
        current_rules = current_rules or {}

        if module == "stock_selection":
            return await self.generate_stock_selection_rules(
                user_id=user_id,
                style=style,
                risk_profile=risk_profile,
                description=description,
                current_rules=current_rules
            )

        if module == "timing":
            return await self.generate_timing_rules(
                user_id=user_id,
                style=style,
                risk_profile=risk_profile,
                description=description,
                current_rules=current_rules
            )

        if module == "risk_management":
            return await self.generate_risk_management_rules(
                user_id=user_id,
                style=style,
                risk_profile=risk_profile,
                description=description,
                current_rules=current_rules
            )

        raise ValueError(f"不支持的规则模块: {module}")

    async def generate_stock_selection_rules(
        self,
        user_id: str,
        style: str,
        risk_profile: str,
        description: str = "",
        current_rules: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """AI生成选股规则。"""
        try:
            prompt = f"""你是一位资深A股交易系统设计师。请根据用户交易风格、风险偏好与系统描述，补强并细化当前选股规则，而不是简单改写成更泛化的版本。

请只输出 JSON 对象，格式如下：
{{
  "must_have": [
    {{"rule": "规则名称或阈值", "description": "为什么要这样筛选"}}
  ],
  "exclude": [
    {{"rule": "排除项", "description": "为什么要排除"}}
  ],
  "bonus": [
    {{"rule": "加分项", "description": "为什么是加分项"}}
  ]
}}

约束：
1. must_have 建议 4-6 条，exclude 建议 2-4 条，bonus 建议 2-4 条。
2. 规则要具体可执行，尽量量化，不要泛泛而谈。
3. 输出字段只允许 must_have、exclude、bonus。
4. 每个数组元素只保留 rule 和 description 两个字段。
5. 如果当前规则里已有较好的条件，优先保留并升级它们，不要降级成更模糊的表述。
6. 必须体现“硬过滤 + 排除项 + 加分项”的完整结构。

用户输入：
- 交易风格: {style}
- 风险偏好: {risk_profile}
- 系统描述: {description or '无'}
- 当前选股规则: {json.dumps(current_rules or {}, ensure_ascii=False)}
"""

            content = await self._call_llm_json_generation(prompt, user_id, temperature=0.3)
            result = self._extract_json_object(content)
            return self._normalize_stock_selection_rules(result)
        except Exception as e:
            logger.error(f"生成选股规则失败: {e}", exc_info=True)
            return self._normalize_stock_selection_rules(current_rules or {})

    async def generate_timing_rules(
        self,
        user_id: str,
        style: str,
        risk_profile: str,
        description: str = "",
        current_rules: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """AI生成择时规则。"""
        try:
            prompt = f"""你是一位资深A股择时交易顾问。请根据用户交易风格、风险偏好与系统描述，补强并细化当前择时规则，而不是只给几个泛泛的入场标签。

请只输出 JSON 对象，格式如下：
{{
    "market_condition": {{"rule": "市场环境", "description": "适合入场的大盘/情绪/趋势条件"}},
    "entry_signals": [
        {{"signal": "信号类型或条件名", "condition": "具体触发条件，尽量详细"}}
    ],
    "confirmation": [
        {{"rule": "确认条件", "description": "二次确认条件，避免假突破"}}
    ]
}}

约束：
1. entry_signals 建议 4-6 条。
2. signal 适合填写短标签，如“市场环境”“技术位置”“资金认可”。
3. condition 适合填写详细触发条件，尽量量化。
4. confirmation 建议 2-4 条。
5. 输出字段只允许 market_condition、entry_signals、confirmation。
6. signal 只适合短标签；真正的触发逻辑写在 condition。
7. 如果当前规则里已有较好的条件，优先保留并升级它们，不要降级成更模糊的表述。

用户输入：
- 交易风格: {style}
- 风险偏好: {risk_profile}
- 系统描述: {description or '无'}
- 当前择时规则: {json.dumps(current_rules or {}, ensure_ascii=False)}
"""

            content = await self._call_llm_json_generation(prompt, user_id, temperature=0.3)
            result = self._extract_json_object(content)
            return self._normalize_timing_rules(result)
        except Exception as e:
            logger.error(f"生成择时规则失败: {e}", exc_info=True)
            return self._normalize_timing_rules(current_rules or {})

    async def discuss_optimization_suggestions(
        self,
        user_id: str,
        trading_plan_data: Dict[str, Any],
        evaluation_result: Optional[Dict[str, Any]] = None,
        user_question: str = "",
        selected_suggestions: Optional[List[str]] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """围绕评估建议与用户进行讨论，并返回可选择应用的结构化更新。"""
        try:
            trading_system = TradingSystem(**trading_plan_data)
            plan_text = self._format_trading_plan_for_evaluation(trading_system)
            evaluation_summary = self._build_evaluation_summary(evaluation_result or {})

            selected_suggestions = [item for item in (selected_suggestions or []) if str(item).strip()]
            conversation_history = conversation_history or []
            history_text = "\n".join([
                f"- {str(item.get('role', 'assistant'))}: {str(item.get('content', ''))}"
                for item in conversation_history[-6:]
                if isinstance(item, dict) and str(item.get('content', '')).strip()
            ]) or "无"

            prompt = f"""你是一位资深交易系统优化顾问。你的任务分两步：
1. 回答用户关于“这些优化建议会提升哪些地方、为什么、如何取舍”的问题。
2. 给出可直接应用到当前交易计划中的结构化修改候选，供前端勾选后合并。

请只输出 JSON 对象，不要输出任何额外说明。

允许修改的模块只有：stock_selection、timing、position、holding、risk_management、review、discipline。

输出格式：
{{
    "reply": "用中文直接回答用户问题，说明会提升哪些维度、为什么值得改、适合什么风格。",
    "updates": [
        {{
            "id": "update_1",
            "module": "risk_management",
            "title": "增加移动止盈",
            "summary": "一句话说明会改什么",
            "reason": "说明为什么这样改、会改善哪些问题",
            "expected_improvements": ["风险控制", "可执行性"],
            "patch": {{
                "risk_management": {{
                    "take_profit": {{
                        "type": "trailing",
                        "trailing_pullback_pct": 0.08,
                        "activation_profit_pct": 0.12,
                        "reference": "highest_price"
                    }}
                }}
            }}
        }}
    ]
}}

约束：
1. updates 最多返回 4 条，每条只修改一个 module。
2. patch 必须是“可直接合并”的 JSON 片段，只放需要更新的字段。
3. 不要删除用户已有大段配置，优先补充缺失字段或增强现有规则。
4. 百分比统一用 0-1 小数。
5. 如果是分批止盈，sell_ratio 总和必须 <= 1。
6. 如果用户问题偏解释性，也尽量给出 1-3 条可选更新。

当前交易计划：
系统名称：{trading_system.name}
交易风格：{trading_system.style.value}
风险偏好：{trading_system.risk_profile.value}
系统描述：{trading_system.description or '无'}

{plan_text}

已有评估摘要：
{evaluation_summary}

本轮重点建议：
{json.dumps(selected_suggestions, ensure_ascii=False) if selected_suggestions else '[]'}

历史对话：
{history_text}

用户本轮问题：
{user_question or '请解释最值得优先优化的点，并给出可直接应用的修改候选。'}
"""

            content = await self._call_llm_json_generation(prompt, user_id, temperature=0.3)
            result = self._extract_json_object(content)
            return self._normalize_optimization_response(result)
        except Exception as e:
            logger.error(f"优化讨论生成失败: {e}", exc_info=True)
            fallback_suggestions = selected_suggestions or (evaluation_result or {}).get("suggestions", []) or []
            return {
                "reply": "本轮讨论暂时未生成结构化修改。我建议先从风险控制和可执行性最弱的项入手，优先补齐止盈止损、排除条件和复盘指标。",
                "updates": [
                    {
                        "id": f"fallback_{index + 1}",
                        "module": "risk_management",
                        "title": "优先处理建议",
                        "summary": suggestion,
                        "reason": "LLM 未返回可应用补丁，先保留建议说明。",
                        "expected_improvements": ["风险控制", "可执行性"],
                        "patch": {}
                    }
                    for index, suggestion in enumerate(fallback_suggestions[:2])
                ]
            }
    
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
            self._log_evaluation_prompt(
                stage="build_evaluation_prompt",
                user_id=user_id,
                system_id=system_id,
                trading_system=trading_system,
                prompt=prompt,
            )
            
            # 调用LLM进行评估
            evaluation_result = await self._call_llm_evaluation(prompt, user_id, system_id=system_id)
            
            # 解析和格式化结果
            formatted_result = self._format_evaluation_result(evaluation_result)
            formatted_result = self._apply_risk_rule_grade_adjustment(
                trading_system=trading_system,
                evaluation_result=formatted_result
            )
            
            # 保存评估历史记录（如果有system_id）
            if system_id:
                evaluation_id = await self._save_evaluation_history(
                    system_id=system_id,
                    user_id=user_id,
                    trading_system=trading_system,
                    evaluation_result=formatted_result
                )
                formatted_result["evaluation_id"] = evaluation_id
            
            logger.info(f"交易计划评估完成: {plan_name}, 等级: {formatted_result.get('grade', '未评价')}")
            
            return formatted_result
            
        except Exception as e:
            logger.error(f"评估交易计划失败: {e}", exc_info=True)
            raise

    def _apply_risk_rule_grade_adjustment(
        self,
        trading_system: TradingSystem,
        evaluation_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """根据风险管理规则完整度对最终等级做轻量校准。"""
        grade = evaluation_result.get("grade", "中等")
        score = self._grade_to_score(grade)
        delta, reason = self._assess_risk_rule_quality(trading_system.risk_management)

        adjusted_score = max(0, min(100, score + delta))
        adjusted_grade = self._score_to_grade(adjusted_score)
        evaluation_result["grade"] = adjusted_grade
        evaluation_result["risk_rule_adjustment"] = {
            "before_grade": grade,
            "before_score": score,
            "delta": delta,
            "after_grade": adjusted_grade,
            "after_score": adjusted_score,
            "reason": reason
        }

        dimension_scores = evaluation_result.get("dimension_scores", self._default_dimension_scores())
        if isinstance(dimension_scores, dict):
            adjusted_risk_score = max(0, min(10, float(dimension_scores.get("risk_control", 7.5)) + delta / 4))
            dimension_scores["risk_control"] = round(adjusted_risk_score, 1)
            evaluation_result["dimension_scores"] = dimension_scores

        if reason:
            suggestions = evaluation_result.get("suggestions", [])
            if isinstance(suggestions, list):
                suggestions.append(f"风险规则校准建议：{reason}")
                evaluation_result["suggestions"] = suggestions

        return evaluation_result

    def _grade_to_score(self, grade: str) -> int:
        mapping = {
            "优秀": 92,
            "良好": 85,
            "中等": 75,
            "及格": 65,
            "不及格": 50
        }
        return mapping.get(grade, 75)

    def _score_to_grade(self, score: int) -> str:
        if score >= 90:
            return "优秀"
        if score >= 80:
            return "良好"
        if score >= 70:
            return "中等"
        if score >= 60:
            return "及格"
        return "不及格"

    def _assess_risk_rule_quality(self, risk_mgmt: Any) -> tuple[int, str]:
        """返回(分值调整, 建议文本)。"""
        delta = 0
        notes = []

        stop_loss = getattr(risk_mgmt, "stop_loss", {}) or {}
        take_profit = getattr(risk_mgmt, "take_profit", {}) or {}
        time_stop = getattr(risk_mgmt, "time_stop", {}) or {}
        logical_stop = getattr(risk_mgmt, "logical_stop", {}) or {}

        stop_type = stop_loss.get("type")
        if stop_type in {"percentage", "technical", "atr"}:
            delta += 2
        else:
            notes.append("补充明确的止损类型")

        take_type = take_profit.get("type")
        if take_type in {"percentage", "trailing", "scaled"}:
            delta += 2
        else:
            notes.append("补充明确的止盈类型")

        if take_type == "scaled":
            levels = take_profit.get("levels", [])
            total_ratio = sum(float(x.get("sell_ratio", 0)) for x in levels) if isinstance(levels, list) else 0
            if isinstance(levels, list) and len(levels) >= 2 and total_ratio <= 1.0001:
                delta += 2
            else:
                delta -= 2
                notes.append("分批止盈建议至少两档且总卖出比例不超过100%")

        if take_type == "trailing":
            if take_profit.get("trailing_pullback_pct") is not None and take_profit.get("activation_profit_pct") is not None:
                delta += 2
            else:
                notes.append("移动止盈建议配置回撤比例和激活盈利阈值")

        if bool(time_stop.get("enabled")) and int(time_stop.get("max_holding_days", 0)) > 0:
            delta += 1

        conditions = logical_stop.get("conditions", [])
        if isinstance(conditions, list) and len([x for x in conditions if str(x).strip()]) > 0:
            delta += 1

        if delta < 2:
            notes.append("风险管理规则仍偏简略，可补充时间止损与逻辑止损")

        # 控制校准幅度，避免覆盖LLM整体判断
        delta = max(-8, min(8, delta - 4))
        reason = "；".join(notes[:2])
        return delta, reason

    def _default_dimension_scores(self) -> Dict[str, float]:
        return {
            "completeness": 7.5,
            "consistency": 7.5,
            "executability": 7.5,
            "risk_control": 7.5,
            "adaptability": 7.5,
            "evolvability": 7.5,
        }

    def _normalize_dimension_scores(
        self,
        dimension_scores: Optional[Dict[str, Any]],
        overall_score: float,
        grade: str
    ) -> Dict[str, float]:
        base_score = round((overall_score / 10), 1) if overall_score else round(self._grade_to_score(grade) / 10, 1)
        defaults = self._default_dimension_scores()
        fallback = {key: base_score for key in defaults}

        if not isinstance(dimension_scores, dict):
            return fallback

        normalized = {}
        for key in defaults:
            try:
                value = float(dimension_scores.get(key, fallback[key]))
            except (TypeError, ValueError):
                value = fallback[key]
            normalized[key] = round(max(0, min(10, value)), 1)
        return normalized

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
    "dimension_scores": {{
        "completeness": 8.5,
        "consistency": 8.0,
        "executability": 8.0,
        "risk_control": 7.5,
        "adaptability": 7.0,
        "evolvability": 8.0
    }},
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
5. dimension_scores 的每一项为 0-10 分，保留一位小数
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
                signal_name = signal.get('signal', '')
                signal_detail = signal.get('condition') or signal.get('description', '')
                lines.append(f"  {i}. {signal_name}: {signal_detail}")
        if timing.confirmation:
            lines.append(f"- 确认条件：{len(timing.confirmation)}条")
            for i, item in enumerate(timing.confirmation[:3], 1):
                lines.append(f"  {i}. {item.get('rule', '')}: {item.get('description', '')}")
        
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

    async def _call_llm_evaluation(self, prompt: str, user_id: str, system_id: Optional[str] = None) -> str:
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
                logger.info(f"🔑 [交易计划评估] API Key: {truncate_api_key(api_key)}")
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
- dimension_scores: 六维评分对象（completeness, consistency, executability, risk_control, adaptability, evolvability，0-10）
- grade: 等级（优秀/良好/中等/及格/不及格）
- strengths: 优点列表（数组）
- weaknesses: 缺点列表（数组）
- suggestions: 改进建议列表（数组）
- detailed_analysis: 详细分析（字符串，300-500字）

交易计划内容：
{prompt}
"""
            self._log_evaluation_prompt(
                stage="final_full_prompt",
                user_id=user_id,
                system_id=system_id,
                prompt=full_prompt,
            )
            
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

    async def _call_llm_json_generation(self, prompt: str, user_id: str, temperature: float = 0.2) -> str:
        """调用LLM生成结构化JSON"""
        try:
            from app.services.config_provider import ConfigProvider
            from app.services.simple_analysis_service import get_provider_and_url_by_model_sync
            from tradingagents.graph.trading_graph import create_llm_by_provider

            config_provider = ConfigProvider()
            system_settings = await config_provider.get_effective_system_settings()
            deep_model = system_settings.get("deep_analysis_model") or system_settings.get("default_model", "qwen-plus")
            provider_info = get_provider_and_url_by_model_sync(deep_model)

            if not provider_info.get("backend_url"):
                raise ValueError(f"模型 {deep_model} 的API地址未配置，请在设置页面配置")

            llm = create_llm_by_provider(
                provider=provider_info.get("provider", "dashscope"),
                model=deep_model,
                backend_url=provider_info.get("backend_url"),
                temperature=temperature,
                max_tokens=3000,
                timeout=120,
                api_key=provider_info.get("api_key")
            )

            logger.info(f"🛡️ [风险规则生成] 开始调用LLM，Prompt长度: {len(prompt)} 字符")
            response = await llm.ainvoke(prompt)

            if hasattr(response, 'content'):
                return response.content
            if isinstance(response, str):
                return response
            return str(response)
        except Exception as e:
            logger.error(f"调用LLM生成风险规则失败: {e}", exc_info=True)
            raise

    def _extract_json_object(self, llm_response: str) -> Dict[str, Any]:
        """从LLM响应中提取JSON对象"""
        json_match = re.search(r'```json\s*(\{[\s\S]*?\})\s*```', llm_response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_match = re.search(r'\{[\s\S]*\}', llm_response)
            if not json_match:
                raise ValueError("未找到JSON对象")
            json_str = json_match.group(0)

        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            json_str_cleaned = json_str.rstrip()
            json_str_cleaned = re.sub(r',\s*([}\]])', r'\1', json_str_cleaned)
            return json.loads(json_str_cleaned)

    def _normalize_risk_management_rules(self, rules: Dict[str, Any]) -> Dict[str, Any]:
        """标准化风险管理规则结构并做安全兜底"""
        rules = rules or {}
        stop_loss = rules.get("stop_loss") or {}
        take_profit = rules.get("take_profit") or {}
        time_stop = rules.get("time_stop") or {}
        logical_stop = rules.get("logical_stop") or {}

        normalized = {
            "stop_loss": {
                "type": stop_loss.get("type", "percentage"),
                "percentage": float(stop_loss.get("percentage", 0.08))
            },
            "take_profit": {
                "type": take_profit.get("type", "percentage"),
                "percentage": float(take_profit.get("percentage", 0.2))
            },
            "time_stop": {
                "enabled": bool(time_stop.get("enabled", False)),
                "max_holding_days": int(time_stop.get("max_holding_days", 30))
            },
            "logical_stop": {
                "conditions": logical_stop.get("conditions", []) if isinstance(logical_stop.get("conditions", []), list) else []
            }
        }

        if normalized["stop_loss"]["type"] == "technical":
            normalized["stop_loss"]["description"] = stop_loss.get("description", "跌破关键支撑位且收盘确认")
        if normalized["stop_loss"]["type"] == "atr":
            normalized["stop_loss"]["atr_multiplier"] = float(stop_loss.get("atr_multiplier", 2.0))

        if normalized["take_profit"]["type"] == "scaled":
            normalized["take_profit"]["levels"] = take_profit.get("levels", [])
            levels = normalized["take_profit"]["levels"]
            if not isinstance(levels, list) or len(levels) == 0:
                levels = [
                    {"target_profit_pct": 0.2, "sell_ratio": 0.3},
                    {"target_profit_pct": 0.35, "sell_ratio": 0.3},
                    {"target_profit_pct": 0.5, "sell_ratio": 0.4}
                ]
            safe_levels = []
            total_ratio = 0.0
            for item in levels:
                target = float(item.get("target_profit_pct", 0.2))
                ratio = float(item.get("sell_ratio", 0.2))
                ratio = max(0.0, min(ratio, 1.0 - total_ratio))
                total_ratio += ratio
                safe_levels.append({"target_profit_pct": target, "sell_ratio": round(ratio, 4)})
                if total_ratio >= 1.0:
                    break
            normalized["take_profit"]["levels"] = safe_levels

        if normalized["take_profit"]["type"] == "trailing":
            normalized["take_profit"]["trailing_pullback_pct"] = float(take_profit.get("trailing_pullback_pct", 0.08))
            normalized["take_profit"]["activation_profit_pct"] = float(take_profit.get("activation_profit_pct", 0.1))
            normalized["take_profit"]["reference"] = take_profit.get("reference", "highest_price")

        return normalized

    def _normalize_stock_selection_rules(self, rules: Dict[str, Any]) -> Dict[str, Any]:
        """标准化选股规则结构。"""
        rules = rules or {}

        def normalize_rule_list(items: Any) -> List[Dict[str, str]]:
            if not isinstance(items, list):
                return []
            normalized_items = []
            for item in items:
                if isinstance(item, dict):
                    rule = str(item.get("rule") or item.get("name") or item.get("condition") or "").strip()
                    description = str(item.get("description") or item.get("reason") or "").strip()
                else:
                    rule = str(item).strip()
                    description = ""
                if rule:
                    normalized_items.append({"rule": rule, "description": description})
            return normalized_items

        return {
            "must_have": normalize_rule_list(rules.get("must_have")),
            "exclude": normalize_rule_list(rules.get("exclude")),
            "bonus": normalize_rule_list(rules.get("bonus"))
        }

    def _normalize_timing_rules(self, rules: Dict[str, Any]) -> Dict[str, Any]:
        """标准化择时规则结构。"""
        rules = rules or {}
        entry_signals = rules.get("entry_signals")
        market_condition = rules.get("market_condition") or {}
        confirmation = rules.get("confirmation")
        normalized_entry_signals = []
        normalized_confirmation = []

        if isinstance(entry_signals, list):
            for item in entry_signals:
                if isinstance(item, dict):
                    signal = str(item.get("signal") or item.get("rule") or item.get("name") or "").strip()
                    condition = str(item.get("condition") or item.get("description") or "").strip()
                else:
                    signal = str(item).strip()
                    condition = ""

                if signal or condition:
                    normalized_entry_signals.append({
                        "signal": signal,
                        "condition": condition
                    })

        if isinstance(confirmation, list):
            for item in confirmation:
                if isinstance(item, dict):
                    rule = str(item.get("rule") or item.get("name") or "").strip()
                    description = str(item.get("description") or item.get("condition") or "").strip()
                else:
                    rule = str(item).strip()
                    description = ""

                if rule or description:
                    normalized_confirmation.append({
                        "rule": rule,
                        "description": description
                    })

        return {
            "market_condition": {
                "rule": str(market_condition.get("rule") or market_condition.get("name") or "市场环境").strip() or "市场环境",
                "description": str(market_condition.get("description") or market_condition.get("condition") or "").strip()
            },
            "entry_signals": normalized_entry_signals,
            "confirmation": normalized_confirmation
        }

    def _build_evaluation_summary(self, evaluation_result: Dict[str, Any]) -> str:
        """将评估结果转为更适合继续讨论的摘要文本。"""
        if not isinstance(evaluation_result, dict) or not evaluation_result:
            return "无"

        lines = []
        grade = evaluation_result.get("grade")
        if grade:
            lines.append(f"- 总体等级：{grade}")

        dimension_scores = evaluation_result.get("dimension_scores") or {}
        if isinstance(dimension_scores, dict) and dimension_scores:
            sorted_scores = sorted(
                dimension_scores.items(),
                key=lambda item: float(item[1] if item[1] is not None else 0)
            )
            weakest = [f"{key}:{float(score):.1f}" for key, score in sorted_scores[:3]]
            lines.append(f"- 偏弱维度：{', '.join(weakest)}")

        weaknesses = evaluation_result.get("weaknesses") or []
        if isinstance(weaknesses, list) and weaknesses:
            lines.append("- 主要短板：")
            lines.extend([f"  - {item}" for item in weaknesses[:4]])

        suggestions = evaluation_result.get("suggestions") or []
        if isinstance(suggestions, list) and suggestions:
            lines.append("- 改进建议：")
            lines.extend([f"  - {item}" for item in suggestions[:5]])

        return "\n".join(lines) if lines else "无"

    def _normalize_optimization_response(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """标准化优化讨论结果，确保前端可安全应用。"""
        allowed_modules = {
            "stock_selection",
            "timing",
            "position",
            "holding",
            "risk_management",
            "review",
            "discipline"
        }

        reply = str(result.get("reply") or "").strip()
        raw_updates = result.get("updates") if isinstance(result.get("updates"), list) else []
        normalized_updates = []

        for index, item in enumerate(raw_updates, 1):
            if not isinstance(item, dict):
                continue

            module = str(item.get("module") or "").strip()
            if module not in allowed_modules:
                continue

            patch = item.get("patch") or {}
            if not isinstance(patch, dict):
                continue

            if module in patch:
                module_patch = patch.get(module)
            elif not any(key in allowed_modules for key in patch.keys()):
                module_patch = patch
            else:
                module_patch = None

            if not isinstance(module_patch, dict):
                continue

            expected_improvements = item.get("expected_improvements")
            if not isinstance(expected_improvements, list):
                expected_improvements = []

            normalized_updates.append({
                "id": str(item.get("id") or f"update_{index}"),
                "module": module,
                "title": str(item.get("title") or f"优化{index}"),
                "summary": str(item.get("summary") or ""),
                "reason": str(item.get("reason") or ""),
                "expected_improvements": [str(label) for label in expected_improvements if str(label).strip()],
                "patch": {
                    module: module_patch
                }
            })

        if not reply:
            reply = "我已经结合当前计划整理出可以直接落地的优化项。你可以先看每条建议预计提升的维度，再勾选需要应用的部分。"

        return {
            "reply": reply,
            "updates": normalized_updates[:4]
        }

    def _format_evaluation_result(self, llm_response: str) -> Dict[str, Any]:
        """解析和格式化LLM返回的评估结果"""
        
        try:
            # 尝试提取JSON
            import re
            
            # 查找JSON代码块 - 使用更健壮的方式
            json_str = None
            
            # 方式1: 查找```json...```代码块
            json_match = re.search(r'```json\s*(\{[\s\S]*?\})\s*```', llm_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                logger.debug(f"通过JSON代码块提取到JSON")
            else:
                # 方式2: 查找纯JSON对象 - 使用非贪心匹配，从首个{开始
                json_match = re.search(r'\{[\s\S]*\}', llm_response)
                if json_match:
                    json_str = json_match.group(0)
                    logger.debug(f"通过正则表达式提取到JSON")
            
            if not json_str:
                raise ValueError("未找到JSON格式的评估结果")
            
            # 调试日志：记录提取的JSON长度和前100字符
            logger.debug(f"提取的JSON长度: {len(json_str)}, 内容预览: {json_str[:100]}")
            
            try:
                result = json.loads(json_str)
            except json.JSONDecodeError as je:
                # 提供更详细的错误信息，帮助调试
                logger.error(f"JSON解析失败 - 行:{je.lineno} 列:{je.colno} 消息:{je.msg}")
                logger.error(f"JSON内容（长度{len(json_str)}）: {json_str}")
                # 尝试清理可能的问题：去除尾部的非JSON字符或不完整的结构
                json_str_cleaned = json_str.rstrip()
                # 处理可能的尾部逗号问题
                if json_str_cleaned.endswith(',}'):
                    json_str_cleaned = json_str_cleaned[:-2] + '}'
                elif json_str_cleaned.endswith(',]'):
                    json_str_cleaned = json_str_cleaned[:-2] + ']'
                try:
                    result = json.loads(json_str_cleaned)
                    logger.info("通过清理JSON成功解析")
                except json.JSONDecodeError:
                    raise je  # 如果清理后仍失败，抛出原始异常
            
            
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
            
            # 如果没有分数但有等级，根据等级设置一个参考分数（用于结构化展示）
            if overall_score == 0 and grade:
                score_map = {
                    "优秀": 92,
                    "良好": 85,
                    "中等": 75,
                    "及格": 65,
                    "不及格": 50
                }
                overall_score = score_map.get(grade, 0)

            dimension_scores = self._normalize_dimension_scores(
                result.get("dimension_scores"),
                overall_score,
                grade
            )

            formatted_result = {
                "grade": grade,
                "dimension_scores": dimension_scores,
                "strengths": result.get("strengths", []),
                "weaknesses": result.get("weaknesses", []),
                "suggestions": result.get("suggestions", []),
                "detailed_analysis": result.get("detailed_analysis", ""),
                "evaluation_date": datetime.utcnow().isoformat()
            }

            return formatted_result
            
        except json.JSONDecodeError as je:
            logger.warning(f"解析LLM响应JSONDecodeError: 行{je.lineno} 列{je.colno} - {je.msg}")
            # 如果解析失败，返回一个基于文本的评估结果
            return {
                "grade": "中等",
                "dimension_scores": self._default_dimension_scores(),
                "strengths": [],
                "weaknesses": [],
                "suggestions": [],
                "detailed_analysis": llm_response,
                "evaluation_date": datetime.utcnow().isoformat(),
                "parse_error": f"JSONDecodeError: {je.msg} at line {je.lineno}"
            }
        except Exception as e:
            logger.warning(f"解析LLM响应失败，使用默认格式: {e}")
            # 如果解析失败，返回一个基于文本的评估结果
            return {
                "grade": "中等",
                "dimension_scores": self._default_dimension_scores(),
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
                
                # 获取grade，如果没有则使用默认值
                grade = eval_result.get("grade", "未评价")
                
                items.append({
                    "evaluation_id": record.get("evaluation_id"),
                    "system_id": record.get("system_id"),
                    "system_name": record.get("system_name"),
                    "system_version": record.get("system_version"),
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

