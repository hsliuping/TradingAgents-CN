# 社区版生成报告

- 基线: 398e8638d fix(agents): 断言执行器可选导入自守卫；r10 剔除 Pro 工具与过时测试
- 生成时间: 2026-09-19T07:22:22.018143
- 删除目录: 34
- 删除文件: 98
- 替换文件: 15
- 清单缺失条目: 0
- 源码泄露扫描: 通过

## 后续验证步骤（发布流程执行）
1. 后端 import 自检: env/Scripts/python -c "import app.main"
2. 后端启动 + OpenAPI 路由对比（Pro 路由应全部消失）
3. 前端: npm install && npx vue-tsc --noEmit && npm run build
4. dist 产物泄露扫描（scan_dist_patterns）
5. 运行冒烟: 登录 / 社区路由 200 / Pro 路由 404