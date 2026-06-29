from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CapabilityDocument(BaseModel):
    capability_id: str = Field(..., description="能力唯一标识")
    registry_tool_id: Optional[str] = Field(default=None, description="若可绑定，对应注册表 tool_id")
    source_type: str = Field(..., description="builtin_tool / mcp_tool / skill / external_skill")
    status: str = Field(default="active", description="active / draft / disabled")
    bindable: bool = Field(default=False, description="是否可直接绑定")
    fc_enabled: bool = Field(default=True, description="是否允许 function calling")
    category: str = Field(default="", description="能力分类")
    name: str = Field(default="", description="显示名称")
    label: str = Field(default="", description="用于 UI / prompt 展示的标签")
    description: str = Field(default="", description="能力描述")
    when_to_use: str = Field(default="", description="适用场景")
    when_not_to_use: str = Field(default="", description="不适用场景")
    returns: str = Field(default="", description="返回结构描述")
    related_tools: List[str] = Field(default_factory=list, description="相关能力")
    coverage_terms: List[str] = Field(default_factory=list, description="领域覆盖关键词")
    retrieval_text: str = Field(default="", description="写入向量库的检索文本")
    data_source: str = Field(default="", description="底层数据源")
    capability_tags: List[str] = Field(default_factory=list, description="结构化能力标签")
    tool_role_hint: str = Field(default="", description="工具角色提示：primary/specialized/supporting/generic/fallback")
    output_shape: str = Field(default="", description="输出形态：structured_metrics/report/text 等")
    preferred_for: List[str] = Field(default_factory=list, description="优先适用的能力原语")
    not_replacement_for: List[str] = Field(default_factory=list, description="不能替代的能力原语")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="附加元数据")


class CapabilitySearchHit(BaseModel):
    capability: CapabilityDocument
    score: float = Field(default=0.0, description="相似度分数，越大越相关")


class CapabilityIndexSyncResult(BaseModel):
    collection_name: str
    fingerprint: str
    total_documents: int = 0
    indexed_documents: int = 0
    skipped_documents: int = 0
    vector_backend: str = ""
    sync_mode: str = "full_rebuild"
