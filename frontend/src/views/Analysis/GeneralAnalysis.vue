﻿<template>
  <div class="general-analysis">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">
            <el-icon class="title-icon"><Document /></el-icon>
            通用研究分析
          </h1>

          <!-- 风险提示 -->
          <div class="risk-disclaimer">
            <el-alert
              type="warning"
              :closable="false"
              show-icon
            >
              <template #title>
                <span style="font-size: 14px;">
                  <strong>⚠️ 重要提示：</strong>本次分析所有结论用于学习和验证AI证券分析技术，不作为真实交易操盘指导。
                </span>
              </template>
            </el-alert>
          </div>

          <p class="page-description">
            基于通用流程的灵活研究工作台，支持自定义分析目标与参数
          </p>
        </div>
      </div>
    </div>

    <!-- 主要内容区（标签页切换） -->
    <el-tabs v-model="activeTab" class="main-tabs">
      <el-tab-pane label="新分析" name="new">
        <!-- 流程选择 + 动态表单 -->
        <div class="analysis-container">
          <el-card class="main-form-card" shadow="hover">
            <template #header>
              <div class="card-header">
                <h3>分析配置</h3>
                <el-tag type="info" size="small">必填信息</el-tag>
              </div>
            </template>

            <!-- 流程选择 -->
            <el-form label-width="100px" class="analysis-form">
              <div class="form-section">
                <h4 class="section-title">📋 分析流程</h4>
                <el-form-item label="流程选择">
                  <el-select
                    v-model="selectedWorkflowId"
                    placeholder="请选择通用分析流程"
                    size="large"
                    style="width: 100%"
                    :loading="loadingWorkflows"
                  >
                    <el-option
                      v-for="workflow in workflows"
                      :key="workflow.id"
                      :label="`${workflow.name} v${workflow.version}`"
                      :value="workflow.id"
                    >
                      <span>{{ workflow.name }}</span>
                      <span style="color: #909399; font-size: 12px; margin-left: 8px;">
                        v{{ workflow.version }}
                      </span>
                      <el-tag
                        v-if="workflow.is_default"
                        type="warning"
                        size="small"
                        effect="plain"
                        style="margin-left: 8px;"
                      >
                        默认
                      </el-tag>
                    </el-option>
                  </el-select>
                  <div v-if="selectedWorkflow" class="workflow-description">
                    <el-icon><InfoFilled /></el-icon>
                    <span>{{ selectedWorkflow.description || '暂无流程描述' }}</span>
                  </div>
                  <el-empty
                    v-else-if="!loadingWorkflows && workflows.length === 0"
                    description="暂无可用的通用分析流程"
                    :image-size="60"
                  />
                </el-form-item>
              </div>
            </el-form>

            <!-- 动态表单（仅当选中流程时显示） -->
            <template v-if="selectedWorkflowId && selectedWorkflow">
              <el-divider content-position="left">执行参数</el-divider>
              <el-form :model="formValues" label-position="top" class="analysis-form">
                <!-- 加载中 -->
                <el-empty v-if="loadingSelectedWorkflow" description="加载参数配置..." :image-size="60"></el-empty>
                <!-- 动态表单：从 selectedWorkflowFull.input_config.fields 生成 -->
                <template v-else-if="inputFields.length > 0">
                  <template v-for="group in groupedFields" :key="group.name">
                    <div v-if="group.name" class="field-group-title">{{ group.name }}</div>
                    <el-form-item
                      v-for="field in group.fields"
                      :key="field.name"
                      :label="field.label || field.name"
                      :required="field.required"
                    >
                      <!-- string: 单行文本 -->
                      <el-input
                        v-if="field.type === 'string'"
                        v-model="formValues[field.name]"
                        :placeholder="field.placeholder || ''"
                      />

                      <!-- textarea: 多行文本 -->
                      <el-input
                        v-else-if="field.type === 'textarea'"
                        v-model="formValues[field.name]"
                        type="textarea"
                        :rows="4"
                        :placeholder="field.placeholder || ''"
                        maxlength="500"
                        show-word-limit
                      />

                      <!-- number: 数字 -->
                      <el-input-number
                        v-else-if="field.type === 'number'"
                        v-model="formValues[field.name]"
                        :min="field.min ?? undefined"
                        :max="field.max ?? undefined"
                        style="width: 100%"
                      />

                      <!-- boolean: 开关 -->
                      <el-switch
                        v-else-if="field.type === 'boolean'"
                        v-model="formValues[field.name]"
                      />

                      <!-- date: 日期选择 -->
                      <el-date-picker
                        v-else-if="field.type === 'date'"
                        v-model="formValues[field.name]"
                        type="date"
                        placeholder="选择日期"
                        style="width: 100%"
                        value-format="YYYY-MM-DD"
                      />

                      <!-- select: 下拉单选 -->
                      <el-select
                        v-else-if="field.type === 'select'"
                        v-model="formValues[field.name]"
                        :placeholder="field.placeholder || '请选择'"
                        style="width: 100%"
                        :loading="modelsLoading"
                      >
                        <!-- 模型字段特殊处理：从 enabledModels 动态填充选项 -->
                        <template v-if="field.name === 'quick_analysis_model' || field.name === 'deep_analysis_model'">
                          <el-option
                            v-for="model in enabledModels"
                            :key="model.model_name"
                            :label="model.model_name"
                            :value="model.model_name"
                          />
                        </template>
                        <!-- 普通选项 -->
                        <template v-else>
                          <el-option
                            v-for="(opt, idx) in (field.options || [])"
                            :key="idx"
                            :label="field.option_labels?.[idx] || String(opt)"
                            :value="opt"
                          />
                        </template>
                      </el-select>

                      <!-- multiselect: 下拉多选 -->
                      <el-select
                        v-else-if="field.type === 'multiselect'"
                        v-model="formValues[field.name]"
                        multiple
                        :placeholder="field.placeholder || '请选择'"
                        style="width: 100%"
                      >
                        <el-option
                          v-for="(opt, idx) in (field.options || [])"
                          :key="idx"
                          :label="field.option_labels?.[idx] || String(opt)"
                          :value="opt"
                        />
                      </el-select>

                      <!-- 参数描述 -->
                      <div v-if="field.description" class="field-description">{{ field.description }}</div>
                    </el-form-item>
                  </template>
                </template>

                <!-- 无输入参数提示 -->
                <el-empty
                  v-else
                  description="此流程无需输入参数"
                  :image-size="60"
                />

                <el-form-item>
                  <el-button
                    type="primary"
                    size="large"
                    :loading="executing"
                    :disabled="!selectedWorkflowId"
                    @click="handleExecute"
                    class="submit-btn"
                  >
                    <el-icon><TrendCharts /></el-icon>
                    开始分析
                  </el-button>
                </el-form-item>
              </el-form>
            </template>
          </el-card>

          <!-- 执行状态展示 -->
          <el-card v-if="taskStatus !== 'idle'" class="status-card" shadow="hover">
            <template #header>
              <div class="card-header">
                <h3>执行状态</h3>
                <el-tag :type="statusTagType" size="small">{{ statusTagText }}</el-tag>
              </div>
            </template>

            <div class="status-content">
              <div class="status-info">
                <div class="info-item">
                  <span class="info-label">任务ID</span>
                  <span class="info-value">
                    <el-text class="task-id-text" truncated>{{ taskId || '—' }}</el-text>
                    <el-button
                      v-if="taskId"
                      type="primary"
                      link
                      size="small"
                      @click="copyTaskId"
                    >
                      <el-icon><CopyDocument /></el-icon>
                      复制
                    </el-button>
                  </span>
                </div>

                <div class="info-item">
                  <span class="info-label">分析目标</span>
                  <span class="info-value">{{ formValues.analysis_target || formValues.ticker || '—' }}</span>
                </div>

                <div class="info-item">
                  <span class="info-label">开始时间</span>
                  <span class="info-value">{{ startedAt || '—' }}</span>
                </div>

                <div v-if="taskStatus === 'running'" class="info-item">
                  <span class="info-label">已用时间</span>
                  <span class="info-value">{{ elapsedText }}</span>
                </div>
              </div>

              <!-- 进度条 -->
              <div v-if="taskStatus === 'running'" class="progress-section">
                <el-progress
                  :percentage="progressPercent"
                  :stroke-width="10"
                  :status="progressStatus"
                  :indeterminate="progressPercent === 0"
                />
                <div v-if="currentStep" class="current-step">
                  <el-icon class="rotating-icon"><Loading /></el-icon>
                  <span>{{ currentStep }}</span>
                </div>
              </div>

              <!-- 错误信息 -->
              <el-alert
                v-if="taskStatus === 'failed' && errorMessage"
                type="error"
                :closable="false"
                show-icon
                :title="errorMessage"
                style="margin-top: 12px;"
              />

              <!-- 完成提示 -->
              <el-alert
                v-if="taskStatus === 'completed'"
                type="success"
                :closable="false"
                show-icon
                title="分析任务已完成"
                style="margin-top: 12px;"
              >
                <template #default>
                  <div>点击上方"查看结果"按钮，可前往任务中心查看完整分析报告。</div>
                </template>
              </el-alert>

              <!-- 结果链接 -->
              <div v-if="taskStatus === 'completed'" class="result-link-section">
                <el-button
                  type="primary"
                  size="large"
                  @click="viewResult"
                  class="submit-btn"
                >
                  <el-icon><Document /></el-icon>
                  查看结果
                </el-button>
                <el-button
                  size="large"
                  @click="resetAnalysis"
                  class="submit-btn"
                >
                  <el-icon><Refresh /></el-icon>
                  重新分析
                </el-button>
              </div>

              <!-- 失败链接 -->
              <div v-if="taskStatus === 'failed'" class="result-link-section">
                <el-button
                  type="danger"
                  size="large"
                  @click="resetAnalysis"
                  class="submit-btn"
                >
                  <el-icon><Refresh /></el-icon>
                  重新分析
                </el-button>
              </div>
            </div>
          </el-card>
        </div>
      </el-tab-pane>

      <!-- 历史结果标签页（保留原逻辑） -->
      <el-tab-pane label="历史结果" name="history">
        <div class="history-container">
          <!-- 筛选栏 -->
          <el-card shadow="never" class="filter-card">
            <el-form :inline="true" :model="historyFilters" size="default">
              <el-form-item label="流程">
                <el-select
                  v-model="historyFilters.workflow_id"
                  placeholder="全部流程"
                  clearable
                  style="width: 200px"
                >
                  <el-option
                    v-for="wf in workflows"
                    :key="wf.id"
                    :label="`${wf.name} v${wf.version}`"
                    :value="wf.id"
                  />
                </el-select>
              </el-form-item>

              <el-form-item label="时间范围">
                <el-date-picker
                  v-model="historyDateRange"
                  type="daterange"
                  range-separator="至"
                  start-placeholder="开始日期"
                  end-placeholder="结束日期"
                  format="YYYY-MM-DD"
                  value-format="YYYY-MM-DD"
                  style="width: 260px"
                />
              </el-form-item>

              <el-form-item label="关键字">
                <el-input
                  v-model="historyFilters.keyword"
                  placeholder="搜索分析目标"
                  clearable
                  style="width: 200px"
                  @keyup.enter="loadHistory"
                />
              </el-form-item>

              <el-form-item label="状态">
                <el-select
                  v-model="historyFilters.status"
                  placeholder="全部状态"
                  clearable
                  style="width: 120px"
                >
                  <el-option label="已完成" value="completed" />
                  <el-option label="进行中" value="processing" />
                  <el-option label="失败" value="failed" />
                  <el-option label="等待中" value="pending" />
                </el-select>
              </el-form-item>

              <el-form-item>
                <el-button type="primary" @click="loadHistory" :loading="historyLoading">
                  <el-icon><Search /></el-icon>
                  查询
                </el-button>
                <el-button @click="resetHistoryFilters">
                  <el-icon><Refresh /></el-icon>
                  重置
                </el-button>
              </el-form-item>
            </el-form>
          </el-card>

          <!-- 历史结果表格 -->
          <el-card shadow="never" class="history-table-card">
            <el-table
              :data="historyList"
              v-loading="historyLoading"
              stripe
              style="width: 100%"
            >
              <template #empty>
                <el-empty description="暂无历史记录，执行新分析后可在此查看结果" />
              </template>

              <el-table-column label="分析目标" min-width="220">
                <template #default="{ row }">
                  <el-link
                    type="primary"
                    @click="showHistoryDetail(row)"
                    style="font-weight: 500;"
                  >
                    {{ row.analysis_target || '—' }}
                  </el-link>
                </template>
              </el-table-column>

              <el-table-column label="流程" min-width="160">
                <template #default="{ row }">
                  {{ getWorkflowName(row.workflow_id) }}
                </template>
              </el-table-column>

              <el-table-column label="状态" width="100" align="center">
                <template #default="{ row }">
                  <el-tag :type="getHistoryStatusColor(row.status)" size="small">
                    {{ getHistoryStatusName(row.status) }}
                  </el-tag>
                </template>
              </el-table-column>

              <el-table-column label="进度" width="120">
                <template #default="{ row }">
                  <el-progress
                    v-if="row.status === 'processing'"
                    :percentage="row.progress || 0"
                    :stroke-width="6"
                  />
                  <span v-else-if="row.status === 'completed'" style="color: #67c23a">100%</span>
                  <span v-else style="color: #909399">—</span>
                </template>
              </el-table-column>

              <el-table-column label="创建时间" width="170">
                <template #default="{ row }">
                  {{ formatHistoryTime(row.created_at) }}
                </template>
              </el-table-column>

              <el-table-column label="耗时" width="100" align="center">
                <template #default="{ row }">
                  <span v-if="row.execution_time > 0">{{ formatDuration(row.execution_time) }}</span>
                  <span v-else style="color: #909399">—</span>
                </template>
              </el-table-column>

              <el-table-column label="操作" width="120" fixed="right" align="center">
                <template #default="{ row }">
                  <el-button link type="primary" size="small" @click="showHistoryDetail(row)">
                    <el-icon><View /></el-icon>
                    查看详情
                  </el-button>
                </template>
              </el-table-column>
            </el-table>

            <!-- 分页 -->
            <div class="pagination-wrapper" v-if="historyTotal > 0">
              <el-pagination
                v-model:current-page="historyCurrentPage"
                v-model:page-size="historyPageSize"
                :total="historyTotal"
                :page-sizes="[10, 20, 50]"
                layout="total, sizes, prev, pager, next"
                @size-change="loadHistory"
                @current-change="loadHistory"
              />
            </div>
          </el-card>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 历史结果详情对话框（保留原逻辑） -->
    <el-dialog
      v-model="detailDialogVisible"
      title="分析结果详情"
      width="90%"
      top="3vh"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <div v-loading="detailLoading" class="detail-container">
        <template v-if="detailData">
          <!-- 基本信息 -->
          <el-card shadow="never" class="detail-section">
            <template #header>
              <div class="detail-card-header">
                <el-icon><InfoFilled /></el-icon>
                <span>基本信息</span>
              </div>
            </template>
            <el-descriptions :column="3" border>
              <el-descriptions-item label="分析目标" :span="2">
                <strong>{{ detailData.task_params?.symbol || detailData.task_params?.analysis_target || detailData.task_params?.ticker || '—' }}</strong>
              </el-descriptions-item>
              <el-descriptions-item label="状态">
                <el-tag :type="getHistoryStatusColor(detailData.status)">
                  {{ getHistoryStatusName(detailData.status) }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="流程">
                {{ getWorkflowName(detailData.workflow_id) }}
              </el-descriptions-item>
              <el-descriptions-item label="创建时间">
                {{ formatHistoryTime(detailData.created_at) }}
              </el-descriptions-item>
              <el-descriptions-item label="耗时">
                {{ detailData.execution_time > 0 ? formatDuration(detailData.execution_time) : '—' }}
              </el-descriptions-item>
            </el-descriptions>
          </el-card>

          <!-- 错误信息 -->
          <el-card v-if="detailData.error_message" shadow="never" class="detail-section error-section">
            <template #header>
              <div class="detail-card-header">
                <el-icon><Warning /></el-icon>
                <span>错误信息</span>
              </div>
            </template>
            <el-alert :title="detailData.error_message" type="error" :closable="false" show-icon />
          </el-card>

          <!-- 分析摘要 -->
          <el-card v-if="detailData.result" shadow="never" class="detail-section">
            <template #header>
              <div class="detail-card-header">
                <el-icon><Document /></el-icon>
                <span>分析摘要</span>
              </div>
            </template>
            <div class="summary-content">
              <div class="summary-item" v-if="detailData.result.summary">
                <div class="summary-label">总结：</div>
                <div class="summary-value">{{ detailData.result.summary }}</div>
              </div>
              <div class="summary-item" v-if="detailData.result.recommendation">
                <div class="summary-label">建议：</div>
                <div class="summary-value">{{ detailData.result.recommendation }}</div>
              </div>
              <div class="summary-item" v-if="detailData.result.risk_level">
                <div class="summary-label">风险等级：</div>
                <div class="summary-value">
                  <el-tag size="small">{{ detailData.result.risk_level }}</el-tag>
                </div>
              </div>
            </div>
          </el-card>

          <!-- 完整工作流输出 -->
          <el-card v-if="detailData.result?.report_manifest?.length" shadow="never" class="detail-section">
            <template #header>
              <div class="detail-card-header">
                <el-icon><DataAnalysis /></el-icon>
                <span>完整工作流输出</span>
              </div>
            </template>
            <el-collapse v-model="activeReportNames" class="report-collapse">
              <el-collapse-item
                v-for="item in sortedReportManifest"
                :key="item.field"
                :name="item.field"
              >
                <template #title>
                  <div class="report-title">
                    <span class="report-icon">{{ item.icon || '📄' }}</span>
                    <span class="report-name">{{ item.display_name || item.field }}</span>
                    <el-tag
                      v-if="item.is_primary"
                      type="warning"
                      size="small"
                      effect="plain"
                      style="margin-left: 8px;"
                    >
                      主报告
                    </el-tag>
                    <el-tag
                      v-if="!item.has_content"
                      type="info"
                      size="small"
                      effect="plain"
                      style="margin-left: 8px;"
                    >
                      无内容
                    </el-tag>
                  </div>
                </template>
                <div class="report-content">
                  <template v-if="getReportContent(item.field)">
                    <div class="markdown-content" v-html="renderMarkdown(getReportContent(item.field))"></div>
                  </template>
                  <el-text v-else type="info">该报告暂无内容</el-text>
                </div>
              </el-collapse-item>
            </el-collapse>
          </el-card>

          <!-- 研究结论信息 -->
          <el-card v-if="detailData.result?.decision" shadow="never" class="detail-section">
            <template #header>
              <div class="detail-card-header">
                <el-icon><Tickets /></el-icon>
                <span>研究结论信息</span>
              </div>
            </template>
            <el-descriptions :column="2" border>
              <el-descriptions-item label="研究结论倾向">
                <el-tag :type="getDecisionColor(detailData.result.decision.action)">
                  {{ detailData.result.decision.action || '—' }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="置信度">
                {{ formatPercent(detailData.result.decision.confidence) }}
              </el-descriptions-item>
              <el-descriptions-item label="风险评分" :span="2">
                {{ detailData.result.decision.risk_score ?? '—' }}
              </el-descriptions-item>
              <el-descriptions-item
                v-if="detailData.result.decision.reasoning"
                label="研究依据"
                :span="2"
              >
                {{ detailData.result.decision.reasoning }}
              </el-descriptions-item>
            </el-descriptions>
          </el-card>

          <!-- 原始数据 -->
          <el-card shadow="never" class="detail-section">
            <template #header>
              <div class="detail-card-header">
                <el-icon><Document /></el-icon>
                <span>原始数据（JSON）</span>
              </div>
            </template>
            <el-collapse>
              <el-collapse-item title="展开查看完整 JSON" name="raw">
                <pre class="json-content">{{ JSON.stringify(detailData, null, 2) }}</pre>
              </el-collapse-item>
            </el-collapse>
          </el-card>
        </template>
        <el-empty v-else-if="!detailLoading" description="暂无数据" />
      </div>

      <template #footer>
        <el-button @click="detailDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Document,
  TrendCharts,
  InfoFilled,
  Loading,
  Refresh,
  CopyDocument,
  Search,
  View,
  Warning,
  DataAnalysis,
  Tickets,
} from '@element-plus/icons-vue'
import { workflowApi, type WorkflowSummary, type WorkflowDefinition, type InputFieldConfig } from '@/api/workflow'
import { analysisApi } from '@/api/analysis'
import { configApi, type LLMConfig } from '@/api/config'
import {
  getGeneralTaskList,
  getTaskDetail,
  GeneralTaskStatusNames,
  GeneralTaskStatusColors,
  type GeneralTaskListItem,
  type GeneralTaskListParams,
} from '@/api/unifiedTasks'
import { useAuthStore } from '@/stores/auth'
import { isJdyunMode, JDYUN_CHAT_MODELS, loadJdyunChatModels } from '@/utils/config'
import { renderMarkdown as safeMarkdown } from '@/utils/markdown'

const router = useRouter()

// ==================== 标签页切换 ====================
const activeTab = ref<'new' | 'history'>('new')

// 流程选择
const workflows = ref<WorkflowSummary[]>([])
const selectedWorkflowId = ref('')
const loadingWorkflows = ref(false)

// 选中流程的完整数据（包含 input_config）
const selectedWorkflowFull = ref<WorkflowDefinition | null>(null)
const loadingSelectedWorkflow = ref(false)

// 模型列表（仅用于 select 类型的模型字段动态填充选项）
const modelsLoading = ref(false)
const allModels = ref<LLMConfig[]>([])
const enabledModels = computed(() => allModels.value.filter(m => m.enabled))

// 动态表单值：formValues[field.name] = 值
const formValues = ref<Record<string, any>>({})

// 输入参数字段列表（从 workflow.input_config.fields 读取）
const selectedWorkflow = computed(() => {
  return workflows.value.find(w => w.id === selectedWorkflowId.value)
})
const inputFields = computed<InputFieldConfig[]>(() => {
  return selectedWorkflowFull.value?.input_config?.fields || []
})

// 按分组组织字段
const groupedFields = computed(() => {
  const fields = [...inputFields.value].sort((a, b) => (a.order || 0) - (b.order || 0))
  const groups: Array<{ name: string; fields: InputFieldConfig[] }> = []
  const groupMap = new Map<string, InputFieldConfig[]>()

  for (const f of fields) {
    const g = f.group || ''
    if (!groupMap.has(g)) groupMap.set(g, [])
    groupMap.get(g)!.push(f)
  }

  for (const [name, fields] of groupMap) {
    groups.push({ name, fields })
  }
  return groups
})

// 执行状态
const executing = ref(false)
const taskId = ref('')
const taskStatus = ref<'idle' | 'running' | 'completed' | 'failed'>('idle')
const errorMessage = ref('')
const progressPercent = ref(0)
const currentStep = ref('')
const startedAt = ref('')
const elapsedSeconds = ref(0)

let pollTimer: ReturnType<typeof setInterval> | null = null
let elapsedTimer: ReturnType<typeof setInterval> | null = null

// 状态标签
const statusTagType = computed<'info' | 'warning' | 'success' | 'danger'>(() => {
  switch (taskStatus.value) {
    case 'running': return 'warning'
    case 'completed': return 'success'
    case 'failed': return 'danger'
    default: return 'info'
  }
})

const statusTagText = computed(() => {
  switch (taskStatus.value) {
    case 'running': return '运行中'
    case 'completed': return '已完成'
    case 'failed': return '执行失败'
    default: return '等待中'
  }
})

// 进度条状态
const progressStatus = computed<'' | 'success' | 'exception'>(() => {
  if (taskStatus.value === 'completed') return 'success'
  if (taskStatus.value === 'failed') return 'exception'
  return ''
})

// 已用时间格式化
const elapsedText = computed(() => {
  const s = elapsedSeconds.value
  if (s < 60) return `${s} 秒`
  const m = Math.floor(s / 60)
  const rest = s % 60
  return `${m} 分 ${rest} 秒`
})

// ==================== 初始化 ====================

// 加载模型配置
const loadModels = async () => {
  modelsLoading.value = true
  try {
    // 🔥 京东云模式：先从后端加载可用模型列表，覆盖默认值
    await loadJdyunChatModels()

    const response = await configApi.getLLMConfigs()
    let models = Array.isArray(response) ? response : []

    // 🔧 京东云模式：仅保留预置的 4 个模型
    if (isJdyunMode()) {
      const jdyunModelSet = new Set<string>(JDYUN_CHAT_MODELS)
      models = models.filter((m: any) => jdyunModelSet.has(m.model_name))
      if (models.length === 0) {
        models = JDYUN_CHAT_MODELS.map(name => ({
          model_name: name,
          model_display_name: name,
          provider: 'jdyun',
          enabled: true
        })) as any
      }
    }
    allModels.value = models
  } catch (error) {
    console.error('加载模型配置失败:', error)
    // 京东云模式兜底
    if (isJdyunMode()) {
      allModels.value = JDYUN_CHAT_MODELS.map(name => ({
        model_name: name,
        model_display_name: name,
        provider: 'jdyun',
        enabled: true
      })) as any
    }
  } finally {
    modelsLoading.value = false
  }
}

// 加载流程列表
const loadWorkflows = async () => {
  loadingWorkflows.value = true
  try {
    const data = await workflowApi.listAll()
    const list = Array.isArray(data) ? data : []
    workflows.value = list.filter((w: WorkflowSummary) => w.workflow_type === 'general')

    // 自动选中默认流程
    const defaultWf = workflows.value.find(w => w.is_default)
    if (defaultWf) {
      selectedWorkflowId.value = defaultWf.id
    } else if (workflows.value.length > 0) {
      selectedWorkflowId.value = workflows.value[0].id
    }
  } catch (e) {
    console.error('加载流程失败', e)
    ElMessage.error('加载流程列表失败')
  } finally {
    loadingWorkflows.value = false
  }
}

// 初始化表单默认值
const initFormValues = async () => {
  const values: Record<string, any> = {}
  // 京东云模式：预置模型白名单，用于校验默认模型
  const jdyunModelSet = isJdyunMode() ? new Set<string>(JDYUN_CHAT_MODELS) : null
  for (const field of inputFields.value) {
    let defaultVal = field.default
    // 特殊处理模型字段：从系统配置加载默认模型
    if (field.name === 'quick_analysis_model' && !defaultVal) {
      try {
        const defaultModels = await configApi.getDefaultModels()
        defaultVal = defaultModels.quick_analysis_model || ''
      } catch { defaultVal = '' }
      // 🔧 京东云模式：默认模型不在白名单内时回退到第一个预置模型
      if (isJdyunMode() && defaultVal && jdyunModelSet && !jdyunModelSet.has(defaultVal)) {
        defaultVal = JDYUN_CHAT_MODELS[0]
      }
    } else if (field.name === 'deep_analysis_model' && !defaultVal) {
      try {
        const defaultModels = await configApi.getDefaultModels()
        defaultVal = defaultModels.deep_analysis_model || ''
      } catch { defaultVal = '' }
      // 🔧 京东云模式：默认模型不在白名单内时回退到第一个预置模型
      if (isJdyunMode() && defaultVal && jdyunModelSet && !jdyunModelSet.has(defaultVal)) {
        defaultVal = JDYUN_CHAT_MODELS[0]
      }
    } else if (field.name === 'research_depth' && !defaultVal) {
      try {
        const authStore = useAuthStore()
        const userPrefs = authStore.user?.preferences
        if (userPrefs?.default_depth) {
          defaultVal = convertDepthToText(Number(userPrefs.default_depth))
        }
      } catch { /* ignore */ }
    }

    if (defaultVal === null || defaultVal === undefined) {
      switch (field.type) {
        case 'boolean': defaultVal = false; break
        case 'number': defaultVal = undefined; break
        case 'multiselect': defaultVal = []; break
        case 'date':
          if (field.name === 'analysis_date') {
            defaultVal = new Date().toISOString().slice(0, 10)
          } else {
            defaultVal = ''
          }
          break
        default: defaultVal = ''
      }
    }
    values[field.name] = defaultVal
  }
  formValues.value = values
}

// 深度值转换
const convertDepthToText = (depth: number) => {
  switch (depth) {
    case 1: return '快速'
    case 2: return '基础'
    case 3: return '标准'
    case 4: return '深度'
    case 5: return '全面'
    default: return '标准'
  }
}

// 选中流程变化时加载完整 workflow 数据
watch(selectedWorkflowId, async (newVal) => {
  if (!newVal) {
    selectedWorkflowFull.value = null
    formValues.value = {}
    return
  }

  loadingSelectedWorkflow.value = true
  try {
    selectedWorkflowFull.value = await workflowApi.get(newVal)
    await initFormValues()
  } catch (e) {
    console.error('加载流程详情失败:', e)
    ElMessage.error('加载流程详情失败')
  } finally {
    loadingSelectedWorkflow.value = false
  }
})

// ==================== 执行分析 ====================

// 复制任务ID
const copyTaskId = async () => {
  if (!taskId.value) return
  try {
    await navigator.clipboard.writeText(taskId.value)
    ElMessage.success('任务ID已复制')
  } catch {
    ElMessage.warning('复制失败，请手动选择文本复制')
  }
}

// 执行分析
const handleExecute = async () => {
  if (!selectedWorkflowId.value) {
    ElMessage.warning('请先选择分析流程')
    return
  }

  // 校验必填字段
  for (const field of inputFields.value) {
    if (field.required) {
      const val = formValues.value[field.name]
      const empty = val === null || val === undefined || val === '' ||
        (Array.isArray(val) && val.length === 0)
      if (empty) {
        ElMessage.warning(`请填写${field.label || field.name}`)
        return
      }
    }
  }

  executing.value = true
  taskStatus.value = 'running'
  errorMessage.value = ''
  progressPercent.value = 0
  currentStep.value = '正在初始化分析引擎...'
  startedAt.value = new Date().toLocaleString('zh-CN', { hour12: false })
  elapsedSeconds.value = 0

  // 启动计时
  startElapsedTimer()

  try {
    // 构造请求参数
    const params: Record<string, any> = {}
    for (const field of inputFields.value) {
      const val = formValues.value[field.name]
      if (val !== null && val !== undefined && val !== '') {
        params[field.name] = val
      }
    }

    // 如果没有 ticker 字段但有 analysis_target，复用作为 ticker（工作流引擎需要 ticker 做参数映射）
    if (!params.ticker) {
      if (params.analysis_target) {
        params.ticker = params.analysis_target
      }
    }

    // 所有参数合并到 custom_params 中
    const customParams: Record<string, any> = { ...params }
    delete customParams.ticker
    params.custom_params = customParams

    const result = await workflowApi.execute(selectedWorkflowId.value, params)

    if (result.success && result.task_id) {
      taskId.value = result.task_id
      ElMessage.success('分析任务已创建')
      startPolling()
    } else {
      throw new Error(result.error || result.message || '未获取到任务ID')
    }
  } catch (e: any) {
    taskStatus.value = 'failed'
    errorMessage.value = e?.message || '执行失败'
    ElMessage.error(errorMessage.value)
    stopElapsedTimer()
  } finally {
    executing.value = false
  }
}

// 开始轮询任务状态
const startPolling = () => {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = setInterval(async () => {
    if (!taskId.value) return
    try {
      const response = await analysisApi.getTaskStatus(taskId.value)
      const status = response.data
      if (!status) return

      if (typeof status.progress === 'number') {
        progressPercent.value = Math.min(100, Math.max(0, Math.round(status.progress)))
      }
      if (status.current_step_name || status.current_step) {
        currentStep.value = status.current_step_name || status.current_step
      } else if (status.message) {
        currentStep.value = status.message
      }

      const st = status.status
      if (st === 'completed' || st === 'success') {
        taskStatus.value = 'completed'
        progressPercent.value = 100
        stopPolling()
        stopElapsedTimer()
        ElMessage.success('分析完成')
      } else if (st === 'failed' || st === 'error') {
        taskStatus.value = 'failed'
        errorMessage.value = status.error || status.error_message || '任务执行失败'
        stopPolling()
        stopElapsedTimer()
        ElMessage.error('分析失败')
      }
    } catch (e) {
      console.error('查询任务状态失败', e)
    }
  }, 3000)
}

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

const startElapsedTimer = () => {
  if (elapsedTimer) clearInterval(elapsedTimer)
  elapsedTimer = setInterval(() => {
    elapsedSeconds.value += 1
  }, 1000)
}

const stopElapsedTimer = () => {
  if (elapsedTimer) {
    clearInterval(elapsedTimer)
    elapsedTimer = null
  }
}

const resetAnalysis = () => {
  stopPolling()
  stopElapsedTimer()
  taskStatus.value = 'idle'
  taskId.value = ''
  errorMessage.value = ''
  progressPercent.value = 0
  currentStep.value = ''
  startedAt.value = ''
  elapsedSeconds.value = 0
}

const viewResult = () => {
  if (!taskId.value) return
  router.push({ path: '/tasks/unified', query: { task_id: taskId.value } })
}

// ==================== 历史结果管理 ====================

const historyList = ref<GeneralTaskListItem[]>([])
const historyLoading = ref(false)
const historyTotal = ref(0)
const historyCurrentPage = ref(1)
const historyPageSize = ref(20)
const historyDateRange = ref<[string, string] | null>(null)

const historyFilters = ref<GeneralTaskListParams>({
  workflow_id: undefined,
  keyword: '',
  status: undefined,
})

const detailDialogVisible = ref(false)
const detailLoading = ref(false)
const detailData = ref<any>(null)
const activeReportNames = ref<string[]>([])

const loadHistory = async () => {
  historyLoading.value = true
  try {
    const params: GeneralTaskListParams = {
      limit: historyPageSize.value,
      skip: (historyCurrentPage.value - 1) * historyPageSize.value,
    }
    if (historyFilters.value.workflow_id) {
      params.workflow_id = historyFilters.value.workflow_id
    }
    if (historyFilters.value.keyword?.trim()) {
      params.keyword = historyFilters.value.keyword.trim()
    }
    if (historyFilters.value.status) {
      params.status = historyFilters.value.status
    }
    if (historyDateRange.value && historyDateRange.value.length === 2) {
      params.date_start = historyDateRange.value[0]
      params.date_end = historyDateRange.value[1]
    }

    const res = await getGeneralTaskList(params) as any
    const data = res?.data?.data || res?.data || {}
    historyList.value = data.tasks || []
    historyTotal.value = data.total || 0
  } catch (e: any) {
    console.error('加载历史结果失败', e)
    ElMessage.error(e?.message || '加载历史结果失败')
  } finally {
    historyLoading.value = false
  }
}

const resetHistoryFilters = () => {
  historyFilters.value = {
    workflow_id: undefined,
    keyword: '',
    status: undefined,
  }
  historyDateRange.value = null
  historyCurrentPage.value = 1
  loadHistory()
}

const showHistoryDetail = async (item: GeneralTaskListItem) => {
  detailLoading.value = true
  detailDialogVisible.value = true
  activeReportNames.value = []
  try {
    const data = await getTaskDetail(item.task_id)
    detailData.value = (data as any)?.data || data
  } catch (e: any) {
    console.error('加载详情失败', e)
    ElMessage.error(e?.message || '加载详情失败')
  } finally {
    detailLoading.value = false
  }
}

const getWorkflowName = (workflowId: string) => {
  const wf = workflows.value.find(w => w.id === workflowId)
  return wf ? `${wf.name} v${wf.version}` : workflowId
}

const getHistoryStatusColor = (status: string) => {
  return GeneralTaskStatusColors[status as keyof typeof GeneralTaskStatusColors] || 'info'
}

const getHistoryStatusName = (status: string) => {
  return GeneralTaskStatusNames[status as keyof typeof GeneralTaskStatusNames] || status
}

const formatHistoryTime = (time: string | number) => {
  if (!time) return '—'
  const d = new Date(time)
  return d.toLocaleString('zh-CN', { hour12: false })
}

const formatDuration = (seconds: number) => {
  if (seconds < 60) return `${seconds}s`
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}m ${s}s`
}

const formatPercent = (value: number | null | undefined) => {
  if (value == null) return '—'
  return `${Math.round(value * 100)}%`
}

const sortedReportManifest = computed(() => {
  if (!detailData.value?.result?.report_manifest) return []
  return [...detailData.value.result.report_manifest].sort((a: any, b: any) => {
    if (a.is_primary && !b.is_primary) return -1
    if (!a.is_primary && b.is_primary) return 1
    return (a.order || 0) - (b.order || 0)
  })
})

const getReportContent = (field: string) => {
  if (!detailData.value?.result?.[field]) return ''
  const content = detailData.value.result[field]
  if (typeof content === 'string') return content
  if (typeof content === 'object') return JSON.stringify(content, null, 2)
  return String(content)
}

const renderMarkdown = (text: string) => {
  try {
    return safeMarkdown(text)
  } catch {
    return text
  }
}

const getDecisionColor = (action: string) => {
  if (!action) return 'info'
  const a = action.toLowerCase()
  // 新合规术语"乐观/审慎/中性"优先匹配（语义为研究结论倾向，非交易指令）
  if (a.includes('乐观')) return 'success'   // 绿色：积极倾向
  if (a.includes('审慎')) return 'warning'   // 黄色：需要谨慎
  if (a.includes('中性')) return 'info'      // 灰色：无明显倾向
  // 旧市场观点术语"看涨/看跌" + 旧交易指令"买入/卖出"（兼容存量数据）
  if (a.includes('buy') || a.includes('做多') || a.includes('买入') || a.includes('看涨')) return 'success'
  if (a.includes('sell') || a.includes('做空') || a.includes('卖出') || a.includes('看跌')) return 'danger'
  return 'info'
}

// ==================== 生命周期 ====================

onMounted(async () => {
  await Promise.all([
    loadModels(),
    loadWorkflows(),
  ])
  if (activeTab.value === 'history') {
    await loadHistory()
  }
})

onUnmounted(() => {
  stopPolling()
  stopElapsedTimer()
})
</script>

<style scoped>
.general-analysis {
  padding: 20px;
  max-width: 1600px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 24px;
}

.header-content {
  padding: 16px;
  background: linear-gradient(135deg, #f5f7fa 0%, #e4e7ed 100%);
  border-radius: 8px;
}

.title-section {
  margin-bottom: 16px;
}

.page-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 8px 0;
  font-size: 24px;
  color: #303133;
}

.page-description {
  margin: 12px 0 0 0;
  color: #606266;
  font-size: 14px;
}

.risk-disclaimer {
  margin-top: 12px;
}

.main-tabs {
  margin-top: 0;
}

.analysis-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.main-form-card {
  border-radius: 8px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.card-header h3 {
  margin: 0;
  font-size: 16px;
  color: #303133;
}

.form-section {
  margin-bottom: 12px;
}

.section-title {
  font-size: 14px;
  color: #909399;
  margin: 0 0 8px 0;
}

.workflow-description {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 6px;
  font-size: 13px;
  color: #606266;
  margin-top: 6px;
}

.field-group-title {
  font-size: 13px;
  color: #909399;
  margin-top: 12px;
  margin-bottom: 8px;
  padding-left: 4px;
  border-left: 3px solid #409eff;
}

.field-description {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.submit-btn {
  width: 100%;
}

.status-card {
  border-radius: 8px;
}

.status-content {
  padding: 4px 0;
}

.status-info {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.info-label {
  font-size: 13px;
  color: #909399;
  min-width: 70px;
}

.info-value {
  font-size: 13px;
  color: #303133;
}

.task-id-text {
  font-family: 'Courier New', monospace;
  font-size: 12px;
}

.progress-section {
  margin-top: 16px;
}

.current-step {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  font-size: 13px;
  color: #606266;
}

.rotating-icon {
  animation: rotate 1s linear infinite;
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.result-link-section {
  margin-top: 16px;
  display: flex;
  gap: 12px;
}

/* 历史结果 */
.history-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.filter-card,
.history-table-card {
  border-radius: 8px;
}

.pagination-wrapper {
  padding: 16px 0 4px 0;
  display: flex;
  justify-content: flex-end;
}

.detail-container {
  padding: 4px 0;
}

.detail-section {
  margin-bottom: 16px;
  border-radius: 6px;
}

.detail-section:last-child {
  margin-bottom: 0;
}

.detail-card-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 500;
  color: #303133;
}

.summary-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.summary-item {
  display: flex;
  gap: 8px;
}

.summary-label {
  font-size: 13px;
  color: #909399;
  min-width: 70px;
}

.summary-value {
  font-size: 13px;
  color: #303133;
  flex: 1;
}

.report-collapse {
  margin-top: 4px;
}

.report-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.report-icon {
  font-size: 16px;
}

.report-name {
  font-size: 14px;
  color: #303133;
}

.report-content {
  padding: 4px 0;
}

.markdown-content {
  line-height: 1.6;
  color: #303133;
}

.markdown-content :deep(h1),
.markdown-content :deep(h2),
.markdown-content :deep(h3),
.markdown-content :deep(h4) {
  color: #303133;
  margin: 12px 0 8px 0;
}

.markdown-content :deep(p) {
  margin: 8px 0;
}

.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  margin: 8px 0;
  padding-left: 24px;
}

.markdown-content :deep(li) {
  margin: 4px 0;
}

.error-section {
  border-color: #fef0f0;
}

.json-content {
  background: #f5f7fa;
  padding: 12px;
  border-radius: 6px;
  font-size: 12px;
  font-family: 'Courier New', monospace;
  overflow-x: auto;
  margin: 0;
  max-height: 400px;
  overflow-y: auto;
}
</style>
