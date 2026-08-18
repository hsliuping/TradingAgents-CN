@echo off
set "JDYUN_AUTH_PASS=Test@123456"
set "JDYUN_BACKEND_TARGET=http://127.0.0.1:8082"
set "JDYUN_INJECT_AUTH=jcloud-ugidvcp:8437F13DABE87D0BC1D4DCCD4739C5A7"
cd /d c:\TradingAgentsCN\frontend
node mock-jdyun-gateway.mjs
