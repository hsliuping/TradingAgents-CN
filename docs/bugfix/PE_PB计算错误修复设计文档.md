# PE/PB 计算错误 Bug 修复设计文档

**文档版本**: v1.0  
**创建日期**: 2026-06-10  
**状态**: 待评审  
**优先级**: 🔴 高

---

## 1. 问题描述

### 1.1 问题现象

在基本面分析中，部分股票的 **PE（市盈率）** 和 **PB（市净率）** 计算结果严重偏离真实值。

**示例：华电新能（600930）**

| 指标 | 系统报告值 | 真实值（BaoStock） | 偏差倍数 |
|:---|:---:|:---:|:---:|
| **PE** | **200.0倍** | **37.27倍** | **5.4倍** |
| **PB** | **3.78倍** | **2.16倍** | **1.75倍** |
| **股价** | ¥5.72 | ¥5.72 | ✅ 正确 |

### 1.2 问题日志

```
2026-06-10 20:22:47,585 | WARNING | ⚠️ [AKShare-总市值-全部失败] 无可用总市值数据
2026-06-10 20:22:47,588 | INFO | ✅ [AKShare-PE计算-第2层成功] PE(单期): 股价10.0 / EPS0.0500 = 200.0倍
2026-06-10 20:22:47,588 | INFO | ✅ [AKShare-PB计算-第2层成功] PB: 股价10.0 / BPS2.647693 = 3.78倍
```

---

## 2. 问题根源分析

### 2.1 根本原因

问题出在 `tradingagents/dataflows/optimized_china_data.py` 的 **`_estimate_financial_metrics`** 方法中：

```python
# 文件：optimized_china_data.py
# 位置：第 973-982 行

def _estimate_financial_metrics(self, symbol: str, current_price: str) -> dict:
    """获取真实财务指标（从 MongoDB、AKShare、Tushare 获取，失败则抛出异常）"""

    # 🔴 问题代码：股价解析失败时使用默认值 10.0
    try:
        price_value = float(current_price.replace('¥', '').replace(',', ''))
    except:
        price_value = 10.0  # ⚠️ 默认值！这就是问题所在！
```

### 2.2 问题链条

```
1. 股价获取失败 → current_price = "N/A"
2. 解析失败 → float("N/A") 抛出异常
3. 使用默认值 → price_value = 10.0（错误！）
4. PE计算错误 → PE = 10.0 / 0.05 = 200倍（错误！）
```

### 2.3 影响范围

- **受影响的股票**：所有在 `get_china_stock_data_unified` 接口中无法获取实时股价的股票
- **影响场景**：基本面分析师调用 `get_stock_fundamentals_unified` 工具时
- **影响程度**：PE/PB 计算结果完全错误，导致投资建议严重偏差

---

## 3. 修复方案

### 3.1 方案选择

#### 方案 A：修复降级逻辑，优先使用 BaoStock 实时 PE/PB（推荐）✅

**优点**：
- 绕过股价获取问题，直接使用可靠数据源
- 实现简单，风险低
- 性能最优（避免重复计算）

**缺点**：
- 依赖 BaoStock 数据源可用性

#### 方案 B：修复股价获取逻辑，确保使用真实股价

**优点**：
- 彻底解决问题根源
- 所有计算都基于真实数据

**缺点**：
- 实现复杂，需要修改多处代码
- 风险较高

**推荐方案 A**，原因：
1. BaoStock 是可靠的备用数据源
2. 实现简单，风险可控
3. 不需要大幅重构现有代码

### 3.2 详细修复方案（方案 A）

#### 修复点 1：修改 `_estimate_financial_metrics` 方法

**文件**：`tradingagents/dataflows/optimized_china_data.py`  
**位置**：第 973-982 行

**修改前**：
```python
def _estimate_financial_metrics(self, symbol: str, current_price: str) -> dict:
    """获取真实财务指标"""
    
    # 🔴 问题代码：股价解析失败时使用默认值 10.0
    try:
        price_value = float(current_price.replace('¥', '').replace(',', ''))
    except:
        price_value = 10.0  # ⚠️ 默认值！这就是问题所在！
```

