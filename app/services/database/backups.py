"""
Backup, import, and export routines extracted from DatabaseService.
"""
from __future__ import annotations

import json
import os
import io
import gzip
import zipfile
import asyncio
import subprocess
import shutil
from datetime import datetime
from typing import Any, Dict, List, Optional
import logging

from bson import ObjectId

from app.core.database import get_mongo_db
from app.core.config import settings
from .serialization import serialize_document

logger = logging.getLogger(__name__)


def _check_mongodump_available() -> bool:
    """
    检查 mongodump 命令是否可用
    
    检查顺序：
    1. PATH 环境变量中的 mongodump
    2. vendors/mongodb/*/bin/mongodump.exe（便携版目录）
    3. 应用目录下的 tools/mongodb-tools/mongodump.exe
    """
    # 1. 检查 PATH 中的 mongodump
    if shutil.which("mongodump") is not None:
        return True
    
    # 2. 检查 vendors/mongodb 目录（便携版）
    # 从当前文件位置向上查找项目根目录
    current_file = os.path.abspath(__file__)
    project_root = current_file
    for _ in range(5):  # 最多向上查找5层
        project_root = os.path.dirname(project_root)
        vendors_mongodb = os.path.join(project_root, "vendors", "mongodb")
        if os.path.exists(vendors_mongodb):
            # 查找 mongodb-* 子目录
            for item in os.listdir(vendors_mongodb):
                mongodb_dir = os.path.join(vendors_mongodb, item)
                if os.path.isdir(mongodb_dir):
                    mongodump_path = os.path.join(mongodb_dir, "bin", "mongodump.exe")
                    if os.path.exists(mongodump_path):
                        logger.info(f"✅ 找到 MongoDB Database Tools: {mongodump_path}")
                        return True
            break
    
    # 3. 检查应用目录下的 tools/mongodb-tools
    app_dir = settings.TRADINGAGENTS_DATA_DIR
    if app_dir:
        # 尝试多个可能的路径
        possible_paths = [
            os.path.join(app_dir, "..", "tools", "mongodb-tools", "mongodump.exe"),
            os.path.join(app_dir, "tools", "mongodb-tools", "mongodump.exe"),
            os.path.join(os.path.dirname(app_dir), "tools", "mongodb-tools", "mongodump.exe"),
        ]
        for path in possible_paths:
            abs_path = os.path.abspath(path)
            if os.path.exists(abs_path):
                logger.info(f"✅ 找到 MongoDB Database Tools: {abs_path}")
                return True
    
    return False


def _get_mongodump_command() -> str:
    """
    获取 mongodump 命令的完整路径
    
    返回：
    - 如果找到，返回完整路径（Windows 需要 .exe 扩展名）
    - 如果未找到，返回 "mongodump"（依赖 PATH）
    """
    # 1. 检查 PATH 中的 mongodump
    mongodump_path = shutil.which("mongodump")
    if mongodump_path:
        return mongodump_path
    
    # 2. 检查 vendors/mongodb 目录（便携版）
    current_file = os.path.abspath(__file__)
    project_root = current_file
    for _ in range(5):  # 最多向上查找5层
        project_root = os.path.dirname(project_root)
        vendors_mongodb = os.path.join(project_root, "vendors", "mongodb")
        if os.path.exists(vendors_mongodb):
            # 查找 mongodb-* 子目录
            for item in os.listdir(vendors_mongodb):
                mongodb_dir = os.path.join(vendors_mongodb, item)
                if os.path.isdir(mongodb_dir):
                    mongodump_path = os.path.join(mongodb_dir, "bin", "mongodump.exe")
                    if os.path.exists(mongodump_path):
                        return mongodump_path
            break
    
    # 3. 检查应用目录下的 tools/mongodb-tools
    app_dir = settings.TRADINGAGENTS_DATA_DIR
    if app_dir:
        possible_paths = [
            os.path.join(app_dir, "..", "tools", "mongodb-tools", "mongodump.exe"),
            os.path.join(app_dir, "tools", "mongodb-tools", "mongodump.exe"),
            os.path.join(os.path.dirname(app_dir), "tools", "mongodb-tools", "mongodump.exe"),
        ]
        for path in possible_paths:
            abs_path = os.path.abspath(path)
            if os.path.exists(abs_path):
                return abs_path
    
    # 4. 如果都找不到，返回默认命令（可能失败，但让调用者处理）
    return "mongodump"


