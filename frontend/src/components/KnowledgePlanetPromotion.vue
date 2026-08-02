<template>
  <div class="knowledge-planet-promotion">
    <div class="promo-header">
      <div class="promo-icon">🌍</div>
      <h2>解锁全部 30 节课程</h2>
      <p class="promo-subtitle">加入知识星球，获取完整课程 + 内部交流社群</p>
    </div>

    <div class="promo-body">
      <div class="features-grid">
        <div class="feature-item">
          <div class="feature-icon">📚</div>
          <div class="feature-text">
            <h4>完整 30 节课程</h4>
            <p>从发现到跟踪、持仓、复盘、扩展，涵盖炒股全生命周期</p>
          </div>
        </div>
        <div class="feature-item">
          <div class="feature-icon">🔄</div>
          <div class="feature-text">
            <h4>持续更新</h4>
            <p>课程内容随平台功能迭代持续更新，一次付费，长期有效</p>
          </div>
        </div>
        <div class="feature-item">
          <div class="feature-icon">💬</div>
          <div class="feature-text">
            <h4>内部交流社群</h4>
            <p>与其他学员交流实战经验，星主定期答疑解惑</p>
          </div>
        </div>
        <div class="feature-item">
          <div class="feature-icon">🎯</div>
          <div class="feature-text">
            <h4>实战案例拆解</h4>
            <p>短线、中长线两种风格的完整案例，学了就能用</p>
          </div>
        </div>
      </div>

      <div class="pricing-section">
        <div class="price-card">
          <div class="price-label">年费会员</div>
          <div class="price-amount">
            <span class="currency">¥</span>
            <span class="number">200</span>
            <span class="period">/年</span>
          </div>
          <div class="price-note">每天不到 6 毛钱</div>
        </div>
      </div>

      <!-- 二维码占位：替换为真实知识星球二维码 -->
      <div class="qrcode-section">
        <div class="qrcode-placeholder">
          <el-icon size="48"><PictureFilled /></el-icon>
          <p>扫码加入知识星球</p>
          <p class="qrcode-hint">（请替换为真实二维码图片）</p>
        </div>
      </div>

      <div class="preview-note">
        <el-icon><InfoFilled /></el-icon>
        <span>前 {{ freeCount }} 节课免费预览中，无需付费即可学习</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { PictureFilled, InfoFilled } from '@element-plus/icons-vue'
import { FREE_LESSON_COUNT } from '@/config/advancedCourses'

const freeCount = FREE_LESSON_COUNT
</script>

<style scoped lang="scss">
.knowledge-planet-promotion {
  max-width: 800px;
  margin: 0 auto;
  padding: 40px 24px;

  .promo-header {
    text-align: center;
    margin-bottom: 32px;

    .promo-icon {
      font-size: 56px;
      margin-bottom: 16px;
    }

    h2 {
      font-size: 24px;
      color: var(--el-text-color-primary);
      margin: 0 0 8px 0;
      font-weight: 600;
    }

    .promo-subtitle {
      font-size: 15px;
      color: var(--el-text-color-regular);
      margin: 0;
    }
  }

  .promo-body {
    .features-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
      margin-bottom: 32px;

      @media (max-width: 600px) {
        grid-template-columns: 1fr;
      }
    }

    .feature-item {
      display: flex;
      align-items: flex-start;
      padding: 16px;
      background: var(--el-fill-color-light);
      border-radius: 10px;
      gap: 12px;

      .feature-icon {
        font-size: 28px;
        flex-shrink: 0;
        width: 40px;
        text-align: center;
      }

      .feature-text {
        h4 {
          font-size: 15px;
          color: var(--el-text-color-primary);
          margin: 0 0 4px 0;
          font-weight: 600;
        }

        p {
          font-size: 13px;
          color: var(--el-text-color-regular);
          margin: 0;
          line-height: 1.5;
        }
      }
    }

    .pricing-section {
      text-align: center;
      margin-bottom: 24px;

      .price-card {
        display: inline-block;
        padding: 20px 40px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 12px;
        color: white;

        .price-label {
          font-size: 14px;
          opacity: 0.85;
          margin-bottom: 4px;
        }

        .price-amount {
          .currency {
            font-size: 20px;
            vertical-align: top;
            margin-right: 2px;
          }

          .number {
            font-size: 48px;
            font-weight: 700;
            line-height: 1;
          }

          .period {
            font-size: 16px;
            opacity: 0.85;
          }
        }

        .price-note {
          font-size: 13px;
          opacity: 0.75;
          margin-top: 4px;
        }
      }
    }

    .qrcode-section {
      text-align: center;
      margin-bottom: 24px;

      .qrcode-placeholder {
        display: inline-flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        width: 200px;
        height: 200px;
        border: 2px dashed var(--el-border-color);
        border-radius: 12px;
        color: var(--el-text-color-placeholder);

        p {
          margin: 4px 0 0 0;
          font-size: 14px;
        }

        .qrcode-hint {
          font-size: 12px;
          opacity: 0.6;
        }
      }
    }

    .preview-note {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      padding: 10px 16px;
      background: var(--el-color-success-light-9);
      border-radius: 8px;
      font-size: 13px;
      color: var(--el-color-success);
    }
  }
}

// 暗黑模式
:global(html.dark) {
  .knowledge-planet-promotion {
    .feature-item {
      background: var(--el-fill-color);
    }

    .qrcode-placeholder {
      border-color: var(--el-border-color);
    }
  }
}
</style>
