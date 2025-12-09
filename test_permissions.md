# 权限测试指南

## 修复内容总结

### 1. 侧边栏菜单权限控制
**文件**: `frontend/src/components/Layout/SidebarMenu.vue`

**修改**: 给系统配置和系统管理菜单添加了 `v-if="authStore.isAdmin"` 条件：
```vue
<!-- 系统配置 - 仅管理员可见 -->
<el-sub-menu v-if="authStore.isAdmin" index="/settings-config">
  <template #title>系统配置</template>
  <el-menu-item index="/settings/config">配置管理</el-menu-item>
  <el-menu-item index="/settings/cache">缓存管理</el-menu-item>
</el-sub-menu>

<!-- 系统管理 - 仅管理员可见 -->
<el-sub-menu v-if="authStore.isAdmin" index="/settings-admin">
  <template #title>系统管理</template>
  <el-menu-item index="/settings/database">数据库管理</el-menu-item>
  <el-menu-item index="/settings/logs">操作日志</el-menu-item>
  <el-menu-item index="/settings/system-logs">系统日志</el-menu-item>
  <el-menu-item index="/settings/sync">多数据源同步</el-menu-item>
  <el-menu-item index="/settings/scheduler">定时任务</el-menu-item>
  <el-menu-item index="/settings/usage">使用统计</el-menu-item>
</el-sub-menu>
```

### 2. 路由权限守卫
**文件**: `frontend/src/router/index.ts`

路由守卫已经包含完善的管理员权限检查，普通用户即使手动输入URL也无法访问管理员页面。

## 测试方法

### 1. 清除浏览器缓存
清除浏览器的localStorage和sessionStorage，确保重新获取用户信息：
```javascript
// 在浏览器控制台运行
localStorage.clear()
sessionStorage.clear()
```

### 2. 测试admin用户
1. 使用admin账号登录
2. 登录后应该能在侧边栏"设置"菜单下看到：
   - ✅ 个人设置
   - ✅ 系统配置
   - ✅ 系统管理

### 3. 测试普通用户
1. 使用user1账号登录
2. 登录后应该只能在侧边栏"设置"菜单下看到：
   - ✅ 个人设置
   - ❌ 系统配置（应该隐藏）
   - ❌ 系统管理（应该隐藏）

### 4. 测试直接URL访问
普通用户登录后，尝试直接访问以下URL，应该被重定向并显示权限警告：
- `/settings/config`
- `/settings/database`
- `/settings/logs`
- `/settings/sync`
- `/settings/usage`

## 预期效果

- **admin用户**: 侧边栏显示完整的设置菜单，包括系统配置和系统管理
- **普通用户**: 侧边栏只显示个人设置，系统配置和系统管理完全隐藏

## 调试信息

如果问题仍然存在，请在浏览器控制台检查：
```javascript
// 检查当前用户的认证信息
console.log('用户信息:', useAuthStore().user)
console.log('是否管理员:', useAuthStore().isAdmin)
console.log('角色:', useAuthStore().roles)
```

确保：
1. `useAuthStore().user.is_admin` 为 true (admin) 或 false (普通用户)
2. `useAuthStore().isAdmin` 返回正确的布尔值
3. `useAuthStore().roles` 包含正确的角色信息