async def create_backup_native(name: str, backup_dir: str, collections: Optional[List[str]] = None, user_id: str | None = None) -> Dict[str, Any]:
    """
    使用 MongoDB 原生 mongodump 命令创建备份（推荐，速度快）

    优势：
    - 速度快（直接操作 BSON，不需要 JSON 转换）
    - 压缩效率高
    - 支持大数据量
    - 并行处理多个集合

    要求：
    - 系统中需要安装 MongoDB Database Tools
    - mongodump 命令在 PATH 中可用
    
    注意：
    - 如果 mongodump 不可用，系统会自动降级到 Python 实现（create_backup）
    """
    if not _check_mongodump_available():
        logger.warning("⚠️ mongodump 命令不可用，将自动使用 Python 实现（速度较慢）")
        logger.warning("💡 提示：安装 MongoDB Database Tools 可获得更快的备份速度")
        logger.warning("   下载地址：https://www.mongodb.com/try/download/database-tools")
        raise Exception("mongodump 命令不可用，请安装 MongoDB Database Tools 或使用 create_backup() 方法")

    db = get_mongo_db()

    backup_id = str(ObjectId())
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_dirname = f"backup_{name}_{timestamp}"
    backup_path = os.path.join(backup_dir, backup_dirname)

    os.makedirs(backup_dir, exist_ok=True)

    # 获取 mongodump 命令路径
    mongodump_cmd = _get_mongodump_command()
    
    # 构建 mongodump 命令
    cmd = [
        mongodump_cmd,
        "--uri", settings.MONGO_URI,
        "--out", backup_path,
        "--gzip"  # 启用压缩
    ]

    # 如果指定了集合，只备份这些集合
    if collections:
        for collection_name in collections:
            cmd.extend(["--collection", collection_name])

    logger.info(f"🔄 开始执行 mongodump 备份: {name}")

    # 🔥 使用 asyncio.to_thread 在线程池中执行阻塞的 subprocess 调用
    def _run_mongodump():
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600  # 1小时超时
        )
        if result.returncode != 0:
            raise Exception(f"mongodump 执行失败: {result.stderr}")
        return result

    try:
        await asyncio.to_thread(_run_mongodump)
        logger.info(f"✅ mongodump 备份完成: {name}")
    except subprocess.TimeoutExpired:
        raise Exception("备份超时（超过1小时）")
    except Exception as e:
        logger.error(f"❌ mongodump 备份失败: {e}")
        # 清理失败的备份目录
        if os.path.exists(backup_path):
            await asyncio.to_thread(shutil.rmtree, backup_path)
        raise

    # 计算备份大小
    def _get_dir_size(path):
        total = 0
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                total += os.path.getsize(filepath)
        return total

    file_size = await asyncio.to_thread(_get_dir_size, backup_path)

    # 获取实际备份的集合列表
    if not collections:
        collections = await db.list_collection_names()
        collections = [c for c in collections if not c.startswith("system.")]

    backup_meta = {
        "_id": ObjectId(backup_id),
        "name": name,
        "filename": backup_dirname,
        "file_path": backup_path,
        "size": file_size,
        "collections": collections,
        "created_at": datetime.utcnow(),
        "created_by": user_id,
        "backup_type": "mongodump",  # 标记备份类型
    }

    await db.database_backups.insert_one(backup_meta)

    return {
        "id": backup_id,
        "name": name,
        "filename": backup_dirname,
        "file_path": backup_path,
        "size": file_size,
        "collections": collections,
        "created_at": backup_meta["created_at"].isoformat(),
        "backup_type": "mongodump",
    }


