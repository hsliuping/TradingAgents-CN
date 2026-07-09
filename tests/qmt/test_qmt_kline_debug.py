"""调试 QMT K 线数据获取"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from datetime import datetime, timedelta

print("=" * 60)
print("🔍 QMT K 线数据获取调试")
print("=" * 60)

# 导入 xtquant
try:
    import xtquant.xtdata as xt
    print("✅ xtquant 导入成功")
except ImportError as e:
    print(f"❌ xtquant 导入失败: {e}")
    sys.exit(1)

# 测试连接
print("\n检查 xtdata 连接...")
try:
    ticks = xt.get_full_tick([])
    print(f"✅ xtdata 连接成功")
except Exception as e:
    print(f"❌ xtdata 连接失败: {e}")
    sys.exit(1)

# 测试获取 K 线数据
print("\n" + "=" * 60)
print("测试 1: 使用 count 参数获取最近 5 天数据")
print("=" * 60)

stock_code = "000001.SZ"  # 平安银行
print(f"股票代码: {stock_code}")

try:
    # 方法 1: 使用 count 参数（推荐）
    data1 = xt.get_market_data(
        field_list=["open", "high", "low", "close", "volume", "amount"],
        stock_list=[stock_code],
        period="1d",
        count=5  # 获取最近 5 条数据
    )
    
    if data1 and stock_code in data1:
        df = data1[stock_code]
        print(f"✅ 成功获取数据（使用 count）")
        print(f"   数据类型: {type(df)}")
        print(f"   数据形状: {df.shape if hasattr(df, 'shape') else 'N/A'}")
        print(f"\n数据内容：")
        print(df)
    else:
        print(f"❌ 未获取到数据")
        print(f"   返回值: {data1}")
        
except Exception as e:
    print(f"❌ 获取失败: {e}")
    import traceback
    traceback.print_exc()

# 测试方法 2: 使用时间范围
print("\n" + "=" * 60)
print("测试 2: 使用时间范围获取数据")
print("=" * 60)

try:
    end = datetime.now()
    start = end - timedelta(days=10)
    start_str = start.strftime("%Y%m%d")
    end_str = end.strftime("%Y%m%d")
    
    print(f"时间范围: {start_str} ~ {end_str}")
    
    data2 = xt.get_market_data(
        field_list=["open", "high", "low", "close", "volume", "amount"],
        stock_list=[stock_code],
        period="1d",
        start_time=start_str,
        end_time=end_str
    )
    
    if data2 and stock_code in data2:
        df = data2[stock_code]
        print(f"✅ 成功获取数据（使用时间范围）")
        print(f"   数据类型: {type(df)}")
        print(f"   数据形状: {df.shape if hasattr(df, 'shape') else 'N/A'}")
        print(f"\n数据内容：")
        print(df)
    else:
        print(f"❌ 未获取到数据")
        print(f"   返回值: {data2}")
        
except Exception as e:
    print(f"❌ 获取失败: {e}")
    import traceback
    traceback.print_exc()

# 测试方法 3: 获取历史数据（使用 download_history_data）
print("\n" + "=" * 60)
print("测试 3: 下载历史数据")
print("=" * 60)

try:
    print(f"尝试下载 {stock_code} 的历史数据...")
    result = xt.download_history_data(
        stock_code=stock_code,
        period="1d",
        start_time="20240101"
    )
    print(f"下载结果: {result}")
    
    # 再次尝试获取
    data3 = xt.get_market_data(
        field_list=["open", "high", "low", "close", "volume", "amount"],
        stock_list=[stock_code],
        period="1d",
        count=5
    )
    
    if data3 and stock_code in data3:
        df = data3[stock_code]
        print(f"✅ 下载后成功获取数据")
        print(f"\n数据内容：")
        print(df)
    else:
        print(f"❌ 下载后仍未获取到数据")
        
except Exception as e:
    print(f"❌ 下载失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("✅ 调试完成")
print("=" * 60)

