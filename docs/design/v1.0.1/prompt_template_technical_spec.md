# 提示词模版系统 - 技术规范

## 🏗️ 核心类设计

### PromptTemplateManager

```python
from typing import Dict, List, Optional
from pathlib import Path
import yaml
from datetime import datetime

class PromptTemplateManager:
    """提示词模版管理器"""
    
    def __init__(self, template_dir: str = "prompts/templates"):
        self.template_dir = Path(template_dir)
        self.cache = {}  # 模版缓存
        
    def load_template(
        self, 
        analyst_type: str, 
        template_name: str
    ) -> Dict:
        """
        加载指定的模版
        
        Args:
            analyst_type: 分析师类型 (fundamentals/market/news/social)
            template_name: 模版名称 (default/conservative/aggressive等)
            
        Returns:
            模版字典，包含所有配置
            
        Raises:
            FileNotFoundError: 模版文件不存在
            ValueError: 模版格式无效
        """
        cache_key = f"{analyst_type}:{template_name}"
        if cache_key in self.cache:
            return self.cache[cache_key]
            
        template_path = (
            self.template_dir / analyst_type / f"{template_name}.yaml"
        )
        
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")
            
        with open(template_path, 'r', encoding='utf-8') as f:
            template = yaml.safe_load(f)
            
        self.validate_template(template)
        self.cache[cache_key] = template
        return template
        
    def list_templates(self, analyst_type: str) -> List[Dict]:
        """列出某个分析师的所有模版"""
        analyst_dir = self.template_dir / analyst_type
        if not analyst_dir.exists():
            return []
            
        templates = []
        for yaml_file in analyst_dir.glob("*.yaml"):
            with open(yaml_file, 'r', encoding='utf-8') as f:
                template = yaml.safe_load(f)
                templates.append({
                    "name": template.get("name"),
                    "description": template.get("description"),
                    "is_default": template.get("is_default", False),
                    "tags": template.get("tags", [])
                })
        return templates
        
    def validate_template(self, template: Dict) -> bool:
        """验证模版格式"""
        required_fields = [
            "version", "analyst_type", "name", "description",
            "system_prompt", "tool_guidance", "analysis_requirements",
            "output_format", "constraints"
        ]
        
        for field in required_fields:
            if field not in template:
                raise ValueError(f"Missing required field: {field}")
                
        return True
        
    def render_template(
        self, 
        template: Dict, 
        **variables
    ) -> Dict:
        """
        渲染模版中的变量
        
        Args:
            template: 模版字典
            **variables: 要注入的变量 (ticker, company_name等)
            
        Returns:
            渲染后的模版
        """
        rendered = {}
        for key, value in template.items():
            if isinstance(value, str):
                rendered[key] = value.format(**variables)
            elif isinstance(value, dict):
                rendered[key] = {
                    k: v.format(**variables) if isinstance(v, str) else v
                    for k, v in value.items()
                }
            else:
                rendered[key] = value
        return rendered
```

## 📋 模版Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": [
    "version", "analyst_type", "name", "description",
    "system_prompt", "tool_guidance", "analysis_requirements",
    "output_format", "constraints"
  ],
  "properties": {
    "version": {
      "type": "string",
      "pattern": "^\\d+\\.\\d+$"
    },
    "analyst_type": {
      "type": "string",
      "enum": ["fundamentals", "market", "news", "social"]
    },
    "name": {
      "type": "string",
      "minLength": 1,
      "maxLength": 100
    },
    "description": {
      "type": "string",
      "maxLength": 500
    },
    "system_prompt": {
      "type": "string",
      "minLength": 50
    },
    "tool_guidance": {
      "type": "string",
      "minLength": 20
    },
    "analysis_requirements": {
      "type": "string",
      "minLength": 20
    },
    "output_format": {
      "type": "string",
      "minLength": 20
    },
    "constraints": {
      "type": "object",
      "properties": {
        "forbidden": {
          "type": "array",
          "items": {"type": "string"}
        },
        "required": {
          "type": "array",
          "items": {"type": "string"}
        }
      }
    },
    "tags": {
      "type": "array",
      "items": {"type": "string"}
    },
    "is_default": {
      "type": "boolean"
    }
  }
}
```

## 🔌 分析师集成接口

```python
def create_fundamentals_analyst(
    llm,
    toolkit,
    template_name: str = "default",
    template_manager: Optional[PromptTemplateManager] = None
):
    """
    创建基本面分析师
    
    Args:
        llm: 语言模型
        toolkit: 工具包
        template_name: 使用的模版名称
        template_manager: 模版管理器实例
    """
    if template_manager is None:
        template_manager = PromptTemplateManager()
        
    # 加载模版
    template = template_manager.load_template("fundamentals", template_name)
    
    def fundamentals_analyst_node(state):
        # 渲染模版变量
        rendered_template = template_manager.render_template(
            template,
            ticker=state["company_of_interest"],
            company_name=company_name,
            market_name=market_info["market_name"],
            currency_name=market_info["currency_name"],
            currency_symbol=market_info["currency_symbol"],
            current_date=state["trade_date"]
        )
        
        # 使用渲染后的模版
        system_prompt = rendered_template["system_prompt"]
        # ... 继续分析流程
