"""测试 QMT 数据下载功能"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 60)
print("🔍 QMT 数据下载测试")
print("=" * 60)

# 导入 xtquant
try:
    import xtquant.xtdata as xt
    print("✅ xtquant 导入成功")
except ImportError as e:
    print(f"❌ xtquant 导入失败: {e}")
    sys.exit(1)

# 测试下载单只股票数据
print("\n" + "=" * 60)
print("测试 1: 下载单只股票历史数据")
print("=" * 60)

stock_code = "000001.SZ"  # 平安银行
print(f"股票代码: {stock_code}")
print(f"周期: 日线 (1d)")
print(f"起始时间: 20240101")

try:
    print("\n开始下载...")
    result = xt.download_history_data(
        stock_code=stock_code,
        period="1d",
        start_time="20240101"
    )
    print(f"下载结果: {result}")
    
    # 尝试获取数据
    print("\n尝试获取下载的数据...")
    data = xt.get_market_data(
        field_list=["open", "high", "low", "close", "volume", "amount"],
        stock_list=[stock_code],
        period="1d",
        count=5
    )
    
    if data and stock_code in data:
        df = data[stock_code]
        if not df.empty:
            print(f"✅ 成功获取数据")
            print(f"   数据形状: {df.shape}")
            print(f"\n最近 5 天数据：")
            print(df)
        else:
            print(f"❌ 数据为空")
    else:
        print(f"❌ 未获取到数据")
        
except Exception as e:
    print(f"❌ 失败: {e}")
    import traceback
    traceback.print_exc()

# 测试批量下载
print("\n" + "=" * 60)
print("测试 2: 批量下载股票数据")
print("=" * 60)

stock_list = ["000001.SZ", "600000.SH", "000002.SZ"]
print(f"股票列表: {stock_list}")

try:
    print("\n开始批量下载...")
    for stock in stock_list:
        print(f"  下载 {stock}...")
        result = xt.download_history_data(
            stock_code=stock,
            period="1d",
            start_time="20240101"
        )
        print(f"    结果: {result}")
    
    print("\n尝试获取批量数据...")
    data = xt.get_market_data(
        field_list=["close"],
        stock_list=stock_list,
        period="1d",
        count=1
    )
    
    if data:
        print(f"✅ 成功获取批量数据")
        for stock in stock_list:
            if stock in data:
                df = data[stock]
                if not df.empty:
                    print(f"  {stock}: {df['close'].iloc[-1] if 'close' in df.columns else 'N/A'}")
                else:
                    print(f"  {stock}: 数据为空")
    else:
        print(f"❌ 未获取到批量数据")
        
except Exception as e:
    print(f"❌ 失败: {e}")
    import traceback
    traceback.print_exc()

# 测试获取本地已有数据
print("\n" + "=" * 60)
print("测试 3: 检查本地数据路径")
print("=" * 60)

try:
    # 获取数据路径
    import os
    data_path = "D:\\gjzq\\bin.x64\\..\\userdata_mini\\datadir"
    print(f"数据路径: {data_path}")
    
    if os.path.exists(data_path):
        print(f"✅ 数据路径存在")
        # 列出部分文件
        files = os.listdir(data_path)
        print(f"   文件数量: {len(files)}")
        if files:
            print(f"   前 5 个文件: {files[:5]}")
    else:
        print(f"❌ 数据路径不存在")
        
except Exception as e:
    print(f"❌ 检查失败: {e}")

print("\n" + "=" * 60)
print("✅ 测试完成")
print("=" * 60)
print("\n💡 提示：")
print("1. 如果下载失败，请检查 MiniQMT 是否已登录")
print("2. 某些券商版本可能需要在 MiniQMT 界面手动下载数据")
print("3. 可以在 MiniQMT 中查看数据管理功能")

