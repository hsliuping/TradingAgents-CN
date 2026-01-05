"""
测试 Session 管理功能

验证：
1. 登录后创建 session
2. 退出登录后 session 失效
3. 修改密码后所有 session 失效
4. Token 泄露后可以撤销
"""

import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.database import init_database, get_mongo_db
from app.services.auth_service import AuthService
from app.services.session_service import get_session_service
from app.services.user_service import user_service


async def test_session_management():
    """测试 Session 管理"""
    
    print("=" * 60)
    print("测试 Session 管理功能")
    print("=" * 60)
    
    # 初始化数据库
    await init_database()

    # 获取 session service（不需要传入 db，会自动使用同步连接）
    session_service = get_session_service()
    
    # 测试用户
    test_username = "testuser"
    test_password = "testpass123"
    
    # 1. 创建测试用户（如果不存在）
    print("\n1️⃣ 创建测试用户...")
    user = await user_service.get_user_by_username(test_username)
    if not user:
        from app.models.user import UserCreate
        user_data = UserCreate(
            username=test_username,
            email="test@example.com",
            password=test_password
        )
        user = await user_service.create_user(user_data)
        print(f"✅ 用户创建成功: {user.username}")
    else:
        print(f"✅ 用户已存在: {user.username}")
    
    # 2. 模拟登录，创建 session
    print("\n2️⃣ 模拟登录，创建 session...")
    session_id = session_service.create_session(
        user_id=str(user.id),
        ip_address="127.0.0.1",
        user_agent="Test Client",
        expires_in_seconds=3600
    )
    print(f"✅ Session 创建成功: {session_id[:16]}...")
    
    # 3. 生成 token（包含 session_id）
    print("\n3️⃣ 生成 JWT Token...")
    token = AuthService.create_access_token(sub=user.username, session_id=session_id)
    print(f"✅ Token 生成成功: {token[:50]}...")
    
    # 4. 验证 token 和 session
    print("\n4️⃣ 验证 Token 和 Session...")
    token_data = AuthService.verify_token(token)
    if token_data:
        print(f"✅ Token 验证成功: sub={token_data.sub}, session_id={token_data.session_id[:16]}...")
        
        session = session_service.verify_session(token_data.session_id)
        if session:
            print(f"✅ Session 验证成功: user_id={session.user_id}")
        else:
            print("❌ Session 验证失败")
    else:
        print("❌ Token 验证失败")
    
    # 5. 测试退出登录（撤销 session）
    print("\n5️⃣ 测试退出登录（撤销 session）...")
    success = session_service.revoke_session(session_id)
    if success:
        print(f"✅ Session 撤销成功")
        
        # 再次验证 session（应该失败）
        session = session_service.verify_session(session_id)
        if session:
            print("❌ Session 仍然有效（不应该）")
        else:
            print("✅ Session 已失效（正确）")
    else:
        print("❌ Session 撤销失败")
    
    # 6. 测试修改密码后撤销所有 session
    print("\n6️⃣ 测试修改密码后撤销所有 session...")
    
    # 创建多个 session
    session_ids = []
    for i in range(3):
        sid = session_service.create_session(
            user_id=str(user.id),
            ip_address=f"192.168.1.{i+1}",
            user_agent=f"Device {i+1}",
            expires_in_seconds=3600
        )
        session_ids.append(sid)
        print(f"  创建 Session {i+1}: {sid[:16]}...")
    
    # 撤销所有 session
    revoked_count = session_service.revoke_all_user_sessions(str(user.id))
    print(f"✅ 撤销了 {revoked_count} 个 session")
    
    # 验证所有 session 都已失效
    for i, sid in enumerate(session_ids):
        session = session_service.verify_session(sid)
        if session:
            print(f"❌ Session {i+1} 仍然有效（不应该）")
        else:
            print(f"✅ Session {i+1} 已失效（正确）")
    
    # 7. 测试获取用户的所有活跃 session
    print("\n7️⃣ 测试获取用户的所有活跃 session...")
    
    # 创建新的 session
    for i in range(2):
        session_service.create_session(
            user_id=str(user.id),
            ip_address=f"10.0.0.{i+1}",
            user_agent=f"Browser {i+1}",
            expires_in_seconds=3600
        )
    
    sessions = session_service.get_user_sessions(str(user.id))
    print(f"✅ 用户有 {len(sessions)} 个活跃 session:")
    for i, s in enumerate(sessions):
        print(f"  Session {i+1}: {s.session_id[:16]}..., IP: {s.ip_address}, UA: {s.user_agent}")
    
    print("\n" + "=" * 60)
    print("✅ 所有测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_session_management())

