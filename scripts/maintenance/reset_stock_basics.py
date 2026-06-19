#!/usr/bin/env python3
"""
重置股票基础信息数据
删除所有现有数据，重新同步
"""
import os
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def build_mongo_uri():
    host = os.getenv("MONGODB_HOST", "localhost")
    port = int(os.getenv("MONGODB_PORT", "27017"))
    db = os.getenv("MONGODB_DATABASE", "tradingagents")
    user = os.getenv("MONGODB_USERNAME", "")
    pwd = os.getenv("MONGODB_PASSWORD", "")
    auth_src = os.getenv("MONGODB_AUTH_SOURCE", "admin")
    if user and pwd:
        return f"mongodb://{user}:{pwd}@{host}:{port}/{db}?authSource={auth_src}"
    return f"mongodb://{host}:{port}/{db}"

def reset_stock_basics():
    """重置股票基础信息数据"""
    print("🔄 重置股票基础信息数据")
    print("=" * 60)
    
    try:
        # 1. 连接 MongoDB 并清空数据
        print("1️⃣ 清空现有数据...")
        uri = build_mongo_uri()
        client = MongoClient(uri)
        dbname = os.getenv("MONGODB_DATABASE", "tradingagents")
        db = client[dbname]
        collection = db.stock_basic_info
        
        # 统计删除前的数据
        count_before = collection.count_documents({})
        print(f"   删除前记录数: {count_before}")
        
        # 删除所有记录
        if count_before > 0:
            result = collection.delete_many({})
            print(f"   ✅ 成功删除 {result.deleted_count} 条记录")
        else:
            print("   ℹ️  数据库已为空")
        
        # 关闭数据库连接
        client.close()
        
        # 2. 清空相关缓存
        print("\n2️⃣ 清空缓存...")
        try:
            response = requests.delete('http://localhost:8100/api/cache/clear', timeout=30)
            if response.ok:
                print("   ✅ 缓存已清空")
            else:
                print(f"   ⚠️ 清空缓存失败: {response.text}")
        except Exception as e:
            print(f"   ⚠️ 清空缓存失败: {e}")
        
        # 3. 重新同步数据
        print("\n3️⃣ 重新同步股票基础信息...")
        try:
            response = requests.post('http://localhost:8100/api/sync/stock_basics/run', timeout=300)
            if response.ok:
                data = response.json()['data']
                print("   ✅ 同步完成:")
                print(f"      总数: {data['total']}")
                print(f"      更新: {data['updated']}")
                print(f"      错误: {data['errors']}")
            else:
                print(f"   ❌ 同步失败: {response.text}")
                return False
        except Exception as e:
            print(f"   ❌ 同步失败: {e}")
            return False
        
        # 4. 验证结果
        print("\n4️⃣ 验证同步结果...")
        client = MongoClient(uri)
        db = client[dbname]
        collection = db.stock_basic_info
        
        total_count = collection.count_documents({})
        extended_count = collection.count_documents({
            "$or": [
                {"pe": {"$exists": True, "$ne": None}},
                {"pb": {"$exists": True, "$ne": None}},
                {"circ_mv": {"$exists": True, "$ne": None}}
            ]
        })
        
        print(f"   📊 总记录数: {total_count}")
        print(f"   📊 有扩展字段的记录: {extended_count} ({extended_count/total_count*100:.1f}%)")
        
        # 检查几个示例股票
        print("\n   📋 示例股票检查:")
        sample_stocks = list(collection.find({"name": {"$in": ["平安银行", "万科A", "中国平安"]}}).limit(3))
        for stock in sample_stocks:
            code = stock.get('code', 'N/A')
            name = stock.get('name', 'N/A')
            pe = stock.get('pe', '无')
            pb = stock.get('pb', '无')
            circ_mv = stock.get('circ_mv', '无')
            print(f"      {code} - {name}: PE={pe}, PB={pb}, 流通市值={circ_mv}")
        
        client.close()
        
        print("\n✅ 重置完成!")
        return True
        
    except Exception as e:
        print(f"❌ 重置失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = reset_stock_basics()
    exit(0 if success else 1)
