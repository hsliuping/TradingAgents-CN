# TradingAgents-CN 自动更新 — 服务端接入文档

> **版本**: v1.0
> **最后更新**: 2026-02-17
> **接入方**: 官网后端 (`tradingagentscn.com`)
> **调用方**: TradingAgents-CN 桌面客户端（Windows 安装版）

> 说明：便携版后续不再作为对外发布形态。当前构建链路中如仍出现 `portable`，仅表示内部打包/安装包验证阶段的中间产物，不再面向实际用户分发。

---

## 一、总体说明

桌面客户端内置了自动更新模块。用户在前端点击「检查更新」后，客户端后端会向官网发出 HTTP 请求。
**官网只需实现 1 个 API + 托管更新包文件**，即可完成整个更新闭环。

### 交互时序

```
┌──────────┐         ┌──────────────┐         ┌──────────────────┐
│  前端 UI  │         │ 客户端后端    │         │ 官网后端          │
│ (Vue 3)  │         │ (FastAPI)    │         │ tradingagentscn  │
└────┬─────┘         └──────┬───────┘         └────────┬─────────┘
     │  点击「检查更新」      │                          │
     │───────────────────>│                          │
     │                    │  GET /api/app/check-update│
     │                    │─────────────────────────>│
     │                    │         JSON 响应         │
     │                    │<─────────────────────────│
     │   显示新版本信息     │                          │
     │<───────────────────│                          │
     │                    │                          │
     │  点击「下载更新」     │                          │
     │───────────────────>│                          │
     │                    │  GET download_url (流式)  │
     │                    │─────────────────────────>│
     │                    │     ZIP 文件流            │
     │                    │<─────────────────────────│
     │   显示下载进度       │                          │
     │<───────────────────│                          │
     │                    │                          │
     │  点击「应用更新」     │                          │
     │───────────────────>│                          │
     │                    │ 启动 updater.ps1 独立进程  │
     │                    │ 后端退出 → 替换文件 → 重启  │
```

---

## 二、API 接口

### `GET /api/app/check-update`

客户端用此接口查询是否有新版本可用。

#### 请求

| 项目 | 值 |
|------|-----|
| **完整 URL** | `https://www.tradingagentscn.com/api/app/check-update` |
| **Method** | `GET` |
| **超时** | 15 秒 |

**Query 参数**:

| 参数 | 类型 | 必填 | 说明 | 示例 |
|------|------|------|------|------|
| `version` | string | ✅ | 客户端当前版本号（语义化版本） | `2.0.0` |
| `build_type` | string | ❌ | 构建类型 | `installer` / `unknown` |
| `channel` | string | ❌ | 更新通道，未传时应按正式通道处理 | `stable` / `test` |

**Headers**:

| Header | 值 |
|--------|-----|
| `User-Agent` | `TradingAgentsCN/{version}`，例如 `TradingAgentsCN/2.0.0` |

**请求示例**:

```
GET /api/app/check-update?version=2.0.0&build_type=installer&channel=stable HTTP/1.1
Host: www.tradingagentscn.com
User-Agent: TradingAgentsCN/2.0.0
```

**通道建议**:

| channel | 用途 | 建议行为 |
|---------|------|----------|
| `stable` | 正式发布 | 返回正式可发布版本 |
| `test` | 内测 / 验证 | 返回测试包、预发包或灰度包 |

> 为兼容旧客户端，服务端应在 `channel` 缺失时默认按 `stable` 处理。

#### 响应

**Content-Type**: `application/json`

**有新版本时**:

```json
{
  "success": true,
  "data": {
    "has_update": true,
    "version": "2.0.1",
    "download_url": "https://www.tradingagentscn.com/downloads/update-2.0.1.zip",
    "file_size": 52428800,
    "sha256": "a1b2c3d4e5f6...完整64位十六进制小写",
    "release_notes": "## v2.0.1 更新日志\n\n### 🐛 修复\n- 修复了xxx问题\n\n### ✨ 新增\n- 新增了xxx功能",
    "release_date": "2026-02-17",
    "is_mandatory": false,
    "min_version": "2.0.0"
  }
}
```

**已是最新版本时**:

```json
{
  "success": true,
  "data": {
    "has_update": false,
    "version": "",
    "download_url": "",
    "file_size": 0,
    "sha256": "",
    "release_notes": "",
    "release_date": "",
    "is_mandatory": false,
    "min_version": ""
  }
}
```