**修改后**：
```python
def _estimate_financial_metrics(self, symbol: str, current_price: str) -> dict:
    """获取真实财务指标"""
    
    # 验证股价是否有效
    try:
        price_value = float(current_price.replace('¥', '').replace(',', ''))
        if price_value <= 0 or price_value > 10000:  # 基本验证
            logger.warning(f"⚠️ 股价值异常: {price_value}，尝试从BaoStock获取")
            price_value = None
    except (ValueError, AttributeError):
        logger.warning(f"⚠️ 股价解析失败: {current_price}，尝试从BaoStock获取")
        price_value = None
    
    # 如果股价无效，尝试从 BaoStock 获取实时 PE/PB
    if price_value is None:
        logger.info(f"🔄 [PE/PB计算] 股价无效，尝试从BaoStock获取实时数据: {symbol}")
        realtime_pe_pb = self._get_baostock_pe_pb(symbol)
        if realtime_pe_pb:
            logger.info(f"✅ [BaoStock] 获取成功: PE={realtime_pe_pb['pe']}, PB={realtime_pe_pb['pb']}")
            # 返回直接使用 BaoStock 数据的结果
            return realtime_pe_pb
        else:
            # 如果BaoStock也失败，抛出异常而不是使用错误数据
            error_msg = f"无法获取股票 {symbol} 的有效股价和PE/PB数据"
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)
```

#### 修复点 2：新增 `_get_baostock_pe_pb` 方法

**文件**：`tradingagents/dataflows/optimized_china_data.py`  
**位置**：在 `_estimate_financial_metrics` 方法之后添加

**新增代码**：
```python
def _get_baostock_pe_pb(self, symbol: str) -> Optional[dict]:
    """
    从BaoStock获取实时PE/PB数据
    
    Args:
        symbol: 6位股票代码（如：600930）
    
    Returns:
        dict: 包含 PE、PB、PE_TTM 等指标的字典，失败返回 None
    """
    try:
        import baostock as bs
        
        # 标准化股票代码
        code = symbol.zfill(6)
        if code.startswith(('6',)):
            bs_code = f"sh.{code}"
        else:
            bs_code = f"sz.{code}"
        
        # 登录BaoStock
        bs.login()
        
        try:
            # 获取日线数据（包含PE/PB）
            rs = bs.query_history_k_data_plus(
                bs_code,
                'date,close,peTTM,pbMRQ',
                start_date=(datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d'),
                end_date=datetime.now().strftime('%Y-%m-%d'),
                frequency='d',
                adjustflag='3'
            )
            
            data_list = []
            while rs.error_code == '0' and rs.next():
                data_list.append(rs.get_row_data())
            
            if not data_list:
                logger.warning(f"⚠️ [BaoStock] 无数据返回: {symbol}")
                return None
            
            # 获取最新数据
            latest = data_list[-1]
            pe_ttm = latest[2] if latest[2] != 'None' else None
            pb = latest[3] if latest[3] != 'None' else None
            price = float(latest[1]) if latest[1] else None
            
            if not pe_ttm or not pb:
                logger.warning(f"⚠️ [BaoStock] PE/PB为空: {symbol}")
                return None
            
            logger.info(f"✅ [BaoStock] 获取成功: {symbol} PE={pe_ttm}, PB={pb}")
            
            return {
                'pe': f"{float(pe_ttm):.1f}倍",
                'pe_ttm': f"{float(pe_ttm):.1f}倍",
                'pb': f"{float(pb):.2f}倍",
                'price': f"¥{price:.2f}" if price else None,
                'data_source': 'BaoStock',
                'fundamental_score': self._calculate_fundamental_score(float(pe_ttm), float(pb)),
            }
            
        finally:
            bs.logout()
            
    except ImportError:
        logger.warning("⚠️ BaoStock模块未安装")
        return None
    except Exception as e:
        logger.error(f"❌ [BaoStock] 获取失败: {symbol}, 错误: {e}")
        return None
```

#### 修复点 3：修改 `_parse_akshare_financial_data` 方法

**文件**：`tradingagents/dataflows/optimized_china_data.py`  
**位置**：第 1551 行附近

