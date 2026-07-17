#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
导出演示数据库到 install 目录（供打包脚本使用）

直接调用后端 app.services.database.backups.export_data 函数，
不依赖 HTTP 服务运行，只需 MongoDB 可连接。

用法:
    python scripts/deployment/export_database.py
    python scripts/deployment/export_database.py --output-dir /custom/path
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path

# 设置项目根目录到 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 加载 .env 环境变量
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

# 需要导出的集合列表（系统运行必需的配置和预置数据）
COLLECTIONS = [
    # 系统配置
    "system_configs",
    "platform_configs",
    "llm_providers",
    "model_catalog",
    "smtp_config",
    "datasource_groupings",
    "market_categories",
    "stock_industry_mappings",
    "mcp_server_configs",
    "sync_status",
    # 用户/认证
    "users",
    "user_tags",
    # Agent/工作流
    "workflow_definitions",
    "workflows",
    "agent_configs",
    "agent_io_definitions",
    "agent_specs",
    "agent_versions",
    "tool_configs",
    "tool_agent_bindings",
    "agent_workflow_bindings",
    "skills",
    "custom_tools",
    "external_skills",
    # 模板/预设
    "prompt_templates",
    "report_templates",
    "screening_presets",
    "industry_analysis_profiles",
    "user_template_configs",
    # 交易系统
    "trading_systems",
    "trading_system_versions",
    "paper_accounts",
    "paper_market_rules",
    # 定时任务
    "scheduled_analysis_configs",
    "scheduler_metadata",
    # 自选股
    "watchlist_groups",
]


async def run_export(output_dir: str, test_mode: bool = False) -> str:
    """调用后端导出函数，返回最终 JSON 文件路径。

    Args:
        output_dir: 输出目录
        test_mode: 测试模式，生成带日期的文件（不覆盖稳定版）
    """
    from app.core.database import init_database, close_database
    from app.services.database.backups import export_data

    # 初始化数据库连接
    print("  正在初始化数据库连接...")
    await init_database()
    print("  ✅ 数据库连接已建立")

    # 临时导出目录
    temp_export_dir = os.path.join(output_dir, "_temp_export")
    os.makedirs(temp_export_dir, exist_ok=True)

    try:
        # 调用后端导出函数（生成 zip）
        print(f"  正在导出 {len(COLLECTIONS)} 个集合...")
        zip_path = await export_data(
            collections=COLLECTIONS,
            export_dir=temp_export_dir,
            format="json",
            sanitize=True,
        )
        print(f"  ✅ 导出完成: {os.path.basename(zip_path)}")

        # 解压 zip 获取 JSON 数据
        with zipfile.ZipFile(zip_path, "r") as zf:
            json_filename = zf.namelist()[0]
            data = json.loads(zf.read(json_filename))

        # 根据模式选择输出文件名
        if test_mode:
            # 测试模式：只生成带日期的文件（不覆盖稳定版）
            date_str = datetime.now().strftime("%Y-%m-%d")
            output_filename = f"database_export_config_{date_str}.json"
            output_path = os.path.join(output_dir, output_filename)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"  ✅ 已保存（测试版）: {output_filename}")
            print(f"  ℹ️  稳定版 database_export_config.json 未修改")
        else:
            # 正式模式：只生成稳定版（覆盖旧文件）
            output_filename = "database_export_config.json"
            output_path = os.path.join(output_dir, output_filename)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"  ✅ 已保存（正式版）: {output_filename}")

        # 输出统计
        export_data_content = data.get("data", {})
        print()
        print("  集合内容统计:")
        total_docs = 0
        for coll_name, docs in export_data_content.items():
            count = len(docs) if isinstance(docs, list) else 0
            total_docs += count
            print(f"    {coll_name}: {count} 条")
        print(f"  总计: {total_docs} 条记录, {len(export_data_content)} 个集合")

        return output_path

    finally:
        # 清理临时目录
        shutil.rmtree(temp_export_dir, ignore_errors=True)
        # 关闭数据库连接
        await close_database()


def main():
    parser = argparse.ArgumentParser(description="导出演示数据库到 install 目录")
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "install"),
        help="输出目录（默认: install/）",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="测试模式：生成带日期的文件（不覆盖稳定版）",
    )
    args = parser.parse_args()

    output_dir = os.path.abspath(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    mode_label = "测试" if args.test else "正式"
    print("=" * 70)
    print(f"  导出演示数据库到 install 目录（{mode_label}模式）")
    print("=" * 70)
    print()

    try:
        result_path = asyncio.run(run_export(output_dir, test_mode=args.test))
        print()
        print("=" * 70)
        print("  数据库导出完成!")
        print("=" * 70)
        print(f"  模式: {mode_label}")
        print(f"  输出目录: {output_dir}")
        print(f"  输出文件: {os.path.basename(result_path)}")
        print()
        return 0
    except Exception as e:
        print()
        print(f"  ❌ 导出失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
