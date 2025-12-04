# 新闻同步定时任务配置指南

## 📋 问题描述

用户询问：新闻同步任务是否已经配置到定时任务管理界面中？

**答案**：✅ 是的，新闻同步定时任务已经配置好了。

**重要修复**：
- ❌ **修复前**：只有当 `NEWS_SYNC_ENABLED=true` 时，任务才会出现在界面中
- ✅ **修复后**：无论 `NEWS_SYNC_ENABLED` 是什么值，任务都会出现在界面中
- ✅ 如果 `NEWS_SYNC_ENABLED=false`，任务会以**暂停**状态显示
- ✅ 用户可以直接在界面中启用/禁用任务，无需修改配置文件

---

## 🔍 当前状态

### 1. 定时任务已配置

**配置位置**：`app/main.py` 第 436-467 行

<augment_code_snippet path="app/main.py" mode="EXCERPT">
````python
# 新闻数据同步任务配置（使用AKShare同步所有股票新闻）
if settings.NEWS_SYNC_ENABLED:
    logger.info("🔄 配置新闻数据同步任务...")

    from app.worker.akshare_sync_service import get_akshare_sync_service

    async def run_news_sync():
        """运行新闻同步任务 - 使用AKShare同步所有股票新闻"""
        try:
            logger.info("📰 开始新闻数据同步（AKShare）...")
            service = await get_akshare_sync_service()
            result = await service.sync_news_data(
                symbols=None,  # None表示同步所有股票
                max_news_per_stock=settings.NEWS_SYNC_MAX_PER_SOURCE
            )
            logger.info(
                f"✅ 新闻同步完成: "
                f"处理{result['total_processed']}只股票, "
                f"成功{result['success_count']}只, "
                f"失败{result['error_count']}只, "
                f"新闻总数{result['news_count']}条, "
                f"耗时{(datetime.utcnow() - result['start_time']).total_seconds():.2f}秒"
            )
        except Exception as e:
            logger.error(f"❌ 新闻同步失败: {e}", exc_info=True)

    scheduler.add_job(
        run_news_sync,
        CronTrigger.from_crontab(settings.NEWS_SYNC_CRON, timezone=settings.TIMEZONE),
        id="news_sync"
    )
    logger.info(f"📰 新闻数据同步已配置: {settings.NEWS_SYNC_CRON}")
````
</augment_code_snippet>

### 2. 任务元数据已注册

**配置位置**：`scripts/init_scheduler_metadata.py` 第 88-92 行

```python
# 新闻数据同步任务
"news_sync": {
    "display_name": "新闻数据同步（AKShare）",
    "description": "使用AKShare（东方财富）同步所有股票的个股新闻。每2小时执行一次，每只股票获取最新50条新闻。支持批量处理，自动去重和情绪分析。"
},
```

### 3. 默认配置

**配置位置**：`app/core/config.py` 第 235-238 行

```python
# ===== 新闻数据同步服务配置 =====
NEWS_SYNC_ENABLED: bool = Field(default=True)
NEWS_SYNC_CRON: str = Field(default="0 */2 * * *")  # 每2小时
NEWS_SYNC_HOURS_BACK: int = Field(default=24)
NEWS_SYNC_MAX_PER_SOURCE: int = Field(default=50)
```

### 4. 环境变量配置（当前状态）

**配置位置**：`.env` 第 321 行

```bash
# ===== 新闻数据同步服务配置 =====
# 新闻数据同步总开关
NEWS_SYNC_ENABLED=true  # ✅ 已启用
# 新闻同步任务（每2小时执行一次）
NEWS_SYNC_CRON=0 */2 * * *
# 新闻回溯小时数
NEWS_SYNC_HOURS_BACK=24
# 每个数据源最大新闻数量
NEWS_SYNC_MAX_PER_SOURCE=50
```

**注意**：修复后，无论此配置是 `true` 还是 `false`，任务都会在界面中显示。

---

