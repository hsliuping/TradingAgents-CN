---
name: ifind-repilot-news-search
description: 通过问句语义化搜索全市场金融资讯（新闻、舆情、市场动态等），返回与问句相关的新闻片段信息。当需要检索金融新闻、市场资讯、行业动态、公司舆情等信息时，使用此 skill。
metadata:  {"openclaw":{"emoji":"📰︎","requires":{"bins":["python3"]}}}
---

## 概述

此 skill 通过自然语言问句查询（向量检索）全市场金融资讯。它调用封装好的 Python 脚本，向同花顺数据接口发送请求，返回与问句相关的新闻列表信息。支持按照时间范围查询。

## 前置要求

### 环境依赖

- Python 3.x
- 标准库：`json`, `urllib`, `pathlib`
- 无需安装第三方库
- 注1：若 `python3` 命令不可用（常见于 Windows），请改用 `python`
- 注2：`<skill_dir>` 为当前 skill 所在目录的完整路径，请根据当前上下文自动获取。

### 首次配置

首次使用 skill 前，需要先配置认证 token。

1. 提示用户先从飞研平台获取 token。平台地址： https://repilot.51ifind.com/ ，菜单路径：业务管理 -> Skills技能库。
2. 用户提供token后，运行以下命令配置 token：
```bash
python3 <skill_dir>/scripts/fetch_data.py --set-token <your_auth_token>
```
3. 检查 token 是否已配置：
```bash
python3 <skill_dir>/scripts/fetch_data.py --check-token
```

注：配置文件位于：`~/.config/ifind-repilot/config.json`

## 使用方式

### 基本查询

```bash
python3 <skill_dir>/scripts/fetch_data.py "<自然语言查询语句>"
```

### 带时间范围查询

```bash
python3 <skill_dir>/scripts/fetch_data.py "<自然语言查询语句>" --start-date <开始日期> --end-date <结束日期>
```

日期格式：`YYYY-MM-DDTHH:MM:SS`，例如 `2025-01-01T00:00:00`

日期参数可以放在查询语句之前或之后：

```bash
# 方式一：日期参数在前
python3 <skill_dir>/scripts/fetch_data.py --start-date 2025-01-01T00:00:00 --end-date 2026-01-01T00:00:00 "美联储利率政策"

# 方式二：日期参数在后
python3 <skill_dir>/scripts/fetch_data.py "美联储利率政策" --start-date 2025-01-01T00:00:00 --end-date 2026-01-01T00:00:00
```

### 查询示例

| 查询内容 | 命令 |
|---------|------|
| 美联储利率政策 | `python3 <skill_dir>/scripts/fetch_data.py "美联储利率政策"` |
| 同花顺最新资讯 | `python3 <skill_dir>/scripts/fetch_data.py "同花顺"` |
| 2025年美联储利率政策 | `python3 <skill_dir>/scripts/fetch_data.py "美联储利率政策" --start-date 2025-01-01T00:00:00 --end-date 2025-12-31T23:59:59` |


### 返回格式

脚本直接返回查询结果的 JSON 数据，包含以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `total` | int | 检索到的新闻总数 |
| `status_code` | int | 状态码，0表示成功 |
| `status_msg` | string | 状态信息 |
| `data` | array | 新闻列表 |

每条新闻包含以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `title` | string | 新闻标题 |
| `summary` | string | 新闻摘要 |
| `url` | string | 新闻原文链接 |
| `channel` | string | 频道类型 |
| `publish_time` | int | 发布时间（Unix时间戳） |
| `publish_date` | string | 发布时间（格式：YYYY-MM-DD HH:MM:SS） |
| `score` | int | 相关性评分 |
| `extra` | object | 扩展信息（如 `publish_source` 来源） |

返回示例：

```json
{
  "total": 15,
  "status_code": 0,
  "data": [
    {
      "title": "龙虎榜丨同花顺今日涨停，二机构合计净卖出6.41亿元",
      "summary": "11月7日，同花顺今日涨停，成交额132.06亿元...",
      "url": "https://www.jiemian.com/article/11954485.html",
      "channel": "news",
      "publish_time": 1730968311,
      "publish_date": "2024-11-07 16:31:51",
      "score": 100,
      "extra": {
        "publish_source": "界面新闻"
      }
    }
  ],
  "status_msg": "OK"
}
```

### 错误处理

| 错误信息 | 原因 | 解决方法 |
|----------|------|----------|
| `请先配置 auth_token` | 未设置 token | 提示用户获取并发送token，收到token后，运行 `--set-token` 配置 |
| `API HTTP 错误` | 请求失败 | 检查网络或 API 地址 |
| `网络错误` | 无法连接 | 检查网络连接 |
| `API 返回失败` | 接口返回错误 | 查看具体错误信息 |
| `API HTTP 错误: 429` | 触发当日请求限制 | 提醒用户到飞研平台检查用量信息 |
| `API HTTP 错误: 401` | 缺失token或者token无效 | 提醒用户检查token是否正确 |
| `API HTTP 错误: 403` | 没有权限访问接口 | 没有权限访问接口 |

## 执行规则

1. 先判断用户请求或任务是否需要金融资讯检索。
2. 若需要金融资讯检索，根据用户请求内容与思考，生成一个合适的自然语言查询语句作为参数调用脚本。
3. 若请求返回未检索到数据、或者返回的数据不符合期望，可以尝试生成一个新的自然语言查询语句重新查询。
4. 不要编造任何金融资讯。若脚本失败或返回空结果，应明确说明失败原因或未检索到数据。
5. 将脚本输出内容进行重新组织和提炼；保留新闻标题、来源和摘要中的重要数据。
6. 当出现401、403、429错误时，请勿再重试，直接提醒用户skill返回的错误内容。