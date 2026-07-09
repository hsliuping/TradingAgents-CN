# 持仓分析流程优化

## 问题背景

用户发现持仓分析流程存在**重复分析**的问题：

### 原有流程

```
第一阶段：单股分析（强制执行）
  ↓
StockAnalysisEngine
  ├─→ 技术面分析
  ├─→ 基本面分析
  └─→ 新闻面分析
  ↓
第二阶段：持仓分析工作流 v2.0
  ↓
position_analysis_v2 工作流
  ├─→ 持仓技术面分析师 v2.0（重复分析技术面）
  ├─→ 持仓基本面分析师 v2.0（重复分析基本面）
  └─→ 持仓风险评估师 v2.0
  ↓
持仓操作建议师 v2.0
```

### 问题分析

1. **重复分析**：技术面、基本面在两个阶段都被分析了一遍
2. **强制执行**：总是先执行单股分析，即使用户不需要
3. **缺少选择**：没有询问用户是否需要单股分析报告

## 优化方案

### 1. 添加用户选择参数

**文件**：`app/models/portfolio.py`

```python
class PositionAnalysisByCodeRequest(BaseModel):
    """按股票代码分析持仓请求"""
    # ... 其他字段 ...
    
    # 单股分析选项
    use_stock_analysis: bool = Field(
        True, 
        description="是否使用单股分析报告作为参考。True: 如果有缓存报告则使用，没有则跳过；False: 不使用单股分析报告"
    )
```

### 2. 优化单股分析获取逻辑

**文件**：`app/services/portfolio_service.py`

#### 修改 `_get_stock_analysis_report` 方法

添加 `skip_if_not_exists` 参数：

```python
async def _get_stock_analysis_report(
    self,
    user_id: str,
    stock_code: str,
    market: str = "A股",
    skip_if_not_exists: bool = False  # ← 新增参数
) -> Optional[Dict[str, Any]]:
    """获取股票的完整分析报告
    
    Args:
        skip_if_not_exists: 如果没有缓存报告，是否跳过（不创建新任务）
    """
```

**逻辑**：
- `skip_if_not_exists=True`：只使用缓存报告，没有缓存则返回 `None`
- `skip_if_not_exists=False`：如果没有缓存，创建新的分析任务

#### 修改 `analyze_position_by_code` 方法

根据用户选择决定是否获取单股分析报告：

```python
# 第一阶段：根据用户选择，决定是否获取单股分析报告
stock_analysis_report = None
if params.use_stock_analysis:
    logger.info(f"📊 检查单股分析报告 - {code}")
    stock_analysis_report = await self._get_stock_analysis_report(
        user_id=user_id,
        stock_code=code,
        market=market_name,
        skip_if_not_exists=True  # 只使用缓存，不创建新任务
    )
    
    if stock_analysis_report:
        logger.info(f"✅ 找到单股分析报告，将作为参考")
    else:
        logger.info(f"ℹ️ 没有找到单股分析报告，将直接进行持仓分析")
else:
    logger.info(f"⏭️ 用户选择不使用单股分析报告")

# 如果没有单股分析报告，创建空结构
if not stock_analysis_report:
    stock_analysis_report = {
        "task_id": None,
        "reports": {},
        "decision": {},
        "summary": "",
        "recommendation": "",
        "source": "none"
    }
```

### 3. 持仓分析 Agent 如何利用单股分析报告

#### 基本面分析师 v2.0

**文件**：`core/agents/adapters/position/fundamental_analyst_v2.py`

```python
def _build_user_prompt(self, ...):
    stock_report = state.get("stock_analysis_report", {})
    reports_data = stock_report.get("reports", {})
    fundamentals_report = reports_data.get("fundamentals_report", "暂无基本面报告")
    
    return f"""
    === 基本面报告 ===
    {fundamentals_report}  # ← 使用单股分析的基本面报告
    """
```

**优势**：
- 如果有单股分析报告，直接引用，避免重复分析
- 如果没有，提示"暂无基本面报告"，Agent 会基于持仓信息进行分析

#### 技术面分析师 v2.0

**文件**：`core/agents/adapters/position/technical_analyst_v2.py`

**当前状态**：只使用 `market_data`，不使用单股分析报告

