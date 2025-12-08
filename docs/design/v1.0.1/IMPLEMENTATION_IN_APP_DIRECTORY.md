# 在app目录中实现模板管理功能

## 📋 概述

本文档说明如何在 `C:\TradingAgentsCN\app` 目录中实现提示词模板管理功能。

**架构说明**:
- **`app/`** - 后端API和核心功能实现（模板管理、用户管理等）
- **`tradingagents/`** - 调用`app/`中实现的功能的Agent模块

---

## 🗂️ 实现目录结构

```
app/
├── models/
│   ├── user.py                    # 现有用户模型 (扩展preferences)
│   ├── prompt_template.py         # 新增: 模板模型
│   ├── analysis_preference.py     # 新增: 分析偏好模型
│   └── template_history.py        # 新增: 历史记录模型
│
├── services/
│   ├── user_service.py            # 现有用户服务
│   ├── prompt_template_service.py # 新增: 模板服务
│   ├── analysis_preference_service.py # 新增: 偏好服务
│   └── template_history_service.py # 新增: 历史记录服务
│
├── routers/
│   ├── auth_db.py                 # 现有认证路由
│   ├── prompt_templates.py        # 新增: 模板API路由
│   ├── analysis_preferences.py    # 新增: 偏好API路由
│   └── template_history.py        # 新增: 历史记录API路由
│
└── schemas/
    ├── prompt_template.py         # 新增: 模板请求/响应模式
    ├── analysis_preference.py     # 新增: 偏好请求/响应模式
    └── template_history.py        # 新增: 历史记录请求/响应模式
```

---

## 📊 数据模型实现

### 1. 分析偏好模型 (app/models/analysis_preference.py)
```python
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from app.utils.timezone import now_tz
from bson import ObjectId

class AnalysisPreference(BaseModel):
    """分析偏好模型"""
    id: Optional[str] = Field(None, alias="_id")
    user_id: str  # 关联到users._id
    preference_type: str  # 'aggressive', 'neutral', 'conservative'
    description: str = ""
    risk_level: float = 0.5  # 0.0-1.0
    confidence_threshold: float = 0.7  # 0.0-1.0
    position_size_multiplier: float = 1.0  # 0.5-2.0
    decision_speed: str = "normal"  # 'fast', 'normal', 'slow'
    is_default: bool = False
    created_at: datetime = Field(default_factory=now_tz)
    updated_at: datetime = Field(default_factory=now_tz)
```

### 2. 提示词模板模型 (app/models/prompt_template.py)
```python
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from app.utils.timezone import now_tz

class PromptTemplate(BaseModel):
    """提示词模板模型"""
    id: Optional[str] = Field(None, alias="_id")
    agent_type: str  # 'analysts', 'researchers', 'debators', 'managers', 'trader'
    agent_name: str
    template_name: str
    preference_type: Optional[str] = None  # null表示通用
    content: Dict[str, Any] = {
        "system_prompt": "",
        "tool_guidance": "",
        "analysis_requirements": "",
        "output_format": "",
        "constraints": ""
    }
    is_system: bool = True
    created_by: Optional[str] = None  # null表示系统模板
    created_at: datetime = Field(default_factory=now_tz)
    updated_at: datetime = Field(default_factory=now_tz)
    version: int = 1
```

### 3. 模板历史模型 (app/models/template_history.py)
```python
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from app.utils.timezone import now_tz

class TemplateHistory(BaseModel):
    """模板历史记录模型"""
    id: Optional[str] = Field(None, alias="_id")
    template_id: str
    user_id: Optional[str] = None  # null表示系统模板
    version: int
    content: Dict[str, Any]
    change_description: str = ""
    change_type: str  # 'create', 'update', 'delete', 'restore'
    created_at: datetime = Field(default_factory=now_tz)
```

---

## 🔧 服务层实现

