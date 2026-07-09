# 时间与时区策略（存储与展示一致）

本文件说明 TradingAgents-CN 在后端与数据库的时间/时区处理策略，以及运维在直接查询数据库时的注意事项与示例。

## 目标与原则

- 存储与展示以同一“配置时区”进行，确保语义一致（例如中国区为 Asia/Shanghai, UTC+8）。
- 配置来源采用“三层优先级”：数据库系统设置 > 环境变量 > 默认值。
- 尽量减少“时区歧义”，保证跨模块一致性与可维护性。

## 配置来源与优先级

1) 系统设置（数据库）
- 键：`system_settings.app_timezone`（例如 `"Asia/Shanghai"`）
- 可在 Web 前端“系统设置”页面可视化编辑；保存后即时生效（缓存失效后立刻应用）。

2) 环境变量（.env / 进程环境）
- 键：`TIMEZONE`（例如 `TIMEZONE=Asia/Shanghai`）
- 当 DB 未配置或缓存尚未命中时作为回退；若设置了 ENV，某些元数据会将该项标记为来自环境变量（只读）。

3) 默认值
- 默认：`Asia/Shanghai`

> 实现参考：`app/utils/timezone.py` 使用 DB（provider cache）> ENV(settings.TIMEZONE) > 默认 的策略获取有效时区。

## 后端行为说明

- 时间生成：统一使用 `now_tz()` 返回“配置时区”的 tz-aware datetime
  - 模型默认时间（例如 created_at, updated_at）通过 `default_factory=now_tz` 赋值。
  - 服务层导出时间（例如 `exported_at`）使用 `now_tz().isoformat()`。
- 时间输出：API 对外序列化为 ISO 8601 字符串，包含偏移量（例如 `+08:00` 或 `Z`）。
- JWT 过期：内部使用 tz-aware datetime 生成过期时间；JWT 编码为数值时间戳，验证与当前 epoch 秒比较保持一致。
- 缓存与生效：更新系统设置后，后端会调用 `config_provider.invalidate()` 失效缓存；provider 层默认 TTL 约 60s（若未手动失效）。

涉及的关键文件（示例）：
- `app/utils/timezone.py`（get_tz_name/get_tz/now_tz/to_config_tz）
- `app/models/*.py`（默认时间统一为 `now_tz`）
- `app/services/config_service.py`（系统设置默认包含 `app_timezone`）
- `app/routers/config.py`（导出时间、保存设置、缓存失效）
- `app/services/auth_service.py`（JWT 过期时间）

## 前端行为说明

- 系统设置页面增加了“系统时区”字段（`app_timezone`），默认显示 `Asia/Shanghai`。
- 保存时遵循“仅提交可编辑项”的规则；来自环境或敏感项会被禁用编辑。
- 修改后影响“新写入”的时间戳，以及 API 对外展示的偏移量。

## 运维直查数据库（MongoDB）注意事项

MongoDB/BSON 内部以 UTC 存储 datetime。由于我们在应用层以“配置时区”生成和解释时间，运维直查时需注意查询条件的时区语义：

1) 在查询条件里显式使用带时区的日期字面量（mongosh）：

```javascript
// 查询【本地时区=Asia/Shanghai】的当天日志（示例）
const start = new Date("2025-09-27T00:00:00+08:00");
const end   = new Date("2025-09-28T00:00:00+08:00");
db.operation_logs.find({ timestamp: { $gte: start, $lt: end } }).limit(5);
```

2) 使用聚合管道在“显示层”转为本地时区：

```javascript
// 将 UTC 字段转换为本地字符串显示（Asia/Shanghai）
db.operation_logs.aggregate([
  { $project: {
      _id: 1,
      user: "$username",
      timestamp_local: {
        $dateToString: { date: "$timestamp", format: "%Y-%m-%d %H:%M:%S", timezone: "Asia/Shanghai" }
      },
      action: 1
  } }
]).limit(5);
```

Compass 小贴士：
- 可在 Aggregation 里使用 `timezone` 进行转换，结果面板直接显示本地时间。
- Compass 偏好中通常也有 “Display dates in local timezone” 选项，按需勾选。

> 若希望“零心智负担”，可建立 MongoDB 视图将 `timestamp` 投影为 `timestamp_local`（按配置时区），运维直接查视图即可。

## 常见问答（FAQ）

- 改了系统时区会影响历史数据吗？
  - 历史 BSON 中仍是 UTC 时间戳；我们在应用层按照“当前配置时区”解释与展示。索引与比较语义不变；仅展示与新写入按新时区生成/显示。

- 多环境（开发/测试/生产）怎么用不同的时区？
  - 使用各自的 DB `system_settings.app_timezone` 或通过环境变量 `TIMEZONE` 进行覆盖。

- API 返回的时间格式是什么？
  - ISO 8601，包含偏移量，例如：`2025-09-28T10:20:30+08:00` 或 `2025-09-28T02:20:30Z`。

- 我想验证是否生效？
  - 在前端“系统设置”修改 `系统时区` → 点击“保存设置”。
  - 调用配置导出接口（例如：`POST /api/config/export`）查看 `exported_at` 的偏移量是否变化。
  - 新增/更新实体（例如创建用户或更新配置）后，查看 `created_at/updated_at` 的偏移量。

## 运维建议

- 编写常用聚合片段并保存为 Compass 视图/收藏，统一展示本地时区字段。
- 如需批量导出或脚本化排障，建议使用内部脚本/工具（可选）对时间字段做统一转换（Asia/Shanghai）。

## 变更影响范围（摘要）

- 新增：`app/utils/timezone.py`
- 调整：`app/models/*`、`app/services/config_service.py`、`app/services/auth_service.py`、`app/routers/config.py`
- 前端：`frontend/src/views/Settings/ConfigManagement.vue` 新增 `app_timezone` 表单项

## 版本与兼容

- 适用：v0.1.16+（含本次“统一时区配置”改造）
- 向后兼容：未配置 DB `app_timezone` 时，使用环境变量 `TIMEZONE`，否则默认 `Asia/Shanghai`；不影响既有 API 协议。

---

如需扩展：
- 更多 IANA 时区下拉项与搜索
- 后端保存时区名合法性校验（无效值报错）
- 视图/脚本自动化（运维零心智负担）

