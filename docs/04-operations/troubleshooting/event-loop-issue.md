# Event Loop 问题成因与最终解决方案

## 结论

当前仓库里的 loop 问题不是一个单点 Bug，而是多种模式叠加形成的系统性问题。

过去“解决过”的大多数问题，本质上是：
- 针对某一个报错点做了局部补丁
- 但没有消除继续制造同类问题的底层模式
- 随着 v3.0 引入更多调度任务、智能助手、智能筛选、后台 worker、fire-and-forget 任务，这些模式更容易被重新触发

最终判断：
- 根因不是 Motor、Redis、APScheduler 某一个库单独不稳定
- 根因是异步资源生命周期管理不统一，跨 event loop、跨线程、跨 shutdown 边界复用 async 客户端对象

## 典型现象

常见报错包括：
- `Event loop is closed`
- `attached to a different loop`
- `Future attached to a different loop`
- 在 shutdown / restart / scheduler job / background task / request handler 中随机出现 MongoDB 或 Redis 读写失败

典型触发点：
- 请求接口正常处理中，读通知、配置、报告、任务状态时抛错
- APScheduler 定时任务执行数据库查询时抛错
- 启动或关闭阶段的 backfill / config sync / cache warmup 抛错
- fire-and-forget 任务在原请求结束后继续运行，访问旧 loop 上的 async 客户端抛错

## 为什么以前修过，还是会反复出现

### 1. 修的是“报错点”，不是“资源模型”

过去已经修过的点包括：
- TradingCalendarService 在 Redis loop mismatch 时回退到同步 Redis
- scheduler 某些路径要求用 `run_coroutine_threadsafe`
- config_bridge 的轻量配置同步改为同步 Mongo + `asyncio.to_thread`
- shutdown 时调度器先收尾再关数据库
- 数据库层为 Mongo 增加 loop 变化后的自动重建

这些修复都是对的，但它们解决的是局部调用链，不是全局资源模型。

### 2. 代码库里仍存在“缓存 async 对象”的模式

仓库中大量服务/worker 在 `__init__` 中直接做：
- `self.db = get_mongo_db()`
- `self._redis = get_redis_client()`

这在单 loop、单生命周期里通常没问题，但一旦：
- 服务实例跨重启存活
- APScheduler / worker / 线程池在别的 loop 里继续复用实例
- shutdown 后实例未立即释放

这些缓存的 `self.db` / `self._redis` 就会变成“绑在旧 loop 上的对象”。

### 3. 调度任务、后台任务、请求任务混用了同一套 async 资源

系统同时存在：
- FastAPI 请求处理
- APScheduler 定时任务
- `asyncio.create_task` / `ensure_future` 的后台任务
- 线程池 / worker 中的异步桥接

这些执行单元并不天然共享完全相同的 loop 生命周期。

如果它们都直接拿全局 async Mongo / async Redis 客户端，问题就会在以下场景爆发：
- 旧 loop 已关闭，但任务对象还活着
- 新 loop 接手执行，但代码里仍持有旧 async 客户端
- scheduler 非阻塞 shutdown 后，job 还在跑，数据库先关了

### 4. 仓库里同时存在两套 Redis 入口

当前既有：
- `app/core/database.py` 中的 async Redis 客户端
- `app/core/redis_client.py` 中的另一套 Redis 管理

这会带来两个问题：
- 资源生命周期不统一
- 调用方不清楚自己拿到的是哪一套 async Redis 客户端

统一资源入口之前，这类问题还会继续出现。

### 5. 某些线程/worker 路径绕过了公共数据库层

仓库里有一部分 worker/sync 服务会在本地自行创建：
- `AsyncIOMotorClient(settings.MONGO_URI)`

这意味着即便公共数据库层已经做了 loop-safe 保护，只要某些模块绕过它，仍然会继续产生新的 loop 问题。

## 根因分层

### A. 资源层根因

- 全局缓存 async Mongo / async Redis 客户端
- 客户端与 event loop 生命周期绑定，但仓库没有统一检测/重建
- 客户端对象被长期缓存并跨 loop 复用

### B. 服务层根因

- 服务实例在 `__init__` 中缓存 async db / redis 对象
- 单例服务被不同 loop / 线程 / scheduler job 反复使用
- fire-and-forget 任务脱离原始调用上下文后继续访问旧资源

### C. 生命周期根因

- shutdown 顺序不严谨
- scheduler job 仍在执行时数据库连接被关闭
- restart / reload / portable 运行模式下 loop 变化频率更高

### D. 架构层根因

