# 待处理：httpx AsyncClient "Event loop is closed" 清理错误

## 状态
⏳ **待处理**（P0/P1/P2 验收后处理）

## 严重度
低 — 不影响分析结果，仅日志噪音 + 潜在连接泄漏

## 症状
```
RuntimeError: Event loop is closed
Task exception was never retrieved
future: <Task ... coro=<AsyncClient.aclose() ...>>
```
每次 LLM 同步调用后可能触发，分析过程中多次出现。

## 根因
`core/agents/base.py` 用 LangChain 同步 `.invoke()` 调 LLM（如 [base.py:831](file:///core/agents/base.py)）。
LangChain sync `.invoke()` 内部：创建事件循环 → 跑 async `.ainvoke()`（httpx AsyncClient 发请求）→ 关闭循环。
循环关闭后，httpx 后台连接清理任务仍在排队，`call_soon` 时发现循环已关 → RuntimeError。

与 [asyncio-thread-pool.md](file:///docs/06-knowledge/lessons-learned/asyncio-thread-pool.md) 记录的
"no current event loop" 是同一类问题的残留变体（那个已修复，这个未修复）。

## 触发位置
- `core/agents/base.py:831` `self._llm.invoke(current_messages)` 等同步 LLM 调用
- 日志见于分析师阶段（如"审慎情景研究员"），但所有 sync LLM 调用均可能触发

## 修复方案（待选）
| 方案 | 风险 | 效果 |
|------|------|------|
| A. asyncio 异常处理器过滤特定错误 | 极低 | 消除噪音，不治本 |
| B. WindowsSelectorEventLoopPolicy | 中 | 治本，可能影响子进程 |
| C. 注入共享 httpx 客户端 | 中高 | 治本，改 LLM 客户端创建 |
| D. 改用持久事件循环 + .ainvoke() | 高 | 治本，改动大 |

## 备注
- 2026-07-28 确认：与 P0/P1/P2 改动无关（P2 断言执行器为纯同步，不创建异步任务/httpx）
- 建议优先尝试方案 A（低风险 band-aid），若需治本再评估 C
