# 京东云 LLM 限速应对方案设计

## 📋 文档信息

| 项目 | 内容 |
|------|------|
| 版本 | v3.0 JD Cloud Edition |
| 分支 | `release/jdyun-v3.0` |
| 日期 | 2026-07-18 |
| 状态 | ✅ P0 已实施（方案2 + 方案3） |
| 关联文档 | [jdyun-edition-design.md](./jdyun-edition-design.md) |

---

## 1. 问题背景

京东云对 LLM 模型服务做了限速处理。在以下场景中，系统可能触发限速（HTTP 429），导致分析任务失败：

- **多股分析**：用户批量分析多只股票，多个分析任务并发执行
- **定时分析**：多个定时任务同时触发，或关注列表中多只股票同时分析
- **单股分析的内部并发**：一次分析涉及 12 个 Agent，产生 15-25 次 LLM 调用

京东云限速的具体参数（RPM/TPM）**暂不确定**，本方案先用保守值（30 RPM）兜底，后续获取实际参数后可动态调整。

---

## 2. 现状分析

### 2.1 单次分析的 LLM 调用规模

一次完整的单股分析涉及约 12 个 Agent：

| Agent 类别 | 数量 | LLM 调用次数 | 说明 |
|------------|------|-------------|------|
| 分析师（Market/Fundamentals/News/Social） | 4 | 4 次 | 并行执行 |
| 研究员（Bull/Bear/Manager） | 3 | 3 次 × 辩论轮数 | 辩论轮数默认 1，可配 1-3 |
| 风险分析师（Risky/Safe/Neutral/Judge） | 4 | 4 次 | 并行执行 |
| 交易员（Trader） | 1 | 1 次 | 最终决策 |
| **合计（1 轮辩论）** | **12** | **约 15-25 次** | 含工具调用可能更多 |

