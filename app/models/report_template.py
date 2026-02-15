"""
报告模板模型

支持为不同工作流配置不同的报告格式和输出结构。
每个工作流可以关联一个报告模板，定义该工作流产出的报告格式。

使用场景：
- 初选流程：简洁的通过/不通过判断报告
- 深度分析：详细的投资分析报告
- 持仓检查：持仓风险评估报告
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from bson import ObjectId


class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, *args, **kwargs):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, *args, **kwargs):
        return {"type": "string"}


class OutputField(BaseModel):
    """报告输出字段定义"""
    name: str = Field(..., description="字段名称")
    type: str = Field(..., description="字段类型: string, number, boolean, array, object")
    description: str = Field("", description="字段说明")
    required: bool = Field(True, description="是否必填")
    default: Optional[Any] = Field(None, description="默认值")
    # 对于 string 类型，可以定义枚举值
    enum: Optional[List[str]] = Field(None, description="枚举值（仅 string 类型）")
    # 对于 number 类型，可以定义范围
    min_value: Optional[float] = Field(None, description="最小值（仅 number 类型）")
    max_value: Optional[float] = Field(None, description="最大值（仅 number 类型）")


class ReportTemplate(BaseModel):
    """
    报告模板模型
    
    定义工作流的报告输出格式，包括：
    - 输出字段定义（output_schema）
    - 报告生成提示词（generator_prompt）
    - 摘要和展示配置
    """
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    
    # 基本信息
    template_id: str = Field(..., description="模板唯一标识符")
    name: str = Field(..., description="模板名称")
    description: str = Field("", description="模板描述")
    
    # 关联的工作流
    workflow_id: str = Field(..., description="关联的工作流ID")
    
    # 输出结构定义
    output_schema: List[OutputField] = Field(
        default_factory=list, 
        description="报告输出字段定义"
    )
    
    # 报告生成器提示词
    generator_prompt: str = Field(
        "", 
        description="用于 LLM 生成报告的提示词模板，可使用 {agent_outputs} 等变量"
    )
    
    # 摘要配置
    summary_fields: List[str] = Field(
        default_factory=list,
        description="用于生成摘要的字段列表"
    )
    
    # 展示配置
    display_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="前端展示配置（字段顺序、样式等）"
    )
    
    # 状态
    status: str = Field("active", description="状态: active, inactive")
    
    # 元数据
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[str] = Field(None, description="创建者用户ID")
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class ReportTemplateCreate(BaseModel):
    """创建报告模板请求"""
    template_id: str
    name: str
    description: str = ""
    workflow_id: str
    output_schema: List[OutputField] = Field(default_factory=list)
    generator_prompt: str = ""
    summary_fields: List[str] = Field(default_factory=list)
    display_config: Dict[str, Any] = Field(default_factory=dict)


class ReportTemplateUpdate(BaseModel):
    """更新报告模板请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    output_schema: Optional[List[OutputField]] = None
    generator_prompt: Optional[str] = None
    summary_fields: Optional[List[str]] = None
    display_config: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


class ReportTemplateResponse(BaseModel):
    """报告模板响应"""
    id: str
    template_id: str
    name: str
    description: str
    workflow_id: str
    output_schema: List[OutputField]
    generator_prompt: str
    summary_fields: List[str]
    display_config: Dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None

