"""bind_loop_safe_mongo_db 防退化锚点。

app/worker 下 8 处调用点（baostock/akshare/tushare sync service）依赖该函数在
事件循环切换后把 loop-safe MongoDB 代理重新绑定到服务实例属性上，
替代手动重建 AsyncIOMotorClient。若该函数被误删或改签，worker 数据同步将静默退化。
"""

from types import SimpleNamespace

from app.core.database import bind_loop_safe_mongo_db


def test_bind_loop_safe_mongo_db_binds_get_mongo_db_result(monkeypatch):
    sentinel = SimpleNamespace(name="loop-safe-db")
    monkeypatch.setattr("app.core.database.get_mongo_db", lambda: sentinel)

    target = SimpleNamespace()
    result = bind_loop_safe_mongo_db(target)

    # 绑定的必须是 get_mongo_db() 返回的同一个 loop-safe 代理对象（不做包装/复制）
    assert target.db is sentinel
    assert result is sentinel


def test_bind_loop_safe_mongo_db_supports_custom_attr_name(monkeypatch):
    sentinel = SimpleNamespace(name="loop-safe-db")
    monkeypatch.setattr("app.core.database.get_mongo_db", lambda: sentinel)

    target = SimpleNamespace()
    result = bind_loop_safe_mongo_db(target, attr_name="mongo_db")

    assert target.mongo_db is sentinel
    assert result is sentinel
    assert not hasattr(target, "db")
