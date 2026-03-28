"""
旧认证路由兼容层。

历史测试和部分旧代码仍从 ``app.routers.auth`` 导入认证依赖，
当前实现已经迁移到 ``app.routers.auth_db``，这里仅做向后兼容转发。
"""

from app.routers.auth_db import *  # noqa: F401,F403

