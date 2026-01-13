# Docker 文件迁移计划

## 📋 迁移清单

### ✅ 需要移动的文件

| 原路径 | 新路径 | 说明 |
|--------|--------|------|
| `Dockerfile.backend` | `docker/Dockerfile.backend` | 后端源码版 |
| `Dockerfile.backend.compiled` | `docker/Dockerfile.backend.compiled` | 后端编译版（Windows） |
| `Dockerfile.frontend` | `docker/Dockerfile.frontend` | 前端 |
| `.dockerignore` | `docker/.dockerignore` | Docker 忽略文件 |
| `docker-compose.yml` | `docker/docker-compose.yml` | 基础配置 |
| `docker-compose.hub.nginx.yml` | `docker/docker-compose.hub.nginx.yml` | Hub + Nginx |
| `docker-compose.hub.nginx.arm.yml` | `docker/docker-compose.hub.nginx.arm.yml` | ARM64 |
| `.env.docker` | `docker/.env.docker` | 环境变量模板 |
| `nginx/nginx.conf` | `docker/nginx/nginx.conf` | Nginx 配置 |
| `nginx/local.nginx.conf` | `docker/nginx/local.nginx.conf` | 本地 Nginx |

### ✅ 需要创建的新文件

| 文件路径 | 说明 |
|---------|------|
| `docker/README.md` | Docker 文档 |
| `docker/Dockerfile.backend.compiled.ubuntu` | Ubuntu 编译版 |
| `docker/scripts/build-compile.sh` | 编译构建脚本 |
| `docker/scripts/build-multiarch.sh` | 多架构构建脚本 |
| `docker/scripts/init.sh` | 初始化脚本 |

### ⚠️ 需要更新引用的文件

以下文件中引用了 Docker 文件路径，需要更新：

1. **构建脚本**:
   - `scripts/build-amd64.ps1`
   - `scripts/build-amd64.sh`
   - `scripts/build-arm64.sh`
   - `scripts/build-multiarch.ps1`
   - `scripts/build-multiarch.sh`
   - `scripts/docker-init.ps1`
   - `scripts/docker-init.sh`

2. **文档**:
   - `docs/deployment/docker/DOCKER_DEPLOYMENT_v1.0.0.md`
   - `docs/deployment/docker/DOCKER_FILES_README.md`
   - `QUICK_START_PRO.md`
   - `README.md`

3. **其他**:
   - `.github/workflows/*.yml` (如果有 CI/CD)

## 🔧 迁移步骤

### 步骤 1: 移动文件

```bash
# 移动 Dockerfile
mv Dockerfile.backend docker/
mv Dockerfile.backend.compiled docker/
mv Dockerfile.frontend docker/

# 移动 docker-compose 文件
mv docker-compose.yml docker/
mv docker-compose.hub.nginx.yml docker/
mv docker-compose.hub.nginx.arm.yml docker/

# 移动 .dockerignore
mv .dockerignore docker/

# 移动 .env.docker
mv .env.docker docker/

# 移动 nginx 配置
mv nginx/nginx.conf docker/nginx/
mv nginx/local.nginx.conf docker/nginx/
```

### 步骤 2: 更新构建脚本

更新所有构建脚本中的 Dockerfile 路径：
- `dockerfile: Dockerfile.backend` → `dockerfile: docker/Dockerfile.backend`
- `dockerfile: Dockerfile.frontend` → `dockerfile: docker/Dockerfile.frontend`

### 步骤 3: 更新文档

更新所有文档中的路径引用。

### 步骤 4: 测试

```bash
# 测试构建
docker-compose -f docker/docker-compose.hub.nginx.yml build

# 测试启动
docker-compose -f docker/docker-compose.hub.nginx.yml up -d

# 测试访问
curl http://localhost/api/health
```

## 📝 兼容性说明

为了保持向后兼容，可以在项目根目录创建软链接：

```bash
# Linux/Mac
ln -s docker/docker-compose.hub.nginx.yml docker-compose.hub.nginx.yml
ln -s docker/Dockerfile.backend Dockerfile.backend
ln -s docker/Dockerfile.frontend Dockerfile.frontend

# Windows (需要管理员权限)
mklink docker-compose.hub.nginx.yml docker\docker-compose.hub.nginx.yml
mklink Dockerfile.backend docker\Dockerfile.backend
mklink Dockerfile.frontend docker\Dockerfile.frontend
```

或者在文档中说明新的路径。

## ✅ 验证清单

- [ ] 所有文件已移动到 `docker/` 目录
- [ ] 构建脚本已更新路径
- [ ] 文档已更新路径
- [ ] Docker Compose 配置已更新路径
- [ ] 测试构建成功
- [ ] 测试启动成功
- [ ] 测试访问成功
- [ ] 更新 `.gitignore`（如果需要）

---

**创建时间**: 2026-01-13  
**状态**: 待执行

