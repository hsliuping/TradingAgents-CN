# 第三方开源组件声明（Third-Party Notices）

本产品随包分发以下第三方开源组件。各组件的完整许可证文本随包提供或可从上游地址获取。

## 需特别声明的组件

### pystray（LGPLv3）

- **许可证**: GNU Lesser General Public License v3.0
- **上游源码**: https://github.com/moses-palmer/pystray
- **用途**: Windows 便携版系统托盘监控（`scripts/monitor/tray_monitor.py`）

按 LGPLv3 条款使用（作为独立库调用，闭源宿主程序允许）：
- 本声明即 LGPL 第 4 条要求的显著声明
- 库源码可从上述上游地址获取
- LGPLv3 全文随包分发（site-packages `pystray-*.dist-info/COPYING.LGPL`）

### pyphen（GPL 2.0+ / LGPL 2.1+ / MPL 1.1 三重许可）

- **许可证**: 三重许可，本产品选择按 **MPL 1.1** 条款使用（文件级弱 copyleft，不传染宿主程序）
- **上游源码**: https://github.com/henrik-lehtinen/pyphen（字典数据来自 LibreOffice）
- **用途**: WeasyPrint PDF 导出的断词（hyphenation）依赖
- **许可证文本**: site-packages `pyphen-*.dist-info/`（含 COPYING.GPL / COPYING.LGPL / COPYING.MPL）

### WeasyPrint（BSD-3-Clause）

- **上游源码**: https://github.com/Kozea/WeasyPrint
- **用途**: 研究报告 PDF 导出（`app/utils/report_exporter.py`）

### mini-racer（ISC）

- **上游源码**: https://github.com/bpcreech/PyMiniRacer
- **用途**: JavaScript 执行引擎

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

## 其余依赖

其他全部 Python 依赖（约 250 个）均为宽松许可证（MIT / BSD / Apache-2.0 / PSFL / ISC），
无 copyleft 传染义务，许可证文本随各包 `dist-info` 分发。完整清单见
`requirements.txt` 及安装后 `pip list --format=freeze`。

