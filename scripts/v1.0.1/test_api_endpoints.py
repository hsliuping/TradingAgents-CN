"""
测试提示词模板系统API端点

测试内容：
1. 获取所有模板
2. 获取特定Agent的模板
3. 获取有效模板（用户优先、系统兜底）
4. 获取所有偏好
5. 创建用户模板配置
"""

import requests
import json
from typing import Optional

# API基础URL
BASE_URL = "http://127.0.0.1:8000/api/v1"

def print_section(title: str):
    """打印分隔线"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def print_result(response: requests.Response):
    """打印响应结果"""
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        try:
            data = response.json()
            print(f"响应数据: {json.dumps(data, ensure_ascii=False, indent=2)}")
        except:
            print(f"响应文本: {response.text}")
    else:
        print(f"错误: {response.text}")

def test_get_all_templates():
    """测试1: 获取所有模板"""
    print_section("测试1: 获取所有模板")
    
    url = f"{BASE_URL}/templates"
    print(f"请求: GET {url}")
    
    response = requests.get(url)
    print_result(response)
    
    if response.status_code == 200:
        data = response.json()
        if data.get("code") == 200:
            templates = data.get("data", [])
            print(f"\n✅ 成功获取 {len(templates)} 个模板")
            
            # 统计模板类型
            system_count = sum(1 for t in templates if t.get("is_system"))
            user_count = len(templates) - system_count
            print(f"   - 系统模板: {system_count} 个")
            print(f"   - 用户模板: {user_count} 个")
            
            # 显示前3个模板的基本信息
            print("\n前3个模板:")
            for i, template in enumerate(templates[:3], 1):
                print(f"   {i}. {template.get('agent_type')}/{template.get('agent_name')} "
                      f"(偏好: {template.get('preference_type')}, "
                      f"系统: {template.get('is_system')}, "
                      f"状态: {template.get('status')})")

def test_get_agent_templates():
    """测试2: 获取特定Agent的模板"""
    print_section("测试2: 获取特定Agent的模板")
    
    agent_type = "analysts"
    agent_name = "fundamentals_analyst"
    
    url = f"{BASE_URL}/templates/agent/{agent_type}/{agent_name}"
    print(f"请求: GET {url}")
    
    response = requests.get(url)
    print_result(response)
    
    if response.status_code == 200:
        data = response.json()
        if data.get("code") == 200:
            templates = data.get("data", [])
            print(f"\n✅ 成功获取 {agent_type}/{agent_name} 的 {len(templates)} 个模板")
            
            for template in templates:
                print(f"   - 偏好: {template.get('preference_type')}, "
                      f"版本: {template.get('version')}, "
                      f"状态: {template.get('status')}")

def test_get_effective_template():
    """测试3: 获取有效模板（用户优先、系统兜底）"""
    print_section("测试3: 获取有效模板")
    
    # 测试参数
    params = {
        "user_id": "test_user_001",
        "agent_type": "analysts",
        "agent_name": "fundamentals_analyst",
        "preference_id": "aggressive"
    }
    
    url = f"{BASE_URL}/user-template-configs/effective-template"
    print(f"请求: GET {url}")
    print(f"参数: {params}")
    
    response = requests.get(url, params=params)
    print_result(response)
    
    if response.status_code == 200:
        data = response.json()
        if data.get("code") == 200:
            template_data = data.get("data")
            if template_data:
                print(f"\n✅ 成功获取有效模板")
                print(f"   - 来源: {template_data.get('source')}")
                print(f"   - 模板ID: {template_data.get('template_id')}")
                print(f"   - 版本: {template_data.get('version')}")
                
                # 显示内容预览
                content = template_data.get("content", {})
                system_prompt = content.get("system_prompt", "")
                if system_prompt:
                    preview = system_prompt[:200] + "..." if len(system_prompt) > 200 else system_prompt
                    print(f"   - 系统提示词预览: {preview}")
            else:
                print("\n⚠️ 未找到有效模板")

def test_get_all_preferences():
    """测试4: 获取所有偏好"""
    print_section("测试4: 获取所有偏好")
    
    url = f"{BASE_URL}/preferences"
    print(f"请求: GET {url}")
    
    response = requests.get(url)
    print_result(response)
    
    if response.status_code == 200:
        data = response.json()
        if data.get("code") == 200:
            preferences = data.get("data", [])
            print(f"\n✅ 成功获取 {len(preferences)} 个偏好")
            
            for pref in preferences:
                print(f"   - {pref.get('preference_id')}: {pref.get('name')} "
                      f"(风险: {pref.get('risk_level')}, "
                      f"速度: {pref.get('decision_speed')})")

def test_get_template_history():
    """测试5: 获取模板历史"""
    print_section("测试5: 获取模板历史")
    
    # 先获取一个模板ID
    templates_response = requests.get(f"{BASE_URL}/templates")
    if templates_response.status_code == 200:
        templates_data = templates_response.json()
        if templates_data.get("code") == 200:
            templates = templates_data.get("data", [])
            if templates:
                template_id = templates[0].get("id")
                
                url = f"{BASE_URL}/template-history/template/{template_id}"
                print(f"请求: GET {url}")
                
                response = requests.get(url)
                print_result(response)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("code") == 200:
                        history = data.get("data", [])
                        print(f"\n✅ 成功获取模板历史 {len(history)} 条记录")

def main():
    """运行所有测试"""
    print("\n" + "🚀" * 40)
    print("  提示词模板系统API端点测试")
    print("🚀" * 40)
    
    try:
        # 测试服务是否可用
        response = requests.get(f"{BASE_URL.replace('/api/v1', '')}/health", timeout=5)
        print(f"\n✅ 服务可用: {response.status_code}")
    except Exception as e:
        print(f"\n❌ 服务不可用: {e}")
        print("请先启动服务: .\\env\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000")
        return
    
    # 运行测试
    test_get_all_templates()
    test_get_agent_templates()
    test_get_effective_template()
    test_get_all_preferences()
    test_get_template_history()
    
    print("\n" + "✅" * 40)
    print("  所有测试完成")
    print("✅" * 40 + "\n")

if __name__ == "__main__":
    main()

