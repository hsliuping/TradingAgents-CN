<template>
  <el-menu
    :default-active="activeMenu"
    :default-openeds="openedMenus"
    :collapse="appStore.sidebarCollapsed"
    :unique-opened="true"
    router
    class="sidebar-menu"
  >
    <template v-for="item in menuItems" :key="item.index">
      <el-menu-item v-if="!item.children && !item.groups" :index="item.index">
        <el-icon v-if="resolveIcon(item.icon)">
          <component :is="resolveIcon(item.icon)" />
        </el-icon>
        <template #title>{{ item.title }}</template>
      </el-menu-item>

      <el-sub-menu v-else :index="item.index">
        <template #title>
          <el-icon v-if="resolveIcon(item.icon)">
            <component :is="resolveIcon(item.icon)" />
          </el-icon>
          <span>{{ item.title }}</span>
        </template>

        <template v-if="item.children">
          <el-menu-item
            v-for="child in item.children"
            :key="child.index"
            :index="child.index"
          >
            {{ child.title }}
          </el-menu-item>
        </template>

        <template v-else-if="item.groups">
          <el-sub-menu
            v-for="group in item.groups"
            :key="group.index"
            :index="group.index"
          >
            <template #title>{{ group.title }}</template>
            <el-menu-item
              v-for="child in group.children"
              :key="child.index"
              :index="child.index"
            >
              {{ child.title }}
            </el-menu-item>
          </el-sub-menu>
        </template>
      </el-sub-menu>
    </template>
  </el-menu>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Component } from 'vue'
import { useRoute } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { routes } from '@/router'
import { useAppStore } from '@/stores/app'
import {
  CreditCard,
  Document,
  InfoFilled,
  List,
  Odometer,
  Reading,
  Search,
  Setting,
  Star,
  TrendCharts
} from '@element-plus/icons-vue'

interface MenuLink {
  index: string
  title: string
  icon?: string
}

interface MenuGroup {
  index: string
  title: string
  children: MenuLink[]
}

interface MenuNode extends MenuLink {
  children?: MenuLink[]
  groups?: MenuGroup[]
}

type RouteMetaValue = string | boolean | undefined

const route = useRoute()
const appStore = useAppStore()

const iconMap: Record<string, Component> = {
  Dashboard: Odometer,
  Odometer,
  Reading,
  TrendCharts,
  Search,
  Star,
  List,
  Document,
  Setting,
  InfoFilled,
  CreditCard
}

const routeMap = new Map(routes.map((routeItem) => [routeItem.path, routeItem]))

const personalSettingsTabs: Record<string, string> = {
  general: '通用设置',
  appearance: '外观设置',
  analysis: '分析偏好',
  notifications: '通知设置',
  security: '安全设置'
}

const resolveIcon = (icon?: string) => (icon ? iconMap[icon] : undefined)

const getRoute = (path: string): RouteRecordRaw | undefined => routeMap.get(path)

const getRouteMetaString = (
  routeItem: RouteRecordRaw | undefined,
  key: 'title' | 'icon'
): string | undefined => {
  const value = routeItem?.meta?.[key] as RouteMetaValue
  return typeof value === 'string' ? value : undefined
}

const getChildRoute = (
  parentPath: string,
  childPath: string
): RouteRecordRaw | undefined => {
  const parentRoute = getRoute(parentPath)
  return parentRoute?.children?.find((child) => child.path === childPath)
}

const createRouteItem = (
  path: string,
  overrides: Partial<MenuLink> = {}
): MenuLink => {
  const routeItem = getRoute(path)
  return {
    index: overrides.index ?? path,
    title: overrides.title ?? getRouteMetaString(routeItem, 'title') ?? path,
    icon: overrides.icon ?? getRouteMetaString(routeItem, 'icon')
  }
}

const createChildRouteItem = (
  parentPath: string,
  childPath: string,
  overrides: Partial<MenuLink> = {}
): MenuLink => {
  const childRoute = getChildRoute(parentPath, childPath)
  const index = `${parentPath}/${childPath}`.replace(/\/+/g, '/')

  return {
    index: overrides.index ?? index,
    title: overrides.title ?? getRouteMetaString(childRoute, 'title') ?? index,
    icon: overrides.icon ?? getRouteMetaString(childRoute, 'icon')
  }
}

const menuItems = computed<MenuNode[]>(() => [
  createRouteItem('/dashboard'),
  createRouteItem('/learning'),
  {
    ...createRouteItem('/analysis'),
    children: [
      createChildRouteItem('/analysis', 'single'),
      createChildRouteItem('/analysis', 'batch'),
      createRouteItem('/reports')
    ]
  },
  createRouteItem('/tasks'),
  createRouteItem('/screening'),
  createRouteItem('/favorites'),
  createRouteItem('/paper'),
  {
    ...createRouteItem('/settings'),
    groups: [
      {
        index: '/settings-personal',
        title: '个人设置',
        children: [
          createRouteItem('/settings', { title: personalSettingsTabs.general }),
          createRouteItem('/settings', {
            index: '/settings?tab=appearance',
            title: personalSettingsTabs.appearance
          }),
          createRouteItem('/settings', {
            index: '/settings?tab=analysis',
            title: personalSettingsTabs.analysis
          }),
          createRouteItem('/settings', {
            index: '/settings?tab=notifications',
            title: personalSettingsTabs.notifications
          }),
          createRouteItem('/settings', {
            index: '/settings?tab=security',
            title: personalSettingsTabs.security
          })
        ]
      },
      {
        index: '/settings-config',
        title: '系统配置',
        children: [
          createChildRouteItem('/settings', 'config'),
          createChildRouteItem('/settings', 'cache')
        ]
      },
      {
        index: '/settings-admin',
        title: '系统管理',
        children: [
          createChildRouteItem('/settings', 'database'),
          createChildRouteItem('/settings', 'logs'),
          createChildRouteItem('/settings', 'system-logs'),
          createChildRouteItem('/settings', 'sync'),
          createChildRouteItem('/settings', 'scheduler'),
          createChildRouteItem('/settings', 'usage')
        ]
      }
    ]
  },
  createRouteItem('/about')
])

const activeMenu = computed(() => {
  if (route.path.startsWith('/reports')) {
    return '/reports'
  }

  if (route.path.startsWith('/learning')) {
    return '/learning'
  }

  if (route.path === '/settings') {
    const currentTab =
      typeof route.query.tab === 'string' ? route.query.tab : 'general'

    if (currentTab in personalSettingsTabs && currentTab !== 'general') {
      return `/settings?tab=${currentTab}`
    }

    return '/settings'
  }

  return route.path
})

const openedMenus = computed(() => {
  if (route.path.startsWith('/analysis') || route.path.startsWith('/reports')) {
    return ['/analysis']
  }

  if (route.path.startsWith('/settings')) {
    if (route.path === '/settings') {
      return ['/settings', '/settings-personal']
    }

    if (
      route.path === '/settings/config' ||
      route.path === '/settings/cache'
    ) {
      return ['/settings', '/settings-config']
    }

    return ['/settings', '/settings-admin']
  }

  return []
})
</script>

<style lang="scss" scoped>
.sidebar-menu {
  border: none;
  height: 100%;

  :deep(.el-menu-item),
  :deep(.el-sub-menu__title) {
    height: 48px;
    line-height: 48px;
  }

  :deep(.el-menu-item.is-active) {
    background-color: var(--el-color-primary-light-9);
    color: var(--el-color-primary);
  }
}
</style>
