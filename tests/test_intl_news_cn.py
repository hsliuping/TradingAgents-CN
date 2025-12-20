
import sys
import os

# 添加项目根目录到python path
sys.path.append(os.getcwd())

from tradingagents.tools.international_news_tools import fetch_cn_international_news

def test_cn_intl_news():
    print("Testing fetch_cn_international_news...")
    try:
        # 测试不带关键词
        result = fetch_cn_international_news.invoke({"keywords": "", "lookback_days": 7})
        print("\n--- Result (No Keywords) ---")
        print(result[:500] + "..." if len(result) > 500 else result)
        
        # 测试带关键词 (假设最近有关于"科技"或"美联储"的新闻，这里用一个比较通用的词)
        # 注意：AKShare返回的新闻是中文的
        keyword = "科技" 
        result_kw = fetch_cn_international_news.invoke({"keywords": keyword, "lookback_days": 7})
        print(f"\n--- Result (Keyword: {keyword}) ---")
        print(result_kw[:500] + "..." if len(result_kw) > 500 else result_kw)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_cn_intl_news()
