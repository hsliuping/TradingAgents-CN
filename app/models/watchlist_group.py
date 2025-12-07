"""
自选股分组相关数据模型
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.utils.timezone import now_tz


class WatchlistGroupCreate(BaseModel):
    """创建自选股分组请求"""
    name: str = Field(..., min_length=1, max_length=50, description="分组名称")
    description: str = Field(default="", max_length=200, description="分组描述")
    color: str = Field(default="#409EFF", description="分组颜色")
    icon: str = Field(default="folder", description="分组图标")
    
    # 分析参数（可选，如果不设置则使用全局默认值）
    analysis_depth: Optional[int] = Field(None, ge=1, le=5, description="分析深度（1-5级）")
    quick_analysis_model: Optional[str] = Field(None, description="快速分析模型")
    deep_analysis_model: Optional[str] = Field(None, description="深度分析模型")
    prompt_template_id: Optional[str] = Field(None, description="提示词模板ID")


class WatchlistGroupUpdate(BaseModel):
    """更新自选股分组请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=50, description="分组名称")
    description: Optional[str] = Field(None, max_length=200, description="分组描述")
    color: Optional[str] = Field(None, description="分组颜色")
    icon: Optional[str] = Field(None, description="分组图标")
    
    # 分析参数
    analysis_depth: Optional[int] = Field(None, ge=1, le=5, description="分析深度（1-5级）")
    quick_analysis_model: Optional[str] = Field(None, description="快速分析模型")
    deep_analysis_model: Optional[str] = Field(None, description="深度分析模型")
    prompt_template_id: Optional[str] = Field(None, description="提示词模板ID")


class WatchlistGroup(BaseModel):
    """自选股分组"""
    id: str = Field(..., description="分组ID")
    user_id: str = Field(..., description="用户ID")
    name: str = Field(..., description="分组名称")
    description: str = Field(default="", description="分组描述")
    color: str = Field(default="#409EFF", description="分组颜色")
    icon: str = Field(default="folder", description="分组图标")
    
    # 分组中的股票代码列表
    stock_codes: List[str] = Field(default_factory=list, description="股票代码列表")
    
    # 分析参数
    analysis_depth: Optional[int] = Field(None, description="分析深度（1-5级）")
    quick_analysis_model: Optional[str] = Field(None, description="快速分析模型")
    deep_analysis_model: Optional[str] = Field(None, description="深度分析模型")
    prompt_template_id: Optional[str] = Field(None, description="提示词模板ID")
    
    # 排序和状态
    sort_order: int = Field(default=0, description="排序顺序")
    is_active: bool = Field(default=True, description="是否启用")
    
    # 时间戳
    created_at: datetime = Field(default_factory=now_tz, description="创建时间")
    updated_at: datetime = Field(default_factory=now_tz, description="更新时间")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "group_123",
                "user_id": "user_456",
                "name": "科技股",
                "description": "关注的科技类股票",
                "color": "#409EFF",
                "icon": "cpu",
                "stock_codes": ["000001", "600519"],
                "analysis_depth": 3,
                "quick_analysis_model": "qwen-plus",
                "deep_analysis_model": "qwen-max",
                "prompt_template_id": "template_789",
                "sort_order": 0,
                "is_active": True
            }
        }


class AddStocksToGroupRequest(BaseModel):
    """添加股票到分组请求"""
    stock_codes: List[str] = Field(..., min_length=1, description="股票代码列表")


class RemoveStocksFromGroupRequest(BaseModel):
    """从分组移除股票请求"""
    stock_codes: List[str] = Field(..., min_length=1, description="股票代码列表")


class MoveStocksRequest(BaseModel):
    """移动股票到其他分组请求"""
    stock_codes: List[str] = Field(..., min_length=1, description="股票代码列表")
    target_group_id: str = Field(..., description="目标分组ID")