async def create_backup(name: str, backup_dir: str, collections: Optional[List[str]] = None, user_id: str | None = None) -> Dict[str, Any]:
    """
    创建数据库备份（Python 实现，兼容性好但速度较慢）

    对于大数据量（>100MB），建议使用 create_backup_native() 方法
    """
    db = get_mongo_db()

    backup_id = str(ObjectId())
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"backup_{name}_{timestamp}.json.gz"
    backup_path = os.path.join(backup_dir, backup_filename)

    if not collections:
        collections = await db.list_collection_names()

    backup_data: Dict[str, Any] = {
        "backup_id": backup_id,
        "name": name,
        "created_at": datetime.utcnow().isoformat(),
        "created_by": user_id,
        "collections": collections,
        "data": {},
    }

    for collection_name in collections:
        collection = db[collection_name]
        documents: List[dict] = []
        async for doc in collection.find():
            documents.append(serialize_document(doc))
        backup_data["data"][collection_name] = documents

    os.makedirs(backup_dir, exist_ok=True)

    # 🔥 使用 asyncio.to_thread 将阻塞的文件 I/O 操作放到线程池执行
    def _write_backup():
        with gzip.open(backup_path, "wt", encoding="utf-8") as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
        return os.path.getsize(backup_path)

    file_size = await asyncio.to_thread(_write_backup)

    backup_meta = {
        "_id": ObjectId(backup_id),
        "name": name,
        "filename": backup_filename,
        "file_path": backup_path,
        "size": file_size,
        "collections": collections,
        "created_at": datetime.utcnow(),
        "created_by": user_id,
    }

    await db.database_backups.insert_one(backup_meta)

    return {
        "id": backup_id,
        "name": name,
        "filename": backup_filename,
        "file_path": backup_path,
        "size": file_size,
        "collections": collections,
        "created_at": backup_meta["created_at"].isoformat(),
    }


async def list_backups() -> List[Dict[str, Any]]:
    db = get_mongo_db()
    backups: List[Dict[str, Any]] = []
    async for backup in db.database_backups.find().sort("created_at", -1):
        backups.append({
            "id": str(backup["_id"]),
            "name": backup["name"],
            "filename": backup["filename"],
            "size": backup["size"],
            "collections": backup["collections"],
            "created_at": backup["created_at"].isoformat(),
            "created_by": backup.get("created_by"),
        })
    return backups


async def delete_backup(backup_id: str) -> None:
    db = get_mongo_db()
    backup = await db.database_backups.find_one({"_id": ObjectId(backup_id)})
    if not backup:
        raise Exception("备份不存在")
    if os.path.exists(backup["file_path"]):
        # 🔥 使用 asyncio.to_thread 将阻塞的文件删除操作放到线程池执行
        backup_type = backup.get("backup_type", "python")
        if backup_type == "mongodump":
            # mongodump 备份是目录，需要递归删除
            await asyncio.to_thread(shutil.rmtree, backup["file_path"])
        else:
            # Python 备份是单个文件
            await asyncio.to_thread(os.remove, backup["file_path"])
    await db.database_backups.delete_one({"_id": ObjectId(backup_id)})


def _convert_date_fields(doc: dict) -> dict:
    """
    转换文档中的日期字段（字符串 -> datetime）

    常见的日期字段：
    - created_at, updated_at, completed_at
    - started_at, finished_at
    - analysis_date (保持字符串格式，因为是日期而非时间戳)
    """
    from dateutil import parser

    date_fields = [
        "created_at", "updated_at", "completed_at",
        "started_at", "finished_at", "deleted_at",
        "last_login", "last_modified", "timestamp"
    ]

    for field in date_fields:
        if field in doc and isinstance(doc[field], str):
            try:
                # 尝试解析日期字符串
                doc[field] = parser.parse(doc[field])
                logger.debug(f"✅ 转换日期字段 {field}: {doc[field]}")
            except Exception as e:
                logger.warning(f"⚠️ 无法解析日期字段 {field}: {doc[field]}, 错误: {e}")

    return doc


