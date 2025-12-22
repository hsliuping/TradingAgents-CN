# 模拟交易 name 字段实现文档

## 问题描述

模拟交易（paper trading）的持仓表 `paper_positions` 缺少股票名称字段，导致前端显示时无法显示股票名称。

## 解决方案

### 1. 后端修改 (`app/routers/paper.py`)

#### 新增函数：`_get_stock_name()`

```python
async def _get_stock_name(code: str, market: str) -> str:
    """
    获取股票名称（支持多市场）

    - A股：从 stock_basic_info 表获取
    - 港股：使用统一接口 get_hk_stock_info_unified()
      （根据数据库配置选择数据源，与A股逻辑一致）
    - 美股：使用硬编码映射字典，默认格式 "美股{code}"
    """
```

**港股数据源优先级**：
- 从数据库 `hk_data_sources` 表读取用户启用的数据源配置
- 按优先级尝试：AKShare → Yahoo Finance → 默认格式
- 与 A股的数据源管理逻辑完全一致

#### 修改位置 1：创建新持仓时保存 name 字段

**位置**：第 418-435 行（买入逻辑中创建新持仓）

```python
# 获取股票名称（根据市场类型）
stock_name = await _get_stock_name(normalized_code, market)

new_pos = {
    ...
    "name": stock_name,  # 添加股票名称
    ...
}
```

#### 修改位置 2：返回持仓列表时包含 name 字段

**位置**：第 591-620 行（`/api/paper/positions` 端点）

```python
detailed_positions.append({
    "code": code,
    "name": name,  # 添加股票名称到响应
    ...
})
```

#### 修改位置 3：列出持仓时包含 name 字段

**位置**：第 591-620 行（`list_positions` 端点）

```python
enriched.append({
    "code": code,
    "name": name,  # 添加股票名称到响应
    ...
})
```

## 数据流

### 新建模拟交易时

1. 用户下单（买入）
2. 后端调用 `_get_stock_name()` 获取股票名称
3. 根据市场类型从不同数据源获取：
   - **A股**：查询 `stock_basic_info` 表
   - **港股**：调用 `get_hk_company_name_improved()`
   - **美股**：使用映射字典或默认格式
4. 将 `name` 字段保存到 `paper_positions` 表
5. 后续查询时直接从数据库返回 `name` 字段

## 测试

### 现有数据

- 数据库中有 7 条旧的 `paper_positions` 记录（测试数据）
- 这些记录没有 `name` 字段（0% 完整率）
- **不需要修复这些旧数据**

### 新数据

- 新建的模拟交易持仓会自动保存 `name` 字段
- 前端可以直接显示股票名称，无需额外 API 调用

## 测试脚本

### 1. `tests/test_paper_positions_name.py`
检查现有持仓的 name 字段完整率

### 2. `tests/test_new_paper_position.py`
模拟新建持仓时的 name 字段保存

### 3. `tests/test_paper_trading_name_field.py`
pytest 集成测试

## 使用说明

### 前端

新增加的模拟交易持仓会自动包含 `name` 字段，可以直接显示：

```javascript
// 持仓列表中的股票名称
position.name  // 例如：宁德时代、腾讯控股、苹果公司
```

### 后端

无需额外配置，自动在创建持仓时获取并保存股票名称。

## 支持的市场

| 市场 | 代码 | 名称来源 | 示例 |
|------|------|--------|------|
| A股 | CN | stock_basic_info | 宁德时代 |
| 港股 | HK | get_hk_company_name_improved() | 腾讯控股 |
| 美股 | US | 映射字典 | 苹果公司 |

## 注意事项

1. **旧数据**：现有的 7 条持仓记录没有 `name` 字段，但不影响新数据
2. **港股和美股**：使用专门的数据源获取名称，不依赖 `stock_basic_info`
3. **容错机制**：如果获取名称失败，会使用默认格式（如 "港股00700"）

