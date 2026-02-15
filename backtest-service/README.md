# 回测服务 (Backtrader)

GPLv3 许可证的 Backtrader 回测引擎，以独立服务运行，通过 HTTP 与主平台通信，避免许可证传染。

## 快速启动

```bash
# 安装依赖
pip install -r requirements.txt

# 确保 MongoDB 已启动且 stock_daily_quotes 有数据

# 启动服务
uvicorn main:app --host 0.0.0.0 --port 8900
```

## Docker

```bash
# 在项目根目录
docker-compose --profile backtest up -d backtest
```

## 端点

- `GET /health` - 健康检查
- `POST /run` - 执行回测，请求体 `{"strategy": {...}}`

## 环境变量

- `MONGO_URI` - MongoDB 连接字符串（需与主平台一致）
- `MONGO_DB` - 数据库名，默认 `tradingagents`
- `PORT` - 服务端口，默认 8900

在 `backtest-service/` 下创建 `.env` 可显式指定 MongoDB 配置，避免被项目根 `.env` 影响。可参考 `.env.example`。
