"""
状态 Schema 构建器

根据 Agent 列表动态生成工作流状态 Schema
"""

import logging
from typing import Any, Dict, List, Optional, Type
from langchain_core.messages import BaseMessage

from .models import (
    StateFieldDefinition,
    AgentIODefinition,
    WorkflowStateSchema,
    FieldType,
)

logger = logging.getLogger(__name__)


class StateSchemaBuilder:
    """
    状态 Schema 构建器
    
    根据工作流中的 Agent 列表，动态生成状态 Schema
    
    用法:
        builder = StateSchemaBuilder()
        schema = builder.build_from_agents(
            workflow_id="position_analysis",
            agent_ids=["pa_technical", "pa_fundamental", "pa_risk", "pa_advisor"]
        )
    """
    
    def __init__(self):
        self._io_cache: Dict[str, AgentIODefinition] = {}
    
    def build_from_agents(
        self,
        workflow_id: str,
        agent_ids: List[str],
        input_fields: Optional[List[StateFieldDefinition]] = None,
        internal_state_fields: Optional[Dict[str, Any]] = None,
    ) -> WorkflowStateSchema:
        """
        根据 Agent 列表构建状态 Schema
        
        Args:
            workflow_id: 工作流 ID
            agent_ids: Agent ID 列表
            input_fields: 额外的输入字段定义
            
        Returns:
            WorkflowStateSchema 实例
        """
        schema = WorkflowStateSchema(workflow_id=workflow_id)
        
        # 添加基础字段（messages）
        schema.add_field(StateFieldDefinition(
            name="messages",
            type=FieldType.LIST_MESSAGES,
            description="LangGraph 消息列表",
            required=True,
            is_input=True,
        ))
        
        # 收集所有 Agent 的 IO 定义
        for agent_id in agent_ids:
            io_def = self._get_agent_io(agent_id)
            if io_def is None:
                logger.warning(f"Agent {agent_id} 没有 IO 定义，跳过")
                continue
            
            # 添加输入字段
            for field in io_def.inputs:
                if field.name not in schema.fields:
                    field.is_input = True
                    schema.add_field(field)
            
            # 添加输出字段
            for field in io_def.outputs:
                field.source_agent = agent_id
                schema.add_field(field)
            
            # 记录依赖关系
            if io_def.reads_from:
                schema.agent_dependencies[agent_id] = io_def.reads_from
        
        # 添加额外输入字段
        if input_fields:
            for field in input_fields:
                field.is_input = True
                schema.add_field(field)

        # 添加工作流内部控制字段
        if internal_state_fields:
            for name, field_type in internal_state_fields.items():
                if name not in schema.fields:
                    schema.add_field(StateFieldDefinition(
                        name=name,
                        type=field_type,
                        description="工作流内部控制字段",
                    ))
        
        logger.info(
            f"构建状态 Schema: {workflow_id}, "
            f"字段数={len(schema.fields)}, "
            f"输入={len(schema.input_fields)}, "
            f"输出={len(schema.output_fields)}"
        )
        
        return schema
    
    def _get_agent_io(self, agent_id: str) -> Optional[AgentIODefinition]:
        """获取 Agent 的 IO 定义"""
        if agent_id in self._io_cache:
            return self._io_cache[agent_id]
        
        # 从 BindingManager 获取
        try:
            from core.config import BindingManager
            binding_manager = BindingManager()
            io_dict = binding_manager.get_agent_io_definition(agent_id)
            
            if io_dict:
                io_def = self._dict_to_io_definition(io_dict)
                self._io_cache[agent_id] = io_def
                return io_def
        except Exception as e:
            logger.warning(f"从 BindingManager 获取 IO 定义失败: {e}")
        
        # 从代码配置获取
        io_def = self._get_io_from_config(agent_id)
        if io_def:
            self._io_cache[agent_id] = io_def
        
        return io_def
    
    def _get_io_from_config(self, agent_id: str) -> Optional[AgentIODefinition]:
        """从代码配置获取 IO 定义（BUILTIN_AGENTS → AgentRegistry 回退）"""
        from core.agents.config import BUILTIN_AGENTS

        agent_meta = None

        # 1. 先查 BUILTIN_AGENTS
        if agent_id in BUILTIN_AGENTS:
            agent_meta = BUILTIN_AGENTS[agent_id]

        # 2. 回退到 AgentRegistry（v2 适配器通过 @register_agent 注册）
        if agent_meta is None:
            try:
                from core.agents.registry import get_registry
                agent_meta = get_registry().get_metadata(agent_id)
            except Exception as e:
                logger.debug(f"从 AgentRegistry 获取 {agent_id} 元数据失败: {e}")

        if agent_meta is None:
            return None
        
        # 构建输入字段
        inputs = []
        for inp in agent_meta.inputs:
            inputs.append(StateFieldDefinition(
                name=inp.name,
                type=FieldType(inp.type) if inp.type in FieldType.__members__.values() else FieldType.STRING,
                description=inp.description,
                required=inp.required,
                default=inp.default,
            ))
        
        # 构建输出字段
        outputs = []
        for out in agent_meta.outputs:
            outputs.append(StateFieldDefinition(
                name=out.name,
                type=FieldType(out.type) if out.type in FieldType.__members__.values() else FieldType.STRING,
                description=out.description,
            ))
        
        # 如果有 output_field 但没有 outputs，自动添加
        if agent_meta.output_field and not outputs:
            outputs.append(StateFieldDefinition(
                name=agent_meta.output_field,
                type=FieldType.STRING,
                description=f"{agent_meta.name} 的输出",
            ))
        
        return AgentIODefinition(
            agent_id=agent_id,
            inputs=inputs,
            outputs=outputs,
            reads_from=agent_meta.reads_from,
            description=agent_meta.description,
        )

    def _dict_to_io_definition(self, data: Dict[str, Any]) -> AgentIODefinition:
        """将字典转换为 AgentIODefinition"""
        inputs = []
        for inp in data.get("inputs", []):
            inputs.append(StateFieldDefinition(
                name=inp.get("name", ""),
                type=FieldType(inp.get("type", "string")),
                description=inp.get("description", ""),
                required=inp.get("required", False),
                default=inp.get("default"),
            ))

        outputs = []
        for out in data.get("outputs", []):
            outputs.append(StateFieldDefinition(
                name=out.get("name", ""),
                type=FieldType(out.get("type", "string")),
                description=out.get("description", ""),
            ))

        return AgentIODefinition(
            agent_id=data.get("agent_id", ""),
            inputs=inputs,
            outputs=outputs,
            reads_from=data.get("reads_from", []),
            description=data.get("description", ""),
        )

    def generate_typed_dict(self, schema: WorkflowStateSchema) -> Type:
        """
        根据 Schema 生成 TypedDict 类（带 LangGraph reducer 注解）

        生成的 TypedDict 每个字段都带有 Annotated reducer，
        确保并行节点执行时状态正确合并：
        - string → Annotated[str, keep_non_empty]（保留非空值）
        - object → Annotated[dict, merge_dict]（智能合并字典）
        - array  → Annotated[list, keep_latest_list]（采用最新列表）
        - messages → Annotated[List[BaseMessage], add_messages]（LangGraph 内置）
        """
        from typing import TypedDict, Annotated, List
        import operator
        from langgraph.graph.message import add_messages
        from .reducers import keep_non_empty, merge_dict, keep_latest_list

        # 动态创建字段（全部带 reducer 注解）
        annotations = {}

        for name, field in schema.fields.items():
            if name == "context":
                annotations[name] = Annotated[Any, keep_non_empty]
            elif name.startswith("_debate_") and name.endswith("_count"):
                annotations[name] = Annotated[int, operator.add]
            elif field.type == FieldType.LIST_MESSAGES:
                annotations[name] = Annotated[List[BaseMessage], add_messages]
            elif field.type == FieldType.STRING:
                annotations[name] = Annotated[str, keep_non_empty]
            elif field.type == FieldType.NUMBER:
                annotations[name] = Annotated[float, keep_non_empty]
            elif field.type == FieldType.BOOLEAN:
                annotations[name] = Annotated[bool, keep_non_empty]
            elif field.type == FieldType.OBJECT:
                annotations[name] = Annotated[dict, merge_dict]
            elif field.type == FieldType.ARRAY:
                annotations[name] = Annotated[list, keep_latest_list]
            else:
                annotations[name] = Annotated[str, keep_non_empty]

        # 创建 TypedDict
        state_class = TypedDict(f"{schema.workflow_id}_State", annotations)

        logger.info(
            f"生成动态 TypedDict: {schema.workflow_id}_State, "
            f"字段数={len(annotations)}（全部带 reducer 注解）"
        )

        return state_class