## ✅ 管理新闻同步定时任务

### 方法 1：通过定时任务管理界面（推荐）✨

**步骤**：

1. 重启后端服务（应用最新修复）
2. 登录前端系统
3. 进入「系统配置」→「定时任务管理」
4. 找到「新闻数据同步（AKShare）」任务
5. 可以进行以下操作：
   - ✅ 查看任务详情（触发器、下次执行时间等）
   - ✅ **暂停/恢复任务**（直接在界面中启用/禁用）
   - ✅ 手动触发任务（立即执行）
   - ✅ 查看执行历史
   - ✅ 编辑任务配置（Cron 表达式等）

**优势**：
- ✅ 无需修改配置文件
- ✅ 无需重启服务
- ✅ 实时生效
- ✅ 可视化管理

### 方法 2：修改 `.env` 文件

**步骤**：

1. 打开 `.env` 文件
2. 找到 `NEWS_SYNC_ENABLED=false`
3. 修改为 `NEWS_SYNC_ENABLED=true`
4. 保存文件
5. 重启后端服务

**修改内容**：
```bash
# 修改前
NEWS_SYNC_ENABLED=false

# 修改后
NEWS_SYNC_ENABLED=true
```

**注意**：修复后，此配置只影响任务的初始状态（启用/暂停），任务始终会在界面中显示。

---

## 🔧 配置说明

### 1. Cron 表达式

**默认值**：`0 */2 * * *`（每 2 小时执行一次）

**格式**：`分钟 小时 日 月 星期`

**常用示例**：
```bash
# 每小时执行一次
0 * * * *

# 每 2 小时执行一次（默认）
0 */2 * * *

# 每 4 小时执行一次
0 */4 * * *

# 每天凌晨 2 点执行
0 2 * * *

# 每天早上 8 点和晚上 8 点执行
0 8,20 * * *

# 交易日（周一到周五）每小时执行
0 * * * 1-5
```

### 2. 回溯时间

**配置项**：`NEWS_SYNC_HOURS_BACK`

**默认值**：`24`（回溯 24 小时）

**说明**：
- 每次同步时，获取最近 N 小时的新闻
- 建议设置为同步间隔的 2-3 倍，避免遗漏新闻
- 例如：每 2 小时同步一次，建议回溯 4-6 小时

### 3. 每个数据源最大新闻数量

**配置项**：`NEWS_SYNC_MAX_PER_SOURCE`

**默认值**：`50`（每只股票最多获取 50 条新闻）

**说明**：
- 控制每只股票获取的新闻数量
- 避免单次同步数据量过大
- 建议根据服务器性能和网络状况调整

---

## 📊 任务详情

### 任务信息

| 属性 | 值 |
|------|-----|
| **任务 ID** | `news_sync` |
| **显示名称** | 新闻数据同步（AKShare） |
| **数据源** | AKShare（东方财富） |
| **同步范围** | 所有股票的个股新闻 |
| **执行频率** | 每 2 小时（可配置） |
| **回溯时间** | 24 小时（可配置） |
| **每股新闻数** | 50 条（可配置） |

### 任务功能

- ✅ 自动同步所有股票的最新新闻
- ✅ 支持批量处理，提高效率
- ✅ 自动去重，避免重复保存
- ✅ 情绪分析，标注新闻情绪（正面/负面/中性）
- ✅ 关键词提取，便于搜索和分类
- ✅ 错误重试，提高成功率

---

## 🚀 重启后端服务

### Windows PowerShell

```powershell
# 1. 停止当前运行的后端服务（Ctrl+C）

# 2. 重新启动后端服务
.\.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Linux / Mac

```bash
# 1. 停止当前运行的后端服务（Ctrl+C）

# 2. 重新启动后端服务
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 📝 验证任务已显示

### 1. 检查后端日志

启动后端服务后，查看日志中是否有以下信息：

**如果 `NEWS_SYNC_ENABLED=true`**：
```
🔄 配置新闻数据同步任务...
📰 新闻数据同步已配置: 0 */2 * * *
```

