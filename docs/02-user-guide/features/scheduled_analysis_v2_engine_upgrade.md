# 定时分析功能 - v2.0 引擎升级

## 📋 更新概述

**日期**: 2026-01-07  
**版本**: v1.0.1  
**更新内容**: 定时分析功能从 v1.x 引擎升级到 v2.0 统一任务引擎

---

## 🎯 升级原因

### 问题描述

用户反馈：定时分析生成的报告与单股分析页面生成的报告格式不一致。

### 根本原因

- **单股分析**: 使用 v2.0 统一任务引擎 (`TaskAnalysisService`)
- **定时分析**: 使用 v1.x 旧引擎 (`SimpleAnalysisService` + `TradingAgentsGraph`)

两个引擎的分析流程和报告格式不同，导致结果不一致。

---

## 🔧 技术变更

### 修改文件

**文件**: `app/worker/watchlist_analysis_task.py`

### 变更详情

#### 1. 任务创建方式

**旧版 (v1.x)**:
```python
from app.services.simple_analysis_service import get_simple_analysis_service
from app.models.analysis import AnalysisParameters

service = get_simple_analysis_service()

# 创建分析参数
parameters = AnalysisParameters(
    market_type="A股",
    research_depth=research_depth,
    selected_analysts=["market", "fundamentals"]
)

# 创建任务
request = SingleAnalysisRequest(
    symbol=stock_code,
    stock_code=stock_code,
    stock_name=stock_name,
    analysis_date=analysis_date,
    parameters=parameters
)

task_info = await service.create_analysis_task(user_id, request)
task_id = task_info.get("task_id")
```

**新版 (v2.0)**:
```python
from app.services.task_analysis_service import get_task_analysis_service
from app.models.analysis import AnalysisTaskType
from app.models.user import PyObjectId

task_service = get_task_analysis_service()

# 准备任务参数
task_params = {
    "symbol": stock_code,
    "stock_code": stock_code,
    "market_type": "cn",
    "analysis_date": analysis_date,
    "research_depth": research_depth,
    "quick_analysis_model": quick_analysis_model,
    "deep_analysis_model": deep_analysis_model
}

# 使用 v2.0 统一任务引擎创建任务
task = await task_service.create_task(
    user_id=PyObjectId(user_id),
    task_type=AnalysisTaskType.STOCK_ANALYSIS,
    task_params=task_params,
    engine_type="auto",  # 自动选择引擎
    preference_type="neutral"
)

task_id = task.task_id
```

#### 2. 任务执行方式

**旧版 (v1.x)**:
```python
async def run_single_analysis(tid: str, req: SingleAnalysisRequest, uid: str, code: str):
    try:
        logger.info(f"    🔄 开始执行: {tid} - {code}")
        await service.execute_analysis_background(tid, uid, req)
        logger.info(f"    ✅ 执行完成: {tid} - {code}")
    except Exception as e:
        logger.error(f"    ❌ 执行失败: {tid} - {code}, 错误: {e}", exc_info=True)
```

**新版 (v2.0)**:
```python
async def run_single_analysis(tid: str, code: str):
    try:
        logger.info(f"    🔄 [v2.0引擎] 开始执行: {tid} - {code}")
        # 使用 v2.0 统一任务引擎执行
        await task_service.execute_task(tid)
        logger.info(f"    ✅ [v2.0引擎] 执行完成: {tid} - {code}")
    except Exception as e:
        logger.error(f"    ❌ [v2.0引擎] 执行失败: {tid} - {code}, 错误: {e}", exc_info=True)
```

---

## ✅ 升级优势

### 1. 报告格式统一

- ✅ 定时分析和单股分析使用相同的引擎
- ✅ 报告格式完全一致
- ✅ 用户体验更好

### 2. 功能更强大

- ✅ 支持多引擎切换（workflow/legacy/llm）
- ✅ 自动选择最佳引擎
- ✅ 更好的进度跟踪
- ✅ 更详细的错误信息

### 3. 性能更好

- ✅ 统一的任务管理
- ✅ 更好的并发控制
- ✅ 更高效的资源利用

### 4. 可维护性更好

- ✅ 代码更简洁
- ✅ 逻辑更清晰
- ✅ 更容易扩展

---

## 🔄 数据库变更

### 任务存储

**旧版**: 存储在 `analysis_tasks` 集合  
**新版**: 存储在 `unified_analysis_tasks` 集合

### 报告存储

**旧版**: 存储在 `analysis_reports` 集合  
**新版**: 
- 主要存储在 `unified_analysis_tasks` 集合的 `result` 字段
- 兼容存储在 `analysis_reports` 集合（保持向后兼容）

---

## 📊 影响范围

### 受影响的功能

1. ✅ 定时分析配置
2. ✅ 自选股分组分析
3. ✅ 测试执行功能

### 不受影响的功能

1. ✅ 单股分析（已经使用 v2.0 引擎）
2. ✅ 批量分析（已经使用 v2.0 引擎）
3. ✅ 分析报告查看

---

## 🧪 测试建议

### 测试步骤

1. **创建定时分析配置**
   - 创建一个新的定时分析配置
   - 添加时间段和分组
   - 保存配置

2. **测试执行**
   - 点击"测试执行"按钮
   - 等待分析完成
   - 查看执行历史

3. **查看报告**
   - 前往"分析报告"页面
   - 查看刚刚生成的报告
   - 对比单股分析的报告格式

4. **验证一致性**
   - 使用相同的股票代码
   - 分别通过单股分析和定时分析生成报告
   - 对比两个报告的格式和内容

### 预期结果

- ✅ 定时分析和单股分析的报告格式完全一致
- ✅ 报告包含相同的分析维度和内容
- ✅ 执行历史正确记录
- ✅ 没有错误日志

---

## 🐛 故障排查

### 问题 1: 任务创建失败

**错误信息**: `创建任务失败：未返回task_id`

**原因**: 
- 用户ID格式错误
- 数据库连接问题

**解决**:
1. 检查用户ID是否为有效的 ObjectId
2. 检查数据库连接
3. 查看后端日志

### 问题 2: 任务执行失败

**错误信息**: `执行失败: xxx`

**原因**:
- LLM 服务异常
- 股票代码无效
- 网络问题

**解决**:
1. 查看执行历史中的详细错误信息
2. 检查 LLM 配置
3. 验证股票代码是否有效

### 问题 3: 报告格式仍然不一致

**原因**:
- 缓存问题
- 旧任务未清理

**解决**:
1. 清除浏览器缓存
2. 重启后端服务
3. 删除旧的定时分析配置，重新创建

---

## 📚 相关文档

- v2.0 引擎设计: `docs/design/v2.0/stock-analysis-engine-design.md`
- 统一任务引擎: `app/services/task_analysis_service.py`
- 定时分析快速开始: `docs/features/SCHEDULED_ANALYSIS_QUICK_START.md`

---

**最后更新**: 2026-01-07  
**版本**: v1.0.1  
**更新人**: TradingAgents-CN Pro Team

