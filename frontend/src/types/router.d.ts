import 'vue-router'

// Augment Vue Router's RouteMeta to include app-specific fields
declare module 'vue-router' {
  interface RouteMeta {
    // 页面标题
    title?: string
    // 是否需要认证
    requiresAuth?: boolean
    // 菜单图标名称（与 Element Plus 图标名称一致）
    icon?: string
    // 是否在菜单中隐藏
    hideInMenu?: boolean
    // 页面切换动画名称（用于 <transition name="...">）
    transition?: string
  }
}