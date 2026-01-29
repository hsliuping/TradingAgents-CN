# 数据验证服务测试程序使用说明

## 概述

`test_data_validation_service.py` 是一个用于测试和验证 `DataValidationService` 功能的测试程序。它可以帮助您：

1. 检查数据验证服务的各个功能是否正常工作
2. 诊断数据完整性检查中的问题
3. 验证数据库中股票数据的完整性

## 已修复的问题

在创建测试程序的过程中，我们发现并修复了以下问题：

### 1. `analysis_date_str` 变量未定义问题

**问题描述：**
- `analysis_date_str` 变量只在 `check_historical_data=True` 时定义
- 但当 `check_financial_data=True` 且 `check_historical_data=False` 时，会使用未定义的 `analysis_date_str`，导致 `NameError`

**修复方案：**
- 将 `analysis_date_str` 的定义移到所有检查之前，确保在所有情况下都可使用
- 修改位置：`app/services/data_validation_service.py` 第115行之后

## 使用方法

### 基本用法

```bash
# 测试单个股票（使用当前日期）
python scripts/test_data_validation_service.py 000001

# 指定分析日期
python scripts/test_data_validation_service.py 000001 2025-01-24

# 指定市场类型
python scripts/test_data_validation_service.py 000001 --market cn
```

### 运行所有测试

```bash
# 运行完整的测试套件（包括所有检查项）
python scripts/test_data_validation_service.py 000001 --test-all

# 运行完整测试并检查数据库中的实际数据
python scripts/test_data_validation_service.py 000001 --test-all --inspect
```

### 批量测试

```bash
# 批量测试多个股票
python scripts/test_data_validation_service.py --batch 000001 600519 000002
```

### 自定义历史数据检查天数

```bash
# 检查近180天的历史数据（默认365天）
python scripts/test_data_validation_service.py 000001 --days 180
```

## 测试项目说明

测试程序包含以下测试项目：

### 1. 基础信息检查 (`test_basic_info_check`)
- 检查股票基础信息是否存在
- 验证集合：`stock_basic_info`（或对应的市场集合）

### 2. 历史数据检查 (`test_historical_data_check`)
- 检查指定日期范围内的历史数据是否存在
- 验证数据量是否足够（至少30个交易日）
- 检查分析日期当天的数据是否存在
- 验证集合：`stock_daily_quotes`、`stock_daily_history` 等

### 3. 财务数据检查 (`test_financial_data_check`)
- 检查财务数据是否存在
- 获取最新报告期信息
- 验证集合：`stock_financial_data`（或对应的市场集合）

### 4. 实时行情检查 (`test_realtime_quotes_check`)
- 检查实时行情数据是否存在
- 获取当前价格和更新时间
- 验证集合：`market_quotes`（或对应的市场集合）

### 5. 完整验证 (`test_full_validation`)
- 执行所有检查项
- 提供完整的验证结果和详细信息

### 6. 数据库数据检查 (`inspect_database_collections`)
- 直接检查数据库中实际存在的数据
- 显示各集合中的数据条数和日期范围
- 帮助诊断数据同步问题

## 输出说明

### 验证结果格式

```
✅ 通过 [测试名称]
消息: 股票 000001 的数据校验通过
```

或

```
❌ 失败 [测试名称]
消息: 股票 000001 的基础信息不存在，请先同步股票基础数据
缺失数据: 基础信息
```

### 详细信息

测试程序会输出详细的检查信息，包括：

- **基础信息详情**：股票名称、上市日期等
- **历史数据详情**：
  - 数据条数
  - 最早和最晚日期
  - 分析日期数据是否存在
  - 检查的集合列表
- **财务数据详情**：最新报告期、报告类型
- **实时行情详情**：当前价格、更新时间

## 常见问题排查

### 1. 基础信息不存在

**可能原因：**
- 股票代码错误
- 数据未同步
- 市场类型不匹配

**解决方法：**
- 检查股票代码是否正确（6位数字）
- 运行数据同步服务
- 确认市场类型（cn/hk/us）是否正确

### 2. 历史数据不足

**可能原因：**
- 数据同步不完整
- 日期范围设置过大
- 股票上市时间较晚

**解决方法：**
- 检查数据同步日志
- 调整 `historical_days` 参数
- 确认股票上市日期

### 3. 财务数据不存在

**可能原因：**
- 财务数据同步未完成
- 股票为新上市股票
- 数据源问题

**解决方法：**
- 财务数据是可选的，不影响基础分析
- 检查财务数据同步服务状态
- 确认数据源配置

### 4. 实时行情不存在

**可能原因：**
- 实时行情同步未运行
- 非交易时间
- 数据源连接问题

**解决方法：**
- 实时行情是可选的，不影响历史分析
- 检查实时行情同步服务状态
- 确认数据源配置

## 注意事项

1. **数据库连接**：确保 MongoDB 数据库已启动并可连接
2. **环境变量**：确保 `.env` 文件中的数据库配置正确
3. **依赖安装**：确保已安装所有必要的 Python 依赖包
4. **异步环境**：测试程序使用异步操作，需要 Python 3.7+

## 示例输出

```
================================================================================
🚀 开始数据验证测试
================================================================================

============================================================
📋 测试5: 完整数据验证（所有检查项）
============================================================
股票代码: 000001
分析日期: 2025-01-24
市场类型: cn
历史数据天数: 365

✅ 通过 [完整验证]
消息: 股票 000001 的数据校验通过

📋 详细信息:
  basic_info: {'exists': True, 'name': '平安银行', 'list_date': '1991-04-03'}
  historical_data: {'exists': True, 'count': 245, 'earliest_date': '2024-01-02', 'latest_date': '2025-01-24', 'analysis_date_exists': True, 'date_range': '2024-01-24 至 2025-01-24'}
  financial_data: {'exists': True, 'latest_report_period': '2024-09-30', 'report_type': 'Q3'}
  realtime_quotes: {'exists': True, 'current_price': 12.34, 'update_time': '2025-01-24 15:00:00'}

================================================================================
✅ 测试完成
================================================================================
```

## 相关文件

- `app/services/data_validation_service.py` - 数据验证服务实现
- `app/services/task_analysis_service.py` - 任务分析服务（使用数据验证）
- `app/core/database.py` - 数据库连接管理

## 反馈和问题

如果测试过程中发现问题，请：

1. 记录完整的错误信息
2. 记录使用的命令和参数
3. 检查数据库连接和配置
4. 查看日志文件获取更多信息
