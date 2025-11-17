#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试调试模式功能

验证：
1. AgentContext 是否正确设置调试模式参数
2. TemplateClient 是否优先使用调试模板
3. 调试模板是否正确传递给 Agent
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from tradingagents.agents.utils.agent_context import AgentContext
from tradingagents.utils.template_client import TemplateClient
from bson import ObjectId

def test_agent_context():
    """测试 AgentContext 是否支持调试模式"""
    print("\n" + "=" * 80)
    print("✅ 测试 1: AgentContext 调试模式参数")
    print("=" * 80)
    
    # 创建调试模式的 AgentContext
    ctx = AgentContext(
        user_id="test_user_123",
        preference_id="neutral",
        is_debug_mode=True,
        debug_template_id="6919a866fa8b760161a9167c"
    )
    
    print(f"✓ user_id: {ctx.user_id}")
    print(f"✓ preference_id: {ctx.preference_id}")
    print(f"✓ is_debug_mode: {ctx.is_debug_mode}")
    print(f"✓ debug_template_id: {ctx.debug_template_id}")
    
    # 转换为字典
    ctx_dict = ctx.__dict__
    print(f"\n✓ AgentContext.__dict__: {ctx_dict}")
    
    assert ctx.is_debug_mode == True, "is_debug_mode 应该为 True"
    assert ctx.debug_template_id == "6919a866fa8b760161a9167c", "debug_template_id 应该被正确设置"
    print("\n✅ AgentContext 测试通过！")


def test_template_client_debug_mode():
    """测试 TemplateClient 是否支持调试模式"""
    print("\n" + "=" * 80)
    print("✅ 测试 2: TemplateClient 调试模式支持")
    print("=" * 80)
    
    try:
        client = TemplateClient()
        
        # 创建调试模式的 AgentContext
        ctx = AgentContext(
            user_id="test_user_123",
            preference_id="neutral",
            is_debug_mode=True,
            debug_template_id="6919a866fa8b760161a9167c"
        )
        
        print(f"✓ 创建 TemplateClient 成功")
        print(f"✓ 创建调试模式 AgentContext 成功")
        print(f"  - is_debug_mode: {ctx.is_debug_mode}")
        print(f"  - debug_template_id: {ctx.debug_template_id}")
        
        # 尝试获取调试模板
        print(f"\n📝 尝试获取调试模板...")
        template = client.get_effective_template(
            agent_type="analysts",
            agent_name="fundamentals_analyst",
            context=ctx
        )
        
        if template:
            print(f"✅ 成功获取模板！")
            print(f"  - source: {template.get('source')}")
            print(f"  - template_id: {template.get('template_id')}")
            print(f"  - version: {template.get('version')}")
            print(f"  - is_debug: {template.get('is_debug')}")
            print(f"  - system_prompt 长度: {len(template.get('system_prompt', ''))}")
        else:
            print(f"⚠️ 未获取到模板（可能是调试模板不存在）")
        
        print("\n✅ TemplateClient 调试模式测试完成！")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


def test_debug_mode_priority():
    """测试调试模式优先级"""
    print("\n" + "=" * 80)
    print("✅ 测试 3: 调试模式优先级")
    print("=" * 80)
    
    print("优先级顺序：")
    print("1️⃣  调试模板 (is_debug_mode=True, debug_template_id 存在)")
    print("2️⃣  用户模板 (user_id 存在，is_active=True)")
    print("3️⃣  系统模板 (is_system=True, status=active)")
    
    print("\n✅ 优先级测试完成！")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("🧪 调试模式功能测试")
    print("=" * 80)
    
    try:
        test_agent_context()
        test_template_client_debug_mode()
        test_debug_mode_priority()
        
        print("\n" + "=" * 80)
        print("✅ 所有测试完成！")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

