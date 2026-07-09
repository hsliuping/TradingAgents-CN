"""简单的 QMT 测试脚本"""
import sys
print("Python 版本:", sys.version)
print("Python 路径:", sys.executable)

print("\n检查 xtquant 库...")
try:
    import xtquant
    print("✅ xtquant 已安装")
    print("   版本:", getattr(xtquant, '__version__', '未知'))
except ImportError as e:
    print("❌ xtquant 未安装")
    print("   错误:", e)
    print("\n安装方法：")
    print("   pip install xtquant")
    sys.exit(1)

print("\n检查 QMT 适配器...")
try:
    from app.services.data_sources.qmt_adapter import QMTAdapter
    print("✅ QMT 适配器模块加载成功")
    
    adapter = QMTAdapter()
    print("\n检查 MiniQMT 连接...")
    is_available = adapter.is_available()
    
    if is_available:
        print("✅ QMT 可用")
        print("   - xtquant 库已安装")
        print("   - MiniQMT 客户端已连接")
        
        print("\n测试获取股票列表...")
        df = adapter.get_stock_list()
        if df is not None and not df.empty:
            print(f"✅ 成功获取 {len(df)} 只股票")
            print("\n前 3 只股票：")
            print(df.head(3))
        else:
            print("❌ 未获取到股票列表")
    else:
        print("❌ QMT 不可用")
        print("\n请检查：")
        print("1. MiniQMT 客户端是否已启动")
        print("2. MiniQMT 是否已登录券商账户")
        print("3. 是否在 Windows 系统上运行")
        
except Exception as e:
    print(f"❌ 错误: {e}")
    import traceback
    traceback.print_exc()

