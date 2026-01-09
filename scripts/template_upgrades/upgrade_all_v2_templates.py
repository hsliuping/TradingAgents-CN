#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
一键升级所有 v2.0 Agent 模板

执行顺序：
1. 研究员 (bull_researcher_v2, bear_researcher_v2)
2. 风险分析师 (risky_analyst_v2, safe_analyst_v2, neutral_analyst_v2)
3. 管理员 (research_manager_v2, risk_manager_v2)
4. 交易员 (trader_v2)
5. 复盘分析师 (timing_analyst_v2, position_analyst_v2, emotion_analyst_v2, attribution_analyst_v2, review_manager_v2)
6. 持仓顾问 (pa_technical_v2, pa_fundamental_v2, pa_risk_v2, pa_advisor_v2)
"""

import os
import sys
import subprocess
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 升级脚本列表
UPGRADE_SCRIPTS = [
    ("研究员", "upgrade_researchers_v2.py"),
    ("风险分析师", "upgrade_risk_analysts_v2.py"),
    ("管理员", "upgrade_managers_v2.py"),
    ("交易员", "upgrade_trader_v2.py"),
    ("复盘分析师", "upgrade_reviewers_v2.py"),
    ("持仓顾问", "upgrade_position_advisors_v2.py"),
]


def run_upgrade_script(script_name: str, script_path: Path) -> bool:
    """运行单个升级脚本"""
    print("\n" + "=" * 80)
    print(f"🔧 升级 {script_name}")
    print("=" * 80)
    
    try:
        # 使用当前 Python 解释器运行脚本
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        
        # 打印输出
        if result.stdout:
            print(result.stdout)
        
        # 检查是否成功
        if result.returncode == 0:
            print(f"✅ {script_name} 升级成功")
            return True
        else:
            print(f"❌ {script_name} 升级失败")
            if result.stderr:
                print(f"错误信息: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ {script_name} 升级失败: {e}")
        return False


def main():
    """主函数"""
    print("=" * 80)
    print("🚀 开始升级所有 v2.0 Agent 模板")
    print("=" * 80)
    
    scripts_dir = Path(__file__).parent
    success_count = 0
    fail_count = 0
    
    for script_name, script_file in UPGRADE_SCRIPTS:
        script_path = scripts_dir / script_file
        
        if not script_path.exists():
            print(f"⚠️ 脚本不存在: {script_path}")
            fail_count += 1
            continue
        
        if run_upgrade_script(script_name, script_path):
            success_count += 1
        else:
            fail_count += 1
    
    # 总结
    print("\n" + "=" * 80)
    print("📊 升级总结")
    print("=" * 80)
    print(f"✅ 成功: {success_count} 个")
    print(f"❌ 失败: {fail_count} 个")
    print(f"📋 总计: {success_count + fail_count} 个")
    
    if fail_count == 0:
        print("\n🎉 所有模板升级成功！")
    else:
        print(f"\n⚠️ 有 {fail_count} 个模板升级失败，请检查错误信息")


if __name__ == "__main__":
    main()

