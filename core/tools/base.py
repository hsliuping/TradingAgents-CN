"""
工具基类和装饰器

提供工具定义的基础设施
"""

import inspect
import logging
from typing import Any, Callable, Dict, List, Optional, get_type_hints
from abc import ABC, abstractmethod
from langchain_core.tools import tool as langchain_tool

logger = logging.getLogger(__name__)


class BaseTool(ABC):
    """
    工具基类
    
    所有自定义工具应继承此类
    
    示例:
        class MyTool(BaseTool):
            id = "my_tool"
            name = "我的工具"
            description = "工具描述"
            category = "custom"
            
            def execute(self, param1: str, param2: int) -> str:
                return f"结果: {param1} - {param2}"
    """
    
    # 工具元数据（子类必须定义）
    id: str = ""
    name: str = ""
    description: str = ""
    category: str = "general"
    
    # 可选配置
    is_online: bool = True
    timeout: int = 30
    rate_limit: Optional[int] = None
    
    @abstractmethod
    def execute(self, *args, **kwargs) -> Any:
        """
        执行工具逻辑
        
        子类必须实现此方法
        """
        pass
    
    def validate_params(self, **kwargs) -> bool:
        """
        验证参数（可选重写）
        
        Returns:
            True if valid, False otherwise
        """
        return True
    
    def to_langchain_tool(self):
        """转换为 LangChain Tool"""
        @langchain_tool
        def wrapped_tool(*args, **kwargs):
            if not self.validate_params(**kwargs):
                raise ValueError(f"Invalid parameters for tool {self.id}")
            return self.execute(*args, **kwargs)
        
        wrapped_tool.name = self.id
        wrapped_tool.description = self.description
        return wrapped_tool


def register_tool(
    tool_id: str,
    name: str = "",
    description: str = "",
    category: str = "general",
    is_online: bool = True,
    auto_register: bool = True,
    parameters: Optional[List] = None,
    timeout_tier: str = "",
    data_source_handling: str = "",
    **kwargs
):
    """
    工具注册装饰器

    用法1: 装饰函数
        @register_tool(
            tool_id="my_tool",
            name="我的工具",
            category="custom",
            data_source_handling="self_contained"
        )
        def my_tool_func(param1: str) -> str:
            return f"Result: {param1}"

    用法2: 装饰类
        @register_tool(
            tool_id="my_tool",
            name="我的工具",
            category="custom",
            data_source_handling="local_only"
        )
        class MyTool(BaseTool):
            def execute(self, param1: str) -> str:
                return f"Result: {param1}"

    Args:
        tool_id: 工具唯一ID
        name: 工具显示名称
        description: 工具描述
        category: 工具分类
        is_online: 是否需要在线
        auto_register: 是否自动注册到 ToolRegistry
        data_source_handling: 数据源处理方式标签 (self_contained / local_only / partial)，
            留空则由 register_function 根据 ToolMetadata 默认值处理
    """
    def decorator(obj):
        # 如果是类
        if isinstance(obj, type):
            # 设置元数据
            obj.id = tool_id
            obj.name = name or tool_id
            obj.description = description or obj.__doc__ or ""
            obj.category = category
            obj.is_online = is_online

            # 自动注册
            if auto_register:
                extra_kwargs = dict(kwargs)
                if data_source_handling:
                    extra_kwargs["data_source_handling"] = data_source_handling
                _auto_register_class(obj, **extra_kwargs)

            return obj

        # 如果是函数
        else:
            func = obj
            func._tool_id = tool_id
            func._tool_name = name or tool_id
            func._tool_description = description or func.__doc__ or ""
            func._tool_category = category
            func._tool_is_online = is_online
            func._tool_parameters = parameters
            func._tool_timeout_tier = timeout_tier

            if auto_register:
                extra_kwargs = dict(kwargs)
                if data_source_handling:
                    extra_kwargs["data_source_handling"] = data_source_handling
                _auto_register_function(func, parameters=parameters, timeout_tier=timeout_tier, **extra_kwargs)

            return func

    return decorator


def _auto_register_class(tool_class: type, **kwargs):
    """自动注册工具类到 ToolRegistry"""
    try:
        from core.tools.registry import ToolRegistry
        
        registry = ToolRegistry()
        
        # 创建实例
        instance = tool_class()
        
        # 注册
        registry.register_function(
            tool_id=tool_class.id,
            func=instance.execute,
            name=tool_class.name,
            category=tool_class.category,
            description=tool_class.description,
            is_online=tool_class.is_online,
            **kwargs
        )
        
        logger.debug(f"自动注册工具类: {tool_class.id}")
    except Exception as e:
        logger.warning(f"自动注册工具类失败: {e}")


def _extract_parameters_from_signature(func: Callable) -> List:
    """
    从函数签名自动提取参数定义列表。

    支持:
    - Annotated[str, "描述"] → ToolParameter(name=..., type="string", description="描述")
    - 普通类型 str, int, float, bool → 自动映射
    - 默认值 → required=False, default=值
    """
    from core.tools.config import ToolParameter

    _type_map = {
        "str": "string",
        "int": "integer",
        "float": "number",
        "bool": "boolean",
        "list": "array",
        "dict": "object",
    }

    params = []
    # 获取原始函数（unwrap @tool 等装饰器）
    raw_func = inspect.unwrap(func)
    sig = inspect.signature(raw_func)

    try:
        hints = get_type_hints(raw_func, include_extras=True)
    except Exception:
        hints = {}

    for name, param in sig.parameters.items():
        if name in ("self", "cls", "return"):
            continue

        hint = hints.get(name)
        description = ""
        base_type = "string"

        # 处理 Annotated[Type, "description"]
        if hint is not None and hasattr(hint, "__metadata__"):
            # Annotated type
            base = getattr(hint, "__origin__", hint)
            if hasattr(hint, "__args__") and hint.__args__:
                base = hint.__args__[0]
            base_type = _type_map.get(getattr(base, "__name__", str(base)), "string")
            # 从 metadata 提取描述
            for meta in hint.__metadata__:
                if isinstance(meta, str):
                    description = meta
                    break
        elif hint is not None:
            type_name = getattr(hint, "__name__", str(hint))
            base_type = _type_map.get(type_name, "string")

        has_default = param.default is not inspect.Parameter.empty
        params.append(ToolParameter(
            name=name,
            type=base_type,
            description=description or f"参数 {name}",
            required=not has_default,
            default=param.default if has_default else None,
        ))

    return params


def _auto_register_function(func: Callable, parameters: Optional[List] = None, timeout_tier: str = "", **kwargs):
    """自动注册工具函数到 ToolRegistry"""
    try:
        from core.tools.registry import ToolRegistry

        registry = ToolRegistry()

        if parameters is None:
            extracted = _extract_parameters_from_signature(func)
            if extracted:
                parameters = extracted
                logger.debug(f"自动提取 {func._tool_id} 的 {len(extracted)} 个参数定义")

        registry.register_function(
            tool_id=func._tool_id,
            func=func,
            name=func._tool_name,
            category=func._tool_category,
            description=func._tool_description,
            is_online=func._tool_is_online,
            parameters=parameters,
            timeout_tier=timeout_tier,
            **kwargs
        )

        logger.info(f"✅ 自动注册工具函数: {func._tool_id}")
    except Exception as e:
        logger.error(f"❌ 自动注册工具函数失败 ({getattr(func, '_tool_id', 'unknown')}): {e}", exc_info=True)

