"""
旧数据库模块兼容层。

历史测试仍从 ``app.database`` 导入数据库访问函数，
当前实现已经迁移到 ``app.core.database``。
"""

from app.core.database import *  # noqa: F401,F403

