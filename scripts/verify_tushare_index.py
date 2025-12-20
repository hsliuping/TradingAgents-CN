
import tushare as ts
import os
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("TUSHARE_TOKEN")
if not token:
    print("Error: Tushare token not found in .env")
    exit(1)

print(f"Using Tushare token: {token[:6]}...")
ts.set_token(token)
pro = ts.pro_api()

try:
    # Search for index containing "机器人"
    df = pro.index_basic(name='机器人')
    if df.empty:
        print("No index found with name containing '机器人'")
    else:
        print("Found indices:")
        print(df[['ts_code', 'name', 'market', 'publisher']].to_string())
        
    # Also check specifically for H30590 if it exists in other calls or if it is a valid code
    # H30590 is often CSI code. Tushare uses different suffixes (.SH, .SZ, .CSI?)
    # Usually CSI indices on Tushare are like '000xxx.SH' or 'Hxxxxx.CSI' is rare?
    # Let's search by code if possible or just list.
    
except Exception as e:
    print(f"Error querying Tushare: {e}")
