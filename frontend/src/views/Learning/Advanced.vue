<template>
  <div class="advanced-courses-page">
    <div class="page-header">
      <h1>🎓 从散户到系统交易者：AI赋能的可进化投资法</h1>
      <p class="subtitle">30节系统课程，按炒股全生命周期组织：发现 → 跟踪 → 持仓 → 复盘 → 扩展</p>
      <div class="header-badges">
        <el-tag type="success" size="default">{{ freeCount }}节免费预览</el-tag>
        <PaidCourseBadge />
      </div>
    </div>

    <!-- 分类筛选提示 -->
    <div v-if="selectedCategoryId" class="category-filter-banner">
      <el-alert
        :closable="true"
        @close="clearCategoryFilter"
        type="info"
        show-icon
      >
        <template #title>
          当前显示：{{ displayedCategories[0]?.name }}
          <el-button 
            type="text" 
            size="small" 
            @click="clearCategoryFilter"
            style="margin-left: 8px"
          >
            查看全部课程
          </el-button>
        </template>
      </el-alert>
    </div>

    <!-- 课程分类列表 -->
    <div class="course-categories">
      <el-card 
        v-for="category in displayedCategories" 
        :key="category.id"
        class="category-card"
        shadow="hover"
      >
        <template #header>
          <div class="card-header">
            <div class="header-left">
              <span class="category-icon">{{ category.icon }}</span>
              <h3>{{ category.name }}</h3>
            </div>
            <el-tag type="success" size="small">{{ category.lessonCount }}课</el-tag>
          </div>
        </template>

        <p class="category-description">{{ category.description }}</p>

        <div class="lessons-list">
          <div 
            v-for="lesson in category.lessons" 
            :key="lesson.id"
            class="lesson-item"
            :class="{ 'lesson-locked': !isFreeLesson(lesson.order) && !hasFullAccess }"
            @click="navigateToLesson(category.id, lesson.id)"
          >
            <div class="lesson-info">
              <span class="lesson-order" :class="{ 'order-free': isFreeLesson(lesson.order), 'order-locked': !isFreeLesson(lesson.order) && !hasFullAccess }">
                {{ isFreeLesson(lesson.order) ? lesson.order : '🔒' }}
              </span>
              <span class="lesson-title">{{ lesson.title }}</span>
            </div>
            <div class="lesson-badges">
              <el-tag v-if="isFreeLesson(lesson.order)" type="success" size="small" effect="plain">免费</el-tag>
              <el-icon class="lesson-arrow"><ArrowRight /></el-icon>
            </div>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 完整版入口卡片（社区版为空壳，不渲染） -->
    <KnowledgePlanetPromotion />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { advancedCourseCategories, isFreeLesson } from '@/config/advancedCourses'
import { useLicenseStore } from '@/stores/license'
import KnowledgePlanetPromotion from '@/components/KnowledgePlanetPromotion.vue'
import PaidCourseBadge from '@/components/PaidCourseBadge.vue'
import { ArrowRight } from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const licenseStore = useLicenseStore()

const hasFullAccess = computed(() => licenseStore.hasLegacyCourseAccess)
const freeCount = computed(() => {
  let count = 0
  for (const cat of advancedCourseCategories) {
    for (const lesson of cat.lessons) {
      if (isFreeLesson(lesson.order)) count++
    }
  }
  return count
})

// 获取URL中的分类参数
const selectedCategoryId = computed(() => route.query.category as string | undefined)

// 过滤显示的课程分类
const displayedCategories = computed(() => {
  if (selectedCategoryId.value) {
    const category = advancedCourseCategories.find(cat => cat.id === selectedCategoryId.value)
    return category ? [category] : advancedCourseCategories
  }
  return advancedCourseCategories
})

const navigateToLesson = (categoryId: string, lessonId: string) => {
  router.push(`/learning/advanced/${categoryId}/${lessonId}`)
}

const clearCategoryFilter = () => {
  router.push('/learning/advanced')
}
</script>

<style scoped lang="scss">
.advanced-courses-page {
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;

  .page-header {
    text-align: center;
    margin-bottom: 48px;
    padding: 40px 20px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 16px;
    color: white;

    h1 {
      font-size: 32px;
      margin-bottom: 12px;
      font-weight: 600;
      line-height: 1.4;
    }

    .subtitle {
      font-size: 16px;
      opacity: 0.9;
      line-height: 1.6;
      margin-bottom: 16px;
    }

    .header-badges {
      display: flex;
      justify-content: center;
      gap: 12px;
    }
  }

  .category-filter-banner {
    margin-bottom: 24px;
  }

  .course-categories {
    .category-card {
      margin-bottom: 24px;
      background: var(--el-fill-color-blank);
      border-color: var(--el-border-color);

      .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;

        .header-left {
          display: flex;
          align-items: center;
          gap: 12px;

          .category-icon {
            font-size: 24px;
          }

          h3 {
            font-size: 20px;
            margin: 0;
            color: var(--el-text-color-primary);
          }
        }
      }

      .category-description {
        font-size: 14px;
        color: var(--el-text-color-regular);
        margin-bottom: 16px;
        line-height: 1.6;
      }

      .lessons-list {
        .lesson-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 12px 16px;
          margin-bottom: 8px;
          border-radius: 8px;
          cursor: pointer;
          transition: all 0.2s ease;
          background: var(--el-fill-color-light);

          &:hover {
            background: var(--el-fill-color);
            transform: translateX(4px);
          }

          &.lesson-locked {
            opacity: 0.7;

            &:hover {
              opacity: 0.85;
              background: var(--el-fill-color);
            }
          }

          .lesson-info {
            display: flex;
            align-items: center;
            gap: 12px;

            .lesson-order {
              display: inline-flex;
              align-items: center;
              justify-content: center;
              width: 28px;
              height: 28px;
              border-radius: 50%;
              background: var(--el-color-primary);
              color: white;
              font-size: 12px;
              font-weight: 600;

              &.order-free {
                background: var(--el-color-success);
              }

              &.order-locked {
                background: var(--el-color-info);
                font-size: 14px;
              }
            }

            .lesson-title {
              font-size: 14px;
              color: var(--el-text-color-primary);
            }
          }

          .lesson-badges {
            display: flex;
            align-items: center;
            gap: 8px;

            .lesson-arrow {
              color: var(--el-text-color-placeholder);
            }
          }
        }
      }
    }
  }
}

// 暗黑模式适配
:global(html.dark) {
  .advanced-courses-page {
    background: #000000 !important;

    .page-header {
      background: #000000 !important;
      border: 1px solid var(--el-border-color-light);
      color: var(--el-text-color-primary);
      
      h1 { color: var(--el-text-color-primary); }
      .subtitle { color: var(--el-text-color-regular); }
    }

    .course-categories .category-card {
      background: #000000 !important;
      border-color: var(--el-border-color) !important;
    }
  }
}

@media (max-width: 768px) {
  .advanced-courses-page {
    padding: 16px;

    .page-header {
      padding: 24px 16px;

      h1 {
        font-size: 24px;
        line-height: 1.4;
      }

      .subtitle {
        font-size: 14px;
      }
    }
  }
}
</style>
