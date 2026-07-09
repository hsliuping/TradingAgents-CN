# 统一分析引擎设计文档

> 版本: 1.1.0
> 日期: 2025-12-10
> 状态: 已实现 ✅

## 1. 背景与目标

### 1.1 当前问题

项目中存在 **三套分析流程**，代码重复且难以维护：

| 系统 | 入口 | 引擎 | 代码位置 |
|------|------|------|---------|
| 前端工作流 | `/api/workflows/{id}/execute` | `WorkflowEngine` | `core/workflow/` |
| 单股/批量分析 | `/api/analysis/single`, `/batch` | `TradingAgentsGraph` | `app/services/simple_analysis_service.py` |
| 新引擎 (未使用) | 测试脚本 | `StockAnalysisEngine` | `tradingagents/core/engine/` |

### 1.2 目标

1. **统一到一套代码** - 所有分析入口使用同一个引擎 ✅
2. **LangGraph 动态构建** - 保持工作流灵活性 ✅
3. **闭环调试** - 前端编辑 → 调试 → 应用到正式分析 ✅
4. **配置化** - 用户可选择使用哪个工作流 ✅

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                        API 层                                │
├─────────────┬─────────────┬─────────────┬──────────────────┤
│ /workflows  │ /analysis   │ /analysis   │    定时任务       │
│ /{id}/exec  │ /single     │ /batch      │                  │
└──────┬──────┴──────┬──────┴──────┬──────┴────────┬─────────┘
       │             │             │               │
       └─────────────┴─────────────┴───────────────┘
                           │
                           ▼
       ┌───────────────────────────────────────────┐
       │        UnifiedAnalysisService (新)         │
       │   - 加载工作流                              │
       │   - 配置解析                                │
       │   - 进度跟踪                                │
       └───────────────────┬───────────────────────┘
                           │
                           ▼
       ┌───────────────────────────────────────────┐
       │     WorkflowEngine + WorkflowBuilder       │
       │   - LangGraph 动态构建                     │
       │   - 节点执行                                │
       │   - 状态管理                                │
       └───────────────────┬───────────────────────┘
                           │
                           ▼
       ┌───────────────────────────────────────────┐
       │            Agent 层 (现有)                  │
       │   tradingagents/agents/*                   │
       └───────────────────────────────────────────┘
```

### 2.2 工作流类型

| 类型 | ID | 说明 | 可修改 |
|------|-----|------|--------|
| 系统默认 | `default` | 预置标准流程 | ❌ |
| 用户自定义 | UUID | 编辑器创建 | ✅ |
| 活动工作流 | 配置项 | 正式分析使用 | 设置 |

### 2.3 调用方式

| 场景 | workflow_id 参数 | 说明 |
|------|-----------------|------|
| 工作流调试 | 用户指定 | 调试编辑中的工作流 |
| 单股分析 | `None` → 活动工作流 | 使用系统配置的工作流 |
| 批量分析 | `None` → 活动工作流 | 使用系统配置的工作流 |
| 定时分析 | 任务配置 | 可单独指定工作流 |

## 3. 核心组件

### 3.1 UnifiedAnalysisService

```python
class UnifiedAnalysisService:
    """统一分析服务"""
    
    async def analyze(
        self,
        stock_code: str,
        analysis_date: str,
        workflow_id: Optional[str] = None,
        config: Optional[AnalysisConfig] = None,
        progress_callback: Optional[Callable] = None,
        task_id: Optional[str] = None,
    ) -> AnalysisResult:
        """
        执行股票分析
        
        Args:
            stock_code: 股票代码
            analysis_date: 分析日期
            workflow_id: 工作流ID，None则使用活动工作流
            config: 分析配置（LLM、模型等）
            progress_callback: 进度回调
            task_id: 任务ID（用于进度跟踪）
        """
        pass
```

### 3.2 DefaultWorkflowProvider

```python
class DefaultWorkflowProvider:
    """默认工作流提供者"""
    
    @staticmethod
    def get_default_workflow() -> WorkflowDefinition:
        """获取系统默认工作流"""
        pass
    
    @staticmethod
    def ensure_default_exists() -> str:
        """确保默认工作流存在于数据库"""
        pass
```

## 4. 实现状态

### Phase 1: 基础设施 ✅ (已完成)

- [x] 创建 `UnifiedAnalysisService` - `app/services/unified_analysis_service.py`
- [x] 创建 `DefaultWorkflowProvider` - `core/workflow/default_workflows.py`
- [x] 增强 `WorkflowEngine` 支持进度回调 - `core/workflow/engine.py`

### Phase 2: API 迁移 ✅ (已完成)

- [x] 修改 `/api/analysis/single` 调用新服务 - 支持新旧流程切换
- [x] 修改 `/api/analysis/batch` 调用新服务 - 使用统一引擎
- [x] 修改 `/api/workflows/{id}/execute` 调用新服务 - 统一调用路径

### Phase 3: 前端集成 ✅ (已完成)

- [x] 单股分析页面支持新旧流程选择
- [x] 批量分析页面使用新流程
- [x] 工作流执行页面统一配置获取
- [x] 前端默认配置统一化

### Phase 4: 测试验证 ✅ (已完成)

- [x] 新流程功能测试 - 目标价格、分析依据正常
- [x] 前端联调 - 三个入口均正常工作
- [x] 配置一致性验证 - 默认模型和深度统一获取

## 5. 用户闭环流程

```
1. 创建工作流
   └─ 前端编辑器拖拽节点、连线
   
2. 调试工作流
   └─ /api/workflows/{id}/execute
   └─ 查看每个节点执行结果
   └─ 调整参数/提示词
   
3. 应用工作流
   └─ 设置为「活动工作流」
   └─ 或在系统设置中选择
   
4. 正式使用
   └─ 单股分析自动使用
   └─ 批量分析自动使用
   └─ 定时任务自动使用
```

## 6. 配置项

### 6.1 系统配置 (MongoDB: system_configs)

```json
{
  "active_workflow_id": "default",  // 活动工作流ID
  "default_research_depth": "标准",  // 默认研究深度
  "enable_workflow_selection": true  // 是否允许用户选择工作流
}
```

### 6.2 任务配置

```json
{
  "task_id": "xxx",
  "stock_code": "000858",
  "workflow_id": null,  // null 表示使用活动工作流
  "config": {
    "research_depth": "深度",
    "quick_model": "qwen-turbo",
    "deep_model": "qwen-max"
  }
}
```

## 7. 当前实现状态

### 7.1 已实现功能 ✅

1. **统一分析引擎**
   - `UnifiedAnalysisService` - 统一所有分析入口
   - `WorkflowEngine` - LangGraph 动态构建和执行
   - `DefaultWorkflowProvider` - 系统默认工作流管理

2. **API 统一**
   - 单股分析：支持新旧流程切换 (`use_new_flow` 参数)
   - 批量分析：完全使用新流程
   - 工作流执行：统一调用路径

3. **前端集成**
   - 单股分析页面：新增流程选择开关
   - 批量分析页面：使用统一引擎
   - 工作流执行页面：统一配置获取
   - 默认配置统一：分析深度和模型选择保持一致

4. **数据处理优化**
   - `SignalProcessor` 集成：统一提取目标价格和结构化数据
   - 报告格式化：清理 Markdown 格式，保持输出一致性
   - 状态合并优化：解决并发执行时的数据覆盖问题

### 7.2 技术亮点

1. **智能状态合并**
   - 增强 `merge_dict` 函数，防止空值覆盖有效数据
   - 解决 LangGraph 并发执行时的状态一致性问题

2. **模型配置统一**
   - 前端三个入口（单股、批量、工作流）统一从系统配置获取默认模型
   - 用户偏好设置统一应用到所有分析场景

3. **向后兼容**
   - 保留旧分析流程，用户可选择使用
   - API 接口保持兼容，不影响现有集成

### 7.3 文件变更清单

| 文件 | 操作 | 说明 | 状态 |
|------|------|------|------|
| `app/services/unified_analysis_service.py` | 新建 | 统一分析服务 | ✅ |
| `core/workflow/default_workflows.py` | 新建 | 默认工作流定义 | ✅ |
| `core/workflow/engine.py` | 修改 | 添加进度回调 | ✅ |
| `core/workflow/builder.py` | 修改 | 增强状态合并逻辑 | ✅ |
| `app/routers/analysis.py` | 修改 | 支持新旧流程切换 | ✅ |
| `app/utils/report_formatter.py` | 新建 | 统一报告格式化 | ✅ |
| `frontend/src/views/Analysis/SingleAnalysis.vue` | 修改 | 新增流程选择 | ✅ |
| `frontend/src/views/Analysis/BatchAnalysis.vue` | 修改 | 使用新流程 | ✅ |
| `frontend/src/views/Workflow/Execute.vue` | 修改 | 统一配置获取 | ✅ |
| `app/services/simple_analysis_service.py` | 保留 | 向后兼容 | 🔄 |

## 8. 下一步计划

### 8.1 短期优化 (1-2 天)

- [ ] 完善错误处理和日志记录
- [ ] 添加性能监控和指标收集
- [ ] 优化前端用户体验（加载状态、错误提示）

### 8.2 中期规划 (1-2 周)

- [ ] 用户反馈收集和问题修复
- [ ] 性能优化和缓存策略
- [ ] 扩展更多工作流模板

### 8.3 长期规划 (1 个月+)

- [ ] 完全废弃旧分析流程
- [ ] 工作流市场和分享功能
- [ ] 高级工作流功能（条件分支、循环等）

