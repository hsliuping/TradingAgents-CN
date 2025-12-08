# 提示词模版系统实现指南

## 📝 实现步骤详解

### Step 1: 创建模版存储结构

#### 1.1 创建目录
```bash
mkdir -p prompts/templates/{fundamentals,market,news,social}
mkdir -p prompts/schema
```

#### 1.2 模版文件示例

**prompts/templates/fundamentals/default.yaml**
```yaml
version: "1.0"
analyst_type: "fundamentals"
name: "基本面分析 - 默认模版"
description: "标准的基本面分析提示词，适合大多数股票分析场景"
created_at: "2024-01-01"
tags: ["default", "fundamentals", "standard"]
is_default: true

system_prompt: |
  你是一位专业的股票基本面分析师。
  ⚠️ 绝对强制要求：你必须调用工具获取真实数据！不允许任何假设或编造！
  
  任务：分析{company_name}（股票代码：{ticker}，{market_name}）
  
  📊 分析要求：
  - 基于真实数据进行深度基本面分析
  - 计算并提供合理价位区间（使用{currency_name}{currency_symbol}）
  - 分析当前股价是否被低估或高估
  - 提供基于基本面的目标价位建议
  - 包含PE、PB、PEG等估值指标分析
  - 结合市场特点进行分析

tool_guidance: |
  🔴 立即调用 get_stock_fundamentals_unified 工具
  参数：ticker='{ticker}', start_date='{start_date}', end_date='{current_date}'
  
  ✅ 工作流程：
  1. 如果消息历史中没有工具结果，立即调用工具
  2. 如果已经有工具结果，立即基于数据生成报告
  3. 不要重复调用工具！

analysis_requirements: |
  - 公司基本信息和财务数据分析
  - PE、PB、PEG等估值指标分析
  - 当前股价是否被低估或高估的判断
  - 合理价位区间和目标价位建议
  - 基于基本面的投资建议（买入/持有/卖出）

output_format: |
  # 公司基本信息
  - 公司名称：{company_name}
  - 股票代码：{ticker}
  
  ## 财务数据分析
  [详细的财务分析]
  
  ## 估值指标分析
  [PE、PB、PEG分析]
  
  ## 投资建议
  [明确的买入/持有/卖出建议]

constraints:
  forbidden:
    - "不允许假设数据"
    - "不允许编造公司信息"
    - "不允许直接回答而不调用工具"
    - "不允许使用英文投资建议"
  required:
    - "必须调用工具获取真实数据"
    - "必须使用中文撰写"
    - "必须提供具体的价位区间"
```

### Step 2: 创建模版管理器

**tradingagents/config/prompt_manager.py**

关键功能：
- 从YAML文件加载模版
- 验证模版格式
- 支持模版版本管理
- 提供模版列表和详情查询
- 支持自定义模版保存

### Step 3: 分析师集成

修改4个分析师文件：
- `fundamentals_analyst.py`
- `market_analyst.py`
- `news_analyst.py`
- `social_media_analyst.py`

集成方式：
```python
def create_fundamentals_analyst(llm, toolkit, template_name="default"):
    # 加载模版
    template = PromptTemplateManager.load_template("fundamentals", template_name)
    
    # 在分析师节点中使用模版
    system_prompt = template["system_prompt"]
    tool_guidance = template["tool_guidance"]
    # ... 使用模版内容
```

### Step 4: Web API 实现

**app/routers/prompts.py**

端点：
- `GET /api/prompts/templates/{analyst_type}` - 列表
- `GET /api/prompts/templates/{analyst_type}/{name}` - 详情
- `POST /api/prompts/templates/{analyst_type}` - 创建
- `PUT /api/prompts/templates/{analyst_type}/{name}` - 更新
- `DELETE /api/prompts/templates/{analyst_type}/{name}` - 删除
- `POST /api/prompts/templates/{analyst_type}/{name}/preview` - 预览

### Step 5: 前端集成

在分析参数中添加：
```typescript
interface AnalysisParameters {
  // ... 现有参数
  analyst_templates: {
    fundamentals?: string;  // 模版名称
    market?: string;
    news?: string;
    social?: string;
  }
}
```

## 🔑 关键设计决策

1. **YAML格式**: 易于编辑和版本控制
2. **模块化结构**: 每个分析师独立的模版目录
3. **版本管理**: 支持模版历史和回滚
4. **动态加载**: 运行时加载，支持热更新
5. **用户自定义**: 支持保存自定义模版到数据库

## 📊 模版变量

所有模版支持以下变量注入：
- `{ticker}` - 股票代码
- `{company_name}` - 公司名称
- `{market_name}` - 市场名称
- `{currency_name}` - 货币名称
- `{currency_symbol}` - 货币符号
- `{current_date}` - 当前日期
- `{start_date}` - 开始日期
- `{tool_names}` - 可用工具列表

