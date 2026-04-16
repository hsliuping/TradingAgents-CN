# 📊 Tushare财务数据功能完整指南

## 🎯 概述

根据Tushare官方文档 (https://tushare.pro/document/2?doc_id=33)，我们已经完整实现了Tushare财务数据获取功能，支持利润表、资产负债表、现金流量表和财务指标的完整获取。

### ✨ 核心特性

- **完整财务报表**: 利润表、资产负债表、现金流量表
- **丰富财务指标**: ROE、ROA、毛利率等60+个指标
- **多期间查询**: 支持按时间范围获取历史数据
- **数据标准化**: 统一的数据格式和字段映射
- **高效API调用**: 优化的批量获取和限流控制
- **错误处理**: 完善的异常处理和重试机制

## 🔧 配置说明

### 1. 获取Tushare API Token

1. 访问 [Tushare官网](https://tushare.pro/weborder/#/login?reg=tacn) 注册账号
2. 登录后在个人中心获取API Token
3. 配置Token到系统中

### 2. 配置方式

#### 方式一：环境变量配置
```bash
# Windows
set TUSHARE_TOKEN=your_token_here

# Linux/Mac
export TUSHARE_TOKEN=your_token_here
```

#### 方式二：.env文件配置
```bash
# 在项目根目录的.env文件中添加
TUSHARE_TOKEN=your_token_here
```

#### 方式三：配置文件
```python
# 在app/core/config.py中已支持
TUSHARE_TOKEN: str = Field(default="", description="Tushare API Token")
```

## 📊 API接口说明

### 核心方法

#### 1. get_financial_data()
```python
async def get_financial_data(
    symbol: str, 
    report_type: str = "quarterly", 
    period: str = None, 
    limit: int = 4
) -> Optional[Dict[str, Any]]
```

**参数说明**:
- `symbol`: 股票代码 (如: "000001")
- `report_type`: 报告类型 ("quarterly"/"annual")
- `period`: 指定报告期 (YYYYMMDD格式)，为空则获取最新数据
- `limit`: 获取记录数量，默认4条（最近4个季度）

**返回数据结构**:
```python
{
    # 基础信息
    "symbol": "000001",
    "ts_code": "000001.SZ",
    "report_period": "20231231",
    "ann_date": "20240320",
    "report_type": "annual",
    
    # 利润表核心指标
    "revenue": 500000000000.0,      # 营业收入
    "net_income": 50000000000.0,    # 净利润
    "oper_profit": 60000000000.0,   # 营业利润
    "total_profit": 55000000000.0,  # 利润总额
    "oper_cost": 300000000000.0,    # 营业成本
    "rd_exp": 10000000000.0,        # 研发费用
    
    # 资产负债表核心指标
    "total_assets": 4500000000000.0,    # 总资产
    "total_liab": 4200000000000.0,      # 总负债
    "total_equity": 280000000000.0,     # 股东权益
    "money_cap": 180000000000.0,        # 货币资金
    "accounts_receiv": 50000000000.0,   # 应收账款
    "inventories": 30000000000.0,       # 存货
    "fix_assets": 200000000000.0,       # 固定资产
    
    # 现金流量表核心指标
    "n_cashflow_act": 80000000000.0,        # 经营活动现金流
    "n_cashflow_inv_act": -20000000000.0,   # 投资活动现金流
    "n_cashflow_fin_act": -10000000000.0,   # 筹资活动现金流
    "c_cash_equ_end_period": 180000000000.0, # 期末现金
    
    # 财务指标
    "roe": 23.21,                   # 净资产收益率
    "roa": 1.44,                    # 总资产收益率
    "gross_margin": 40.0,           # 销售毛利率
    "netprofit_margin": 10.0,       # 销售净利率
    "debt_to_assets": 93.33,        # 资产负债率
    "current_ratio": 1.2,           # 流动比率
    "quick_ratio": 0.8,             # 速动比率
    
    # 原始数据（用于详细分析）
    "raw_data": {
        "income_statement": [...],      # 利润表原始数据
        "balance_sheet": [...],         # 资产负债表原始数据
        "cashflow_statement": [...],    # 现金流量表原始数据
        "financial_indicators": [...],  # 财务指标原始数据
        "main_business": [...]          # 主营业务构成数据
    }
}
```

#### 2. get_financial_data_by_period()
```python
async def get_financial_data_by_period(
    symbol: str, 
    start_period: str = None, 
    end_period: str = None, 
    report_type: str = "quarterly"
) -> Optional[List[Dict[str, Any]]]
```

按时间范围获取多期财务数据，返回按报告期倒序排列的数据列表。

#### 3. get_financial_indicators_only()
```python
async def get_financial_indicators_only(
    symbol: str, 
    limit: int = 4
) -> Optional[Dict[str, Any]]
```

仅获取财务指标数据的轻量级接口，适用于快速获取关键指标。

## 🚀 使用示例

### 1. 基础使用

```python
from tradingagents.dataflows.providers.tushare_provider import get_tushare_provider

# 获取提供者实例
provider = get_tushare_provider()

# 检查连接状态
if provider.is_available():
    # 获取最新财务数据
    financial_data = await provider.get_financial_data("000001")
    
    if financial_data:
        print(f"营业收入: {financial_data['revenue']:,.0f}")
        print(f"净利润: {financial_data['net_income']:,.0f}")
        print(f"ROE: {financial_data['roe']:.2f}%")
```

### 2. 获取指定期间数据

```python
# 获取2023年年报数据
annual_data = await provider.get_financial_data(
    symbol="000001",
    period="20231231",
    limit=1
)

# 获取最近4个季度数据
quarterly_data = await provider.get_financial_data(
    symbol="000001",
    report_type="quarterly",
    limit=4
)
```

### 3. 按时间范围查询

```python
# 获取2022-2023年的所有财务数据
period_data = await provider.get_financial_data_by_period(
    symbol="000001",
    start_period="20220101",
    end_period="20231231"
)

if period_data:
    for data in period_data:
        period = data['report_period']
        revenue = data['revenue']
        print(f"{period}: 营业收入 {revenue:,.0f}")
```

### 4. 仅获取财务指标

```python
# 快速获取关键财务指标
indicators = await provider.get_financial_indicators_only("000001")

if indicators:
    latest = indicators['financial_indicators'][0]
    print(f"ROE: {latest['roe']:.2f}%")
    print(f"ROA: {latest['roa']:.2f}%")
    print(f"毛利率: {latest['gross_margin']:.2f}%")
```

### 5. 集成到财务数据服务

```python
from app.services.financial_data_service import get_financial_data_service

# 获取并保存财务数据
provider = get_tushare_provider()
service = await get_financial_data_service()

financial_data = await provider.get_financial_data("000001")

if financial_data:
    saved_count = await service.save_financial_data(
        symbol="000001",
        financial_data=financial_data,
        data_source="tushare",
        market="CN"
    )
    print(f"保存了 {saved_count} 条记录")
```

### 6. 批量处理多只股票

```python
symbols = ["000001", "000002", "600000", "600036"]

for symbol in symbols:
    try:
        financial_data = await provider.get_financial_data(symbol)
        
        if financial_data:
            # 处理财务数据
            process_financial_data(symbol, financial_data)
        
        # API限流
        await asyncio.sleep(0.5)
        
    except Exception as e:
        print(f"处理 {symbol} 失败: {e}")
```

## 📈 数据字段映射

### Tushare原始字段 → 标准化字段

#### 利润表字段
| Tushare字段 | 标准化字段 | 说明 |
|------------|-----------|------|
| revenue | revenue | 营业收入 |
| oper_rev | oper_rev | 营业收入 |
| n_income | net_income | 净利润 |
| n_income_attr_p | net_profit | 归属母公司净利润 |
| oper_profit | oper_profit | 营业利润 |
| total_profit | total_profit | 利润总额 |
| oper_cost | oper_cost | 营业成本 |
| rd_exp | rd_exp | 研发费用 |

#### 资产负债表字段
| Tushare字段 | 标准化字段 | 说明 |
|------------|-----------|------|
| total_assets | total_assets | 总资产 |
| total_liab | total_liab | 总负债 |
| total_hldr_eqy_exc_min_int | total_equity | 股东权益 |
| total_cur_assets | total_cur_assets | 流动资产 |
| total_nca | total_nca | 非流动资产 |
| money_cap | money_cap | 货币资金 |
| accounts_receiv | accounts_receiv | 应收账款 |
| inventories | inventories | 存货 |

#### 现金流量表字段
| Tushare字段 | 标准化字段 | 说明 |
|------------|-----------|------|
| n_cashflow_act | n_cashflow_act | 经营活动现金流 |
| n_cashflow_inv_act | n_cashflow_inv_act | 投资活动现金流 |
| n_cashflow_fin_act | n_cashflow_fin_act | 筹资活动现金流 |
| c_cash_equ_end_period | c_cash_equ_end_period | 期末现金 |

#### 财务指标字段
| Tushare字段 | 标准化字段 | 说明 |
|------------|-----------|------|
| roe | roe | 净资产收益率 |
| roa | roa | 总资产收益率 |
| gross_margin | gross_margin | 销售毛利率 |
| netprofit_margin | netprofit_margin | 销售净利率 |
| debt_to_assets | debt_to_assets | 资产负债率 |
| current_ratio | current_ratio | 流动比率 |
| quick_ratio | quick_ratio | 速动比率 |

## 🔍 高级功能

### 1. 财务数据分析

```python
def analyze_financial_health(financial_data):
    """分析财务健康度"""
    roe = financial_data.get('roe', 0)
    debt_ratio = financial_data.get('debt_to_assets', 0)
    current_ratio = financial_data.get('current_ratio', 0)
    
    score = 0
    if roe > 15: score += 30
    if debt_ratio < 60: score += 30
    if current_ratio > 1.2: score += 40
    
    return {
        'score': score,
        'level': 'excellent' if score >= 80 else 'good' if score >= 60 else 'fair'
    }
```

### 2. 趋势分析

```python
async def analyze_financial_trend(symbol, periods=8):
    """分析财务指标趋势"""
    provider = get_tushare_provider()
    
    financial_data = await provider.get_financial_data(
        symbol=symbol,
        limit=periods
    )
    
    if financial_data and financial_data.get('raw_data'):
        indicators = financial_data['raw_data']['financial_indicators']
        
        # 计算ROE趋势
        roe_trend = [item.get('roe', 0) for item in indicators]
        
        # 计算增长率
        if len(roe_trend) >= 2:
            growth_rate = (roe_trend[0] - roe_trend[1]) / roe_trend[1] * 100
            return {
                'roe_trend': roe_trend,
                'growth_rate': growth_rate,
                'trend': 'up' if growth_rate > 0 else 'down'
            }
    
    return None
```

### 3. 行业对比

```python
async def compare_with_industry(symbols, metric='roe'):
    """行业财务指标对比"""
    provider = get_tushare_provider()
    results = {}
    
    for symbol in symbols:
        financial_data = await provider.get_financial_data(symbol)
        if financial_data:
            results[symbol] = financial_data.get(metric, 0)
        
        await asyncio.sleep(0.5)  # API限流
    
    # 计算行业平均值
    values = list(results.values())
    industry_avg = sum(values) / len(values) if values else 0
    
    return {
        'individual': results,
        'industry_average': industry_avg,
        'ranking': sorted(results.items(), key=lambda x: x[1], reverse=True)
    }
```

## ⚠️ 注意事项

### 1. API限制
- Tushare有调用频率限制，建议在请求间添加延迟
- 不同积分等级有不同的调用限制
- 建议使用批量接口减少API调用次数

### 2. 数据质量
- 财务数据可能存在更新延迟
- 部分指标可能为空值，需要做空值处理
- 建议结合多个数据源进行验证

### 3. 错误处理
- 网络异常时会自动重试
- API限制时会返回None
- 建议在业务逻辑中添加异常处理

## 📊 测试验证

运行测试脚本验证功能：

```bash
# 运行Tushare财务数据测试
python test_tushare_financial_data.py
```

测试内容包括：
- ✅ Tushare连接测试
- ✅ 基础财务数据获取
- ✅ 财务指标获取
- ✅ 期间范围数据获取
- ✅ 数据集成测试
- ✅ 多股票批量测试

## 📝 总结

优化后的Tushare财务数据功能提供了：

- ✅ **完整性**: 支持利润表、资产负债表、现金流量表和财务指标
- ✅ **标准化**: 统一的数据格式和字段映射
- ✅ **灵活性**: 支持多种查询方式和参数配置
- ✅ **可靠性**: 完善的错误处理和重试机制
- ✅ **高效性**: 优化的API调用和批量处理
- ✅ **集成性**: 与财务数据服务无缝集成

该功能特别适合：
- 📊 **基本面分析**: 完整的财务报表数据支持深度分析
- 🔍 **投资研究**: 丰富的财务指标支持投资决策
- 📈 **趋势分析**: 多期间数据支持趋势分析
- 🤖 **量化策略**: 标准化数据支持策略开发
