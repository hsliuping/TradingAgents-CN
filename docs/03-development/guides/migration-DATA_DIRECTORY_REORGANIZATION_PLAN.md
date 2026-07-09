# 数据目录重新规划方案

## 📊 当前问题分析

### 🔍 现状
项目中存在多个分散的数据目录，导致数据管理混乱：

1. **项目根目录 `data/`** - 数据库数据、报告、会话
2. **Web目录 `web/data/`** - Web应用相关数据
3. **Results目录 `results/`** - 分析结果报告
4. **缓存目录 `tradingagents/dataflows/data_cache/`** - 数据缓存

### ❌ 存在的问题
- 数据分散存储，难以管理
- 路径配置复杂，容易出错
- 备份和清理困难
- 开发和部署环境不一致

## 🎯 新的目录结构设计

### 📁 统一数据根目录：`data/`

```
data/
├── 📊 cache/                    # 数据缓存 (原 tradingagents/dataflows/data_cache/)
│   ├── stock_data/             # 股票数据缓存
│   ├── news_data/              # 新闻数据缓存
│   ├── fundamentals/           # 基本面数据缓存
│   └── metadata/               # 缓存元数据
│
├── 📈 analysis_results/         # 分析结果 (原 web/data/analysis_results/ + results/)
│   ├── summary/                # 分析摘要
│   ├── detailed/               # 详细报告
│   └── exports/                # 导出文件 (PDF, Word, MD)
│
├── 🗄️ databases/               # 数据库数据 (原 data/mongodb/, data/redis/)
│   ├── mongodb/                # MongoDB数据文件
│   └── redis/                  # Redis数据文件
│
├── 📝 sessions/                # 会话数据 (合并 data/sessions/ + web/data/sessions/)
│   ├── web_sessions/           # Web会话
│   └── cli_sessions/           # CLI会话
│
├── 📋 logs/                    # 日志文件 (原 web/data/operation_logs/)
│   ├── application/            # 应用日志
│   ├── operations/             # 操作日志
│   └── user_activities/        # 用户活动日志 (原 web/data/user_activities/)
│
├── 🔧 config/                  # 配置文件缓存
│   ├── user_configs/           # 用户配置
│   └── system_configs/         # 系统配置
│
└── 📦 temp/                    # 临时文件
    ├── downloads/              # 下载的临时文件
    └── processing/             # 处理中的临时文件
```

## 🔧 环境变量配置

### 新增环境变量
```bash
# 统一数据根目录
TRADINGAGENTS_DATA_DIR=./data

# 子目录配置（可选，使用默认值）
TRADINGAGENTS_CACHE_DIR=${TRADINGAGENTS_DATA_DIR}/cache
TRADINGAGENTS_RESULTS_DIR=${TRADINGAGENTS_DATA_DIR}/analysis_results
TRADINGAGENTS_SESSIONS_DIR=${TRADINGAGENTS_DATA_DIR}/sessions
TRADINGAGENTS_LOGS_DIR=${TRADINGAGENTS_DATA_DIR}/logs
TRADINGAGENTS_CONFIG_DIR=${TRADINGAGENTS_DATA_DIR}/config
TRADINGAGENTS_TEMP_DIR=${TRADINGAGENTS_DATA_DIR}/temp
```

## 📋 迁移计划

### 阶段1：创建新目录结构
1. 创建统一的 `data/` 目录结构
2. 更新环境变量配置
3. 修改代码中的路径引用

### 阶段2：数据迁移
1. 迁移缓存数据：`tradingagents/dataflows/data_cache/` → `data/cache/`
2. 迁移分析结果：`results/` + `web/data/analysis_results/` → `data/analysis_results/`
3. 迁移会话数据：`data/sessions/` + `web/data/sessions/` → `data/sessions/`
4. 迁移日志数据：`web/data/operation_logs/` + `web/data/user_activities/` → `data/logs/`

### 阶段3：代码更新
1. 更新路径配置逻辑
2. 修改文件操作代码
3. 更新文档和示例

### 阶段4：清理旧目录
1. 验证新目录结构正常工作
2. 删除旧的分散目录
3. 更新 `.gitignore` 文件

## 🎯 实施优势

### ✅ 优点
1. **统一管理**：所有数据集中在一个根目录下
2. **清晰分类**：按功能明确分类，易于理解
3. **便于备份**：只需备份一个 `data/` 目录
4. **环境一致**：开发、测试、生产环境配置一致
5. **易于扩展**：新增数据类型时有明确的存放位置

### 🔧 配置灵活性
- 支持环境变量自定义路径
- 支持相对路径和绝对路径
- 支持Docker容器化部署
- 支持多环境配置

## 📝 注意事项

1. **向后兼容**：迁移过程中保持向后兼容
2. **数据安全**：迁移前做好数据备份
3. **渐进式迁移**：分阶段实施，降低风险
4. **文档更新**：及时更新相关文档和示例

## 🚀 下一步行动

1. 确认方案可行性
2. 创建迁移脚本
3. 在测试环境验证
4. 逐步在生产环境实施