```

## 🌐 API数据模型

```python
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class PromptTemplateResponse(BaseModel):
    """模版响应模型"""
    id: str
    analyst_type: str
    name: str
    description: str
    version: str
    is_default: bool
    tags: List[str]
    created_at: datetime
    updated_at: datetime

class PromptTemplateDetailResponse(PromptTemplateResponse):
    """模版详情响应"""
    system_prompt: str
    tool_guidance: str
    analysis_requirements: str
    output_format: str
    constraints: Dict

class CreatePromptTemplateRequest(BaseModel):
    """创建模版请求"""
    name: str
    description: str
    system_prompt: str
    tool_guidance: str
    analysis_requirements: str
    output_format: str
    constraints: Dict
    tags: Optional[List[str]] = []

class PromptTemplatePreviewRequest(BaseModel):
    """模版预览请求"""
    template: Dict
    variables: Dict  # 要注入的变量
```

## 📊 数据库模型 (可选)

```python
from sqlalchemy import Column, String, Text, DateTime, Boolean
from datetime import datetime

class PromptTemplateDB(Base):
    """数据库模型 - 用于保存自定义模版"""
    __tablename__ = "prompt_templates"
    
    id = Column(String(36), primary_key=True)
    analyst_type = Column(String(50), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    version = Column(String(10), default="1.0")
    system_prompt = Column(Text, nullable=False)
    tool_guidance = Column(Text, nullable=False)
    analysis_requirements = Column(Text, nullable=False)
    output_format = Column(Text, nullable=False)
    constraints = Column(JSON)
    tags = Column(JSON)
    is_default = Column(Boolean, default=False)
    is_custom = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(100))
```

## 🔄 版本管理

```python
class PromptTemplateVersion:
    """模版版本管理"""
    
    def save_version(self, template: Dict, version: str):
        """保存模版版本"""
        version_dir = self.template_dir / ".versions"
        version_dir.mkdir(exist_ok=True)
        
        version_file = (
            version_dir / 
            f"{template['analyst_type']}_{template['name']}_v{version}.yaml"
        )
        
        with open(version_file, 'w', encoding='utf-8') as f:
            yaml.dump(template, f, allow_unicode=True)
            
    def get_versions(self, analyst_type: str, template_name: str) -> List[str]:
        """获取模版的所有版本"""
        version_dir = self.template_dir / ".versions"
        pattern = f"{analyst_type}_{template_name}_v*.yaml"
        
        versions = []
        for file in version_dir.glob(pattern):
            version = file.stem.split('_v')[-1]
            versions.append(version)
        return sorted(versions)
```

## 🧪 测试用例

```python
def test_load_template():
    """测试加载模版"""
    manager = PromptTemplateManager()
    template = manager.load_template("fundamentals", "default")
    assert template["analyst_type"] == "fundamentals"
    assert "system_prompt" in template

def test_validate_template():
    """测试模版验证"""
    manager = PromptTemplateManager()
    invalid_template = {"name": "test"}
    with pytest.raises(ValueError):
        manager.validate_template(invalid_template)

def test_render_template():
    """测试模版渲染"""
    manager = PromptTemplateManager()
    template = {
        "system_prompt": "分析 {ticker} ({company_name})"
    }
    rendered = manager.render_template(
        template,
        ticker="000001",
        company_name="平安银行"
    )
    assert "000001" in rendered["system_prompt"]
```

