"""
迁移脚本基类

每个迁移脚本需要继承此基类，或者直接定义模块级别的常量和函数。

方式一（推荐，简单）：模块级别定义
    # migrations/v2_0_1.py
    VERSION = "2.0.1"
    DESCRIPTION = "添加 xxx 字段"
    
    async def upgrade(db):
        await db.some_collection.update_many(...)
    
    async def downgrade(db):
        await db.some_collection.update_many(...)

方式二：类继承
    class Migration(BaseMigration):
        VERSION = "2.0.1"
        DESCRIPTION = "添加 xxx 字段"
        
        async def upgrade(self, db):
            ...
"""

from abc import ABC, abstractmethod


class BaseMigration(ABC):
    """迁移脚本基类（可选使用）"""
    
    VERSION: str = ""
    DESCRIPTION: str = ""
    
    @abstractmethod
    async def upgrade(self, db):
        """
        正向迁移 - 应用数据库变更
        
        Args:
            db: AsyncIOMotorDatabase 实例
            
        注意事项：
        - 必须是幂等的（重复执行不会出错）
        - 使用 $exists 检查字段是否已存在
        - 使用 find_one 检查数据是否已插入
        - 创建索引时使用 create_index（已存在会自动跳过）
        """
        raise NotImplementedError
    
    async def downgrade(self, db):
        """
        回滚迁移 - 撤销数据库变更（可选实现）
        
        Args:
            db: AsyncIOMotorDatabase 实例
        """
        raise NotImplementedError(
            f"Migration {self.VERSION} does not support downgrade"
        )