**建议**：可以参考基本面分析师的做法，利用单股分析的技术面报告

## 优化后的流程

### 场景 1：用户选择使用单股分析报告 + 有缓存

```
用户请求（use_stock_analysis=True）
  ↓
检查缓存（3小时内）
  ↓
找到缓存报告 ✅
  ↓
持仓分析工作流 v2.0
  ├─→ 持仓技术面分析师 v2.0（参考单股分析的技术面报告）
  ├─→ 持仓基本面分析师 v2.0（参考单股分析的基本面报告）
  └─→ 持仓风险评估师 v2.0
  ↓
持仓操作建议师 v2.0
```

### 场景 2：用户选择使用单股分析报告 + 无缓存

```
用户请求（use_stock_analysis=True）
  ↓
检查缓存（3小时内）
  ↓
没有缓存报告 ❌
  ↓
跳过单股分析
  ↓
持仓分析工作流 v2.0
  ├─→ 持仓技术面分析师 v2.0（基于持仓信息直接分析）
  ├─→ 持仓基本面分析师 v2.0（基于持仓信息直接分析）
  └─→ 持仓风险评估师 v2.0
  ↓
持仓操作建议师 v2.0
```

### 场景 3：用户选择不使用单股分析报告

```
用户请求（use_stock_analysis=False）
  ↓
跳过单股分析
  ↓
持仓分析工作流 v2.0
  ├─→ 持仓技术面分析师 v2.0（基于持仓信息直接分析）
  ├─→ 持仓基本面分析师 v2.0（基于持仓信息直接分析）
  └─→ 持仓风险评估师 v2.0
  ↓
持仓操作建议师 v2.0
```

## 优势总结

### ✅ 避免重复分析

- 如果有单股分析报告，持仓分析 Agent 直接引用，不重复分析
- 如果没有，持仓分析 Agent 基于持仓信息直接分析

### ✅ 用户可选

- `use_stock_analysis=True`：优先使用缓存的单股分析报告
- `use_stock_analysis=False`：不使用单股分析报告，直接进行持仓分析

### ✅ 性能优化

- 不强制执行单股分析，减少不必要的 API 调用
- 只使用缓存报告（3小时内），不创建新任务

### ✅ 灵活性

- 用户可以根据需求选择是否需要单股分析报告
- 系统会智能判断是否有可用的缓存报告

## 前端建议

### API 调用示例

```javascript
// 场景 1：使用单股分析报告（如果有缓存）
POST /api/portfolio/positions/analyze-by-code
{
  "code": "600519",
  "market": "CN",
  "use_stock_analysis": true  // ← 默认值
}

// 场景 2：不使用单股分析报告
POST /api/portfolio/positions/analyze-by-code
{
  "code": "600519",
  "market": "CN",
  "use_stock_analysis": false
}
```

### UI 建议

可以添加一个复选框：

```
☑️ 使用单股分析报告作为参考（如果有缓存）
```

或者更智能的提示：

```
检测到该股票有 15 分钟前的单股分析报告，是否使用？
[ 使用 ] [ 不使用 ]
```

## 文件修改清单

| 文件 | 修改内容 |
|------|--------|
| `app/models/portfolio.py` | 添加 `use_stock_analysis` 字段 |
| `app/services/portfolio_service.py` | 修改 `_get_stock_analysis_report` 添加 `skip_if_not_exists` 参数 |
| `app/services/portfolio_service.py` | 修改 `_get_stock_analysis_via_legacy` 添加 `skip_if_not_exists` 参数 |
| `app/services/portfolio_service.py` | 修改 `analyze_position_by_code` 根据用户选择获取单股分析报告 |

## 测试建议

1. **测试场景 1**：`use_stock_analysis=True` + 有缓存报告
   - 验证：使用缓存报告，不创建新任务
   
2. **测试场景 2**：`use_stock_analysis=True` + 无缓存报告
   - 验证：跳过单股分析，直接进行持仓分析
   
3. **测试场景 3**：`use_stock_analysis=False`
   - 验证：不检查缓存，直接进行持仓分析
   
4. **验证日志**：
   - `✅ 找到单股分析报告，将作为参考`
   - `ℹ️ 没有找到单股分析报告，将直接进行持仓分析`
   - `⏭️ 用户选择不使用单股分析报告`

