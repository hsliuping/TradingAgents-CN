# K8s 部署文档

## 前置条件

1. K8s 集群（京东云容器服务 / 自建 / 公有云）
2. kubectl 工具
3. 镜像已构建并推送到镜像仓库
4. 已申请 StorageClass（如京东云 `ssd-sata`）

## 部署步骤

### 1. 构建并推送镜像

```bash
# 在项目根目录
cd tradingagents-cn-pro
bash deploy-all-in-one/build.sh 3.0.0 --push

# 或推送到京东云镜像仓库
docker tag tradingagents-cn-pro:3.0.0 \
  registry.cn-north-1.jdcloud.com/your-namespace/tradingagents-cn-pro:3.0.0
docker push registry.cn-north-1.jdcloud.com/your-namespace/tradingagents-cn-pro:3.0.0
```

### 2. 准备 Secret

复制 `10-secret.yaml.example` 为 `10-secret.yaml`，编辑填入实际密码：

```bash
cd deploy-all-in-one/k8s
cp 10-secret.yaml.example 10-secret.yaml
vim 10-secret.yaml
```

### 3. 修改 Deployment

编辑 `30-deployment.yaml`，修改 `image` 字段为你的镜像地址：

```yaml
image: registry.cn-north-1.jdcloud.com/your-namespace/tradingagents-cn-pro:3.0.0
```

调整资源限制：

```yaml
resources:
  requests:
    cpu: "500m"
    memory: "1Gi"
  limits:
    cpu: "4000m"
    memory: "4Gi"
```

### 4. 按顺序应用

```bash
# 1. 创建命名空间
kubectl apply -f 00-namespace.yaml

# 2. 创建 Secret（注意不要提交到 git）
kubectl apply -f 10-secret.yaml

# 3. 创建 PVC
kubectl apply -f 20-pvc.yaml

# 4. 部署应用
kubectl apply -f 30-deployment.yaml

# 5. 创建 Service + Ingress
kubectl apply -f 40-service.yaml
```

### 5. 验证部署

```bash
# 查看 Pod 状态
kubectl -n tradingagents get pods -l app=tradingagents-cn-pro

# 查看日志（包含 s6 服务输出）
kubectl -n tradingagents logs -f -l app=tradingagents-cn-pro

# 检查健康状态
kubectl -n tradingagents get pods -l app=tradingagents-cn-pro \
  -o jsonpath='{.items[0].status.conditions[?(@.type=="Ready")].status}'
```

### 6. 端口转发（开发调试）

```bash
# 转发 8082 端口到本地
kubectl -n tradingagents port-forward svc/tradingagents 8082:8082

# 访问
curl http://localhost:8082/api/health
open http://localhost:8082
```

## 京东云特殊配置

### 1. 使用京东云托管 MongoDB（推荐生产环境）

如果 MongoDB 在集群外部（京东云文档数据库），需修改 Secret 和 Deployment：

```yaml
# 10-secret.yaml
stringData:
  MONGODB_HOST: "mongo-xxx.jdcloud.com"
  MONGODB_PORT: "27017"
  MONGODB_PASSWORD: "xxx"

# 30-deployment.yaml
env:
- name: MONGODB_HOST
  value: "mongo-xxx.jdcloud.com"
```

并在 `volumeMounts` 中移除 MongoDB 相关的挂载：

```yaml
volumeMounts:
# 删除这些：
# - name: data
#   mountPath: /data/db
# - name: logs
#   mountPath: /var/log/mongodb
```

### 2. 使用京东云托管 Redis

同理修改：

```yaml
env:
- name: REDIS_HOST
  value: "redis-xxx.jdcloud.com"
- name: REDIS_PORT
  value: "6379"
```

### 3. 京东云 SLB Ingress

修改 `40-service.yaml` 的 Service type 为 LoadBalancer：

```yaml
spec:
  type: LoadBalancer
  annotations:
    service.beta.kubernetes.io/jdcloud-loadbalancer-id: "lb-xxx"
```

## 故障排查

### Pod 一直 Pending

```bash
kubectl describe pod -n tradingagents <pod-name>
# 检查 PVC 是否绑定，资源是否足够
```

### 健康检查失败

```bash
# 查看健康检查日志
kubectl logs -n tradingagents <pod-name> | grep -i "health"

# 进入容器调试
kubectl exec -it -n tradingagents <pod-name> -- /bin/bash

# 在容器内检查各服务状态
sv status /etc/s6-overlay/s6-rc.d
```

### 数据初始化失败

```bash
# 查看 init-data 日志
kubectl logs -n tradingagents <pod-name> | grep -i "init-data"

# 手动执行初始化
kubectl exec -it -n tradingagents <pod-name> -- \
  python3 scripts/import_config_and_create_user.py
```

### 升级镜像

```bash
# 1. 修改 Deployment 镜像 tag
kubectl -n tradingagents set image deployment/tradingagents \
  tradingagents=tradingagents-cn-pro:3.0.1

# 2. 观察滚动更新
kubectl -n tradingagents rollout status deployment/tradingagents

# 3. 回滚（如需要）
kubectl -n tradingagents rollout undo deployment/tradingagents
```

## 备份与恢复

### 备份 MongoDB

```bash
# 进入 Pod 执行 mongodump
kubectl exec -n tradingagents <pod-name> -- \
  mongodump --uri="mongodb://admin:xxx@127.0.0.1:27017/tradingagents?authSource=admin" \
  --out=/tmp/backup

# 拷贝到本地
kubectl cp tradingagents/<pod-name>:/tmp/backup ./backup-$(date +%Y%m%d)
```

### 恢复 MongoDB

```bash
# 拷贝到 Pod
kubectl cp ./backup-xxx tradingagents/<pod-name>:/tmp/backup

# 执行 mongorestore
kubectl exec -n tradingagents <pod-name> -- \
  mongorestore --uri="mongodb://admin:xxx@127.0.0.1:27017/tradingagents?authSource=admin" \
  /tmp/backup
```

## 监控

### 资源使用

```bash
# 实时资源使用
kubectl -n tradingagents top pod -l app=tradingagents-cn-pro

# 京东云控制台 → 容器服务 → 工作负载 → 监控
```

### 日志收集

京东云日志服务 CLS：

```yaml
# 在 Pod spec 中添加 annotation
metadata:
  annotations:
    log-driver: "jdcloud-cls"
    log-topic-id: "your-topic-id"
```
