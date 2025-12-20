
import akshare as ak
import pandas as pd

def test_sector_news():
    print("Testing AKShare sector news capabilities...")
    
    sectors = ["半导体", "医药", "新能源"]
    
    for sector in sectors:
        print(f"\n--- Testing sector: {sector} ---")
        try:
            # 尝试使用 stock_news_em 获取板块新闻
            # 根据经验，东方财富的这个接口 symbol 参数可能支持板块名称
            news_df = ak.stock_news_em(symbol=sector)
            if not news_df.empty:
                print(f"Success! Found {len(news_df)} items.")
                print(news_df[['新闻标题', '发布时间']].head(3))
            else:
                print("No data returned.")
        except Exception as e:
            print(f"Error fetching news for {sector}: {e}")

def test_other_sources():
    print("\n--- Testing other news sources ---")
    try:
        # 尝试获取财联社电报 (注意：之前的 stock_telegraph_cls 失败了，尝试其他类似的)
        # ak.stock_info_global_cls() 也是一个可能的接口
        print("Testing stock_info_global_cls...")
        if hasattr(ak, 'stock_info_global_cls'):
            df = ak.stock_info_global_cls()
            if not df.empty:
                print(f"Success! Found {len(df)} items.")
                print(df.head(3))
        else:
            print("stock_info_global_cls not found in akshare.")
            
    except Exception as e:
        print(f"Error with stock_info_global_cls: {e}")

    try:
        # 尝试获取新浪财经新闻
        print("Testing stock_news_sina...")
        # 注意：akshare接口变动频繁，需要尝试
        # 假设 ak.stock_news_sina(symbol='go_A_share') 或类似
        # 先查一下文档或尝试常用参数
        pass 
    except Exception:
        pass

if __name__ == "__main__":
    test_sector_news()
    # test_other_sources() # 暂时先测板块，以免输出太多混乱