- 轻量配置同步、缓存写入、进度刷新这类逻辑，本不必强依赖 async 客户端
- 但历史代码里很多场景默认直接用 Motor/async Redis
- 结果把不需要异步资源的链路也绑定到了 loop 生命周期上

## 最终解决方案

最终方案不是再继续“见一个报错修一个”，而是统一采用以下治理模型。

### 1. 统一 async 资源入口，禁止裸持有全局 async 客户端

统一要求：
- 所有 async Mongo 访问都经过 `app/core/database.py`
- 所有 async Redis 访问都经过 `app/core/database.py`
- 不允许业务层直接持有“裸的全局 AsyncIOMotorDatabase / Redis 客户端”作为长期成员

已经落地：
- `app/core/database.py` 已为 Mongo 增加 loop 绑定检测与自动重建
- `app/core/database.py` 已为 Redis 增加 loop 绑定检测与自动重建
- `get_mongo_db()` / `get_redis_client()` 已调整为 loop-safe 代理入口，降低缓存 `self.db` / `self._redis` 时的旧 loop 复用风险

### 2. 将“缓存对象”改为“缓存代理或工厂”，而不是缓存真实 async 连接

推荐模式：
- 可以缓存 `get_mongo_db()` 返回的代理对象
- 但不要缓存通过 `db["collection"]` 得到的真实 async collection 作为跨 loop 长生命周期成员
- 更推荐在方法内临时取 collection，而不是在构造器里固化

推荐写法：
- `db = get_mongo_db()` 然后在方法里使用
- `redis_client = get_redis_client()` 然后在方法里使用

避免写法：
- `self.collection = get_mongo_db()["xxx"]`
- `self.pubsub = get_redis_client().pubsub()` 后跨请求长期复用

### 3. 线程/worker/scheduler 的轻量读写优先改用同步客户端

适用场景：
- 配置同步
- cache warmup
- pricing/config 落盘
- 只读统计
- 线程池中的辅助写入

推荐方案：
- Mongo：`get_mongo_db_sync()` + `asyncio.to_thread()`
- Redis：`get_redis_sync_client()` + `asyncio.to_thread()`

原因：
- 这些场景的核心诉求是稳定，不是极致 async 吞吐
- 同步客户端天然与当前 event loop 解耦，更适合线程和边缘生命周期场景

已经落地：
- `app/core/config_bridge.py` 的定价配置同步已改为同步 Mongo + `asyncio.to_thread`
- TradingCalendarService 已在 Redis loop mismatch 时回退到同步 Redis

### 4. shutdown 顺序必须强约束

统一顺序：
1. 停止接收新请求/新任务
2. 等待 scheduler/后台任务收尾
3. 关闭线程池 worker
4. 关闭数据库连接
5. 退出进程

已经落地：
- `app/main.py` 中 scheduler shutdown 已改为等待收尾，再关闭数据库

### 5. 禁止在业务模块中随意新建 AsyncIOMotorClient

原则：
- 业务模块不得随意 `AsyncIOMotorClient(settings.MONGO_URI)`
- 如果确实处于线程/独立 loop 环境：
  - 要么使用同步 Mongo 客户端
  - 要么显式说明该 client 只在当前 loop 生命周期内使用，不能跨线程/跨 loop 缓存

治理要求：
- 清理 worker/sync service 中自行 new AsyncIOMotorClient 的路径
- 统一替换为公共数据库层或同步客户端方案

### 6. fire-and-forget 任务必须分级管理

允许继续使用 `asyncio.create_task()` 的前提：
- 任务明确绑定当前 loop 生命周期
- 任务内部不缓存旧 async db / redis 对象
- 应用 shutdown 时有统一收尾路径

否则应改为：
- 调度器任务
- worker 队列任务
- `run_coroutine_threadsafe` 提交到主 loop
- 或同步客户端 + 线程执行

### 7. 清理双入口 Redis 设计

最终目标：
- `app/core/database.py` 成为唯一推荐的 async Redis 入口
- `app/core/redis_client.py` 逐步降级为兼容层或废弃

原因：
- 多套 async Redis 生命周期管理会继续制造资源边界不一致
- loop 问题要收口，必须先收口入口

## 已实施项

