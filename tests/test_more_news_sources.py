
import akshare as ak
import pandas as pd

def test_candidates():
    candidates = [
        'stock_news_main_cx',
        'stock_info_global_sina',
        'stock_info_global_ths',
        'stock_info_global_futu',
        'stock_info_global_em'
    ]

    for name in candidates:
        print(f"\n--- Testing {name} ---")
        if hasattr(ak, name):
            try:
                func = getattr(ak, name)
                # Some might require parameters, but let's try without first
                df = func()
                if not df.empty:
                    print(f"Success! Shape: {df.shape}")
                    print(df.head(2))
                else:
                    print("Empty result.")
            except Exception as e:
                print(f"Error: {e}")
        else:
            print("Function not found.")

if __name__ == "__main__":
    test_candidates()
