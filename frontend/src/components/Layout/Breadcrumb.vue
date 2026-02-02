<template>
  <el-breadcrumb separator="/" class="breadcrumb">
    <el-breadcrumb-item
      v-for="item in breadcrumbList"
      :key="item.path"
      :to="item.path"
    >
      {{ item.title }}
    </el-breadcrumb-item>
  </el-breadcrumb>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const breadcrumbList = computed(() => {
  const matched = route.matched.filter(item => item.meta && item.meta.title)
  
  const breadcrumbs = matched.map(item => ({
    path: item.path,
    title: item.meta.title as string
  }))

  // 🔥 模板管理路径已调整，不在设置下面，所以去掉"设置"这个面包屑
  // 如果当前路径包含 templates，过滤掉"设置"标题
  if (route.path.includes('/templates') || route.path.includes('/settings/templates')) {
    return breadcrumbs.filter(item => item.title !== '设置')
  }

  return breadcrumbs
})
</script>

<style lang="scss" scoped>
.breadcrumb {
  font-size: 14px;
}
</style>
