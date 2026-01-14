"""
检查所有工具的参数定义情况

检查：
1. BUILTIN_TOOLS 中是否有参数定义
2. @register_tool 中是否传递了 parameters
3. 找出缺失参数定义的工具
"""

import sys
import ast
import re
from pathlib import Path
from typing import Dict, List, Tuple

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.tools.config import BUILTIN_TOOLS, ToolParameter

def extract_register_tool_info(file_path: Path) -> List[Dict]:
    """从文件中提取 @register_tool 装饰器的信息"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tools = []
        
        # 使用正则表达式查找 @register_tool 装饰器
        pattern = r'@register_tool\s*\(\s*([^)]+)\)'
        matches = re.finditer(pattern, content, re.DOTALL)
        
        for match in matches:
            decorator_content = match.group(1)
            
            # 提取 tool_id
            tool_id_match = re.search(r'tool_id\s*=\s*["\']([^"\']+)["\']', decorator_content)
            tool_id = tool_id_match.group(1) if tool_id_match else None
            
            # 检查是否有 parameters 参数
            has_parameters = 'parameters' in decorator_content or 'parameters=' in decorator_content
            
            # 提取函数签名中的参数
            # 查找下一个函数定义
            func_start = match.end()
            func_match = re.search(r'def\s+(\w+)\s*\(([^)]*)\)', content[func_start:func_start+500])
            
            func_params = []
            if func_match:
                params_str = func_match.group(2)
                # 简单解析参数（处理 Annotated 类型）
                param_pattern = r'(\w+)\s*:\s*[^=,]+(?:=\s*[^,]+)?'
                func_params = re.findall(param_pattern, params_str)
            
            tools.append({
                'tool_id': tool_id,
                'file': str(file_path.relative_to(project_root)),
                'has_parameters_in_decorator': has_parameters,
                'func_params': func_params,
            })
        
        return tools
    except Exception as e:
        print(f"❌ 解析文件失败 {file_path}: {e}")
        return []

def check_all_tools():
    """检查所有工具的参数定义"""
    print("=" * 80)
    print("检查所有工具的参数定义情况")
    print("=" * 80)
    
    # 1. 获取 BUILTIN_TOOLS 中的所有工具ID和参数
    builtin_tools = {}
    for tool_id, metadata in BUILTIN_TOOLS.items():
        builtin_tools[tool_id] = {
            'has_parameters': len(metadata.parameters) > 0,
            'parameters': metadata.parameters,
            'param_count': len(metadata.parameters),
        }
    
    print(f"\n📊 BUILTIN_TOOLS 中定义了 {len(builtin_tools)} 个工具")
    
    # 2. 查找所有使用 @register_tool 的文件
    tools_dir = project_root / "core" / "tools" / "implementations"
    registered_tools = {}
    
    if tools_dir.exists():
        for py_file in tools_dir.rglob("*.py"):
            if py_file.name.startswith("_"):
                continue
            
            tools = extract_register_tool_info(py_file)
            for tool in tools:
                if tool['tool_id']:
                    registered_tools[tool['tool_id']] = tool
    
    print(f"📊 找到 {len(registered_tools)} 个使用 @register_tool 注册的工具\n")
    
    # 3. 分析结果
    print("=" * 80)
    print("分析结果")
    print("=" * 80)
    
    # 分类统计
    categories = {
        'both_defined': [],  # 两者都有定义
        'only_builtin': [],  # 只在 BUILTIN_TOOLS 中定义
        'only_registered': [],  # 只在 @register_tool 中注册
        'missing_params': [],  # 缺少参数定义
        'params_mismatch': [],  # 参数数量不匹配
    }
    
    all_tool_ids = set(builtin_tools.keys()) | set(registered_tools.keys())
    
    for tool_id in sorted(all_tool_ids):
        in_builtin = tool_id in builtin_tools
        in_registered = tool_id in registered_tools
        
        builtin_info = builtin_tools.get(tool_id, {})
        registered_info = registered_tools.get(tool_id, {})
        
        builtin_params = builtin_info.get('param_count', 0)
        func_params = len(registered_info.get('func_params', []))
        has_params_in_decorator = registered_info.get('has_parameters_in_decorator', False)
        
        status = []
        if in_builtin:
            status.append("BUILTIN_TOOLS")
        if in_registered:
            status.append("@register_tool")
        
        # 判断分类
        if in_builtin and in_registered:
            if builtin_params > 0:
                categories['both_defined'].append(tool_id)
            elif func_params > 0:
                categories['missing_params'].append(tool_id)
        elif in_builtin:
            categories['only_builtin'].append(tool_id)
        elif in_registered:
            if func_params > 0 and not has_params_in_decorator:
                categories['missing_params'].append(tool_id)
            categories['only_registered'].append(tool_id)
        
        # 检查参数数量是否匹配
        if in_builtin and in_registered and builtin_params > 0:
            if builtin_params != func_params:
                categories['params_mismatch'].append({
                    'tool_id': tool_id,
                    'builtin_params': builtin_params,
                    'func_params': func_params,
                })
    
    # 打印统计
    print(f"\n✅ 两者都有定义且参数完整: {len(categories['both_defined'])} 个")
    print(f"📝 只在 BUILTIN_TOOLS 中定义: {len(categories['only_builtin'])} 个")
    print(f"🔧 只在 @register_tool 中注册: {len(categories['only_registered'])} 个")
    print(f"⚠️  缺少参数定义: {len(categories['missing_params'])} 个")
    print(f"❌ 参数数量不匹配: {len(categories['params_mismatch'])} 个")
    
    # 详细列出问题工具
    if categories['missing_params']:
        print("\n" + "=" * 80)
        print("⚠️  缺少参数定义的工具:")
        print("=" * 80)
        for tool_id in categories['missing_params']:
            print(f"\n🔴 {tool_id}")
            if tool_id in builtin_tools:
                print(f"   BUILTIN_TOOLS: 有定义，但参数数量: {builtin_tools[tool_id]['param_count']}")
            else:
                print(f"   BUILTIN_TOOLS: ❌ 未定义")
            
            if tool_id in registered_tools:
                info = registered_tools[tool_id]
                print(f"   @register_tool: ✅ 已注册")
                print(f"   文件: {info['file']}")
                print(f"   函数参数数量: {len(info['func_params'])}")
                print(f"   函数参数: {', '.join(info['func_params'])}")
                print(f"   装饰器中是否有parameters: {'✅' if info['has_parameters_in_decorator'] else '❌'}")
    
    if categories['params_mismatch']:
        print("\n" + "=" * 80)
        print("❌ 参数数量不匹配的工具:")
        print("=" * 80)
        for item in categories['params_mismatch']:
            tool_id = item['tool_id']
            print(f"\n🔴 {tool_id}")
            print(f"   BUILTIN_TOOLS 参数数量: {item['builtin_params']}")
            print(f"   函数参数数量: {item['func_params']}")
            if tool_id in registered_tools:
                info = registered_tools[tool_id]
                print(f"   函数参数: {', '.join(info['func_params'])}")
                if tool_id in builtin_tools:
                    params = builtin_tools[tool_id]['parameters']
                    print(f"   BUILTIN_TOOLS 参数: {[p.name for p in params]}")
    
    if categories['only_registered']:
        print("\n" + "=" * 80)
        print("🔧 只在 @register_tool 中注册的工具（建议添加到 BUILTIN_TOOLS）:")
        print("=" * 80)
        for tool_id in categories['only_registered']:
            info = registered_tools[tool_id]
            print(f"\n  {tool_id}")
            print(f"    文件: {info['file']}")
            print(f"    函数参数: {', '.join(info['func_params']) if info['func_params'] else '无'}")
            print(f"    装饰器中是否有parameters: {'✅' if info['has_parameters_in_decorator'] else '❌'}")
    
    print("\n" + "=" * 80)
    print("检查完成")
    print("=" * 80)

if __name__ == "__main__":
    check_all_tools()