async def import_data(content: bytes, collection: str, *, format: str = "json", overwrite: bool = False, filename: str | None = None) -> Dict[str, Any]:
    """
    导入数据到数据库

    支持两种导入模式：
    1. 单集合模式：导入数据到指定集合
    2. 多集合模式：导入包含多个集合的导出文件（自动检测）
    
    支持的文件格式：
    - JSON 文件（.json）
    - ZIP 压缩文件（.zip），自动解压后提取 JSON 文件
    """
    db = get_mongo_db()

    # 检测是否为 ZIP 文件
    is_zip = False
    if filename and filename.lower().endswith('.zip'):
        is_zip = True
    elif content[:2] == b'PK':  # ZIP 文件魔数
        is_zip = True
    
    if is_zip:
        logger.info("📦 检测到 ZIP 文件，开始解压...")
        # 🔥 使用 asyncio.to_thread 将阻塞的 ZIP 解压操作放到线程池执行
        def _extract_zip():
            zip_buffer = io.BytesIO(content)
            with zipfile.ZipFile(zip_buffer, 'r') as zipf:
                # 查找 JSON 文件
                json_files = [f for f in zipf.namelist() if f.lower().endswith('.json')]
                if not json_files:
                    raise Exception("ZIP 文件中未找到 JSON 文件")
                if len(json_files) > 1:
                    logger.warning(f"⚠️ ZIP 文件中包含多个 JSON 文件，使用第一个: {json_files[0]}")
                # 读取第一个 JSON 文件
                json_content = zipf.read(json_files[0])
                return json_content.decode("utf-8")
        
        json_content_str = await asyncio.to_thread(_extract_zip)
        logger.info("✅ ZIP 文件解压成功")
        
        # 解析 JSON
        def _parse_json():
            return json.loads(json_content_str)
        
        data = await asyncio.to_thread(_parse_json)
    elif format.lower() == "json":
        # 🔥 使用 asyncio.to_thread 将阻塞的 JSON 解析放到线程池执行
        def _parse_json():
            return json.loads(content.decode("utf-8"))

        data = await asyncio.to_thread(_parse_json)
    else:
        raise Exception(f"不支持的格式: {format}")

    # 检测是否为多集合导出格式
    logger.info(f"🔍 [导入检测] 数据类型: {type(data)}")

    # 🔥 新格式：包含 export_info 和 data 的字典
    if isinstance(data, dict) and "export_info" in data and "data" in data:
        logger.info(f"📦 检测到新版多集合导出文件（包含 export_info）")
        export_info = data.get("export_info", {})
        logger.info(f"📋 导出信息: 创建时间={export_info.get('created_at')}, 集合数={len(export_info.get('collections', []))}")

        # 提取实际数据
        data = data["data"]
        logger.info(f"📦 包含 {len(data)} 个集合: {list(data.keys())}")

    # 🔥 旧格式：直接是集合名到文档列表的映射
    if isinstance(data, dict):
        logger.info(f"🔍 [导入检测] 字典包含 {len(data)} 个键")
        logger.info(f"🔍 [导入检测] 键列表: {list(data.keys())[:10]}")  # 只显示前10个

        # 检查每个键值对的类型
        for k, v in list(data.items())[:5]:  # 只检查前5个
            logger.info(f"🔍 [导入检测] 键 '{k}': 值类型={type(v)}, 是否为列表={isinstance(v, list)}")
            if isinstance(v, list):
                logger.info(f"🔍 [导入检测] 键 '{k}': 列表长度={len(v)}")

    if isinstance(data, dict) and all(isinstance(k, str) and isinstance(v, list) for k, v in data.items()):
        # 多集合模式
        logger.info(f"📦 确认为多集合导入模式，包含 {len(data)} 个集合")

        total_inserted = 0
        imported_collections = []

        for coll_name, documents in data.items():
            if not documents:  # 跳过空集合
                logger.info(f"⏭️ 跳过空集合: {coll_name}")
                continue

            collection_obj = db[coll_name]

            if overwrite:
                deleted_count = await collection_obj.delete_many({})
                logger.info(f"🗑️ 清空集合 {coll_name}：删除 {deleted_count.deleted_count} 条文档")

            # 处理 _id 字段和日期字段
            for doc in documents:
                # 转换 _id
                if "_id" in doc and isinstance(doc["_id"], str):
                    try:
                        doc["_id"] = ObjectId(doc["_id"])
                    except Exception:
                        del doc["_id"]

                # 🔥 转换日期字段（字符串 -> datetime）
                _convert_date_fields(doc)

            # 插入数据
            if documents:
                res = await collection_obj.insert_many(documents)
                inserted_count = len(res.inserted_ids)
                total_inserted += inserted_count
                imported_collections.append(coll_name)
                logger.info(f"✅ 导入集合 {coll_name}：{inserted_count} 条文档")

        return {
            "mode": "multi_collection",
            "collections": imported_collections,
            "total_collections": len(imported_collections),
            "total_inserted": total_inserted,
            "filename": filename,
            "format": format,
            "overwrite": overwrite,
        }
    else:
        # 单集合模式（兼容旧版本）
        logger.info(f"📄 单集合导入模式，目标集合: {collection}")
        logger.info(f"🔍 [单集合模式] 数据类型: {type(data)}")

        if isinstance(data, dict):
            logger.info(f"🔍 [单集合模式] 字典包含 {len(data)} 个键")
            logger.info(f"🔍 [单集合模式] 键列表: {list(data.keys())[:10]}")

        collection_obj = db[collection]

        if not isinstance(data, list):
            logger.info(f"🔍 [单集合模式] 数据不是列表，转换为列表")
            data = [data]

        logger.info(f"🔍 [单集合模式] 准备插入 {len(data)} 条文档")

        if overwrite:
            deleted_count = await collection_obj.delete_many({})
            logger.info(f"🗑️ 清空集合 {collection}：删除 {deleted_count.deleted_count} 条文档")

        for doc in data:
            # 转换 _id
            if "_id" in doc and isinstance(doc["_id"], str):
                try:
                    doc["_id"] = ObjectId(doc["_id"])
                except Exception:
                    del doc["_id"]

            # 🔥 转换日期字段（字符串 -> datetime）
            _convert_date_fields(doc)

        inserted_count = 0
        if data:
            res = await collection_obj.insert_many(data)
            inserted_count = len(res.inserted_ids)

        return {
            "mode": "single_collection",
            "collection": collection,
            "inserted_count": inserted_count,
            "filename": filename,
            "format": format,
            "overwrite": overwrite,
        }


