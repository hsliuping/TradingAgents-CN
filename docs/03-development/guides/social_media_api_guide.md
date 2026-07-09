# 社媒消息API接入指南

本文档介绍如何通过API上传和查询社媒消息数据。

## 目录

- [API基础信息](#api基础信息)
- [认证方式](#认证方式)
- [数据格式说明](#数据格式说明)
- [API接口说明](#api接口说明)
- [使用示例](#使用示例)
- [模板文件](#模板文件)

## API基础信息

- **基础URL**: `http://your-domain:8000/api/social-media`
- **支持格式**: JSON、CSV、Excel (.xlsx, .xls)
- **编码**: UTF-8（推荐）、GBK、GB2312

## 认证方式

**所有API端点都需要用户认证**。使用API前，必须先登录获取访问令牌（Token）。

### 1. 登录获取Token

**接口**: `POST /api/auth/login`

**请求体**:
```json
{
  "username": "your_username",
  "password": "your_password"
}
```

**响应示例**:
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in": 86400,
    "user": {
      "id": "...",
      "username": "your_username",
      "email": "user@example.com"
    }
  }
}
```

**使用示例**:
```bash
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "your_username",
    "password": "your_password"
  }'
```

### 2. 使用Token访问API

获取Token后，在所有API请求的请求头中添加：

```http
Authorization: Bearer <your-token>
```

**重要提示**:
- Token有效期为24小时（默认）
- Token过期后需要重新登录获取
- 未认证的请求将返回 `401 Unauthorized` 错误

## 数据格式说明

### 必需字段

- `message_id`: 消息ID（唯一标识，同一平台内不能重复）
- `platform`: 平台类型（weibo/wechat/douyin/xiaohongshu/zhihu/twitter/reddit/xueqiu/eastmoney）
- `symbol`: 股票代码（如：000001、00700.HK、AAPL）
- `content`: 消息内容
- `publish_time`: 发布时间（格式：YYYY-MM-DD HH:MM:SS）

### 可选字段（推荐填写）

- `market`: 市场类型（A股/港股/美股）。如果不填写，系统会根据股票代码自动识别

### 可选字段

- `message_type`: 消息类型（post/comment/repost/reply/article/video）
- `author`: 作者信息对象
  - `author_id`: 作者ID
  - `author_name`: 作者名称
  - `verified`: 是否认证（true/false）
  - `influence_score`: 影响力评分（0-100）
  - `followers_count`: 粉丝数
  - `avatar_url`: 头像URL
- `engagement`: 互动数据对象
  - `views`: 浏览量
  - `likes`: 点赞数
  - `shares`: 转发/分享数
  - `comments`: 评论数
  - `engagement_rate`: 互动率
- `sentiment`: 情绪类型（positive/negative/neutral）
- `sentiment_score`: 情绪评分（-1.0 到 1.0）
- `hashtags`: 话题标签列表
- `keywords`: 关键词列表
- `topics`: 话题列表
- `importance`: 重要性（low/medium/high）
- `credibility`: 可信度（low/medium/high）
- `language`: 语言代码（默认：none，MongoDB文本索引支持：none/english/spanish/french/german/portuguese/russian/chinese）
- `data_source`: 数据来源（默认：manual）

## API接口说明

### 1. 上传文件

**接口**: `POST /api/social-media/upload`

**请求参数**:
- `file`: 文件（multipart/form-data）
- `symbol`: 股票代码（必需）
- `platform`: 默认平台类型（可选）
- `encoding`: 文件编码（可选，默认：utf-8）
- `overwrite`: 是否覆盖已存在的消息（可选，默认：false）

**响应示例**:
```json
{
  "success": true,
  "message": "成功上传并保存 10 条社媒消息",
  "data": {
    "filename": "social_media.json",
    "symbol": "000001",
    "platform": "weibo",
    "total_messages": 10,
    "saved": 10,
    "failed": 0,
    "upserted": 8,
    "modified": 2
  }
}
```

**使用示例**:
```bash
curl -X POST "http://localhost:8000/api/social-media/upload" \
  -H "Authorization: Bearer <your-token>" \
  -F "file=@social_media_template.json" \
  -F "symbol=000001" \
  -F "platform=weibo" \
  -F "encoding=utf-8" \
  -F "overwrite=false"
```

### 2. 批量保存消息（JSON格式）

**接口**: `POST /api/social-media/save`

**请求体**:
```json
{
  "symbol": "000001",
  "messages": [
    {
      "message_id": "weibo_001",
      "platform": "weibo",
      "content": "消息内容",
      "publish_time": "2025-01-15 10:30:00",
      ...
    }
  ]
}
```

**响应示例**:
```json
{
  "success": true,
  "message": "成功保存 5 条社媒消息",
  "data": {
    "saved": 5,
    "failed": 0,
    "upserted": 5,
    "modified": 0
  }
}
```

### 3. 查询消息

**接口**: `POST /api/social-media/query`

**请求体**:
```json
{
  "symbol": "000001",
  "platform": "weibo",
  "sentiment": "positive",
  "start_time": "2025-01-15 00:00:00",
  "end_time": "2025-01-15 23:59:59",
  "limit": 50,
  "skip": 0
}
```

**响应示例**:
```json
{
  "success": true,
  "message": "查询到 20 条社媒消息",
  "data": {
    "messages": [...],
    "count": 20,
    "params": {...}
  }
}
```

### 4. 获取最新消息

**接口**: `GET /api/social-media/latest/{symbol}`

**查询参数**:
- `platform`: 平台类型（可选）
- `limit`: 返回数量（可选，默认：20）

**响应示例**:
```json
{
  "success": true,
  "message": "获取到 20 条最新消息",
  "data": {
    "messages": [...],
    "count": 20,
    "symbol": "000001",
    "platform": "weibo"
  }
}
```

### 5. 搜索消息

**接口**: `GET /api/social-media/search`

**查询参数**:
- `query`: 搜索关键词（必需）
- `symbol`: 股票代码（可选）
- `platform`: 平台类型（可选）
- `limit`: 返回数量（可选，默认：50）

**响应示例**:
```json
{
  "success": true,
  "message": "搜索到 15 条相关消息",
  "data": {
    "messages": [...],
    "count": 15,
    "query": "平安银行",
    "symbol": "000001",
    "platform": "weibo"
  }
}
```

### 6. 获取统计信息

**接口**: `GET /api/social-media/statistics`

**查询参数**:
- `symbol`: 股票代码（可选）
- `market`: 市场类型（可选，A股/港股/美股）
- `platform`: 平台类型（可选）
- `sentiment`: 情绪类型（可选，positive/negative/neutral）
- `hours_back`: 回溯小时数（可选，不传则统计所有数据）

**响应示例**:
```json
{
  "success": true,
  "message": "统计信息获取成功",
  "data": {
    "statistics": {
      "total_count": 100,
      "positive_count": 60,
      "negative_count": 20,
      "neutral_count": 20,
      "platforms": {...},
      "avg_engagement_rate": 5.5
    },
    "symbol": "000001",
    "time_range": {...}
  }
}
```

### 7. 获取情绪分析

**接口**: `GET /api/social-media/sentiment-analysis/{symbol}`

**查询参数**:
- `platform`: 平台类型（可选）
- `hours_back`: 回溯小时数（可选，默认：24）

**响应示例**:
```json
{
  "success": true,
  "message": "情绪分析完成，共分析 100 条消息",
  "data": {
    "symbol": "000001",
    "total_messages": 100,
    "sentiment_distribution": {
      "positive": 60,
      "negative": 20,
      "neutral": 20
    },
    "sentiment_score": 0.4,
    "platform_sentiment": {...},
    "hourly_sentiment": {...}
  }
}
```

### 8. 获取支持的平台列表

**接口**: `GET /api/social-media/platforms`

**响应示例**:
```json
{
  "success": true,
  "message": "支持的平台列表获取成功",
  "data": {
    "platforms": [
      {
        "code": "weibo",
        "name": "微博",
        "description": "新浪微博社交平台"
      },
      ...
    ],
    "count": 8
  }
}
```

## 使用示例

### Python示例

详细示例代码请参考：`docs/examples/social_media_api_example.py`

```python
import requests
from social_media_api_example import SocialMediaAPIClient

# 步骤1：登录获取Token
login_url = "http://localhost:8000/api/auth/login"
login_data = {
    "username": "your_username",
    "password": "your_password"
}
login_response = requests.post(login_url, json=login_data)
token = login_response.json()["data"]["access_token"]

# 步骤2：使用Token初始化客户端
client = SocialMediaAPIClient(
    base_url="http://localhost:8000/api/social-media",
    token=token  # 传入token，客户端会自动添加Authorization header
)

# 步骤3：使用客户端调用API
# 上传文件
result = client.upload_file(
    file_path="social_media_template.json",
    symbol="000001",
    platform="weibo"
)
print(f"保存了 {result['data']['saved']} 条消息")

# 查询消息
result = client.query_messages(
    symbol="000001",
    sentiment="positive",
    limit=20
)
print(f"找到 {result['data']['count']} 条消息")

# 获取情绪分析
result = client.get_sentiment_analysis(
    symbol="000001",
    hours_back=24
)
print(f"情绪评分: {result['data']['sentiment_score']}")
```

### JavaScript/TypeScript示例

```javascript
// 步骤1：登录获取Token
const loginResponse = await fetch('http://localhost:8000/api/auth/login', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    username: 'your_username',
    password: 'your_password'
  })
});

