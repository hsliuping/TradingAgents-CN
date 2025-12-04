# 提示词模版系统 - 架构对比

## 📊 现有系统 vs 新系统

### 现有系统架构

```
分析师代码
    ↓
硬编码提示词
    ↓
LLM执行分析
    ↓
返回结果
```

**问题**:
- ❌ 提示词硬编码在代码中
- ❌ 修改提示词需要改代码
- ❌ 用户无法自定义分析师行为
- ❌ 无法A/B测试不同的提示词
- ❌ 无版本控制

### 新系统架构

```
用户选择模版
    ↓
Web API
    ↓
PromptTemplateManager
    ↓
加载YAML模版
    ↓
分析师代码
    ↓
注入模版内容
    ↓
LLM执行分析
    ↓
返回结果
```

**优势**:
- ✅ 提示词与代码分离
- ✅ 用户可自定义模版
- ✅ 支持多个预设模版
- ✅ 易于A/B测试
- ✅ 完整的版本控制
- ✅ 热更新支持

## 🔄 数据流对比

### 现有流程

```python
# fundamentals_analyst.py (硬编码)
system_message = (
    f"你是一位专业的股票基本面分析师。"
    f"⚠️ 绝对强制要求：你必须调用工具获取真实数据！..."
    # ... 200+ 行硬编码提示词
)

def create_fundamentals_analyst(llm, toolkit):
    def fundamentals_analyst_node(state):
        # 直接使用硬编码的提示词
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_message),
            ...
        ])
```

### 新流程

```python
# fundamentals_analyst.py (使用模版)
def create_fundamentals_analyst(llm, toolkit, template_name="default"):
    def fundamentals_analyst_node(state):
        # 1. 加载模版
        template = PromptTemplateManager.load_template(
            "fundamentals", 
            template_name
        )
        
        # 2. 提取模版内容
        system_prompt = template["system_prompt"]
        tool_guidance = template["tool_guidance"]
        analysis_requirements = template["analysis_requirements"]
        
        # 3. 组合提示词
        full_prompt = f"{system_prompt}\n{tool_guidance}\n{analysis_requirements}"
        
        # 4. 使用提示词
        prompt = ChatPromptTemplate.from_messages([
            ("system", full_prompt),
            ...
        ])
```

## 📁 文件结构对比

### 现有结构

```
tradingagents/agents/analysts/
├── fundamentals_analyst.py      (包含硬编码提示词)
├── market_analyst.py            (包含硬编码提示词)
├── news_analyst.py              (包含硬编码提示词)
└── social_media_analyst.py      (包含硬编码提示词)
```

### 新结构

```
tradingagents/
├── agents/analysts/
│   ├── fundamentals_analyst.py  (使用模版)
│   ├── market_analyst.py        (使用模版)
│   ├── news_analyst.py          (使用模版)
│   ├── social_media_analyst.py  (使用模版)
│   └── prompt_templates.py      (模版工具函数)
├── config/
│   └── prompt_manager.py        (模版管理器)

prompts/
├── templates/
│   ├── fundamentals/
│   │   ├── default.yaml
│   │   ├── conservative.yaml
│   │   └── aggressive.yaml
│   ├── market/
│   │   ├── default.yaml
│   │   ├── short_term.yaml
│   │   └── long_term.yaml
│   ├── news/
│   │   ├── default.yaml
│   │   ├── real_time.yaml
│   │   └── deep.yaml
│   └── social/
│       ├── default.yaml
│       ├── sentiment_focus.yaml
│       └── trend_focus.yaml
├── schema/
│   └── prompt_template_schema.json
└── README.md
```

## 🎯 功能对比

| 功能 | 现有系统 | 新系统 |
|------|--------|--------|
| 提示词管理 | 硬编码 | 文件+数据库 |
| 用户自定义 | ❌ | ✅ |
| 多个模版 | ❌ | ✅ |
| 版本控制 | ❌ | ✅ |
| 热更新 | ❌ | ✅ |
| A/B测试 | ❌ | ✅ |
| Web编辑 | ❌ | ✅ |
| 模版预览 | ❌ | ✅ |
| 模版分享 | ❌ | ✅ |

## 🔌 集成点

### 分析师创建函数

```python
# 现有
create_fundamentals_analyst(llm, toolkit)

# 新增
create_fundamentals_analyst(llm, toolkit, template_name="default")
```

### 分析API

```python
# 现有
POST /api/analysis
{
  "ticker": "000001",
  "selected_analysts": ["fundamentals", "market"]
}

# 新增
POST /api/analysis
{
  "ticker": "000001",
  "selected_analysts": ["fundamentals", "market"],
  "analyst_templates": {
    "fundamentals": "conservative",
    "market": "short_term"
  }
}
```

## 📈 迁移路径

### Phase 1: 并行运行
- 新系统与现有系统并行
- 默认使用现有系统
- 用户可选择使用新系统

### Phase 2: 逐步迁移
- 将硬编码提示词提取到模版
- 更新分析师代码
- 保持向后兼容

### Phase 3: 完全迁移
- 所有分析师使用模版系统
- 删除硬编码提示词
- 完整的模版管理功能

## 💡 使用场景

### 场景1: 用户自定义分析风格
```
用户 → 编辑模版 → 保存自定义模版 → 选择模版 → 执行分析
```

### 场景2: A/B测试
```
创建两个模版 → 分别执行分析 → 对比结果 → 选择最优模版
```

### 场景3: 多语言支持
```
创建中文模版 → 创建英文模版 → 用户选择语言 → 执行分析
```

### 场景4: 行业特定模版
```
创建科技行业模版 → 创建金融行业模版 → 用户选择行业 → 执行分析
```

