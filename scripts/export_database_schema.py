"""
导出 MongoDB 数据库所有集合的表结构

使用方法:
    python scripts/export_database_schema.py
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import json
from typing import Dict, Any, List
from collections import defaultdict
from pymongo import MongoClient
from dotenv import load_dotenv

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 加载环境变量
load_dotenv()


def get_mongo_db():
    """获取 MongoDB 数据库连接"""
    # 从 .env 文件读取配置（使用正确的变量名）
    mongo_host = os.getenv("MONGODB_HOST", os.getenv("MONGO_HOST", "localhost"))
    mongo_port = int(os.getenv("MONGODB_PORT", os.getenv("MONGO_PORT", "27017")))
    mongo_db = os.getenv("MONGODB_DATABASE", os.getenv("MONGO_DB", "tradingagents"))
    mongo_user = os.getenv("MONGODB_USERNAME", os.getenv("MONGO_USER", ""))
    mongo_password = os.getenv("MONGODB_PASSWORD", os.getenv("MONGO_PASSWORD", ""))
    mongo_auth_source = os.getenv("MONGODB_AUTH_SOURCE", "admin")

    # 构建连接字符串
    if mongo_user and mongo_password:
        # 使用认证连接
        connection_string = f"mongodb://{mongo_user}:{mongo_password}@{mongo_host}:{mongo_port}/{mongo_db}?authSource={mongo_auth_source}"
    else:
        # 无认证连接
        connection_string = f"mongodb://{mongo_host}:{mongo_port}/"

    client = MongoClient(connection_string)
    return client[mongo_db]


def infer_field_type(value: Any) -> str:
    """推断字段类型"""
    if value is None:
        return "null"
    elif isinstance(value, bool):
        return "boolean"
    elif isinstance(value, int):
        return "integer"
    elif isinstance(value, float):
        return "float"
    elif isinstance(value, str):
        return "string"
    elif isinstance(value, datetime):
        return "datetime"
    elif isinstance(value, list):
        if len(value) > 0:
            return f"array<{infer_field_type(value[0])}>"
        return "array"
    elif isinstance(value, dict):
        return "object"
    else:
        return str(type(value).__name__)


def analyze_collection_schema(collection, sample_size=100) -> Dict[str, Any]:
    """分析集合的表结构"""
    # 获取样本文档
    documents = list(collection.find().limit(sample_size))
    
    if not documents:
        return {
            "collection_name": collection.name,
            "document_count": 0,
            "sample_size": 0,
            "fields": {},
            "sample_document": None
        }
    
    # 统计字段信息
    field_stats = defaultdict(lambda: {
        "types": set(),
        "count": 0,
        "null_count": 0,
        "sample_values": []
    })
    
    for doc in documents:
        analyze_document(doc, field_stats, prefix="")
    
    # 转换为可序列化的格式
    fields = {}
    for field_path, stats in field_stats.items():
        fields[field_path] = {
            "types": list(stats["types"]),
            "count": stats["count"],
            "null_count": stats["null_count"],
            "presence_rate": f"{stats['count'] / len(documents) * 100:.1f}%",
            "sample_values": stats["sample_values"][:3]  # 只保留3个示例
        }
    
    return {
        "collection_name": collection.name,
        "document_count": collection.count_documents({}),
        "sample_size": len(documents),
        "fields": fields,
        "sample_document": documents[0] if documents else None
    }


def analyze_document(doc: Dict, field_stats: Dict, prefix: str = "", max_depth: int = 3):
    """递归分析文档结构"""
    if max_depth <= 0:
        return
    
    for key, value in doc.items():
        field_path = f"{prefix}.{key}" if prefix else key
        
        # 记录字段类型
        field_type = infer_field_type(value)
        field_stats[field_path]["types"].add(field_type)
        field_stats[field_path]["count"] += 1
        
        if value is None:
            field_stats[field_path]["null_count"] += 1
        
        # 记录示例值
        if len(field_stats[field_path]["sample_values"]) < 3:
            if isinstance(value, (str, int, float, bool)):
                field_stats[field_path]["sample_values"].append(value)
            elif isinstance(value, datetime):
                field_stats[field_path]["sample_values"].append(value.isoformat())
        
        # 递归分析嵌套对象
        if isinstance(value, dict) and max_depth > 1:
            analyze_document(value, field_stats, field_path, max_depth - 1)


def export_schema_to_markdown(schema_data: List[Dict[str, Any]], output_file: Path, db_name: str):
    """导出表结构为 Markdown 文档"""
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("# TradingAgents-CN Pro 数据库表结构\n\n")
        f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**数据库**: {db_name}\n\n")
        f.write(f"**集合数量**: {len(schema_data)}\n\n")
        f.write("---\n\n")
        
        # 目录
        f.write("## 📋 集合目录\n\n")
        for schema in schema_data:
            collection_name = schema["collection_name"]
            doc_count = schema["document_count"]
            f.write(f"- [{collection_name}](#{collection_name}) ({doc_count:,} 条记录)\n")
        f.write("\n---\n\n")
        
        # 详细表结构
        for schema in schema_data:
            collection_name = schema.get("collection_name", "unknown")
            doc_count = schema.get("document_count", 0)
            sample_size = schema.get("sample_size", 0)
            fields = schema.get("fields", {})
            
            f.write(f"## {collection_name}\n\n")
            f.write(f"**文档数量**: {doc_count:,}\n\n")
            f.write(f"**分析样本**: {sample_size} 条\n\n")
            
            if fields:
                f.write("### 字段列表\n\n")
                f.write("| 字段路径 | 类型 | 出现率 | 示例值 |\n")
                f.write("|---------|------|--------|--------|\n")
                
                for field_path, field_info in sorted(fields.items()):
                    types = ", ".join(field_info["types"])
                    presence = field_info["presence_rate"]
                    samples = field_info["sample_values"]
                    sample_str = str(samples[0]) if samples else "-"
                    
                    # 截断过长的示例值
                    if len(sample_str) > 50:
                        sample_str = sample_str[:47] + "..."
                    
                    f.write(f"| `{field_path}` | {types} | {presence} | {sample_str} |\n")
                
                f.write("\n")
            
            f.write("---\n\n")


def main():
    print("🔍 连接 MongoDB...")
    db = get_mongo_db()

    print(f"📊 数据库: {db.name}")

    # 获取所有集合
    all_collection_names = sorted(db.list_collection_names())
    
    # 过滤掉系统集合（以 system. 开头的集合）
    collection_names = [name for name in all_collection_names if not name.startswith('system.')]
    
    print(f"📁 找到 {len(all_collection_names)} 个集合（包含 {len(all_collection_names) - len(collection_names)} 个系统集合）")
    print(f"📊 将分析 {len(collection_names)} 个用户集合\n")

    schema_data = []

    for collection_name in collection_names:
        try:
            print(f"   分析集合: {collection_name}...", end=" ")
            collection = db[collection_name]
            schema = analyze_collection_schema(collection)
            schema_data.append(schema)
            print(f"✅ ({schema['document_count']:,} 条记录)")
        except Exception as e:
            print(f"❌ 错误: {str(e)}")
            # 即使出错也继续处理其他集合
            continue

    # 导出为 Markdown
    output_dir = Path("docs/database")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "schema.md"

    print(f"\n📝 导出表结构到: {output_file}")
    export_schema_to_markdown(schema_data, output_file, db.name)

    print(f"✅ 完成！")


if __name__ == "__main__":
    main()

