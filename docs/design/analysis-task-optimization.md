# 分析任务模块优化方案

## 📋 当前问题

### 1. 流程类型硬编码
- 每个分析流程都是独立的服务方法
- 添加新流程需要修改多处代码
- 缺乏统一的流程管理机制

### 2. 任务模型不够通用
- `AnalysisTask` - 股票分析专用
- `PositionAnalysisReport` - 持仓分析专用
- `TradeReview` - 交易复盘专用
- 缺乏统一的任务抽象

### 3. 工作流引擎集成不统一
- 有些用 `WorkflowAPI`
- 有些用 `StockAnalysisEngine`
- 有些用传统 LLM 调用
- 缺乏统一的引擎选择机制

---

## 🎯 优化目标

1. **统一任务模型** - 支持多种分析流程
2. **流程配置化** - 通过配置添加新流程
3. **引擎抽象化** - 统一的引擎选择和调用机制
4. **易于扩展** - 添加新流程无需修改核心代码

---

## 🏗️ 优化方案

### 方案 A：统一任务模型 + 流程注册表（推荐）

#### 1. 统一任务模型

```python
class AnalysisTaskType(str, Enum):
    """分析任务类型"""
    STOCK_ANALYSIS = "stock_analysis"           # 股票分析
    POSITION_ANALYSIS = "position_analysis"     # 持仓分析
    TRADE_REVIEW = "trade_review"               # 交易复盘
    PORTFOLIO_HEALTH = "portfolio_health"       # 组合健康度
    RISK_ASSESSMENT = "risk_assessment"         # 风险评估
    # 未来可扩展...

class UnifiedAnalysisTask(BaseModel):
    """统一分析任务模型"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    task_id: str = Field(..., description="任务唯一标识")
    user_id: PyObjectId
    
    # 任务类型和参数
    task_type: AnalysisTaskType = Field(..., description="任务类型")
    task_params: Dict[str, Any] = Field(default_factory=dict, description="任务参数（JSON）")
    
    # 执行配置
    workflow_id: Optional[str] = Field(None, description="工作流ID（如果使用工作流引擎）")
    engine_type: str = Field("auto", description="引擎类型: auto/workflow/legacy/llm")
    preference_type: str = Field("neutral", description="分析偏好: aggressive/neutral/conservative")
    
    # 状态和进度
    status: AnalysisStatus = AnalysisStatus.PENDING
    progress: int = Field(default=0, ge=0, le=100)
    
    # 结果
    result: Optional[Dict[str, Any]] = Field(None, description="分析结果（JSON）")
    
    # 元数据
    created_at: datetime = Field(default_factory=now_tz)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_time: float = 0.0
    error_message: Optional[str] = None
```

#### 2. 流程注册表

```python
class AnalysisWorkflowConfig(BaseModel):
    """分析流程配置"""
    task_type: AnalysisTaskType
    workflow_id: str                    # 工作流ID
    default_engine: str = "workflow"    # 默认引擎
    required_params: List[str]          # 必需参数
    optional_params: Dict[str, Any]     # 可选参数及默认值
    timeout: int = 300                  # 超时时间（秒）
    
class AnalysisWorkflowRegistry:
    """分析流程注册表"""
    _registry: Dict[AnalysisTaskType, AnalysisWorkflowConfig] = {}
    
    @classmethod
    def register(cls, config: AnalysisWorkflowConfig):
        """注册流程"""
        cls._registry[config.task_type] = config
    
    @classmethod
    def get_config(cls, task_type: AnalysisTaskType) -> Optional[AnalysisWorkflowConfig]:
        """获取流程配置"""
        return cls._registry.get(task_type)
    
    @classmethod
    def list_all(cls) -> List[AnalysisWorkflowConfig]:
        """列出所有流程"""
        return list(cls._registry.values())

# 注册内置流程
AnalysisWorkflowRegistry.register(AnalysisWorkflowConfig(
    task_type=AnalysisTaskType.STOCK_ANALYSIS,
    workflow_id="v2_stock_analysis",
    required_params=["symbol", "market_type"],
    optional_params={"research_depth": "标准", "analysis_date": None},
    timeout=600
))

AnalysisWorkflowRegistry.register(AnalysisWorkflowConfig(
    task_type=AnalysisTaskType.POSITION_ANALYSIS,
    workflow_id="position_analysis",
    required_params=["position_id"],
    optional_params={"research_depth": "标准", "include_add_position": True},
    timeout=300
))

AnalysisWorkflowRegistry.register(AnalysisWorkflowConfig(
    task_type=AnalysisTaskType.TRADE_REVIEW,
    workflow_id="trade_review",
    required_params=["review_id"],
    optional_params={"trading_system_id": None},
    timeout=300
))
```

