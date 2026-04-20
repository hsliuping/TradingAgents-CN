<template>
  <div class="news-dialog">
    <!-- 标题栏 -->
    <div class="dialog-header">
      <h3 class="title">AI 新闻解读</h3>
      <span class="source">{{ news.source }} · {{ news.time }}</span>
      <span class="tag">{{ news.model }}</span>
    </div>

    <!-- 内容区 -->
    <div class="content-wrapper">
      <!-- 核心概念 -->
      <div class="section">
        <h4 class="section-title">核心产业链概念分析</h4>
        <div class="concept-content">
          <p>{{ conceptText }}</p>
          <ol class="concept-list">
            <li v-for="(item, index) in concepts" :key="index" class="concept-item">
              <strong>{{ item.name }}</strong>：{{ item.desc }}
            </li>
          </ol>
        </div>
      </div>

      <!-- 龙头股推荐 -->
      <div class="section">
        <h4 class="section-title">相关龙头个股推荐（A股/港股）</h4>
        <div class="stock-table">
          <table>
            <thead>
              <tr>
                <th>股票名称</th>
                <th>代码</th>
                <th>关联理由</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(stock, index) in stocks" :key="index">
                <td>{{ stock.name }}</td>
                <td>{{ stock.code }}</td>
                <td class="reason">{{ stock.reason }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 提示信息 -->
      <div class="tip">
        <i class="el-icon el-icon-warning"></i>
        <span>提示：上述公司均在各自细分领域具备“AI+能源”深度融合的技术积累与商业化落地能力，符合国家能源局强调的“科技创新驱动新质生产力”的发展方向。</span>
      </div>
    </div>

    <!-- 关闭按钮 -->
    <div class="close-btn" @click="$emit('close')">
      关闭
    </div>
  </div>
</template>

<script>
export default {
  name: 'NewsInterpretation',
  props: {
    news: {
      type: Object,
      required: true
    },
    concepts: {
      type: Array,
      default: () => []
    },
    stocks: {
      type: Array,
      default: () => []
    }
  },
  computed: {
    conceptText() {
      return this.news.conceptText || '';
    }
  }
}
</script>

<style scoped>
.news-dialog {
  width: 90%;
  max-width: 800px;
  margin: 20px auto;
  background: #f8f9fa;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  overflow: hidden;
}

.dialog-header {
  padding: 20px 24px;
  background: white;
  border-bottom: 1px solid #e9ecef;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title {
  font-size: 18px;
  font-weight: 600;
  color: #1a1a1a;
  margin: 0;
}

.source {
  font-size: 12px;
  color: #6c757d;
  margin-left: 8px;
}

.tag {
  font-size: 12px;
  background: #e3f2fd;
  color: #1976d2;
  padding: 2px 8px;
  border-radius: 4px;
  margin-left: 8px;
}

.content-wrapper {
  padding: 24px;
  background: #ffffff;
}

.section {
  margin-bottom: 24px;
}

.section-title {
  font-size: 16px;
  font-weight: 60 of 16px;
  color: #1a1a1a;
  margin-bottom: 12px;
  border-bottom: 2px solid #2563eb;
  padding-bottom: 4px;
}

.concept-content {
  line-height: 1.6;
  color: #333;
  font-size: 14px;
}

.concept-list {
  margin-top: 12px;
  list-style-type: decimal;
  padding-left: 20px;
}

.concept-item {
  margin: 8px 0;
  font-size: 14px;
}

.stock-table {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
}

.stock-table th,
.stock-table td {
  padding: 12px 16px;
  text-align: left;
  border-bottom: 1px solid #e9ecef;
  font-size: 14px;
}

.stock-table th {
  background-color: #f8f9fa;
  font-weight: 500;
  color: #495057;
}

.stock-table tbody tr:hover {
  background-color: #f1f3f5;
}

.reason {
  background-color: #f8f9fa;
  padding: 8px;
  border-radius: 4px;
  font-size: 13px;
  color: #2563eb;
  word-break: break-word;
}

.tip {
  margin-top: 20px;
  padding: 12px 16px;
  background-color: #f0f8ff;
  border-left: 4px solid #2563eb;
  border-radius: 4px;
  font-size: 13px;
  color: #333;
  display: flex;
  align-items: center;
  gap: 8px;
}

.close-btn {
  padding: 12px 24px;
  background: #2563eb;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  text-align: center;
  margin: 20px auto;
  display: block;
  transition: background 0.2s;
}

.close-btn:hover {
  background: #1d4ed8;
}

/* 响应式 */
@media (max-width: 768px) {
  .news-dialog {
    width: 95%;
    margin: 10px;
    padding: 16px;
  }

  .dialog-header {
    flex-direction: column;
    gap: 8px;
    text-align: center;
  }

  .stock-table th,
  .stock-table td {
    padding: 8px;
    font-size: 13px;
  }
}
</style>