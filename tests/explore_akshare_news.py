
import akshare as ak
import inspect

def explore_ak_news():
    print("Exploring akshare news interfaces...")
    
    # Get all functions in akshare
    all_functions = inspect.getmembers(ak, inspect.isfunction)
    
    # Filter for functions that might be related to news
    news_funcs = [name for name, func in all_functions if 'news' in name.lower() or 'info' in name.lower()]
    
    print(f"Found {len(news_funcs)} potential news functions. Listing first 50:")
    for name in news_funcs[:50]:
        print(f"- {name}")

    print("\n--- Testing Specific Candidates ---")
    
    # Candidate 1: Sina Finance (Global/A-share)
    # stock_news_sina is a likely candidate if it exists
    if hasattr(ak, 'stock_news_sina'):
        print("\nTesting stock_news_sina...")
        try:
            # Need to guess parameters, usually no params or symbol
            # Trying with no params first or checking docs pattern
            # Often getting a specific roll news
            pass
        except Exception as e:
            print(f"Error: {e}")

    # Candidate 2: 10jqka (Tonghuashun)
    # stock_news_10jqka
    
    # Candidate 3: Gelonghui
    # stock_news_gelonghui
    
    # Let's try to run a few likely ones if they exist
    candidates = [
        ('stock_info_global_cls', {}), # Cailianshe global info
        ('stock_telegraph_cls', {}),   # Cailianshe telegraph - known to fail before, but worth re-checking if name changed
        ('news_cctv', {}),             # CCTV - already used
        ('news_economic_baidu', {}),   # Baidu Economic News
        ('stock_news_em', {'symbol': 'A股'}), # East Money - already used
    ]

    for func_name, kwargs in candidates:
        if hasattr(ak, func_name):
            print(f"\nTesting {func_name}...")
            try:
                func = getattr(ak, func_name)
                df = func(**kwargs)
                if not df.empty:
                    print(f"Success! Shape: {df.shape}")
                    print(df.head(2))
                else:
                    print("Empty result.")
            except Exception as e:
                print(f"Error running {func_name}: {e}")
        else:
            print(f"Function {func_name} not found in akshare.")

if __name__ == "__main__":
    explore_ak_news()