#### 3. 统一执行引擎

```python
class UnifiedAnalysisEngine:
    """统一分析引擎"""
    
    async def execute_task(
        self,
        task: UnifiedAnalysisTask,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """执行分析任务"""
        
        # 1. 获取流程配置
        config = AnalysisWorkflowRegistry.get_config(task.task_type)
        if not config:
            raise ValueError(f"未注册的任务类型: {task.task_type}")
        
        # 2. 验证参数
        self._validate_params(task.task_params, config)
        
        # 3. 选择执行引擎
        engine = self._select_engine(task.engine_type, config.default_engine)
        
        # 4. 执行分析
        if engine == "workflow":
            return await self._execute_via_workflow(task, config, progress_callback)
        elif engine == "legacy":
            return await self._execute_via_legacy(task, config, progress_callback)
        elif engine == "llm":
            return await self._execute_via_llm(task, config, progress_callback)
        else:
            raise ValueError(f"不支持的引擎类型: {engine}")

    async def _execute_via_workflow(
        self,
        task: UnifiedAnalysisTask,
        config: AnalysisWorkflowConfig,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """通过工作流引擎执行"""
        from core.api.workflow_api import WorkflowAPI

        workflow_api = WorkflowAPI()
        result = await workflow_api.execute(
            workflow_id=task.workflow_id or config.workflow_id,
            inputs=task.task_params,
            config={"preference_type": task.preference_type}
        )
        return result

    async def _execute_via_legacy(
        self,
        task: UnifiedAnalysisTask,
        config: AnalysisWorkflowConfig,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """通过旧引擎执行"""
        # 调用 TradingAgentsGraph
        pass

    async def _execute_via_llm(
        self,
        task: UnifiedAnalysisTask,
        config: AnalysisWorkflowConfig,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """通过直接LLM调用执行"""
        # 调用 LLM
        pass
```

---

### 方案 B：基于工作流模板的动态流程（更灵活）

#### 核心思想
- 所有分析流程都定义为工作流模板
- 任务执行统一通过工作流引擎
- 用户可以自定义工作流

#### 优点
- 最大灵活性
- 用户可自定义流程
- 统一的执行机制

#### 缺点
- 实现复杂度较高
- 需要完善的工作流编辑器

---

## 📊 对比分析

| 特性 | 方案A（推荐） | 方案B |
|------|--------------|-------|
| 实现难度 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 灵活性 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 向后兼容 | ✅ 完全兼容 | ⚠️ 需要迁移 |
| 扩展性 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 用户自定义 | ❌ 不支持 | ✅ 支持 |
| 开发周期 | 1-2周 | 4-6周 |

---

## 🚀 实施计划（方案A）

### Phase 1: 核心模型和注册表（1-2天）
- [ ] 创建 `UnifiedAnalysisTask` 模型
- [ ] 实现 `AnalysisWorkflowRegistry`
- [ ] 注册现有的3个流程

### Phase 2: 统一执行引擎（2-3天）
- [ ] 实现 `UnifiedAnalysisEngine`
- [ ] 实现工作流引擎适配器
- [ ] 实现旧引擎适配器
- [ ] 实现LLM适配器

### Phase 3: 服务层重构（2-3天）
- [ ] 创建 `UnifiedAnalysisService`
- [ ] 迁移现有服务到新架构
- [ ] 保持向后兼容

### Phase 4: API层更新（1-2天）
- [ ] 添加统一的任务创建API
- [ ] 添加流程列表API
- [ ] 更新前端调用

