# Nginx 动态 DNS 解析修复

## 问题描述

当使用 Docker Compose 部署时，更新前端服务后，Nginx 容器会报错：

```
[emerg] host not found in upstream "frontend" in /etc/nginx/conf.d/default.conf:35
```

需要重新安装 Nginx 容器才能恢复正常。

## 问题原因

1. **DNS 缓存问题**：Nginx 在启动时会解析 `frontend` 和 `backend` 主机名到 IP 地址，并缓存这个解析结果。
2. **容器 IP 变化**：当前端服务更新时，Docker 会创建新的容器实例，IP 地址可能发生变化。
3. **静态解析**：Nginx 使用静态配置（如 `proxy_pass http://frontend:80;`），无法自动更新已缓存的 IP 地址。

## 解决方案

使用 Nginx 的 `resolver` 指令和变量来实现动态 DNS 解析，让每次请求都重新解析主机名。

### 配置修改

在 `nginx/nginx.conf` 中添加：

1. **DNS 解析器配置**：
   ```nginx
   # Docker 内部 DNS 解析器（动态解析）
   resolver 127.0.0.11 valid=10s ipv6=off;
   ```
   - `127.0.0.11` 是 Docker 内置的 DNS 服务器
   - `valid=10s` 表示 DNS 解析结果缓存 10 秒
   - `ipv6=off` 禁用 IPv6 解析

2. **使用变量实现动态解析**：
   ```nginx
   # 前端代理
   location / {
       set $frontend_upstream http://frontend:80;
       proxy_pass $frontend_upstream;
       # ... 其他配置
   }

   # 后端 API 代理
   location /api/ {
       set $backend_upstream http://backend:8000;
       proxy_pass $backend_upstream/api/;
       # ... 其他配置
   }
   ```

### 工作原理

- 当 `proxy_pass` 使用变量时，Nginx 会在每次请求时重新解析变量中的主机名
- `resolver` 指令告诉 Nginx 使用哪个 DNS 服务器进行解析
- `valid=10s` 确保 DNS 解析结果会定期刷新，但不会每次都查询（提升性能）

## 优势

1. **自动适应容器更新**：前端或后端服务更新后，无需重启 Nginx 容器
2. **性能优化**：DNS 解析结果缓存 10 秒，避免每次请求都查询 DNS
3. **向后兼容**：不影响现有功能，只是增强了 DNS 解析的灵活性

## 验证方法

1. 启动所有服务：
   ```bash
   docker-compose -f docker-compose.hub.nginx.yml up -d
   ```

2. 更新前端服务：
   ```bash
   docker-compose -f docker-compose.hub.nginx.yml up -d --force-recreate frontend
   ```

3. 检查 Nginx 日志，应该不再出现 "host not found" 错误：
   ```bash
   docker logs tradingagents-nginx
   ```

4. 访问前端页面，应该能正常加载。

## 注意事项

1. **DNS 解析延迟**：首次请求可能会有轻微的 DNS 解析延迟（通常 < 100ms）
2. **DNS 服务器地址**：`127.0.0.11` 是 Docker 的标准 DNS 服务器，如果使用自定义网络配置，可能需要调整
3. **IPv6**：如果 Docker 网络支持 IPv6，可以移除 `ipv6=off` 参数

## 相关文件

- `nginx/nginx.conf` - Nginx 主配置文件
- `docker-compose.hub.nginx.yml` - Docker Compose 配置文件
- `docker-compose.hub.nginx.arm.yml` - ARM 架构的 Docker Compose 配置

## 参考文档

- [Nginx resolver 指令文档](http://nginx.org/en/docs/http/ngx_http_core_module.html#resolver)
- [Docker 网络 DNS 配置](https://docs.docker.com/config/containers/container-networking/#dns-services)
