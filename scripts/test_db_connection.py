"""测试数据库连接并查看 prompt_templates 集合结构"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pymongo import MongoClient
from dotenv import load_dotenv
import os
import json

load_dotenv()

# 连接数据库
mongo_host = os.getenv("MONGO_HOST", "localhost")
mongo_port = int(os.getenv("MONGO_PORT", "27017"))
mongo_db = os.getenv("MONGO_DB", "tradingagents")

print(f"连接到: mongodb://{mongo_host}:{mongo_port}/{mongo_db}")

client = MongoClient(f"mongodb://{mongo_host}:{mongo_port}/")
db = client[mongo_db]

print(f"\n数据库: {db.name}")
print(f"集合数量: {len(db.list_collection_names())}")

# 查看 prompt_templates 集合
print("\n" + "="*60)
print("prompt_templates 集合")
print("="*60)

collection = db.prompt_templates
count = collection.count_documents({})
print(f"文档数量: {count}")

if count > 0:
    # 获取一个示例文档
    sample = collection.find_one({"is_system": True, "agent_type": "analysts"})
    
    if sample:
        print("\n示例文档结构:")
        print(json.dumps({
            "_id": str(sample.get("_id")),
            "agent_type": sample.get("agent_type"),
            "agent_name": sample.get("agent_name"),
            "template_name": sample.get("template_name"),
            "is_system": sample.get("is_system"),
            "content_keys": list(sample.get("content", {}).keys()) if "content" in sample else []
        }, indent=2, ensure_ascii=False))
        
        # 查看 user_prompt
        content = sample.get("content", {})
        user_prompt = content.get("user_prompt", "")
        
        print(f"\nuser_prompt 字段:")
        print(f"  长度: {len(user_prompt)}")
        print(f"  包含 current_price: {'current_price' in user_prompt}")
        print(f"  包含 {{{{current_price}}}}: {'{{current_price}}' in user_prompt}")
        
        if user_prompt:
            print(f"\n  前300字符:")
            print(f"  {user_prompt[:300]}")

client.close()
print("\n✅ 完成")

