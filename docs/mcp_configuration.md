# MCP 配置指南

本文档介绍如何在 TradingAgents-CN 中配置和使用 MCP (Model Context Protocol) 服务器。

## 概述

MCP 是一种用于连接 AI 代理与外部工具和数据源的协议。TradingAgents-CN 支持两种 MCP 服务器模式：

- **stdio 模式**: 通过子进程通信的本地服务器
- **HTTP 模式**: 通过 HTTP/HTTPS 协议通信的远程服务器

## 配置文件位置

MCP 配置文件位于 `.kiro/settings/mcp.json`。

## 配置格式

```json
{
  "mcpServers": {
    "server-name": {
      "type": "stdio | http",
      "command": "uvx",
      "args": ["package-name"],
      "env": {
        "ENV_VAR": "value"
      },
      "url": "http://localhost:8080",
      "headers": {
        "Authorization": "Bearer token"
      },
      "description": "服务器描述",
      "_enabled": true,
      "healthCheck": {
        "enabled": true,
        "interval": 60,
        "timeout": 10
      }
    }
  }
}
```

## stdio 模式配置

stdio 模式用于运行本地 MCP 服务器。

### 必需字段

- `type`: 设置为 `"stdio"`
- `command`: 可执行命令（如 `uvx`, `npx`, `python`）
- `args`: 命令参数数组

### 可选字段

- `env`: 环境变量对象
- `description`: 服务器描述
- `_enabled`: 是否启用（默认 true）
- `healthCheck`: 健康检查配置

### 示例：使用 uvx 运行 Python MCP 服务器

```json
{
  "mcpServers": {
    "aws-docs": {
      "type": "stdio",
      "command": "uvx",
      "args": ["awslabs.aws-documentation-mcp-server@latest"],
      "env": {
        "FASTMCP_LOG_LEVEL": "ERROR"
      },
      "description": "AWS 文档 MCP 服务器",
      "_enabled": true
    }
  }
}
```

### 示例：使用 npx 运行 Node.js MCP 服务器

```json
{
  "mcpServers": {
    "filesystem": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "./"],
      "description": "文件系统 MCP 服务器",
      "_enabled": true
    }
  }
}
```

## HTTP 模式配置

HTTP 模式用于连接远程 MCP 服务器。

### 必需字段

- `type`: 设置为 `"http"`
- `url`: 服务器 URL（必须以 http:// 或 https:// 开头）

### 可选字段

- `headers`: HTTP 请求头（用于认证等）
- `description`: 服务器描述
- `_enabled`: 是否启用（默认 true）
- `healthCheck`: 健康检查配置

### 示例：连接远程 MCP 服务器

```json
{
  "mcpServers": {
    "remote-server": {
      "type": "http",
      "url": "https://api.example.com/mcp",
      "headers": {
        "Authorization": "Bearer your-api-token"
      },
      "description": "远程 MCP 服务器",
      "_enabled": true,
      "healthCheck": {
        "enabled": true,
        "interval": 30,
        "timeout": 5
      }
    }
  }
}
```

## 健康检查配置

健康检查用于监控 MCP 服务器的可用性。

```json
{
  "healthCheck": {
    "enabled": true,
    "interval": 60,
    "timeout": 10
  }
}
```

- `enabled`: 是否启用健康检查
- `interval`: 检查间隔（秒），范围 10-3600
- `timeout`: 超时时间（秒），范围 1-60

## Docker 部署配置

### 环境变量

在 Docker 环境中，可以使用以下环境变量：

- `MCP_CONFIG_PATH`: MCP 配置文件路径
- `MCP_ALLOWED_COMMANDS`: 允许的命令列表（逗号分隔）

### docker-compose.yml 配置

```yaml
services:
  backend:
    volumes:
      - ./.kiro/settings:/app/.kiro/settings
    environment:
      MCP_CONFIG_PATH: "/app/.kiro/settings/mcp.json"
      MCP_ALLOWED_COMMANDS: "uvx,npx,python,node"
```

### Docker 镜像要求

Docker 镜像需要包含：

- Python 3.10+
- uv 和 uvx（用于 Python MCP 服务器）
- Node.js（用于 Node.js MCP 服务器）

## 安全最佳实践

### 命令白名单

默认情况下，只允许以下命令：

- `uvx`
- `npx`
- `python`
- `python3`
- `node`
- `npm`

可以通过 `MCP_ALLOWED_COMMANDS` 环境变量自定义。

### HTTP 安全

- 生产环境建议使用 HTTPS
- 敏感的认证信息应该通过环境变量传递
- 定期轮换 API 令牌

### 环境变量安全

- 不要在配置文件中硬编码敏感信息
- 使用环境变量引用敏感值

## 故障排除

### 服务器无法启动

1. 检查命令是否在允许列表中
2. 检查命令是否已安装
3. 查看日志获取详细错误信息

### HTTP 连接失败

1. 检查 URL 是否正确
2. 检查网络连接
3. 检查认证信息是否有效
4. 检查 SSL 证书（HTTPS）

### 健康检查失败

1. 检查服务器是否正在运行
2. 检查超时设置是否合理
3. 检查网络延迟

### 配置热重载不生效

1. 检查配置文件语法
2. 检查文件权限
3. 查看日志确认重载是否触发

## 支持的环境变量

| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| `MCP_CONFIG_PATH` | 配置文件路径 | `.kiro/settings/mcp.json` |
| `MCP_ALLOWED_COMMANDS` | 允许的命令列表 | `uvx,npx,python,node` |
| `MCP_ALLOWED_ROOTS` | 允许的根目录 | 配置目录 |

## API 端点

### 列出连接器

```
GET /api/mcp/connectors
```

### 更新配置

```
POST /api/mcp/connectors/update
```

### 切换服务器

```
PATCH /api/mcp/connectors/{name}/toggle
```

### 删除服务器

```
DELETE /api/mcp/connectors/{name}
```

### 列出工具

```
GET /api/mcp/tools
```

### 获取健康状态

```
GET /api/mcp/health
```
