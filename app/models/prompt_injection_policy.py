"""
Prompt 注入策略数据模型

按 Agent + 场景精细控制上下文注入规则：
- 是否注入行业/个股画像
- 注入粒度（none / summary / full）
- 是否继承行业画像（个股场景）
- 是否附带能力块
- 注入到模板的哪个字段
"""

from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field, ConfigDict

from app.utils.timezone import now_tz


class PromptInjectionPolicy(BaseModel):
    """
    Prompt 注入策略
    
    对应设计文档 §7.2，控制不同 Agent 在不同场景下如何注入上下文。
    """
    agent_type: str = Field(..., description="Agent 类型，如 analysts_v2")
    agent_name: str = Field(..., description="Agent 名称，如 market_analyst_v2")
    scope: str = Field(
        default="general",
        description="场景: general / industry / stock"
    )
    enabled: bool = Field(default=True, description="是否启用")
    injection_mode: str = Field(
        default="summary",
        description="注入粒度: none / summary / full"
    )
    inherit_industry_for_stock: bool = Field(
        default=True,
        description="个股分析时是否继承行业画像"
    )
    include_capability_block: bool = Field(
        default=True,
        description="是否附带能力边界说明块"
    )
    include_external_gap_notice: bool = Field(
        default=True,
        description="是否附带外部依赖提醒"
    )
    include_comparable_companies: bool = Field(
        default=True,
        description="是否注入可比公司"
    )
    inject_position: str = Field(
        default="analysis_requirements",
        description="注入到哪个模板字段: system_prompt / analysis_requirements / constraints"
    )
    version: int = Field(default=1, description="版本号")
    created_at: Optional[datetime] = Field(default_factory=now_tz)
    updated_at: Optional[datetime] = Field(default_factory=now_tz)

    model_config = ConfigDict(populate_by_name=True)


# === Request/Response 模型 ===

class PromptInjectionPolicyCreate(BaseModel):
    """创建策略请求"""
    agent_type: str = Field(..., description="Agent 类型")
    agent_name: str = Field(..., description="Agent 名称")
    scope: str = Field(default="general", description="场景")
    enabled: bool = True
    injection_mode: str = "summary"
    inherit_industry_for_stock: bool = True
    include_capability_block: bool = True
    include_external_gap_notice: bool = True
    include_comparable_companies: bool = True
    inject_position: str = "analysis_requirements"


class PromptInjectionPolicyUpdate(BaseModel):
    """更新策略请求（所有字段可选）"""
    enabled: Optional[bool] = None
    injection_mode: Optional[str] = None
    inherit_industry_for_stock: Optional[bool] = None
    include_capability_block: Optional[bool] = None
    include_external_gap_notice: Optional[bool] = None
    include_comparable_companies: Optional[bool] = None
    inject_position: Optional[str] = None