def _sanitize_document(doc: Any) -> Any:
    """
    递归清空文档中的敏感字段

    敏感字段关键词：api_key, api_secret, secret, token, password,
                    client_secret, webhook_secret, private_key

    排除字段：max_tokens, timeout, retry_times 等配置字段（不是敏感信息）
    """
    SENSITIVE_KEYWORDS = [
        "api_key", "api_secret", "secret", "token", "password",
        "client_secret", "webhook_secret", "private_key"
    ]

    # 排除的字段（虽然包含敏感关键词，但不是敏感信息）
    EXCLUDED_FIELDS = [
        "max_tokens",      # LLM 配置：最大 token 数
        "timeout",         # 超时时间
        "retry_times",     # 重试次数
        "context_length",  # 上下文长度
    ]

    if isinstance(doc, dict):
        sanitized = {}
        for k, v in doc.items():
            # 检查是否在排除列表中
            if k.lower() in [f.lower() for f in EXCLUDED_FIELDS]:
                # 保留该字段
                if isinstance(v, (dict, list)):
                    sanitized[k] = _sanitize_document(v)
                else:
                    sanitized[k] = v
            # 检查字段名是否包含敏感关键词（忽略大小写）
            elif any(keyword in k.lower() for keyword in SENSITIVE_KEYWORDS):
                sanitized[k] = ""  # 清空敏感字段
            elif isinstance(v, (dict, list)):
                sanitized[k] = _sanitize_document(v)  # 递归处理
            else:
                sanitized[k] = v
        return sanitized
    elif isinstance(doc, list):
        return [_sanitize_document(item) for item in doc]
    else:
        return doc


