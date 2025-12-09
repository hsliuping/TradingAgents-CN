#!/usr/bin/env python3
"""
调试用户token中的信息
"""

import asyncio
import sys
import os
from pathlib import Path
import jwt
import datetime

# 添加项目根目录到Python路径
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings
from app.services.auth_service import AuthService

def debug_jwt_token():
    """调试JWT token"""
    print("🔍 JWT Token调试...")

    # 模拟创建token（使用相同的密钥）
    test_token = AuthService.create_access_token(sub="user3")
    print(f"✅ 创建的token: {test_token[:50]}...")

    # 解码token
    try:
        decoded = jwt.decode(test_token, options={"verify_signature": False})
        print(f"📋 Token解码内容:")
        for key, value in decoded.items():
            print(f"   {key}: {value}")
    except Exception as e:
        print(f"❌ Token解码失败: {e}")

def check_user_in_db():
    """检查数据库中的用户信息"""
    print("\n🔍 数据库用户信息检查...")

    import asyncio
    async def check_db():
        from app.services.user_service import user_service

        user = await user_service.get_user_by_username("user3")
        if user:
            print(f"✅ 用户名: {user.username}")
            print(f"✅ 邮箱: {user.email}")
            print(f"✅ 是否为管理员: {user.is_admin}")
            print(f"✅ 用户ID: {user.id}")

            # 检查模型是否有vip_level属性
            if hasattr(user, 'vip_level'):
                print(f"✅ VIP等级: {user.vip_level}")
            else:
                print("⚠️ 用户模型没有vip_level属性")

            # 模拟API响应
            api_response = {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "is_admin": user.is_admin,
                "roles": ["admin"] if user.is_admin else ["user"],
            }
            print(f"\n📋 模拟API响应:")
            for key, value in api_response.items():
                print(f"   {key}: {value}")
        else:
            print("❌ user3用户不存在")

    asyncio.run(check_db())

def check_auth_service():
    """检查认证服务"""
    print("\n🔍 认证服务检查...")

    try:
        # 尝试验证token
        test_token = AuthService.create_access_token(sub="user3")
        token_data = AuthService.verify_token(test_token)

        if token_data:
            print(f"✅ Token验证成功")
            print(f"   用户名: {token_data.sub}")
            print(f"   过期时间: {datetime.datetime.fromtimestamp(token_data.exp)}")
        else:
            print("❌ Token验证失败")

    except Exception as e:
        print(f"❌ 认证服务错误: {e}")

def main():
    print("🎯 用户权限调试工具")
    print("=" * 50)

    check_auth_service()
    debug_jwt_token()
    check_user_in_db()

    print("\n📋 调试建议:")
    print("1. 检查浏览器localStorage中的用户信息")
    print("2. 检查浏览器Network标签中的API响应")
    print("3. 清除浏览器缓存和localStorage后重新测试")
    print("4. 检查前端authStore的初始化逻辑")

if __name__ == "__main__":
    main()