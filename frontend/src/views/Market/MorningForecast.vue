<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2 class="title">早盘预测</h2>
        <div class="subtitle">开盘前的情景推演与关键观察点（当前为前端占位数据）</div>
      </div>
      <div class="actions">
        <el-button type="primary" @click="generate">生成</el-button>
      </div>
    </div>

    <el-row :gutter="16">
      <el-col :xs="24" :lg="10">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>参数</span>
              <el-tag type="info" size="small">仅前端</el-tag>
            </div>
          </template>

          <el-form label-position="top">
            <el-form-item label="市场">
              <el-segmented
                v-model="form.market"
                :options="[
                  { label: 'A股', value: 'A股' },
                  { label: '港股', value: '港股' },
                  { label: '美股', value: '美股' }
                ]"
              />
            </el-form-item>

            <el-form-item label="日期">
              <el-date-picker v-model="form.date" type="date" style="width: 100%" />
            </el-form-item>

            <el-form-item label="情景偏好">
              <el-select v-model="form.scenario" style="width: 100%">
                <el-option label="偏多情景" value="bull" />
                <el-option label="中性情景" value="neutral" />
                <el-option label="偏空情景" value="bear" />
              </el-select>
            </el-form-item>

            <el-form-item label="关注点">
              <el-checkbox-group v-model="form.focus">
                <el-checkbox label="指数方向" />
                <el-checkbox label="情绪修复" />
                <el-checkbox label="主线强度" />
                <el-checkbox label="风险事件" />
              </el-checkbox-group>
            </el-form-item>
          </el-form>

          <el-alert
            type="warning"
            :closable="false"
            show-icon
            title="后续接入后端后，将基于实时数据与模型输出生成预测内容。"
          />
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="14">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>预测结果</span>
              <el-tag type="info" size="small">{{ resultTitle }}</el-tag>
            </div>
          </template>

          <el-empty v-if="!result" description="点击“生成”得到早盘预测内容" />
          <div v-else class="result">
            <el-alert :title="result.summary" type="info" show-icon :closable="false" />
            <div class="sections">
              <el-card v-for="sec in result.sections" :key="sec.title" shadow="never" class="sec">
                <div class="sec-title">{{ sec.title }}</div>
                <ul class="sec-list">
                  <li v-for="line in sec.lines" :key="line">{{ line }}</li>
                </ul>
              </el-card>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'

type Market = 'A股' | '港股' | '美股'
type Scenario = 'bull' | 'neutral' | 'bear'

const form = ref({
  market: 'A股' as Market,
  date: new Date(),
  scenario: 'neutral' as Scenario,
  focus: ['指数方向', '主线强度'] as string[]
})

type ForecastResult = {
  summary: string
  sections: Array<{ title: string; lines: string[] }>
}

const result = ref<ForecastResult | null>(null)

const resultTitle = computed(() => dayjs(form.value.date).format('YYYY-MM-DD'))

function scenarioText(s: Scenario) {
  if (s === 'bull') return '偏多'
  if (s === 'bear') return '偏空'
  return '中性'
}

function generate() {
  const m = form.value.market
  const s = scenarioText(form.value.scenario)
  const f = form.value.focus.join('、') || '综合'
  result.value = {
    summary: `${m} 早盘预测（${s}情景）：关注 ${f} 的确认信号与量价配合。`,
    sections: [
      {
        title: '关键观察位',
        lines: ['关注指数关键点位的开盘回踩与量能是否放大', '观察强势主线是否延续（高开低走需谨慎）']
      },
      {
        title: '可能的主线',
        lines: ['优先观察强度最高的题材是否继续扩散到低位分支', '防御板块若走强，可能意味着风险偏好下降']
      },
      {
        title: '风险提示',
        lines: ['警惕盘前消息导致的高开回落', '若情绪不及预期，避免追涨，关注低吸与轮动']
      }
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

  .result {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .sections {
    display: grid;
    grid-template-columns: 1fr;
    gap: 12px;
  }
  .sec {
    :deep(.el-card__body) {
      padding: 12px 14px;
    }
  }
  .sec-title {
    font-weight: 700;
    margin-bottom: 6px;
    color: var(--el-text-color-primary);
  }
  .sec-list {
    margin: 0;
    padding-left: 18px;
    color: var(--el-text-color-regular);
    font-size: 13px;
    line-height: 1.8;
  }
}
</style>