async def export_data(collections: Optional[List[str]] = None, *, export_dir: str, format: str = "json", sanitize: bool = False) -> str:
    import pandas as pd

    # 🔥 使用异步数据库连接
    db = get_mongo_db()
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    if not collections:
        # 🔥 异步调用 list_collection_names()
        collections = await db.list_collection_names()
        collections = [c for c in collections if not c.startswith("system.")]

    os.makedirs(export_dir, exist_ok=True)

    all_data: Dict[str, List[dict]] = {}
    for collection_name in collections:
        collection = db[collection_name]
        docs: List[dict] = []

        # users 集合在脱敏模式下只导出空数组（保留结构，不导出实际用户数据）
        if sanitize and collection_name == "users":
            all_data[collection_name] = []
            continue

        # 🔥 异步迭代查询结果
        async for doc in collection.find():
            docs.append(serialize_document(doc))
        all_data[collection_name] = docs

    # 如果启用脱敏，递归清空所有敏感字段
    if sanitize:
        all_data = _sanitize_document(all_data)

    if format.lower() == "json":
        filename = f"export_{timestamp}.json"
        file_path = os.path.join(export_dir, filename)
        export_data_dict = {
            "export_info": {
                "created_at": datetime.utcnow().isoformat(),
                "collections": collections,
                "format": format,
            },
            "data": all_data,
        }

        # 🔥 使用 asyncio.to_thread 将阻塞的文件 I/O 操作放到线程池执行
        def _write_json():
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(export_data_dict, f, ensure_ascii=False, indent=2)

        await asyncio.to_thread(_write_json)
        
        # 压缩文件
        zip_filename = f"export_{timestamp}.zip"
        zip_path = os.path.join(export_dir, zip_filename)
        
        def _create_zip():
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(file_path, arcname=filename)
            # 删除临时 JSON 文件
            os.remove(file_path)
        
        await asyncio.to_thread(_create_zip)
        return zip_path

    if format.lower() == "csv":
        filename = f"export_{timestamp}.csv"
        file_path = os.path.join(export_dir, filename)
        rows: List[dict] = []
        for collection_name, documents in all_data.items():
            for doc in documents:
                row = {**doc}
                row["_collection"] = collection_name
                rows.append(row)

        # 🔥 使用 asyncio.to_thread 将阻塞的文件 I/O 操作放到线程池执行
        def _write_csv():
            if rows:
                pd.DataFrame(rows).to_csv(file_path, index=False, encoding="utf-8-sig")
            else:
                pd.DataFrame().to_csv(file_path, index=False, encoding="utf-8-sig")

        await asyncio.to_thread(_write_csv)
        
        # 压缩文件
        zip_filename = f"export_{timestamp}.zip"
        zip_path = os.path.join(export_dir, zip_filename)
        
        def _create_zip():
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(file_path, arcname=filename)
            # 删除临时 CSV 文件
            os.remove(file_path)
        
        await asyncio.to_thread(_create_zip)
        return zip_path

    if format.lower() in ["xlsx", "excel"]:
        filename = f"export_{timestamp}.xlsx"
        file_path = os.path.join(export_dir, filename)

        # 🔥 使用 asyncio.to_thread 将阻塞的文件 I/O 操作放到线程池执行
        def _write_excel():
            with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
                for collection_name, documents in all_data.items():
                    df = pd.DataFrame(documents) if documents else pd.DataFrame()
                    sheet = collection_name[:31]
                    df.to_excel(writer, sheet_name=sheet, index=False)

        await asyncio.to_thread(_write_excel)
        
        # 压缩文件
        zip_filename = f"export_{timestamp}.zip"
        zip_path = os.path.join(export_dir, zip_filename)
        
        def _create_zip():
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(file_path, arcname=filename)
            # 删除临时 Excel 文件
            os.remove(file_path)
        
        await asyncio.to_thread(_create_zip)
        return zip_path

    raise Exception(f"不支持的导出格式: {format}")

