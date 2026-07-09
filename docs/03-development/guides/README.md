# 社媒消息数据上传示例

本目录包含社媒消息数据上传的模板文件和API接入示例。

## 文件说明

### 模板文件

1. **`social_media_template.json`** - JSON格式模板文件
   - 包含完整的字段示例
   - 适合程序化生成数据
   - 支持批量上传

2. **`social_media_template.csv`** - CSV格式模板文件
   - 表格格式，易于编辑
   - 适合Excel编辑后导出
   - 支持中文内容

### API接入示例

1. **`social_media_api_example.py`** - Python API客户端示例
   - 完整的API客户端封装
   - 包含所有接口的使用示例
   - 可直接运行测试

2. **`social_media_api_guide.md`** - API接入指南文档
   - 详细的API接口说明
   - 请求/响应示例
   - 错误处理说明

## 快速开始

### 方式1：使用Web界面上传（推荐）

1. 登录系统
2. 访问：**设置 → 系统管理 → 社媒消息管理**
3. 点击 **"上传社媒数据"** 按钮
4. 选择模板文件（JSON/CSV/Excel）
5. 填写股票代码和参数
6. 点击上传

### 方式2：使用API上传

#### Python示例

```python
from social_media_api_example import SocialMediaAPIClient

# 初始化客户端
client = SocialMediaAPIClient(base_url="http://localhost:8000/api/social-media")

# 上传文件
result = client.upload_file(
    file_path="social_media_template.json",
    symbol="000001",
    platform="weibo"
)

print(f"✅ 保存了 {result['data']['saved']} 条消息")
```

#### cURL示例

```bash
curl -X POST "http://localhost:8000/api/social-media/upload" \
  -F "file=@social_media_template.json" \
  -F "symbol=000001" \
  -F "platform=weibo"
```

## 数据格式要求

### 必需字段

- `message_id`: 消息ID（唯一标识）
- `platform`: 平台类型
- `symbol`: 股票代码
- `content`: 消息内容
- `publish_time`: 发布时间

### 支持的平台

- `weibo` - 微博
- `wechat` - 微信
- `douyin` - 抖音
- `xiaohongshu` - 小红书
- `zhihu` - 知乎
- `twitter` - Twitter
- `reddit` - Reddit
- `xueqiu` - 雪球
- `eastmoney` - 东方财富

### 时间格式

- 格式：`YYYY-MM-DD HH:MM:SS`
- 示例：`2025-01-15 10:30:00`

## 使用建议

1. **数据准备**
   - 使用模板文件作为参考
   - 确保必需字段完整
   - 检查时间格式正确

2. **批量上传**
   - 建议单次上传不超过1000条
   - 大文件可以分批上传
   - 使用 `overwrite=false` 避免覆盖已有数据

3. **数据质量**
   - 确保 `message_id` 唯一性
   - 填写准确的股票代码
   - 尽量包含完整的作者和互动数据

## 更多帮助

- 查看完整API文档：`social_media_api_guide.md`
- 运行示例程序：`python social_media_api_example.py`
- 访问Web界面：`/settings/social-media`

