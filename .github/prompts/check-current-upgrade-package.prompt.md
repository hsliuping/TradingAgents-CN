---
description: "检查当前版本升级包是否可以安全发布，自动识别版本并重点审查打包清单、更新器替换清单、upgrade_config 和 migration。"
name: "检查当前升级包是否可发"
argument-hint: "可选填写版本范围或补充说明，例如：重点检查升级包一致性和回滚风险。"
agent: "autoreleases"
---

检查当前仓库当前版本的升级包是否可以安全发布。

要求：
1. 如果我没有明确给出版本范围，自动识别目标版本和上一个版本。
2. 扫描这个版本范围内的 git log 和变更文件。
3. 重点检查 build_update_package.ps1、apply_update.ps1、start_all.ps1、apply_upgrade_config.py、manifest、upgrade_config、migration 和发布流程文档。
4. 如果仓库已采用 D:/release/<version>/revNNN/ 归档规则，检查升级包归档是否存在、字节数与 sha256 是否已写入 RELEASE_UPLOAD_INFO.md。
5. 重点输出升级包一致性、更新器替换一致性、发布归档与上传物料、upgrade_config 覆盖情况、migration 风险、回滚风险和最终结论。
6. 先输出阻塞项，再输出需要修改的文件和验证清单。
7. 默认采用只读分析模式，除非我明确要求开始实施，否则不要直接修改文件。