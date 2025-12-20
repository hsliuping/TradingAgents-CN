
import sys
import os

# 添加项目根目录到python path
sys.path.append(os.getcwd())

from tradingagents.tools.index_tools import fetch_sector_news

def test_tool():
    print("Testing fetch_sector_news tool...")
    try:
        # 测试板块
        sectors = ["半导体", "A股", "大盘"]
        for s in sectors:
            print(f"\n--- Testing sector: {s} ---")
            result = fetch_sector_news.invoke({"sector_name": s, "lookback_days": 3})
            print(result[:300] + "..." if len(result) > 300 else result)
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_tool()
