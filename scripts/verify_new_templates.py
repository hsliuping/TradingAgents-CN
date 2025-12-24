#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""验证新创建的模板"""

from pymongo import MongoClient

client = MongoClient('mongodb://admin:tradingagents123@localhost:27017/')
db = client['tradingagents']

templates = list(db.prompt_templates.find({
    'agent_type': 'reviewers_v2',
    'preference_type': 'neutral'
}))

print(f'找到 {len(templates)} 个模板:')
for t in templates:
    print(f'  - {t.get("agent_name")}: preference_type={t.get("preference_type")}')

