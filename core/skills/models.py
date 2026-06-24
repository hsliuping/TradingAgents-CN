"""
Skill 数据模型

混合标准：
- Agent Skills 标准字段：name, description（生态兼容）
- 扩展字段：parameters, returns, implementation（Function Calling 支持）
- 支持多种执行协议：python, http, mcp
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from datetime import datetime


# =============================================================================
# 执行协议定义
# =============================================================================

class ImplementationType(str, Enum):
    """执行协议类型"""
    PYTHON = "python"   # 内置 Python 函数
    HTTP = "http"       # 外部 HTTP API
    MCP = "mcp"         # MCP Server


class PythonImplementation(BaseModel):
    """Python 函数执行配置
    
    支持三种执行方式：
    1. module + function：调用项目内部已存在的 Python 函数
    2. code：直接执行一段 Python 代码（沙箱执行），适合外部导入的 Skill
    3. skill_dir + script_path：执行本地 Skill 包中的 Python 脚本（ClawHub/OpenClaw）
    """
    type: ImplementationType = ImplementationType.PYTHON
    module: Optional[str] = Field(default=None, description="Python 模块路径，如 'core.tools.implementations.market.stock_data'")
    function: Optional[str] = Field(default=None, description="函数名称，如 'get_stock_market_data_unified'")
    code: Optional[str] = Field(default=None, description="可直接执行的 Python 代码，优先于 module/function")
    script_path: Optional[str] = Field(default=None, description="本地 Skill 包内的脚本路径，如 'scripts/fetch_data.py'")
    skill_dir: Optional[str] = Field(default=None, description="本地 Skill 包目录")
    timeout: int = Field(default=60, description="脚本执行超时时间（秒）")
    is_async: bool = Field(default=False, description="是否为异步函数")


class HttpImplementation(BaseModel):
    """HTTP API 执行配置"""
    type: ImplementationType = ImplementationType.HTTP
    url: str = Field(..., description="API URL，支持 {param} 占位符")
    method: str = Field(default="GET", description="HTTP 方法: GET, POST, PUT, DELETE")
    headers: Optional[Dict[str, str]] = Field(default=None, description="请求头")
    body_template: Optional[Dict[str, Any]] = Field(default=None, description="请求体模板（POST/PUT）")
    auth: Optional[Dict[str, str]] = Field(default=None, description="认证配置")
    response_mapping: Optional[Dict[str, str]] = Field(
        default=None,
        description="响应字段映射，如 {'result': 'data.items'}"
    )
    timeout: int = Field(default=30, description="超时时间（秒）")


class McpImplementation(BaseModel):
    """MCP Server 执行配置"""
    type: ImplementationType = ImplementationType.MCP
    server_url: str = Field(..., description="MCP Server URL（sse/streamable_http）或命令路径（stdio）")
    tool_name: str = Field(..., description="MCP 工具名称")
    transport: str = Field(default="sse", description="传输协议: stdio, sse, streamable_http")


# 联合类型
SkillImplementation = Union[PythonImplementation, HttpImplementation, McpImplementation]


# =============================================================================
# Skill 参数与返回值
# =============================================================================

class SkillParameter(BaseModel):
    """Skill 参数定义（兼容 Agent Skills + Function Calling）"""
    name: str = Field(..., description="参数名称")
    type: str = Field(default="string", description="参数类型: string, integer, number, boolean, array, object")
    description: str = Field(default="", description="参数描述")
    required: bool = Field(default=True, description="是否必填")
    default: Optional[Any] = Field(default=None, description="默认值")
    enum: Optional[List[Any]] = Field(default=None, description="可选值列表")


class SkillReturns(BaseModel):
    """Skill 返回值定义"""
    type: str = Field(default="string", description="返回类型: string, object, array")
    description: str = Field(default="", description="返回值描述")
    json_schema: Optional[Dict[str, Any]] = Field(default=None, alias="schema", description="JSON Schema 定义（可选）")

    class Config:
        populate_by_name = True


# =============================================================================
# Skill 元数据（核心模型）
# =============================================================================

class SkillMetadata(BaseModel):
    """
    Skill 元数据定义
    
    混合标准：
    - Agent Skills 标准字段（name + description + markdown body）
    - 扩展字段（parameters + returns + implementation）
    """
    
    # ===== Agent Skills 标准字段 =====
    name: str = Field(..., description="Skill 唯一标识符（小写、连字符分隔，如 'get-stock-news'）")
    description: str = Field(..., description="Skill 描述（简明扼要说明做什么及何时使用）")
    
    # ===== Agent Skills 可选标准字段 =====
    allowed_tools: Optional[List[str]] = Field(default=None, description="限制 Skill 可使用的工具列表")
    
    # ===== 扩展元数据字段 =====
    version: str = Field(default="1.0.0", description="版本号")
    author: str = Field(default="", description="作者")
    category: str = Field(default="general", description="分类")
    tags: List[str] = Field(default_factory=list, description="标签列表")
    icon: str = Field(default="🔧", description="图标")
    color: str = Field(default="#95a5a6", description="颜色")
    
    # ===== Function Calling 扩展字段 =====
    when_to_use: str = Field(default="", description="何时使用此 Skill（详细的 LLM 调用指导）")
    parameters: List[SkillParameter] = Field(default_factory=list, description="结构化参数定义")
    returns: Optional[SkillReturns] = Field(default=None, description="返回值定义")
    examples: List[str] = Field(default_factory=list, description="使用示例")
    
    # ===== 执行实现 =====
    implementation: Optional[SkillImplementation] = Field(
        default=None,
        description="执行实现配置（python/http/mcp）。为 None 表示知识型 Skill"
    )
    
    # ===== Markdown 指令内容 =====
    instructions: str = Field(default="", description="SKILL.md 的 Markdown body 部分（自然语言指令）")
    
    # ===== 状态与配置 =====
    enabled: bool = Field(default=True, description="是否启用")
    fc_enabled: bool = Field(default=True, description="是否启用 Function Calling")
    is_builtin: bool = Field(default=False, description="是否为内置 Skill（从代码注册的工具转换而来）")
    source_file: Optional[str] = Field(default=None, description="来源文件路径（如 SKILL.md 路径）")
    
    # ===== 时间戳 =====
    created_at: Optional[datetime] = Field(default=None, description="创建时间")
    updated_at: Optional[datetime] = Field(default=None, description="更新时间")
    
    @property
    def is_executable(self) -> bool:
        """是否为可执行 Skill（有 implementation 且有 parameters）"""
        return self.implementation is not None
    
    @property
    def is_knowledge_only(self) -> bool:
        """是否为纯知识型 Skill（只有 instructions，无 implementation）"""
        return self.implementation is None
    
    @property
    def skill_type(self) -> str:
        """Skill 类型描述"""
        if self.is_knowledge_only:
            return "knowledge"
        if self.implementation:
            return self.implementation.type.value
        return "unknown"
    
    class Config:
        use_enum_values = True

