#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
升级用户为高级学员

将指定用户升级为高级学员（PRO），以便使用批量导入等高级功能。

使用方法：
    python scripts/upgrade_user_to_pro.py [username]
    
示例：
    python scripts/upgrade_user_to_pro.py admin

作者: TradingAgents-CN Pro Team
版本: v1.0.0
创建日期: 2026-01-24
"""

import os
import sys
import asyncio
from datetime import datetime, timedelta

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


async def upgrade_user_to_pro(username: str = "admin"):
    """升级用户为高级学员"""
    from app.core.database import init_database, get_mongo_db
    
    print(f"\n{'='*60}")
    print(f"  升级用户为高级学员")
    print(f"{'='*60}\n")
    
    try:
        # 初始化数据库连接
        print("⏳ 正在连接数据库...")
        await init_database()
        db = get_mongo_db()
        print("✅ 数据库连接成功\n")
        
        # 查找用户
        print(f"🔍 查找用户: {username}")
        user = await db.users.find_one({"username": username})
        
        if not user:
            print(f"❌ 用户不存在: {username}")
            return False
        
        print(f"✅ 找到用户: {user.get('username')}")
        print(f"   当前计划: {user.get('plan', 'free')}")
        print(f"   当前角色: {user.get('role', 'user')}")
        
        # 检查是否已经是高级学员
        if user.get("plan") == "pro":
            print(f"\n✅ 用户已经是高级学员，无需升级")
            return True
        
        # 升级为高级学员
        print(f"\n⏳ 正在升级用户为高级学员...")
        
        # 设置许可证过期时间为1年后
        license_expires_at = datetime.utcnow() + timedelta(days=365)
        
        update_result = await db.users.update_one(
            {"username": username},
            {
                "$set": {
                    "plan": "pro",
                    "license_expires_at": license_expires_at,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if update_result.modified_count > 0:
            print(f"✅ 升级成功！")
            print(f"\n用户信息：")
            print(f"   用户名: {username}")
            print(f"   计划: pro (高级学员)")
            print(f"   许可证过期时间: {license_expires_at.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"\n现在可以使用批量导入等高级功能了！")
            return True
        else:
            print(f"❌ 升级失败：数据库更新失败")
            return False
            
    except Exception as e:
        print(f"❌ 升级过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主函数"""
    # 获取用户名参数
    username = sys.argv[1] if len(sys.argv) > 1 else "admin"
    
    # 升级用户
    success = await upgrade_user_to_pro(username)
    
    if success:
        print(f"\n{'='*60}")
        print(f"  升级完成！")
        print(f"{'='*60}\n")
    else:
        print(f"\n{'='*60}")
        print(f"  升级失败！")
        print(f"{'='*60}\n")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

