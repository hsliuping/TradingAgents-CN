---
description: "基于当前版本差异生成 upgrade_config、migration、manifest 和发布修复建议，默认只读分析。"
name: "生成升级建议"
argument-hint: "可选填写版本范围或补充说明，例如：从 2.0.0 到 2.0.1，重点生成 upgrade_config 和 migration 建议。"
agent: "autoreleases"
---

基于当前仓库版本差异生成升级建议。

要求：
1. 如果我没有明确给出版本范围，自动识别目标版本和上一个版本。
2. 扫描这个版本范围内的 git log 和变更文件。
3. 判断哪些变化需要补 manifest、upgrade_config、migration、打包脚本、归档脚本或发布说明。
4. 如果仓库已采用 D:/release/<version>/revNNN/ 归档规则，额外指出是否需要补发布归档目录、上传说明文档或字节数记录。
5. 输出时按以下优先级组织：阻塞项、需要修改的文件、发布归档与上传物料、upgrade_config 建议、migration 建议、验证清单、最终结论。
6. 对 upgrade_config 要指出建议检查的集合，例如 system_configs、prompt_templates、agent_configs、workflow_definitions、tool_configs。
7. 对 migration 要指出是否缺失、是否不完整、是否存在幂等性或字段复制风险。
8. 默认采用只读分析模式，除非我明确要求开始实施，否则不要直接修改文件。
9. 额外整理一份“目标版本相对上一版本的改进说明文档”草稿，供最终发布说明直接复用；如果我要求写入最终物料，则以单独 Markdown 文档形式输出。