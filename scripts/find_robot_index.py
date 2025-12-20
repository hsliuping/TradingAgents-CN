import tushare as ts
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get token from env
token = os.getenv("TUSHARE_TOKEN")
if not token:
    print("Error: TUSHARE_TOKEN not found in .env")
    exit(1)

print(f"Using token: {token[:10]}...")

ts.set_token(token)
pro = ts.pro_api()

try:
    # Search for indices with '机器人' in name
    # We can use index_basic
    df = pro.index_basic(market='SW') # Shenwan
    robot_indices = df[df['name'].str.contains('机器人', na=False)]
    if not robot_indices.empty:
        print("Found SW indices:")
        print(robot_indices[['ts_code', 'name', 'market']])
    
    df = pro.index_basic(market='CSI') # CSI
    robot_indices = df[df['name'].str.contains('机器人', na=False)]
    if not robot_indices.empty:
        print("Found CSI indices:")
        print(robot_indices[['ts_code', 'name', 'market']])

    df = pro.index_basic(market='SZSE') # Shenzhen
    robot_indices = df[df['name'].str.contains('机器人', na=False)]
    if not robot_indices.empty:
        print("Found SZSE indices:")
        print(robot_indices[['ts_code', 'name', 'market']])
        
except Exception as e:
    print(f"Error: {e}")