**响应字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `has_update` | bool | **核心字段** — 是否有新版本。客户端据此判断是否显示更新 UI |
| `version` | string | 最新版本号，语义化版本格式，如 `2.0.1`、`2.1.0` |
| `package_type` | string | 包类型。`installer` 表示安装包，`update` 表示应用内更新包。客户端会据此决定是下载安装程序还是执行应用内升级 |
| `download_url` | string | 更新包下载地址（完整 URL）。客户端会用 **HTTP 流式下载**（`httpx.stream`），服务端需支持 `Content-Length` 响应头 |
| `file_size` | int | 更新包文件大小（字节）。用于前端显示和进度计算。如果 download_url 的响应带了 `Content-Length`，会优先用响应头的值 |
| `sha256` | string | 更新包的 SHA256 校验值（**64位十六进制小写**）。下载完成后客户端会校验，不匹配则拒绝安装。**留空则跳过校验**（不推荐） |
| `release_notes` | string | 更新日志，支持 **Markdown 格式**。前端会用 `v-html` 渲染。建议用 `##` 标题 + `- ` 列表 |
| `release_date` | string | 发布日期，格式 `YYYY-MM-DD` |
| `is_mandatory` | bool | 是否强制更新。`true` 时前端会阻止用户跳过此版本（当前版本 UI 已预留，后续可加弹窗拦截） |
| `min_version` | string | 此更新包支持的最低客户端版本。例如 `2.0.0` 表示只有 ≥2.0.0 的客户端才能安装此更新包（当前客户端未校验此字段，**预留**） |

### 服务端同步改造清单

本次客户端协议扩展是 **在原有接口上新增一个可选查询参数 `channel`**。

#### 1. 必须修改

服务端需要同步修改 `GET /api/app/check-update` 的入参解析逻辑：

| 项目 | 旧版 | 新版 |
|------|------|------|
| Query 参数 | `version`、`build_type` | `version`、`build_type`、`channel` |
| `channel` 是否必填 | 不存在 | 否 |
| 兼容要求 | 无 | **未传时必须按 `stable` 处理** |

建议服务端伪代码：

```python
channel = (request.query_params.get("channel") or "stable").strip().lower()
if channel not in {"stable", "test"}:
    channel = "stable"
```

然后在查找可发布版本时，按 `channel` 过滤可用版本：

- `stable`: 只返回正式发布版本
- `test`: 返回测试/灰度/预发布版本

#### 2. 响应体是否需要修改

**需要新增 `package_type` 字段。**

客户端当前会解析下面这些字段，其中新增了 `package_type`：

- `has_update`
- `version`
- `package_type`
- `download_url`
- `file_size`
- `sha256`
- `release_notes`
- `release_date`
- `is_mandatory`
- `min_version`

也就是说，这次服务端协议改动的核心有两项：

**支持按 `channel` 参数分流返回版本。**

**返回 `package_type`，让客户端区分当前下载地址指向安装包还是更新包。**

#### 3. 服务端数据模型建议增加的信息

如果服务端当前是把发布信息存数据库或配置文件，建议每个发布记录增加一个 `channel` 字段。

推荐最小结构：

```json
{
  "version": "2.0.1",
  "channel": "stable",
  "package_type": "installer",
  "build_type": "installer",
  "download_url": "https://.../TradingAgentsCN-Setup-2.0.1.exe",
  "sha256": "...",
  "file_size": 12345678,
  "release_notes": "...",
  "release_date": "2026-03-12",
  "is_mandatory": false,
  "min_version": "2.0.0"
}
```

其中新增的是：

- `channel`: `stable` 或 `test`
- `package_type`: `installer` 或 `update`

其余字段沿用原逻辑即可。

#### 3.1 `package_type` 的实际含义

| package_type | 含义 | `download_url` 应指向 |
|--------------|------|-----------------------|
| `installer` | 安装包 | 安装程序下载地址（如 `.exe`） |
| `update` | 应用内更新包 | 更新包地址（如 `update-{version}.zip`） |

客户端行为：

- `installer`: 仅下载安装程序，不走应用内更新器替换流程
- `update`: 下载更新包，并交给应用内更新器执行替换升级

#### 4. 服务端筛选逻辑建议

如果服务端当前是“取最新版本号”直接返回，需要改成“按通道取最新版本号”后再返回。

建议逻辑：

1. 先确定请求通道 `channel`
2. 在该通道内筛选可用版本
3. 找到该通道下最新版本
4. 与客户端传入的 `version` 比较
5. 如果服务端版本更高，则返回更新信息；否则返回 `has_update=false`

