<template>
  <div class="advanced-courses-page">
    <div class="page-header">
      <h1>🎓 从散户到系统交易者：AI赋能的可进化投资法</h1>
      <p class="subtitle">完整的投资系统构建课程，24节精心设计的课程，涵盖从基础概念到实战应用的完整投资闭环</p>
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
            @click="navigateToLesson(category.id, lesson.id)"
          >
            <div class="lesson-info">
              <span class="lesson-order">{{ lesson.order }}</span>
              <span class="lesson-title">{{ lesson.title }}</span>
            </div>
            <el-icon class="lesson-arrow"><ArrowRight /></el-icon>
          </div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { advancedCourseCategories } from '@/config/advancedCourses'
import { ArrowRight } from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()

// 获取URL中的分类参数
const selectedCategoryId = computed(() => route.query.category as string | undefined)

// 过滤显示的课程分类（如果有选择，只显示该分类）
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

// 清除分类筛选
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
            }

            .lesson-title {
              font-size: 14px;
              color: var(--el-text-color-primary);
            }
          }

          .lesson-arrow {
            color: var(--el-text-color-placeholder);
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

