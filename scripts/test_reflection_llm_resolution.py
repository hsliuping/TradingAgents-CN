"""验证 _resolve_reflection_llm_client 在不同 db 类型下都能正确解析 LLM。

复现 trade_review_service 的场景：传入 Motor async db，
确认不再返回 None（之前会因 Motor find_one 返回 coroutine 而失败，走 deepseek 兜底）。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))


def _summarize(label: str, client) -> None:
    print(f"\n--- {label} ---")
    if client is None:
        print("  结果: None（反思会降级到原文写入，不再调 LLM 提炼）")
        return
    # UnifiedLLMClient 内部持有 LLMConfig
    cfg = getattr(client, "_config", None) or getattr(client, "config", None)
    if cfg is None:
        print(f"  结果: client={type(client).__name__}（无法读取 config）")
        return
    print(f"  结果: client={type(client).__name__}")
    print(f"    provider = {getattr(cfg, 'provider', '')}")
    print(f"    model    = {getattr(cfg, 'model', '')}")
    print(f"    api_key  = {'已配置' if getattr(cfg, 'api_key', '') else '未配置'}")
    print(f"    base_url = {getattr(cfg, 'base_url', '')}")


def main() -> int:
    from core.agents.reflection_helper import _resolve_reflection_llm_client

    # 场景 1：传 None（应回退到同步 db）
    client_none = _resolve_reflection_llm_client(None)
    _summarize("场景 1: db=None（应回退到 get_mongo_db_sync）", client_none)

    # 场景 2：传 Motor async db（trade_review_service 的真实场景）
    try:
        from app.core.database import get_mongo_db
        motor_db = get_mongo_db()
        client_motor = _resolve_reflection_llm_client(motor_db)
        _summarize("场景 2: db=Motor AsyncIOMotorDatabase（trade_review 路径）", client_motor)
    except Exception as e:
        print(f"\n场景 2 失败: {type(e).__name__}: {e}")

    # 场景 3：传同步 PyMongo Database（researcher._get_db_handle 的兜底路径）
    try:
        from app.core.database import get_mongo_db_sync
        sync_db = get_mongo_db_sync()
        client_sync = _resolve_reflection_llm_client(sync_db)
        _summarize("场景 3: db=PyMongo sync Database（researcher 兜底路径）", client_sync)
    except Exception as e:
        print(f"\n场景 3 失败: {type(e).__name__}: {e}")

    # 断言：三种场景应解析到同一个 LLM 配置
    success = client_none is not None and client_motor is not None and client_sync is not None
    print(f"\n=== 结论：{'✅ 三种 db 类型均成功解析 LLM' if success else '⚠️  仍有场景解析失败'} ===")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