**修改前**：
```python
if stock_code:
    logger.info(f"📊 [AKShare-PE计算-第1层] 尝试使用实时PE/PB计算: {stock_code}")
    
    from tradingagents.config.database_manager import get_database_manager
    from tradingagents.dataflows.realtime_metrics import get_pe_pb_with_fallback
    
    db_manager = get_database_manager()
    if db_manager.is_mongodb_available():
        client = db_manager.get_mongodb_client()
        realtime_metrics = get_pe_pb_with_fallback(stock_code, client)
```

**修改后**：
```python
if stock_code:
    logger.info(f"📊 [AKShare-PE计算-第1层] 尝试使用实时PE/PB计算: {stock_code}")
    
    realtime_metrics = None
    
    # 方案1：尝试从MongoDB获取
    from tradingagents.config.database_manager import get_database_manager
    from tradingagents.dataflows.realtime_metrics import get_pe_pb_with_fallback
    
    db_manager = get_database_manager()
    if db_manager.is_mongodb_available():
        try:
            client = db_manager.get_mongodb_client()
            realtime_metrics = get_pe_pb_with_fallback(stock_code, client)
        except Exception as e:
            logger.warning(f"⚠️ [MongoDB] PE/PB获取失败: {e}")
    
    # 方案2：如果MongoDB失败，尝试从BaoStock获取
    if not realtime_metrics:
        logger.info(f"🔄 [PE/PB计算] MongoDB失败，尝试从BaoStock获取: {stock_code}")
        baostock_metrics = self._get_baostock_pe_pb(stock_code)
        if baostock_metrics:
            # 转换为统一格式
            realtime_metrics = {
                'pe': float(baostock_metrics['pe'].replace('倍', '')),
                'pe_ttm': float(baostock_metrics['pe_ttm'].replace('倍', '')),
                'pb': float(baostock_metrics['pb'].replace('倍', '')),
                'source': 'baostock',
                'is_realtime': True,
            }
            logger.info(f"✅ [BaoStock] 降级成功: {stock_code}")
```

---

## 4. 数据流图

### 4.1 当前错误的数据流

```
基本面分析师
    ↓
get_stock_fundamentals_unified
    ↓
get_china_stock_data_unified (股价="N/A")
    ↓
_estimate_financial_metrics
    ↓
price_value = 10.0  ❌ 默认值！
    ↓
_parse_akshare_financial_data
    ↓
PE = 10.0 / 0.05 = 200倍  ❌ 错误计算！
```

### 4.2 修复后的数据流

```
基本面分析师
    ↓
get_stock_fundamentals_unified
    ↓
get_china_stock_data_unified (股价无效)
    ↓
_estimate_financial_metrics
    ↓
_get_baostock_pe_pb  ✅ 直接获取真实PE/PB
    ↓
PE = 37.27, PB = 2.16  ✅ 正确数据！
    ↓
返回正确的基本面分析报告
```

---

## 5. 测试计划

### 5.1 单元测试

#### 测试用例 1：股价无效时的PE/PB获取

```python
def test_baostock_pe_pb_fallback():
    """测试股价无效时能否正确从BaoStock获取PE/PB"""
    
    analyzer = OptimizedChinaDataProvider()
    
    # 测试600930
    result = analyzer._get_baostock_pe_pb('600930')
    
    assert result is not None, "应该返回结果"
    assert 'pe' in result, "应该包含PE"
    assert 'pb' in result, "应该包含PB"
    assert '37' in result['pe'] or '38' in result['pe'], f"PE应该在37-38之间，实际: {result['pe']}"
    assert '2.' in result['pb'], f"PB应该在2.x，实际: {result['pb']}"
```

#### 测试用例 2：股价异常值检测

```python
def test_invalid_price_detection():
    """测试股价异常值检测"""
    
    analyzer = OptimizedChinaDataProvider()
    
    # 测试边界值
    test_cases = [
        ("N/A", None),      # 无效值
        ("-5.0", None),     # 负数
        ("0", None),        # 零
        ("100000", None),   # 异常大值
        ("5.72", 5.72),     # 正常值
        ("¥5.72", 5.72),   # 带货币符号
    ]
    
    for input_val, expected in test_cases:
        try:
            price = float(input_val.replace('¥', '').replace(',', ''))
            if price <= 0 or price > 10000:
                result = None
            else:
                result = price
        except:
            result = None
        
        assert result == expected, f"输入: {input_val}, 期望: {expected}, 实际: {result}"
```