当前已完成：
- Mongo async 客户端 loop 变化自动重建
- Redis async 客户端 loop 变化自动重建
- Mongo / Redis 代理入口，降低缓存旧对象的风险
- 新增 `bind_loop_safe_mongo_db()`，将 worker 中的数据库重绑统一收口到公共数据库层
- Tushare / BaoStock / AKShare 历史同步主链路已移除手写 `AsyncIOMotorClient` 重建逻辑，统一改走 loop-safe Mongo 代理
- 新增 `create_isolated_async_mongo_binding()`，为线程池和独立 loop 任务提供受控的隔离 Mongo 连接创建入口
- unified_thread_pool_sync_service 与 financial_data_sync_service 已改为通过公共 helper 创建隔离连接，避免各模块重复手写 Motor 初始化
- financial_data_sync_service 已补线程内异步 Mongo 客户端关闭，避免隔离连接泄漏
- `app/core/redis_client.py` 已收口为兼容层，不再维护独立 Redis 连接池与客户端状态
- `RedisService` 兼容封装已移除 Redis 客户端成员缓存，兼容层本身也不再长期持有 Redis 实例
- worker_app 与 analysis_worker 已移除重复的 `init_redis()/close_redis()` 调用，统一只依赖 `init_database()/close_database()` 管理 Redis 生命周期
- `TradeDateCacheService` 已移除自建/自缓存的同步与异步 Redis 客户端，统一改走数据库层同步/异步 Redis 入口
- 已完成对 request-scoped `pubsub` 与局部 `pipeline` 的细粒度审计；当前仅发现 `sse.py` 的请求级 PubSub 与 `RedisService.increment_with_ttl()` 的局部 pipeline，均未发现跨请求缓存或异常路径泄漏
- 已补 SSE 回归测试，验证 `task_progress_generator` 在生成器关闭时会执行 `unsubscribe + close`，确保 PubSub 连接按请求释放
- config_bridge 配置同步改为同步 Mongo + 线程包装
- TradingCalendarService 的 Redis fallback
- scheduler shutdown 等待收尾再关数据库

## 还需要继续完成的收尾项

### 高优先级

1. 扫描并整改所有 `self.db = get_mongo_db()` 的长生命周期服务
2. 继续扫描并整改剩余手动创建 `AsyncIOMotorClient` 的 worker/sync service，尤其是初始化类与少量遗留线程池辅助路径
3. 继续将 Redis 调用方迁移到数据库层统一入口，并逐步把 `app/core/redis_client.py` 压缩为纯兼容壳/常量壳
4. 继续保持对新增 request-scoped `pubsub` 与局部 `pipeline` 用法的代码审查约束，防止后续回归到跨请求/跨 loop 缓存模式

### 中优先级

1. 继续将 scheduler/worker 场景分流为两类 helper：共享 loop-safe 代理与隔离连接 helper
2. 为配置同步/状态刷新/进度更新这类轻量链路统一切到 sync client + `to_thread`
3. 为关键服务继续补 event loop mismatch 的单测或集成回归用例；SSE PubSub 释放路径已补首个回归测试

### 低优先级

1. 加代码规范文档，禁止新增裸 async client 缓存模式
2. 为数据库层 loop 重绑增加监控计数，观察是否还有频繁 loop 漂移

## 推荐落地策略

### 阶段 1：止血

目标：先让线上/本地 portable 模式不再频繁报 loop 错

执行：
- 保留当前数据库层重绑与代理方案
- 继续将轻量配置/缓存链路迁移到 sync client + `to_thread`
- 所有 scheduler shutdown 改为等待收尾

### 阶段 2：收口

目标：不再让业务层制造新的 loop 风险

执行：
- 清理 `self.db` / `self._redis` 的旧缓存模式
- 清理 worker 中手动 new `AsyncIOMotorClient`
- 统一 Redis 入口

### 阶段 3：治理

目标：把 loop 问题从“靠经验避免”变成“架构上不容易再犯”

执行：
- 引入共享 helper / 基类
- 加代码审查规则
- 增加回归测试与监控

## 最终标准

满足以下条件，才能认为 loop 问题真正收敛：

1. 请求链不再因为旧 async Mongo / Redis 客户端而报 `Event loop is closed`
2. scheduler job 在 shutdown/restart 时不再访问已关闭连接
3. 配置同步、cache warmup、辅助写入链路不再依赖 Motor loop 生命周期
4. worker / thread pool 中没有随意 new `AsyncIOMotorClient` 的历史残留
5. Redis async 入口统一，跨 loop 场景默认可降级到同步 Redis

## 一句话总结

以前的问题之所以“修过还反复出现”，不是因为以前修错了，而是因为以前修的是具体报错点；现在的最终方案是把 async Mongo / async Redis 从“裸对象共享”改成“loop-safe 资源入口 + 同步客户端兜底 + 生命周期强约束”，从根上收掉这类问题。