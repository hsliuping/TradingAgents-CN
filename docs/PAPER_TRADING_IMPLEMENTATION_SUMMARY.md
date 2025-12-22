# 模拟交易 name 字段实现总结

## 问题

模拟交易（paper trading）的持仓表 `paper_positions` 缺少股票名称字段，导致前端显示时无法显示股票名称。

## 解决方案

### 1. 后端修改 (`app/routers/paper.py`)

#### 新增函数：`_get_stock_name(code: str, market: str) -> str`

**位置**：第 194-250 行

**功能**：根据市场类型获取股票名称

**数据源**：
- **A股 (CN)**：从 `stock_basic_info` 表查询
- **港股 (HK)**：使用 `get_hk_stock_info_unified()` 统一接口
  - 根据数据库配置选择数据源（AKShare → Yahoo Finance）
  - 与 A股数据源管理逻辑一致
- **美股 (US)**：使用硬编码映射字典 + 默认格式

#### 修改位置 1：创建新持仓时保存 name 字段

**位置**：第 418-435 行（买入逻辑）

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

**位置**：第 340-363 行（`/api/paper/account` 端点）

```python
detailed_positions.append({
    "code": code,
    "name": name,  # 添加股票名称到响应
    ...
})
```

#### 修改位置 3：列出持仓时包含 name 字段

**位置**：第 599-627 行（`/api/paper/positions` 端点）

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
3. 根据市场类型从不同数据源获取
4. 将 `name` 字段保存到 `paper_positions` 表
5. 后续查询时直接从数据库返回 `name` 字段

## 关键特性

✅ **多市场支持**：A股、港股、美股

✅ **数据源灵活性**：港股使用统一接口，根据数据库配置选择数据源

✅ **容错机制**：如果获取名称失败，使用默认格式（如 "港股00700"）

✅ **性能优化**：名称保存在数据库，避免重复查询

## 测试

### 测试脚本

1. `tests/test_paper_positions_name.py` - 检查现有持仓的 name 字段
2. `tests/test_new_paper_position.py` - 模拟新建持仓时的 name 字段保存
3. `tests/test_paper_trading_name_field.py` - pytest 集成测试

### 测试结果

✅ 新建持仓时自动保存 name 字段（100% 完整率）

⚠️ 现有 7 条旧测试数据没有 name 字段（0% 完整率）
- 这些是测试数据，不需要修复

## 使用说明

### 前端

新增加的模拟交易持仓会自动包含 `name` 字段：

```javascript
position.name  // 例如：宁德时代、腾讯控股、苹果公司
```

### 后端

无需额外配置，自动在创建持仓时获取并保存股票名称。

## 支持的市场

| 市场 | 代码 | 名称来源 | 示例 |
|------|------|--------|------|
| A股 | CN | stock_basic_info | 宁德时代 |
| 港股 | HK | get_hk_stock_info_unified() | 腾讯控股 |
| 美股 | US | 映射字典 | 苹果公司 |

