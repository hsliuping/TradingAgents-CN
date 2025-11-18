<template>
  <div class="learning-center">
    <div class="learning-header">
      <h1>📚 学习中心</h1>
      <p class="subtitle">了解AI、大模型和智能股票分析</p>
    </div>

    <el-row :gutter="20" class="learning-categories">
      <!-- AI基础知识 -->
      <el-col :xs="24" :sm="12" :md="8" :lg="6">
        <el-card class="category-card" shadow="hover" @click="navigateTo('ai-basics')">
          <div class="card-icon">🤖</div>
          <h3>AI基础知识</h3>
          <p>什么是AI？什么是大模型？了解人工智能的基本概念</p>
          <el-tag type="primary" size="small">1篇文章</el-tag>
        </el-card>
      </el-col>

      <!-- 提示词工程 -->
      <el-col :xs="24" :sm="12" :md="8" :lg="6">
        <el-card class="category-card" shadow="hover" @click="navigateTo('prompt-engineering')">
          <div class="card-icon">✍️</div>
          <h3>提示词工程</h3>
          <p>学习如何编写有效的提示词，让AI更好地理解你的需求</p>
          <el-tag type="success" size="small">2篇文章</el-tag>
        </el-card>
      </el-col>

      <!-- 模型选择指南 -->
      <el-col :xs="24" :sm="12" :md="8" :lg="6">
        <el-card class="category-card" shadow="hover" @click="navigateTo('model-selection')">
          <div class="card-icon">🎯</div>
          <h3>模型选择指南</h3>
          <p>了解不同大模型的特点，选择最适合你的模型</p>
          <el-tag type="warning" size="small">1篇文章</el-tag>
        </el-card>
      </el-col>

      <!-- AI分析股票原理 -->
      <el-col :xs="24" :sm="12" :md="8" :lg="6">
        <el-card class="category-card" shadow="hover" @click="navigateTo('analysis-principles')">
          <div class="card-icon">📊</div>
          <h3>AI分析股票原理</h3>
          <p>深入了解多智能体如何协作分析股票</p>
          <el-tag type="info" size="small">1篇文章</el-tag>
        </el-card>
      </el-col>

      <!-- 风险与局限性 -->
      <el-col :xs="24" :sm="12" :md="8" :lg="6">
        <el-card class="category-card" shadow="hover" @click="navigateTo('risks-limitations')">
          <div class="card-icon">⚠️</div>
          <h3>风险与局限性</h3>
          <p>了解AI的潜在问题和正确使用方式</p>
          <el-tag type="danger" size="small">1篇文章</el-tag>
        </el-card>
      </el-col>

      <!-- 源项目与论文 -->
      <el-col :xs="24" :sm="12" :md="8" :lg="6">
        <el-card class="category-card" shadow="hover" @click="navigateTo('resources')">
          <div class="card-icon">📖</div>
          <h3>源项目与论文</h3>
          <p>TradingAgents项目介绍和学术论文资源</p>
          <el-tag type="primary" size="small">2篇文章</el-tag>
        </el-card>
      </el-col>

      <!-- 实战教程 -->
      <el-col :xs="24" :sm="12" :md="8" :lg="6">
        <el-card class="category-card" shadow="hover" @click="navigateTo('tutorials')">
          <div class="card-icon">🎓</div>
          <h3>实战教程</h3>
          <p>通过实际案例学习如何使用本工具</p>
          <el-tag type="success" size="small">2篇文章</el-tag>
        </el-card>
      </el-col>

      <!-- 常见问题 -->
      <el-col :xs="24" :sm="12" :md="8" :lg="6">
        <el-card class="category-card" shadow="hover" @click="navigateTo('faq')">
          <div class="card-icon">❓</div>
          <h3>常见问题</h3>
          <p>快速找到常见问题的答案</p>
          <el-tag type="info" size="small">1篇文章</el-tag>
        </el-card>
      </el-col>
    </el-row>

    <!-- 推荐文章 -->
    <div class="recommended-section">
      <h2>🌟 推荐阅读</h2>
      <el-row :gutter="20">
        <el-col :xs="24" :sm="12" :md="8" v-for="article in recommendedArticles" :key="article.id">
          <el-card class="article-card" shadow="hover" @click="openArticle(article.id)">
            <div class="article-meta">
              <el-tag :type="article.tagType" size="small">{{ article.category }}</el-tag>
              <span class="read-time">{{ article.readTime }}</span>
            </div>
            <h4>{{ article.title }}</h4>
            <p>{{ article.description }}</p>
          </el-card>
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

// 为 Element Plus Tag 的 type 属性定义允许的联合类型，避免模板类型不匹配
type TagType = 'primary' | 'success' | 'warning' | 'info' | 'danger'

interface RecommendedArticle {
  id: string
  category: string
  tagType: TagType
  title: string
  description: string
  readTime: string
}

