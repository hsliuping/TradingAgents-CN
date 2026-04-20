<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2 class="title">晚间总结</h2>
        <div class="subtitle">复盘要点、主线演化与次日关注（当前为前端占位数据）</div>
      </div>
      <div class="actions">
        <el-date-picker v-model="date" type="date" />
        <el-button type="primary" @click="generate">生成</el-button>
      </div>
    </div>

    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>复盘报告</span>
          <el-tag type="info" size="small">{{ dateText }}</el-tag>
        </div>
      </template>

      <el-empty v-if="!report" description="点击“生成”得到晚间复盘内容" />
      <div v-else class="report">
        <el-alert :title="report.headline" type="info" show-icon :closable="false" />

        <el-row :gutter="12" style="margin-top: 12px">
          <el-col :xs="24" :md="12">
            <el-card shadow="never" class="block">
              <div class="block-title">今日主线</div>
              <ul class="list">
                <li v-for="x in report.mainlines" :key="x">{{ x }}</li>
              </ul>
            </el-card>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-card shadow="never" class="block">
              <div class="block-title">风险提示</div>
              <ul class="list">
                <li v-for="x in report.risks" :key="x">{{ x }}</li>
              </ul>
            </el-card>
          </el-col>
        </el-row>

        <el-card shadow="never" class="block" style="margin-top: 12px">
          <div class="block-title">明日关注清单</div>
          <el-table :data="report.watch" style="width: 100%" row-key="code">
            <el-table-column prop="code" label="代码" width="120" />
            <el-table-column prop="name" label="名称" width="160" />
            <el-table-column prop="reason" label="关注理由" min-width="260" />
            <el-table-column prop="plan" label="观察计划" width="220" />
          </el-table>
        </el-card>

        <el-alert
          class="hint"
          type="warning"
          :closable="false"
          show-icon
          title="说明：后续接入后端后，可基于实际交易数据与新闻源自动生成复盘报告，并支持导出与订阅推送。"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'

const date = ref<Date>(new Date())

type Report = {
  headline: string
  mainlines: string[]
  risks: string[]
  watch: Array<{ code: string; name: string; reason: string; plan: string }>
}

const report = ref<Report | null>(null)

const dateText = computed(() => dayjs(date.value).format('YYYY-MM-DD'))

function generate() {
  report.value = {
    headline: '市场延续结构性行情，主线分化但核心抱团仍在。',
    mainlines: ['主线A：趋势延续，强者恒强', '主线B：轮动加快，分支分化', '防御线：高股息走强，风险偏好略降'],
    risks: ['情绪高位回落风险，谨慎追涨', '盘后消息扰动导致次日高开回落', '成交额萎缩时注意缩量假突破'],
    watch: [
      { code: '300750', name: '示例公司A', reason: '趋势结构完整，主线核心', plan: '观察回踩承接与量能' },
      { code: '688788', name: '示例公司B', reason: '分支补涨预期，弹性较高', plan: '关注开盘冲高回落形态' }
    ]
  }
  ElMessage.success('已生成（占位内容）')
}
</script>

<style lang="scss" scoped>
.page {
  .page-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 16px;
  }
  .title {
    margin: 0;
    font-size: 22px;
    font-weight: 700;
    color: var(--el-text-color-primary);
  }
  .subtitle {
    margin-top: 6px;
    font-size: 13px;
    color: var(--el-text-color-regular);
  }
  .actions {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }

  .report {
    display: flex;
    flex-direction: column;
  }
  .block {
    :deep(.el-card__body) {
      padding: 12px 14px;
    }
  }
  .block-title {
    font-weight: 700;
    color: var(--el-text-color-primary);
    margin-bottom: 6px;
  }
  .list {
    margin: 0;
    padding-left: 18px;
    color: var(--el-text-color-regular);
    font-size: 13px;
    line-height: 1.8;
  }
  .hint {
    margin-top: 12px;
  }
}
</style>
