
import akshare as ak
import inspect

def list_all_news_funcs():
    all_functions = inspect.getmembers(ak, inspect.isfunction)
    news_funcs = [name for name, func in all_functions if 'news' in name.lower() or 'info' in name.lower()]
    
    print(f"Found {len(news_funcs)} functions. Listing all:")
    for name in news_funcs:
        print(f"- {name}")

if __name__ == "__main__":
    list_all_news_funcs()