// 推荐文章
const recommendedArticles = ref<RecommendedArticle[]>([
  {
    id: 'what-is-llm',
    category: 'AI基础',
    tagType: 'primary',
    title: '什么是大语言模型（LLM）？',
    description: '从零开始了解大语言模型的基本概念和工作原理',
    readTime: '10分钟'
  },
  {
    id: 'multi-agent-system',
    category: 'AI分析',
    tagType: 'info',
    title: '多智能体系统详解',
    description: '了解本工具如何通过多个AI智能体协作分析股票',
    readTime: '15分钟'
  },
  {
    id: 'best-practices',
    category: '提示词',
    tagType: 'success',
    title: '提示词工程最佳实践',
    description: '学习如何编写高质量的提示词，提升AI分析效果',
    readTime: '12分钟'
  }
])

const navigateTo = (category: string) => {
  router.push(`/learning/${category}`)
}

const openArticle = (articleId: string) => {
  // 外链文章直接在新标签打开
  const externalMap: Record<string, string> = {
    'getting-started': 'https://mp.weixin.qq.com/s/uAk4RevdJHMuMvlqpdGUEw',
    'usage-guide-preview': 'https://mp.weixin.qq.com/s/ppsYiBncynxlsfKFG8uEbw'
  }
  const external = externalMap[articleId]
  if (external) {
    window.open(external, '_blank')
    return
  }
  router.push(`/learning/article/${articleId}`)
}
</script>

<style scoped lang="scss">
.learning-center {
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;

  .learning-header {
    text-align: center;
    margin-bottom: 48px;
    padding: 40px 20px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 16px;
    color: white;

    h1 {
      font-size: 36px;
      margin-bottom: 12px;
      font-weight: 600;
    }

    .subtitle {
      font-size: 18px;
      opacity: 0.9;
    }
  }

  .learning-categories {
    margin-bottom: 48px;

    .category-card {
      cursor: pointer;
      transition: all 0.3s ease;
      height: 220px;
      margin-bottom: 20px;
      background: var(--el-fill-color-blank);
      border-color: var(--el-border-color);

      &:hover {
        transform: translateY(-8px);
        box-shadow: 0 12px 24px rgba(0, 0, 0, 0.15);
      }

      .card-icon {
        font-size: 48px;
        text-align: center;
        margin-bottom: 16px;
      }

      h3 {
        font-size: 18px;
        margin-bottom: 12px;
        color: var(--el-text-color-primary);
      }

      p {
        font-size: 14px;
        color: var(--el-text-color-regular);
        margin-bottom: 16px;
        line-height: 1.6;
        min-height: 60px;
      }

      .el-tag {
        margin-top: 8px;
      }
    }
  }

  .recommended-section {
    margin-top: 48px;

    h2 {
      font-size: 24px;
      margin-bottom: 24px;
      color: var(--el-text-color-primary);
    }

    .article-card {
      cursor: pointer;
      transition: all 0.3s ease;
      margin-bottom: 20px;
      height: 180px;
      background: var(--el-fill-color-blank);
      border-color: var(--el-border-color);

      &:hover {
        transform: translateY(-4px);
        box-shadow: 0 8px 16px rgba(0, 0, 0, 0.1);
      }

      .article-meta {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;

        .read-time {
          font-size: 12px;
          color: var(--el-text-color-secondary);
        }
      }

      h4 {
        font-size: 16px;
        margin-bottom: 8px;
        color: var(--el-text-color-primary);
        font-weight: 600;
      }

      p {
        font-size: 14px;
        color: var(--el-text-color-regular);
        line-height: 1.6;
      }
    }
  }
}

// 暗黑模式样式
:global(html.dark) {
  .learning-center {
    background: #000000 !important;

    .learning-header {
      background: #000000 !important;
      border: 1px solid var(--el-border-color-light);
      color: var(--el-text-color-primary);
      h1 { color: var(--el-text-color-primary); }
      .subtitle { color: var(--el-text-color-regular); }
    }

    .learning-categories .category-card,
    .recommended-section .article-card {
      background: #000000 !important;
      border-color: var(--el-border-color) !important;
    }

    .learning-categories .category-card h3,
    .recommended-section h2,
    .recommended-section .article-card h4,
    .recommended-section .article-card p,
    .recommended-section .article-card .read-time {
      color: var(--el-text-color-primary) !important;
    }

    .recommended-section .article-card p,
    .learning-categories .category-card p,
    .recommended-section .article-card .read-time {
      color: var(--el-text-color-regular) !important;
    }
  }
}

@media (max-width: 768px) {
  .learning-center {
    padding: 16px;

    .learning-header {
      padding: 24px 16px;

      h1 {
        font-size: 28px;
      }

      .subtitle {
        font-size: 16px;
      }
    }
  }
}
</style>

