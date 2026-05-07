# v2.1.0 Release Checklist

## Pre-release verification

- [ ] manifest.json 已审阅，确认 features、config_changes、env_changes 与最终发版范围一致
- [ ] upgrade_config.json 已补齐 2.0.1 -> 2.1.0 新增或变更的 providers、models、templates、bindings 和 workflows
- [ ] migrations/v2_1_0.py 已在预发布库执行，确认索引创建与升级记录链路正常
- [ ] BUILD_INFO 已重新生成，并验证版本接口对外返回 2.1.0
- [ ] 已执行 release_all.ps1 -Version "2.1.0"，并完成 D:/release/2.1.0/revNNN 归档
- [ ] 对外发布说明已确认，必要时补充用户视角简版更新说明

## Change summary (c43ea451..139cce1a)

- env_changes：新增 AIHUBMIX_API_KEY、AIHUBMIX_BASE_URL
- config_changes：模型选择协议升级为 provider::model，并依赖 default_provider 做歧义消解
- runtime：统一线程池同步服务修复 async cross-loop，市场分析补充最近 5 日成交量明细
- release：安装目录数据库导出快照刷新到 2026-04-30，便于安装与升级保持配置一致

## Build command

```powershell
.\scripts\deployment\release_all.ps1 -Version "2.1.0"
```