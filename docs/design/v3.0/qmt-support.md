# QMT（迅投 MiniQMT）数据源支持

## 📋 文档信息

| 项目 | 内容 |
|------|------|
| 版本 | v1.0 |
| 状态 | 已实现 |
| 日期 | 2026-02 |
| 目标 | 支持迅投 QMT/MiniQMT 量化终端作为数据源，获取股票列表、行情、K 线、财务数据 |

---

## 1. 概述

QMT（迅投 MiniQMT）是券商量化终端，通过 `xtquant.xtdata` 连接本地 MiniQMT 客户端获取行情数据。作为多数据源之一，可与 Tushare、AKShare、BaoStock 等按优先级协同工作。

**前置条件**：
- MiniQMT 客户端需已启动（仅 Windows 支持）
- 获取行情数据不需要登录券商账户
- 新闻不支持，统一使用 AKShare 数据源

---

## 2. 已实现能力

| 模块 | 实现位置 | 说明 |
|------|----------|------|
| **数据源适配器** | `app/services/data_sources/qmt_adapter.py` | QMTAdapter，实现 DataSourceAdapter 接口 |
| **同步服务** | `app/worker/qmt_sync_service.py` | QMTSyncService，股票基础信息同步、实时行情同步 |
| **定时任务** | `app/main.py` | QMT 基础信息同步 CRON（默认工作日 7 点） |
| **配置** | `app/core/config.py` | QMT_UNIFIED_ENABLED、QMT_BASIC_INFO_SYNC_CRON |
| **数据源注册** | `app/services/data_sources/manager.py` | 与 Tushare、AKShare 等并列注册 |
| **多数据源同步** | `app/routers/stock_sync.py` | 支持 data_source=qmt 的基础数据同步 |

---

## 3. 数据能力

| 能力 | 说明 |
|------|------|
| 股票列表 | 通过沪深 A 股板块获取，支持北交所（8/4/92 开头 → .BJ） |
| 日线行情 | get_market_data_ex，需 MiniQMT 已下载历史数据 |
| 实时行情 | get_full_tick |
| 财务数据 | download_financial_data、get_financial_data |
| 新闻 | 不支持，由 DataSourceManager 回退到 AKShare |

---

## 4. 代码格式转换

- 6 位代码 ↔ xtdata 格式：`000001.SZ`、`600000.SH`、`920985.BJ`
- 北交所：43/83/87/89/92 开头 → `.BJ`

---

## 5. 启用方式

1. 安装 xtquant（随 MiniQMT 安装）
2. 启动 MiniQMT 客户端
3. 在 `.env` 设置 `QMT_UNIFIED_ENABLED=true`
4. 定时任务将按 CRON 执行；也可通过多数据源同步页面手动触发
