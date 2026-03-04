# 统一通知架构设计

**版本**: v3.0
**最后更新**: 2026-03-05
**状态**: 设计已确定，已全部实现

---

## 1. 设计目标

任务完成（分析、预警等）后，系统需要通过多种渠道通知用户。  
**核心原则**：所有通知都走同一个入口，由统一的通知服务负责分发，业务层不关心渠道细节。

---

## 2. 整体架构

```
业务层（TaskAnalysisService 等）
        │
        │ create_and_publish(NotificationCreate)
        ▼
┌─────────────────────────────────────────────────┐
│          NotificationsService（统一入口）         │
│                                                 │
│  1. 写入 MongoDB notifications 集合              │
│  2. WebSocket → 前端站内铃铛（实时）              │
│  3. ChannelNotifier.dispatch() → 外部渠道        │
└──────────────┬──────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────┐
│              ChannelNotifier（渠道分发器）        │
│                                                 │
│  读取 user_channel_configs（用户开关配置）        │
│  过滤：已启用 + 订阅了此 event_type 的渠道        │
│                                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │   邮件   │ │飞书/钉钉 │ │  QQ IM（v3.0新增）│ │
│  │  Email   │ │企微 Bots │ │  GatewayRouter   │ │
│  └──────────┘ └──────────┘ └──────────────────┘ │
└─────────────────────────────────────────────────┘
```

---

## 3. 关键组件

### 3.1 NotificationsService（`app/services/notifications_service.py`）

统一通知入口，**所有业务层只调用此服务**，禁止直接调用邮件/IM 发送函数。

```python
await notifications_service.create_and_publish(NotificationCreate(
    user_id=str(task.user_id),
    type="analysis",
    title=f"✅ {stock_name}({symbol}) 分析完成",
    content=summary,
    link=f"/analysis/{task.task_id}",
    source="task_analysis",
    metadata={
        # 可选：若任务由 IM 触发，携带回调渠道
        "_im_channel": {"channel_type": "qq", "channel_id": "c2c:xxx"}
    }
))
```

**内部处理顺序**：
1. 写 MongoDB `notifications` 集合（持久化，供前端历史查询）
2. 通过 `websocket_notifications` 推送到前端（实时铃铛）
3. 调用 `ChannelNotifier.dispatch()` 分发外部渠道（fire-and-forget）

### 3.2 ChannelNotifier（`app/services/channel_notifier.py`）

读取用户的渠道订阅配置（`user_channel_configs` 集合），按事件类型过滤并并发发送。

**已支持渠道**：`email`、`feishu`、`dingtalk`、`wechat_work`

**v3.0 新增渠道**：`qq_im`
- 触发条件：`metadata._im_channel` 存在（即任务由 QQ 触发）
- 实现：调用 `GatewayRouter.send_im_notification(channel_type, channel_id, text)`
- 不需要用户在渠道配置里手动开启，有 `_im_channel` 就自动推送

### 3.3 GatewayRouter（`core/gateway/router.py`）

IM 平台的统一发送出口，支持所有已注册适配器（QQ、飞书等）。

```python
await gateway_router.send_im_notification(
    channel_type="qq",
    channel_id="c2c:0B6E41FDC8DFBDEB33E497A78013B0D0",
    text="✅ 贵州茅台(600519) 分析完成！\n..."
)
```

---

## 4. IM 渠道的上下文传播机制

QQ 用户触发分析任务时，需要把"回调给谁"的信息带入异步任务，流程如下：

```
QQ 用户发消息
    │
    ▼
GatewayRouter._invoke_assistant()
    │  set_current_im_channel("qq", "c2c:xxx")   ← ContextVar
    ▼
IntelligentAssistantService.chat()
    │
    ▼ (LLM 调用工具)
trigger_stock_analysis()
    │  get_current_im_channel()
    │  task_params["_im_channel"] = {"channel_type":"qq","channel_id":"c2c:xxx"}
    ▼
TaskAnalysisService（后台执行，数分钟后完成）
    │
    ▼
NotificationsService.create_and_publish(metadata={"_im_channel": ...})
    │
    ▼
ChannelNotifier → GatewayRouter → QQ 用户收到通知
```

