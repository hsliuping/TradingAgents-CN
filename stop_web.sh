#!/bin/bash
# 停止前端 Web 服务脚本

set -e  # 遇到错误时退出（可选）

echo "🛑 开始停止前端 Web 服务..."

# 停止 Vite 开发服务器
echo "1️⃣ 停止 Vite 开发服务器..."
pkill -f "vite" 2>/dev/null && echo "   ✅ 已停止 Vite 进程" || echo "   ⚠️ 没有找到运行中的 Vite 进程"

# 停止 npm run dev 进程
echo "2️⃣ 停止 npm run dev 进程..."
pkill -f "npm run dev" 2>/dev/null && echo "   ✅ 已停止 npm run dev 进程" || echo "   ⚠️ 没有找到运行中的 npm run dev 进程"

# 停止 node 进程（前端相关）
echo "3️⃣ 停止前端 Node.js 进程..."
pkill -f "node.*frontend" 2>/dev/null && echo "   ✅ 已停止前端 Node.js 进程" || echo "   ⚠️ 没有找到运行中的前端 Node.js 进程"

# 检查并强制释放端口 3000
echo "4️⃣ 检查端口 3000..."
PORT_PID=$(lsof -ti:3000 2>/dev/null)
if [ -n "$PORT_PID" ]; then
    echo "   ⚠️ 端口 3000 被进程 $PORT_PID 占用，强制终止..."
    kill -9 $PORT_PID 2>/dev/null && echo "   ✅ 已释放端口 3000" || echo "   ❌ 无法释放端口 3000"
else
    echo "   ✅ 端口 3000 已空闲"
fi

# 等待进程完全终止
sleep 1

# 最终验证
echo "5️⃣ 最终验证..."
if lsof -ti:3000 >/dev/null 2>&1; then
    echo "   ❌ 端口 3000 仍被占用"
    exit 1
else
    echo "   ✅ 端口 3000 确认空闲"
fi

if pgrep -f "vite|npm run dev" >/dev/null 2>&1; then
    echo "   ⚠️ 仍有相关进程运行"
    pgrep -fl "vite|npm run dev"
else
    echo "   ✅ 所有前端服务已停止"
fi

echo ""
echo "🎉 前端 Web 服务停止完成！"