#### 5. 兼容性要求

为了兼容旧客户端，服务端必须满足：

- 没有 `channel` 参数时，默认等同于 `stable`
- `channel` 传了未知值时，建议回退为 `stable`
- 不要因为缺少 `channel` 就返回 4xx

#### 6. 客户端本次已新增的信息

本次客户端已经新增并实际发出的信息如下：

| 信息 | 位置 | 示例 | 说明 |
|------|------|------|------|
| `channel` | Query 参数 | `stable` / `test` | 新增，用于区分正式和测试更新流 |

客户端内部还新增了一个本地配置项：

- `UPDATE_CHECK_CHANNEL`: 控制客户端发给服务端的通道值，默认 `stable`

可接受的配置别名会被客户端归一化，例如：

- 归一化到 `stable`: `stable`、`formal`、`prod`、`production`、`release`、`official`、`正式`、`线上`
- 归一化到 `test`: `test`、`testing`、`beta`、`staging`、`preview`、`测试`、`预发`

因此服务端最终实际接收到的值，正常情况下只会是：

- `stable`
- `test`

#### 7. 推荐联调样例

正式通道：

```http
GET /api/app/check-update?version=2.0.0&build_type=installer&channel=stable
```

测试通道：

```http
GET /api/app/check-update?version=2.0.0&build_type=installer&channel=test
```

旧客户端兼容样例：

```http
GET /api/app/check-update?version=2.0.0&build_type=installer
```

这三种请求都应该返回 200，差别仅在于服务端选用哪个发布通道的数据。

---

## 三、更新包规范

### 文件格式

- **格式**: `.zip`（标准 ZIP 压缩）
- **命名**: `update-{version}.zip`，如 `update-2.0.1.zip`
- **大小**: 约 50-80 MB（仅代码，不含运行时）

### 内部目录结构

更新包解压后的顶层结构**必须**如下（按需包含，不存在的可省略）：

```
update-2.0.1.zip
├── app/                    # 后端代码（.pyc 编译后）
├── core/                   # 核心引擎代码（.pyc/.pyd）
├── frontend/               # 前端构建产物
│   └── dist/               #   └── 静态文件
├── scripts/                # 工具脚本和启动脚本
├── tradingagents/          # v1.x 兼容层代码
├── prompts/                # 提示词模板
├── migrations/             # 数据库迁移脚本
├── VERSION                 # 版本号文本文件（如 "2.0.1"）
└── BUILD_INFO              # 构建信息 JSON
```

> **关键**: 更新器脚本会把上述每个顶层项整体替换到安装目录。
> **不要**包含以下内容（否则会覆盖用户数据）：
> - `vendors/`（Python/MongoDB/Redis 运行时）
> - `data/`（数据库文件）
> - `.env`（用户配置）
> - `logs/`（日志文件）
> - `runtime/`（临时文件）
> - `backup/`（备份文件）

### VERSION 文件

纯文本，只有一行版本号：

```
2.0.1
```

### BUILD_INFO 文件

JSON 格式：

```json
{
    "build_type": "installer",
    "version": "2.0.1",
    "build_date": "2026-02-17T10:30:00Z",
    "git_commit": "abc1234",
    "full_version": "2.0.1-build20260217-103000"
}
```

### 构建更新包

项目中已有构建脚本：

```powershell
# 在项目根目录执行
.\scripts\deployment\build_update_package.ps1

# 指定版本号
.\scripts\deployment\build_update_package.ps1 -Version "2.0.1"
```

输出文件：
- `release/packages/update-2.0.1.zip` — 更新包
- `release/packages/update-2.0.1.sha256` — SHA256 校验文件（内容如 `a1b2c3...  update-2.0.1.zip`）

---

## 四、文件托管

更新包需要通过 HTTP 可下载，`download_url` 指向的地址需满足：

| 要求 | 说明 |
|------|------|
| **支持 GET 请求** | 返回 ZIP 文件流 |
| **Content-Length 响应头** | 客户端用于计算下载进度百分比 |
| **支持大文件** | 更新包约 50-80 MB |
| **HTTPS** | 推荐，但客户端不强制校验证书 |
| **无需鉴权** | 客户端下载时不带 Token（更新包本身不含敏感信息） |

**托管方案建议**：
- 直接放在官网服务器的静态目录（如 Nginx 的 `/downloads/`）
- 或使用 CDN / 对象存储（阿里云 OSS、腾讯云 COS 等），`download_url` 直接填 CDN 地址

---

## 五、版本比较逻辑

