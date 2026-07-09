# 项目依赖许可证审计 - GPL 检查报告

**检查日期**: 2026-02-07  
**目的**: 确认主项目（专有许可证）无 GPLv3 传染风险

## 结论摘要

**主项目依赖中未发现 GPLv3 许可证**。Backtrader 已隔离至独立容器 `backtest-service/`，通过 HTTP 调用，不构成代码链接。

## 详细检查结果

### 核心依赖（pyproject.toml / requirements.txt）

| 包名 | 许可证 | 说明 |
|------|--------|------|
| pandas | BSD-3-Clause | 宽松 |
| chromadb | Apache 2.0 | 宽松 |
| weasyprint | BSD-3-Clause | 宽松 |
| stockstats | BSD | 宽松 |
| feedparser | BSD-2-Clause | 宽松 |
| parsel | BSD-3-Clause | 宽松 |
| lxml (parsel 依赖) | BSD-3-Clause | 宽松 |
| tushare | BSD | 宽松 |
| baostock | BSD | 宽松 |
| akshare | MIT | 宽松 |
| langchain / langgraph | MIT | 宽松 |
| PRAW | BSD-2-Clause | 宽松 |
| curl-cffi | MIT | 宽松 |
| pdfkit | MIT | 宽松，封装 wkhtmltopdf |
| pypandoc | MIT | 宽松，封装 pandoc |
| GitPython | BSD-3-Clause | 宽松 |
| celery | BSD-3-Clause | 宽松 |

### 需关注的间接依赖

| 包名 | 间接工具 | 许可证 | 风险 |
|------|----------|--------|------|
| **pypandoc** | pandoc (外部进程) | GPL v2 | 低 - 子进程调用一般不构成衍生作品 |
| **pdfkit** | wkhtmltopdf (外部进程) | LGPL v3 | 无 - LGPL 允许专有软件调用 |
| **pytdx** | - | 部分 fork 未明确声明 | 建议确认所使用分发的具体许可 |

### 已隔离的 GPL 组件

- **Backtrader** (GPLv3) - 已移至 `backtest-service/` 独立容器，主平台仅通过 HTTP 调用
- 符合设计文档中的 GPL 合规策略

## 建议

1. **pytdx**：若使用 gitee/businesskame 等未声明许可证的分支，建议联系维护者或考虑替换
2. **pypandoc**：若对 GPL 极为谨慎，可考虑改用纯 Python 方案（如 pydocx、markdown2 等）替代 pandoc
3. **持续审计**：新增依赖时可用 `pip-licenses` 检查：`pip install pip-licenses && pip-licenses --format=markdown`
