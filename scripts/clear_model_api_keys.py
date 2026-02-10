"""清空 system_configs.llm_configs 中所有模型的 api_key 字段

问题：
- 后端在保存模型配置时，会自动从 llm_providers 复制 API Key 到模型配置中
- 导致模型配置中的 API Key 成为"快照"，不会随厂家配置更新而更新
- 优先级：模型配置 > 厂家配置 > 环境变量，所以旧值一直被使用

解决方案：
- 清空所有模型配置中的 api_key 字段
- 让系统回退到使用厂家配置的 API Key（已经更新为新值）
"""
import os
import sys
sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv()

from pymongo import MongoClient

# 构建 MongoDB 连接字符串（与后端逻辑一致）
MONGODB_HOST = os.getenv('MONGODB_HOST', 'localhost')
MONGODB_PORT = int(os.getenv('MONGODB_PORT', '27017'))
MONGODB_USERNAME = os.getenv('MONGODB_USERNAME', '')
MONGODB_PASSWORD = os.getenv('MONGODB_PASSWORD', '')
MONGODB_DATABASE = os.getenv('MONGODB_DATABASE', 'tradingagents')
MONGODB_AUTH_SOURCE = os.getenv('MONGODB_AUTH_SOURCE', 'admin')

if MONGODB_USERNAME and MONGODB_PASSWORD:
    MONGO_URI = f"mongodb://{MONGODB_USERNAME}:{MONGODB_PASSWORD}@{MONGODB_HOST}:{MONGODB_PORT}/{MONGODB_DATABASE}?authSource={MONGODB_AUTH_SOURCE}"
else:
    MONGO_URI = f"mongodb://{MONGODB_HOST}:{MONGODB_PORT}/{MONGODB_DATABASE}"

print(f"🔗 MongoDB URI: {MONGO_URI.replace(MONGODB_PASSWORD, '***') if MONGODB_PASSWORD else MONGO_URI}")

def main():
    client = MongoClient(MONGO_URI)
    db = client[MONGODB_DATABASE]
    
    # 1. 查看当前状态
    doc = db.system_configs.find_one({"is_active": True}, sort=[("version", -1)])
    if not doc or "llm_configs" not in doc:
        print("❌ 未找到 system_configs")
        client.close()
        return
    
    configs = doc["llm_configs"]
    print(f"=== 当前状态 ({len(configs)} 个模型) ===")
    has_api_key_count = 0
    for i, cfg in enumerate(configs):
        model = cfg.get("model_name", "unknown")
        provider = cfg.get("provider", "unknown")
        api_key = cfg.get("api_key", "")
        if api_key:
            has_api_key_count += 1
            print(f"  [{i}] {provider}/{model}: api_key = {api_key[:20]}... (将被清空)")
        else:
            print(f"  [{i}] {provider}/{model}: api_key = (空)")
    
    if has_api_key_count == 0:
        print("\n✅ 所有模型配置的 api_key 已经是空，无需清空")
        client.close()
        return
    
    print(f"\n⚠️  发现 {has_api_key_count} 个模型配置包含 api_key")
    
    # 2. 确认操作
    confirm = input("\n是否清空这些 api_key？(yes/no): ")
    if confirm.lower() != 'yes':
        print("❌ 操作已取消")
        client.close()
        return
    
    # 3. 清空所有模型配置的 api_key
    print("\n🔧 开始清空...")
    for cfg in configs:
        if "api_key" in cfg:
            cfg["api_key"] = ""  # 设置为空字符串
    
    # 4. 更新数据库
    result = db.system_configs.update_one(
        {"_id": doc["_id"]},
        {
            "$set": {
                "llm_configs": configs,
                "version": doc.get("version", 0) + 1
            },
            "$currentDate": {"updated_at": True}
        }
    )
    
    if result.modified_count > 0:
        print(f"✅ 成功清空 {has_api_key_count} 个模型配置的 api_key")
        print(f"✅ 配置版本已更新: {doc.get('version', 0)} → {doc.get('version', 0) + 1}")
        print("\n💡 下一步：")
        print("   1. 重启后端服务")
        print("   2. 运行分析任务测试")
        print("   3. 检查日志确认使用的是厂家配置的 API Key")
    else:
        print("❌ 更新失败")
    
    client.close()

if __name__ == "__main__":
    main()

