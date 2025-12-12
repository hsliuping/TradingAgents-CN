# 研究深度统一为5个级别

## 📋 问题描述

在之前的实现中，前端（frontend）和后端（app）的研究深度级别不一致：
- **Web界面（web/）**: 支持5个级别（1-5级）
- **Frontend界面（frontend/）**: 只支持3个级别（快速、标准、深度）
- **后端服务（app/）**: 只支持3个级别（快速、标准、深度）

这导致用户体验不一致，且无法充分利用系统的分析能力。

## ✅ 解决方案

将前端和后端统一为5个研究深度级别，与Web界面保持一致。

### 5个研究深度级别

| 级别 | 名称 | 辩论轮次 | 风险讨论 | 记忆 | 在线工具 | 预期耗时 | 适用场景 |
|------|------|----------|----------|------|----------|----------|----------|
| 1级 | 快速分析 | 1轮 | 1轮 | ❌ | ❌ | 2-4分钟 | 日常快速决策、市场概览 |
| 2级 | 基础分析 | 1轮 | 1轮 | ✅ | ✅ | 4-6分钟 | 常规投资决策、基础研究 |
| 3级 | 标准分析 | 1轮 | 2轮 | ✅ | ✅ | 6-10分钟 | 重要投资决策（推荐） |
| 4级 | 深度分析 | 2轮 | 2轮 | ✅ | ✅ | 10-15分钟 | 多轮辩论，深度研究 |
| 5级 | 全面分析 | 3轮 | 3轮 | ✅ | ✅ | 15-25分钟 | 最全面的分析报告 |

### 级别说明

#### ⚡ 1级 - 快速分析
- **配置**: 1轮辩论 + 1轮风险讨论
- **特点**: 禁用记忆和在线工具，使用缓存数据
- **优势**: 速度最快，成本最低
- **适用**: 日常市场监控，快速获取市场概况

#### 📈 2级 - 基础分析
- **配置**: 1轮辩论 + 1轮风险讨论
- **特点**: 启用记忆和在线工具，获取最新数据
- **优势**: 速度较快，包含最新数据
- **适用**: 常规投资决策，基础研究

#### 🎯 3级 - 标准分析（推荐）
- **配置**: 1轮辩论 + 2轮风险讨论
- **特点**: 平衡速度和质量
- **优势**: 性价比最高，适合大多数场景
- **适用**: 重要投资决策，标准研究流程

#### 🔍 4级 - 深度分析
- **配置**: 2轮辩论 + 2轮风险讨论
- **特点**: 多轮辩论确保全面性
- **优势**: 分析深度高，适合重要决策
- **适用**: 重大投资决策，深度研究

#### 🏆 5级 - 全面分析
- **配置**: 3轮辩论 + 3轮风险讨论
- **特点**: 最全面的分析，最高质量
- **优势**: 最可靠的结果
- **适用**: 最重要的投资决策，完整研究报告

## 🔧 修改内容

### 前端修改

#### 1. SingleAnalysis.vue
```typescript
// 深度选项（5个级别，与Web界面保持一致）
const depthOptions = [
  { icon: '⚡', name: '1级 - 快速分析', description: '基础数据概览，快速决策', time: '2-4分钟' },
  { icon: '📈', name: '2级 - 基础分析', description: '常规投资决策', time: '4-6分钟' },
  { icon: '🎯', name: '3级 - 标准分析', description: '技术+基本面，推荐', time: '6-10分钟' },
  { icon: '🔍', name: '4级 - 深度分析', description: '多轮辩论，深度研究', time: '10-15分钟' },
  { icon: '🏆', name: '5级 - 全面分析', description: '最全面的分析报告', time: '15-25分钟' }
]

// 默认值改为3（标准分析）
researchDepth: 3
```

#### 2. BatchAnalysis.vue
```vue
<el-option label="⚡ 1级 - 快速分析 (2-4分钟/只)" value="快速" />
<el-option label="📈 2级 - 基础分析 (4-6分钟/只)" value="基础" />
<el-option label="🎯 3级 - 标准分析 (6-10分钟/只，推荐)" value="标准" />
<el-option label="🔍 4级 - 深度分析 (10-15分钟/只)" value="深度" />
<el-option label="🏆 5级 - 全面分析 (15-25分钟/只)" value="全面" />
```

#### 3. types/analysis.ts
```typescript
export interface AnalysisParameters {
  research_depth: '快速' | '基础' | '标准' | '深度' | '全面'
  // ...
}
```

### 后端修改

