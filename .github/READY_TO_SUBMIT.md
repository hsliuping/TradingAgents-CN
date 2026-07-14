# 🚀 提交指南 — GitHub 恢复后执行

## 前置准备（已做完）

- ✅ 分支 `fix/news-report-empty-pyarrow-regex` 已创建
- ✅ 修复代码已提交（2个文件）
- ✅ Issue 模板已写入 `.github/ISSUE_TEMPLATE/news_report_empty.md`
- ✅ PR 描述已写好（见下文）

## 提交步骤

### 1. 设置 GitHub Token

```bash
export GITHUB_TOKEN="你的personal_access_token"
```

### 2. Push 分支到远程

```bash
cd ~/projects/TradingAgents-CN
git push origin fix/news-report-empty-pyarrow-regex
```

### 3. 创建 Issue

用 GitHub API：

```bash
curl -X POST https://api.github.com/repos/hsliuping/TradingAgents-CN/issues \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Content-Type: application/json" \
  -d @.github/ISSUE_TEMPLATE/news_report_empty.md
```

或者直接复制 `.github/ISSUE_TEMPLATE/news_report_empty.md` 的内容粘贴到 GitHub 的 New Issue 页面。

### 4. 创建 PR

```bash
curl -X POST https://api.github.com/repos/hsliuping/TradingAgents-CN/pulls \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "fix: CLI模式下新闻报告为空 — PyArrow正则兼容 + 缺少Fallback",
    "head": "fix/news-report-empty-pyarrow-regex",
    "base": "main",
    "body": "## 问题\\n\\nCLI模式分析A股时，新闻报告始终为空（仅输出\"我将先调用工具获取最新新闻数据\"）。\\n\\n## 根因\\n\\n1. **PyArrow正则兼容**：`ak.stock_news_em()` 的 `str.replace(r\"\\\\u3000\", \"\", regex=True)` 在PyArrow后端下抛出 `ArrowInvalid: invalid escape sequence: \\\\u`\\n2. **缺少Fallback**：`get_stock_news_sync()` 在 `ak.stock_news_em()` 失败后直接返回None，未使用已有的 `_get_stock_news_direct()`\\n3. **绕弯路**：`_get_a_share_news()` 在数据库空时先走脆弱的 `_sync_news_from_akshare()`（30秒超时异步线程），才试东方财富\\n\\n## 修复\\n\\n### `akshare.py`\\n- `get_stock_news_sync()` 中 `ak.stock_news_em()` 重试3次失败后，fallback到 `_get_stock_news_direct()` 直接调东方财富API\\n\\n### `unified_news_tool.py`\\n- 跳过 `_sync_news_from_akshare()` 步骤，直接走东方财富\\n- 所有失败路径升级为 `logger.error`，便于排查\\n\\n## 验证\\n\\n修复后统一新闻工具成功返回10条东方财富新闻（2990字符）：\\n- \"中谷物流(603565).SH：2025年年报净利润为20.01亿元\"\\n- \"13.33亿元主力资金今日撤离交通运输板块\"\\n- \"52股今日获机构买入评级\"\\n\\nCloses #（创建Issue后填入编号）"
  }'
```

或者手动在 GitHub 上操作：
1. 打开 https://github.com/hsliuping/TradingAgents-CN
2. Push 后会出现分支提示 "fix/news-report-empty-pyarrow-regex" → 点 "Compare & pull request"
3. 将 Issue 和 PR 内容粘贴进去

---

## 修改的文件

| 文件 | 修改类型 | 说明 |
|------|---------|------|
| `tradingagents/dataflows/providers/china/akshare.py` | +16/-6 行 | 加 fallback 到 `_get_stock_news_direct` |
| `tradingagents/tools/unified_news_tool.py` | +31/-34 行 | 跳过 AKShare sync + error日志 |
