#!/usr/bin/env python3
"""
AKShare 优化点验证测试脚本

验证内容：
1. stock_zh_a_spot_em 批量接口返回的字段（确认是否包含 PE/PB/总市值/换手率）
2. stock_individual_info_em 单只查询的字段对比
3. find_latest_trade_date 中的 asyncio.run bug 是否真的会触发
4. stock_zh_a_hist 历史数据接口的返回结构

运行方式:
    cd c:\TradingAgentsCN
    python tests/test_akshare_optimization_verify.py
"""
import asyncio
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def print_header(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_subheader(title: str):
    print(f"\n--- {title} ---")


def test_1_batch_vs_single_basic_data():
    """测试1: 对比批量接口 vs 单只接口的估值数据字段"""
    print_header("测试1: stock_zh_a_spot_em 批量接口 vs stock_individual_info_em 单只接口")
    
    try:
        import akshare as ak
    except ImportError:
        print("❌ akshare 未安装，跳过测试")
        return
    
    test_codes = ["000002", "600519", "000001"]  # 万科、茅台、平安银行
    
    # ========== 批量接口 ==========
    print_subheader("1.1 调用 stock_zh_a_spot_em（全市场快照，1次调用）")
    start_time = time.time()
    try:
        df_batch = ak.stock_zh_a_spot_em()
        batch_elapsed = time.time() - start_time
        print(f"✅ 耗时: {batch_elapsed:.2f}s, 返回 {len(df_batch)} 只股票")
        print(f"📋 列名: {df_batch.columns.tolist()}")
        
        # 检查是否包含关键字段
        required_fields = {
            "代码": ["代码", "symbol", "股票代码"],
            "名称": ["名称", "name"],
            "最新价": ["最新价", "现价", "最新"],
            "PE": ["市盈率-动态", "市盈率", "pe"],
            "PB": ["市净率", "pb"],
            "总市值": ["总市值", "总市值(元)"],
            "换手率": ["换手率", "turnover_rate"],
        }
        
        print_subheader("1.2 关键字段匹配")
        matched_fields = {}
        for field_name, possible_cols in required_fields.items():
            matched = [c for c in possible_cols if c in df_batch.columns]
            if matched:
                print(f"  ✅ {field_name}: 找到列 '{matched[0]}'")
                matched_fields[field_name] = matched[0]
            else:
                print(f"  ❌ {field_name}: 未找到（期望列: {possible_cols}）")
        
        # 打印测试股票的数据
        print_subheader("1.3 测试股票的批量接口数据")
        code_col = matched_fields.get("代码", "代码")
        for test_code in test_codes:
            row = df_batch[df_batch[code_col].astype(str).str.contains(test_code, na=False)]
            if not row.empty:
                print(f"\n  📊 {test_code}:")
                for field_name, col_name in matched_fields.items():
                    val = row.iloc[0].get(col_name)
                    print(f"     {field_name}: {val}")
            else:
                print(f"  ⚠️ {test_code} 未找到")
        
    except Exception as e:
        print(f"❌ stock_zh_a_spot_em 调用失败: {e}")
        return
    
    # ========== 单只接口 ==========
    print_subheader("1.4 调用 stock_individual_info_em（单只查询，3次调用）")
    single_total_time = 0
    for test_code in test_codes:
        start_time = time.time()
        try:
            info_df = ak.stock_individual_info_em(symbol=test_code)
            elapsed = time.time() - start_time
            single_total_time += elapsed
            print(f"\n  📊 {test_code} (耗时 {elapsed:.2f}s):")
            if info_df is not None and not info_df.empty:
                info_dict = dict(zip(info_df['item'], info_df['value']))
                for key in ["股票简称", "最新", "总市值", "流通市值", "行业", "上市时间"]:
                    if key in info_dict:
                        print(f"     {key}: {info_dict[key]}")
        except Exception as e:
            print(f"  ❌ {test_code} 查询失败: {e}")
    
    # ========== 对比总结 ==========
    print_subheader("1.5 对比总结")
    print(f"  批量接口: 1 次调用, 耗时 {batch_elapsed:.2f}s, 获取 {len(df_batch)} 只股票")
    print(f"  单只接口: {len(test_codes)} 次调用, 耗时 {single_total_time:.2f}s, 获取 {len(test_codes)} 只股票")
    print(f"  要获取 5000 只股票:")
    print(f"    批量接口: 1 次调用, ~{batch_elapsed:.0f}s")
    estimated_single = (single_total_time / len(test_codes)) * 5000
    print(f"    单只接口: 5000 次调用, ~{estimated_single:.0f}s ({estimated_single/60:.1f} 分钟)")
    print(f"  结论: 批量接口效率提升约 {estimated_single / batch_elapsed:.0f} 倍")


def test_2_find_latest_trade_date_bug():
    """测试2: 验证 find_latest_trade_date 中的 asyncio.run bug"""
    print_header("测试2: find_latest_trade_date 中的 asyncio.run bug")
    
    print_subheader("2.1 在异步上下文中调用 asyncio.run() 的行为")
    
    async def test_asyncio_run_in_async_context():
        """模拟 akshare_adapter.py L614 的代码"""
        print("  尝试在异步上下文中调用 asyncio.run()...")
        try:
            # 这正是 akshare_adapter.py L614 的写法
            async def dummy_coro():
                return "ok"
            
            result = asyncio.run(dummy_coro())
            print(f"  ✅ asyncio.run() 成功返回: {result}")
            print(f"  ℹ️ 注意: 在某些 Python 版本中这可能不会立即报错，但有潜在风险")
            return True
        except RuntimeError as e:
            if "cannot be called from a running event loop" in str(e):
                print(f"  ❌ 确认 Bug: {e}")
                print(f"  这是预期的错误 —— asyncio.run() 不能在运行的事件循环中调用")
                return False
            else:
                print(f"  ⚠️ 其他 RuntimeError: {e}")
                return None
        except Exception as e:
            print(f"  ⚠️ 其他异常: {type(e).__name__}: {e}")
            return None
    
    result = asyncio.run(test_asyncio_run_in_async_context())
    
    print_subheader("2.2 正确的写法应该是")
    print("  # 错误写法（当前代码）:")
    print("    asyncio.run(cache_service.set_cached_trade_date('akshare', yesterday))")
    print()
    print("  # 正确写法1: 使用 await")
    print("    await cache_service.set_cached_trade_date('akshare', yesterday)")
    print()
    print("  # 正确写法2: 使用同步方法（如果有的话）")
    print("    cache_service.set_cached_trade_date_sync('akshare', yesterday)")
    print()
    print("  # 注意: akshare_adapter.py L542 已经用了同步方法 set_cached_trade_date_sync")
    print("  # 但 L614 的兜底分支却用了 asyncio.run，不一致")


def test_3_historical_data_structure():
    """测试3: 验证 stock_zh_a_hist 历史数据接口的返回结构"""
    print_header("测试3: stock_zh_a_hist 历史数据接口返回结构")
    
    try:
        import akshare as ak
    except ImportError:
        print("❌ akshare 未安装，跳过测试")
        return
    
    test_code = "000002"  # 万科A（有数据）
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
    
    print_subheader(f"3.1 调用 stock_zh_a_hist({test_code}, daily, {start_date}~{end_date})")
    start_time = time.time()
    try:
        df = ak.stock_zh_a_hist(
            symbol=test_code,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq"
        )
        elapsed = time.time() - start_time
        print(f"✅ 耗时: {elapsed:.2f}s, 返回 {len(df)} 条记录")
        print(f"📋 列名: {df.columns.tolist()}")
        if not df.empty:
            print(f"\n前3行数据:")
            print(df.head(3).to_string(index=False))
    except Exception as e:
        print(f"❌ 调用失败: {e}")
    
    print_subheader("3.2 验证: stock_zh_a_hist 是单只查询接口，无法批量")
    print("  结论: 历史数据同步必须逐只查询，串行 + 延迟是正确的防封策略")
    print("  优化方向: 历史同步主力交给 Tushare（付费API无封IP风险），AKShare做兜底")


def test_4_summary():
    """测试4: 优化建议总结"""
    print_header("测试4: 优化建议总结")
    
    print("""
┌─────────────────────────────────────────────────────────────────────┐
│  优化项                          │ 风险   │ 收益   │ 建议          │
├─────────────────────────────────────────────────────────────────────┤
│ 1. get_daily_basic 改用批量接口  │ 低     │ 高     │ ✅ 优先做     │
│    stock_zh_a_spot_em 1次调用    │        │        │              │
│    替代 stock_individual_info_em │        │        │              │
│    5000次调用                    │        │        │              │
├─────────────────────────────────────────────────────────────────────┤
│ 2. 修复 asyncio.run bug          │ 无     │ 中     │ ✅ 顺手修     │
│    L614 改用 await 或同步方法    │        │        │              │
├─────────────────────────────────────────────────────────────────────┤
│ 3. 历史同步保持串行               │ -      │ -      │ ⚠️ 不要并发   │
│    AKShare 单只查询会被封IP      │        │        │              │
│    主力交给 Tushare              │        │        │              │
└─────────────────────────────────────────────────────────────────────┘
""")


def main():
    print_header("AKShare 优化点验证测试")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Python: {sys.version.split()[0]}")
    
    try:
        import akshare as ak
        print(f"AKShare 版本: {ak.__version__}")
    except ImportError:
        print("❌ akshare 未安装")
        return
    except AttributeError:
        print("AKShare 已安装（版本号未知）")
    
    # 执行测试
    test_1_batch_vs_single_basic_data()
    test_2_find_latest_trade_date_bug()
    test_3_historical_data_structure()
    test_4_summary()
    
    print_header("测试完成")


if __name__ == "__main__":
    main()