### Phase 5: 测试和文档（2-3天）
- [ ] 单元测试
- [ ] 集成测试
- [ ] 更新文档

**总计：8-13天**

---

## 💡 使用示例

### 创建股票分析任务
```python
task = UnifiedAnalysisTask(
    task_id=str(uuid.uuid4()),
    user_id=user_id,
    task_type=AnalysisTaskType.STOCK_ANALYSIS,
    task_params={
        "symbol": "000858",
        "market_type": "cn",
        "research_depth": "标准"
    },
    engine_type="auto",  # 自动选择最佳引擎
    preference_type="neutral"
)

engine = UnifiedAnalysisEngine()
result = await engine.execute_task(task)
```

### 创建持仓分析任务
```python
task = UnifiedAnalysisTask(
    task_id=str(uuid.uuid4()),
    user_id=user_id,
    task_type=AnalysisTaskType.POSITION_ANALYSIS,
    task_params={
        "position_id": "pos_123",
        "research_depth": "深度",
        "include_add_position": True
    },
    workflow_id="position_analysis_v2",  # 可指定特定工作流
    preference_type="conservative"
)

result = await engine.execute_task(task)
```

### 添加新的分析流程
```python
# 1. 定义工作流模板（在 core/workflow/templates/）
# 2. 注册流程
AnalysisWorkflowRegistry.register(AnalysisWorkflowConfig(
    task_type=AnalysisTaskType.RISK_ASSESSMENT,
    workflow_id="risk_assessment_v1",
    required_params=["portfolio_id"],
    optional_params={"risk_model": "var"},
    timeout=180
))

# 3. 立即可用！
task = UnifiedAnalysisTask(
    task_type=AnalysisTaskType.RISK_ASSESSMENT,
    task_params={"portfolio_id": "port_456"}
)
result = await engine.execute_task(task)
```

---

## 🎯 预期收益

1. **开发效率提升 50%**
   - 添加新流程只需注册配置
   - 无需修改核心代码

2. **代码复用率提升 70%**
   - 统一的任务模型
   - 统一的执行引擎

3. **维护成本降低 60%**
   - 集中的流程管理
   - 清晰的架构边界

4. **扩展性大幅提升**
   - 支持插件式流程
   - 支持多引擎切换

---

## ✅ 已完成的工作

### Phase 1: 核心模型和注册表 ✅

**文件**: `app/models/analysis.py`
- ✅ 创建 `AnalysisTaskType` 枚举（7种任务类型）
- ✅ 创建 `UnifiedAnalysisTask` 模型（统一任务模型）

**文件**: `app/services/workflow_registry.py`
- ✅ 创建 `AnalysisWorkflowConfig` 配置模型
- ✅ 创建 `AnalysisWorkflowRegistry` 注册表
- ✅ 实现 `initialize_builtin_workflows()` 初始化函数
- ✅ 注册 4 个内置流程：
  - stock_analysis (股票完整分析)
  - position_analysis (持仓分析)
  - trade_review (交易复盘)
  - portfolio_health (组合健康度)

**文件**: `app/main.py`
- ✅ 在应用启动时初始化工作流注册表

**测试**: `scripts/test_workflow_registry.py`
- ✅ 测试通过，所有功能正常

### Phase 2: 统一执行引擎 ✅

**文件**: `app/services/unified_analysis_engine.py`
- ✅ 创建 `UnifiedAnalysisEngine` 类
- ✅ 实现 `execute_task()` 主执行方法
- ✅ 实现 `_execute_via_workflow()` 工作流引擎适配器
- ✅ 实现 `_execute_via_legacy()` 旧引擎适配器
- ✅ 实现 `_execute_via_llm()` LLM 适配器
- ✅ 实现 `_build_prompt_for_task()` 提示词构建
- ✅ 实现 `_select_engine()` 引擎选择逻辑

**测试**: `scripts/test_unified_engine.py`
- ✅ 测试通过，所有功能正常

### Phase 3: 服务层 ✅

