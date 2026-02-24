# 对话驱动回测服务

## 📋 文档信息

| 项目 | 内容 |
|------|------|
| 版本 | v1.0 |
| 状态 | 已实现 |
| 日期 | 2026-02 |
| 目标 | 用户通过自然语言描述投资策略想法 → AI 分析可行性 → 生成策略 → 执行回测 → 展示结果 |

---

## 1. 概述

对话驱动回测系统（Conversational Backtesting System）实现类似 OpenClaw/NexusTrade 的对话式策略回测功能。用户用自然语言描述策略想法，AI 分析可行性、生成结构化策略（Python 代码 + config），调用独立回测引擎执行，并支持迭代优化。

---

## 2. 架构

```
用户描述想法 → AI 分析可行性 → 用户确认 → 生成策略 → 执行回测 → 展示结果
                    ↓
             [策略迭代优化] 评估结果 → 优化策略 → 再次回测
```

---

## 3. 已实现能力

### 3.1 后端

| 模块 | 实现位置 | 说明 |
|------|----------|------|
| **API 路由** | `app/routers/backtest.py` | 统一前缀 `/api/backtest` |
| **业务服务** | `app/services/backtest_service.py` | 策略分析、生成、执行、会话管理 |
| **策略分析器** | `core/backtest/strategy_analyzer.py` | LLM 分析策略可行性 |
| **策略生成器** | `core/backtest/strategy_generator.py` | LLM 生成 Python 策略 + config |
| **结果评估器** | `core/backtest/result_evaluator.py` | 评估回测结果、生成优化建议 |
| **迭代优化器** | `core/backtest/iterative_optimizer.py` | 执行→评估→优化→再回测 |
| **引擎客户端** | `core/backtest/engine_client.py` | HTTP 调用独立回测服务 |
| **DSL 校验** | `core/backtest/dsl_validator.py`、`dsl_evaluator.py` | L2 语义校验、L3 执行校验与自修正 |

### 3.2 回测引擎（独立服务）

| 模块 | 实现位置 | 说明 |
|------|----------|------|
| **回测服务** | `backtest-service/main.py` | FastAPI，端口 8900 |
| **引擎** | Backtrader (GPLv3) | DSL 或 Python 策略执行 |
| **股票池** | `backtest-service/universe.py` | 指数/行业成分股、动态龙头（避免生存者偏差） |
| **Docker** | `docker-compose.yml` | `--profile backtest` 启动 |

### 3.3 前端

| 模块 | 实现位置 | 说明 |
|------|----------|------|
| **回测页面** | `frontend/src/views/Backtest/index.vue` | 新建回测、策略列表、会话管理 |
| **API** | `frontend/src/api/backtest.ts` | analyze、generate、run、optimize、evaluate |
| **侧边栏** | `SidebarMenu.vue` | 策略回测入口 |

---

## 4. API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/backtest/analyze | AI 分析策略可行性 |
| POST | /api/backtest/generate | 生成策略（Python 代码 + config） |
| POST | /api/backtest/run | 执行回测，保存会话 |
| POST | /api/backtest/optimize | 迭代优化（OpenClaw 风格） |
| POST | /api/backtest/evaluate | 评估现有回测结果 |
| POST | /api/backtest/generate-optimized | 基于评估生成优化策略 |
| GET | /api/backtest/sessions | 列出回测会话 |
| GET | /api/backtest/sessions/:id | 获取会话详情 |
| PATCH | /api/backtest/sessions/:id | 更新会话名称 |
| DELETE | /api/backtest/sessions/:id | 删除会话 |

---

## 5. 数据存储

- MongoDB 集合：`backtest_sessions`、`backtest_results`
- 会话按用户 ID 隔离

---

## 6. 配置

- `BACKTEST_SERVICE_URL`：回测服务地址（默认 http://localhost:8900）
- `BACKTEST_SERVICE_TIMEOUT`：超时秒数（默认 1200）
- 设置页：启用 L3 轻量回测校验（需回测服务已启动）
