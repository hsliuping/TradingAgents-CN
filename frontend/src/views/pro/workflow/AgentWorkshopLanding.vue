<template>
  <div class="agent-workshop-landing-page">
    <section class="hero-section">
      <div class="hero-copy">
        <div class="hero-kicker">Agent 工坊</div>
        <h1>Agent 工坊</h1>
        <p class="hero-description">
          这里先不直接堆列表，而是先给你默认主路径。优先从助手模式进入，用对话快速澄清需求、起草 Agent 并推进迭代；需要更强的结构化控制时，再进入标准工作页。
        </p>
      </div>
      <div class="hero-actions">
        <el-button type="primary" size="large" @click="goToAssistantStudio()">进入助手模式</el-button>
        <el-button size="large" plain @click="goToWorkshopCreate()">进入标准工作页</el-button>
      </div>
    </section>

    <section class="entry-section">
      <div class="section-header">
        <h2>选择进入方式</h2>
        <span>按照当前任务目标进入最合适的工作模式。</span>
      </div>

      <div class="entry-grid">
        <el-card shadow="never" class="entry-card primary-entry-card">
          <div class="entry-card-head">
            <el-tag type="success" effect="dark" size="small">推荐主路径</el-tag>
            <span class="entry-card-kicker">助手模式</span>
          </div>
          <div class="entry-card-title">助手模式</div>
          <p class="entry-card-description">
            先把想法聊清楚，再让助手起草规格、推进迭代并查看评估结果。这条路径更轻、更快，也更适合作为 Agent 工坊的默认入口。
          </p>
          <div class="entry-card-points">
            <span>对话澄清</span>
            <span>快速起草</span>
            <span>助手迭代</span>
          </div>
          <div class="entry-card-actions">
            <el-button type="primary" @click="goToAssistantStudio()">进入助手模式</el-button>
          </div>
        </el-card>

        <el-card shadow="never" class="entry-card standard-entry-card">
          <div class="entry-card-head">
            <el-tag type="primary" effect="plain" size="small">结构化流程</el-tag>
            <span class="entry-card-kicker">标准流程</span>
          </div>
          <div class="entry-card-title">标准工作页</div>
          <p class="entry-card-description">
            从需求、规格、版本、评估到发布按步骤推进，更适合正式搭建一个可持续迭代的 Agent。
          </p>
          <div class="entry-card-points">
            <span>规格编辑</span>
            <span>版本生成</span>
            <span>评估发布</span>
          </div>
          <div class="entry-card-actions">
            <el-button plain @click="goToWorkshopCreate()">进入标准工作页</el-button>
          </div>
        </el-card>

        <el-card shadow="never" class="entry-card management-entry-card">
          <div class="entry-card-head">
            <el-tag type="info" effect="plain" size="small">资产视图</el-tag>
            <span class="entry-card-kicker">Management</span>
          </div>
          <div class="entry-card-title">Agent 管理列表</div>
          <p class="entry-card-description">
            已经有草稿、规格或测试版本时，从这里统一查看进行中的会话和已沉淀的 Agent 资产。
          </p>
          <div class="entry-card-points">
            <span>草稿会话</span>
            <span>规格列表</span>
            <span>状态筛选</span>
          </div>
          <div class="entry-card-actions">
            <el-button @click="goToManager()">打开管理列表</el-button>
          </div>
        </el-card>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

const goToWorkshopCreate = () => {
  router.push('/workflow/agent-workshop/create')
}

const goToAssistantStudio = () => {
  router.push('/workflow/agent-studio')
}

const goToManager = () => {
  router.push('/workflow/agent-workshop/manage')
}
</script>

<style scoped lang="scss">
.agent-workshop-landing-page {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.hero-section {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  padding: 28px;
  border-radius: 24px;
  background:
    radial-gradient(circle at top left, rgba(14, 116, 144, 0.14), transparent 38%),
    linear-gradient(135deg, #f7fbfa, #eef6f3);
  border: 1px solid rgba(18, 63, 57, 0.08);
}

.hero-copy {
  max-width: 760px;

  h1 {
    margin: 10px 0 0;
    font-size: 34px;
    color: #123f39;
  }
}

.hero-kicker {
  color: #0e7490;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.hero-description {
  margin: 16px 0 0;
  color: #41514d;
  line-height: 1.8;
  font-size: 15px;
}

.hero-actions,
.entry-card-head,
.entry-card-actions,
.entry-card-points,
.section-header {
  display: flex;
  align-items: center;
}

.hero-actions {
  gap: 12px;
  align-self: flex-end;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.section-header {
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
  flex-wrap: wrap;

  h2 {
    margin: 0;
    font-size: 18px;
    color: #123f39;
  }

  span {
    color: var(--el-text-color-secondary);
    font-size: 13px;
  }
}

.entry-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.entry-card {
  border-radius: 20px;
  border: 1px solid rgba(18, 63, 57, 0.08);
}

.primary-entry-card {
  background: linear-gradient(135deg, rgba(14, 116, 144, 0.08), rgba(18, 63, 57, 0.02));
}

.standard-entry-card {
  background: linear-gradient(135deg, rgba(234, 179, 8, 0.1), rgba(255, 255, 255, 0.72));
}

.management-entry-card {
  background: linear-gradient(135deg, rgba(100, 116, 139, 0.09), rgba(255, 255, 255, 0.78));
}

.entry-card-head {
  justify-content: space-between;
  gap: 12px;
}

.entry-card-kicker {
  color: #70837d;
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.entry-card-title {
  margin-top: 16px;
  color: #123f39;
  font-size: 24px;
  font-weight: 700;
}

.entry-card-description {
  margin: 12px 0 0;
  min-height: 78px;
  color: #4e5b57;
  line-height: 1.75;
}

.entry-card-points {
  gap: 8px;
  margin-top: 16px;
  flex-wrap: wrap;

  span {
    padding: 6px 10px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.68);
    color: #3d4c48;
    font-size: 12px;
  }
}

.entry-card-actions {
  justify-content: flex-start;
  margin-top: 18px;
}

@media (max-width: 1100px) {
  .hero-section {
    flex-direction: column;
  }

  .hero-actions {
    align-self: flex-start;
    justify-content: flex-start;
  }

  .entry-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .agent-workshop-landing-page {
    padding: 16px;
  }

  .hero-section {
    padding: 20px;
  }

  .hero-copy h1 {
    font-size: 28px;
  }

  .hero-actions {
    width: 100%;

    :deep(.el-button) {
      width: 100%;
    }
  }
}
</style>