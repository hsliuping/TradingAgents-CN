# 修复持仓分析工作流调用问题

## 问题描述

用户通过 `POST /api/portfolio/positions/analyze-by-code` 接口进行持仓分析时，发现**没有使用 v2.0 工作流引擎**，而是直接使用了传统 LLM 分析。

## 问题根源

**文件**：`app/services/portfolio_service.py`

### 对比两个方法

#### ✅ `analyze_position` 方法（第 2081-2175 行）- 正确实现

```python
async def analyze_position(
    self,
    user_id: str,
    position_id: str,
    params: PositionAnalysisRequest
) -> PositionAnalysisReport:
    """单股持仓分析 - 方案2实现"""
    
    # 第一阶段：调用单股分析
    stock_analysis_report = await self._get_stock_analysis_report(...)
    
    # 第二阶段：持仓分析
    # ✅ 根据配置选择分析引擎
    if _use_stock_engine():
        logger.info(f"🚀 [持仓分析] 使用工作流引擎v2.0进行分析")
        ai_result = await self._call_position_ai_analysis_workflow(...)
    else:
        logger.info(f"🤖 [持仓分析] 使用传统LLM分析")
        ai_result = await self._call_position_ai_analysis_v2(...)
```

#### ❌ `analyze_position_by_code` 方法（第 2390-2530 行）- 缺少判断

```python
async def analyze_position_by_code(
    self,
    user_id: str,
    code: str,
    market: str,
    params: "PositionAnalysisByCodeRequest"
) -> PositionAnalysisReport:
    """按股票代码分析持仓（汇总多条持仓记录）"""
    
    # 第一阶段：调用单股分析
    stock_analysis_report = await self._get_stock_analysis_report(...)
    
    # 第二阶段：持仓分析
    # ❌ 直接调用传统LLM分析，没有判断是否使用工作流引擎
    ai_result = await self._call_position_ai_analysis_v2(...)
```

## 修复方案

在 `analyze_position_by_code` 方法中添加工作流引擎判断逻辑。

### 修改内容

**文件**：`app/services/portfolio_service.py` 第 2505-2512 行

**修改前**：
```python
# 第二阶段：结合持仓信息进行持仓分析
logger.info(f"📊 [汇总持仓分析] 第二阶段：持仓专用分析 - {code}")
ai_result = await self._call_position_ai_analysis_v2(
    snapshot=snapshot,
    params=analysis_params,
    stock_analysis_report=stock_analysis_report,
    user_id=user_id
)
```

**修改后**：
```python
# 第二阶段：结合持仓信息进行持仓分析
logger.info(f"📊 [汇总持仓分析] 第二阶段：持仓专用分析 - {code}")

# 根据配置选择分析引擎（USE_STOCK_ENGINE=true 时使用工作流引擎v2.0）
if _use_stock_engine():
    logger.info(f"🚀 [汇总持仓分析] 使用工作流引擎v2.0进行分析")
    ai_result = await self._call_position_ai_analysis_workflow(
        snapshot=snapshot,
        params=analysis_params,
        stock_analysis_report=stock_analysis_report,
        user_id=user_id
    )
else:
    logger.info(f"🤖 [汇总持仓分析] 使用传统LLM分析")
    ai_result = await self._call_position_ai_analysis_v2(
        snapshot=snapshot,
        params=analysis_params,
        stock_analysis_report=stock_analysis_report,
        user_id=user_id
    )
```

## 影响范围

### 修复前

| 接口 | 方法 | 是否使用工作流 v2.0 |
|------|------|-------------------|
| `POST /api/portfolio/positions/{position_id}/analysis` | `analyze_position` | ✅ 是（如果 `USE_STOCK_ENGINE=true`） |
| `POST /api/portfolio/positions/analyze-by-code` | `analyze_position_by_code` | ❌ **否**（总是使用传统 LLM） |

### 修复后

| 接口 | 方法 | 是否使用工作流 v2.0 |
|------|------|-------------------|
| `POST /api/portfolio/positions/{position_id}/analysis` | `analyze_position` | ✅ 是（如果 `USE_STOCK_ENGINE=true`） |
| `POST /api/portfolio/positions/analyze-by-code` | `analyze_position_by_code` | ✅ **是**（如果 `USE_STOCK_ENGINE=true`） |

## 两个接口的区别

### 1. `POST /api/portfolio/positions/{position_id}/analysis`

- **输入**：`position_id`（单条持仓记录的 ID）
- **场景**：分析单条持仓记录
- **调用方法**：`analyze_position`

### 2. `POST /api/portfolio/positions/analyze-by-code`

- **输入**：`code` + `market`（股票代码 + 市场）
- **场景**：分析某只股票的**所有持仓记录**（汇总分析）
- **调用方法**：`analyze_position_by_code`
- **特点**：
  - 查询该股票的所有持仓记录
  - 汇总计算总数量、平均成本价
  - 作为一个整体进行分析
  - **异步模式**：立即返回分析 ID，后台执行分析

## 测试建议

1. **重启 Web 服务**
2. **确认环境变量**：`USE_STOCK_ENGINE=true`
3. **测试接口**：`POST /api/portfolio/positions/analyze-by-code`
4. **检查日志**：应该看到 `🚀 [汇总持仓分析] 使用工作流引擎v2.0进行分析`
5. **验证结果**：分析报告应该包含 4 个维度的分析（技术面、基本面、风险、操作建议）

## 总结

✅ **修复完成**

现在两个持仓分析接口都会根据 `USE_STOCK_ENGINE` 环境变量自动选择：
- `USE_STOCK_ENGINE=true`：使用 v2.0 工作流引擎（4 个并行分析师 + 1 个操作建议师）
- `USE_STOCK_ENGINE=false`：使用传统 LLM 分析（单次调用）

