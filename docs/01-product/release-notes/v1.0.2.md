# TradingAgents-CN Pro v1.0.2 发布说明

**发布日期**: 2026-01-06  
**版本类型**: Bug 修复版本

---

## 🔥 重要修复

### 1. 修复 Session 时区和异步问题

**问题**:
- 用户登录后一段时间自动退出
- 刷新 token 时返回 401 错误
- 错误日志：`can't compare offset-naive and offset-aware datetimes`

**修复**:
- ✅ `SessionService` 使用同步数据库连接 (`get_mongo_db_sync()`)
- ✅ 统一使用 UTC 时间（naive datetime）存储和比较
- ✅ 修复所有时间相关方法的时区问题

**影响文件**:
- `app/services/session_service.py` (新增)
- `tests/test_session_management.py` (新增)

---

### 2. 修复 Cookie 认证问题

**问题**:
- 用户登录成功后立即被重定向回登录页
- Axios 默认不发送 Cookie

**修复**:
- ✅ 在 `frontend/src/api/request.ts` 中添加 `withCredentials: true`
- ✅ 允许 Axios 发送和接收 Cookie
- ✅ 支持跨域请求携带 Cookie

**影响文件**:
- `frontend/src/api/request.ts`

---

### 3. 修复代理配置问题

**问题**:
- 代理配置保存后未生效
- 前端显示的代理状态不准确
- 配置优先级混乱

**修复**:
- ✅ `ConfigProvider` 优先从数据库读取代理配置
- ✅ 添加配置缓存机制（5分钟 TTL）
- ✅ 前端实时显示当前生效的代理配置
- ✅ 统一配置优先级：数据库 > 环境变量 > 代码默认值

**影响文件**:
- `app/services/config_provider.py`
- `app/services/config_service.py`
- `app/core/config.py`
- `app/core/config_bridge.py`
- `frontend/src/views/Settings/ConfigManagement.vue`

---

## 📝 新增文档

### 认证相关
- `docs/HYBRID_AUTH.md` - 混合认证方案文档
- `docs/TROUBLESHOOTING_AUTH.md` - 认证问题排查指南
- `docs/fixes/SESSION_TIMEZONE_FIX.md` - Session 时区问题修复文档

### 代理配置相关
- `docs/troubleshooting/proxy-configuration-fix.md` - 代理配置修复文档
- `docs/troubleshooting/proxy-fix-checklist.md` - 代理修复检查清单
- `PROXY_FIX_REPORT.md` - 代理修复报告
- `PROXY_FIX_SUMMARY.md` - 代理修复总结

---

## 🧪 新增测试

- `tests/test_cookie_auth.html` - Cookie 认证测试页面
- `tests/test_hybrid_auth.py` - 混合认证测试脚本
- `tests/test_session_management.py` - Session 管理测试
- `tests/test_proxy_configuration.py` - 代理配置测试
- `scripts/verify_proxy_fix.py` - 代理修复验证脚本

---

## 🔧 其他改进

- 更新 `requirements.txt` 添加必要依赖
- 优化便携版打包脚本
- 更新 NSIS 安装程序配置
- 更新数据库配置导出文件

---

## 📦 发布产物

### 1. 便携版
- **文件**: `TradingAgentsCN-Portable-1.0.2-20260106-074811.zip`
- **大小**: 477.45 MB
- **说明**: 解压即用，无需安装

### 2. Windows 安装包
- **文件**: `TradingAgentsCNSetup-1.0.2.exe`
- **大小**: 452.82 MB
- **说明**: 标准 Windows 安装程序

---

## 🚀 升级指南

### 从 v1.0.1 升级

1. **清除旧的 Session 数据**（重要！）

   ```javascript
   // 在 MongoDB 中执行
   db.user_sessions.deleteMany({})
   ```

2. **更新代码**

   ```bash
   git pull
   ```

3. **更新依赖**

   ```bash
   pip install -r requirements.txt
   cd frontend
   yarn install
   ```

4. **重启服务**

   ```bash
   # 停止所有服务
   # 重新启动
   python app/main.py
   ```

5. **清除浏览器缓存**

   - F12 → Application → Clear storage → Clear site data

---

## ⚠️ 重要提示

1. **Session 数据不兼容**: 旧版本的 session 数据使用了带时区的时间，必须清除后才能正常使用
2. **浏览器缓存**: 建议清除浏览器缓存以确保前端更新生效
3. **代理配置**: 如果之前配置了代理，请在升级后重新检查代理设置

---

## 🐛 已知问题

无

---

## 📞 技术支持

如有问题，请查看：
- 认证问题：`docs/TROUBLESHOOTING_AUTH.md`
- 代理配置：`docs/troubleshooting/proxy-configuration-fix.md`
- Session 问题：`docs/fixes/SESSION_TIMEZONE_FIX.md`

---

**完整更新日志**: [GitHub Commits](https://github.com/your-repo/commits/v1.0.2)