**关键文件**：
- ContextVar 定义：`core/tools/context.py`（`_current_im_channel`）
- 上下文设置：`core/gateway/router.py`（`_invoke_assistant`）
- 上下文读取：`core/tools/implementations/assistant_ops/analysis_trigger.py`

---

## 5. 通知消息格式规范

### 站内通知（WebSocket → 前端）

```json
{
  "type": "notification",
  "data": {
    "id": "mongo_doc_id",
    "type": "analysis",
    "title": "✅ 贵州茅台(600519) 分析完成",
    "content": "综合评级：买入。...",
    "link": "/analysis/task_id",
    "source": "task_analysis",
    "status": "unread",
    "created_at": "2026-03-04T23:30:00+08:00"
  }
}
```

### QQ IM 通知（纯文本，限制 400 字）

```
✅ 贵州茅台(600519) 分析完成！
综合评级：买入。基本面优秀...（≤60字摘要）
耗时: 187秒
可回复「查看报告」获取完整分析。
```

---

## 6. 用户配置（user_channel_configs）

用户可在「个人设置 → 通知渠道」里开关各渠道及事件订阅。

| 渠道类型 | 配置方式 | 事件类型 |
|---------|---------|---------|
| `email` | 用户填写邮箱 | analysis_complete, alert, system |
| `feishu` | Webhook URL | analysis_complete, alert |
| `dingtalk` | Webhook URL | analysis_complete, alert |
| `wechat_work` | Webhook URL | analysis_complete, alert |
| `qq_im` | 自动（由触发场景决定） | analysis_complete |

`qq_im` 渠道无需用户手动配置，只要是通过 QQ 触发的任务，完成后自动推回原频道。

---

## 7. 实现状态

| 组件 | 状态 | 说明 |
|------|------|------|
| `NotificationsService.create_and_publish` | ✅ 已实现 | 站内 WebSocket + ChannelNotifier |
| `ChannelNotifier`（邮件/飞书/钉钉/企微） | ✅ 已实现 | 读 user_channel_configs 分发 |
| `GatewayRouter.send_im_notification` | ✅ 已实现 | 支持 QQ C2C / 群聊主动推送 |
| IM 上下文传播（ContextVar） | ✅ 已实现 | context.py + router.py + analysis_trigger.py |
| `ChannelNotifier` 新增 `qq_im` 分支 | ✅ 已实现 | 检查 metadata._im_channel 后调 GatewayRouter |
| `TaskAnalysisService` 改用统一入口 | ✅ 已实现 | 替换独立的 email/IM 通知方法，邮件（PDF附件）保留独立路径 |

---

## 8. 扩展新渠道

未来新增 IM 渠道（如微信、Telegram）只需两步：

1. 在 `core/gateway/adapters/` 下实现新的 `BaseGatewayAdapter` 子类并注册
2. 在 `ChannelNotifier` 里增加对应的 `channel_type` 分支

业务层代码（`TaskAnalysisService`、`NotificationsService`）无需修改。

---

## 9. 相关文件索引

| 文件 | 职责 |
|------|------|
| `app/services/notifications_service.py` | 统一通知入口 |
| `app/services/channel_notifier.py` | 外部渠道分发器 |
| `app/routers/websocket_notifications.py` | 前端 WebSocket 推送 |
| `core/gateway/router.py` | IM 平台发送出口 |
| `core/gateway/adapters/qq.py` | QQ Bot 适配器 |
| `core/tools/context.py` | IM 渠道 ContextVar |
| `app/models/notification.py` | 通知数据模型 |
| `app/models/channel_config.py` | 渠道配置模型 |
| `docs/design/professional-edition/email-notification-design.md` | 邮件通知详细设计 |

