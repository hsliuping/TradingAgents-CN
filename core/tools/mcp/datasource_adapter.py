"""
MCP 数据源适配器

将数据源类 MCP 工具返回的原始数据标准化后持久化到 MongoDB。
支持三层数据处理策略：
  1. 结构化 + 字段映射 → 写入现有/新集合
  2. 无字段映射配置   → 原样写入目标集合（需 data_mapping 指定 target_collection）
  3. 无 data_mapping  → 非结构化，写入 mcp_documents 集合
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MCP_DOCUMENTS_COLLECTION = "mcp_documents"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class MCPDatasourceAdapter:
    """
    MCP 数据源适配器

    负责将 MCP 工具原始响应（字符串）解析、字段映射、单位转换，
    然后持久化到 MongoDB。
    """

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def adapt_and_persist(
        self,
        raw_result: str,
        tool_name: str,
        data_mapping: Optional[Dict],
        server_name: str,
    ) -> Optional[str]:
        """
        解析 raw_result，应用字段映射，写入 MongoDB。

        Args:
            raw_result:   MCP call_tool 返回的原始字符串
            tool_name:    工具名称（仅用于日志）
            data_mapping: 来自 mcp_server_configs.data_mappings 中对应 tool_name 的条目
            server_name:  MCP 服务器名称（写入 data_source 标识）

        Returns:
            写入的目标集合名，写入失败时返回 None
        """
        if data_mapping is None:
            # 无映射配置 → 非结构化处理
            self.persist_unstructured(raw_result, tool_name, server_name)
            return MCP_DOCUMENTS_COLLECTION

        target_collection = data_mapping.get("target_collection")
        if not target_collection:
            logger.warning(f"[MCP Adapter] data_mapping 缺少 target_collection，工具: {tool_name}")
            self.persist_unstructured(raw_result, tool_name, server_name)
            return MCP_DOCUMENTS_COLLECTION

        # 解析 JSON 数据
        records = self._parse_result(raw_result)
        if not records:
            logger.info(f"[MCP Adapter] {tool_name} 返回空数据，跳过持久化")
            return target_collection

        # 应用字段映射和单位转换（支持 field_mapping_list 数组格式，实现一源多目标）
        field_mapping = data_mapping.get("field_mapping", {})
        field_mapping_list = data_mapping.get("field_mapping_list", [])
        if field_mapping_list:
            mapping_pairs = [
                (p.get("source") or p.get("key"), p.get("target") or p.get("value"))
                for p in field_mapping_list
                if (p.get("source") or p.get("key")) and (p.get("target") or p.get("value"))
            ]
        else:
            mapping_pairs = list(field_mapping.items())
        unit_conversion = data_mapping.get("unit_conversion", {})
        mapped_records = [
            self._map_record(record, mapping_pairs, unit_conversion, server_name)
            for record in records
        ]

        # 写入 MongoDB
        self._write_to_collection(target_collection, mapped_records)
        logger.info(f"[MCP Adapter] {tool_name} → {target_collection}: {len(mapped_records)} 条记录")
        return target_collection

    def persist_unstructured(
        self,
        raw_result: str,
        tool_name: str,
        server_name: str,
        meta: Optional[Dict] = None,
    ) -> None:
        """
        将非结构化数据写入 mcp_documents 集合。

        Args:
            raw_result:  原始文本内容
            tool_name:   工具名称
            server_name: MCP 服务器名称
            meta:        附加元数据（如 stock_code、doc_type 等）
        """
        doc = {
            "server_name": server_name,
            "tool_name": tool_name,
            "content": raw_result,
            "doc_type": (meta or {}).get("doc_type", "raw"),
            "stock_code": (meta or {}).get("stock_code"),
            "tags": (meta or {}).get("tags", []),
            "created_at": _now_utc(),
        }
        try:
            from app.core.database import get_mongo_db_sync
            db = get_mongo_db_sync()
            if db is not None:
                db[MCP_DOCUMENTS_COLLECTION].insert_one(doc)
                logger.info(f"[MCP Adapter] 非结构化数据写入 mcp_documents ({tool_name})")
        except Exception as e:
            logger.warning(f"[MCP Adapter] 写入 mcp_documents 失败: {e}")

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    def _parse_result(self, raw_result: str) -> List[Dict]:
        """尝试将 raw_result 解析为记录列表"""
        try:
            data = json.loads(raw_result)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                # 常见结构：{"data": [...]} 或 {"records": [...]} 或直接是单条记录
                for key in ("data", "records", "result", "rows"):
                    if isinstance(data.get(key), list):
                        return data[key]
                return [data]  # 单条记录
        except (json.JSONDecodeError, TypeError):
            pass
        return []

    def _map_record(
        self,
        record: Dict,
        mapping_pairs: List[tuple],
        unit_conversion: Dict[str, Dict],
        server_name: str,
    ) -> Dict:
        """将单条原始记录按映射规则转换。mapping_pairs 为 [(src, dst), ...]，支持一源多目标"""
        if not mapping_pairs:
            # 无映射规则，原样保留，只追加 data_source
            record["data_source"] = f"mcp:{server_name}"
            return record

        mapped: Dict[str, Any] = {}
        mapped_src_keys = set()
        for src_field, dst_field in mapping_pairs:
            if src_field in record:
                value = record[src_field]
                # 单位转换
                conv = unit_conversion.get(src_field)
                if conv and isinstance(value, (int, float)):
                    factor = conv.get("factor", 1)
                    value = value * factor
                mapped[dst_field] = value
                mapped_src_keys.add(src_field)

        # 保留未映射的字段（extra_fields: preserve 行为）
        for k, v in record.items():
            if k not in mapped_src_keys:
                mapped[k] = v

        mapped["data_source"] = f"mcp:{server_name}"
        mapped["updated_at"] = _now_utc()
        return mapped

    def _write_to_collection(self, collection_name: str, records: List[Dict]) -> None:
        """批量写入 MongoDB 集合（upsert 需由调用方通过字段自行实现，此处为 insert_many）"""
        try:
            from app.core.database import get_mongo_db_sync
            db = get_mongo_db_sync()
            if db is not None:
                db[collection_name].insert_many(records, ordered=False)
        except Exception as e:
            logger.warning(f"[MCP Adapter] 写入集合 {collection_name} 失败: {e}")


# ------------------------------------------------------------------
# 全局单例
# ------------------------------------------------------------------

_adapter: Optional[MCPDatasourceAdapter] = None


def get_mcp_datasource_adapter() -> MCPDatasourceAdapter:
    """获取 MCPDatasourceAdapter 全局单例"""
    global _adapter
    if _adapter is None:
        _adapter = MCPDatasourceAdapter()
    return _adapter

