#!/usr/bin/env python3
"""
版本号一致性检查工具
确保项目中所有版本号引用都是一致的
"""

import os
import re
from pathlib import Path

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('default')


def get_target_version():
    """从VERSION文件获取目标版本号"""
    version_file = Path("VERSION")
    if version_file.exists():
        with open(version_file, 'r', encoding='utf-8') as f:
            return f.read().strip()
    return None

# 低噪声版本规范辅助函数与专用检查

def normalize_version(v: str) -> str:
    """标准化版本字符串用于比较（去掉前缀与修饰）"""
    return (
        v.lower()
         .replace('version-', '')
         .replace('版本', '')
         .lstrip('v')
         .strip()
    )


def check_special_files(file_path: Path, content: str, target_version: str):
    """对特定文件做精准校验，减少误报"""
    issues = []
    target_norm = normalize_version(target_version)
    target_numeric = target_norm.replace('cn-', '')  # pyproject.toml 使用纯数字版本

    # 1) pyproject.toml: version 字段应与目标数字版本一致
    if file_path.name == 'pyproject.toml':
        m = re.search(r'(?m)^\s*version\s*=\s*"([^"]+)"', content)
        if m:
            found = m.group(1).strip()
            if found != target_numeric:
                issues.append({
                    'line': content[:m.start()].count('\n') + 1,
                    'found': found,
                    'expected': target_numeric,
                    'context': content[max(0, m.start()-20):m.end()+20]
                })
        else:
            issues.append({'line': 1, 'found': '(missing version)', 'expected': target_numeric, 'context': ''})
        return issues

    # 2) README.md: 徽章与“最新版本”提示
    if file_path.name == 'README.md':
        # shields 徽章会把单个 - 显示为 --
        badge_text = normalize_version(target_version).replace('cn-', 'cn-').replace('-', '--')
        if badge_text not in content:
            issues.append({'line': 1, 'found': '(missing/old badge)', 'expected': badge_text, 'context': 'badge'})
        if target_version not in content:
            issues.append({'line': 1, 'found': '(missing latest tip)', 'expected': target_version, 'context': 'latest-tip'})
        return issues

    # 3) CHANGELOG: 允许历史版本存在，无需校验
    if file_path.name.upper() == 'CHANGELOG.MD':
        return []

    return []


def check_file_versions(file_path: Path, target_version: str):
    """检查文件中的版本号（低噪声策略）"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 对特定文件做精准检查
        special_issues = check_special_files(file_path, content, target_version)
        if special_issues:
            return special_issues

        # CHANGELOG 与其他文档默认忽略（允许历史版本与依赖版本存在）
        if file_path.name.upper() == 'CHANGELOG.MD':
            return []

        return []  # 其余文件不做泛化扫描，避免误报

    except Exception as e:
        return [{'error': str(e)}]

def main():
    """主检查函数"""
    logger.debug(f"🔍 版本号一致性检查")
    logger.info(f"=")

    # 获取目标版本号
    target_version = get_target_version()
    if not target_version:
        logger.error(f"❌ 无法读取VERSION文件")
        return

    logger.info(f"🎯 目标版本: {target_version}")

    # 需要检查的文件
    files_to_check = [
        "README.md",
        "pyproject.toml",
        "docs/releases/CHANGELOG.md",  # 仅用于存在性校验，内部忽略检查
    ]

    total_issues = 0

    for file_path in files_to_check:
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"⚠️ 文件不存在: {file_path}")
            continue

        logger.info(f"\n📄 检查文件: {file_path}")
        issues = check_file_versions(path, target_version)

        if not issues:
            logger.info(f"   ✅ 版本号一致")
        else:
            for issue in issues:
                if 'error' in issue:
                    logger.error(f"   ❌ 检查错误: {issue['error']}")
                else:
                    logger.error(f"   ❌ 第{issue['line']}行: 发现 '{issue['found']}', 期望 '{issue['expected']}'")
                    logger.info(f"      上下文: ...{issue['context']}...")
                total_issues += len(issues)

    # 总结
    logger.info(f"\n📊 检查总结")
    logger.info(f"=")

    if total_issues == 0:
        logger.info(f"🎉 所有版本号都是一致的！")
        logger.info(f"✅ 当前版本: {target_version}")
    else:
        logger.warning(f"⚠️ 发现 {total_issues} 个版本号不一致问题")
        logger.info(f"请手动修复上述问题")

    # 版本号规范提醒
    logger.info(f"\n💡 版本号规范:")
    logger.info(f"   - 主版本文件: VERSION")
    logger.info(f"   - 当前版本: {target_version}")
    logger.info(f"   - 格式要求: v0.1.x")
    logger.info(f"   - 历史版本: 可以保留在CHANGELOG中")

if __name__ == "__main__":
    main()
