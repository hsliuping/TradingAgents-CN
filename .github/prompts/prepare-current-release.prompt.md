---
description: "为当前仓库准备当前版本发布，自动识别上一个版本并输出发布阻塞项、所需文件修改和验证清单。"
name: "准备当前版本发布"
argument-hint: "可选填写版本范围或补充说明，例如：从 2.0.0 到 2.0.1，重点检查升级包和 migration。"
agent: "autoreleases"
---

为当前仓库准备当前版本发布。

要求：
1. 如果我没有明确给出版本范围，自动识别目标版本和上一个版本。
2. 扫描这个版本范围内的 git log 和变更文件。
3. 检查 VERSION、BUILD_INFO、releases/<目标版本>/manifest.json、releases/<目标版本>/upgrade_config.json、migrations、打包脚本、更新器脚本、启动脚本以及发布流程文档。
4. 如果仓库已采用 D:/release/<version>/revNNN/ 归档规则，检查归档目录是否完整、子版本号是否递增，以及 RELEASE_UPLOAD_INFO.md 是否记录了安装包和升级包字节数。
5. 先输出阻塞项，再输出需要修改的文件，然后输出升级包一致性、发布归档与上传物料、upgrade_config 覆盖情况、migration 审查、验证清单和最终结论。
6. 默认采用只读分析模式，除非我明确要求开始实施，否则不要直接修改文件。