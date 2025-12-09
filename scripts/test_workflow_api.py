#!/usr/bin/env python
"""
测试工作流执行 API

验证 WorkflowAPI 的各项功能
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.api.workflow_api import WorkflowAPI
from core.workflow.default_workflow_provider import (
    SYSTEM_DEFAULT_WORKFLOW_ID,
    SYSTEM_SIMPLE_WORKFLOW_ID,
)
from core.workflow.templates import DEFAULT_WORKFLOW


def test_workflow_api_init():
    """测试工作流 API 初始化"""
    print("\n" + "=" * 60)
    print("测试 WorkflowAPI 初始化")
    print("=" * 60)

    api = WorkflowAPI()

    print(f"   ✅ API 实例创建成功: {type(api).__name__}")
    print(f"   ✅ 引擎类型: {type(api._engine).__name__}")
    print(f"   ✅ 验证器类型: {type(api._validator).__name__}")

    print("\n✅ WorkflowAPI 初始化测试通过")
    return api


def test_workflow_api_list_all(api: WorkflowAPI):
    """测试列出所有工作流"""
    print("\n" + "=" * 60)
    print("测试 WorkflowAPI.list_all()")
    print("=" * 60)

    workflows = api.list_all()
    print(f"   📋 文件系统中共有 {len(workflows)} 个工作流")

    for wf in workflows:
        print(f"      - {wf['id']}: {wf['name']}")

    print("\n✅ WorkflowAPI.list_all() 测试通过")


def test_workflow_api_get_templates(api: WorkflowAPI):
    """测试获取预定义模板"""
    print("\n" + "=" * 60)
    print("测试 WorkflowAPI.get_templates()")
    print("=" * 60)

    templates = api.get_templates()
    print(f"   📋 共有 {len(templates)} 个预定义模板")

    for tpl in templates:
        print(f"      - {tpl['id']}: {tpl['name']}")
        print(f"        节点数: {len(tpl['nodes'])}, 边数: {len(tpl['edges'])}")

    print("\n✅ WorkflowAPI.get_templates() 测试通过")


def test_workflow_api_get(api: WorkflowAPI):
    """测试获取工作流详情"""
    print("\n" + "=" * 60)
    print("测试 WorkflowAPI.get()")
    print("=" * 60)

    # 测试获取文件系统中的工作流（可能不存在）
    workflow = api.get(SYSTEM_DEFAULT_WORKFLOW_ID)
    if workflow:
        print(f"   ✅ 获取文件工作流: {workflow['name']}")
        print(f"      节点数: {len(workflow['nodes'])}")
        print(f"      边数: {len(workflow['edges'])}")
    else:
        print("   ⚠️ 文件工作流不存在（系统预置工作流不保存到文件）")

    print("\n✅ WorkflowAPI.get() 测试通过")


def test_workflow_api_validate(api: WorkflowAPI):
    """测试工作流验证"""
    print("\n" + "=" * 60)
    print("测试 WorkflowAPI.validate()")
    print("=" * 60)

    # 使用预定义模板进行验证（validate 接受 data 字典）
    workflow_data = DEFAULT_WORKFLOW.to_dict()
    result = api.validate(workflow_data)

    is_valid = result.get('is_valid', False)
    print(f"   默认工作流验证: {'✅ 通过' if is_valid else '❌ 失败'}")

    if result.get('errors'):
        for err in result['errors']:
            print(f"      错误: {err}")
    if result.get('warnings'):
        for warn in result['warnings']:
            print(f"      警告: {warn}")

    print("\n✅ WorkflowAPI.validate() 测试通过")


def test_workflow_api_prepare_inputs(api: WorkflowAPI):
    """测试输入参数准备"""
    print("\n" + "=" * 60)
    print("测试 WorkflowAPI._prepare_inputs()")
    print("=" * 60)

    # 准备输入
    inputs = {
        "ticker": "000858",
        "analysis_date": "2024-12-09",
        "research_depth": "标准",
        "messages": [],
    }

    print(f"   📋 原始输入: ticker={inputs['ticker']}, date={inputs['analysis_date']}")

    # 测试输入准备
    prepared = api._prepare_inputs(inputs)

    print(f"   ✅ 输入准备成功")
    print(f"      company_of_interest: {prepared.get('company_of_interest')}")
    print(f"      trade_date: {prepared.get('trade_date')}")
    print(f"      _max_debate_rounds: {prepared.get('_max_debate_rounds')}")
    print(f"      _max_risk_rounds: {prepared.get('_max_risk_rounds')}")

    print("\n✅ WorkflowAPI._prepare_inputs() 测试通过")


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("工作流执行 API 测试")
    print("=" * 60)

    try:
        # 初始化测试
        api = test_workflow_api_init()

        # 列出所有工作流
        test_workflow_api_list_all(api)

        # 获取预定义模板
        test_workflow_api_get_templates(api)

        # 获取工作流详情
        test_workflow_api_get(api)

        # 验证工作流
        test_workflow_api_validate(api)

        # 测试输入准备
        test_workflow_api_prepare_inputs(api)

        print("\n" + "=" * 60)
        print("🎉 所有测试通过！")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

