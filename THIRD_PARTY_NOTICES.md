# 第三方开源组件声明（Third-Party Notices）

本产品随包分发以下第三方开源组件。各组件的完整许可证文本随包提供或可从上游地址获取。

## SearXNG

- **许可证**: GNU Affero General Public License v3.0 或更新版本（AGPL-3.0-or-later）
- **上游源码**: https://github.com/searxng/searxng
- **随包版本**: 2026.8.6+b023a28
- **许可证文本**: wheel 包内 `searxng-*.dist-info/licenses/LICENSE`（安装后位于 site-packages）

### 使用方式

SearXNG 以**独立进程/容器**运行（Windows 安装包内为独立进程，Docker 部署为独立容器），
本产品通过标准 HTTP API（`/search?format=json`）与其通信。

两个程序运行于独立地址空间、仅通过网络接口交互，不构成合并作品；
本产品的其余代码不受 SearXNG 许可证的传染约束。

### 本地修改（Corresponding Source 说明）

依据 AGPL-3.0 第 13 条与分发条款，现将本产品对 SearXNG 的全部本地修改公开如下：

**修改补丁文件**: [`config/searxng/searxng-local-modifications.patch`](config/searxng/searxng-local-modifications.patch)

| 文件 | 修改内容 | 原因 |
|------|---------|------|
| `searx/valkeydb.py` | `import pwd` 改为 try/except ImportError 容错 | `pwd` 是 Unix-only 模块，Windows 上不存在 |
| `searx/settings.yml` | 默认引擎配置微调 | 国内环境可用性 |

补丁文件本身按 AGPL-3.0 授权。应用方式：

```bash
cd searxng/
git apply ../config/searxng/searxng-local-modifications.patch
```

### 源码可获得性

- 分发的 wheel 为纯 Python 包，安装后的 `searx/*.py` **即完整对应源码**（含上述修改）
- 上游未修改源码可从上述 GitHub 地址获取
- 本地修改见补丁文件

### 搜索引擎使用提示

SearXNG 聚合的搜索结果来自第三方引擎（百度、360、Bing、搜狗等）。本产品仅限
私有部署、内部使用；各引擎服务条款对程序化访问的限制由部署方自行评估。