**文件**: `app/services/task_analysis_service.py`
- ✅ 创建 `TaskAnalysisService` 类
- ✅ 实现 `create_task()` 创建任务
- ✅ 实现 `execute_task()` 执行任务
- ✅ 实现 `create_and_execute_task()` 一步到位
- ✅ 实现 `get_task()` 查询任务
- ✅ 实现 `list_user_tasks()` 列出用户任务
- ✅ 实现 `cancel_task()` 取消任务
- ✅ 实现 `get_task_statistics()` 任务统计
- ✅ 实现 `_save_task()` 和 `_update_task()` 数据库操作
- ✅ 提供 `get_task_analysis_service()` 单例函数

### Phase 4: 集成到现有服务 ✅

**文件**: `app/services/portfolio_service.py`
- ✅ 添加 `analyze_position_by_code_v2()` 方法
- ✅ 使用 `TaskAnalysisService` 执行持仓分析
- ✅ 支持引擎选择和偏好设置
- ✅ 保持与旧方法的兼容性

**文件**: `app/services/simple_analysis_service.py`
- ✅ 添加 `create_and_execute_analysis_v2()` 方法
- ✅ 使用 `TaskAnalysisService` 执行股票分析
- ✅ 支持引擎选择和偏好设置
- ✅ 保持与旧方法的兼容性

**文件**: `app/services/trade_review_service.py`
- ✅ 添加 `create_trade_review_v2()` 方法
- ✅ 使用 `TaskAnalysisService` 执行交易复盘
- ✅ 支持引擎选择和偏好设置
- ✅ 保持与旧方法的兼容性

---

## 📋 下一步工作

### Phase 5: API 路由更新（1-2天）

**目标**: 在 API 路由中支持引擎选择

**任务**:
1. 更新 `app/routers/portfolio.py`
   - 在 `analyze_position_by_code` 端点中添加 `use_unified_engine` 参数
   - 根据参数选择调用 v1 或 v2 方法

2. 更新 `app/routers/analysis.py`
   - 在 `single` 端点中添加 `use_unified_engine` 参数
   - 根据参数选择调用 v1 或 v2 方法

3. 更新 `app/routers/review.py`
   - 在 `create_trade_review` 端点中添加 `use_unified_engine` 参数
   - 根据参数选择调用 v1 或 v2 方法

### Phase 6: 测试和文档（2-3天）

**任务**:
1. 单元测试
2. 集成测试
3. 性能测试
4. 更新用户文档
5. 更新开发文档

---

## 🎯 核心优势总结

### 1. 统一的任务模型
```python
# 所有分析任务都使用同一个模型
task = UnifiedAnalysisTask(
    task_type=AnalysisTaskType.STOCK_ANALYSIS,  # 或其他类型
    task_params={...},  # 灵活的参数
    engine_type="auto",  # 自动选择引擎
    preference_type="neutral"  # 分析偏好
)
```

### 2. 配置化的流程管理
```python
# 注册新流程只需配置
AnalysisWorkflowRegistry.register(AnalysisWorkflowConfig(
    task_type=AnalysisTaskType.NEW_ANALYSIS,
    workflow_id="new_workflow",
    required_params=["param1", "param2"],
    ...
))
```

### 3. 统一的执行接口
```python
# 所有任务都通过同一个引擎执行
engine = UnifiedAnalysisEngine()
result = await engine.execute_task(task)
```

### 4. 简洁的服务层
```python
# 一行代码完成创建和执行
service = get_task_analysis_service()
task = await service.create_and_execute_task(
    user_id=user_id,
    task_type=AnalysisTaskType.STOCK_ANALYSIS,
    task_params={"symbol": "000858", "market_type": "cn"}
)
```

---

## 📊 架构对比

### 旧架构
```
API → Service → Engine (硬编码)
  ├─ stock_analysis → TradingAgentsGraph
  ├─ position_analysis → PositionAnalysisService
  └─ trade_review → TradeReviewService
```

### 新架构
```
API → TaskAnalysisService → UnifiedAnalysisEngine → Registry
                                      ├─ workflow (推荐)
                                      ├─ legacy
                                      └─ llm
```

**优势**:
- ✅ 统一入口
- ✅ 配置驱动
- ✅ 易于扩展
- ✅ 向后兼容
```


