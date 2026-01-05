"""
测试混合认证方案

验证：
1. JWT Token 认证（API 调用）
2. Session Cookie 认证（Web 前端）
3. 退出登录时两种方式都失效
4. 修改密码时两种方式都失效
"""

import asyncio
import httpx
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


async def test_hybrid_auth():
    """测试混合认证"""
    
    print("=" * 60)
    print("测试混合认证方案")
    print("=" * 60)
    
    base_url = "http://localhost:8000"
    
    # 测试用户
    test_username = "admin"
    test_password = "admin123"
    
    async with httpx.AsyncClient(base_url=base_url, follow_redirects=True) as client:
        
        # 1. 测试登录（获取 JWT Token 和 Session Cookie）
        print("\n1️⃣ 测试登录...")
        login_response = await client.post(
            "/api/auth/login",
            json={"username": test_username, "password": test_password}
        )
        
        if login_response.status_code == 200:
            login_data = login_response.json()
            access_token = login_data["data"]["access_token"]
            print(f"✅ 登录成功")
            print(f"   JWT Token: {access_token[:50]}...")
            print(f"   Cookies: {client.cookies}")
        else:
            print(f"❌ 登录失败: {login_response.text}")
            return
        
        # 2. 测试 JWT Token 认证
        print("\n2️⃣ 测试 JWT Token 认证（API 调用）...")
        me_response = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        if me_response.status_code == 200:
            user_data = me_response.json()
            print(f"✅ JWT Token 认证成功: {user_data['data']['username']}")
        else:
            print(f"❌ JWT Token 认证失败: {me_response.text}")
        
        # 3. 测试 Session Cookie 认证（不带 Authorization header）
        print("\n3️⃣ 测试 Session Cookie 认证（Web 前端）...")
        me_response_cookie = await client.get("/api/auth/me")
        
        if me_response_cookie.status_code == 200:
            user_data = me_response_cookie.json()
            print(f"✅ Session Cookie 认证成功: {user_data['data']['username']}")
        else:
            print(f"❌ Session Cookie 认证失败: {me_response_cookie.text}")
        
        # 4. 测试退出登录（清除 Session Cookie）
        print("\n4️⃣ 测试退出登录（不带 Authorization header）...")
        logout_response = await client.post("/api/auth/logout")
        
        if logout_response.status_code == 200:
            print(f"✅ 退出登录成功")
            
            # 验证 Session Cookie 已失效
            me_response_after_logout = await client.get("/api/auth/me")
            if me_response_after_logout.status_code == 401:
                print(f"✅ Session Cookie 已失效（正确）")
            else:
                print(f"❌ Session Cookie 仍然有效（不应该）")
        else:
            print(f"❌ 退出登录失败: {logout_response.text}")
        
        # 5. 测试 JWT Token 是否仍然有效（应该失效）
        print("\n5️⃣ 测试 JWT Token 是否失效...")
        me_response_jwt = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        if me_response_jwt.status_code == 401:
            print(f"✅ JWT Token 已失效（正确）")
        else:
            print(f"❌ JWT Token 仍然有效（不应该）")
        
        # 6. 重新登录测试修改密码
        print("\n6️⃣ 重新登录测试修改密码...")
        login_response2 = await client.post(
            "/api/auth/login",
            json={"username": test_username, "password": test_password}
        )
        
        if login_response2.status_code == 200:
            login_data2 = login_response2.json()
            access_token2 = login_data2["data"]["access_token"]
            print(f"✅ 重新登录成功")
            
            # 修改密码（改成相同的密码）
            print("\n7️⃣ 测试修改密码...")
            change_pwd_response = await client.post(
                "/api/auth/change-password",
                json={
                    "old_password": test_password,
                    "new_password": test_password  # 改成相同的密码
                }
            )
            
            if change_pwd_response.status_code == 200:
                print(f"✅ 密码修改成功")
                
                # 验证 Session Cookie 已失效
                me_response_after_pwd = await client.get("/api/auth/me")
                if me_response_after_pwd.status_code == 401:
                    print(f"✅ Session Cookie 已失效（正确）")
                else:
                    print(f"❌ Session Cookie 仍然有效（不应该）")
                
                # 验证 JWT Token 已失效
                me_response_jwt2 = await client.get(
                    "/api/auth/me",
                    headers={"Authorization": f"Bearer {access_token2}"}
                )
                if me_response_jwt2.status_code == 401:
                    print(f"✅ JWT Token 已失效（正确）")
                else:
                    print(f"❌ JWT Token 仍然有效（不应该）")
            else:
                print(f"❌ 密码修改失败: {change_pwd_response.text}")
        else:
            print(f"❌ 重新登录失败: {login_response2.text}")
    
    print("\n" + "=" * 60)
    print("✅ 所有测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_hybrid_auth())

