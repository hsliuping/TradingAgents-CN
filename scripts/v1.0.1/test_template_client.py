"""
测试模板客户端 - 验证Agent能否从MongoDB获取提示词
"""

import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tradingagents.utils.template_client import get_agent_prompt, get_template_client, close_template_client


def print_section(title: str):
    """打印分隔线"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def test_get_template_client():
    """测试1: 获取模板客户端"""
    print_section("测试1: 获取模板客户端")
    
    try:
        client = get_template_client()
        print(f"✅ 模板客户端初始化成功")
        print(f"   - 数据库: {client.db_name}")
        print(f"   - 模板集合: {client.templates_collection.name}")
        print(f"   - 配置集合: {client.configs_collection.name}")
        
        # 统计模板数量
        template_count = client.templates_collection.count_documents({})
        system_count = client.templates_collection.count_documents({"is_system": True})
        user_count = template_count - system_count
        
        print(f"   - 总模板数: {template_count}")
        print(f"   - 系统模板: {system_count}")
        print(f"   - 用户模板: {user_count}")
        
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_get_effective_template():
    """测试2: 获取有效模板"""
    print_section("测试2: 获取有效模板")
    
    try:
        client = get_template_client()
        
        # 测试获取fundamentals_analyst的模板
        template_content = client.get_effective_template(
            agent_type="analysts",
            agent_name="fundamentals_analyst",
            preference_id="neutral"
        )
        
        if template_content:
            print(f"✅ 成功获取模板")
            print(f"   - 包含字段: {list(template_content.keys())}")
            
            # 显示system_prompt预览
            system_prompt = template_content.get("system_prompt", "")
            if system_prompt:
                preview = system_prompt[:200] + "..." if len(system_prompt) > 200 else system_prompt
                print(f"   - system_prompt预览: {preview}")
            
            return True
        else:
            print(f"❌ 未获取到模板")
            return False
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_format_template():
    """测试3: 格式化模板"""
    print_section("测试3: 格式化模板")
    
    try:
        client = get_template_client()
        
        # 获取模板
        template_content = client.get_effective_template(
            agent_type="analysts",
            agent_name="fundamentals_analyst",
            preference_id="neutral"
        )
        
        if not template_content:
            print(f"❌ 未获取到模板")
            return False
        
        # 格式化模板
        variables = {
            "ticker": "600519.SH",
            "company_name": "贵州茅台",
            "market_name": "A股",
            "current_date": datetime.now().strftime("%Y-%m-%d"),
            "start_date": "2024-01-01",
            "currency_name": "人民币",
            "currency_symbol": "¥",
            "tool_names": "get_stock_fundamentals_unified"
        }
        
        formatted = client.format_template(template_content, variables)
        
        print(f"✅ 模板格式化成功")
        print(f"   - 变量数量: {len(variables)}")
        print(f"   - 格式化后字段: {list(formatted.keys())}")
        
        # 检查变量是否被替换
        system_prompt = formatted.get("system_prompt", "")
        if "贵州茅台" in system_prompt and "600519.SH" in system_prompt:
            print(f"   - ✅ 变量替换成功")
        else:
            print(f"   - ⚠️ 变量可能未完全替换")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_get_agent_prompt():
    """测试4: 获取Agent提示词（便捷函数）"""
    print_section("测试4: 获取Agent提示词")
    
    try:
        variables = {
            "ticker": "000001.SZ",
            "company_name": "平安银行",
            "market_name": "A股",
            "current_date": datetime.now().strftime("%Y-%m-%d"),
            "start_date": "2024-01-01",
            "currency_name": "人民币",
            "currency_symbol": "¥",
            "tool_names": "get_stock_fundamentals_unified"
        }
        
        prompt = get_agent_prompt(
            agent_type="analysts",
            agent_name="fundamentals_analyst",
            variables=variables,
            preference_id="neutral",
            fallback_prompt="这是降级提示词"
        )
        
        print(f"✅ 成功获取提示词")
        print(f"   - 提示词长度: {len(prompt)} 字符")
        print(f"   - 包含公司名: {'平安银行' in prompt}")
        print(f"   - 包含股票代码: {'000001.SZ' in prompt}")
        
        # 显示提示词预览
        preview = prompt[:300] + "..." if len(prompt) > 300 else prompt
        print(f"\n提示词预览:")
        print("-" * 80)
        print(preview)
        print("-" * 80)
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "🚀" * 40)
    print("  模板客户端测试")
    print("🚀" * 40)
    
    results = []
    
    # 运行测试
    results.append(("获取模板客户端", test_get_template_client()))
    results.append(("获取有效模板", test_get_effective_template()))
    results.append(("格式化模板", test_format_template()))
    results.append(("获取Agent提示词", test_get_agent_prompt()))
    
    # 关闭连接
    close_template_client()
    
    # 打印测试结果
    print("\n" + "=" * 80)
    print("  测试结果汇总")
    print("=" * 80)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} - {test_name}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！")
    else:
        print(f"\n⚠️ {total - passed} 个测试失败")


if __name__ == "__main__":
    main()

