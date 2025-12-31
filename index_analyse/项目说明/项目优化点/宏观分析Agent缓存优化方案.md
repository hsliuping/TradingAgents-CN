
<!--
 * @Author: zhengweicheng 46236959+zwczwczwc@users.noreply.github.com
 * @Date: 2025-12-31 10:09:26
 * @LastEditors: zhengweicheng 46236959+zwczwczwc@users.noreply.github.com
 * @LastEditTime: 2026-01-01 00:54:59
 * @FilePath: /TradingAgents-CN-Test/index_analyse/项目说明/项目优化点/宏观分析Agent缓存优化方案.md
 * @Description: 这是默认设置,请设置`customMade`, 打开koroFileHeader查看配置 进行设置: https://github.com/OBKoro1/koro1FileHeader/wiki/%E9%85%8D%E7%BD%AE
-->
# 宏观分析Agent缓存优化方案

## 1. 问题背景

宏观分析Agent (`Macro Analyst`) 负责根据宏观经济数据 (`GDP`、`CPI`、`PMI`、`M2`、`LPR` 等) 进行分析并生成报告。由于宏观数据更新频率相对较低 (例如，`GDP` 为季度数据，其他指标多为月度数据)，每次请求都重新执行数据获取和分析过程会导致资源浪费，并可能增加API调用成本和响应时间。

目前 `Macro Analyst` 通过调用 `tradingagents/tools/index_tools.py` 中的 `fetch_macro_data` 工具来获取宏观数据。

## 2. 优化目标

引入缓存机制，复用近期已分析的宏观报告，从而：
- 降低系统负载
- 减少不必要的外部API调用
- 缩短报告生成时间

## 3. 改造方案

### 3.1. 缓存策略

- **缓存介质**: 利用现有项目中的MongoDB数据库进行数据存储。
- **缓存键 (Cache Key)**: 考虑使用 `macro_analysis:{trade_date}` 作为缓存键，其中 `trade_date` 是进行宏观分析的日期。
- **缓存有效期 (TTL)**: 考虑到宏观数据更新频率，建议设置缓存有效期为7天。这意味着如果7天内有相同的请求，将直接返回缓存结果。
- **数据存储**: 缓存中应包含宏观分析报告的结构化输出 (例如 `JSON` 格式) 以及可能相关的原始数据或用于生成报告的必要信息，以便在复用时能完整重建报告内容。

### 3.2. 实现位置

缓存逻辑将集成到 `tradingagents/tools/index_tools.py` 模块中的 `fetch_macro_data` 工具函数内。

### 3.3. 具体实现步骤

1. **引入MongoDB连接**: 在 `fetch_macro_data` 函数中，通过 `from tradingagents.config.database_manager import get_mongodb_db` 引入MongoDB连接。
2. **构建缓存键**: 根据传入的 `end_date` (即 `query_date`) 构造唯一的缓存键。例如：`cache_key = f"macro_analysis:{end_date}"`。
3. **查询缓存**: 在执行实际数据获取和分析之前，首先查询MongoDB中是否存在对应的缓存记录。
    - 查询条件包括 `cache_key` 和一个时间戳判断，确保缓存未过期 (例如，`cache_timestamp > (now - 7 days)` )。
4. **处理缓存命中**: 如果找到有效的缓存记录，直接从缓存中提取分析报告并返回。
5. **处理缓存未命中**: 如果未找到有效的缓存记录或缓存已过期，则执行原有的数据获取和分析逻辑。
    - **执行分析**: 调用 `provider.get_macro_data(end_date=query_date)` 获取宏观数据，并进行后续分析处理。
    - **存储到缓存**: 将新生成的分析报告 (包括原始数据和格式化报告) 存储到MongoDB中，并关联 `cache_key` 和当前时间戳，设置过期时间。
6. **错误处理**: 确保在缓存读写失败时，不影响正常的宏观数据获取和分析流程，即降级为不使用缓存。

## 4. 预期效益

- 大幅减少 `Macro Analyst` 代理的执行时间。
- 降低对外部宏观数据API的调用频率，节省成本。
- 提高系统整体的响应速度和用户体验。

## 5. 待讨论事项

- 具体缓存数据结构：除了最终报告，是否需要缓存原始宏观数据？如果需要，如何存储和反序列化？
- 缓存键的精确性：是否需要考虑除了 `trade_date` 之外的其他参数来构成缓存键，以应对未来可能引入的更多分析维度？
- 缓存更新策略：除了TTL，是否需要考虑手动触发缓存更新的机制 (例如，当检测到宏观数据源有更新时)？

## 6. 实施记录 (2026-01-01)

### 6.1. 完成情况

- **代码修改**: 已修改 `tradingagents/tools/index_tools.py` 中的 `fetch_macro_data` 函数，实现了基于 MongoDB 的缓存读取和写入逻辑。
- **缓存键设计**: 采用 `macro_analysis:{target_date}`，其中 `target_date` 为传入的查询日期或当前日期 (YYYY-MM-DD)。
- **TTL控制**: 设置了 7 天的有效期判断，过期后自动刷新。
- **故障降级**: 添加了完善的 `try-except` 块，确保在数据库连接失败时自动降级为直接调用外部 API，不影响主流程。
- **测试验证**: 创建了 `tests/test_macro_cache.py` 单元测试，覆盖了“缓存命中”、“缓存过期”、“首次写入”及“数据库故障”四种场景，全部测试通过。

### 6.2. 验证结果

- **功能性**: 成功实现了缓存的“查询-命中返回”和“未命中-获取-写入”闭环。
- **健壮性**: 在模拟数据库连接失败的情况下，系统能够正常回退到无缓存模式运行。
- **性能**: 缓存命中时，无需进行外部 API 调用，响应时间显著降低。