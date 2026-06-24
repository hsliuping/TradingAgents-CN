---
name: ifind-repilot-finance-data-search
description: 使用自然语言查询金融数据，支持A股股票、基金、期货等上市品种，覆盖基本资料、财务数据、日频行情信息、持仓信息及各类分析指标等数据。也支持宏观经济数据，包括世界经济数据、全球经济数据、中国经济数据、区域经济数据、行业经济数据、利率走势数据、商品数据和特色数据等。当需要查询上述金融相关数据查询时使用此 skill。
metadata:  {"openclaw":{"emoji":"🔍︎","requires":{"bins":["python3"]}}}
---

## 概述

此 skill 通过自然语言查询金融数据。通过调用封装好的 Python 脚本，向同花顺金融数据接口发送请求，返回半结构化的金融数据。

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

### 查询示例

| 查询内容 | 命令 |
|---------|------|
| 同花顺收盘价 | `python3 <skill_dir>/scripts/fetch_data.py "同花顺收盘价"` |
| 茅台股价 | `python3 <skill_dir>/scripts/fetch_data.py "贵州茅台当前股价"` |
| 苹果公司财报 | `python3 <skill_dir>/scripts/fetch_data.py "苹果公司最近季度营收和利润"` |
| 上证指数 | `python3 <skill_dir>/scripts/fetch_data.py "上证指数今日行情"` |
| 股票对比 | `python3 <skill_dir>/scripts/fetch_data.py "比亚迪和蔚来股价对比"` |

### 返回格式

脚本直接返回查询结果的文本内容，通常是文本与 Markdown 表格格式的组合，示例：

```
提取数据：数据浏览器
|证券代码|证券简称|收盘价（元）|
|---|---|---|
|300033.SZ|同花顺|291.74|

提取数据：FinQuery
|股票代码|股票简称|日期|收盘价:不复权|
|---|---|---|---|
|300033.SZ|同花顺|20250808|287.78|
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
| `暂无结果` | 当前问句没有检索到数据，并非token权限问题 | 尝试生成一个新的自然语言查询语句重新查询 |


## 执行规则

1. 先判断用户请求或任务是否需要金融数据检索。
2. 若需要金融数据检索，根据用户请求内容与思考，生成一个合适的自然语言查询语句作为参数调用脚本。
3. 若问题包含时间范围不明确的财务数据请求，默认查询最近已披露季度或最近财年，并在回答中明确说明默认时间范围。
4. 若请求返回未检索到数据、或者返回的数据不符合期望，可以尝试生成一个新的自然语言查询语句重新查询。
5. 不要编造任何金融数据。若脚本失败或返回空结果，应明确说明失败原因或未检索到数据。
6. 将脚本输出中的关键数据提炼为简洁结论；如有表格，优先保留表格。
7. 当出现401、403、429错误时，请勿再重试，直接提醒用户skill返回的错误内容。