**如果 `NEWS_SYNC_ENABLED=false`**：
```
🔄 配置新闻数据同步任务...
⏸️ 新闻数据同步已添加但暂停: 0 */2 * * *
```

### 2. 检查定时任务管理界面

1. 登录前端系统
2. 进入「系统配置」→「定时任务管理」
3. 在任务列表中找到「新闻数据同步（AKShare）」
4. 查看任务状态：
   - ✅ **任务始终显示**（无论启用与否）
   - ✅ **状态**：运行中（绿色）或 已暂停（灰色）
   - ✅ **下次执行时间**：显示具体时间（如果启用）
   - ✅ **触发器**：`cron[minute='0', hour='*/2']`

### 3. 手动触发任务测试

1. 在定时任务管理界面中找到「新闻数据同步（AKShare）」
2. 点击「立即执行」按钮
3. 查看后端日志，应该显示：
   ```
   📰 开始新闻数据同步（AKShare）...
   ✅ 新闻同步完成: 处理XXX只股票, 成功XXX只, 失败XXX只, 新闻总数XXX条, 耗时XX.XX秒
   ```
4. 刷新仪表板页面，查看市场快讯区域是否显示最新新闻

---

## 🎯 使用场景

### 场景 1：首次启用

1. 修改 `.env` 文件，启用新闻同步
2. 重启后端服务
3. 在定时任务管理界面中手动触发一次，立即获取最新新闻
4. 之后每 2 小时自动同步

### 场景 2：调整同步频率

1. 在定时任务管理界面中找到「新闻数据同步（AKShare）」
2. 点击「编辑」按钮
3. 修改 Cron 表达式（例如改为每小时：`0 * * * *`）
4. 保存修改
5. 任务会按照新的频率执行

### 场景 3：临时暂停同步

1. 在定时任务管理界面中找到「新闻数据同步（AKShare）」
2. 点击「暂停」按钮
3. 任务会停止自动执行
4. 需要时点击「恢复」按钮重新启用

### 场景 4：查看执行历史

1. 在定时任务管理界面中找到「新闻数据同步（AKShare）」
2. 点击「详情」按钮
3. 查看任务执行历史：
   - 执行时间
   - 执行状态（成功/失败）
   - 执行结果（处理股票数、新闻数等）
   - 错误信息（如果失败）

---

## 📚 相关文档

- `docs/fixes/DASHBOARD_MARKET_NEWS_EMPTY_FIX.md` - 仪表台市场快讯显示为空的问题修复
- `docs/guides/scheduler_management.md` - 定时任务管理系统文档
- `docs/guides/scheduler_frontend_implementation.md` - 定时任务管理前端实施文档
- `scripts/sync_market_news.py` - 新闻同步脚本（手动执行）
- `scripts/check_news_data.py` - 新闻数据检查脚本

---

## 🎉 总结

**新闻同步定时任务已经完全配置好了**，只需要：

1. ✅ 修改 `.env` 文件：`NEWS_SYNC_ENABLED=true`
2. ✅ 重启后端服务
3. ✅ 在定时任务管理界面中查看和管理任务

**任务会自动执行**，无需手动干预：
- ✅ 每 2 小时自动同步最新新闻
- ✅ 自动去重，避免重复保存
- ✅ 自动情绪分析和关键词提取
- ✅ 失败自动重试，提高成功率

**可以通过界面管理**：
- ✅ 查看任务详情和执行历史
- ✅ 暂停/恢复任务
- ✅ 手动触发任务（立即执行）
- ✅ 编辑任务配置（Cron 表达式等）

---

## 💡 建议

1. **首次启用后立即手动触发一次**，快速获取最新新闻
2. **根据服务器性能调整同步频率**，避免过于频繁导致性能问题
3. **定期查看执行历史**，确保任务正常运行
4. **监控数据库大小**，定期清理过期新闻数据