const loginResult = await loginResponse.json();
const token = loginResult.data.access_token;

// 步骤2：使用Token调用API
// 上传文件
const formData = new FormData();
formData.append('file', fileInput.files[0]);
formData.append('symbol', '000001');
formData.append('platform', 'weibo');

const uploadResponse = await fetch('http://localhost:8000/api/social-media/upload', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`  // 添加Authorization header
  },
  body: formData
});

const uploadResult = await uploadResponse.json();
console.log(`保存了 ${uploadResult.data.saved} 条消息`);

// 查询消息
const queryResponse = await fetch('http://localhost:8000/api/social-media/query', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`  // 添加Authorization header
  },
  body: JSON.stringify({
    symbol: '000001',
    sentiment: 'positive',
    limit: 20
  })
});

const queryResult = await queryResponse.json();
console.log(`找到 ${queryResult.data.count} 条消息`);
```

## 模板文件

### JSON模板

参考文件：`docs/examples/social_media_template.json`

```json
[
  {
    "message_id": "weibo_1234567890",
    "platform": "weibo",
    "symbol": "000001",
    "content": "消息内容",
    "publish_time": "2025-01-15 10:30:00",
    "author": {
      "author_id": "user_001",
      "author_name": "作者名称",
      "verified": true
    },
    "engagement": {
      "views": 1000,
      "likes": 50
    },
    "sentiment": "positive"
  }
]
```

### CSV模板

参考文件：`docs/examples/social_media_template.csv`

CSV文件格式说明：
- 第一行为表头（字段名）
- 字段之间用逗号分隔
- 列表字段（如hashtags、keywords）用逗号分隔的字符串表示
- 时间格式：`YYYY-MM-DD HH:MM:SS`
- 布尔值：`true`/`false` 或 `1`/`0`

### Excel模板

Excel文件格式与CSV相同，第一行为表头。

## 注意事项

1. **消息ID唯一性**: `message_id` + `platform` 组合必须唯一，重复上传会更新现有记录
2. **时间格式**: 发布时间必须符合 `YYYY-MM-DD HH:MM:SS` 格式
3. **股票代码**: 建议使用6位数字代码（如：000001），系统会自动处理后缀（.SH、.SZ等）
4. **文件大小**: 建议单次上传不超过10MB
5. **编码问题**: CSV文件如果包含中文，建议使用UTF-8编码，或指定正确的编码参数

## 错误处理

API返回错误时，响应格式如下：

```json
{
  "detail": "错误描述信息"
}
```

常见错误：
- `400`: 请求参数错误
- `401`: 未认证（缺少或无效的Token）
  - 错误信息：`No authorization header` - 请求头中缺少Authorization
  - 错误信息：`Invalid authorization format` - Authorization格式错误（应为 `Bearer <token>`）
  - 错误信息：`Invalid token` - Token无效或已过期
  - 错误信息：`User not found` - Token中的用户不存在
- `403`: 无权限
- `500`: 服务器内部错误

**处理401错误的建议**:
1. 检查请求头中是否包含 `Authorization: Bearer <token>`
2. 确认Token未过期（默认24小时）
3. 如果Token过期，重新登录获取新Token
4. 确认用户账号未被禁用

## 更多信息

- API文档：访问 `http://your-domain:8000/docs` 查看完整的Swagger文档
- 前端界面：访问 `/settings/social-media` 使用Web界面上传和管理数据

