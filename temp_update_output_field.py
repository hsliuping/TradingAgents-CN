#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""临时脚本：更新行业比较研究员的输出字段"""

from core.db import get_db

def main():
    db = get_db()
    
    # 更新 agent_workshop_specs 的 output_field
    result1 = db.agent_workshop_specs.update_one(
        {'spec_id': 'spec_nanobot_industry_comparison_researcher_v1'},
        {'$set': {'output_field': 'industry_comparison_report', 'updated_at': '2026-04-07T19:12:00+08:00'}}
    )
    print(f'Updated spec: matched={result1.matched_count}, modified={result1.modified_count}')
    
    # 更新 agent_workshop_versions 的 agent_metadata.output_field
    result2 = db.agent_workshop_versions.update_one(
        {'version_id': 'spec_nanobot_industry_comparison_researcher_v1_v1'},
        {'$set': {'agent_metadata.output_field': 'industry_comparison_report', 'updated_at': '2026-04-07T19:12:00+08:00'}}
    )
    print(f'Updated version: matched={result2.matched_count}, modified={result2.modified_count}')
    
    # 验证更新
    spec = db.agent_workshop_specs.find_one({'spec_id': 'spec_nanobot_industry_comparison_researcher_v1'})
    print(f'spec output_field: {spec.get("output_field")}')
    
    version = db.agent_workshop_versions.find_one({'version_id': 'spec_nanobot_industry_comparison_researcher_v1_v1'})
    print(f'version agent_metadata.output_field: {version.get("agent_metadata", {}).get("output_field")}')

if __name__ == '__main__':
    main()