#### 1. app/models/analysis.py
```python
class AnalysisParameters(BaseModel):
    """分析参数模型
    
    研究深度说明：
    - 快速: 1级 - 快速分析 (2-4分钟)
    - 基础: 2级 - 基础分析 (4-6分钟)
    - 标准: 3级 - 标准分析 (6-10分钟，推荐)
    - 深度: 4级 - 深度分析 (10-15分钟)
    - 全面: 5级 - 全面分析 (15-25分钟)
    """
    research_depth: str = "标准"  # 默认使用3级标准分析（推荐）
```

#### 2. app/services/simple_analysis_service.py
```python
def create_analysis_config(...):
    # 根据研究深度调整配置 - 支持5个级别（与Web界面保持一致）
    if research_depth == "快速":
        # 1级 - 快速分析
        config["max_debate_rounds"] = 1
        config["max_risk_discuss_rounds"] = 1
        config["memory_enabled"] = False  # 禁用记忆以加速
        config["online_tools"] = False  # 使用缓存数据
        
    elif research_depth == "基础":
        # 2级 - 基础分析
        config["max_debate_rounds"] = 1
        config["max_risk_discuss_rounds"] = 1
        config["memory_enabled"] = True
        config["online_tools"] = True
        
    elif research_depth == "标准":
        # 3级 - 标准分析（推荐）
        config["max_debate_rounds"] = 1
        config["max_risk_discuss_rounds"] = 2
        config["memory_enabled"] = True
        config["online_tools"] = True
        
    elif research_depth == "深度":
        # 4级 - 深度分析
        config["max_debate_rounds"] = 2
        config["max_risk_discuss_rounds"] = 2
        config["memory_enabled"] = True
        config["online_tools"] = True
        
    elif research_depth == "全面":
        # 5级 - 全面分析
        config["max_debate_rounds"] = 3
        config["max_risk_discuss_rounds"] = 3
        config["memory_enabled"] = True
        config["online_tools"] = True
```

## 📊 影响范围

### 前端
- ✅ `frontend/src/views/Analysis/SingleAnalysis.vue` - 单股分析页面
- ✅ `frontend/src/views/Analysis/BatchAnalysis.vue` - 批量分析页面
- ✅ `frontend/src/views/Analysis/index.vue` - 分析首页
- ✅ `frontend/src/types/analysis.ts` - 类型定义

### 后端
- ✅ `app/models/analysis.py` - 数据模型
- ✅ `app/services/simple_analysis_service.py` - 分析服务

### 兼容性
- ✅ 向后兼容：旧的3个级别仍然有效
- ✅ 新增2个级别："基础"和"全面"
- ✅ 默认值统一为"标准"（3级）

## 🎯 优势

1. **用户体验一致**: Web界面和Frontend界面提供相同的选项
2. **更细粒度控制**: 用户可以根据需求选择更合适的分析级别
3. **明确预期**: 每个级别都标注了预期耗时
4. **灵活性**: 从快速概览到全面分析，满足不同场景需求
5. **成本优化**: 用户可以根据重要性选择合适的级别，避免过度消耗

## 📝 使用建议

| 使用场景 | 推荐级别 | 理由 |
|----------|----------|------|
| 日常市场监控 | 1-2级 | 快速获取市场概况，成本低 |
| 常规投资决策 | 2-3级 | 平衡速度和质量 |
| 重要投资决策 | 3-4级 | 确保分析质量，多轮辩论 |
| 重大资金投入 | 4-5级 | 最全面的风险评估 |
| 研究报告撰写 | 4-5级 | 需要详细的分析内容 |

## 🔄 迁移指南

### 对于现有用户
- 如果之前使用"快速"，现在对应1级
- 如果之前使用"标准"，现在对应3级（推荐）
- 如果之前使用"深度"，现在对应4级
- 新增"基础"（2级）和"全面"（5级）可供选择

### 对于开发者
- 前端发送的 `research_depth` 字段值：`"快速"` | `"基础"` | `"标准"` | `"深度"` | `"全面"`
- 后端接收并处理这5个值
- 默认值统一为 `"标准"`

## ✅ 测试验证

### 前端测试
1. 单股分析页面显示5个深度选项
2. 批量分析页面显示5个深度选项
3. 默认选中"标准"（3级）
4. 每个选项显示正确的图标、名称、描述和预期耗时

### 后端测试
1. 接收5个不同的 `research_depth` 值
2. 正确配置辩论轮次和风险讨论轮次
3. 正确启用/禁用记忆和在线工具
4. 默认值为"标准"

### 集成测试
1. 提交不同深度级别的分析任务
2. 验证实际执行的配置是否正确
3. 验证耗时是否符合预期
4. 验证分析质量是否符合级别要求

## 📅 更新日期

2025-01-XX

## 👥 相关人员

- 开发者：AI Assistant
- 审核者：待定

