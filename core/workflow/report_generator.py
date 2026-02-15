"""
通用报告生成器

根据报告模板和 Agent 输出，生成结构化报告。
支持 LLM 辅助生成和规则提取两种模式。

使用流程：
1. 工作流执行完成，收集所有 Agent 输出
2. 根据 workflow_id 获取关联的报告模板
3. 调用报告生成器生成结构化报告
4. 保存报告到 analysis_reports 集合
"""
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class ReportGenerator:
    """
    通用报告生成器
    
    支持两种生成模式：
    1. LLM 生成：使用报告模板的 generator_prompt 调用 LLM 生成报告
    2. 规则提取：从 Agent 输出中按规则提取字段
    """
    
    def __init__(self, db=None):
        """
        初始化报告生成器
        
        Args:
            db: MongoDB 数据库连接（可选，用于获取报告模板）
        """
        self.db = db
        self._templates_cache: Dict[str, Any] = {}
    
    async def get_template(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """
        获取工作流关联的报告模板
        
        Args:
            workflow_id: 工作流ID
            
        Returns:
            报告模板字典，如果没有则返回 None
        """
        # 检查缓存
        if workflow_id in self._templates_cache:
            return self._templates_cache[workflow_id]
        
        if not self.db:
            logger.warning("数据库连接未设置，无法获取报告模板")
            return None
        
        try:
            template = await self.db.report_templates.find_one({
                "workflow_id": workflow_id,
                "status": "active"
            })
            
            if template:
                self._templates_cache[workflow_id] = template
                logger.info(f"✅ 获取报告模板: {template.get('name')} (workflow_id={workflow_id})")
            else:
                logger.info(f"📝 工作流 {workflow_id} 没有关联报告模板，将使用默认格式")
            
            return template
        except Exception as e:
            logger.error(f"❌ 获取报告模板失败: {e}")
            return None
    
    async def generate_report(
        self,
        workflow_id: str,
        agent_outputs: Dict[str, Any],
        workflow_state: Optional[Dict[str, Any]] = None,
        use_llm: bool = True
    ) -> Dict[str, Any]:
        """
        生成报告
        
        Args:
            workflow_id: 工作流ID
            agent_outputs: 各 Agent 的输出字典
            workflow_state: 工作流状态（包含 ticker、context 等）
            use_llm: 是否使用 LLM 生成报告
            
        Returns:
            结构化报告字典
        """
        template = await self.get_template(workflow_id)
        
        if not template:
            # 没有模板，返回原始 Agent 输出
            return self._generate_default_report(agent_outputs, workflow_state)
        
        if use_llm and template.get("generator_prompt"):
            return await self._generate_with_llm(template, agent_outputs, workflow_state)
        else:
            return self._generate_with_rules(template, agent_outputs, workflow_state)
    
    def _generate_default_report(
        self,
        agent_outputs: Dict[str, Any],
        workflow_state: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """生成默认格式报告（无模板时使用）"""
        return {
            "report_type": "default",
            "generated_at": datetime.utcnow().isoformat(),
            "workflow_id": workflow_state.get("workflow_id") if workflow_state else None,
            "ticker": workflow_state.get("ticker") if workflow_state else None,
            "agent_outputs": agent_outputs,
            "summary": self._extract_summary_from_outputs(agent_outputs)
        }
    
    def _extract_summary_from_outputs(self, agent_outputs: Dict[str, Any]) -> str:
        """从 Agent 输出中提取摘要"""
        summaries = []
        for agent_name, output in agent_outputs.items():
            if isinstance(output, dict):
                if "summary" in output:
                    summaries.append(f"【{agent_name}】{output['summary']}")
                elif "conclusion" in output:
                    summaries.append(f"【{agent_name}】{output['conclusion']}")
        return "\n".join(summaries) if summaries else "暂无摘要"
    
    def _generate_with_rules(
        self,
        template: Dict[str, Any],
        agent_outputs: Dict[str, Any],
        workflow_state: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """使用规则从 Agent 输出中提取字段"""
        output_schema = template.get("output_schema", [])
        result = {
            "report_type": template.get("template_id"),
            "template_name": template.get("name"),
            "generated_at": datetime.utcnow().isoformat(),
            "workflow_id": template.get("workflow_id"),
            "ticker": workflow_state.get("ticker") if workflow_state else None,
        }
        
        # 按 output_schema 提取字段
        for field_def in output_schema:
            field_name = field_def.get("name")
            field_type = field_def.get("type", "string")
            default = field_def.get("default")
            
            # 尝试从 agent_outputs 中提取
            value = self._extract_field_value(field_name, agent_outputs, field_type)
            result[field_name] = value if value is not None else default
        
        # 添加原始 agent_outputs（可选，用于调试）
        result["agent_outputs"] = agent_outputs

        return result

    def _extract_field_value(
        self,
        field_name: str,
        agent_outputs: Dict[str, Any],
        field_type: str
    ) -> Any:
        """从 Agent 输出中提取字段值"""
        # 遍历所有 Agent 输出，查找匹配的字段
        for agent_name, output in agent_outputs.items():
            if isinstance(output, dict):
                if field_name in output:
                    return self._convert_type(output[field_name], field_type)
                # 尝试嵌套查找
                for key, value in output.items():
                    if isinstance(value, dict) and field_name in value:
                        return self._convert_type(value[field_name], field_type)
        return None

    def _convert_type(self, value: Any, target_type: str) -> Any:
        """类型转换"""
        try:
            if target_type == "string":
                return str(value) if value is not None else None
            elif target_type == "number":
                return float(value) if value is not None else None
            elif target_type == "boolean":
                return bool(value) if value is not None else None
            elif target_type == "array":
                if isinstance(value, list):
                    return value
                return [value] if value is not None else []
            elif target_type == "object":
                return value if isinstance(value, dict) else {}
            return value
        except (ValueError, TypeError):
            return None

    async def _generate_with_llm(
        self,
        template: Dict[str, Any],
        agent_outputs: Dict[str, Any],
        workflow_state: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """使用 LLM 生成报告"""
        try:
            from core.llm.unified_client import UnifiedLLMClient

            llm_client = UnifiedLLMClient()

            # 构建提示词
            generator_prompt = template.get("generator_prompt", "")
            output_schema = template.get("output_schema", [])

            # 格式化 output_schema 为 JSON Schema 描述
            schema_description = self._format_output_schema(output_schema)

            # 构建完整提示词
            prompt = f"""你是一个专业的金融分析报告生成器。

## 任务
根据以下分析师的分析结果，生成一份结构化的分析报告。

## 分析结果
{json.dumps(agent_outputs, ensure_ascii=False, indent=2)}

## 报告要求
{generator_prompt}

## 输出格式
请按照以下 JSON 格式输出报告：
{schema_description}

## 注意事项
1. 只输出 JSON 格式，不要包含其他文字
2. 确保所有必填字段都有值
3. 数值类型的字段请使用数字而非字符串
4. 保持客观中立，基于分析结果得出结论

请生成报告："""

            # 调用 LLM
            response = await llm_client.chat_async(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )

            # 解析 LLM 响应
            result = self._parse_llm_response(response, template)

            # 添加元数据
            result["report_type"] = template.get("template_id")
            result["template_name"] = template.get("name")
            result["generated_at"] = datetime.utcnow().isoformat()
            result["workflow_id"] = template.get("workflow_id")
            result["ticker"] = workflow_state.get("ticker") if workflow_state else None
            result["generation_method"] = "llm"

            return result

        except Exception as e:
            logger.error(f"❌ LLM 报告生成失败: {e}，降级到规则提取")
            return self._generate_with_rules(template, agent_outputs, workflow_state)

    def _format_output_schema(self, output_schema: List[Dict[str, Any]]) -> str:
        """格式化 output_schema 为易读的描述"""
        lines = ["{"]
        for field in output_schema:
            name = field.get("name")
            field_type = field.get("type", "string")
            desc = field.get("description", "")
            required = field.get("required", True)
            enum_values = field.get("enum")

            type_hint = field_type
            if enum_values:
                type_hint = f"string, 可选值: {enum_values}"

            req_mark = "*必填*" if required else "可选"
            lines.append(f'  "{name}": {type_hint},  // {desc} ({req_mark})')

        lines.append("}")
        return "\n".join(lines)

    def _parse_llm_response(
        self,
        response: str,
        template: Dict[str, Any]
    ) -> Dict[str, Any]:
        """解析 LLM 响应"""
        try:
            # 尝试提取 JSON
            content = response.strip()

            # 处理 markdown 代码块
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                content = content[start:end].strip()
            elif "```" in content:
                start = content.find("```") + 3
                end = content.find("```", start)
                content = content[start:end].strip()

            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ LLM 响应 JSON 解析失败: {e}")
            return {"raw_response": response, "parse_error": str(e)}

