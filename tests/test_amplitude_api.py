"""测试振幅 API"""
import requests
import json

# API 配置
BASE_URL = "http://localhost:8100"
USERNAME = "admin"
PASSWORD = "admin123"

def login():
    """登录获取 token"""
    url = f"{BASE_URL}/api/auth/login"
    data = {
        "username": USERNAME,
        "password": PASSWORD
    }
    response = requests.post(url, json=data)
    if response.status_code == 200:
        result = response.json()
        return result.get("data", {}).get("access_token")
    else:
        print(f"❌ 登录失败: {response.status_code}")
        print(response.text)
        return None

def get_quote(token, code):
    """获取股票行情"""
    url = f"{BASE_URL}/api/stocks/{code}/quote"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"❌ 获取行情失败: {response.status_code}")
        print(response.text)
        return None

def main():
    print("=" * 60)
    print("🧪 测试振幅 API")
    print("=" * 60)
    
    # 1. 登录
    print("\n1️⃣ 登录...")
    token = login()
    if not token:
        return
    print(f"✅ 登录成功")
    
    # 2. 获取 300750 行情
    print("\n2️⃣ 获取 300750 行情...")
    result = get_quote(token, "300750")
    if not result:
        return
    
    print(f"✅ 获取成功")
    print(f"\n📊 行情数据:")
    data = result.get("data", {})
    
    # 打印关键字段
    fields = [
        ("代码", "code"),
        ("名称", "name"),
        ("价格", "price"),
        ("涨跌幅", "change_percent"),
        ("开盘", "open"),
        ("最高", "high"),
        ("最低", "low"),
        ("昨收", "prev_close"),
        ("成交量", "volume"),
        ("成交额", "amount"),
        ("换手率", "turnover_rate"),
        ("振幅", "amplitude"),  # 🔥 新增
        ("换手率日期", "turnover_rate_date"),
        ("振幅日期", "amplitude_date"),  # 🔥 新增
    ]
    
    for label, key in fields:
        value = data.get(key)
        if value is not None:
            if key in ["change_percent", "turnover_rate", "amplitude"]:
                print(f"  {label}: {value}%")
            elif key == "volume":
                print(f"  {label}: {value:,.0f}")
            elif key == "amount":
                print(f"  {label}: {value:,.2f}")
            else:
                print(f"  {label}: {value}")
        else:
            print(f"  {label}: -")
    
    # 验证振幅计算
    print("\n3️⃣ 验证振幅计算...")
    high = data.get("high")
    low = data.get("low")
    prev_close = data.get("prev_close")
    amplitude = data.get("amplitude")
    
    if high and low and prev_close:
        expected_amplitude = round((high - low) / prev_close * 100, 2)
        print(f"  高: {high}")
        print(f"  低: {low}")
        print(f"  昨收: {prev_close}")
        print(f"  期望振幅: {expected_amplitude}%")
        print(f"  实际振幅: {amplitude}%")
        
        if abs(expected_amplitude - amplitude) < 0.01:
            print(f"  ✅ 振幅计算正确！")
        else:
            print(f"  ❌ 振幅计算错误！")
    else:
        print(f"  ⚠️ 数据不完整，无法验证")

if __name__ == "__main__":
    main()

