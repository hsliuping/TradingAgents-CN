# MCP 配置示例

本目录包含 MCP 服务器配置的示例文件。

## 文件说明

### stdio_examples.json

stdio 模式的 MCP 服务器配置示例，包括：

- **aws-docs**: AWS 文档服务器（使用 uvx）
- **filesystem**: 文件系统服务器（使用 npx）
- **fetch**: HTTP 获取服务器
- **git**: Git 仓库服务器
- **sqlite**: SQLite 数据库服务器

### http_examples.json

HTTP 模式的 MCP 服务器配置示例，包括：

- **remote-api**: 远程 API 服务器
- **local-http**: 本地 HTTP 服务器
- **authenticated-server**: 带认证的服务器

### docker_examples.json

Docker 环境下的 MCP 服务器配置示例，包括：

- **docker-stdio**: Docker 中的 stdio 服务器
- **docker-http-internal**: Docker 内部网络服务器
- **docker-http-external**: Docker 外部服务器

## 使用方法

1. 复制所需的配置到 `.kiro/settings/mcp.json`
2. 根据需要修改配置
3. 将 `_enabled` 设置为 `true` 启用服务器

## 环境变量

示例中使用的环境变量占位符：

- `${MCP_API_TOKEN}`: API 令牌
- `${MCP_API_KEY}`: API 密钥
- `${HTTP_PROXY}`: HTTP 代理
- `${HTTPS_PROXY}`: HTTPS 代理

请在运行前设置这些环境变量。

## 注意事项

- 所有示例默认禁用（`_enabled: false`），请根据需要启用
- 生产环境请使用 HTTPS
- 敏感信息请通过环境变量传递