### 1. 分析偏好服务 (app/services/analysis_preference_service.py)
```python
from typing import List, Optional
from pymongo import MongoClient
from app.core.config import settings
from app.models.analysis_preference import AnalysisPreference

class AnalysisPreferenceService:
    def __init__(self):
        self.client = MongoClient(settings.MONGO_URI)
        self.db = self.client[settings.MONGO_DB]
        self.collection = self.db.analysis_preferences
    
    async def create_preference(self, preference: AnalysisPreference) -> AnalysisPreference:
        """创建分析偏好"""
        result = self.collection.insert_one(preference.dict(exclude={"id"}))
        preference.id = str(result.inserted_id)
        return preference
    
    async def get_user_preferences(self, user_id: str) -> List[AnalysisPreference]:
        """获取用户的所有偏好"""
        prefs = self.collection.find({"user_id": user_id})
        return [AnalysisPreference(**p) for p in prefs]
    
    async def get_default_preference(self, user_id: str) -> Optional[AnalysisPreference]:
        """获取用户的默认偏好"""
        pref = self.collection.find_one({"user_id": user_id, "is_default": True})
        return AnalysisPreference(**pref) if pref else None
    
    async def update_preference(self, preference_id: str, updates: dict) -> AnalysisPreference:
        """更新偏好"""
        self.collection.update_one({"_id": ObjectId(preference_id)}, {"$set": updates})
        pref = self.collection.find_one({"_id": ObjectId(preference_id)})
        return AnalysisPreference(**pref)
    
    async def delete_preference(self, preference_id: str) -> bool:
        """删除偏好"""
        result = self.collection.delete_one({"_id": ObjectId(preference_id)})
        return result.deleted_count > 0
```

### 2. 提示词模板服务 (app/services/prompt_template_service.py)
```python
from typing import List, Optional
from pymongo import MongoClient
from app.core.config import settings
from app.models.prompt_template import PromptTemplate

class PromptTemplateService:
    def __init__(self):
        self.client = MongoClient(settings.MONGO_URI)
        self.db = self.client[settings.MONGO_DB]
        self.collection = self.db.prompt_templates
    
    async def create_template(self, template: PromptTemplate) -> PromptTemplate:
        """创建模板"""
        result = self.collection.insert_one(template.dict(exclude={"id"}))
        template.id = str(result.inserted_id)
        return template
    
    async def get_templates_by_agent(self, agent_type: str, agent_name: str) -> List[PromptTemplate]:
        """获取Agent的所有模板"""
        templates = self.collection.find({"agent_type": agent_type, "agent_name": agent_name})
        return [PromptTemplate(**t) for t in templates]
    
    async def get_template_by_preference(self, agent_type: str, agent_name: str, 
                                        preference_type: str) -> Optional[PromptTemplate]:
        """获取特定偏好的模板"""
        template = self.collection.find_one({
            "agent_type": agent_type,
            "agent_name": agent_name,
            "preference_type": preference_type
        })
        return PromptTemplate(**template) if template else None
    
    async def update_template(self, template_id: str, updates: dict) -> PromptTemplate:
        """更新模板"""
        self.collection.update_one({"_id": ObjectId(template_id)}, {"$set": updates})
        template = self.collection.find_one({"_id": ObjectId(template_id)})
        return PromptTemplate(**template)
```

### 3. 模板历史服务 (app/services/template_history_service.py)
```python
from typing import List
from pymongo import MongoClient
from app.core.config import settings
from app.models.template_history import TemplateHistory

class TemplateHistoryService:
    def __init__(self):
        self.client = MongoClient(settings.MONGO_URI)
        self.db = self.client[settings.MONGO_DB]
        self.collection = self.db.template_history
    
    async def record_change(self, history: TemplateHistory) -> TemplateHistory:
        """记录模板修改"""
        result = self.collection.insert_one(history.dict(exclude={"id"}))
        history.id = str(result.inserted_id)
        return history
    
    async def get_template_history(self, template_id: str) -> List[TemplateHistory]:
        """获取模板的修改历史"""
        histories = self.collection.find({"template_id": template_id}).sort("version", -1)
        return [TemplateHistory(**h) for h in histories]
    
    async def get_version(self, template_id: str, version: int) -> Optional[TemplateHistory]:
        """获取特定版本"""
        history = self.collection.find_one({"template_id": template_id, "version": version})
        return TemplateHistory(**history) if history else None
```

---

## 🔌 API路由实现

