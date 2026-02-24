# 智能助手

## 📋 文档信息

| 项目 | 内容 |
|------|------|
| 版本 | v1.0 |
| 状态 | 已实现 |
| 日期 | 2026-02 |
| 目标 | Agent 自主编排模式，支持 ReAct 工具调用与规划分析（Plan-then-Execute） |

---

## 1. 概述

智能助手是 TradingAgents-CN 的对话式分析入口，支持两种模式：

- **快速对话（ReAct）**：助手逐步调用工具回答问题，适合轻量查询
- **深度分析（规划分析）**：先制定计划，并行执行多步骤，生成综合报告，适合复杂分析

---

## 2. 已实现能力

### 2.1 后端

| 模块 | 实现位置 | 说明 |
|------|----------|------|
| **API 路由** | `app/routers/intelligent_assistant.py` | 统一前缀 `/api/assistant` |
| **智能助手服务** | `app/services/intelligent_assistant_service.py` | ReAct 模式、LLM 配置、RAG 知识检索 |
| **规划分析服务** | `app/services/planned_analysis_service.py` | 种子流程匹配 → LLM 规划 → ReAct 回退 |
| **请求/响应模型** | `app/schemas/intelligent_assistant.py` | ChatRequest、ChatResponse、PlannedAnalysisResponse |

### 2.2 前端

| 模块 | 实现位置 | 说明 |
|------|----------|------|
| **助手页面** | `frontend/src/views/Assistant/index.vue` | 对话界面、模式切换（快速/深度） |
| **API** | `frontend/src/api/assistant.ts` | chat、planned-analysis、conversation |
| **侧边栏** | `SidebarMenu.vue` | 智能助手入口 |

---

## 3. API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/assistant/chat | 智能助手对话（ReAct 模式） |
| POST | /api/assistant/planned-analysis | 规划分析（Plan-then-Execute） |
| GET | /api/assistant/conversation | 获取会话历史 |
| DELETE | /api/assistant/conversation | 清空会话 |

---

## 4. 规划分析三级保障

| 级别 | 说明 |
|------|------|
| 1. 种子流程匹配 | 匹配预设种子流程（如单股分析、板块分析），执行固定工作流 |
| 2. LLM 自主规划 | 无匹配时，LLM 规划多步骤执行计划，并行执行 |
| 3. ReAct 回退 | 规划失败时，回退到 ReAct 模式逐步调用工具 |

---

## 5. 能力特性

- **RAG 知识检索**：从向量数据库获取金融知识片段注入系统提示词
- **工具自主选择**：根据 when_to_use 描述，LLM 自主选择最合适的工具
- **会话持久化**：对话历史持久化，支持下次进入查看
- **教练风格**：教方法、讲框架、用数据说话，不直接给投资建议

---

## 6. 配置

- LLM 配置：从数据库 system_configs 读取，支持 quick_analysis_model、deep_analysis_model、deep_reasoning_model
- **ASSISTANT_TIMEOUT_SECONDS**：整体超时（默认 120 秒）