> 代码位置：[trading_graph.py:1269-1274](file:///c:/TradingAgentsCN/tradingagents/graph/trading_graph.py#L1269)

### 2.2 当前并发控制机制

| 场景 | 并发控制 | 默认值 | 代码位置 |
|------|----------|--------|----------|
| 批量分析 | `asyncio.Semaphore(max_concurrent)` | 3 只股票并行 | [unified_analysis_service.py:625](file:///c:/TradingAgentsCN/app/services/unified_analysis_service.py#L625) |
| 定时任务 Worker | `asyncio.Semaphore(max_concurrent_tasks)` | 3 个任务并行 | [analysis_worker.py:530](file:///c:/TradingAgentsCN/app/worker/analysis_worker.py#L530) |
| 队列用户并发限制 | `DEFAULT_USER_CONCURRENT_LIMIT` | 3 | [queue/keys.py:21](file:///c:/TradingAgentsCN/app/services/queue/keys.py#L21) |

### 2.3 峰值 LLM 请求量估算

```
3 个并发任务 × 每任务 15-25 次 LLM 调用 = 峰值 45-75 次并发请求
```

如果京东云限速为 30 RPM，当前配置下 **1 分钟内就会触发限速**。

### 2.4 现有的重试机制（不足）

| 机制 | 现状 | 问题 |
|------|------|------|
| ChatOpenAI max_retries | 使用 langchain 默认值（2 次） | [trading_graph.py:208](file:///c:/TradingAgentsCN/tradingagents/graph/trading_graph.py#L208) 未显式配置，重试次数不足 |
| 429 错误处理 | 无专门处理 | 全局搜索仅 `clawhub_skill_service.py` 有 429 处理，LLM 调用链路没有 |
| LLM 限速器 | 无 | [rate_limiter.py](file:///c:/TradingAgentsCN/app/core/rate_limiter.py) 仅针对数据源，LLM 调用无速率控制 |
| 指数退避 | 依赖 langchain 内置 | 默认退避策略可能不适合京东云的限速窗口 |

---

## 3. 解决方案设计

### 3.1 方案 1：LLM 级别限速器（主动控制）

**目标**：从源头控制 LLM 请求发送速率，避免触发 429

#### 3.1.1 新建 LLM 限速器

**文件**: `app/core/llm_rate_limiter.py`（新建）

```python
"""
LLM 速率限制器
用于控制 LLM API 调用频率，避免超过京东云等平台的限流限制
"""
import asyncio
import time
import logging
from collections import deque
from typing import Optional
from app.core.jdyun import is_jdyun_mode

logger = logging.getLogger(__name__)


class LLMRateLimiter:
    """
    LLM 专用速率限制器（滑动窗口算法）
    
    京东云模式下自动启用，控制每分钟 LLM 请求次数
    """
    
    def __init__(self, max_calls: int = 24, time_window: float = 60):
        """
        Args:
            max_calls: 时间窗口内最大调用次数（默认 24，即 30 RPM × 0.8 安全边际）
            time_window: 时间窗口大小（秒，默认 60）
        """
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = deque()
        self.lock = asyncio.Lock()
        self.total_calls = 0
        self.total_waits = 0
        self.total_wait_time = 0.0
        
    async def acquire(self):
        """获取调用许可，超限时自动等待"""
        async with self.lock:
            now = time.time()
            while self.calls and self.calls[0] <= now - self.time_window:
                self.calls.popleft()
            
            if len(self.calls) >= self.max_calls:
                oldest = self.calls[0]
                wait_time = oldest + self.time_window - now + 0.1
                if wait_time > 0:
                    self.total_waits += 1
                    self.total_wait_time += wait_time
                    logger.info(f"⏳ [LLM限速] 达到 {self.max_calls}次/{self.time_window}秒，等待 {wait_time:.1f}秒")
                    await asyncio.sleep(wait_time)
                    now = time.time()
                    while self.calls and self.calls[0] <= now - self.time_window:
                        self.calls.popleft()
            
            self.calls.append(now)
            self.total_calls += 1


# 全局单例
_llm_limiter: Optional[LLMRateLimiter] = None


def get_llm_rate_limiter() -> Optional[LLMRateLimiter]:
    """获取 LLM 限速器（仅京东云模式启用）"""
    global _llm_limiter
    if not is_jdyun_mode():
        return None
    if _llm_limiter is None:
        # 从环境变量读取配置，默认 24 RPM（30 RPM × 0.8 安全边际）
        import os
        max_rpm = int(os.getenv("JDYUN_LLM_MAX_RPM", "30"))
        max_calls = int(max_rpm * 0.8)  # 安全边际 80%
        _llm_limiter = LLMRateLimiter(max_calls=max_calls, time_window=60)
        logger.info(f"🔧 [LLM限速器] 已启用: {max_calls}次/60秒（原始限制 {max_rpm} RPM）")
    return _llm_limiter
```

#### 3.1.2 在 LLM 调用前注入限速

**文件**: `tradingagents/graph/trading_graph.py`（修改）

在 `create_llm_by_provider()` 返回的 ChatOpenAI 实例上包装限速逻辑：

```python
# 方式 A：使用 langchain 的 runnable middleware（推荐）
from langchain_core.runnables import RunnableLambda

def create_llm_by_provider(...):
    llm = ChatOpenAI(...)
    
    # 京东云模式：包装限速
    if is_jdyun_mode():
        limiter = get_llm_rate_limiter()
        if limiter:
            async def rate_limited_ainvoke(*args, **kwargs):
                await limiter.acquire()
                return await llm.ainvoke(*args, **kwargs)
            # 返回包装后的 LLM
            ...
    
    return llm
```

> **注意**：LangChain 的 ChatOpenAI 内部使用 httpx 连接池，直接包装 ainvoke 可能影响流式输出。需要评估是否使用 RunnableBinding 或自定义 BaseChatModel 子类。

### 3.2 方案 2：429 错误指数退避重试（被动兜底）

**目标**：当 LLM 调用触发 429 时，自动指数退避重试，确保不丢失请求

#### 3.2.1 增强 ChatOpenAI 重试参数

**文件**: `tradingagents/graph/trading_graph.py`（修改）

在所有 `ChatOpenAI()` 创建处增加 `max_retries` 参数：

```python
# 京东云模式：max_retries 提升到 8，增加重试次数
jdyun_max_retries = 8 if is_jdyun_mode() else 2

return ChatOpenAI(
    model=model,
    base_url=backend_url,
    api_key=api_key,
    temperature=temperature,
    max_tokens=max_tokens,
    timeout=timeout,
    max_retries=jdyun_max_retries,  # 🔧 新增：京东云模式提升重试次数
    **_extra
)
```

> **影响范围**：[trading_graph.py](file:///c:/TradingAgentsCN/tradingagents/graph/trading_graph.py) 中有约 11 处 `ChatOpenAI()` 调用，需要统一修改。建议提取为公共变量。

#### 3.2.2 自定义重试回调（可选增强）

LangChain 的 ChatOpenAI 内置重试使用固定间隔，可以通过 `retry_callback` 自定义指数退避：

```python
# 使用 langchain 的 retry_if_exception_type
from langchain_core.language_models.chat_models import BaseChatModel

# 京东云模式下的 ChatOpenAI 创建
def _create_jdyun_chat_openai(model, base_url, api_key, **kwargs):
    return ChatOpenAI(
        model=model,
        base_url=base_url,
        api_key=api_key,
        max_retries=8,  # 重试 8 次
        # langchain 内部已实现指数退避：1s, 2s, 4s, 8s, 16s, 32s, 64s, 128s
        **kwargs
    )
```

> **LangChain 重试机制说明**：langchain_openai 的 ChatOpenAI 使用 openai 库的内置重试，默认对 429/5xx 做指数退避，间隔为 `1s, 2s, 4s, 8s, ...`。设置 `max_retries=8` 后，最长可等待约 4 分钟。

### 3.3 方案 3：降低京东云模式并发数（减小压力）

**目标**：从任务调度层面降低并发，减少同时发起的 LLM 请求数

#### 3.3.1 批量分析并发降低

**文件**: `app/services/unified_analysis_service.py`（修改）

```python
async def analyze_batch(
    self,
    stock_codes: List[str],
    ...
    max_concurrent: int = 3,
) -> List[Dict[str, Any]]:
    # 🔧 京东云模式：降低并发数，避免 LLM 限速
    if is_jdyun_mode():
        max_concurrent = min(max_concurrent, 1)  # 京东云模式串行执行
        logger.info(f"🔧 [京东云模式] 批量分析并发数降为 {max_concurrent}")
    
    semaphore = asyncio.Semaphore(max_concurrent)
    ...
```

#### 3.3.2 定时任务 Worker 并发降低

**文件**: `app/worker/analysis_worker.py`（修改）

```python
# 在 start() 方法中读取配置后
self.max_concurrent_tasks = int(effective_settings.get("worker_max_concurrent_tasks", 3))

# 🔧 京东云模式：降低 Worker 并发数
if is_jdyun_mode():
    self.max_concurrent_tasks = min(self.max_concurrent_tasks, 1)
    logger.info(f"🔧 [京东云模式] Worker 并发数降为 {self.max_concurrent_tasks}")

self.semaphore = asyncio.Semaphore(self.max_concurrent_tasks)
```

#### 3.3.3 队列用户并发限制降低

**文件**: `app/services/queue_service.py`（修改）

```python
# 京东云模式：用户并发限制降为 1
if is_jdyun_mode():
    self.user_concurrent_limit = 1
    self.global_concurrent_limit = 1
else:
    self.user_concurrent_limit = DEFAULT_USER_CONCURRENT_LIMIT
    self.global_concurrent_limit = GLOBAL_CONCURRENT_LIMIT
```

### 3.4 方案 4：定时分析错峰执行（可选优化）

**目标**：定时分析多只股票时，股票之间增加间隔，避免连续触发 LLM 限速

#### 3.4.1 关注列表分析增加间隔

**文件**: `app/worker/watchlist_analysis_task.py`（修改）

```python
async def run_watchlist_analysis(stocks: List[str], ...):
    for i, stock in enumerate(stocks):
        result = await analyze_single(stock, ...)
        
        # 🔧 京东云模式：股票之间增加间隔
        if is_jdyun_mode() and i < len(stocks) - 1:
            interval = int(os.getenv("JDYUN_STOCK_INTERVAL_SECONDS", "10"))
            logger.info(f"⏳ [京东云模式] 股票分析间隔 {interval}秒...")
            await asyncio.sleep(interval)
```

---

## 4. 配置参数设计

通过环境变量配置京东云 LLM 限速参数，无需修改代码即可调整：

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `JDYUN_LLM_MAX_RPM` | `30` | 京东云 LLM 每分钟最大请求数（RPM） |
| `JDYUN_LLM_MAX_RETRIES` | `8` | LLM 调用最大重试次数 |
| `JDYUN_BATCH_MAX_CONCURRENT` | `1` | 京东云模式批量分析最大并发数 |
| `JDYUN_WORKER_MAX_CONCURRENT` | `1` | 京东云模式 Worker 最大并发任务数 |
| `JDYUN_STOCK_INTERVAL_SECONDS` | `10` | 定时分析股票间的间隔秒数 |

在 `.env.example` 中添加：

```bash
# 京东云 LLM 限速配置（可选，有默认值）
JDYUN_LLM_MAX_RPM=30
JDYUN_LLM_MAX_RETRIES=8
JDYUN_BATCH_MAX_CONCURRENT=1
JDYUN_WORKER_MAX_CONCURRENT=1
JDYUN_STOCK_INTERVAL_SECONDS=10
```

---

## 5. 推荐实施策略

### 5.1 推荐组合：方案 2 + 方案 3

| 优先级 | 方案 | 实施成本 | 效果 | 说明 |
|--------|------|----------|------|------|
| **P0** | 方案 2：429 重试 | 低 | 兜底所有 429 | 只需在 ChatOpenAI 创建处加 `max_retries=8` |
| **P0** | 方案 3：降并发 | 低 | 减小压力 | 3 个文件各加 2-3 行 if 判断 |
| **P1** | 方案 1：LLM 限速器 | 中 | 主动控制 | 需要新建限速器 + 包装 LLM 调用 |
| **P2** | 方案 4：错峰执行 | 低 | 定时分析优化 | 在循环中加 sleep |

**推荐理由**：
- 方案 2 + 方案 3 实施成本最低（约 1-2 小时），能解决 80% 的问题
- 方案 1 作为 P1 增强，待获取京东云实际限速参数后再实施
- 方案 4 作为可选优化，针对定时分析场景

### 5.2 实施工作量估算

| 方案 | 涉及文件 | 修改量 | 工作量 |
|------|----------|--------|--------|
| 方案 2 | `trading_graph.py` | 11 处 ChatOpenAI 调用加参数 | 0.5 天 |
| 方案 3 | `unified_analysis_service.py`、`analysis_worker.py`、`queue_service.py` | 3 个文件各加 if 判断 | 0.5 天 |
| 方案 1 | 新建 `llm_rate_limiter.py` + 修改 `trading_graph.py` | 新建文件 + 包装逻辑 | 1 天 |
| 方案 4 | `watchlist_analysis_task.py` | 循环中加 sleep | 0.5 天 |
| **P0 合计** | — | — | **1 天** |
| **P0+P1 合计** | — | — | **2 天** |

---

## 6. 风险分析

### 6.1 降并发导致分析速度变慢

**风险**：京东云模式批量分析并发降为 1，10 只股票的分析时间可能从 15 分钟增加到 30-50 分钟

**缓解措施**：
- 批量分析是用户手动触发，可接受较长时间
- 前端显示进度条，用户可感知进度
- 可通过 `JDYUN_BATCH_MAX_CONCURRENT` 环境变量调整

### 6.2 限速参数不匹配

**风险**：默认 30 RPM 可能与京东云实际限速不匹配

**缓解措施**：
- 所有参数通过环境变量配置，无需改代码即可调整
- 限速器有统计信息（total_waits、total_wait_time），可用于判断配置是否合理
- 首次部署后建议观察日志，根据 429 频率调整参数

### 6.3 重试导致超时

**风险**：max_retries=8 时，极端情况下单次 LLM 调用可能重试 8 次（最长约 4 分钟），导致分析任务超时

**缓解措施**：
- Worker 的 `visibility_timeout` 默认 30 分钟，足以覆盖重试时间
- 重试日志会输出到日志文件，便于排查
- 如频繁超时，可降低 `JDYUN_LLM_MAX_RETRIES`

---

## 7. 测试计划

### 7.1 单元测试

- LLM 限速器的 `acquire()` 逻辑测试
- 京东云模式检测和并发数降级测试
- 环境变量配置读取测试

### 7.2 集成测试

- 模拟 429 响应，验证重试逻辑
- 批量分析 3 只股票，验证串行执行
- 定时分析多只股票，验证错峰间隔

### 7.3 压力测试

- 使用京东云实际 API Key，批量分析 10 只股票
- 观察日志中的 429 频率和重试次数
- 根据测试结果调整限速参数

---

## 8. 实施清单

### Phase 1: P0 快速实施（方案 2 + 方案 3）✅ 已完成

- [x] `trading_graph.py`：所有 OpenAI 兼容 LLM 创建处增加 `max_retries` 参数（京东云模式 8，普通模式 2）—— 共 15 处（5 处 `create_llm_by_provider` + 10 处类初始化）
- [x] `unified_analysis_service.py`：`analyze_batch()` 京东云模式降并发为 1
- [x] `analysis_worker.py`：Worker 京东云模式降并发为 1（max_concurrent_tasks / user_concurrent_limit / global_concurrent_limit 三项）
- [x] `analysis_worker.py`：任务间添加间隔等待（`_process_task_with_semaphore` 中任务完成后等待 10 秒）
- [x] `app/core/jdyun.py`：添加 6 个限速配置读取函数
- [x] `.env.jdyun.example` + `docker-compose.jdyun.yml`：添加 5 个限速环境变量
- [x] 语法和导入验证全部通过

### Phase 2: P1 LLM 限速器（方案 1）⏳ 待实施

- [ ] 新建 `app/core/llm_rate_limiter.py`
- [ ] `trading_graph.py`：LLM 调用前注入限速器
- [ ] 限速器统计信息暴露到 `/api/config/jdyun/status` 端点

### Phase 3: P2 错峰执行（方案 4）⏳ 待实施

- [ ] `watchlist_analysis_task.py`：股票间增加间隔（P0 已在 Worker 层实现，此为任务层补充）
- [ ] 定时分析页面显示预估完成时间

---

## 9. 待确认事项

1. **京东云实际限速参数**：RPM/TPM 具体值？是否有突发流量配额？需要咨询京东云获取
2. **限速触发后的行为**：返回 429 还是排队等待？Retry-After 头是否有？
3. **不同模型的限速差异**：GLM-5 和 DeepSeek-V4-Flash 是否共享配额？
4. **Embedding 模型限速**：Qwen3-Embedding-8B 是否与对话模型共享限速配额？
5. **是否需要方案 1**：如果方案 2+3 足以应对限速，可以不实施方案 1（LLM 限速器）

---

## 10. P0 实施记录（2026-07-18）

### 10.1 修改文件清单

| 文件 | 修改内容 | 状态 |
|------|---------|------|
| `app/core/jdyun.py` | 添加 6 个限速配置读取函数 | ✅ |
| `tradingagents/graph/trading_graph.py` | 15 处 OpenAI 兼容 LLM 调用添加 `max_retries=get_llm_max_retries()` | ✅ |
| `app/services/unified_analysis_service.py` | `analyze_batch()` 京东云模式降并发为 1 | ✅ |
| `app/worker/analysis_worker.py` | Worker 降并发（3 项）+ 任务间间隔等待 | ✅ |
| `scripts/deployment/build_pro_package.ps1` | `.env.jdyun.example` 模板添加 5 个限速环境变量 | ✅ |
| `docker/docker-compose.jdyun.yml` | 添加 5 个限速环境变量 | ✅ |

### 10.2 限速配置参数

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `JDYUN_LLM_MAX_RETRIES` | 8 | LLM 调用最大重试次数（指数退避：1s,2s,4s,8s,16s,32s,64s,128s） |
| `JDYUN_LLM_MAX_RPM` | 30 | LLM 每分钟最大请求数（P1 限速器使用） |
| `JDYUN_BATCH_MAX_CONCURRENT` | 1 | 批量分析最大并发数 |
| `JDYUN_WORKER_MAX_CONCURRENT` | 1 | Worker 最大并发任务数 |
| `JDYUN_STOCK_INTERVAL_SECONDS` | 10 | 任务间间隔秒数 |

### 10.3 限速策略工作流程

```
京东云模式（JDYUN_MODE=true）下的分析任务执行流程：

1. 批量分析入口（unified_analysis_service.py）
   └─ max_concurrent > 1 时，降为 1（JDYUN_BATCH_MAX_CONCURRENT）

2. Worker 启动（analysis_worker.py）
   ├─ max_concurrent_tasks: 3 → 1（JDYUN_WORKER_MAX_CONCURRENT）
   ├─ user_concurrent_limit: 3 → 1
   └─ global_concurrent_limit: 3 → 1

3. LLM 创建（trading_graph.py）
   └─ ChatOpenAI(max_retries=8)（JDYUN_LLM_MAX_RETRIES）
      └─ 遇到 429 时指数退避重试：1s → 2s → 4s → 8s → 16s → 32s → 64s → 128s

4. 任务执行完成（analysis_worker.py）
   └─ 等待 10 秒后开始下一个任务（JDYUN_STOCK_INTERVAL_SECONDS）
```

### 10.4 验证结果

- ✅ 所有 4 个 Python 文件 `py_compile` 语法验证通过
- ✅ 所有 4 个 Python 文件 AST 解析通过
- ✅ `jdyun.py` 6 个限速函数导入和调用验证通过
- ✅ 京东云模式（JDYUN_MODE=true）下函数返回正确值
- ✅ 非京东云模式下函数返回默认值（不影响原有功能）
- ✅ `trading_graph.py` 中 15 处 max_retries 调用均为 OpenAI 兼容 LLM（ChatOpenAI / create_openai_compatible_llm），ChatAnthropic 等非 OpenAI 调用未修改
