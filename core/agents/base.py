"""
智能体基类

所有智能体都应继承此基类
v2.0 新增：标准化工具调用循环处理
"""

import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable
from app.utils.api_key_utils import truncate_api_key

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage
from langchain_core.tools import BaseTool

from ..collaboration_runtime import (
    InvocationArtifactRef,
    InvocationPolicy,
    InvocationProvenance,
    InvocationRequest,
    InvocationResult,
    InvocationSourceType,
    InvocationStatus,
    InvocationTargetType,
    utc_now,
)
from .config import AgentMetadata, AgentConfig

logger = logging.getLogger(__name__)

# 默认配置
DEFAULT_MAX_TOOL_ITERATIONS = 3  # 最大工具调用迭代次数
_DEFAULT_AGENT_CALLABLE_SURFACES = {"assistant", "workflow", "agent"}
GENERIC_REPORT_FALLBACK = "工具执行或模型生成未完成，当前结论仍待验证。"


class BaseAgent(ABC):
    """
    智能体基类

    提供统一的接口和通用功能:
    - LLM 调用
    - 工具管理（支持动态绑定）
    - 提示词渲染
    - 状态管理
    - 日志记录

    v2.0 新特性:
    - 支持从配置或数据库动态加载工具
    - 支持 LangChain 工具集成
    - 支持元数据自动加载
    """

    # 子类需要定义的元数据
    metadata: AgentMetadata = None

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        llm: Optional[BaseChatModel] = None,
        tool_ids: Optional[List[str]] = None
    ):
        """
        初始化 Agent

        Args:
            config: Agent 配置（旧版兼容）
            llm: LangChain LLM 实例（新版）
            tool_ids: 工具 ID 列表（新版，可选）
        """
        logger.info(f"[BaseAgent] 🚀 开始初始化 Agent")
        # 🔥 排除 llm_provider 和 llm_model，因为这些不应该在 Agent 配置中
        config_dict_log = config.model_dump(exclude={'llm_provider', 'llm_model'}) if config else None
        logger.info(f"   - config: {config_dict_log}")
        logger.info(f"   - llm: {type(llm).__name__ if llm else 'None'}")
        logger.info(f"   - tool_ids: {tool_ids}")

        self.config = config or AgentConfig()
        self._llm_client = None
        self._llm = llm  # LangChain LLM（新版）
        self._tools: Dict[str, Callable] = {}  # 旧版工具字典
        self._langchain_tools: List[BaseTool] = []  # 新版 LangChain 工具列表
        self._prompt_template: Optional[str] = None
        self._last_llm_debug: Dict[str, Any] = {}
        self._last_tool_debug: List[Dict[str, Any]] = []

        # v2.0: 动态加载工具
        if tool_ids is not None:
            logger.info(f"[BaseAgent] 🔧 开始加载工具: {tool_ids}")
            self._load_tools_v2(tool_ids)
            logger.info(f"[BaseAgent] ✅ 工具加载完成，工具数量: {len(self._langchain_tools)}")
        else:
            logger.info(f"[BaseAgent] ⚠️ 未提供 tool_ids，跳过工具加载")

        logger.info(f"[BaseAgent] ✅ Agent 初始化完成")
        logger.info(f"   - Agent ID: {self.agent_id if hasattr(self, 'agent_id') else 'N/A'}")
        logger.info(f"   - _llm: {type(self._llm).__name__ if self._llm else 'None'}")
        logger.info(f"   - _langchain_tools 数量: {len(self._langchain_tools)}")
    
    @classmethod
    def get_metadata(cls) -> AgentMetadata:
        """获取智能体元数据"""
        if cls.metadata is None:
            raise NotImplementedError(f"{cls.__name__} 必须定义 metadata")
        return cls.metadata

    def set_dependencies(self, llm: BaseChatModel, toolkit: Optional[Any] = None):
        """
        设置依赖项（LLM和工具）

        由WorkflowEngine调用，用于注入LLM和工具依赖

        Args:
            llm: 语言模型实例
            toolkit: 工具集（可选）
        """
        self._llm = llm
        if toolkit and hasattr(toolkit, 'tools'):
            # 如果提供了toolkit，可以选择性地添加工具
            # 但不覆盖已有的工具
            pass
        logger.info(f"✅ Agent {self.agent_id} 已设置LLM依赖")

    def initialize(self) -> None:
        """
        初始化智能体
        
        子类可以覆盖此方法进行额外初始化
        """
        logger.info(f"[BaseAgent.initialize] 🔧 开始初始化 Agent: {self.agent_id}")
        logger.info(f"   - _llm 值: {type(self._llm).__name__ if self._llm else 'None'}")
        logger.info(f"   - _llm_client 值: {type(self._llm_client).__name__ if self._llm_client else 'None'}")
        
        # 🔥 如果已经传入了 llm，就不需要创建 _llm_client
        # LLM provider 和 model 应该由分析流程指定，而不是 Agent 配置
        if self._llm is None:
            logger.warning(
                f"⚠️ Agent {self.agent_id} 的 _llm 为 None，将尝试从配置创建 LLM 客户端。"
                f"这通常不应该发生，因为 LLM 应该由 WorkflowBuilder 在创建 Agent 时传入。"
                f"请检查：1) WorkflowBuilder 是否正确传入了 llm 参数；2) AgentFactory 是否正确传递了 llm 参数。"
            )
            self._setup_llm()
        else:
            logger.info(f"✅ Agent {self.agent_id} 已传入 LLM 实例: {type(self._llm).__name__}")
            # 🔍 验证 LLM 实例是否有 API key
            if hasattr(self._llm, 'openai_api_key'):
                api_key_val = self._llm.openai_api_key
                if hasattr(api_key_val, 'get_secret_value'):
                    api_key_val = api_key_val.get_secret_value()
                logger.info(f"   - LLM API Key: {'有值' if api_key_val else '空'}")
            elif hasattr(self._llm, 'api_key'):
                api_key_val = self._llm.api_key
                if hasattr(api_key_val, 'get_secret_value'):
                    api_key_val = api_key_val.get_secret_value()
                logger.info(f"   - LLM API Key: {'有值' if api_key_val else '空'}")
        
        logger.info(f"[BaseAgent.initialize] 🔧 开始设置工具...")
        self._setup_tools()
        logger.info(f"[BaseAgent.initialize] 🔧 开始设置提示词...")
        self._setup_prompt()
        logger.info(f"[BaseAgent.initialize] ✅ Agent {self.agent_id} 初始化完成")
    
    def _setup_llm(self) -> None:
        """
        设置 LLM 客户端（仅在未传入 llm 时调用）
        
        ⚠️ 注意：此方法会从环境变量读取 API key，这通常不应该发生。
        正确的做法是在创建 Agent 时传入已配置好的 LLM 实例。
        """
        from ..llm import UnifiedLLMClient
        
        # 🔥 如果 config 中没有 llm_provider 和 llm_model，使用默认值
        # 但这种情况不应该发生，因为 LLM 应该由分析流程传入
        provider = getattr(self.config, 'llm_provider', None) or "dashscope"
        model = getattr(self.config, 'llm_model', None)
        
        if not model:
            logger.warning(
                f"⚠️ Agent {self.agent_id} 的 config 中没有 llm_model，无法创建 LLM 客户端。"
                f"LLM 应该由分析流程（WorkflowBuilder）在创建 Agent 时传入，而不是从 Agent 配置中读取。"
            )
            return
        
        logger.warning(
            f"⚠️ Agent {self.agent_id} 正在从环境变量读取 API key 来创建 LLM 客户端。"
            f"这通常不应该发生，因为 LLM 应该由 WorkflowBuilder 在创建 Agent 时传入。"
            f"Provider: {provider}, Model: {model}"
        )
        
        self._llm_client = UnifiedLLMClient.from_provider(
            provider=provider,
            model=model,
            temperature=self.config.temperature,
            timeout=self.config.timeout,
        )
    
    def _setup_tools(self) -> None:
        """
        设置工具

        子类应覆盖此方法注册可用工具
        """
        pass

    def _load_tools_v2(self, tool_ids: List[str]) -> None:
        """
        v2.0: 从工具 ID 列表加载 LangChain 工具

        Args:
            tool_ids: 工具 ID 列表
        """
        from core.tools.registry import ToolRegistry

        registry = ToolRegistry()
        self._langchain_tools = []

        logger.info(f"🔧 [Agent {self.agent_id}] 开始加载工具: {tool_ids}")

        for tool_id in tool_ids:
            # 🔍 详细诊断：检查工具是否在注册表中
            has_metadata = registry.has_tool(tool_id)
            has_function = registry.get_function(tool_id) is not None
            
            if not has_metadata:
                logger.warning(
                    f"⚠️ [Agent {self.agent_id}] 工具未找到: {tool_id}\n"
                    f"   - 元数据: ❌ 不存在\n"
                    f"   - 函数: {'✅ 存在' if has_function else '❌ 不存在'}\n"
                    f"   💡 可能原因: 工具模块未加载或工具ID错误"
                )
            elif not has_function:
                logger.warning(
                    f"⚠️ [Agent {self.agent_id}] 工具未找到: {tool_id}\n"
                    f"   - 元数据: ✅ 存在\n"
                    f"   - 函数: ❌ 不存在\n"
                    f"   💡 可能原因: 工具函数未注册，请检查工具模块是否正确导入"
                )
                # 🔧 尝试重新加载工具模块
                try:
                    from core.tools.loader import get_tool_loader
                    loader = get_tool_loader()
                    if loader.load_tool(tool_id):
                        logger.info(f"🔄 [Agent {self.agent_id}] 已重新加载工具模块: {tool_id}")
                        # 重新尝试获取
                        tool = registry.get_langchain_tool(tool_id)
                        if tool:
                            self._langchain_tools.append(tool)
                            logger.info(f"✅ [Agent {self.agent_id}] 重新加载后成功获取工具: {tool_id}")
                            continue
                except Exception as e:
                    logger.debug(f"重新加载工具失败 {tool_id}: {e}")
            else:
                tool = registry.get_langchain_tool(tool_id)
                if tool:
                    self._langchain_tools.append(tool)
                    logger.info(f"✅ [Agent {self.agent_id}] 成功加载工具: {tool_id}")
                else:
                    logger.warning(
                        f"⚠️ [Agent {self.agent_id}] 工具元数据和函数存在，但无法创建 LangChain 工具: {tool_id}\n"
                        f"   - 元数据: ✅ 存在\n"
                        f"   - 函数: ✅ 存在\n"
                        f"   💡 可能原因: 函数格式不正确或 LangChain 工具创建失败"
                    )

        logger.info(f"🔧 [Agent {self.agent_id}] 工具加载完成: {len(self._langchain_tools)}/{len(tool_ids)} 个工具")

    def load_tools_from_config(self) -> List[str]:
        """
        v2.0: 从配置加载工具列表

        优先级:
        1. 数据库配置（BindingManager）
        2. 元数据中的默认工具
        3. 空列表

        Returns:
            工具 ID 列表
        """
        try:
            # 优先从数据库配置加载
            from core.config.binding_manager import BindingManager
            tool_ids = BindingManager().get_tools_for_agent(self.agent_id)

            if tool_ids:
                logger.info(f"📦 从数据库加载 {len(tool_ids)} 个工具: {tool_ids}")
                return tool_ids

            # 降级：使用元数据中的默认工具
            metadata = self.get_metadata()
            if hasattr(metadata, 'default_tools') and metadata.default_tools:
                logger.info(f"📦 从元数据加载 {len(metadata.default_tools)} 个默认工具")
                return metadata.default_tools

            if hasattr(metadata, 'tools') and metadata.tools:
                logger.info(f"📦 从元数据加载 {len(metadata.tools)} 个工具")
                return metadata.tools

            logger.warning(f"⚠️ Agent '{self.agent_id}' 没有配置工具")
            return []

        except Exception as e:
            logger.error(f"❌ 加载工具配置失败: {e}")
            return []
    
    def _setup_prompt(self) -> None:
        """
        设置提示词模板
        
        子类应覆盖此方法设置提示词
        """
        pass
    
    def register_tool(
        self,
        func: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> None:
        """注册工具"""
        tool_def = self._llm_client.register_tool(func, name, description)
        tool_name = tool_def["function"]["name"]
        self._tools[tool_name] = func

    def _normalize_callable_surfaces(self, raw_surfaces: Optional[List[Any]]) -> set:
        normalized = {
            str(item).strip().lower()
            for item in (raw_surfaces or [])
            if str(item).strip()
        }
        return normalized or set(_DEFAULT_AGENT_CALLABLE_SURFACES)

    def _ensure_agent_surface_access(self, target_agent_id: str) -> None:
        from app.core.database import get_mongo_db_sync

        from .registry import get_registry

        registry = get_registry()
        metadata = registry.get_metadata(target_agent_id)
        metadata_surfaces = getattr(metadata, "callable_surfaces", None)
        db_surfaces = None

        try:
            db = get_mongo_db_sync()
            if db is not None:
                doc = db.agent_configs.find_one(
                    {"agent_id": target_agent_id},
                    {"metadata.callable_surfaces": 1},
                ) or {}
                db_surfaces = ((doc.get("metadata") or {}).get("callable_surfaces"))
        except Exception as exc:
            logger.warning("[BaseAgent] 读取 Agent 调用面配置失败 %s: %s", target_agent_id, exc)

        allowed_surfaces = self._normalize_callable_surfaces(db_surfaces or metadata_surfaces)
        if "agent" not in allowed_surfaces:
            raise ValueError(f"Agent {target_agent_id} 当前不允许从 agent 入口直接调用")

    def _extract_runtime_context(self, state: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        runtime_context: Dict[str, Any] = {}
        if not isinstance(state, dict):
            return runtime_context

        runtime_context.update(dict(state.get("_workflow_runtime") or {}))

        lineage = state.get("invocation_lineage")
        if isinstance(lineage, dict):
            for field_name in ("current_invocation_id", "parent_invocation_id", "root_invocation_id"):
                field_value = lineage.get(field_name)
                if field_value and not runtime_context.get(field_name):
                    runtime_context[field_name] = field_value

        invocation_provenance = state.get("invocation_provenance")
        if isinstance(invocation_provenance, dict):
            provenance_metadata = invocation_provenance.get("metadata") if isinstance(invocation_provenance.get("metadata"), dict) else {}
            for field_name in ("root_invocation_id", "parent_invocation_id"):
                field_value = provenance_metadata.get(field_name)
                if field_value and not runtime_context.get(field_name):
                    runtime_context[field_name] = field_value

        if state.get("workflow_id") and not runtime_context.get("workflow_id"):
            runtime_context["workflow_id"] = state.get("workflow_id")
        if state.get("node_id") and not runtime_context.get("node_id"):
            runtime_context["node_id"] = state.get("node_id")
        if state.get("user_id") and not runtime_context.get("user_id"):
            runtime_context["user_id"] = state.get("user_id")
        if state.get("thread_id") and not runtime_context.get("thread_id"):
            runtime_context["thread_id"] = state.get("thread_id")

        context = state.get("context")
        if isinstance(context, dict):
            if context.get("workflow_id") and not runtime_context.get("workflow_id"):
                runtime_context["workflow_id"] = context.get("workflow_id")
            if context.get("node_id") and not runtime_context.get("node_id"):
                runtime_context["node_id"] = context.get("node_id")
            if context.get("user_id") and not runtime_context.get("user_id"):
                runtime_context["user_id"] = context.get("user_id")
            if context.get("session_id") and not runtime_context.get("session_id"):
                runtime_context["session_id"] = context.get("session_id")
            if context.get("thread_id") and not runtime_context.get("thread_id"):
                runtime_context["thread_id"] = context.get("thread_id")
            extra = context.get("extra") if isinstance(context.get("extra"), dict) else {}
            for field_name in ("invocation_id", "root_invocation_id", "parent_invocation_id"):
                field_value = extra.get(field_name)
                target_field = "current_invocation_id" if field_name == "invocation_id" else field_name
                if field_value and not runtime_context.get(target_field):
                    runtime_context[target_field] = field_value
        elif context is not None:
            for field_name in ("workflow_id", "node_id", "user_id", "session_id", "thread_id"):
                field_value = getattr(context, field_name, None)
                if field_value and not runtime_context.get(field_name):
                    runtime_context[field_name] = field_value
            extra = getattr(context, "extra", None)
            if isinstance(extra, dict):
                for field_name in ("invocation_id", "root_invocation_id", "parent_invocation_id"):
                    field_value = extra.get(field_name)
                    target_field = "current_invocation_id" if field_name == "invocation_id" else field_name
                    if field_value and not runtime_context.get(target_field):
                        runtime_context[target_field] = field_value

        return runtime_context

    def _sanitize_invocation_value(self, value: Any, max_text_length: int = 3000, depth: int = 0) -> Any:
        if isinstance(value, str):
            return value[:max_text_length]
        if isinstance(value, (int, float, bool)) or value is None:
            return value
        if depth >= 1:
            return str(value)[:max_text_length]
        if isinstance(value, list):
            return [self._sanitize_invocation_value(item, max_text_length=max_text_length, depth=depth + 1) for item in value[:10]]
        if isinstance(value, dict):
            sanitized: Dict[str, Any] = {}
            for key, item in list(value.items())[:20]:
                sanitized[str(key)] = self._sanitize_invocation_value(item, max_text_length=max_text_length, depth=depth + 1)
            return sanitized
        return str(value)[:max_text_length]

    def _build_agent_invocation_payload(
        self,
        state: Optional[Dict[str, Any]],
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        prepared_payload = dict(payload or {})
        if not isinstance(state, dict):
            return prepared_payload or {"raw_state": self._sanitize_invocation_value(state)}

        preferred_keys = [
            "symbol",
            "ticker",
            "stock_symbol",
            "stock_code",
            "trade_date",
            "analysis_date",
            "market_type",
            "task",
            "task_description",
            "query",
        ]
        for key in preferred_keys:
            if key in state and key not in prepared_payload:
                prepared_payload[key] = self._sanitize_invocation_value(state.get(key))

        if prepared_payload:
            return prepared_payload

        snapshot: Dict[str, Any] = {}
        for key, value in state.items():
            if str(key).startswith("_") or key in {"messages", "context"}:
                continue
            snapshot[str(key)] = self._sanitize_invocation_value(value)
            if len(snapshot) >= 12:
                break
        return {"state_snapshot": snapshot}

    def _resolve_agent_output_field(self, target_agent_id: str) -> Optional[str]:
        from app.core.database import get_mongo_db_sync

        from .registry import get_registry

        try:
            db = get_mongo_db_sync()
            if db is not None:
                doc = db.agent_configs.find_one(
                    {"agent_id": target_agent_id},
                    {"output_field": 1, "metadata.output_field": 1},
                ) or {}
                if doc.get("output_field"):
                    return str(doc["output_field"])
                if (doc.get("metadata") or {}).get("output_field"):
                    return str(doc["metadata"]["output_field"])
        except Exception as exc:
            logger.warning("[BaseAgent] 读取 Agent 输出字段失败 %s: %s", target_agent_id, exc)

        metadata = get_registry().get_metadata(target_agent_id)
        if metadata and getattr(metadata, "output_field", None):
            return str(metadata.output_field)
        outputs = getattr(metadata, "outputs", None) or []
        if outputs and getattr(outputs[0], "name", None):
            return str(outputs[0].name)
        return None

    def _extract_invocation_output_text(self, result: Dict[str, Any], output_field: Optional[str]) -> str:
        candidate_fields = [
            output_field,
            "final_report",
            "analysis_report",
            "summary",
            "analysis_result",
        ]
        for field_name in candidate_fields:
            if not field_name:
                continue
            value = result.get(field_name)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, dict):
                for nested_key in ("content", "markdown", "text", "message", "report"):
                    nested_value = value.get(nested_key)
                    if isinstance(nested_value, str) and nested_value.strip():
                        return nested_value.strip()

        for value in result.values():
            if isinstance(value, str) and value.strip() and len(value.strip()) > 20:
                return value.strip()
        return ""

    def _sanitize_structured_output(self, result: Any) -> Dict[str, Any]:
        if not isinstance(result, dict):
            return {"raw_result": self._sanitize_invocation_value(result, max_text_length=4000)}

        sanitized: Dict[str, Any] = {}
        for key, value in result.items():
            if key == "messages":
                continue
            sanitized[str(key)] = self._sanitize_invocation_value(value, max_text_length=4000)
        return sanitized

    def _persist_agent_invocation_record(
        self,
        request: InvocationRequest,
        result: InvocationResult,
    ) -> None:
        from app.core.database import get_mongo_db_sync

        try:
            db = get_mongo_db_sync()
            if db is None:
                return
            db.agent_agent_invocations.update_one(
                {"invocation_id": request.invocation_id},
                {
                    "$set": {
                        "invocation_id": request.invocation_id,
                        "root_invocation_id": request.metadata.get("root_invocation_id") or request.provenance.metadata.get("root_invocation_id") or request.invocation_id,
                        "parent_invocation_id": request.metadata.get("parent_invocation_id") or request.provenance.metadata.get("parent_invocation_id"),
                        "source_agent_id": request.provenance.source_id,
                        "workflow_id": request.provenance.workflow_id,
                        "execution_id": request.provenance.session_id,
                        "step_id": request.provenance.step_id,
                        "user_id": request.provenance.user_id,
                        "thread_id": request.provenance.thread_id,
                        "target_type": request.target_type.value,
                        "target_id": request.target_id,
                        "status": result.status.value,
                        "request": request.to_python_dict(),
                        "result": result.to_python_dict(),
                        "updated_at": datetime.utcnow(),
                    },
                    "$setOnInsert": {"created_at": datetime.utcnow()},
                },
                upsert=True,
            )
        except Exception as exc:
            logger.warning("[BaseAgent] 持久化 Agent 调用记录失败 %s -> %s: %s", request.provenance.source_id, request.target_id, exc)

    def invoke_agent(
        self,
        *,
        target_agent_id: str,
        state: Dict[str, Any],
        payload: Optional[Dict[str, Any]] = None,
        config: Optional[AgentConfig] = None,
        tool_ids: Optional[List[str]] = None,
        visible_to_caller: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """在 Agent 内部统一调用另一个 Agent，并记录协作运行时。"""
        from .factory import AgentFactory

        if self._llm is None:
            raise ValueError(f"Agent {self.agent_id} 当前没有可复用的 LLM，无法委托调用 {target_agent_id}")

        self._ensure_agent_surface_access(target_agent_id)

        runtime_context = self._extract_runtime_context(state)
        invocation_id = f"ginv_{uuid.uuid4().hex}"
        source_node_id = runtime_context.get("node_id") or self.agent_id
        execution_id = runtime_context.get("execution_id") or runtime_context.get("session_id")
        parent_invocation_id = runtime_context.get("current_invocation_id") or runtime_context.get("parent_invocation_id")
        root_invocation_id = runtime_context.get("root_invocation_id") or parent_invocation_id or invocation_id
        invocation_request = InvocationRequest(
            invocation_id=invocation_id,
            target_type=InvocationTargetType.AGENT,
            target_id=target_agent_id,
            action="execute",
            payload=self._build_agent_invocation_payload(state, payload),
            provenance=InvocationProvenance(
                source_type=InvocationSourceType.AGENT,
                source_id=self.agent_id,
                user_id=runtime_context.get("user_id"),
                session_id=execution_id,
                thread_id=runtime_context.get("thread_id"),
                workflow_id=runtime_context.get("workflow_id"),
                step_id=source_node_id,
                trigger="agent_delegate",
                metadata={
                    "target_agent_id": target_agent_id,
                    "source_node_id": source_node_id,
                    "root_invocation_id": root_invocation_id,
                    "parent_invocation_id": parent_invocation_id,
                    **(metadata or {}),
                },
            ),
            policy=InvocationPolicy(
                idempotency_key=f"{self.agent_id}:{target_agent_id}:{execution_id or invocation_id}",
                timeout_seconds=int((config or self.config).timeout if (config or self.config) else 180),
                lane=f"agent.{runtime_context.get('workflow_id') or self.agent_id}",
                visible_to_caller=visible_to_caller,
            ),
            metadata={
                "invocation_source": "agent",
                "source_agent_id": self.agent_id,
                "root_invocation_id": root_invocation_id,
                "parent_invocation_id": parent_invocation_id,
                **(metadata or {}),
            },
        )
        started_at = utc_now()
        output_field = self._resolve_agent_output_field(target_agent_id)

        try:
            delegated_agent = AgentFactory().create(
                target_agent_id,
                config=config or AgentConfig(),
                llm=self._llm,
                tool_ids=tool_ids,
                memory=getattr(self, "memory", None) or getattr(self, "_memory", None),
            )
            delegated_state = dict(state or {})
            delegated_state["node_id"] = target_agent_id
            delegated_state["invocation_provenance"] = invocation_request.provenance.to_python_dict()
            delegated_state["invocation_lineage"] = {
                "current_invocation_id": invocation_request.invocation_id,
                "parent_invocation_id": parent_invocation_id,
                "root_invocation_id": root_invocation_id,
            }

            raw_result = delegated_agent(delegated_state)
            result = raw_result if isinstance(raw_result, dict) else {
                (output_field or f"{target_agent_id}_report"): raw_result
            }

            invocation_result = InvocationResult(
                invocation_id=invocation_request.invocation_id,
                target_type=InvocationTargetType.AGENT,
                target_id=target_agent_id,
                status=InvocationStatus.SUCCEEDED,
                started_at=started_at,
                output_text=self._extract_invocation_output_text(result, output_field),
                structured_output=self._sanitize_structured_output(result),
                output_field=output_field,
                artifacts=[
                    InvocationArtifactRef(
                        ref_type="agent_agent_invocation",
                        artifact_key=invocation_request.invocation_id,
                        title=f"Agent委托调用：{self.agent_id} -> {target_agent_id}",
                        summary=self._extract_invocation_output_text(result, output_field)[:300],
                        source_collection="agent_agent_invocations",
                        output_field=output_field,
                        metadata={
                            "source_agent_id": self.agent_id,
                            "target_agent_id": target_agent_id,
                            "workflow_id": runtime_context.get("workflow_id"),
                        },
                    )
                ],
                metadata={
                    "source_agent_id": self.agent_id,
                    "workflow_id": runtime_context.get("workflow_id"),
                    "root_invocation_id": root_invocation_id,
                    "parent_invocation_id": parent_invocation_id,
                    **(metadata or {}),
                },
            )
            self._persist_agent_invocation_record(invocation_request, invocation_result)
            return result
        except Exception as exc:
            invocation_result = InvocationResult(
                invocation_id=invocation_request.invocation_id,
                target_type=InvocationTargetType.AGENT,
                target_id=target_agent_id,
                status=InvocationStatus.FAILED,
                started_at=started_at,
                output_field=output_field,
                error_message=str(exc),
                metadata={
                    "source_agent_id": self.agent_id,
                    "workflow_id": runtime_context.get("workflow_id"),
                    "root_invocation_id": root_invocation_id,
                    "parent_invocation_id": parent_invocation_id,
                    **(metadata or {}),
                },
            )
            self._persist_agent_invocation_record(invocation_request, invocation_result)
            raise
    
    @abstractmethod
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行智能体逻辑
        
        Args:
            state: 当前状态字典
            
        Returns:
            更新后的状态字典
        """

    def describe_capabilities(self) -> Dict[str, Any]:
        """返回当前 Agent 的结构化能力声明。"""
        metadata = self.get_metadata()
        growth_outputs = list(metadata.growth_outputs or [])
        if not growth_outputs and metadata.output_field:
            growth_outputs = [metadata.output_field]

        return {
            "agent_id": metadata.id,
            "category": metadata.category,
            "reads_from": list(metadata.reads_from or []),
            "output_field": metadata.output_field,
            "requires_tools": metadata.requires_tools,
            "default_tools": list(metadata.default_tools or []),
            "max_tool_calls": metadata.max_tool_calls,
            "growth_role": metadata.growth_role,
            "growth_outputs": growth_outputs,
            "memory_scope_hint": metadata.memory_scope_hint,
            "review_level": metadata.review_level,
            "growth_source_type": metadata.growth_source_type,
            "maturity_level": metadata.maturity_level,
            "input_mode": metadata.input_mode,
            "debug_replay_mode": metadata.debug_replay_mode,
            "maintenance_status": metadata.maintenance_status,
            "callable_surfaces": list(metadata.callable_surfaces or []),
        }

    def get_growth_artifacts(
        self,
        result: Dict[str, Any],
        state: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """基于元数据返回适合进入成长抽取的候选产物。"""
        metadata = self.get_metadata()
        candidate_fields = list(metadata.growth_outputs or [])
        if not candidate_fields and metadata.output_field:
            candidate_fields = [metadata.output_field]

        artifacts: List[Dict[str, Any]] = []
        source_state = state or {}
        for field_name in candidate_fields:
            value = result.get(field_name)
            if value is None:
                value = source_state.get(field_name)
            if value in (None, "", [], {}):
                continue

            artifacts.append(
                {
                    "field": field_name,
                    "content": value,
                    "review_level": metadata.review_level,
                    "memory_scope_hint": metadata.memory_scope_hint,
                    "growth_source_type": metadata.growth_source_type,
                }
            )

        return artifacts

    def get_review_requirement(self) -> str:
        """返回成长产物的审核要求。"""
        return str(self.get_metadata().review_level)
        pass
    
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """使智能体可调用，用于 LangGraph 节点"""
        return self.execute(state)
    
    def render_prompt(
        self,
        template: Optional[str] = None,
        **variables
    ) -> str:
        """
        渲染提示词模板
        
        Args:
            template: 提示词模板 (如果为 None，使用默认模板)
            **variables: 模板变量
            
        Returns:
            渲染后的提示词
        """
        tpl = template or self._prompt_template
        if tpl is None:
            return ""
        
        # 合并配置中的变量
        all_vars = {**self.config.prompt_variables, **variables}
        
        try:
            return tpl.format(**all_vars)
        except KeyError as e:
            # 记录警告但不中断
            return tpl
    
    def log(self, message: str, level: str = "info") -> None:
        """记录日志"""
        # TODO: 集成统一日志系统
        prefix = f"[{self.get_metadata().name}]"
        print(f"{prefix} {message}")
    
    @property
    def agent_id(self) -> str:
        """智能体 ID"""
        return self.get_metadata().id
    
    @property
    def agent_name(self) -> str:
        """智能体名称"""
        return self.get_metadata().name
    
    @property
    def llm(self):
        """LLM 客户端（旧版）或 LangChain LLM（新版）"""
        return self._llm or self._llm_client

    @property
    def tools(self) -> List[BaseTool]:
        """v2.0: 获取 LangChain 工具列表"""
        return self._langchain_tools

    @property
    def tool_names(self) -> List[str]:
        """v2.0: 获取工具名称列表"""
        return [tool.name for tool in self._langchain_tools]

    # ========== v2.0: 标准化工具调用循环处理 ==========

    def invoke_with_tools(
        self,
        messages: List,
        analysis_prompt: Optional[str] = None,
        max_iterations: int = DEFAULT_MAX_TOOL_ITERATIONS
    ) -> str:
        """
        v2.0: 标准化的工具调用循环处理（自包含模式）

        这是推荐的 LLM + 工具调用方式，所有 Agent 都应该使用这个方法。

        流程:
        1. 调用 LLM（绑定工具）
        2. 如果 LLM 返回 tool_calls:
           a. 在 Agent 内部执行所有工具
           b. 将工具结果添加到消息历史
           c. 再次调用 LLM（不绑定工具）生成最终报告
        3. 返回最终报告内容

        Args:
            messages: 消息列表（包含 SystemMessage 和 HumanMessage）
            analysis_prompt: 工具执行后的分析提示词（可选）
            max_iterations: 最大工具调用迭代次数（防止死循环）

        Returns:
            str: 最终的分析报告内容
        """
        if not self._llm:
            raise ValueError("LLM 未配置，无法执行工具调用")

        current_messages = list(messages)
        self._last_tool_debug = []

        logger.info(f"🚀 [{self.agent_id}] 开始工具调用循环，最大迭代次数: {max_iterations}")
        logger.info(f"🔧 [{self.agent_id}] 可用工具数量: {len(self._langchain_tools) if self._langchain_tools else 0}")
        if self._langchain_tools:
            logger.info(f"🔧 [{self.agent_id}] 工具列表: {[tool.name for tool in self._langchain_tools]}")

        for iteration in range(max_iterations):
            logger.info(f"🔄 [{self.agent_id}] 工具调用迭代 {iteration + 1}/{max_iterations}")

            # 绑定工具并调用 LLM
            if self._langchain_tools:
                llm_with_tools = self._llm.bind_tools(self._langchain_tools)
                logger.info(f"🔗 [{self.agent_id}] LLM已绑定 {len(self._langchain_tools)} 个工具")
            else:
                llm_with_tools = self._llm
                logger.info(f"🔗 [{self.agent_id}] LLM未绑定工具")

            logger.info(f"💬 [{self.agent_id}] 调用LLM，消息数量: {len(current_messages)}")

            # 🔍 打印 LLM 配置信息（包括 API Key 前5位）
            logger.info(f"=" * 100)
            logger.info(f"🔍 [{self.agent_id}] LLM 配置信息:")
            logger.info(f"=" * 100)
            if hasattr(self._llm, 'model_name'):
                logger.info(f"   模型: {self._llm.model_name}")
            if hasattr(self._llm, 'openai_api_base') or hasattr(self._llm, 'base_url'):
                base_url = getattr(self._llm, 'openai_api_base', None) or getattr(self._llm, 'base_url', None)
                logger.info(f"   API Base URL: {base_url}")
            # 🔍 尝试多种方式获取真实的 API Key（绕过脱敏）
            api_key = None

            # 方法1: 从 client 对象获取
            if hasattr(self._llm, 'client') and hasattr(self._llm.client, 'api_key'):
                api_key = self._llm.client.api_key
                logger.info(f"   API Key 来源: client.api_key")

            # 方法2: 从 _client 对象获取（私有属性）
            elif hasattr(self._llm, '_client') and hasattr(self._llm._client, 'api_key'):
                api_key = self._llm._client.api_key
                logger.info(f"   API Key 来源: _client.api_key")

            # 方法3: 从环境变量获取（作为对比）
            else:
                import os
                env_api_key = os.getenv("DASHSCOPE_API_KEY")
                if env_api_key:
                    logger.info(f"   API Key 来源: 环境变量 DASHSCOPE_API_KEY")
                    logger.info(f"   环境变量 API Key: {truncate_api_key(env_api_key)}")

                # 尝试从属性获取（可能被脱敏）
                api_key = getattr(self._llm, 'openai_api_key', None) or getattr(self._llm, 'api_key', None)
                if api_key and str(api_key) != "**********":
                    logger.info(f"   API Key 来源: LLM 属性")
                else:
                    logger.info(f"   API Key 来源: LLM 属性（已脱敏）")

            # 打印 API Key 信息（完整值，用于调试）
            if api_key:
                api_key_str = str(api_key)
                if api_key_str == "**********":
                    logger.info(f"   API Key: 已脱敏（无法获取真实值）")
                else:
                    logger.info(f"   API Key: 有值")
                    #logger.info(f"   API Key: {truncate_api_key(api_key_str)}")
                    logger.info(f"   API Key 长度: {len(api_key_str)}")
            else:
                logger.info(f"   API Key: 空")
            if hasattr(self._llm, 'temperature'):
                logger.info(f"   Temperature: {self._llm.temperature}")
            if hasattr(self._llm, 'max_tokens'):
                logger.info(f"   Max Tokens: {self._llm.max_tokens}")
            if hasattr(self._llm, 'timeout') or hasattr(self._llm, 'request_timeout'):
                timeout = getattr(self._llm, 'timeout', None) or getattr(self._llm, 'request_timeout', None)
                logger.info(f"   Timeout: {timeout}")
            logger.info(f"=" * 100)

            # 详细打印每条消息
            logger.info(f"=" * 100)
            logger.info(f"📋 [{self.agent_id}] 第 {iteration + 1} 次 LLM 调用 - 消息详情:")
            logger.info(f"=" * 100)
            for idx, msg in enumerate(current_messages):
                msg_type = type(msg).__name__
                if hasattr(msg, 'content'):
                    # 🔥 对于SystemMessage，打印完整内容以便验证模板是否正确
                    if msg_type == "SystemMessage":
                        logger.info(f"  [{idx+1}] {msg_type}:")
                        logger.info(f"      内容长度: {len(msg.content)} 字符")
                        logger.info(f"      🔍 完整内容: {msg.content}")
                    else:
                        content_preview = msg.content[:200] if len(msg.content) > 200 else msg.content
                        logger.info(f"  [{idx+1}] {msg_type}:")
                        logger.info(f"      内容长度: {len(msg.content)} 字符")
                        logger.info(f"      内容预览: {content_preview}")
                elif hasattr(msg, 'tool_calls'):
                    logger.info(f"  [{idx+1}] {msg_type}:")
                    logger.info(f"      工具调用数量: {len(msg.tool_calls)}")
                    for tc_idx, tc in enumerate(msg.tool_calls):
                        logger.info(f"        [{tc_idx+1}] {tc.get('name', 'unknown')}: {tc.get('args', {})}")
                else:
                    logger.info(f"  [{idx+1}] {msg_type}: {str(msg)[:200]}")
            logger.info(f"=" * 100)

            from core.utils.retry import retry_sync, is_retryable
            max_retries = getattr(self.config, 'max_retries', 3)
            response = retry_sync(
                llm_with_tools.invoke,
                current_messages,
                max_retries=max_retries,
                label=self.agent_id,
                retryable=is_retryable,
            )

            # 打印响应详情
            logger.info(f"=" * 100)
            logger.info(f"📤 [{self.agent_id}] LLM 响应详情:")
            logger.info(f"=" * 100)
            logger.info(f"  响应类型: {type(response).__name__}")
            if hasattr(response, 'content'):
                logger.info(f"  content 长度: {len(response.content)} 字符")
                logger.info(f"  content 预览: {response.content[:200] if response.content else '(空)'}")
            if hasattr(response, 'tool_calls') and response.tool_calls:
                logger.info(f"  tool_calls 数量: {len(response.tool_calls)}")
                for tc_idx, tc in enumerate(response.tool_calls):
                    logger.info(f"    [{tc_idx+1}] {tc.get('name', 'unknown')}: {tc.get('args', {})}")
            logger.info(f"=" * 100)
            logger.info(f"💬 [{self.agent_id}] LLM响应完成")

            # 检查是否有工具调用
            if hasattr(response, 'tool_calls') and response.tool_calls:
                logger.info(f"🔧 [{self.agent_id}] 检测到 {len(response.tool_calls)} 个工具调用")

                # 执行所有工具调用
                tool_messages = self._execute_tool_calls(response.tool_calls)

                # 构建新的消息历史
                current_messages = current_messages + [response] + tool_messages

                # 添加分析提示词（如果提供）
                if analysis_prompt:
                    logger.info(f"📝 [{self.agent_id}] 添加分析提示词，长度: {len(analysis_prompt)} 字符")
                    current_messages.append(HumanMessage(content=analysis_prompt))
                else:
                    # 如果没有提供 analysis_prompt，添加默认的报告生成提示
                    logger.warning(f"⚠️ [{self.agent_id}] 未提供 analysis_prompt，使用默认提示")
                    default_prompt = """✅ 工具调用已完成，所有需要的数据都已获取。

🚫 **严格禁止再次调用工具**

📝 **现在请立即执行**：
基于上述工具返回的真实数据，按照之前的分析要求和输出格式，直接撰写完整的分析报告。

⚠️ **重要提醒**：
- 不要返回任何工具调用（tool_calls）
- 不要说"我需要调用工具"或"让我先获取数据"
- 直接输出中文分析报告内容

请立即开始撰写报告："""
                    current_messages.append(HumanMessage(content=default_prompt))

                # 再次调用 LLM（不绑定工具，强制生成报告）
                logger.info(f"📝 [{self.agent_id}] 工具执行完成，生成最终报告...")
                logger.info(f"📝 [{self.agent_id}] 当前消息数量: {len(current_messages)}")

                # 详细打印最终报告生成前的消息
                logger.info(f"=" * 100)
                logger.info(f"📋 [{self.agent_id}] 最终报告生成 - 消息详情:")
                logger.info(f"=" * 100)
                for idx, msg in enumerate(current_messages):
                    msg_type = type(msg).__name__
                    if hasattr(msg, 'content'):
                        content_preview = msg.content[:200] if len(msg.content) > 200 else msg.content
                        logger.info(f"  [{idx+1}] {msg_type}:")
                        logger.info(f"      内容长度: {len(msg.content)} 字符")
                        logger.info(f"      内容预览: {content_preview}")
                    elif hasattr(msg, 'tool_calls'):
                        logger.info(f"  [{idx+1}] {msg_type}:")
                        logger.info(f"      工具调用数量: {len(msg.tool_calls)}")
                        for tc_idx, tc in enumerate(msg.tool_calls):
                            logger.info(f"        [{tc_idx+1}] {tc.get('name', 'unknown')}: {tc.get('args', {})}")
                    else:
                        logger.info(f"  [{idx+1}] {msg_type}: {str(msg)[:200]}")
                logger.info(f"=" * 100)

                # 🔧 直接调用 LLM 生成报告（不绑定工具）
                # 注意：不使用 bind_tools([])，因为 DashScope 不接受空的 tools 数组
                logger.info(f"🔗 [{self.agent_id}] 直接调用 LLM 生成报告（无工具绑定）")
                
                max_retries = getattr(self.config, 'max_retries', 3)
                final_response = retry_sync(
                    self._llm.invoke,
                    current_messages,
                    max_retries=max_retries,
                    label=f"{self.agent_id}/report",
                    retryable=is_retryable,
                )

                # 打印最终响应详情
                logger.info(f"=" * 100)
                logger.info(f"📤 [{self.agent_id}] 最终报告响应详情:")
                logger.info(f"=" * 100)
                logger.info(f"  响应类型: {type(final_response).__name__}")
                if hasattr(final_response, 'content'):
                    logger.info(f"  content 长度: {len(final_response.content)} 字符")
                    logger.info(f"  content 预览: {final_response.content[:200] if final_response.content else '(空)'}")
                if hasattr(final_response, 'tool_calls') and final_response.tool_calls:
                    logger.info(f"  tool_calls 数量: {len(final_response.tool_calls)}")
                    for tc_idx, tc in enumerate(final_response.tool_calls):
                        logger.info(f"    [{tc_idx+1}] {tc.get('name', 'unknown')}: {tc.get('args', {})}")
                logger.info(f"=" * 100)

                # 检查是否还有 tool_calls（理论上不应该有，因为没有绑定工具）
                if hasattr(final_response, 'tool_calls') and final_response.tool_calls:
                    logger.warning(f"⚠️ [{self.agent_id}] 第二次调用仍返回 tool_calls: {len(final_response.tool_calls)} 个")
                    logger.warning(f"⚠️ [{self.agent_id}] LLM 没有理解指令，尝试添加更强烈的提示并重试")

                    # 添加更强烈的提示
                    retry_prompt = """🚨 **严重警告：你刚才返回了工具调用，这是错误的！**

❌ **禁止的行为**：
- 禁止返回任何 tool_calls
- 禁止说"我需要调用工具"
- 禁止说"让我先获取数据"

✅ **正确的行为**：
- 所有数据已经在上面的 ToolMessage 中
- 你现在唯一的任务是：撰写中文分析报告
- 直接输出报告文本内容

📝 **立即执行**：
基于上述工具返回的数据，按照之前的要求，直接撰写完整的分析报告。

现在开始撰写报告（只输出报告文本，不要有任何其他内容）："""
                    current_messages.append(HumanMessage(content=retry_prompt))

                    # 重试一次
                    logger.info(f"🔄 [{self.agent_id}] 重试生成报告...")

                    # 详细打印重试前的消息
                    logger.info(f"=" * 100)
                    logger.info(f"📋 [{self.agent_id}] 重试报告生成 - 消息详情:")
                    logger.info(f"=" * 100)
                    for idx, msg in enumerate(current_messages):
                        msg_type = type(msg).__name__
                        if hasattr(msg, 'content'):
                            content_preview = msg.content[:200] if len(msg.content) > 200 else msg.content
                            logger.info(f"  [{idx+1}] {msg_type}:")
                            logger.info(f"      内容长度: {len(msg.content)} 字符")
                            logger.info(f"      内容预览: {content_preview}")
                        elif hasattr(msg, 'tool_calls'):
                            logger.info(f"  [{idx+1}] {msg_type}:")
                            logger.info(f"      工具调用数量: {len(msg.tool_calls)}")
                            for tc_idx, tc in enumerate(msg.tool_calls):
                                logger.info(f"        [{tc_idx+1}] {tc.get('name', 'unknown')}: {tc.get('args', {})}")
                        else:
                            logger.info(f"  [{idx+1}] {msg_type}: {str(msg)[:200]}")
                    logger.info(f"=" * 100)

                    # 🔧 重试时直接调用 LLM（不绑定工具）
                    logger.info(f"🔗 [{self.agent_id}] 重试时直接调用 LLM（无工具绑定）")
                    
                    max_retries = getattr(self.config, 'max_retries', 3)
                    final_response = retry_sync(
                        self._llm.invoke,
                        current_messages,
                        max_retries=max_retries,
                        label=f"{self.agent_id}/retry-report",
                        retryable=is_retryable,
                    )

                    # 打印重试响应详情
                    logger.info(f"=" * 100)
                    logger.info(f"📤 [{self.agent_id}] 重试响应详情:")
                    logger.info(f"=" * 100)
                    logger.info(f"  响应类型: {type(final_response).__name__}")
                    if hasattr(final_response, 'content'):
                        logger.info(f"  content 长度: {len(final_response.content)} 字符")
                        logger.info(f"  content 预览: {final_response.content[:200] if final_response.content else '(空)'}")
                    if hasattr(final_response, 'tool_calls') and final_response.tool_calls:
                        logger.info(f"  tool_calls 数量: {len(final_response.tool_calls)}")
                        for tc_idx, tc in enumerate(final_response.tool_calls):
                            logger.info(f"    [{tc_idx+1}] {tc.get('name', 'unknown')}: {tc.get('args', {})}")
                    logger.info(f"=" * 100)

                    # 再次检查
                    if hasattr(final_response, 'tool_calls') and final_response.tool_calls:
                        logger.error(f"❌ [{self.agent_id}] 重试后仍返回 tool_calls，放弃")
                        return "分析报告生成失败：LLM 持续返回工具调用而不是报告内容。请更换模型或重试。"

                content = final_response.content if hasattr(final_response, 'content') else str(final_response)
                self._last_llm_debug = {
                    "response_type": type(final_response).__name__,
                    "final_response_content": content,
                    "tool_mode": True,
                    "tool_trace": list(self._last_tool_debug),
                }
                logger.info(f"✅ [{self.agent_id}] 报告生成完成，长度: {len(content)} 字符")
                logger.debug(f"🔍 [{self.agent_id}] 报告内容预览: {content[:200] if content else '(空)'}")
                if not content or len(content.strip()) == 0:
                    logger.warning(f"⚠️ [{self.agent_id}] 报告内容为空！final_response类型: {type(final_response)}, hasattr content: {hasattr(final_response, 'content')}")
                    if hasattr(final_response, 'content'):
                        logger.warning(f"⚠️ [{self.agent_id}] final_response.content值: {repr(final_response.content)}")
                    # 检查是否有 tool_calls
                    if hasattr(final_response, 'tool_calls'):
                        logger.warning(f"⚠️ [{self.agent_id}] final_response.tool_calls: {final_response.tool_calls}")
                    # 打印完整的响应对象
                    logger.warning(f"⚠️ [{self.agent_id}] final_response完整对象: {final_response}")
                return content
            else:
                # 没有工具调用，直接返回内容
                content = response.content if hasattr(response, 'content') else str(response)
                self._last_llm_debug = {
                    "response_type": type(response).__name__,
                    "final_response_content": content,
                    "tool_mode": False,
                    "tool_trace": list(self._last_tool_debug),
                }
                logger.info(f"📝 [{self.agent_id}] 直接响应（无工具调用），长度: {len(content)} 字符")
                return content

        # 达到最大迭代次数
        logger.warning(f"⚠️ [{self.agent_id}] 达到最大迭代次数 {max_iterations}")
        return f"分析未能完成（达到最大迭代次数 {max_iterations}）"

    def _execute_tool_calls(self, tool_calls: List[Dict]) -> List[ToolMessage]:
        """
        执行工具调用并返回 ToolMessage 列表

        Args:
            tool_calls: 工具调用列表

        Returns:
            List[ToolMessage]: 工具执行结果消息列表
        """
        tool_messages = []

        for tool_call in tool_calls:
            tool_name = tool_call.get('name')
            tool_args = tool_call.get('args', {})
            tool_id = tool_call.get('id')
            tool_success = False

            logger.info(f"🔧 [{self.agent_id}] 执行工具: {tool_name}")
            logger.info(f"🔧 [{self.agent_id}] 工具参数: {tool_args}")

            # 找到对应的工具并执行
            tool_result = None
            for tool in self._langchain_tools:
                if hasattr(tool, 'name') and tool.name == tool_name:
                    try:
                        logger.info(f"🔄 [{self.agent_id}] 开始调用工具 {tool_name}...")
                        logger.debug(f"🔍 [{self.agent_id}] 工具类型: {type(tool)}")
                        logger.debug(f"🔍 [{self.agent_id}] 工具 func: {getattr(tool, 'func', 'N/A')}")
                        
                        tool_result = tool.invoke(tool_args)
                        
                        # 🔥 检查返回的是否是协程对象（修复异步函数问题）
                        import asyncio
                        if asyncio.iscoroutine(tool_result):
                            logger.warning(f"⚠️ [{self.agent_id}] 工具 {tool_name} 返回协程对象，尝试等待完成...")
                            try:
                                # 尝试获取事件循环并等待协程
                                loop = asyncio.get_event_loop()
                                if loop.is_running():
                                    # 如果事件循环正在运行，需要在新线程中运行
                                    import threading
                                    result_container = {}
                                    exception_container = {}
                                    
                                    def run_coroutine():
                                        try:
                                            new_loop = asyncio.new_event_loop()
                                            asyncio.set_event_loop(new_loop)
                                            result_container['value'] = new_loop.run_until_complete(tool_result)
                                            new_loop.close()
                                        except Exception as e:
                                            exception_container['value'] = e
                                    
                                    thread = threading.Thread(target=run_coroutine, daemon=True)
                                    thread.start()
                                    thread.join(timeout=30)  # 30秒超时
                                    
                                    if thread.is_alive():
                                        raise TimeoutError("工具协程执行超时")
                                    if 'value' in exception_container:
                                        raise exception_container['value']
                                    tool_result = result_container.get('value')
                                else:
                                    tool_result = loop.run_until_complete(tool_result)
                            except RuntimeError:
                                # 没有事件循环，创建新的
                                tool_result = asyncio.run(tool_result)
                            logger.info(f"✅ [{self.agent_id}] 协程执行完成，结果类型: {type(tool_result).__name__}")

                        # 记录工具返回结果的详细信息
                        if isinstance(tool_result, str):
                            result_preview = tool_result[:200] + "..." if len(tool_result) > 200 else tool_result
                            logger.info(f"✅ [{self.agent_id}] 工具 {tool_name} 执行成功，返回长度: {len(tool_result)} 字符")
                            logger.info(f"📄 [{self.agent_id}] 工具 {tool_name} 返回预览: {result_preview}")
                        else:
                            logger.info(f"✅ [{self.agent_id}] 工具 {tool_name} 执行成功，返回类型: {type(tool_result).__name__}")
                            logger.info(f"📄 [{self.agent_id}] 工具 {tool_name} 返回内容: {str(tool_result)[:200]}...")
                        tool_success = True

                    except Exception as e:
                        logger.error(f"❌ [{self.agent_id}] 工具 {tool_name} 执行失败: {e}")
                        import traceback
                        logger.error(f"❌ [{self.agent_id}] 工具 {tool_name} 错误详情: {traceback.format_exc()}")
                        tool_result = f"工具执行失败: {str(e)}"
                        # 🔧 上报工具执行失败缺口（fire-and-forget，不阻塞）
                        try:
                            from core.tools.external.skill_gap_detector import SkillGapDetector
                            SkillGapDetector.report_gap(
                                gap_type="tool_execution_error",
                                tool_name=tool_name,
                                agent_id=self.agent_id,
                                error=str(e),
                                context={"tool_call_args": tool_args},
                            )
                        except Exception:
                            pass
                    break

            if tool_result is None:
                tool_result = f"未找到工具: {tool_name}"
                logger.warning(f"⚠️ [{self.agent_id}] {tool_result}")
                logger.warning(f"⚠️ [{self.agent_id}] 可用工具列表: {[t.name for t in self._langchain_tools]}")
                # 🔧 上报工具未找到缺口（fire-and-forget，不阻塞）
                try:
                    from core.tools.external.skill_gap_detector import SkillGapDetector
                    SkillGapDetector.report_gap(
                        gap_type="tool_not_found",
                        tool_name=tool_name,
                        agent_id=self.agent_id,
                        context={"tool_call_args": tool_args},
                    )
                except Exception:
                    pass

            tool_result_text = str(tool_result)
            self._last_tool_debug.append({
                "tool_name": tool_name,
                "tool_args": tool_args,
                "success": tool_success,
                "result_preview": tool_result_text[:800],
                "result_length": len(tool_result_text),
                "tool_call_id": tool_id,
            })

            # 创建工具消息
            tool_messages.append(ToolMessage(
                content=tool_result_text,
                tool_call_id=tool_id
            ))

        return tool_messages

    def _get_prompt_from_template(
        self,
        agent_type: str,
        agent_name: str,
        variables: Dict[str, Any],
        context: Any = None,
        fallback_prompt: Optional[str] = None,
        state: Optional[Dict[str, Any]] = None,
        prompt_type: str = "user"  # 🆕 新增参数：提示词类型（"user" 或 "system"）
    ) -> Optional[str]:
        """
        从模板系统获取提示词（通用方法）

        此方法被所有 Agent 基类共享，避免重复代码。
        自动从 state 中提取系统变量（如 current_price、industry 等）。

        支持流程专属提示词：会自动从 state 或 context 中提取 workflow_id，
        优先加载该流程的专属提示词，如果没有则回退到默认提示词。

        Args:
            agent_type: Agent 类型（如 "analysts_v2", "researchers_v2", "managers_v2", "trader_v2"）
            agent_name: Agent 名称（如 "market_analyst_v2", "bull_researcher_v2"）
            variables: 模板变量字典
            context: AgentContext 对象（包含 user_id、preference_id、workflow_id）
            fallback_prompt: 降级提示词
            state: 工作流状态（可选，用于提取系统变量和 workflow_id）
            prompt_type: 提示词类型（"user" 获取用户提示词，"system" 获取系统提示词）

        Returns:
            提示词文本，如果获取失败则返回 fallback_prompt
        """
        try:
            if prompt_type == "user":
                from tradingagents.utils.template_client import get_user_prompt as get_prompt_func
            else:
                from tradingagents.utils.template_client import get_agent_prompt as get_prompt_func
        except (ImportError, KeyError) as e:
            logger.warning(f"无法导入模板系统: {e}")
            return fallback_prompt

        try:
            # 🆕 自动从 state 中提取系统变量（由工作流引擎准备）
            if state:
                system_vars = [
                    "current_price", "industry", "market_name",
                    "currency_name", "currency_symbol", "current_date", "start_date",
                    # 🆕 行业/个股分析维度（Phase 1 维度注入）
                    "industry_dimensions", "industry_focus",
                    "stock_dimensions", "stock_special_notes",
                ]
                for var in system_vars:
                    if var in state and var not in variables:
                        variables[var] = state[var]
                        if var in ("industry_dimensions", "stock_dimensions"):
                            logger.info(f"🏭 [维度注入] 自动提取 {var}: {len(str(state[var]))} 字符")
                        else:
                            logger.info(f"📊 [系统变量] 自动提取 {var}: {state[var]}")

            # 🆕 注入已批准的成长记忆（如果工作流传入了 growth_memory_recall）
            if state and "growth_memory_recall" not in variables:
                recall = None
                runtime = state.get("_workflow_runtime")
                if isinstance(runtime, dict):
                    recall = runtime.get("growth_memory_recall")
                if not recall:
                    recall = state.get("growth_memory_recall")
                if recall:
                    variables["growth_memory_recall"] = recall

            # 🆕 分层提示词组装：始终注入三块（analysis_context_block / capability_block / task_block）
            # 设计文档 §5：通用分析也注入能力块；analysis_type 可推断
            industry = state.get("industry") if state else None
            stock_symbol = state.get("stock_symbol") if state else None
            task_description = state.get("task_description", "") if state else ""
            analysis_type = (state.get("analysis_type") if state else None) or (
                "stock" if stock_symbol else "industry" if industry else "general"
            )

            try:
                from app.services.prompt_assembly_service import get_prompt_assembly_service
                assembly_service = get_prompt_assembly_service()

                # 始终生成 analysis_context_block（general 时为空；策略 injection_mode=none 时也为空）
                if "analysis_context_block" not in variables:
                    context_block = assembly_service.build_analysis_context_block(
                        analysis_type=analysis_type,
                        industry=industry,
                        stock_symbol=stock_symbol,
                        agent_type=agent_type,
                        agent_name=agent_name,
                    )
                    variables["analysis_context_block"] = context_block
                    if context_block:
                        logger.info(f"📋 [分层组装] analysis_context_block 注入，长度: {len(context_block)}")

                # 始终生成 capability_block（策略可关闭；通用分析时也提供能力边界）
                if "capability_block" not in variables:
                    capability_block = assembly_service.build_capability_block(
                        analysis_type=analysis_type,
                        industry=industry,
                        stock_symbol=stock_symbol,
                        agent_type=agent_type,
                        agent_name=agent_name,
                    )
                    variables["capability_block"] = capability_block
                    if capability_block:
                        logger.info(f"🔧 [分层组装] capability_block 注入，长度: {len(capability_block)}")

                # 有任务描述时生成 task_block
                if task_description and "task_block" not in variables:
                    task_block = assembly_service.build_task_block(
                        task_description=task_description,
                        analysis_type=analysis_type,
                    )
                    variables["task_block"] = task_block
                    if task_block:
                        logger.info(f"🎯 [分层组装] task_block 注入，长度: {len(task_block)}")
            except Exception as e:
                logger.warning(f"⚠️ [分层组装] 生成块失败: {e}")
            # 保证模板中占位符有默认值（未注入时由 template_client 统一置空）
            variables.setdefault("analysis_context_block", "")
            variables.setdefault("capability_block", "")
            variables.setdefault("task_block", "")

            # 从 context 中提取 user_id、preference_id、workflow_id 和 node_id
            user_id = None
            preference_id = "neutral"
            workflow_id = None  # 🆕 流程专属提示词支持
            node_id = None      # 🆕 节点专属提示词支持

            # 🆕 优先从 state 中提取 workflow_id 和 node_id
            if state and 'workflow_id' in state:
                workflow_id = state['workflow_id']
                logger.info(f"📊 [workflow_id] 从 state 中提取: {workflow_id}")
            if state and 'node_id' in state:
                node_id = state['node_id']
                logger.info(f"📊 [node_id] 从 state 中提取: {node_id}")

            if context:
                # 🔍 诊断日志：打印 context 的类型和内容
                logger.info(f"🔍 [_get_prompt_from_template] context 类型: {type(context)}")
                if isinstance(context, dict):
                    logger.info(f"🔍 [_get_prompt_from_template] context 是字典，内容: {context}")
                    user_id = context.get("user_id")
                    preference_id = context.get("preference_id", "neutral")
                    # 🆕 从 context 中提取 workflow_id 和 node_id（如果 state 中没有）
                    if not workflow_id:
                        workflow_id = context.get("workflow_id")
                    if not node_id:
                        node_id = context.get("node_id")
                else:
                    logger.info(f"🔍 [_get_prompt_from_template] context 是对象，属性: {dir(context)}")
                    if hasattr(context, 'user_id'):
                        user_id = context.user_id
                    if hasattr(context, 'preference_id'):
                        preference_id = context.preference_id or "neutral"
                    # 🆕 从 context 对象中提取 workflow_id 和 node_id（如果 state 中没有）
                    if not workflow_id and hasattr(context, 'workflow_id'):
                        workflow_id = context.workflow_id
                    if not node_id and hasattr(context, 'node_id'):
                        node_id = context.node_id

                logger.info(f"🔍 [_get_prompt_from_template] 提取的 preference_id: {preference_id}, user_id: {user_id}, workflow_id: {workflow_id}, node_id: {node_id}")

            # 🔍 调试：打印传递给模板系统的变量
            logger.info(f"🔍 [_get_prompt_from_template] 准备传递给模板系统的变量 (共 {len(variables)} 个):")
            if not variables:
                logger.warning(f"⚠️ [_get_prompt_from_template] 变量字典为空！")
            else:
                for k, v in variables.items():
                    if isinstance(v, str) and len(v) > 100:
                        logger.info(f"  - {k}: {v[:100]}...")
                    else:
                        logger.info(f"  - {k}: {v}")
            
            # 🔍 诊断日志：打印传递给模板系统的参数
            logger.info(
                f"🔍 [_get_prompt_from_template] 调用模板系统参数: "
                f"agent_type={agent_type}, agent_name={agent_name}, "
                f"preference_id={preference_id}, user_id={user_id}, "
                f"workflow_id={workflow_id}, node_id={node_id}, variables数量={len(variables)}"
            )

            # 调用模板系统（🆕 支持流程专属提示词 + 节点专属提示词）
            prompt = get_prompt_func(
                agent_type=agent_type,
                agent_name=agent_name,
                variables=variables,
                preference_id=preference_id,
                user_id=user_id,
                fallback_prompt=fallback_prompt,
                context=context,
                workflow_id=workflow_id,  # 🆕 传递 workflow_id 用于加载流程专属提示词
                node_id=node_id           # 🆕 传递 node_id 用于同一 agent 不同节点的提示词区分
            )

            if prompt:
                logger.info(
                    f"✅ 从模板系统获取 {agent_name} {prompt_type} 提示词 "
                    f"(user_id={user_id}, preference_id={preference_id}, workflow_id={workflow_id}, node_id={node_id}, 长度={len(prompt)})"
                )
                # 🔍 诊断日志：打印提示词的前200字符，检查模板内容
                prompt_preview = prompt[:200] if len(prompt) > 200 else prompt
                logger.info(f"🔍 [_get_prompt_from_template] 提示词预览: {prompt_preview}")
                return prompt
            else:
                logger.warning(f"模板系统返回空提示词，使用降级提示词")
                return fallback_prompt

        except Exception as e:
            logger.warning(f"从模板系统获取提示词失败: {e}")
            return fallback_prompt

