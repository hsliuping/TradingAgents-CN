# TradingAgents-CN v0.1.16 部署与运维指南

## 架构组件
- Nginx: 静态文件和反向代理
- FastAPI: 后端服务 (Uvicorn/Gunicorn)
- Redis: 队列与缓存
- MongoDB: 数据存储
- Worker: 任务执行进程

## 参考拓扑
```
[Internet] -> [Nginx] -> [FastAPI] -> [Redis/MongoDB]
                           |-> [Worker x N]
```

## 部署步骤
1. 准备环境
- Python 3.10+
- Node.js 18+
- Redis 6+
- MongoDB 5+

2. 后端部署
- 创建虚拟环境并安装依赖
- 配置环境变量(.env)
- 启动Uvicorn服务

3. 前端部署
- 构建Vue3应用
- 将dist目录部署到Nginx

4. Worker部署
- 配置并启动worker进程
- 建议使用supervisor/systemd进行守护

5. Nginx配置
- 静态文件缓存
- 反代 /api 与 /api/stream
- SSE的缓存与连接保持配置

## 运行维护
- 监控指标：队列长度、任务成功率、API延迟
- 日志归集：后端、Worker、Nginx
- 备份策略：MongoDB定期备份
- 故障演练：Redis/MongoDB节点故障切换

## 灰度与回滚
- 蓝绿部署或金丝雀发布
- 保留Streamlit回退入口
- 回滚流程预案