# AWS 大阪部署

Terraform 创建独立 VPC、公有子网、Internet Gateway、路由、安全组、SSH 公钥、EC2 和 Elastic IP。
默认大阪 `ap-northeast-3`、Ubuntu 22.04 x86_64、`t3.large`、80 GB 加密 gp3 根磁盘。
本次部署的账号不允许创建 `t3.large`，实际 `terraform.tfvars` 使用免费套餐适用的 `m7i-flex.large`（2 vCPU、8 GB）。免费套餐适用仍会消耗账号额度，不代表永久免费。
费用为 EC2 + EBS + 公网 IPv4 + 流量，另有大模型调用费用；不是 Lightsail 套餐。

## 准备与创建

1. 在本机配置 AWS 凭证，可使用 AWS CLI 的 `aws configure sso` / `aws sso login`，并设置 `$env:AWS_PROFILE`；也可使用 AWS 标准凭证环境变量。不要将凭证写入代码或聊天。账号需要创建上述资源的权限。
2. 准备 SSH 密钥，例如 `ssh-keygen -t ed25519 -f "$env:USERPROFILE/.ssh/tradingagents"`。已存在则不要覆盖。
3. 在此目录复制 `terraform.tfvars.example` 为 `terraform.tfvars`，填写公钥路径和你的公网 IPv4 `/32`。
4. 执行：

```powershell
terraform init
terraform fmt -check
terraform validate
terraform plan '-out=deploy.tfplan'
terraform apply 'deploy.tfplan'
terraform output
```

请先查看计划中的账号、区域和资源。`apply` 会产生 AWS 费用。提交 `.terraform.lock.hcl`，不要提交 state、计划文件或凭证。

## 验证和访问

实例创建成功不等于应用初始化完成，首次安装 Docker 和拉取镜像需要数分钟。

```powershell
$serverIp = terraform output -raw public_ip
ssh -i "$env:USERPROFILE/.ssh/tradingagents" "ubuntu@$serverIp" "sudo cloud-init status --wait"
ssh -i "$env:USERPROFILE/.ssh/tradingagents" "ubuntu@$serverIp" "sudo test -f /opt/tradingagents/bootstrap-complete && sudo docker compose -f /opt/tradingagents/compose.yaml --project-directory /opt/tradingagents ps"
ssh -i "$env:USERPROFILE/.ssh/tradingagents" -N -L 8080:127.0.0.1:80 "ubuntu@$serverIp"
```

公网访问地址为 http://16.208.96.255，无需域名或 SSH 隧道。执行 `Invoke-RestMethod http://16.208.96.255/api/health` 检查后端。
上面的 SSH 隧道仍可用于访问 http://localhost:8080，但不是网页访问的必要条件。
若私钥设置了密码，交互运行 SSH 时输入密码，或先通过 `ssh-add` 加载到已启动的 Windows ssh-agent。
首次 cloud-init 因上游未发布 v1.0.1 镜像而失败，已通过 SSH 更换已发布镜像并恢复。历史 cloud-init 状态可能仍显示 error；以 `bootstrap-complete`、容器状态和 API 响应判断修复后的服务状态。
按用户要求启用公网 HTTP：安全组向所有 IPv4 地址开放 80，Nginx 映射宿主机 80 端口；SSH 仍限制 admin_cidr，数据库端口不公开。未配置 HTTPS，登录和其他 HTTP 内容不加密。
首次登录后更改管理员密码，再在“设置 → 配置管理”填写大模型供应商密钥并测试。

此发布镜像不会自动创建管理员。新数据库启动后，上传本目录的 `init_admin.py` 到服务器，通过 `sudo docker exec -i tradingagents-backend-1 python - < init_admin.py` 执行。脚本仅在用户集合为空时初始化，不覆盖现有账号；随机密码保存在服务器 `/opt/tradingagents/data/admin-initial-password.txt`（600 权限），并验证登录接口能返回 token。本次部署已完成初始化，初始登录信息通过 SSH 保存至本机本目录下的 `admin-initial-password.txt`（已被 Git 忽略）。改密后请删除两处初始密码文件。

## 数据与运维

- 镜像首次启动不会自动导入厂家目录。将本目录 `init_providers.py` 上传至服务器，通过 `sudo docker exec -i tradingagents-backend-1 python - < init_providers.py` 执行，导入镜像自带的厂家与模型目录。脚本只补充缺失记录，保留已有配置，不导入 API 密钥或用户；新厂家默认禁用，填写密钥后在网页启用。本次已补齐 9 个厂家及 9 个模型目录。

- 初始化脚本在服务器 `/opt/tradingagents/.env` 生成数据库、Redis、JWT 和 CSRF 密钥（权限 600），不会将这些密钥放入 Terraform state。
- 使用 Docker Hub 实际发布的 v1.0.0-preview 镜像（仓库引用的 v1.0.1 标签未发布），不包含本机当前代码；如需当前代码，请构建并发布自己的镜像再替换 compose 镜像地址。
- MongoDB 4.4 与现有部署保持一致；上线长期使用前应制定数据库版本升级和兼容性验证方案。
- 数据库使用 Docker 持久化卷；`/opt/tradingagents/data` 和 `logs` 保存应用数据及日志。没有配置自动备份，应另行安排数据库备份和 EBS 快照。
- EC2 设置 `prevent_destroy`，根盘设置 `delete_on_termination=false`。删除实例后保留磁盘仍会计费；保留磁盘不等于备份。
- 启动脚本仅在首次创建实例时使用，Terraform 忽略已有实例的 user_data 变化。已有实例更新应通过 SSH 上传修改后的文件，再执行 `sudo docker compose up -d`；更换数据库密码必须同步更新数据库内部账号，不能只改 `.env`。
- 公网 IP 改变时更新 `admin_cidr` 并重新 apply。检查失败可查看 `sudo tail -n 100 /var/log/cloud-init-output.log` 和 `sudo docker compose logs --tail 100`（在应用目录执行）。
- T3 实例 CPU 积分为 standard，避免额外积分费用；持续高负载耗尽积分后会限速。M7i-flex 不使用该积分配置。

参考：[Lightsail 区域列表（不包含大阪）](https://docs.aws.amazon.com/lightsail/latest/userguide/understanding-regions-and-availability-zones-in-amazon-lightsail.html)。
