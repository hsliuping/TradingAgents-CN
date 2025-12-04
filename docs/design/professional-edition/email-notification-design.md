# 分析结果邮件通知功能设计

## 1. 功能概述

### 1.1 功能定位

| 项目 | 说明 |
|------|------|
| **功能名称** | 分析结果邮件通知 |
| **版本** | 专业版功能 |
| **目标用户** | 需要及时获取分析结果的付费用户 |
| **核心价值** | 不在电脑前也能第一时间收到分析结果 |

### 1.2 使用场景

```
┌─────────────────────────────────────────────────────────────────┐
│  场景1：定时分析完成通知                                         │
│  用户设置了每天9:30自动分析自选股                                 │
│  → 分析完成后自动发送邮件摘要                                    │
│  → 用户在手机上查看邮件，决定是否需要操作                         │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  场景2：重要信号预警                                             │
│  分析发现某只股票出现重大利好/利空                                │
│  → 立即发送预警邮件                                              │
│  → 用户收到后可快速决策                                          │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  场景3：批量分析汇总                                             │
│  用户批量分析了10只股票                                          │
│  → 发送一封汇总邮件，列出所有结果摘要                             │
│  → 用户可快速浏览，选择深入查看                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 与现有系统关系

```
现有通知系统 (notifications_service.py)
├── WebSocket实时推送  ── 用户在线时
├── MongoDB持久存储   ── 历史记录
└── 站内通知列表      ── 应用内查看

新增邮件通知 (email_service.py)    ✨
├── SMTP发送邮件      ── 用户离线也能收到
├── 邮件模板系统      ── 美观的HTML邮件
└── 发送队列          ── 异步处理，不阻塞分析
```

---

## 2. 系统架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        触发源                                    │
│  ├── 单股分析完成                                                │
│  ├── 批量分析完成                                                │
│  ├── 定时分析完成                                                │
│  └── 重要信号检测                                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    邮件通知服务                                   │
│  ├── 权限检查 (是否专业版用户)                                    │
│  ├── 用户偏好检查 (是否开启邮件通知)                              │
│  ├── 频率限制 (防止邮件轰炸)                                      │
│  └── 邮件构建 (选择模板、填充数据)                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    邮件发送队列                                   │
│  ├── Redis队列 (异步处理)                                        │
│  ├── 重试机制 (发送失败自动重试)                                  │
│  └── 发送记录 (MongoDB存储)                                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SMTP服务                                      │
│  ├── 云端SMTP (推荐: SendGrid/阿里云/腾讯云)                      │
│  └── 自建SMTP (可选)                                             │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 邮件类型

| 类型 | 触发条件 | 优先级 | 频率限制 |
|------|----------|--------|----------|
| **单股分析结果** | 单股分析完成 | 普通 | 同一股票1小时内不重复 |
| **批量分析汇总** | 批量分析完成 | 普通 | 无特殊限制 |
| **定时分析报告** | 定时任务完成 | 普通 | 按任务周期 |
| **重要信号预警** | 检测到重大信号 | 高 | 同一信号24小时内不重复 |
| **系统通知** | 试用到期、订阅续费等 | 低 | 每类通知3天内不重复 |

---

## 3. 数据模型设计

### 3.1 用户邮件偏好

```python
# app/models/user.py - 扩展UserPreferences

class EmailNotificationSettings(BaseModel):
    """邮件通知设置"""
    enabled: bool = False                    # 总开关
    email_address: Optional[str] = None      # 接收邮箱（可与注册邮箱不同）
    
    # 通知类型开关
    single_analysis: bool = True             # 单股分析结果
    batch_analysis: bool = True              # 批量分析汇总
    scheduled_analysis: bool = True          # 定时分析报告
    important_signals: bool = True           # 重要信号预警
    system_notifications: bool = False       # 系统通知
    
    # 发送时间偏好
    quiet_hours_enabled: bool = False        # 是否启用免打扰时段
    quiet_hours_start: str = "22:00"         # 免打扰开始时间
    quiet_hours_end: str = "08:00"           # 免打扰结束时间
    
    # 邮件格式偏好
    format: str = "html"                     # html / text
    include_charts: bool = True              # 是否包含图表
    language: str = "zh-CN"                  # 邮件语言

class UserPreferences(BaseModel):
    # ... 现有字段 ...
    
    # 新增邮件通知设置
    email_notifications: EmailNotificationSettings = Field(
        default_factory=EmailNotificationSettings
    )
