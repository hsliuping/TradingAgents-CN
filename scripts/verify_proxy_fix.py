#!/usr/bin/env python3
"""
验证代理配置修复

检查：
1. PROXY_ENABLED 字段是否存在于代码中
2. 前端是否添加了代理启用开关
3. 配置提供者是否允许编辑代理配置
4. Tushare API 测试是否临时禁用代理
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def check_file_content(file_path: Path, search_text: str) -> bool:
    """检查文件中是否包含指定文本"""
    try:
        content = file_path.read_text(encoding='utf-8')
        return search_text in content
    except Exception as e:
        print(f"   ❌ 读取文件失败: {e}")
        return False


def main():
    print("=" * 60)
    print("代理配置修复验证")
    print("=" * 60)

    all_passed = True

    # 1. 检查后端配置文件
    print("\n1️⃣ 检查后端配置文件 (app/core/config.py)...")
    config_file = project_root / 'app' / 'core' / 'config.py'

    if check_file_content(config_file, 'PROXY_ENABLED'):
        print("   ✅ PROXY_ENABLED 字段已添加")
    else:
        print("   ❌ PROXY_ENABLED 字段未找到")
        all_passed = False

    if check_file_content(config_file, 'Field(default=False)'):
        print("   ✅ 默认值设置为 False")
    else:
        print("   ⚠️ 默认值可能不是 False")

    if check_file_content(config_file, 'if settings.PROXY_ENABLED:'):
        print("   ✅ 代理启用逻辑已添加")
    else:
        print("   ❌ 代理启用逻辑未找到")
        all_passed = False

    # 2. 检查配置提供者
    print("\n2️⃣ 检查配置提供者 (app/services/config_provider.py)...")
    provider_file = project_root / 'app' / 'services' / 'config_provider.py'

    if check_file_content(provider_file, 'proxy_keys'):
        print("   ✅ 代理配置特殊处理已添加")
    else:
        print("   ❌ 代理配置特殊处理未找到")
        all_passed = False

    if check_file_content(provider_file, 'editable = True'):
        print("   ✅ 代理配置可编辑逻辑已添加")
    else:
        print("   ❌ 代理配置可编辑逻辑未找到")
        all_passed = False

    # 3. 检查 Tushare API 测试
    print("\n3️⃣ 检查 Tushare API 测试 (app/services/config_service.py)...")
    service_file = project_root / 'app' / 'services' / 'config_service.py'

    if check_file_content(service_file, 'original_http_proxy'):
        print("   ✅ 临时禁用代理逻辑已添加")
    else:
        print("   ❌ 临时禁用代理逻辑未找到")
        all_passed = False

    if check_file_content(service_file, "del os.environ['HTTP_PROXY']"):
        print("   ✅ 代理清除逻辑已添加")
    else:
        print("   ❌ 代理清除逻辑未找到")
        all_passed = False

    # 4. 检查前端界面
    print("\n4️⃣ 检查前端界面 (frontend/src/views/Settings/ConfigManagement.vue)...")
    frontend_file = project_root / 'frontend' / 'src' / 'views' / 'Settings' / 'ConfigManagement.vue'

    if check_file_content(frontend_file, 'proxy_enabled'):
        print("   ✅ proxy_enabled 字段已添加")
    else:
        print("   ❌ proxy_enabled 字段未找到")
        all_passed = False

    if check_file_content(frontend_file, 'el-switch'):
        print("   ✅ 代理启用开关已添加")
    else:
        print("   ❌ 代理启用开关未找到")
        all_passed = False

    if check_file_content(frontend_file, '启用代理'):
        print("   ✅ 前端标签已添加")
    else:
        print("   ❌ 前端标签未找到")
        all_passed = False

    # 5. 总结
    print("\n" + "=" * 60)
    print("验证结果")
    print("=" * 60)

    if all_passed:
        print("\n✅ 所有检查通过！代理配置修复已完成。")
        print("\n📝 下一步操作：")
        print("   1. 重启后端服务")
        print("   2. 访问 Web 界面 → 设置 → 配置管理 → 系统设置")
        print("   3. 在 '网络代理' 部分查看 '启用代理' 开关")
        print("   4. 根据需要开启或关闭代理")
    else:
        print("\n❌ 部分检查未通过，请检查上述错误。")

    print("\n" + "=" * 60)

    return all_passed


if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ 验证失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

