#!/usr/bin/env python3
"""
对比 requirements.txt 和 pyproject.toml 中的依赖包
找出缺失的包
"""

import re
from pathlib import Path

def normalize_package_name(name):
    """标准化包名：小写，下划线转连字符"""
    return name.lower().replace('_', '-')

def extract_from_requirements(file_path):
    """从 requirements.txt 提取包名"""
    packages = {}
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # 跳过注释和空行
            if not line or line.startswith('#'):
                continue
            
            # 提取包名（去掉版本号和注释）
            match = re.match(r'^([a-zA-Z0-9_-]+)', line)
            if match:
                pkg_name = match.group(1)
                normalized = normalize_package_name(pkg_name)
                packages[normalized] = line
    
    return packages

def extract_from_pyproject(file_path):
    """从 pyproject.toml 提取包名"""
    packages = set()
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

        # 提取 dependencies 列表中的包
        in_dependencies = False
        bracket_count = 0
        for line in content.split('\n'):
            if 'dependencies = [' in line:
                in_dependencies = True
                bracket_count = 1
                continue

            if in_dependencies:
                # 计算括号
                bracket_count += line.count('[') - line.count(']')

                # 如果括号闭合，结束
                if bracket_count == 0:
                    break

                # 提取包名
                if '"' in line:
                    match = re.search(r'"([a-zA-Z0-9_-]+)', line)
                    if match:
                        pkg_name = match.group(1)
                        normalized = normalize_package_name(pkg_name)
                        packages.add(normalized)

    return packages

def main():
    # 文件路径
    req_file = Path('requirements.txt')
    toml_file = Path('pyproject.toml')
    
    # 提取包名
    req_packages = extract_from_requirements(req_file)
    toml_packages = extract_from_pyproject(toml_file)
    
    # 找出缺失的包
    missing = []
    for pkg, full_line in sorted(req_packages.items()):
        if pkg not in toml_packages:
            missing.append((pkg, full_line))
    
    # 输出结果
    print('=' * 70)
    print('requirements.txt 中有但 pyproject.toml 中缺失的包:')
    print('=' * 70)
    
    if missing:
        for pkg, full_line in missing:
            print(f'  {full_line}')
        print(f'\n总计缺失: {len(missing)} 个包')
    else:
        print('  ✅ 没有缺失的包')
    
    print('\n' + '=' * 70)
    print('pyproject.toml 中的包总数:', len(toml_packages))
    print('requirements.txt 中的包总数:', len(req_packages))
    print('=' * 70)

if __name__ == '__main__':
    main()

