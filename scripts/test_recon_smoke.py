#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""侦察工具冒烟测试 — 验证新增的 8 个 recon 工具能正常调用。"""

import sys, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def main():
    print("=" * 60)
    print("侦察工具冒烟测试")
    print("=" * 60)

    from core.tools.external.recon_tools import (
        list_available_collections,
        inspect_collection_schema,
        check_field_coverage,
        inspect_symbol_sample,
        describe_runtime_helper,
        list_runtime_functions,
        list_external_data_sources,
        list_mcp_tools,
        RECON_TOOLS,
    )

    # 1
    print("\n[1] list_available_collections")
    r = json.loads(list_available_collections())
    names = [x.get("collection", x.get("name", "?")) for x in r]
    print(f"  返回 {len(r)} 个集合: {names}")

    # 2
    print("\n[2] list_external_data_sources")
    r = json.loads(list_external_data_sources())
    print(f"  supported: {r.get('supported_sources', [])}")
    print(f"  configured: {r.get('configured_sources', [])}")

    # 3
    print("\n[3] list_mcp_tools")
    r = json.loads(list_mcp_tools())
    print(f"  MCP 工具数: {len(r)}")
    for t in r[:3]:
        print(f"    - {t.get('name')}: {t.get('description', '')[:60]}")

    # 4
    print("\n[4] list_runtime_functions('external_sources')")
    r = json.loads(list_runtime_functions("external_sources"))
    if isinstance(r, list):
        print(f"  函数数: {len(r)}")
        for f in r[:5]:
            print(f"    - {f.get('name')}: {f.get('summary', '')[:50]}")
    else:
        print(f"  结果: {r}")

    # 5
    print("\n[5] list_runtime_functions('data_access')")
    r = json.loads(list_runtime_functions("data_access"))
    if isinstance(r, list):
        print(f"  函数数: {len(r)}")
        for f in r[:5]:
            print(f"    - {f.get('name')}: {f.get('summary', '')[:50]}")

    # 6
    print("\n[6] describe_runtime_helper('data_access', 'get_stock_valuation_context')")
    r = json.loads(describe_runtime_helper("data_access", "get_stock_valuation_context"))
    if "error" in r:
        print(f"  (预期可能不存在) {r}")
    else:
        print(f"  签名: {r.get('signature', '')}")
        print(f"  文档: {r.get('docstring', '')[:100]}")

    # 7 RECON_TOOLS 完整性
    print("\n[7] RECON_TOOLS 列表")
    print(f"  工具数: {len(RECON_TOOLS)}")
    for t in RECON_TOOLS:
        print(f"    - {t.__name__}")

    assert len(RECON_TOOLS) == 8, f"预期 8 个工具，实际 {len(RECON_TOOLS)}"

    print("\n" + "=" * 60)
    print("✅ 冒烟测试全部通过")
    print("=" * 60)


if __name__ == "__main__":
    main()