```

### 3.2 邮件发送记录

```python
# app/models/email.py

class EmailStatus(str, Enum):
    PENDING = "pending"      # 待发送
    SENDING = "sending"      # 发送中
    SENT = "sent"           # 已发送
    FAILED = "failed"       # 发送失败
    BOUNCED = "bounced"     # 退信

class EmailRecord(BaseModel):
    """邮件发送记录"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    
    # 基本信息
    user_id: str
    to_email: str
    subject: str
    template_name: str
    
    # 邮件类型
    email_type: str          # single_analysis/batch_analysis/scheduled/signal/system
    
    # 关联数据
    reference_id: Optional[str] = None   # 关联的分析报告ID等
    reference_type: Optional[str] = None # analysis_report/scheduled_task等
    
    # 发送状态
    status: EmailStatus = EmailStatus.PENDING
    retry_count: int = 0
    max_retries: int = 3
    
    # 时间戳
    created_at: datetime = Field(default_factory=now_tz)
    sent_at: Optional[datetime] = None
    
    # 错误信息
    error_message: Optional[str] = None
    
    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

---

## 4. 邮件模板设计

### 4.1 模板结构

```
prompts/
├── email_templates/
│   ├── zh/
│   │   ├── single_analysis.html      # 单股分析结果
│   │   ├── batch_analysis.html       # 批量分析汇总
│   │   ├── scheduled_report.html     # 定时分析报告
│   │   ├── signal_alert.html         # 重要信号预警
│   │   ├── trial_expiring.html       # 试用即将到期
│   │   └── base_layout.html          # 基础布局模板
│   └── en/
│       └── ... (同上)
```

### 4.2 单股分析邮件模板示例

```html
<!-- prompts/email_templates/zh/single_analysis.html -->
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    .container { max-width: 600px; margin: 0 auto; font-family: 'Microsoft YaHei', sans-serif; }
    .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; }
    .stock-info { display: flex; align-items: center; }
    .stock-code { font-size: 24px; font-weight: bold; }
    .stock-name { font-size: 14px; opacity: 0.9; }
    .recommendation { font-size: 32px; padding: 20px; text-align: center; }
    .recommendation.buy { color: #e74c3c; }
    .recommendation.sell { color: #27ae60; }
    .recommendation.hold { color: #f39c12; }
    .section { padding: 15px; border-bottom: 1px solid #eee; }
    .section-title { font-weight: bold; color: #333; margin-bottom: 10px; }
    .key-points li { margin: 8px 0; color: #555; }
    .footer { background: #f5f5f5; padding: 15px; font-size: 12px; color: #999; }
    .btn { display: inline-block; padding: 10px 20px; background: #667eea; color: white; 
           text-decoration: none; border-radius: 4px; }
  </style>
</head>
<body>
  <div class="container">
    <!-- 头部 -->
    <div class="header">
      <div class="stock-info">
        <div>
          <div class="stock-code">{{ stock_code }}</div>
          <div class="stock-name">{{ stock_name }}</div>
        </div>
      </div>
      <div style="font-size: 12px; margin-top: 10px;">
        分析时间: {{ analysis_time }}
      </div>
    </div>
    
    <!-- 投资建议 -->
    <div class="recommendation {{ recommendation_class }}">
      {{ recommendation }}
    </div>
    
    <!-- 核心观点 -->
    <div class="section">
      <div class="section-title">📌 核心观点</div>
      <ul class="key-points">
        {% for point in key_points %}
        <li>{{ point }}</li>
        {% endfor %}
      </ul>
    </div>
    
    <!-- 风险提示 -->
    <div class="section">
      <div class="section-title">⚠️ 风险提示</div>
      <ul class="key-points">
        {% for risk in risks %}
        <li>{{ risk }}</li>
        {% endfor %}
      </ul>
    </div>
    
    <!-- 查看详情按钮 -->
    <div style="text-align: center; padding: 20px;">
      <a href="{{ detail_url }}" class="btn">查看完整分析报告</a>
    </div>
    
    <!-- 页脚 -->
    <div class="footer">
      <p>此邮件由 TradingAgents-CN 自动发送</p>
      <p>如需退订，请在应用设置中关闭邮件通知</p>
      <p style="color: #c0392b;">
        ⚠️ 免责声明：以上分析仅供参考，不构成投资建议。投资有风险，决策需谨慎。
      </p>
    </div>
  </div>
</body>
</html>
```

### 4.3 批量分析汇总邮件

```html
<!-- prompts/email_templates/zh/batch_analysis.html -->
<!-- 简化展示，实际模板更完整 -->
<div class="container">
  <div class="header">
    <h1>📊 批量分析结果</h1>
    <p>共分析 {{ total_count }} 只股票</p>
  </div>

  <!-- 汇总统计 -->
  <div class="summary">
    <div class="stat buy">建议买入: {{ buy_count }}</div>
    <div class="stat hold">建议持有: {{ hold_count }}</div>
    <div class="stat sell">建议卖出: {{ sell_count }}</div>
  </div>

  <!-- 股票列表 -->
  <table>
    <tr>
      <th>股票</th>
      <th>建议</th>
      <th>核心观点</th>
    </tr>
    {% for stock in stocks %}
    <tr>
      <td>{{ stock.code }} {{ stock.name }}</td>
      <td class="{{ stock.recommendation_class }}">{{ stock.recommendation }}</td>
      <td>{{ stock.summary }}</td>
    </tr>
    {% endfor %}
  </table>

  <div class="cta">
    <a href="{{ batch_detail_url }}" class="btn">查看详细报告</a>
  </div>
</div>
```

---

## 5. 后端服务实现

### 5.1 邮件服务

```python
# app/services/email_service.py

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Environment, FileSystemLoader
from typing import Optional, Dict, Any, List
from datetime import datetime
import asyncio

from app.core.config import settings
from app.models.email import EmailRecord, EmailStatus
from app.core.database import get_mongo_db
from app.utils.permission import check_feature

logger = get_logger("email_service")

class EmailService:
    """邮件发送服务"""

    def __init__(self):
        self.template_env = Environment(
            loader=FileSystemLoader("prompts/email_templates")
        )
        self.collection = "email_records"

    async def send_analysis_email(
        self,
        user_id: str,
        email_type: str,
        template_name: str,
        template_data: Dict[str, Any],
        reference_id: Optional[str] = None
    ) -> Optional[str]:
        """发送分析结果邮件"""

        # 1. 权限检查
        if not await check_feature(user_id, "email_notification"):
            logger.debug(f"用户 {user_id} 无邮件通知权限")
            return None

        # 2. 获取用户邮件设置
        user = await self._get_user(user_id)
        email_settings = user.preferences.email_notifications

        if not email_settings.enabled:
            logger.debug(f"用户 {user_id} 未开启邮件通知")
            return None

        # 3. 检查该类型通知是否开启
        type_enabled = getattr(email_settings, email_type, False)
        if not type_enabled:
            logger.debug(f"用户 {user_id} 未开启 {email_type} 类型通知")
            return None

        # 4. 检查免打扰时段
        if self._is_quiet_hours(email_settings):
            logger.debug(f"当前处于免打扰时段，邮件将延迟发送")
            # 加入延迟队列
            return await self._schedule_email(
                user_id, email_type, template_name, template_data, reference_id
            )

        # 5. 频率限制检查
        if not await self._check_rate_limit(user_id, email_type, reference_id):
            logger.debug(f"触发频率限制，跳过发送")
            return None

        # 6. 渲染邮件模板
        to_email = email_settings.email_address or user.email
        subject, html_content, text_content = self._render_template(
            template_name, template_data, email_settings.language
        )

        # 7. 创建邮件记录
        record = await self._create_record(
            user_id=user_id,
            to_email=to_email,
            subject=subject,
            template_name=template_name,
            email_type=email_type,
            reference_id=reference_id
        )

        # 8. 异步发送（加入队列）
        await self._enqueue_email(record.id, to_email, subject, html_content, text_content)

        return str(record.id)

    def _render_template(
        self,
        template_name: str,
        data: Dict[str, Any],
        language: str = "zh"
    ) -> tuple:
        """渲染邮件模板"""
        # 加载HTML模板
        html_template = self.template_env.get_template(f"{language}/{template_name}.html")
        html_content = html_template.render(**data)

        # 生成纯文本版本
        text_content = self._html_to_text(html_content)

        # 生成标题
        subject = self._generate_subject(template_name, data, language)

        return subject, html_content, text_content

    async def _send_smtp(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str
    ) -> bool:
        """通过SMTP发送邮件"""
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = settings.SMTP_FROM
            msg["To"] = to_email

            # 添加纯文本和HTML版本
            msg.attach(MIMEText(text_content, "plain", "utf-8"))
            msg.attach(MIMEText(html_content, "html", "utf-8"))

            # 发送邮件
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                if settings.SMTP_TLS:
                    server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(msg)

            logger.info(f"✅ 邮件发送成功: {to_email}")
            return True

        except Exception as e:
            logger.error(f"❌ 邮件发送失败: {e}")
            return False

    async def _check_rate_limit(
        self,
        user_id: str,
        email_type: str,
        reference_id: Optional[str]
    ) -> bool:
        """检查频率限制"""
        db = get_mongo_db()

        # 定义不同类型的限制
        limits = {
            "single_analysis": {"hours": 1, "same_ref": True},
            "batch_analysis": {"hours": 0, "same_ref": False},
            "scheduled_analysis": {"hours": 0, "same_ref": False},
            "important_signals": {"hours": 24, "same_ref": True},
            "system_notifications": {"hours": 72, "same_ref": True}
        }

        limit_config = limits.get(email_type, {"hours": 1, "same_ref": False})

        if limit_config["hours"] == 0:
            return True

        query = {
            "user_id": user_id,
            "email_type": email_type,
            "status": {"$in": [EmailStatus.SENT, EmailStatus.PENDING, EmailStatus.SENDING]},
            "created_at": {
                "$gte": datetime.utcnow() - timedelta(hours=limit_config["hours"])
            }
        }

        if limit_config["same_ref"] and reference_id:
            query["reference_id"] = reference_id

        count = await db[self.collection].count_documents(query)
        return count == 0


# 全局实例
_email_service: Optional[EmailService] = None

def get_email_service() -> EmailService:
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
```

### 5.2 邮件队列Worker

```python
# app/worker/email_worker.py

import asyncio
from typing import Optional
from app.core.database import get_redis_client, get_mongo_db
from app.services.email_service import get_email_service
from app.models.email import EmailStatus

logger = get_logger("email_worker")

class EmailWorker:
    """邮件发送Worker"""

    def __init__(self):
        self.queue_key = "email:send_queue"
        self.running = False
        self.email_service = get_email_service()

    async def start(self):
        """启动Worker"""
        self.running = True
        logger.info("📧 邮件发送Worker启动")

        while self.running:
            try:
                await self._process_queue()
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Worker处理异常: {e}")
                await asyncio.sleep(5)

    async def stop(self):
        """停止Worker"""
        self.running = False
        logger.info("📧 邮件发送Worker停止")

    async def _process_queue(self):
        """处理队列中的邮件"""
        redis = get_redis_client()

        # 从队列获取任务
        task_data = await redis.lpop(self.queue_key)
        if not task_data:
            return

        task = json.loads(task_data)
        record_id = task["record_id"]

        # 更新状态为发送中
        await self._update_status(record_id, EmailStatus.SENDING)

        # 发送邮件
        success = await self.email_service._send_smtp(
            to_email=task["to_email"],
            subject=task["subject"],
            html_content=task["html_content"],
            text_content=task["text_content"]
        )

        if success:
            await self._update_status(record_id, EmailStatus.SENT)
        else:
            # 检查重试次数
            record = await self._get_record(record_id)
            if record.retry_count < record.max_retries:
                # 重新加入队列
                await self._update_retry_count(record_id)
                await redis.rpush(self.queue_key, task_data)
            else:
                await self._update_status(record_id, EmailStatus.FAILED)
```

### 5.3 SMTP配置

```python
# app/core/config.py - 新增配置

class Settings(BaseSettings):
    # ... 现有配置 ...

    # SMTP邮件配置
    SMTP_ENABLED: bool = Field(default=False)
    SMTP_HOST: str = Field(default="smtp.example.com")
    SMTP_PORT: int = Field(default=587)
    SMTP_USER: str = Field(default="")
    SMTP_PASSWORD: str = Field(default="")
    SMTP_FROM: str = Field(default="noreply@tradingagents.cn")
    SMTP_FROM_NAME: str = Field(default="TradingAgents-CN")
    SMTP_TLS: bool = Field(default=True)

    # 邮件发送限制
    EMAIL_DAILY_LIMIT: int = Field(default=100)  # 每用户每天最多发送数
    EMAIL_RATE_LIMIT: int = Field(default=10)    # 每分钟最多发送数
```

---

## 6. API设计

### 6.1 邮件设置API

```python
# app/routers/email_settings.py

router = APIRouter(prefix="/api/v1/email", tags=["email"])

@router.get("/settings")
async def get_email_settings(
    current_user: dict = require_feature("email_notification")
):
    """获取邮件通知设置"""
    user = await get_full_user(current_user["id"])
    return {
        "settings": user.preferences.email_notifications.dict()
    }

@router.put("/settings")
async def update_email_settings(
    settings: EmailNotificationSettings,
    current_user: dict = require_feature("email_notification")
):
    """更新邮件通知设置"""
    await user_service.update_email_settings(current_user["id"], settings)
    return {"success": True, "message": "设置已更新"}

@router.post("/test")
async def send_test_email(
    current_user: dict = require_feature("email_notification")
):
    """发送测试邮件"""
    email_service = get_email_service()
    result = await email_service.send_test_email(current_user["id"])
    return {"success": result, "message": "测试邮件已发送" if result else "发送失败"}

@router.get("/history")
async def get_email_history(
    page: int = 1,
    page_size: int = 20,
    current_user: dict = require_feature("email_notification")
):
    """获取邮件发送历史"""
    records = await email_service.get_history(current_user["id"], page, page_size)
    return records
```

---

## 7. 前端设计

### 7.1 邮件设置页面

```vue
<!-- views/Settings/EmailNotification.vue -->
<template>
  <el-card>
    <template #header>
      <div class="header">
        <span>📧 邮件通知设置</span>
        <el-tag type="warning" size="small">专业版</el-tag>
      </div>
    </template>

    <el-form :model="settings" label-width="140px">
      <!-- 总开关 -->
      <el-form-item label="开启邮件通知">
        <el-switch v-model="settings.enabled" />
      </el-form-item>

      <!-- 接收邮箱 -->
      <el-form-item label="接收邮箱">
        <el-input
          v-model="settings.email_address"
          placeholder="默认使用注册邮箱"
          :disabled="!settings.enabled"
        />
      </el-form-item>

      <el-divider>通知类型</el-divider>

      <!-- 通知类型开关 -->
      <el-form-item label="单股分析结果">
        <el-switch v-model="settings.single_analysis" :disabled="!settings.enabled" />
        <span class="tip">分析完成后发送邮件</span>
      </el-form-item>

      <el-form-item label="批量分析汇总">
        <el-switch v-model="settings.batch_analysis" :disabled="!settings.enabled" />
        <span class="tip">批量分析完成后发送汇总邮件</span>
      </el-form-item>

      <el-form-item label="定时分析报告">
        <el-switch v-model="settings.scheduled_analysis" :disabled="!settings.enabled" />
        <span class="tip">定时任务完成后发送报告</span>
      </el-form-item>

      <el-form-item label="重要信号预警">
        <el-switch v-model="settings.important_signals" :disabled="!settings.enabled" />
        <span class="tip">检测到重大信号时立即通知</span>
      </el-form-item>

      <el-divider>免打扰设置</el-divider>

      <!-- 免打扰时段 -->
      <el-form-item label="启用免打扰">
        <el-switch v-model="settings.quiet_hours_enabled" :disabled="!settings.enabled" />
      </el-form-item>

      <el-form-item label="免打扰时段" v-if="settings.quiet_hours_enabled">
        <el-time-picker
          v-model="quietHoursRange"
          is-range
          range-separator="至"
          start-placeholder="开始时间"
          end-placeholder="结束时间"
          :disabled="!settings.enabled"
        />
      </el-form-item>

      <!-- 操作按钮 -->
      <el-form-item>
        <el-button type="primary" @click="saveSettings" :loading="saving">
          保存设置
        </el-button>
        <el-button @click="sendTestEmail" :loading="testing" :disabled="!settings.enabled">
          发送测试邮件
        </el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>
```

### 7.2 邮件发送历史

```vue
<!-- views/Settings/EmailHistory.vue -->
<template>
  <el-card>
    <template #header>邮件发送记录</template>

    <el-table :data="records" v-loading="loading">
      <el-table-column prop="subject" label="主题" min-width="200" />
      <el-table-column prop="email_type" label="类型" width="120">
        <template #default="{ row }">
          <el-tag size="small">{{ typeLabels[row.email_type] }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusTypes[row.status]" size="small">
            {{ statusLabels[row.status] }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="发送时间" width="180">
        <template #default="{ row }">
          {{ formatTime(row.created_at) }}
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="page"
      :page-size="pageSize"
      :total="total"
      @current-change="loadRecords"
    />
  </el-card>
</template>
```

---

## 8. 集成点

### 8.1 分析完成时触发

```python
# app/services/analysis_service.py

async def on_analysis_complete(
    user_id: str,
    analysis_id: str,
    analysis_result: dict
):
    """分析完成回调"""

    # 1. 站内通知（现有）
    await notifications_service.create_and_publish(
        NotificationCreate(
            user_id=user_id,
            type="analysis",
            title=f"分析完成: {analysis_result['stock_code']}",
            content=analysis_result['summary'],
            link=f"/analysis/report/{analysis_id}"
        )
    )

    # 2. 邮件通知（新增） ✨
    await email_service.send_analysis_email(
        user_id=user_id,
        email_type="single_analysis",
        template_name="single_analysis",
        template_data={
            "stock_code": analysis_result["stock_code"],
            "stock_name": analysis_result["stock_name"],
            "recommendation": analysis_result["recommendation"],
            "key_points": analysis_result["key_points"],
            "risks": analysis_result["risks"],
            "detail_url": f"{settings.APP_URL}/analysis/report/{analysis_id}"
        },
        reference_id=analysis_id
    )
```

### 8.2 定时分析完成时触发

```python
# app/worker/watchlist_analysis_task.py

async def on_scheduled_task_complete(task_id: str, results: List[dict]):
    """定时分析任务完成回调"""
    task = await get_task(task_id)

    # 邮件通知
    await email_service.send_analysis_email(
        user_id=task.user_id,
        email_type="scheduled_analysis",
        template_name="scheduled_report",
        template_data={
            "task_name": task.name,
            "total_count": len(results),
            "stocks": results,
            "buy_count": sum(1 for r in results if r["recommendation"] == "买入"),
            "hold_count": sum(1 for r in results if r["recommendation"] == "持有"),
            "sell_count": sum(1 for r in results if r["recommendation"] == "卖出"),
            "detail_url": f"{settings.APP_URL}/scheduled/report/{task_id}"
        },
        reference_id=task_id
    )
```

---

## 9. 权限与功能分层

### 9.1 功能权限

```python
# 添加到功能权限配置
FEATURE_PERMISSIONS = {
    # ... 现有配置 ...

    # 邮件通知 - 专业版功能
    Feature.EMAIL_NOTIFICATION: ['trial', 'pro', 'lifetime'],
}
```

### 9.2 邮件配额

| 用户等级 | 每日邮件上限 | 支持类型 |
|----------|-------------|----------|
| FREE | 0 | 不支持 |
| TRIAL | 20 | 全部 |
| PRO | 50 | 全部 |
| LIFETIME | 100 | 全部 |

---

## 10. 实现计划

### Phase 1: 基础架构 (Week 1)

- [ ] SMTP配置和邮件服务
- [ ] 邮件发送队列
- [ ] 邮件记录存储

### Phase 2: 模板系统 (Week 2)

- [ ] 单股分析邮件模板
- [ ] 批量分析汇总模板
- [ ] 定时分析报告模板
- [ ] 信号预警模板

### Phase 3: 用户设置 (Week 3)

- [ ] 邮件设置数据模型
- [ ] 设置API
- [ ] 前端设置页面

### Phase 4: 集成与测试 (Week 4)

- [ ] 分析完成触发集成
- [ ] 定时任务触发集成
- [ ] 发送测试与调优

---

## 11. 注意事项

### 11.1 邮件送达率

| 措施 | 说明 |
|------|------|
| **SPF记录** | 配置发送域名的SPF记录 |
| **DKIM签名** | 启用DKIM邮件签名 |
| **退订链接** | 每封邮件包含退订入口 |
| **发送频率** | 控制发送频率，避免被标记为垃圾邮件 |

### 11.2 用户体验

| 场景 | 处理 |
|------|------|
| 邮件过多 | 提供汇总模式，合并多条通知 |
| 重复通知 | 频率限制，同一内容不重复发送 |
| 用户退订 | 简单的一键退订流程 |

### 11.3 成本控制

- 使用云邮件服务（SendGrid/阿里云等）按量付费
- 设置每用户每日发送上限
- 优先使用站内通知，邮件作为补充

