"""
Serialization helpers for MongoDB documents.
"""
from __future__ import annotations

from datetime import datetime
from bson import ObjectId


def serialize_document(doc: dict) -> dict:
    """Serialize special MongoDB types to JSON-friendly primitives.
    - ObjectId -> str
    - datetime -> ISO string
    - Recurse into nested dict/list
    """
    serialized = {}
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            serialized[key] = str(value)
        elif isinstance(value, datetime):
            serialized[key] = value.isoformat()
        elif isinstance(value, dict):
            serialized[key] = serialize_document(value)
        elif isinstance(value, list):
            out_list = []
            for item in value:
                if isinstance(item, dict):
                    out_list.append(serialize_document(item))
                elif isinstance(item, ObjectId):
                    out_list.append(str(item))
                elif isinstance(item, datetime):
                    out_list.append(item.isoformat())
                else:
                    out_list.append(item)
            serialized[key] = out_list
        else:
            serialized[key] = value
    return serialized

