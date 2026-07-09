# ClawHub 工具生态利用方案

## 📋 文档信息

| 项目 | 内容 |
|------|------|
| 版本 | v1.0 |
| 状态 | 调研完成 |
| 日期 | 2026-02 |
| 目标 | 评估 ClawHub 工具生态的接入方式和利用价值 |

---

## 1. 调研结论

### 1.1 ClawHub 是什么

ClawHub 是 OpenClaw 的公共 Skill 市场，托管 5,705+ 社区构建的 Skills（截至 2026-02-07）。

- **网站**: `clawhub.ai`
- **源码仓库**: `github.com/openclaw/skills`
- **安装方式**: `npx clawhub@latest install <skill-slug>`
- **格式**: Agent Skills Specification（SKILL.md + 可选脚本/资源）

### 1.2 关键发现：Agent Skills ≠ MCP

Agent Skills 和 MCP 是 Anthropic 推出的**两套完全不同的标准**：

| 维度 | Agent Skills (ClawHub) | MCP |
|------|----------------------|-----|
| **本质** | 文件夹打包格式（SKILL.md + 脚本） | JSON-RPC 通信协议 |
| **执行方式** | 进程内加载、直接执行 | 独立进程、进程隔离 |
| **安全边界** | 无隔离、共享环境 | 进程隔离、凭证作用域 |
| **动态性** | Agent 可运行时自修改 | 需预配置 |
| **治理** | ClawHub 市场（社区自审） | AAIF 基金会（Linux Foundation） |
| **采用者** | Claude Code、Codex CLI、Cursor、OpenClaw | Claude Desktop、各种 IDE、我们的系统 |

**结论：ClawHub 没有 MCP 方案。** ClawHub 上的 Skills 使用 Agent Skills 规范，不是 MCP Server。虽然有少数 Skills 内部封装了 MCP Server 调用，但这不是官方接入方式。

### 1.3 安全风险评估

2026 年 1 月，安全研究人员发现 ClawHub 上 **341 个恶意 Skills**：

| 攻击类型 | 说明 |
|----------|------|
| 凭证窃取 | 将 API Key 发送到外部服务器 |
| Token 盗用 | 窃取 OAuth Token |
| 键盘记录 | 针对浏览器和系统密钥 |
| 反向 Shell | 建立远程控制通道 |

攻击手法：创建与合法开发者相似的账户名（typosquatting），发布"增强版"热门 Skills。

> **风险评级：高。** 直接从 ClawHub 安装并执行 Skills 存在严重安全隐患。

---

## 2. 利用方案

鉴于安全风险和技术差异，我们**不直接集成 ClawHub**，而是采取以下策略：

### 方案 A：参考型利用（推荐，零风险）

**思路**：将 ClawHub 作为"工具创意库"，人工挑选有价值的工具概念，通过我们自己的 Skill 生成管线重新实现。

**流程**：
1. 浏览 ClawHub 分类（Finance、Data Analysis、API Integration 等）
2. 发现有价值的工具概念（如 PDF 解析、数据可视化、特定 API 集成）
3. 提取工具的功能规格（名称、描述、输入输出）
4. 在我们的 Skill 工坊中创建，走完整验证管线（静态分析 + 沙箱执行 + Judge 评分）

**优势**：
- 零安全风险
- 利用 ClawHub 5,700+ Skills 的创意库
- 生成的 Skill 完全符合我们的质量标准

### 方案 B：SKILL.md 解析器（中期）

**思路**：构建 SKILL.md 解析器，自动提取工具规格，预填到 Skill 工坊。

```python
class SkillMDParser:
    """解析 ClawHub SKILL.md 格式，提取工具规格"""

    def parse(self, skill_md_content: str) -> SkillSpec:
        """
        从 SKILL.md 提取：
        - name, description (YAML frontmatter)
        - input_params, output_format (从 instructions 分析)
        - dependencies (从 setup 步骤提取)
        """
        ...

    def to_skill_spec(self, parsed: dict) -> SkillSpec:
        """转换为我们的 SkillSpec 格式，供 Skill 工坊使用"""
        ...
```

**流程**：
1. 用户粘贴 SKILL.md 内容（或提供 GitHub URL）
2. 解析器提取工具规格
3. 预填到 Skill 工坊创建向导
4. LLM 基于规格重新生成实现代码（不使用原始代码）
5. 走完整验证管线

**优势**：
- 半自动化，效率更高
- 只使用规格描述，不执行任何 ClawHub 代码
- 通过我们的管线保证代码质量

### 方案 C：MCP Server 桥接（已有能力）

**思路**：对于提供 MCP Server 的工具（不在 ClawHub 上，而是独立的 MCP Server），直接通过我们已实现的 MCP 支持接入。

我们的 MCP 支持已实现：
- SSE / Streamable HTTP / stdio 三种传输
- 工具自动发现和注册
- 前端管理界面

**适用场景**：
- 官方 MCP Server（如 Trello MCP、Gmail MCP 等）
- 社区维护的高质量 MCP Server
- 企业自建的 MCP Server

---

## 3. ClawHub 中与金融分析相关的 Skills

经过筛选，ClawHub 上金融/交易相关的 Skills **极少且质量不高**：

| Skill | 说明 | 可利用性 |
|-------|------|----------|
| `stock-analyzer` | 基础股票分析 | ⚠️ 功能简单，不如我们现有工具 |
| `financial-data` | 财务数据查询 | ⚠️ 仅支持美股 |
| `crypto-*` | 加密货币相关 | ❌ 与我们 A 股方向不符 |

**结论**：ClawHub 的金融类 Skills 对我们价值有限，但其他类别（文档处理、API 集成、数据可视化）有参考价值。

---

## 4. 实施优先级

| 优先级 | 方案 | 时间 | 说明 |
|--------|------|------|------|
| P0 | 方案 A（参考型利用） | 立即可用 | 人工浏览 + Skill 工坊创建 |
| P1 | 方案 C（MCP 桥接） | 已实现 | 对独立 MCP Server 直接接入 |
| P2 | 方案 B（SKILL.md 解析器） | v3.1 | 半自动化工具规格提取 |

---

## 5. 相关文档

- [MCP 支持](./mcp-support.md) — MCP Server 接入能力
- [Skill 生成系统](./skill-generation-system.md) — Skill 创建管线
- [Skill 缺口感知](./skill-gap-perception.md) — 运行时工具缺口检测