### 5.2 集成测试

#### 测试用例 3：完整的基本面分析流程

```python
def test_fundamentals_analysis_integration():
    """测试完整的基本面分析流程"""
    
    # 使用CLI测试600930
    result = subprocess.run([
        'python3', '-m', 'cli.main', 'analyze'
    ], input='600930\n2026-06-10\n',
       capture_output=True, text=True)
    
    # 读取生成的报告
    report_path = 'results/600930/2026-06-10/reports/fundamentals_report.md'
    with open(report_path, 'r') as f:
        report = f.read()
    
    # 验证PE值是否在合理范围内
    assert '37' in report or '38' in report, "PE应该在37-38倍之间"
    assert '200' not in report or '200倍' not in report, "不应该出现200倍PE"
    
    # 验证PB值
    assert '2.' in report, "PB应该在2.x倍"
```

### 5.3 回归测试

测试以下股票，确保修复不影响正常流程：
- 600519（茅台）
- 000001（平安银行）
- 601318（平安保险）

---

## 6. 回滚方案

### 6.1 回滚触发条件

如果出现以下情况，立即回滚：
1. BaoStock 数据源不可用率 > 50%
2. PE/PB 计算错误率 > 10%
3. 系统出现未捕获异常

### 6.2 回滚步骤

```bash
# 1. 切换到回滚分支
git checkout hotfix/pe-pb-bugfix
git log --oneline -1  # 确认当前版本

# 2. 回滚代码修改
git revert HEAD

# 3. 部署旧版本
pip install -e .

# 4. 监控24小时
# 如果问题解决，合并回滚提交
# 如果问题未解决，分析原因重新修复
```

### 6.3 备用方案

如果BaoStock数据源不可用，可以临时使用：
- **东方财富**（需要API Key）
- **新浪财经**（免费但不稳定）
- **腾讯证券**（免费但需要爬虫）

---

## 7. 部署计划

### 7.1 部署步骤

1. **代码审查**（1天）
   - 审查修复代码
   - 检查测试覆盖
   - 确认无副作用

2. **测试环境验证**（1天）
   - 运行所有单元测试
   - 运行集成测试
   - 手动测试3-5支股票

3. **预发布**（1天）
   - 部署到预发布环境
   - 监控24小时
   - 收集日志和指标

4. **正式发布**（1天）
   - 分批次发布（10% → 50% → 100%）
   - 实时监控错误率
   - 准备回滚

### 7.2 监控指标

| 指标 | 目标值 | 告警阈值 |
|:---|:---:|:---:|
| PE/PB 计算错误率 | 0% | > 1% |
| BaoStock 可用率 | > 95% | < 90% |
| 基本面分析成功率 | > 98% | < 95% |
| 响应时间 | < 5s | > 10s |

---

## 8. 附录

### 8.1 相关文件清单

| 文件路径 | 修改类型 | 说明 |
|---------|:---:|------|
| `tradingagents/dataflows/optimized_china_data.py` | 修改 | 核心修复文件 |
| `tradingagents/agents/utils/agent_utils.py` | 无需修改 | 调用方，无需改动 |
| `tradingagents/agents/analysts/fundamentals_analyst.py` | 无需修改 | 调用方，无需改动 |

### 8.2 日志关键字

修复后，日志中应出现以下关键字：
```
✅ [BaoStock] 获取成功: 600930 PE=37.27, PB=2.16
🔄 [PE/PB计算] MongoDB失败，尝试从BaoStock获取
⚠️ 股价解析失败: N/A，尝试从BaoStock获取
```

不应再出现：
```
❌ PE(单期): 股价10.0 / EPS0.0500 = 200.0倍  （这是错误值）
⚠️ 股价值异常: 10.0，尝试从BaoStock获取  （需要修复检测逻辑）
```

### 8.3 参考资料

- BaoStock API 文档：https://baostock.com/baostock/index.php
- AKShare 文档：https://akshare.akfamily.xyz/
- 原始问题定位：logs/tradingagents.log 2026-06-10 20:22:47

---

**文档结束**

*如有疑问，请联系：数据分析团队*