客户端**不做**版本号比较，完全依赖服务端返回的 `has_update` 字段。

**服务端的版本判断逻辑建议**：

```python
from packaging.version import Version

def check_update(client_version: str, build_type: str) -> dict:
    latest = get_latest_release()  # 从数据库或配置读取

    client_ver = Version(client_version)
    latest_ver = Version(latest["version"])

    has_update = latest_ver > client_ver

    return {
        "success": True,
        "data": {
            "has_update": has_update,
            "version": latest["version"] if has_update else "",
            "download_url": latest["download_url"] if has_update else "",
            "file_size": latest["file_size"] if has_update else 0,
            "sha256": latest["sha256"] if has_update else "",
            "release_notes": latest["release_notes"] if has_update else "",
            "release_date": latest["release_date"] if has_update else "",
            "is_mandatory": latest.get("is_mandatory", False) if has_update else False,
            "min_version": latest.get("min_version", "") if has_update else "",
        }
    }
```

---

## 六、客户端更新流程详解

供服务端开发者理解完整流程：

```
1. 用户点击「检查更新」
   → 客户端 GET /api/app/check-update?version=2.0.0
   → 服务端返回 has_update=true, version=2.0.1

2. 用户点击「下载更新」
   → 客户端 GET {download_url}（流式下载）
   → 保存到 runtime/updates/update-2.0.1.zip
   → SHA256 校验

3. 用户点击「应用更新」
   → 客户端启动独立进程 scripts/updater/apply_update.ps1
   → 客户端后端进程退出（3秒延迟）
   → 更新器等待后端完全退出
   → 停止所有服务（MongoDB/Redis/Nginx）
   → 备份当前版本到 backup/v2.0.0_20260217/
   → 解压更新包，替换代码文件
   → 重启所有服务
   → 新版本启动时自动执行数据库迁移（migrations/）
   → 用户刷新浏览器即可使用新版本
```

---

## 七、测试清单

服务端开发完成后，按以下步骤验证：

### 1. 接口联调

```bash
# 模拟客户端请求
curl -s "https://www.tradingagentscn.com/api/app/check-update?version=2.0.0&build_type=installer" \
  -H "User-Agent: TradingAgentsCN/2.0.0" | python -m json.tool
```

确认：
- [ ] 返回 `success: true`
- [ ] `has_update` 为 `true`（当 version 低于最新版时）
- [ ] `has_update` 为 `false`（当 version 等于最新版时）
- [ ] `download_url` 可访问且可下载
- [ ] `sha256` 与实际文件匹配
- [ ] `file_size` 与实际文件大小一致

### 2. 下载验证

```bash
# 下载更新包
curl -o update.zip "https://www.tradingagentscn.com/downloads/update-2.0.1.zip"

# 校验 SHA256
sha256sum update.zip
# 或 PowerShell:
# (Get-FileHash update.zip -Algorithm SHA256).Hash.ToLower()

# 检查内部结构
unzip -l update.zip | head -30
```

确认：
- [ ] 响应头包含 `Content-Length`
- [ ] SHA256 匹配接口返回值
- [ ] ZIP 内包含 `VERSION` 文件
- [ ] ZIP 内**不**包含 `vendors/`、`data/`、`.env`

### 3. 端到端测试

在 Windows 安装版中：
- [ ] 设置 → 系统管理 → 系统更新
- [ ] 点击「检查更新」→ 显示新版本信息
- [ ] 点击「下载更新」→ 进度条正常推进到 100%
- [ ] 点击「应用更新」→ 服务重启 → 刷新浏览器 → 版本号已更新

---

## 八、FAQ

**Q: 客户端多久检查一次更新？**
A: 目前只在用户手动点击「检查更新」时才检查，没有自动轮询。

**Q: 如果服务端返回 HTTP 500 或网络不通怎么办？**
A: 客户端会显示「无法连接更新服务器」，不会中断正常使用。

**Q: download_url 可以指向第三方 CDN 吗？**
A: 可以。客户端会跟随 301/302 重定向（`follow_redirects=True`）。

**Q: sha256 可以留空吗？**
A: 可以但**强烈不推荐**。留空时客户端跳过校验，存在文件损坏风险。

**Q: is_mandatory 当前有什么效果？**
A: 当前仅前端展示标记，不阻止用户跳过。后续版本会加强制弹窗。

**Q: 支持增量更新/差量更新吗？**
A: 当前为全量替换。更新包只包含代码部分（~50-80MB），不含运行时（~350MB），所以体积已经可接受。