### 1. 分析偏好API (app/routers/analysis_preferences.py)
```python
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.services.analysis_preference_service import AnalysisPreferenceService
from app.models.analysis_preference import AnalysisPreference

router = APIRouter(prefix="/api/v1/preferences", tags=["preferences"])
service = AnalysisPreferenceService()

@router.post("", response_model=AnalysisPreference)
async def create_preference(preference: AnalysisPreference):
    """创建分析偏好"""
    return await service.create_preference(preference)

@router.get("/user/{user_id}", response_model=List[AnalysisPreference])
async def get_user_preferences(user_id: str):
    """获取用户的所有偏好"""
    return await service.get_user_preferences(user_id)

@router.get("/user/{user_id}/default", response_model=AnalysisPreference)
async def get_default_preference(user_id: str):
    """获取用户的默认偏好"""
    pref = await service.get_default_preference(user_id)
    if not pref:
        raise HTTPException(status_code=404, detail="Default preference not found")
    return pref

@router.put("/{preference_id}", response_model=AnalysisPreference)
async def update_preference(preference_id: str, updates: dict):
    """更新偏好"""
    return await service.update_preference(preference_id, updates)

@router.delete("/{preference_id}")
async def delete_preference(preference_id: str):
    """删除偏好"""
    success = await service.delete_preference(preference_id)
    if not success:
        raise HTTPException(status_code=404, detail="Preference not found")
    return {"message": "Preference deleted"}
```

### 2. 提示词模板API (app/routers/prompt_templates.py)
```python
from fastapi import APIRouter, HTTPException
from typing import List
from app.services.prompt_template_service import PromptTemplateService
from app.models.prompt_template import PromptTemplate

router = APIRouter(prefix="/api/v1/templates", tags=["templates"])
service = PromptTemplateService()

@router.post("", response_model=PromptTemplate)
async def create_template(template: PromptTemplate):
    """创建模板"""
    return await service.create_template(template)

@router.get("/agent/{agent_type}/{agent_name}", response_model=List[PromptTemplate])
async def get_agent_templates(agent_type: str, agent_name: str):
    """获取Agent的所有模板"""
    return await service.get_templates_by_agent(agent_type, agent_name)

@router.get("/agent/{agent_type}/{agent_name}/{preference_type}", response_model=PromptTemplate)
async def get_template_by_preference(agent_type: str, agent_name: str, preference_type: str):
    """获取特定偏好的模板"""
    template = await service.get_template_by_preference(agent_type, agent_name, preference_type)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template

@router.put("/{template_id}", response_model=PromptTemplate)
async def update_template(template_id: str, updates: dict):
    """更新模板"""
    return await service.update_template(template_id, updates)
```

---

## 📝 集成步骤

### Step 1: 创建模型文件
```bash
# 创建新的模型文件
touch app/models/analysis_preference.py
touch app/models/prompt_template.py
touch app/models/template_history.py
```

### Step 2: 创建服务文件
```bash
# 创建新的服务文件
touch app/services/analysis_preference_service.py
touch app/services/prompt_template_service.py
touch app/services/template_history_service.py
```

### Step 3: 创建路由文件
```bash
# 创建新的路由文件
touch app/routers/analysis_preferences.py
touch app/routers/prompt_templates.py
touch app/routers/template_history.py
```

### Step 4: 在main.py中注册路由
```python
# app/main.py
from app.routers import analysis_preferences, prompt_templates, template_history

app.include_router(analysis_preferences.router)
app.include_router(prompt_templates.router)
app.include_router(template_history.router)
```

### Step 5: 创建数据库集合和索引
```bash
# 执行初始化脚本
python scripts/create_template_collections.py
```

---

## 🚀 tradingagents中的使用

在 `tradingagents/` 中，Agent可以这样调用模板：

```python
# tradingagents/agents/analysts/market_analyst.py
from app.services.prompt_template_service import PromptTemplateService
from app.services.analysis_preference_service import AnalysisPreferenceService

class MarketAnalyst:
    def __init__(self, user_id: str, preference_type: str = "neutral"):
        self.template_service = PromptTemplateService()
        self.preference_service = AnalysisPreferenceService()
        self.user_id = user_id
        self.preference_type = preference_type
    
    async def get_system_prompt(self):
        """获取系统提示词"""
        template = await self.template_service.get_template_by_preference(
            agent_type="analysts",
            agent_name="market_analyst",
            preference_type=self.preference_type
        )
        return template.content["system_prompt"] if template else ""
```

---

**版本**: v1.0.1  
**状态**: 实现指南  
**下一步**: 开始实现

