"""
批量为路由函数添加依赖注入参数
"""
import re

def add_dependency_to_function(file_path, service_param, service_type, depends_func):
    """为路由函数添加依赖注入参数"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 查找所有使用service的地方（但不在函数参数中）
    # 匹配 async def function_name(...): 后面使用 service_param 的函数
    pattern = r'(async def \w+\([^)]*\):)'
    
    def replace_func(match):
        func_def = match.group(1)
        # 检查是否已经有依赖注入
        if f'{service_param}:' in func_def or f'{service_param} =' in func_def:
            return func_def
        
        # 在函数参数末尾添加依赖注入
        if func_def.endswith('):'):
            # 检查是否有其他参数
            if '(' in func_def and func_def.index('(') + 1 < func_def.index(')'):
                # 有其他参数，添加逗号
                new_def = func_def[:-2] + f',\n    {service_param}: {service_type} = Depends({depends_func})\n):'
            else:
                # 没有其他参数
                new_def = func_def[:-2] + f'\n    {service_param}: {service_type} = Depends({depends_func})\n):'
            return new_def
        return func_def
    
    # 替换所有匹配的函数定义
    new_content = re.sub(pattern, replace_func, content)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"✅ 已更新 {file_path}")


if __name__ == "__main__":
    # 为 user_template_configs.py 添加依赖注入
    add_dependency_to_function(
        "app/routers/user_template_configs.py",
        "config_service",
        "UserTemplateConfigService",
        "get_config_service"
    )
    
    # 为 template_history.py 添加依赖注入
    add_dependency_to_function(
        "app/routers/template_history.py",
        "history_service",
        "TemplateHistoryService",
        "get_history_service"
    )
    
    print("✅ 所有文件已更新")

