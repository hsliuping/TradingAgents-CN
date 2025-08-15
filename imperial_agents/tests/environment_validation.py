# imperial_agents/tests/environment_validation.py
"""
帝国AI环境验证脚本
验证所有必需组件是否正常工作
"""

import os
import sys
import importlib
from typing import Dict, List

def check_python_version() -> bool:
    """检查Python版本"""
    version = sys.version_info
    if version.major == 3 and version.minor >= 10:
        print(f"✅ Python版本: {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"❌ Python版本过低: {version.major}.{version.minor}.{version.micro} (需要3.10+)")
        return False

def check_required_packages() -> bool:
    """检查必需的Python包"""
    required_packages = [
        'streamlit', 'pandas', 'numpy', 'requests', 
        'pytdx', 'python-dotenv', 'openai'
    ]
    
    failed_packages = []
    for package in required_packages:
        try:
            importlib.import_module(package.replace('-', '_'))
            print(f"✅ {package}: 安装成功")
        except ImportError:
            print(f"❌ {package}: 未安装")
            failed_packages.append(package)
    
    return len(failed_packages) == 0

def check_api_keys() -> bool:
    """检查API密钥配置"""
    from dotenv import load_dotenv
    load_dotenv()
    
    api_keys = {
        'DASHSCOPE_API_KEY': os.getenv('DASHSCOPE_API_KEY'),
        'FINNHUB_API_KEY': os.getenv('FINNHUB_API_KEY')
    }
    
    all_configured = True
    for key, value in api_keys.items():
        if value and value != 'your_api_key_here' and len(value) > 10:
            print(f"✅ {key}: 已配置")
        else:
            print(f"❌ {key}: 未配置或无效")
            all_configured = False
    
    return all_configured

def check_data_sources() -> bool:
    """检查数据源连接"""
    try:
        # 测试通达信连接
        from pytdx.hq import TdxHq_API
        api = TdxHq_API()
        result = api.connect('119.147.212.81', 7709)
        if result:
            print("✅ 通达信API: 连接成功")
            api.disconnect()
            return True
        else:
            print("❌ 通达信API: 连接失败")
            return False
    except Exception as e:
        print(f"❌ 通达信API: 连接错误 - {str(e)}")
        return False

def check_trading_agents_import() -> bool:
    """检查TradingAgents模块导入"""
    try:
        # 尝试导入TradingAgents相关模块
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
        
        # 检查主要模块
        import web.app
        print("✅ TradingAgents Web模块: 导入成功")
        
        return True
    except Exception as e:
        print(f"❌ TradingAgents模块: 导入失败 - {str(e)}")
        return False

def check_imperial_directories() -> bool:
    """检查帝国扩展目录结构"""
    base_dir = os.path.join(os.path.dirname(__file__), '..')
    required_dirs = [
        'roles', 'core', 'wisdom', 'config', 'tests'
    ]
    
    all_exist = True
    for dir_name in required_dirs:
        dir_path = os.path.join(base_dir, dir_name)
        if os.path.exists(dir_path):
            print(f"✅ imperial_agents/{dir_name}: 目录存在")
        else:
            print(f"❌ imperial_agents/{dir_name}: 目录不存在")
            all_exist = False
    
    return all_exist

def run_full_validation() -> Dict[str, bool]:
    """运行完整的环境验证"""
    print("🚀 帝国AI环境验证开始...")
    print("=" * 60)
    
    results = {}
    
    print("\n1. Python环境检查:")
    results['python'] = check_python_version()
    
    print("\n2. 必需包检查:")
    results['packages'] = check_required_packages()
    
    print("\n3. API密钥检查:")
    results['api_keys'] = check_api_keys()
    
    print("\n4. 数据源检查:")
    results['data_sources'] = check_data_sources()
    
    print("\n5. TradingAgents检查:")
    results['trading_agents'] = check_trading_agents_import()
    
    print("\n6. 帝国目录检查:")
    results['imperial_dirs'] = check_imperial_directories()
    
    print("\n" + "=" * 60)
    print("📊 验证结果汇总:")
    
    all_passed = True
    critical_checks = ['python', 'packages', 'api_keys', 'trading_agents']
    
    for check, passed in results.items():
        status = "✅" if passed else "❌"
        critical = " (关键)" if check in critical_checks else " (可选)"
        print(f"{status} {check}{critical}")
        
        if check in critical_checks and not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 环境验证通过！帝国AI系统已准备就绪！")
        print("\n📋 下一步: 开始Phase 4G-G2 帝国角色适配层开发")
    else:
        print("⚠️  环境验证未完全通过，请检查上述问题")
        print("\n🔧 修复建议:")
        if not results.get('packages', True):
            print("   - 安装缺失的Python包: pip install [package_name]")
        if not results.get('api_keys', True):
            print("   - 检查.env文件中的API密钥配置")
        if not results.get('data_sources', True):
            print("   - 检查网络连接和防火墙设置")
    
    return results

if __name__ == "__main__":
    run_full_validation()