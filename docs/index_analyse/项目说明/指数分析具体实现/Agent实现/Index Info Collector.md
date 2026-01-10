# Index Info Collector (指数信息收集器)

**职责**: 解析用户输入，标准化指数代码和名称

**调用工具/接口**:
- `tradingagents.utils.index_resolver.IndexResolver.resolve()`
- AKShare数据库查询接口

**数据获取流程**:
```python
# 1. 输入处理
code = state.get("company_of_interest")  # 用户原始输入

# 2. 多层级解析
resolved = asyncio.run(IndexResolver.resolve(code, market_type))

# 3. 解析策略优先级
# - 概念板块匹配 (980022 -> BK0022 -> 半导体)
# - 行业板块匹配 
# - 标准指数验证 (000300.SH)
```

**数据处理**:
- 输入格式标准化（移除前缀后缀）
- 动态查询AKShare板块列表
- 代码到名称的智能映射
- 缓存机制避免重复查询

**输出信息结构**:
```python
{
    "name": "半导体",                    # 标准名称
    "symbol": "半导体",                   # AKShare查询代码
    "source_type": "concept",            # 数据源类型
    "original_code": "980022",           # 用户原始输入
    "description": "半导体概念板块"        # 描述信息
}