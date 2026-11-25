<template>
  <div class="single-analysis">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">
            <el-icon class="title-icon"><Document /></el-icon>
            {{ analysisForm.market === 'ETF' ? 'ETF分析' : '单股分析' }}
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
                  <strong>⚠️ 重要提示：</strong>本次分析所有分析结论用于学习和验证AI证券分析技术，不作为真实交易操盘指导。
                </span>
              </template>
            </el-alert>
          </div>
          
          <p class="page-description">
            AI驱动的智能证券分析，多维度评估投资价值与风险
          </p>
        </div>
      </div>
    </div>

    <!-- 主要分析表单 -->
    <div class="analysis-container">
      <el-row :gutter="24">
        <!-- 左侧：基础配置 -->
        <el-col :span="18">
          <el-card class="main-form-card" shadow="hover">
            <template #header>
              <div class="card-header">
                <h3>分析配置</h3>
                <el-tag type="info" size="small">必填信息</el-tag>
              </div>
            </template>

            <el-form :model="analysisForm" label-width="100px" class="analysis-form">
              <!-- 标的信息 -->
              <div class="form-section">
                <h4 class="section-title">📊 {{ analysisForm.market === 'ETF' ? 'ETF信息' : '股票信息' }}</h4>
                <el-row :gutter="16">
                  <el-col :span="12">
                    <el-form-item :label="analysisForm.market === 'ETF' ? 'ETF代码' : '股票代码'" required>
                      <el-input
                        v-model="analysisForm.stockCode"
                        placeholder="如：000001、512400(ETF)"
                        clearable
                        size="large"
                        class="stock-input"
                        :class="{ 'is-error': stockCodeError }"
                        @blur="validateStockCodeInput"
                        @input="onStockCodeInput"
                      >
                        <template #prefix>
                          <el-icon><TrendCharts /></el-icon>
                        </template>
                      </el-input>
                      <div v-if="stockCodeError" class="error-message">
                        <el-icon><WarningFilled /></el-icon>
                        {{ stockCodeError }}
                      </div>
                      <div v-else-if="stockCodeHelp" class="help-message">
                        <el-icon><InfoFilled /></el-icon>
                        {{ stockCodeHelp }}
                      </div>
                    </el-form-item>
                  </el-col>
                  <el-col :span="12">
                    <el-form-item label="市场类型">
                      <el-select
                        v-model="analysisForm.market"
                        placeholder="选择市场"
                        size="large"
                        style="width: 100%"
                        @change="onMarketChange"
                      >
                        <el-option label="🇨🇳 A股市场" value="A股">
                          <span>🇨🇳 A股市场</span>
                          <span style="color: #909399; font-size: 12px; margin-left: 8px;">（6位数字）</span>
                        </el-option>
                        <el-option label="📈 ETF 基金" value="ETF">
                          <span>📈 ETF 基金</span>
                          <span style="color: #909399; font-size: 12px; margin-left: 8px;">（510050、159919 等）</span>
                        </el-option>
                      </el-select>
                    </el-form-item>
                  </el-col>
                </el-row>

                <el-form-item label="分析日期">
                  <div style="display: flex; align-items: center; gap: 8px; width: 100%">
                    <el-date-picker
                      v-model="analysisForm.analysisDate"
                      type="date"
                      placeholder="选择分析基准日期"
                      size="large"
                      style="flex: 1"
                      :disabled-date="disabledDate"
                    />
                    <el-button
                      type="primary"
                      size="large"
                      :loading="validatingData"
                      @click="handleValidateData"
                      :disabled="!analysisForm.stockCode.trim()"
                      style="white-space: nowrap"
                    >
                      <el-icon><DocumentChecked /></el-icon>
                      数据检验
                    </el-button>
                  </div>
                </el-form-item>
              </div>

              <!-- 分析深度 -->
              <div class="form-section">
                <h4 class="section-title">🎯 分析深度</h4>
                <div class="depth-selector">
                  <div
                    v-for="(depth, index) in depthOptions"
                    :key="index"
                    class="depth-option"
                    :class="{ active: analysisForm.researchDepth === index + 1 }"
                    @click="analysisForm.researchDepth = index + 1"
                  >
                    <div class="depth-icon">{{ depth.icon }}</div>
                    <div class="depth-info">
                      <div class="depth-name">{{ depth.name }}</div>
                      <div class="depth-desc">{{ depth.description }}</div>
                      <div class="depth-time">{{ depth.time }}</div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 分析师团队 -->
              <div class="form-section">
                <h4 class="section-title">👥 分析师团队</h4>
                <div class="analysts-grid">
                  <div
                    v-for="analyst in availableAnalysts"
                    :key="analyst.id"
                    class="analyst-card"
                    :class="{ 
                      active: analysisForm.selectedAnalysts.includes(analyst.name),
                      disabled: analyst.disabled
                    }"
                    @click="!analyst.disabled && toggleAnalyst(analyst.name)"
                  >
                    <div class="analyst-avatar">
                      <el-icon>
                        <component :is="analyst.icon" />
                      </el-icon>
                    </div>
                    <div class="analyst-content">
                      <div class="analyst-name">
                        {{ analyst.name }}
                        <el-tag v-if="analyst.disabled" size="small" type="info" style="margin-left: 8px;">
                          仅A股
                        </el-tag>
                      </div>
                      <div class="analyst-desc">{{ analyst.description }}</div>
                    </div>
                    <div class="analyst-check">
                      <el-icon v-if="analysisForm.selectedAnalysts.includes(analyst.name)" class="check-icon">
                        <Check />
                      </el-icon>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 操作按钮 -->
              <div class="form-section">
                <!-- 执行轨迹开关 -->
                <div style="display: flex; justify-content: center; margin-bottom: 12px;">
                  <el-tooltip
                    content="开启后，系统会记录每个 Agent 的完整执行过程（Prompt全文、LLM原始返回、校验结果），用于排查分析问题。数据量较大，平时不需要时建议关闭。"
                    placement="top"
                  >
                    <el-checkbox v-model="analysisForm.enableTrace" size="small">
                      <el-icon style="margin-right: 4px;"><View /></el-icon>
                      记录执行轨迹（排查问题时开启）
                    </el-checkbox>
                  </el-tooltip>
                </div>

                <div class="action-buttons" style="display: flex; justify-content: center; align-items: center; width: 100%; text-align: center;">
                  <el-button
                    v-if="analysisStatus === 'idle'"
                    type="primary"
                    size="large"
                    @click="submitAnalysis"
                    :loading="submitting"
                    :disabled="!analysisForm.stockCode.trim()"
                    class="submit-btn large-analysis-btn"
                    style="width: 280px; height: 56px; font-size: 18px; font-weight: 700; border-radius: 16px;"
                  >
                    <el-icon><TrendCharts /></el-icon>
                    开始智能分析
                  </el-button>

                  <el-button
                    v-else-if="analysisStatus === 'running'"
                    type="warning"
                    size="large"
                    disabled
                    class="submit-btn large-analysis-btn"
                    style="width: 280px; height: 56px; font-size: 18px; font-weight: 700; border-radius: 16px;"
                  >
                    <el-icon><Loading /></el-icon>
                    分析进行中...
                  </el-button>

                  <div v-else-if="analysisStatus === 'completed'" style="display: flex; gap: 12px;">
                    <el-button
                      type="success"
                      size="large"
                      @click="showResults = !showResults"
                      class="submit-btn"
                      style="width: 180px; height: 56px; font-size: 16px; font-weight: 700; border-radius: 16px;"
                    >
                      <el-icon><Document /></el-icon>
                      {{ showResults ? '隐藏结果' : '查看结果' }}
                    </el-button>

                    <el-button
                      type="primary"
                      size="large"
                      @click="restartAnalysis"
                      class="submit-btn"
                      style="width: 180px; height: 56px; font-size: 16px; font-weight: 700; border-radius: 16px;"
                    >
                      <el-icon><Refresh /></el-icon>
                      重新分析
                    </el-button>
                  </div>

                  <el-button
                    v-else-if="analysisStatus === 'failed'"
                    type="danger"
                    size="large"
                    @click="restartAnalysis"
                    class="submit-btn large-analysis-btn"
                    style="width: 280px; height: 56px; font-size: 18px; font-weight: 700; border-radius: 16px;"
                  >
                    <el-icon><Refresh /></el-icon>
                    重新分析
                  </el-button>
                </div>
              </div>

              <!-- 分析进度显示 -->
              <div v-if="analysisStatus === 'running'" class="progress-section">
                <el-card class="progress-card" shadow="hover">
                  <template #header>
                    <div class="progress-header">
                      <h4>
                        <el-icon class="rotating-icon">
                          <Loading />
                        </el-icon>
                        分析进行中...
                      </h4>
                      <el-button
                        type="primary"
                        size="small"
                        @click="startNewAnalysis"
                        style="margin-left: auto;"
                      >
                        <el-icon><Plus /></el-icon>
                        开始新分析
                      </el-button>
                      <!-- 任务ID已隐藏 -->
                      <!-- <el-tag type="warning">{{ currentTaskId }}</el-tag> -->
                    </div>
                  </template>

                  <div class="progress-content">
                    <!-- 总体进度信息 -->
                    <div class="overall-progress-info">
                      <div class="progress-stats">
                        <!-- 当前步骤已隐藏 -->
                        <!--
                        <div class="stat-item">
                          <div class="stat-label">当前步骤</div>
                          <div class="stat-value">{{ progressInfo.currentStep || '初始化中...' }}</div>
                        </div>
                        -->
                        <!-- 整体进度已隐藏 -->
                        <!--
                        <div class="stat-item">
                          <div class="stat-label">整体进度</div>
                          <div class="stat-value">{{ progressInfo.progress.toFixed(1) }}%</div>
                        </div>
                        -->
                        <div class="stat-item">
                          <div class="stat-label">已用时间</div>
                          <div class="stat-value">{{ formatTime(progressInfo.elapsedTime) }}</div>
                        </div>
                        <div class="stat-item">
                          <div class="stat-label">预计剩余</div>
                          <div class="stat-value">{{ formatTime(progressInfo.remainingTime) }}</div>
                        </div>
                        <div class="stat-item">
                          <div class="stat-label">预计总时长</div>
                          <div class="stat-value">{{ formatTime(progressInfo.totalTime) }}</div>
                        </div>
                      </div>
                    </div>

                    <!-- 进度条 -->
                    <div class="progress-bar-section">
                      <el-progress
                        :percentage="Math.round(progressInfo.progress)"
                        :stroke-width="12"
                        :show-text="true"
                        :status="getProgressStatus()"
                        class="main-progress-bar"
                      />
                    </div>

                    <!-- 当前任务详情 -->
                    <div class="current-task-info">
                      <div class="task-title">
                        <el-icon class="task-icon">
                          <Loading />
                        </el-icon>
                        {{ progressInfo.currentStep || '正在初始化分析引擎...' }}
                      </div>
                      <div
                        class="task-description"
                        style="white-space: pre-wrap; line-height: 1.6;"
                      >
                        {{ progressInfo.currentStepDescription || progressInfo.message || 'AI正在根据您的要求重点分析相关内容' }}
                      </div>
                    </div>

                    <!-- 分析步骤显示 - 已隐藏 -->
                    <!--
                    <div v-if="analysisSteps.length > 0" class="analysis-steps">
                      <h5 class="steps-title">📋 分析步骤</h5>
                      <div class="steps-container">
                        <div
                          v-for="(step, index) in analysisSteps"
                          :key="index"
                          class="step-item"
                          :class="{
                            'step-completed': step.status === 'completed',
                            'step-current': step.status === 'current',
                            'step-pending': step.status === 'pending'
                          }"
                        >
                          <div class="step-icon">
                            <el-icon v-if="step.status === 'completed'" class="completed-icon">
                              <Check />
                            </el-icon>
                            <el-icon v-else-if="step.status === 'current'" class="current-icon rotating-icon">
                              <Loading />
                            </el-icon>
                            <el-icon v-else class="pending-icon">
                              <Clock />
                            </el-icon>
                          </div>
                          <div class="step-content">
                            <div class="step-title">{{ step.title }}</div>
                            <div class="step-description">{{ step.description }}</div>
                          </div>
                        </div>
                      </div>
                    </div>
                    -->
                  </div>
                </el-card>
              </div>
            </el-form>
          </el-card>
        </el-col>

        <!-- 右侧：高级配置 -->
        <el-col :span="6">
          <el-card class="config-card" shadow="hover">
            <template #header>
              <div class="card-header">
                <h3>高级配置</h3>
                <el-tag type="warning" size="small">可选设置</el-tag>
              </div>
            </template>

            <div class="config-content">
              <!-- AI模型配置 -->
              <div class="config-section">
                <h4 class="config-title">🤖 AI模型配置</h4>
                <div class="model-config">
                  <div class="model-item">
                    <div class="model-label">
                      <span>快速分析模型</span>
                      <el-tooltip content="用于市场分析、新闻分析、基本面分析等" placement="top">
                        <el-icon class="help-icon"><InfoFilled /></el-icon>
                      </el-tooltip>
                    </div>
                    <el-select v-model="modelSettings.quickAnalysisModel" size="small" style="width: 100%" filterable>
                      <el-option
                        v-for="model in availableModels"
                        :key="`quick-${model.provider}/${model.model_name}`"
                        :label="model.model_display_name || model.model_name"
                        :value="model.model_name"
                      >
                        <div style="display: flex; justify-content: space-between; align-items: center; gap: 8px;">
                          <span style="flex: 1;">{{ model.model_display_name || model.model_name }}</span>
                          <div style="display: flex; align-items: center; gap: 4px;">
                            <!-- 能力等级徽章 -->
                            <el-tag
                              v-if="model.capability_level"
                              :type="getCapabilityTagType(model.capability_level)"
                              size="small"
                              effect="plain"
                            >
                              {{ getCapabilityText(model.capability_level) }}
                            </el-tag>
                            <!-- 角色标签 -->
                            <el-tag
                              v-if="isQuickAnalysisRole(model.suitable_roles)"
                              type="success"
                              size="small"
                              effect="plain"
                            >
                              ⚡快速
                            </el-tag>
                            <span style="font-size: 12px; color: #909399;">{{ model.provider }}</span>
                          </div>
                        </div>
                      </el-option>
                    </el-select>
                  </div>

                  <div class="model-item">
                    <div class="model-label">
                      <span>深度决策模型</span>
                      <el-tooltip content="用于研究整合员综合决策、风险评估师最终评估" placement="top">
                        <el-icon class="help-icon"><InfoFilled /></el-icon>
                      </el-tooltip>
                    </div>
                    <DeepModelSelector v-model="modelSettings.deepAnalysisModel" :available-models="availableModels" type="deep" size="small" width="100%" />
                  </div>
                </div>

                <!-- 🆕 模型推荐提示 -->
                <el-alert
                  v-if="modelRecommendation"
                  :title="modelRecommendation.title"
                  :type="modelRecommendation.type"
                  :closable="false"
                  style="margin-top: 12px;"
                >
                  <template #default>
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 12px;">
                      <div style="font-size: 13px; line-height: 1.8; flex: 1; white-space: pre-line;">
                        {{ modelRecommendation.message }}
                      </div>
                      <el-button
                        v-if="modelRecommendation.quickModel && modelRecommendation.deepModel"
                        type="primary"
                        size="small"
                        @click="applyRecommendedModels"
                        style="flex-shrink: 0;"
                      >
                        应用推荐
                      </el-button>
                    </div>
                  </template>
                </el-alert>
              </div>

              <!--  流程选择器 -->
              <div class="config-section" v-if="workflowsSorted.length > 0">
                <h4 class="config-title">📋 分析流程</h4>
                <el-select
                  :key="`workflow-select-${analysisForm.market}`"
                  v-model="selectedWorkflowId"
                  size="small"
                  style="width: 100%"
                  placeholder="选择分析流程"
                >
                  <el-option
                    v-for="workflow in workflowsSorted"
                    :key="workflow.id"
                    :label="`${workflow.name} v${workflow.version}`"
                    :value="workflow.id"
                  />
                </el-select>
                <el-tooltip content="选择不同的分析流程，系统会使用该流程对应的智能体和步骤进行分析" placement="top">
                  <el-icon style="margin-left: 8px; color: #909399; cursor: help;"><InfoFilled /></el-icon>
                </el-tooltip>
              </div>

              <!-- 分析选项 - 已隐藏，流程内置 -->
              <!--
              <div class="config-section">
                <h4 class="config-title">⚙️ 分析选项</h4>
                <div class="option-list">
                  <div class="option-item">
                    <div class="option-info">
                      <span class="option-name">情绪分析</span>
                      <span class="option-desc">分析市场情绪和投资者心理</span>
                    </div>
                    <el-switch v-model="analysisForm.includeSentiment" />
                  </div>

                  <div class="option-item">
                    <div class="option-info">
                      <span class="option-name">风险评估</span>
                      <span class="option-desc">包含详细的风险因素分析</span>
                    </div>
                    <el-switch v-model="analysisForm.includeRisk" />
                  </div>

                  <div class="option-item">
                    <div class="option-info">
                      <span class="option-name">语言偏好</span>
                    </div>
                    <el-select v-model="analysisForm.language" size="small" style="width: 100px">
                      <el-option label="中文" value="zh-CN" />
                      <el-option label="English" value="en-US" />
                    </el-select>
                  </div>
                </div>
              </div>
              -->

            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 分析结果显示 -->
      <div v-if="showResults && analysisResults" class="results-section">
        <el-row :gutter="24">
          <el-col :span="24">
            <el-card class="results-card" shadow="hover">
              <template #header>
                <div class="results-header">
                  <h3>📊 分析结果</h3>
                  <div class="result-meta">
                    <el-tag type="success">{{ analysisResults.symbol || analysisResults.stock_symbol || analysisForm.symbol || analysisForm.stockCode }}</el-tag>
                    <el-tag>{{ analysisResults.analysis_date }}</el-tag>
                    <el-tag v-if="analysisResults.model_info && analysisResults.model_info !== 'Unknown'" type="info">
                      <el-icon><Cpu /></el-icon>
                      {{ analysisResults.model_info }}
                    </el-tag>
                  </div>
                </div>
              </template>

              <div class="results-content">
                <!-- 风险提示 -->
                <div class="risk-disclaimer">
                  <el-alert
                    type="warning"
                    :closable="false"
                    show-icon
                  >
                    <template #title>
                      <div class="disclaimer-content">
                        <el-icon class="disclaimer-icon"><WarningFilled /></el-icon>
                        <div class="disclaimer-text">
                          <p style="margin: 0 0 8px 0;"><strong>⚠️ 重要风险提示与免责声明</strong></p>
                          <ul style="margin: 0; padding-left: 20px; line-height: 1.8;">
                            <li><strong>平台性质：</strong>本平台为AI辅助分析技术学习平台，专注于AI技术在证券与ETF分析领域的应用验证和技术学习。</li>
                            <li><strong>分析目的：</strong>所有分析结论仅用于学习和验证AI辅助分析技术，不作为真实交易操盘指导或投资依据。</li>
                            <li><strong>非投资建议：</strong>所有分析结果、评分、建议仅为技术验证参考，不构成任何买卖建议或投资决策依据。</li>
                            <li><strong>数据局限性：</strong>分析基于历史数据和公开信息，可能存在延迟、不完整或不准确的情况，无法预测未来市场走势。</li>
                            <li><strong>投资风险：</strong>股票与ETF投资均存在市场风险、流动性风险、政策风险等多种风险，可能导致本金损失。</li>
                            <li><strong>独立决策：</strong>投资者应基于自身风险承受能力、投资目标和财务状况独立做出投资决策。</li>
                            <li><strong>责任声明：</strong>使用本平台产生的任何投资决策及其后果由使用者自行承担，本平台不承担任何责任。</li>
                          </ul>
                        </div>
                      </div>
                    </template>
                  </el-alert>
                </div>

                <!-- 降级节点警告 -->
                <el-alert
                  v-if="analysisResults.degraded_nodes && Object.keys(analysisResults.degraded_nodes).length > 0"
                  type="warning"
                  :closable="false"
                  show-icon
                  style="margin-bottom: 16px"
                >
                  <template #title>部分分析节点执行失败（已降级）</template>
                  <div style="margin-top: 4px; font-size: 13px; line-height: 1.6">
                    <div v-for="(info, nodeId) in analysisResults.degraded_nodes" :key="nodeId">
                      <strong>{{ info.label || nodeId }}</strong>：{{ info.error ? info.error.substring(0, 120) : '未知错误' }}
                    </div>
                    <div style="margin-top: 4px; color: #909399">其余节点的分析结果不受影响。</div>
                  </div>
                </el-alert>

                <!-- 分析概览 -->
                <div v-if="overviewBriefContent" class="overview-section">
                  <h4>📊 分析概览</h4>
                  <div class="overview-card">
                    <div class="overview-summary">
                      <div class="markdown-content" v-html="renderMarkdown(overviewBriefContent)"></div>
                    </div>

                    <!-- v2.1.0 结果页以研究简报为主入口，不再在这里重复堆叠另一张决策卡 -->
                  </div>
                </div>

                <TaskGrowthPanel
                  v-if="growthTaskId"
                  class="growth-panel-section"
                  :task-id="growthTaskId"
                />

                <!-- 详细分析报告 -->
                <div v-if="analysisResults.state || analysisResults.reports" class="reports-section">
                  <h4>📋 详细分析报告</h4>

                  <!-- 美观的标签页展示 -->
                  <div class="analysis-tabs-container">
                    <el-tabs
                      v-model="activeReportTab"
                      type="card"
                      class="analysis-tabs"
                      tab-position="top"
                      :key="analysisResults?.id || 'default'"
                    >
                      <el-tab-pane
                        v-for="(report, key) in getAnalysisReports(analysisResults)"
                        :key="key"
                        :name="key.toString()"
                        :label="report.title"
                        class="report-tab-pane"
                      >
                        <!-- 标签页内容头部 -->
                        <div class="report-header">
                          <div class="report-title">
                            <span class="report-icon">{{ getReportIcon(report.field, report.title) }}</span>
                            <span class="report-name">{{ getReportName(report.title) }}</span>
                          </div>
                          <div class="report-description">{{ getReportDescription(report.field, report.title) }}</div>
                        </div>

                        <!-- 报告内容 -->
                        <div class="report-content-wrapper">
                          <!-- AI分析免责声明 -->
                          <el-alert
                            type="info"
                            :closable="false"
                            show-icon
                            style="margin-bottom: 16px;"
                          >
                            <template #title>
                              <span style="font-size: 13px;">
                                ⚠️ 重要提示：本报告由AI基于有限资料分析生成，仅供参考，不构成投资建议。投资有风险，决策需谨慎。
                              </span>
                            </template>
                          </el-alert>
                          
                          <div
                            class="report-content"
                            v-html="formatReportContent(report.content)"
                            v-if="report.content"
                          ></div>
                          <div v-else class="no-content">
                            <el-empty description="暂无内容" />
                          </div>
                        </div>
                      </el-tab-pane>
                    </el-tabs>
                  </div>
                </div>

                <!-- 操作按钮 -->
                <div class="result-actions">
                  <el-dropdown trigger="click" @command="downloadReport">
                    <el-button type="primary">
                      <el-icon><Download /></el-icon>
                      下载报告
                      <el-icon class="el-icon--right"><arrow-down /></el-icon>
                    </el-button>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item command="markdown">
                          <el-icon><document /></el-icon> Markdown
                        </el-dropdown-item>
                        <el-dropdown-item command="docx">
                          <el-icon><document /></el-icon> Word 文档
                        </el-dropdown-item>
                        <el-dropdown-item command="pdf">
                          <el-icon><document /></el-icon> PDF
                        </el-dropdown-item>
                        <el-dropdown-item command="json" divided>
                          <el-icon><document /></el-icon> JSON (原始数据)
                        </el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                </div>

                <!-- 风险提示 -->
                <el-alert
                  type="warning"
                  :closable="false"
                  show-icon
                  class="risk-disclaimer"
                >
                  <template #title>
                    <span style="font-weight: bold;">报告依据真实交易数据使用AI分析生成，仅供参考，不构成任何投资建议。市场有风险，投资需谨慎。</span>
                  </template>
                </el-alert>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </div>
    </div>

    <!-- 数据校验结果对话框 -->
    <el-dialog
      v-model="showValidationDialog"
      title="数据检验结果"
      width="800px"
      :close-on-click-modal="false"
    >
      <div v-if="validationResult" class="validation-result">
        <!-- 总体状态 -->
        <el-alert
          :type="validationResult.is_valid ? 'success' : 'warning'"
          :closable="false"
          show-icon
          style="margin-bottom: 20px"
        >
          <template #title>
            <strong>{{ validationResult.is_valid ? '✅ 数据正常' : '⚠️ 数据不完整' }}</strong>
            <span style="margin-left: 10px; font-weight: normal;">{{ validationResult.message }}</span>
          </template>
        </el-alert>

        <!-- 缺失数据提示 -->
        <el-alert
          v-if="validationResult.missing_data && validationResult.missing_data.length > 0"
          type="error"
          :closable="false"
          show-icon
          style="margin-bottom: 20px"
        >
          <template #title>
            <strong>缺失数据：</strong>{{ validationResult.missing_data.join('、') }}
          </template>
        </el-alert>

        <!-- 详细数据表格 -->
        <div v-if="validationResult.details" class="validation-details">
          <div
            v-for="(table, index) in formatValidationDetails(validationResult.details)"
            :key="index"
            class="detail-table-section"
            style="margin-bottom: 24px"
          >
            <h4 style="margin-bottom: 12px; color: #409eff; font-size: 16px; font-weight: 600">
              {{ table.title }}
            </h4>
            <el-table
              :data="table.data"
              border
              stripe
              style="width: 100%"
              :show-header="false"
            >
              <el-table-column prop="label" width="180" label="项目">
                <template #default="{ row }">
                  <strong>{{ row.label }}</strong>
                </template>
              </el-table-column>
              <el-table-column prop="value" label="值">
                <template #default="{ row }">
                  <span v-html="row.value"></span>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </div>
      </div>

      <template #footer>
        <div style="display: flex; align-items: center; gap: 12px; justify-content: space-between;">
          <div v-if="syncStatus !== 'idle'" style="display: flex; align-items: center; gap: 8px;">
            <el-icon v-if="syncStatus === 'running'" class="is-loading" style="animation: rotate 1.5s linear infinite;">
              <Loading />
            </el-icon>
            <el-icon v-else-if="syncStatus === 'success'" style="color: #67c23a;">
              <Check />
            </el-icon>
            <el-icon v-else style="color: #f56c6c;">
              <WarningFilled />
            </el-icon>
            <span>{{ syncStatus === 'running' ? '正在同步...' : syncStatus === 'success' ? '同步完成' : '同步失败' }}</span>
          </div>
          <div style="display: flex; gap: 12px;">
            <el-button type="primary" :disabled="syncStatus === 'running'" @click="handleSyncMissingData">
              <el-icon><Refresh /></el-icon>
              同步缺失数据
            </el-button>
            <el-button @click="showValidationDialog = false">关闭</el-button>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Document,
  TrendCharts,
  InfoFilled,
  Check,
  Loading,
  Refresh,
  Download,
  WarningFilled,
  Cpu,
  ArrowDown,
  Plus,
  DocumentChecked,
  View,
} from '@element-plus/icons-vue'
import { analysisApi, type SingleAnalysisRequest } from '@/api/analysis'
import { workflowApi, isSelectableAnalysisWorkflow, type WorkflowSummary } from '@/api/workflow'
import { stocksApi, type FundamentalsResponse } from '@/api/stocks'
import { stockSyncApi, type StockSyncTaskStatus, type SingleStockSyncResponse } from '@/api/stockSync'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import { ApiClient } from '@/api/request'
import { configApi } from '@/api/config'
import DeepModelSelector from '@/components/DeepModelSelector.vue'
import TaskGrowthPanel from '@/components/growth/TaskGrowthPanel.vue'
import { ANALYSTS, convertAnalystNamesToIds } from '@/constants/analysts'
import { marked } from 'marked'
import { recommendModels } from '@/api/modelCapabilities'
import { validateStockCode, getStockCodeFormatHelp } from '@/utils/stockValidator'
import { normalizeMarketForAnalysis, getMarketByStockCode } from '@/utils/market'
import { fetchTaskResultWithRetry, hasTaskResultContent, mergeTaskResult } from '@/utils/taskResult'
import type { StockInfo } from '@/types/analysis'

// 配置marked选项
marked.setOptions({
  breaks: true,        // 支持换行符转换为<br>
  gfm: true           // 启用GitHub风格的Markdown
})

// 市场类型定义
type MarketType = 'A股' | 'ETF'

// 分析引擎类型
type AnalysisEngineType = 'legacy' | 'v2'

// 表单类型定义
interface AnalysisForm {
  stockCode: string
  symbol: string
  market: MarketType
  analysisDate: Date
  researchDepth: number
  selectedAnalysts: string[]
  includeSentiment: boolean
  includeRisk: boolean
  language: 'zh-CN' | 'en-US'
  engine: AnalysisEngineType  // 分析引擎: 固定使用 v2.0 引擎
  enableTrace: boolean  // 执行轨迹开关：默认关闭，排查问题时可开启
}

// 使用store
const router = useRouter()
const route = useRoute()

const submitting = ref(false)
const validatingData = ref(false)
const showValidationDialog = ref(false)
const validationResult = ref<any>(null)
const factorPreviewLoading = ref(false)
const factorPreview = ref<FundamentalsResponse | null>(null)
const syncStatus = ref<'idle' | 'running' | 'success' | 'error'>('idle')
const syncPollingTimer = ref<any>(null)

// 分析进度和结果相关状态
const currentTaskId = ref('')
const analysisStatus = ref('idle') // 'idle', 'running', 'completed', 'failed'
const showResults = ref(false)
const analysisResults = ref<any>(null)
const analysisReportManifest = ref<Array<{ field: string; display_name: string; icon?: string; description?: string }>>([])
const activeReportTab = ref('') // 当前激活的报告标签页
const growthTaskId = computed(() => analysisResults.value?.task_id || currentTaskId.value || null)
const progressInfo = ref({
  progress: 0,
  currentStep: '',
  currentStepDescription: '',  // 当前步骤描述
  message: '',
  elapsedTime: 0,      // 已用时间（秒）
  remainingTime: 0,    // 预计剩余时间（秒）
  totalTime: 0         // 预计总时长（秒）
})
const pollingTimer = ref<any>(null)

const applyAnalysisResult = (result: any) => {
  analysisResults.value = result
  activeReportTab.value = ''
}

const loadCompletedAnalysisResult = async (taskId: string, status?: any) => {
  const statusResult = status?.result_data && typeof status.result_data === 'object' ? status.result_data : null
  const finalResult = await fetchTaskResultWithRetry(taskId, {
    seedData: statusResult,
    isComplete: result => {
      const merged = mergeTaskResult(statusResult, result)
      console.log('📦 获取分析结果尝试:', {
        hasContent: hasTaskResultContent(merged),
        hasDecision: !!merged?.decision,
        hasSummary: !!merged?.summary,
        reportCount: Object.keys(merged?.reports || {}).length
      })
      return hasTaskResultContent(merged)
    }
  })

  return mergeTaskResult(statusResult, finalResult)
}

// 分析步骤定义（动态生成）
const analysisSteps = ref<any[]>([])

// 从后端步骤数据生成前端步骤
const generateStepsFromBackend = (backendSteps: any[]) => {
  if (!backendSteps || !Array.isArray(backendSteps)) {
    return []
  }

  return backendSteps.map((step: any, index: number) => ({
    key: `step_${index}`,
    title: step.name || `步骤 ${index + 1}`,
    description: step.description || '处理中...',
    status: 'pending'
  }))
}

// 模型设置
const modelSettings = ref({
  quickAnalysisModel: 'qwen-turbo',
  deepAnalysisModel: 'qwen-max'
})

// 可用的模型列表（从配置中获取）
const availableModels = ref<any[]>([])
const workflows = ref<WorkflowSummary[]>([])
const workflowsSorted = computed(() => {
  // 根据市场类型做级联过滤
  const expectedType = analysisForm.market === 'ETF' ? 'etf_analysis' : 'stock_analysis'
  const arr = workflows.value.filter(
    (w: WorkflowSummary) => isSelectableAnalysisWorkflow(w, expectedType)
  )
  
  // 按版本号倒序排序
  arr.sort((a, b) => {
    const vA = a.version || ''
    const vB = b.version || ''
    const verA = parseVersion(vA)
    const verB = parseVersion(vB)
    
    for (let i = 0; i < Math.max(verA.length, verB.length); i++) {
      const numA = verA[i] || 0
      const numB = verB[i] || 0
      if (numA !== numB) {
        return numB - numA
      }
    }
    return 0
  })
  
  return arr
})

// 解析版本号为数字数组
function parseVersion(v: string | number): number[] {
  const str = String(v || '')
  return str.split('.').map(p => parseInt(p.trim(), 10) || 0)
}
const selectedWorkflowId = ref<string>('v2_stock_analysis')

// 🆕 模型推荐提示
const modelRecommendation = ref<{
  title: string
  message: string
  type: 'success' | 'warning' | 'info' | 'error'
  quickModel?: string
  deepModel?: string
} | null>(null)

// 分析表单
const analysisForm = reactive<AnalysisForm>({
  stockCode: '',  // 保留用于表单绑定
  symbol: '',     // 标准化后的代码
  market: 'A股',
  analysisDate: new Date(),
  researchDepth: 3, // 默认选中3级标准分析（推荐），将在 onMounted 中从用户偏好加载
  selectedAnalysts: ['市场分析师', '基本面分析师'], // 将在 onMounted 中从用户偏好加载
  includeSentiment: true,
  includeRisk: true,
  language: 'zh-CN',
  engine: 'v2',  // 固定使用 v2.0 引擎
  enableTrace: false  // 执行轨迹：默认关闭，排查问题时可开启
})

// 监听市场类型变化，自动切换到对应类型的默认流程
watch(
  () => analysisForm.market,
  () => {
    // 使用已过滤（排除 v1.0/快速/空白流程）并按版本排序的列表
    const targetWorkflows = workflowsSorted.value
    
    if (targetWorkflows.length > 0) {
      // 优先找 is_default 的
      const defaultWf = targetWorkflows.find(w => w.is_default)
      if (defaultWf) {
        selectedWorkflowId.value = defaultWf.id
      } else {
        // 没找到的话选第一个（最高版本）
        selectedWorkflowId.value = targetWorkflows[0].id
      }
    }
  }
)

// 股票代码验证相关
const stockCodeError = ref<string>('')
const stockCodeHelp = ref<string>('')

// 深度选项（5个级别，基于实际测试数据更新）
const depthOptions = [
  { icon: '⚡', name: '1级 - 快速分析', description: '基础数据概览，快速决策', time: '2-5分钟' },
  { icon: '📈', name: '2级 - 基础分析', description: '常规投资决策', time: '3-6分钟' },
  { icon: '🎯', name: '3级 - 标准分析', description: '技术+基本面，推荐', time: '4-8分钟' },
  { icon: '🔍', name: '4级 - 深度分析', description: '多轮辩论，深度研究', time: '6-11分钟' },
  { icon: '🏆', name: '5级 - 全面分析', description: '最全面的分析报告', time: '8-16分钟' }
]

// 禁用日期
const disabledDate = (time: Date) => {
  return time.getTime() > Date.now()
}

const factorPreviewRow = computed<StockInfo>(() => ({
  symbol: analysisForm.stockCode || '',
  name: analysisForm.stockCode || '',
  market: analysisForm.market,
  report_period: factorPreview.value?.report_period,
  factor_diagnostics: factorPreview.value?.factor_diagnostics || {},
  factor_warnings: factorPreview.value?.factor_warnings || {},
}))

const clearFactorPreview = () => {
  factorPreview.value = null
}

const fetchFactorPreview = async (normalizedCode?: string) => {
  if (analysisForm.market !== 'A股') {
    clearFactorPreview()
    return
  }

  const targetCode = String(normalizedCode || analysisForm.stockCode || '').trim()
  if (!targetCode) {
    clearFactorPreview()
    return
  }

  factorPreviewLoading.value = true
  try {
    const response = await stocksApi.getFundamentals(targetCode)
    factorPreview.value = ((response as any)?.data || null) as FundamentalsResponse | null
  } catch (error) {
    console.warn('获取因子预览失败', error)
    clearFactorPreview()
  } finally {
    factorPreviewLoading.value = false
  }
}

// 股票代码输入时的处理
const onStockCodeInput = () => {
  // 清除错误信息
  stockCodeError.value = ''
  clearFactorPreview()
  // 显示格式提示
  stockCodeHelp.value = getStockCodeFormatHelp(analysisForm.market)
}

const ETF_ANALYST_NAMES = ['ETF分析师', '市场分析师', '新闻分析师']

const normalizeSelectedAnalystsForMarket = (market: MarketType, analysts: string[]) => {
  if (market === 'ETF') {
    return [...ETF_ANALYST_NAMES]
  }

  const disallowedAnalysts = ['ETF分析师']
  if (market !== 'A股') {
    disallowedAnalysts.push('大盘分析师', '板块分析师')
  }

  return analysts.filter(name => !disallowedAnalysts.includes(name))
}

// 🔥 根据市场类型过滤可用的分析师（大盘和板块分析师仅支持A股，ETF 仅显示 etf/market/news）
const availableAnalysts = computed(() => {
  const isAStock = analysisForm.market === 'A股'
  const isETF = analysisForm.market === 'ETF'
  const etfAnalystIds = ['etf', 'market', 'news']

  return ANALYSTS.filter(analyst => {
    if (isETF) return etfAnalystIds.includes(analyst.id)
    if (analyst.id === 'etf') return false
    return true
  }).map(analyst => {
    const isMacroAnalyst = analyst.id === 'index_analyst' || analyst.id === 'sector_analyst'
    return {
      ...analyst,
      disabled: !isAStock && isMacroAnalyst
    }
  })
})

// 市场类型变更时的处理
const onMarketChange = () => {
  clearFactorPreview()
  // 重新验证股票代码
  if (analysisForm.stockCode.trim()) {
    validateStockCodeInput()
  } else {
    // 显示新市场的格式提示
    stockCodeHelp.value = getStockCodeFormatHelp(analysisForm.market)
  }

  // 🔥 ETF 市场：固定使用 ETF / 市场 / 新闻 分析师
  if (analysisForm.market === 'ETF') {
    analysisForm.selectedAnalysts = [...ETF_ANALYST_NAMES]
    return
  }

  analysisForm.selectedAnalysts = normalizeSelectedAnalystsForMarket(
    analysisForm.market,
    analysisForm.selectedAnalysts
  )
}

// 验证股票代码输入
const validateStockCodeInput = () => {
  const code = analysisForm.stockCode.trim()

  if (!code) {
    stockCodeError.value = ''
    stockCodeHelp.value = ''
    return
  }

  // 验证股票代码格式
  let validation = validateStockCode(code, analysisForm.market)

  if (!validation.valid) {
    // 🔥 智能提示：A股验证失败但代码符合ETF格式时，提示用户切换市场
    if (analysisForm.market === 'A股') {
      const etfCheck = validateStockCode(code, 'ETF')
      if (etfCheck.valid) {
        stockCodeError.value = '该代码为ETF基金，请将市场类型改为「ETF 基金」'
        stockCodeHelp.value = ''
        return
      }
    }
    stockCodeError.value = validation.message || '股票代码格式不正确'
    stockCodeHelp.value = ''
  } else {
    stockCodeError.value = ''
    stockCodeHelp.value = `✓ ${validation.market}代码格式正确`

    // 自动更新市场类型（如果识别出的市场与当前选择不同）
    // V3.0 聚焦 A 股，港美股已暂停
    if (validation.market && validation.market !== analysisForm.market) {
      const validMarkets: MarketType[] = ['A股', 'ETF']
      if ((validMarkets as string[]).includes(validation.market)) {
        analysisForm.market = validation.market as MarketType
        onMarketChange()  // 同步更新分析师选择（如 ETF 固定分析师）
        ElMessage.success(`已自动识别为${validation.market}`)
      }
    }

    // 标准化代码
    if (validation.normalizedCode) {
      analysisForm.stockCode = validation.normalizedCode
    }
  }

  // 获取股票信息
  fetchStockInfo()
}

// 获取股票信息（实时行情，用于显示股票名称和当前价格）
const fetchStockInfo = async () => {
  const code = analysisForm.stockCode.trim()
  if (!code) return

  try {
    const response = await stocksApi.getQuote(code)
    const data = (response as any)?.data
    if (data) {
      // 更新 factorPreviewRow 中的名称（如果行情返回了名称）
      if (data.name && factorPreviewRow.value) {
        factorPreviewRow.value.name = data.name
      }
    }
  } catch (error) {
    // 行情获取失败不影响主流程，静默处理
    console.warn('获取股票行情失败', error)
  }
}

// 切换分析师
const toggleAnalyst = (analystName: string) => {
  const index = analysisForm.selectedAnalysts.indexOf(analystName)
  if (index > -1) {
    analysisForm.selectedAnalysts.splice(index, 1)
  } else {
    analysisForm.selectedAnalysts.push(analystName)
  }
}

// 数据校验
const handleValidateData = async () => {
  const stockCode = analysisForm.stockCode.trim()
  if (!stockCode) {
    ElMessage.warning('请先输入股票代码')
    return
  }

  // 验证股票代码格式
  let validation = validateStockCode(stockCode, analysisForm.market)
  if (!validation.valid) {
    if (analysisForm.market === 'A股') {
      const etfCheck = validateStockCode(stockCode, 'ETF')
      if (etfCheck.valid) {
        ElMessage.warning('该代码为ETF基金，请将市场类型改为「ETF 基金」后再进行数据校验')
        return
      }
    }
    ElMessage.error(validation.message || '股票代码格式不正确')
    return
  }

  // 使用标准化后的代码
  const normalizedCode = validation.normalizedCode || stockCode.toUpperCase()

  // 确定市场类型（用于API调用）
  const marketTypeMap: Record<string, string> = {
    'A股': 'cn',
    'ETF': 'cn'  // ETF 为 A 股场内基金
  }
  const marketType = marketTypeMap[analysisForm.market] || 'cn'

  // 格式化分析日期
  const analysisDate = analysisForm.analysisDate instanceof Date
    ? analysisForm.analysisDate.toISOString().split('T')[0]
    : analysisForm.analysisDate

  validatingData.value = true

  try {
    const response = await stocksApi.validateData(
      normalizedCode,
      analysisDate,
      marketType,
      {
        check_basic_info: true,
        check_historical_data: true,
        check_financial_data: true,
        check_realtime_quotes: true
      }
    )

    if (response.data) {
      const result = response.data
      await fetchFactorPreview(normalizedCode)
      
      // 显示校验结果对话框
      showValidationResultDialog(result)
    } else {
      ElMessage.error('数据校验失败：未返回结果')
    }
  } catch (error: any) {
    console.error('数据校验失败:', error)
    ElMessage.error(`数据校验失败：${error.response?.data?.detail || error.message || '未知错误'}`)
  } finally {
    validatingData.value = false
  }
}

const sleep = (ms: number) => new Promise(resolve => window.setTimeout(resolve, ms))

const isTerminalStockSyncStatus = (status?: string): boolean => {
  return status === 'success' || status === 'success_with_errors' || status === 'failed'
}

const buildSingleSyncTaskMessage = (task: StockSyncTaskStatus, symbol: string): string => {
  const result = task.result as SingleStockSyncResponse | null | undefined
  if (!result) {
    return task.error || task.message || `股票 ${symbol} 同步失败`
  }

  const parts = [`股票 ${symbol} 数据同步完成`]

  if (result.realtime_sync) {
    if (result.realtime_sync.success) {
      const dataSourceUsed = (result.realtime_sync as any).data_source_used
      if (dataSourceUsed) {
        parts.push(`实时行情同步成功（数据源 ${String(dataSourceUsed).toUpperCase()}）`)
      } else {
        parts.push('实时行情同步成功')
      }
    } else {
      parts.push(`实时行情同步失败: ${result.realtime_sync.error || '未知错误'}`)
    }
  }

  if (result.historical_sync) {
    parts.push(result.historical_sync.success ? `历史数据 ${result.historical_sync.records || 0} 条` : `历史数据同步失败: ${result.historical_sync.error || '未知错误'}`)
  }
  if (result.financial_sync) {
    parts.push(result.financial_sync.success ? '财务数据同步成功' : `财务数据同步失败: ${result.financial_sync.error || '未知错误'}`)
  }
  if (result.basic_sync) {
    parts.push(result.basic_sync.success ? '基础数据同步成功' : `基础数据同步失败: ${result.basic_sync.error || '未知错误'}`)
  }

  return parts.join('；')
}

const STOCK_SYNC_POLL_MAX_ATTEMPTS = 60
const STOCK_SYNC_POLL_INTERVAL_MS = 2000

const waitForStockSyncTask = async (taskId: string): Promise<StockSyncTaskStatus> => {
  for (let attempt = 0; attempt < STOCK_SYNC_POLL_MAX_ATTEMPTS; attempt += 1) {
    const res = await stockSyncApi.getTaskStatus(taskId)
    if (res.success && isTerminalStockSyncStatus(res.data.status)) {
      return res.data
    }

    await sleep(STOCK_SYNC_POLL_INTERVAL_MS)
  }

  throw new Error('同步任务执行超时，请稍后刷新页面查看结果')
}

const monitorSingleSyncTask = async (taskId: string, symbol: string) => {
  try {
    const task = await waitForStockSyncTask(taskId)
    const message = buildSingleSyncTaskMessage(task, symbol)
    if (task.status === 'success') {
      ElMessage.success(message)
    } else if (task.status === 'success_with_errors') {
      ElMessage.warning(message)
    } else {
      ElMessage.error(message)
    }

    // 同步完成后，重新调用数据检验
    await handleValidateData()
  } catch (error: any) {
    if (error?.message !== '页面已离开，停止等待同步结果') {
      ElMessage.error(error?.message || '同步结果查询失败，请稍后刷新页面查看')
    }
  } finally {
    clearSyncPolling()
  }
}

// 同步缺失数据
const handleSyncMissingData = async () => {
  const stockCode = analysisForm.stockCode.trim()
  const validation = validateStockCode(stockCode, analysisForm.market)

  if (!validation.valid) {
    ElMessage.error('股票代码不正确')
    return
  }

  const normalizedCode = validation.normalizedCode || stockCode.toUpperCase()
  const missingData = validationResult.value?.missing_data || [] as string[]

  // 根据缺失数据确定同步什么
  const syncTypes: string[] = []
  if (missingData.includes('实时行情')) syncTypes.push('realtime')
  if (missingData.includes('历史数据')) syncTypes.push('historical')
  if (missingData.includes('财务数据')) syncTypes.push('financial')
  if (missingData.includes('基础信息')) syncTypes.push('basic')

  // 如果没有明确指定缺失，默认都同步
  if (syncTypes.length === 0) {
    syncTypes.push('realtime', 'historical', 'financial', 'basic')
  }

  try {
    syncStatus.value = 'running'
    const res = await stockSyncApi.syncSingle({
      symbol: normalizedCode,
      sync_realtime: syncTypes.includes('realtime'),
      sync_historical: syncTypes.includes('historical'),
      sync_financial: syncTypes.includes('financial'),
      sync_basic: syncTypes.includes('basic'),
      data_source: 'akshare',
      days: 365
    })

    if (res.success) {
      ElMessage.success(`股票 ${normalizedCode} 同步任务已提交，后台执行中`)
      void monitorSingleSyncTask(res.data.task_id, normalizedCode)
    } else {
      syncStatus.value = 'error'
      ElMessage.error(res.message || '同步失败')
    }
  } catch (error: any) {
    console.error('同步失败:', error)
    syncStatus.value = 'error'
    ElMessage.error(error.message || '同步失败，请稍后重试')
  }
}

// 清理同步轮询定时器
const clearSyncPolling = () => {
  if (syncPollingTimer.value) {
    clearInterval(syncPollingTimer.value)
    syncPollingTimer.value = null
  }
}

// 显示校验结果对话框
const showValidationResultDialog = (result: any) => {
  validationResult.value = result
  showValidationDialog.value = true
  syncStatus.value = 'idle' // 重置同步状态
}

// 格式化校验结果详情为表格数据
const formatValidationDetails = (details: any) => {
  const tables: Array<{ title: string; data: Array<{ label: string; value: any }> }> = []
  
  // 基础信息
  if (details.basic_info) {
    const basicInfo = details.basic_info
    tables.push({
      title: '基础信息',
      data: [
        { label: '状态', value: basicInfo.exists ? '✅ 存在' : '❌ 不存在' },
        { label: analysisForm.market === 'ETF' ? 'ETF名称' : '股票名称', value: basicInfo.name || '-' },
        { label: '上市日期', value: basicInfo.list_date || '-' }
      ]
    })
  }
  
  // 历史数据
  if (details.historical_data) {
    const histData = details.historical_data
    tables.push({
      title: '历史数据',
      data: [
        { label: '状态', value: histData.exists ? '✅ 存在' : '❌ 不存在' },
        { label: '数据条数', value: histData.count || 0 },
        { label: '最早日期', value: histData.earliest_date || '-' },
        { label: '最新日期', value: histData.latest_date || '-' },
        { label: '分析日期数据', value: histData.analysis_date_exists ? '✅ 存在' : '⚠️ 不存在' },
        { label: '日期范围', value: histData.date_range || '-' },
        { label: '警告', value: histData.warning ? '⚠️ 是' : '✅ 否' }
      ]
    })
  }
  
  // 财务数据
  if (details.financial_data !== undefined) {
    const finData = details.financial_data
    tables.push({
      title: '财务数据',
      data: [
        { label: '状态', value: finData.exists ? '✅ 存在' : '❌ 不存在' },
        { label: '最新报告期', value: finData.latest_report_period || '-' },
        { label: '报告类型', value: finData.report_type || '-' }
      ]
    })
  }
  
  // 实时行情
  if (details.realtime_quotes !== undefined) {
    const quotesData = details.realtime_quotes
    tables.push({
      title: '实时行情',
      data: [
        { label: '状态', value: quotesData.exists ? '✅ 存在' : '❌ 不存在' },
        { label: '当前价格', value: quotesData.current_price ? `¥${quotesData.current_price}` : '-' },
        { label: '更新时间', value: quotesData.update_time || '-' }
      ]
    })
  }
  
  return tables
}



// 提交分析
const submitAnalysis = async () => {
  const stockCode = analysisForm.stockCode.trim()
  if (!stockCode) {
    ElMessage.warning('请输入股票代码')
    return
  }

  // 验证股票代码格式
  let validation = validateStockCode(stockCode, analysisForm.market)
  if (!validation.valid) {
    if (analysisForm.market === 'A股') {
      const etfCheck = validateStockCode(stockCode, 'ETF')
      if (etfCheck.valid) {
        const msg = '该代码为ETF基金，请将市场类型改为「ETF 基金」后再开始分析'
        ElMessage.warning(msg)
        stockCodeError.value = msg
        return
      }
    }
    ElMessage.error(validation.message || '股票代码格式不正确')
    stockCodeError.value = validation.message || '股票代码格式不正确'
    return
  }

  // 使用标准化后的代码
  analysisForm.symbol = validation.normalizedCode || stockCode.toUpperCase()
  await fetchFactorPreview(analysisForm.symbol)

  if (analysisForm.selectedAnalysts.length === 0) {
    ElMessage.warning('请至少选择一个分析师')
    return
  }

  // 🔥 分析前预检：检查数据源配置、基础数据同步状态
  try {
    const precheckResp = await analysisApi.precheck(analysisForm.symbol)
    const precheck = precheckResp.data || precheckResp
    if (!precheck.can_submit) {
      // 阻止提交，引导用户先完成配置/同步
      const redirect = precheck.redirect || '/settings/config'
      const reason = precheck.reason || 'unknown'
      const message = precheck.message || '请先完成系统配置'

      // 根据原因设置跳转参数
      let redirectUrl = redirect
      if (precheck.redirect_tab) {
        redirectUrl = `${redirect}?tab=${precheck.redirect_tab}`
      }

      await ElMessageBox.confirm(
        message,
        '无法开始分析',
        {
          confirmButtonText: reason === 'no_datasource' ? '去配置数据源' : '去同步数据',
          cancelButtonText: '取消',
          type: 'warning',
          showClose: true,
        }
      )
      router.push(redirectUrl)
      return
    }
  } catch (precheckErr: any) {
    // 用户点击取消或预检异常时，不继续提交
    if (precheckErr === 'cancel' || precheckErr?.toString?.().includes('cancel')) {
      return
    }
    // 预检接口本身异常，降级放行（后端 Worker 还有兜底校验）
    console.warn('⚠️ 分析预检异常，降级放行:', precheckErr)
  }

  submitting.value = true

  try {
    // 确保 analysisDate 是 Date 对象
    const analysisDate = analysisForm.analysisDate instanceof Date
      ? analysisForm.analysisDate
      : new Date(analysisForm.analysisDate)

    const request: SingleAnalysisRequest = {
      symbol: analysisForm.symbol,
      stock_code: analysisForm.symbol,  // 兼容字段
      parameters: {
        market_type: analysisForm.market,
        analysis_date: analysisDate.toISOString().split('T')[0],
        research_depth: getDepthDescription(analysisForm.researchDepth),
        selected_analysts: convertAnalystNamesToIds(analysisForm.selectedAnalysts),
        include_sentiment: analysisForm.includeSentiment,
        include_risk: analysisForm.includeRisk,
        language: analysisForm.language,
        quick_analysis_model: modelSettings.value.quickAnalysisModel,
        deep_analysis_model: modelSettings.value.deepAnalysisModel,
        engine: 'v2',  // 🔥 固定使用 v2.0 引擎（旧版引擎已隐藏）
        workflow_id: selectedWorkflowId.value,
        enable_trace: analysisForm.enableTrace  // 执行轨迹开关
      }
    }

    const response = await analysisApi.startSingleAnalysis(request)

    console.log('🔍 分析响应数据:', response)
    console.log('🔍 响应数据结构:', response.data)
    console.log('🔍 任务ID:', response.data?.task_id)

    ElMessage.success('分析任务已提交，正在处理中...')

    // 响应拦截器已返回 response.data，所以直接访问 response.data.task_id
    currentTaskId.value = response.data.task_id

    if (!currentTaskId.value) {
      console.error('❌ 任务ID为空:', response)
      ElMessage.error('任务ID获取失败，请重试')
      return
    }

    console.log('✅ 任务ID设置成功:', currentTaskId.value)

    // 保存任务状态到缓存
    saveTaskToCache(currentTaskId.value, {
      parameters: { ...analysisForm },
      submitTime: new Date().toISOString()
    })

    analysisStatus.value = 'running'
    showResults.value = false
    analysisResults.value = null
    activeReportTab.value = ''
    progressInfo.value = {
      progress: 0,
      currentStep: '正在初始化分析...',
      currentStepDescription: '分析任务已提交，正在启动分析流程',
      message: '分析任务已提交，正在启动分析流程',
      elapsedTime: 0,
      remainingTime: 0,
      totalTime: 0
    }

    // 初始化空的步骤列表，等待后端数据
    analysisSteps.value = []

    // 开始轮询任务状态
    startPollingTaskStatus()

    // 立即查询一次状态（不等待第一次轮询）
    setTimeout(async () => {
      try {
        const response = await analysisApi.getTaskStatus(currentTaskId.value)
        const status = response.data // 响应拦截器已返回 response.data
        console.log('🔄 立即查询状态:', status)
        console.log('🔄 当前 analysisStatus:', analysisStatus.value)
        if (status.status === 'pending' || status.status === 'running') {
          analysisStatus.value = 'running'
          console.log('✅ 设置 analysisStatus 为 running')
          updateProgressInfo(status)
        }
      } catch (error) {
        console.error('立即查询状态失败:', error)
      }
    }, 1000) // 1秒后查询

  } catch (error: any) {
    ElMessage.error(error.message || '提交分析失败')
  } finally {
    submitting.value = false
  }
}

// 轮询任务状态
const startPollingTaskStatus = () => {
  if (pollingTimer.value) {
    clearInterval(pollingTimer.value)
  }

  // 检查任务ID是否有效
  if (!currentTaskId.value) {
    console.error('❌ 任务ID为空，无法开始轮询')
    return
  }

  console.log('🔄 开始轮询任务状态:', currentTaskId.value)

  pollingTimer.value = setInterval(async () => {
    try {
      if (!currentTaskId.value) {
        console.error('❌ 轮询中任务ID为空')
        if (pollingTimer.value) {
          clearInterval(pollingTimer.value)
        }
        return
      }

      console.log('🔄 开始查询任务状态:', currentTaskId.value)
      const response = await analysisApi.getTaskStatus(currentTaskId.value)
      const status = response.data // 响应拦截器已返回 response.data

      console.log('🔍 任务状态响应:', response)
      console.log('🔍 任务状态数据:', status)
      console.log('🔍 当前状态:', status.status, '进度:', status.progress)

      if (status.status === 'completed') {
        if (pollingTimer.value) {
          clearInterval(pollingTimer.value)
          pollingTimer.value = null
        }

        // 分析完成，调用专门的结果API获取完整数据
        console.log('🎉 分析完成，正在获取完整结果...')

        try {
          const finalResult = await loadCompletedAnalysisResult(currentTaskId.value, status)
          applyAnalysisResult(finalResult)
          console.log('✅ 获取完整分析结果成功:', finalResult)

          // 添加调试信息
          console.log('🔍 完整结果数据结构:', {
            hasDecision: !!finalResult?.decision,
            hasState: !!finalResult?.state,
            hasReports: !!finalResult?.reports,
            hasSummary: !!finalResult?.summary,
            hasRecommendation: !!finalResult?.recommendation,
            keys: Object.keys(finalResult || {})
          })
        } catch (error) {
          console.error('❌ 获取分析结果异常:', error)
          applyAnalysisResult(status.result_data || null)
        }

        analysisStatus.value = 'completed'
        showResults.value = true
        progressInfo.value.progress = 100
        progressInfo.value.currentStep = '分析完成'
        progressInfo.value.message = '分析已完成！'

        // 任务完成后保持缓存，以便刷新后能看到结果
        // clearTaskCache() // 不清除，让用户能在30分钟内刷新查看结果

        ElMessage.success('分析完成！')

      } else if (status.status === 'failed') {
        // 分析失败
        analysisStatus.value = 'failed'
        progressInfo.value.currentStep = '分析失败'

        // 格式化错误消息（保留换行符）
        const errorMessage = status.error_message || '分析过程中发生错误'
        progressInfo.value.message = errorMessage

        if (pollingTimer.value) {
          clearInterval(pollingTimer.value)
          pollingTimer.value = null
        }

        // 任务失败时清除缓存
        clearTaskCache()

        // 显示友好的错误提示（使用 dangerouslyUseHTMLString 支持换行）
        ElMessage({
          type: 'error',
          message: errorMessage.replace(/\n/g, '<br>'),
          dangerouslyUseHTMLString: true,
          duration: 10000, // 显示10秒，让用户有时间阅读
          showClose: true
        })

      } else if (status.status === 'pending' || status.status === 'running') {
        // 分析进行中，更新进度
        console.log('🔄 轮询中设置 analysisStatus 为 running')
        analysisStatus.value = 'running'
        updateProgressInfo(status)
      }

    } catch (error) {
      console.error('获取任务状态失败:', error)
      // 继续轮询，不中断
    }
  }, 5000) // 每5秒轮询一次
}

// 更新进度信息
const updateProgressInfo = (status: any) => {
  console.log('🔄 更新进度信息:', status)
  console.log('🔄 当前进度信息:', progressInfo.value)

  // 使用后端返回的实际进度数据
  if (status.progress !== undefined) {
    console.log('📊 更新进度:', status.progress)
    progressInfo.value.progress = status.progress
  }

  if (status.current_step_name) {
    console.log('📋 更新步骤:', status.current_step_name)
    progressInfo.value.currentStep = status.current_step_name
  }

  if (status.current_step_description) {
    console.log('📝 更新步骤描述:', status.current_step_description)
    progressInfo.value.currentStepDescription = status.current_step_description
  }

  if (status.message) {
    console.log('💬 更新消息:', status.message)
    progressInfo.value.message = status.message
  }

  // 接收后端返回的时间数据
  if (status.elapsed_time !== undefined) {
    progressInfo.value.elapsedTime = status.elapsed_time
  }

  if (status.remaining_time !== undefined) {
    progressInfo.value.remainingTime = status.remaining_time
  }

  if (status.estimated_total_time !== undefined) {
    progressInfo.value.totalTime = status.estimated_total_time
  }

  // 如果后端提供了步骤数据，更新步骤列表
  if (status.steps && Array.isArray(status.steps)) {
    if (analysisSteps.value.length === 0) {
      // 首次生成步骤列表
      analysisSteps.value = generateStepsFromBackend(status.steps)
      console.log('📋 从后端生成步骤列表:', analysisSteps.value.length, '个步骤')
    }
  }

  console.log('🔄 更新后进度信息:', progressInfo.value)

  // 更新分析步骤状态
  updateAnalysisSteps(status)

  // 前端不进行估算，只展示后端返回的数据
  progressInfo.value.message = status.message || '分析正在进行中...'
}

// 重新开始分析
const restartAnalysis = () => {
  // 清除任务缓存
  clearTaskCache()

  analysisStatus.value = 'idle'
  showResults.value = false
  analysisResults.value = null
  currentTaskId.value = ''
  progressInfo.value = {
    progress: 0,
    currentStep: '',
    currentStepDescription: '',
    message: '',
    elapsedTime: 0,
    remainingTime: 0,
    totalTime: 0
  }

  if (pollingTimer.value) {
    clearInterval(pollingTimer.value)
    pollingTimer.value = null
  }
}

// 开始新分析（保留当前分析在后台运行）
const startNewAnalysis = () => {
  // 停止当前任务的轮询（但不清除任务ID，让后台继续运行）
  if (pollingTimer.value) {
    clearInterval(pollingTimer.value)
    pollingTimer.value = null
  }

  // 重置分析状态和结果，但不清除任务ID（让用户可以在任务中心查看）
  analysisStatus.value = 'idle'
  showResults.value = false
  analysisResults.value = null
  
  // 重置进度信息
  progressInfo.value = {
    progress: 0,
    currentStep: '',
    currentStepDescription: '',
    message: '',
    elapsedTime: 0,
    remainingTime: 0,
    totalTime: 0
  }

  // 清空股票代码，让用户输入新的股票代码
  analysisForm.stockCode = ''
  
  // 滚动到顶部，方便用户输入新的股票代码
  window.scrollTo({ top: 0, behavior: 'smooth' })
  
  ElMessage.success('可以开始分析新的股票了，之前的分析任务仍在后台进行中')
}


const analysisModuleMeta: Record<string, { title: string; description: string }> = {
  index_report: { title: '📊 大盘环境研究', description: '大盘指数走势、市场环境与系统性风险研究' },
  sector_report: { title: '🏭 行业板块研究', description: '行业趋势、板块轮动与同业比较研究' },
  market_report: { title: '📈 市场技术研究', description: '技术指标、趋势结构与关键位置研究' },
  fundamentals_report: { title: '💰 基本面研究', description: '财务质量、估值水平与盈利能力研究' },
  sentiment_report: { title: '💭 情绪研究', description: '市场热度、投资者情绪与讨论偏差研究' },
  news_report: { title: '📰 新闻研究', description: '公告、新闻事件与催化影响研究' },
  bull_researcher: { title: '🐂 乐观情景研究员', description: '围绕结论上修空间的研究论证' },
  bull_report: { title: '🐂 乐观情景研究员', description: '围绕结论上修空间的研究论证' },
  bear_researcher: { title: '🐻 审慎情景研究员', description: '围绕脆弱前提与下修风险的研究论证' },
  bear_report: { title: '🐻 审慎情景研究员', description: '围绕脆弱前提与下修风险的研究论证' },
  research_team_decision: { title: '🔬 平衡研究结论', description: '综合乐观与审慎材料后的研究层结论' },
  investment_plan: { title: '📋 研究经理简报', description: '研究经理对多维分析的整合摘要' },
  trader_investment_plan: { title: '🧩 研究简报', description: '面向用户的综合研究简报与阅读入口' },
  risky_analyst: { title: '🔥 高弹性情景观点', description: '结论上修条件与强化催化研究' },
  risky_opinion: { title: '🔥 高弹性情景观点', description: '结论上修条件与强化催化研究' },
  safe_analyst: { title: '🛡️ 防御情景观点', description: '脆弱前提、关键风险与下修条件研究' },
  safe_opinion: { title: '🛡️ 防御情景观点', description: '脆弱前提、关键风险与下修条件研究' },
  neutral_analyst: { title: '⚖️ 基准情景观点', description: '基准情景、证据质量与信息缺口研究' },
  neutral_opinion: { title: '⚖️ 基准情景观点', description: '基准情景、证据质量与信息缺口研究' },
  risk_management_decision: { title: '⚠️ 风险审阅结论', description: '综合情景审阅后的最终稳健性结论' },
  risk_assessment: { title: '⚠️ 风险审阅结论', description: '综合情景审阅后的最终稳健性结论' },
  final_trade_decision: { title: '📝 综合研究结论', description: '融合研究结论与风险审阅后的总览结论' },
}

const getResearchContentFingerprint = (moduleData: any) => {
  const prepared = prepareMarkdownContent(getModuleContent(moduleData) || '')
  if (!prepared) {
    return ''
  }

  return prepared
    .replace(/```[\s\S]*?```/g, '')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/^[-*+]\s+/gm, '')
    .replace(/^\d+[.)]\s+/gm, '')
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/__(.*?)__/g, '$1')
    .replace(/`([^`]*)`/g, '$1')
    .replace(/\[(.*?)\]\([^)]*\)/g, '$1')
    .replace(/[>_*|~]/g, ' ')
    .replace(/[\s\u3000]+/g, '')
}

const shouldHideDuplicateResearchManagerBrief = (moduleKey: string, reportsData: any) => {
  if (moduleKey !== 'investment_plan') {
    return false
  }

  const researchDecision = getResearchContentFingerprint(reportsData?.research_team_decision)
  const managerBrief = getResearchContentFingerprint(reportsData?.investment_plan)

  return !!researchDecision && researchDecision === managerBrief
}

const extractReportsSource = (data: any): Record<string, any> | null => {
  if (data?.reports && typeof data.reports === 'object' && Object.keys(data.reports).length > 0) {
    return data.reports
  }

  if (data?.state && typeof data.state === 'object' && Object.keys(data.state).length > 0) {
    return data.state
  }

  return null
}

const normalizeDisplayedResearchText = (content: string) => {
  if (!content) return ''

  const replacements: Array<[RegExp, string]> = [
    [/交易分析计划/g, '研究简报'],
    [/交易员计划/g, '研究简报'],
    [/初步投资计划/g, '平衡研究结论'],
    [/投资计划/g, '研究结论'],
    [/投资建议/g, '研究结论'],
    [/操作建议/g, '研究观点'],
    [/大盘指数分析/g, '大盘环境研究'],
    [/行业板块分析/g, '行业板块研究'],
    [/市场情绪分析/g, '情绪研究'],
    [/新闻事件分析/g, '新闻研究'],
    [/风险管理决策/g, '风险审阅结论'],
    [/风险审阅摘要/g, '风险审阅结论'],
    [/综合研究简报/g, '综合研究结论'],
    [/最终分析结果/g, '综合研究结论'],
    [/激进风险分析师/g, '高弹性情景分析师'],
    [/保守风险分析师/g, '防御情景分析师'],
    [/中性风险分析师/g, '基准情景分析师'],
  ]

  return replacements.reduce((text, [pattern, replacement]) => text.replace(pattern, replacement), content)
}

/**
 * 将风险审阅 JSON 对象渲染为可读的 Markdown 文本。
 * 字段与后端 risk_assessment / risk_management_decision 结构保持一致。
 */
const formatRiskAssessment = (value: any): string | null => {
  if (!value || typeof value !== 'object') return null
  const riskLevel = value.risk_level || value.riskLevel
  const riskScore = value.risk_score ?? value.riskScore
  const reasoning = value.reasoning || value.conclusion || value.summary || value.assessment
  const keyRisks = value.key_risks || value.keyRisks || value.risks
  const riskControl = value.risk_control || value.riskControl || value.control || value.suggestions
  const investmentAdjustment = value.investment_adjustment || value.investmentAdjustment || value.adjustment

  if (riskLevel === undefined && riskScore === undefined && !reasoning && !riskControl && !investmentAdjustment) {
    return null
  }

  const parts: string[] = []
  if (riskLevel !== undefined) {
    parts.push(`**风险等级**：${riskLevel}`)
  }
  if (riskScore !== undefined) {
    const score = typeof riskScore === 'number' ? riskScore.toFixed(2) : riskScore
    parts.push(`**风险评分**：${score}`)
  }
  if (reasoning) {
    parts.push(`**评估结论**：${reasoning}`)
  }
  if (Array.isArray(keyRisks) && keyRisks.length > 0) {
    parts.push(`**核心风险**：`)
    keyRisks.forEach((risk: any) => {
      if (risk) parts.push(`- ${String(risk).trim()}`)
    })
  }
  if (riskControl) {
    parts.push(`**风控建议**：${riskControl}`)
  }
  if (investmentAdjustment) {
    parts.push(`**投资调整建议**：${investmentAdjustment}`)
  }

  return parts.join('\n\n')
}

const _stripJsonCodeFence = (text: string): string => {
  // 去除 ```json ... ``` 或 ``` ... ``` 代码块包裹
  let t = text.trim()
  const fenceMatch = t.match(/^```(?:json|JSON)?\s*\n([\s\S]*?)\n```\s*$/i)
  if (fenceMatch) {
    t = fenceMatch[1].trim()
  }
  return t
}

const _looksLikeRiskJson = (text: string): boolean => {
  const lowered = text.toLowerCase()
  return (
    text.startsWith('{') &&
    (lowered.includes('"risk_level"') ||
      lowered.includes('"risk_score"') ||
      lowered.includes('"reasoning"') ||
      lowered.includes('"key_risks"') ||
      lowered.includes('"risk_control"') ||
      lowered.includes('"investment_adjustment"'))
  )
}

const extractStructuredText = (value: any): string | null => {
  if (!value) return null

  if (typeof value === 'string') {
    // 先剥离 ```json 代码块，再判断是否为风险审阅 JSON
    const stripped = _stripJsonCodeFence(value.trim())
    if (!stripped) return null

    if (_looksLikeRiskJson(stripped)) {
      try {
        const parsed = JSON.parse(stripped)
        const riskText = formatRiskAssessment(parsed)
        if (riskText) return riskText
      } catch {
        // 不是合法 JSON，按普通文本返回
      }
    }
    // 如果原文是 ```json 代码块但不是风险 JSON，返回剥离后的内容
    return stripped !== value.trim() ? stripped : value.trim()
  }

  if (typeof value === 'object') {
    // 风险审阅结构化对象直接渲染为可读文本
    const riskText = formatRiskAssessment(value)
    if (riskText) return riskText

    // 对象里嵌套 content/text 字段时，递归尝试解析
    // 真实数据结构: { content: "```json\n{...}\n```", success: true }
    for (const key of ['content', 'markdown', 'text', 'message', 'report', 'judge_decision', 'risk_assessment', 'risk_management_decision']) {
      const item = value[key]
      if (item) {
        const nested = extractStructuredText(item)
        if (nested) return nested
      }
    }
  }

  return null
}

const prepareMarkdownContent = (content: string) => {
  let preparedText = normalizeDisplayedResearchText(content || '').trim()

  if (
    ((preparedText.startsWith('"') && preparedText.endsWith('"')) ||
      (preparedText.startsWith("'") && preparedText.endsWith("'"))) &&
    preparedText.length >= 2
  ) {
    preparedText = preparedText.slice(1, -1).trim()
  }

  const fencedMarkdownMatch = preparedText.match(/^```(?:markdown|md)?\s*\n([\s\S]*?)\n```\s*$/i)
  if (fencedMarkdownMatch) {
    preparedText = fencedMarkdownMatch[1].trim()
  }

  return preparedText
}

const renderMarkdown = (content: string) => {
  if (!content) return ''

  try {
    return marked.parse(prepareMarkdownContent(content)) as string
  } catch {
    return `<pre style="white-space: pre-wrap; font-family: inherit;">${prepareMarkdownContent(content)}</pre>`
  }
}

const getModuleContent = (moduleData: any): string | null => {
  const extractedText = extractStructuredText(moduleData)
  if (extractedText) {
    return normalizeDisplayedResearchText(extractedText)
  }

  if (moduleData && typeof moduleData !== 'string') {
    return null
  }

  return typeof moduleData === 'string' ? normalizeDisplayedResearchText(moduleData) : null
}

const getOverviewBriefContent = (data: any): string | null => {
  const reportsData = extractReportsSource(data)
  const traderBrief = getModuleContent(reportsData?.trader_investment_plan)
  if (traderBrief) {
    return traderBrief
  }

  return getModuleContent(data?.summary) || getModuleContent(data?.recommendation)
}

const overviewBriefContent = computed(() => getOverviewBriefContent(analysisResults.value))

// 获取分析报告
const getAnalysisReports = (data: any) => {
  const reports: Array<{field: string, title: string, content: any}> = []

  const reportsData = extractReportsSource(data)
  if (!reportsData) {
    return reports
  }

  const isEtfAnalysis = data?.task_type === 'etf_analysis' || (Array.isArray(data?.analysts) && data.analysts.includes('etf_analyst'))
  const addedKeys = new Set<string>()

  const pushReport = (key: string, title: string, content: any) => {
    if (!content || addedKeys.has(key)) {
      return
    }
    addedKeys.add(key)
    reports.push({ field: key, title, content })
  }

  // 动态模式：使用 report_manifest（自定义工作流产出物描述）
  const manifest = data?.report_manifest as Array<{
    field: string; display_name: string; icon?: string; description?: string; category: string; order: number; is_primary: boolean
  }> | undefined
  analysisReportManifest.value = manifest || []
  if (reportsData && manifest && manifest.length > 0) {
    const sorted = [...manifest].sort((a, b) => a.order - b.order)
    for (const m of sorted) {
      const content = reportsData[m.field]
      if (content) {
        pushReport(m.field, m.display_name || m.field.replace(/_/g, ' '), content)
      }
    }
  }

  // --- 旧逻辑：内置工作流使用硬编码映射 ---
  const reportMappings = [
    { key: 'index_report', title: '📊 大盘环境研究' },
    { key: 'sector_report', title: '🏭 行业板块研究' },
    { key: 'market_report', title: '📈 市场技术研究' },
    { key: 'fundamentals_report', title: isEtfAnalysis ? '📊 ETF 分析' : '💰 基本面研究' },
    { key: 'sentiment_report', title: '💭 情绪研究' },
    { key: 'news_report', title: '📰 新闻研究' },
    { key: 'chip_report', title: '🧮 筹码分布研究' },
    // 工坊 Agent 新增
    { key: 'valuation_report', title: '📊 多维度估值分析' },
    // 研究团队（去重：优先用带后缀的）
    { key: 'bull_report', title: '🐂 乐观情景研究员' },
    { key: 'bear_report', title: '🐻 审慎情景研究员' },
    { key: 'research_team_decision', title: '🔬 平衡研究结论' },
    { key: 'investment_plan', title: '📋 研究经理简报' },
    { key: 'trader_investment_plan', title: '🧩 研究简报' },
    // 风险团队（去重：优先用带后缀的）
    { key: 'risky_opinion', title: '🔥 高弹性情景观点' },
    { key: 'safe_opinion', title: '🛡️ 防御情景观点' },
    { key: 'neutral_opinion', title: '⚖️ 基准情景观点' },
    { key: 'risk_assessment', title: '⚠️ 风险审阅结论' },
    { key: 'final_trade_decision', title: '📝 综合研究结论' },
  ]

  reportMappings.forEach(mapping => {
    if (addedKeys.has(mapping.key)) return
    if (shouldHideDuplicateResearchManagerBrief(mapping.key, reportsData)) {
      addedKeys.add(mapping.key)  // 标记为已处理，避免兜底遍历重复添加
      return
    }
    const content = reportsData?.[mapping.key]
    if (content) {
      pushReport(mapping.key, mapping.title, content)
    }
  })

  Object.keys(reportsData).forEach(key => {
    if (key === 'structured_reports' || addedKeys.has(key)) {
      return
    }

    // 跳过重复的 key（避免 researcher/analyst 后缀的重复项）
    const skipPatterns = [
      // 研究团队：跳过 _researcher 后缀（优先用 _report）
      /^bull_researcher$/,
      /^bear_researcher$/,
      // 风险团队：跳过 _analyst 后缀（优先用 _opinion）
      /^risky_analyst$/,
      /^safe_analyst$/,
      /^neutral_analyst$/,
      /^risk_management_decision$/, // 跳过这个（优先用 risk_assessment）
    ]
    if (skipPatterns.some(p => p.test(key))) {
      addedKeys.add(key)
      return
    }

    const content = reportsData[key]
    if (content) {
      pushReport(key, key.replace(/_/g, ' '), content)
    }
  })

  console.log(`📊 总共找到 ${reports.length} 个报告`)

  // 设置第一个报告为默认激活标签页
  if (reports.length > 0 && !activeReportTab.value) {
    activeReportTab.value = '0'
  }

  return reports
}

// 获取报告图标
const getReportIcon = (field: string, title: string) => {
  // 1. 优先从 manifest 获取 icon
  const manifestEntry = analysisReportManifest.value.find((m) => m.field === field)
  if (manifestEntry?.icon) {
    return manifestEntry.icon
  }
  // 2. 回退到硬编码 iconMap
  const iconMap: Record<string, string> = {
    // 🆕 宏观分析师图标
    '📊 大盘指数分析': '📊',
    '🏭 行业板块分析': '🏭',
    // 分析师团队图标
    '📈 市场技术分析': '📈',
    '💰 基本面分析': '💰',
    '📊 ETF 分析': '📊',
    '📰 新闻事件分析': '📰',
    '💭 市场情绪分析': '💭',
    '💡 初步研究观察': '💡',
    '🔬 研究团队分析': '🔬',
    '🐂 积极证据研究': '🐂',
    '🐻 谨慎证据研究': '🐻',
    '💼 研究简报': '💼',
    '⚖️ 风险管理团队': '⚖️',
    '🔥 高弹性情景研究观察': '🔥',
    '🛡️ 防御情景研究观察': '🛡️',
    '⚖️ 基准情景研究观察': '⚖️',
    '⚠️ 风险评估': '⚠️',
    '🎯 最终分析结果': '🎯'
  }
  return iconMap[title] || '📊'
}

// 获取报告名称（去掉图标前缀）
const getReportName = (title: string) => {
  return title.replace(/^[^\s]+\s/, '')
}

// 获取报告描述
const getReportDescription = (field: string, title: string) => {
  // 1. 优先从 manifest 获取 description
  const manifestEntry = analysisReportManifest.value.find((m) => m.field === field)
  if (manifestEntry?.description) {
    return manifestEntry.description
  }
  // 2. 回退到硬编码 analysisModuleMeta
  const plainTitle = title.replace(/^[^\s]+\s/, '')
  return Object.values(analysisModuleMeta).find(meta => meta.title === title)?.description
    || Object.values(analysisModuleMeta).find(meta => meta.title.endsWith(plainTitle))?.description
    || '详细研究报告'
}

// 格式化报告内容
const formatReportContent = (content: any) => {
  const normalizedContent = getModuleContent(content)
  return normalizedContent ? renderMarkdown(normalizedContent) : ''
}

// 下载报告
const downloadReport = async (format: string = 'markdown') => {
  try {
    if (!analysisResults.value && !currentTaskId.value) {
      ElMessage.error('报告尚未生成，无法下载')
      return
    }

    // 显示加载提示
    const loadingMsg = ElMessage({
      message: `正在生成${getFormatName(format)}格式报告...`,
      type: 'info',
      duration: 0
    })

    const reportId = (analysisResults.value?.id as any) || currentTaskId.value
    const res: any = await ApiClient.get(`/api/reports/${reportId}/download`, { format }, { responseType: 'blob' })

    loadingMsg.close()

    // 响应拦截器直接返回 Blob（response.data）；兼容返回 { data: Blob } 的旧实现
    const blob = res instanceof Blob ? res : (res?.data instanceof Blob ? res.data : new Blob([res]))
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    const code =
      analysisResults.value?.stock_code ||
      analysisResults.value?.stock_symbol ||
      analysisResults.value?.symbol ||
      'stock'
    const dateStr = analysisResults.value?.analysis_date || new Date().toISOString().slice(0, 10)

    // 根据格式设置文件扩展名
    const ext = getFileExtension(format)
    a.download = `${String(code)}_分析报告_${String(dateStr).slice(0, 10)}.${ext}`

    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)

    ElMessage.success(`${getFormatName(format)}报告下载成功`)
  } catch (err: any) {
    console.error('下载报告出错:', err)

    // 显示详细错误信息
    if (err.message && err.message.includes('pandoc')) {
      ElMessage.error({
        message: 'Word 导出需要安装 pandoc 工具（PDF 导出不需要 pandoc）',
        duration: 5000
      })
    } else if (err.message && (err.message.includes('weasyprint') || err.message.includes('pdfkit'))) {
      ElMessage.error({
        message: 'PDF 导出需要安装 PDF 引擎：pip install weasyprint（推荐）',
        duration: 5000
      })
    } else {
      ElMessage.error(`下载报告失败: ${err.message || '未知错误'}`)
    }
  }
}

// 辅助函数：获取格式名称
const getFormatName = (format: string): string => {
  const names: Record<string, string> = {
    'markdown': 'Markdown',
    'docx': 'Word',
    'pdf': 'PDF',
    'json': 'JSON'
  }
  return names[format] || format
}

// 辅助函数：获取文件扩展名
const getFileExtension = (format: string): string => {
  const extensions: Record<string, string> = {
    'markdown': 'md',
    'docx': 'docx',
    'pdf': 'pdf',
    'json': 'json'
  }
  return extensions[format] || 'txt'
}

// 组件销毁时清理定时器
onUnmounted(() => {
  if (pollingTimer.value) {
    clearInterval(pollingTimer.value)
    pollingTimer.value = null
  }
  clearSyncPolling()
})

// 页面可见性变化时的处理
const handleVisibilityChange = () => {
  if (document.hidden) {
    console.log('📱 页面隐藏，暂停轮询')
  } else {
    console.log('📱 页面显示，恢复轮询')
    // 页面重新可见时，立即查询一次状态
    if (currentTaskId.value && analysisStatus.value === 'running') {
      setTimeout(async () => {
        try {
          const response = await analysisApi.getTaskStatus(currentTaskId.value)
          const status = response.data // 响应拦截器已返回 response.data
          console.log('🔄 页面恢复查询状态:', status)
          if (status.status === 'pending' || status.status === 'running') {
            analysisStatus.value = 'running'
            updateProgressInfo(status)
          }
        } catch (error) {
          console.error('页面恢复查询状态失败:', error)
        }
      }, 500)
    }
  }
}

// 监听页面可见性变化
document.addEventListener('visibilitychange', handleVisibilityChange)

// 获取深度描述
const getDepthDescription = (depth: number) => {
  const descriptions = ['快速', '基础', '标准', '深度', '全面']
  return descriptions[depth - 1] || '标准'
}

// 获取进度条状态
const getProgressStatus = () => {
  if (analysisStatus.value === 'completed') {
    return 'success'
  } else if (analysisStatus.value === 'failed') {
    return 'exception'
  } else if (analysisStatus.value === 'running') {
    return '' // 默认状态，显示蓝色进度条
  }
  return ''
}

// 简单的时间格式化方法（只用于显示后端返回的时间）
const formatTime = (seconds: number) => {
  if (!seconds || seconds <= 0) {
    return '计算中...'
  }

  if (seconds < 60) {
    return `${Math.floor(seconds)}秒`
  } else if (seconds < 3600) {
    const minutes = Math.floor(seconds / 60)
    const remainingSeconds = Math.floor(seconds % 60)
    return remainingSeconds > 0 ? `${minutes}分${remainingSeconds}秒` : `${minutes}分钟`
  } else {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    return `${hours}小时${minutes}分钟`
  }
}

// 更新分析步骤状态
const updateAnalysisSteps = (status: any) => {
  console.log('📋 步骤更新输入:', status)

  if (analysisSteps.value.length === 0) {
    console.log('📋 没有步骤定义，跳过更新')
    return
  }

  // 优先使用后端提供的详细步骤信息
  let currentStepIndex = 0

  if (status.current_step !== undefined) {
    // 后端提供了精确的步骤索引
    currentStepIndex = status.current_step
    console.log('📋 使用后端步骤索引:', currentStepIndex)
  } else {
    // 兜底方案：使用进度百分比估算
    const progress = status.progress_percentage || status.progress || 0
    if (progress > 0) {
      const progressRatio = progress / 100
      currentStepIndex = Math.floor(progressRatio * (analysisSteps.value.length - 1))
      if (progress > 0 && currentStepIndex === 0) {
        currentStepIndex = 1
      }
    }
    console.log('📋 使用进度估算步骤索引:', currentStepIndex, '进度:', progress)
  }

  // 确保索引在有效范围内
  currentStepIndex = Math.max(0, Math.min(currentStepIndex, analysisSteps.value.length - 1))

  console.log('📋 最终步骤索引:', currentStepIndex, '/', analysisSteps.value.length)

  // 更新所有步骤状态
  analysisSteps.value.forEach((step, index) => {
    if (index < currentStepIndex) {
      step.status = 'completed'
    } else if (index === currentStepIndex) {
      step.status = 'current'
    } else {
      step.status = 'pending'
    }
  })

  const statusSummary = analysisSteps.value.map((s, i) => `${i}:${s.status}`).join(', ')
  console.log('📋 步骤状态更新完成:', statusSummary)
}

// 初始化模型设置
const initializeModelSettings = async () => {
  try {
    // 获取默认模型
    const defaultModels = await configApi.getDefaultModels()
    modelSettings.value.quickAnalysisModel = defaultModels.quick_analysis_model
    modelSettings.value.deepAnalysisModel = defaultModels.deep_analysis_model

    // 获取所有可用的模型列表
    const llmConfigs = await configApi.getLLMConfigs()
    availableModels.value = llmConfigs.filter((config: any) => config.enabled)

    console.log('✅ 加载模型配置成功:', {
      quick: modelSettings.value.quickAnalysisModel,
      deep: modelSettings.value.deepAnalysisModel,
      available: availableModels.value.length
    })
    console.log('🔍 可用模型详细信息:', availableModels.value.map(m => ({
      model_name: m.model_name,
      model_display_name: m.model_display_name,
      provider: m.provider
    })))
  } catch (error) {
    console.error('加载默认模型配置失败:', error)
    modelSettings.value.quickAnalysisModel = 'qwen-turbo'
    modelSettings.value.deepAnalysisModel = 'qwen-max'
  }
}

// 任务状态缓存管理
const TASK_CACHE_KEY = 'trading_analysis_task'
const TASK_CACHE_DURATION = 30 * 60 * 1000 // 30分钟

// 保存任务状态到缓存
const saveTaskToCache = (taskId: string, taskData: any) => {
  const cacheData = {
    taskId,
    taskData,
    timestamp: Date.now()
  }
  localStorage.setItem(TASK_CACHE_KEY, JSON.stringify(cacheData))
  console.log('💾 任务状态已缓存:', taskId)
}

// 从缓存获取任务状态
const getTaskFromCache = () => {
  try {
    const cached = localStorage.getItem(TASK_CACHE_KEY)
    if (!cached) return null

    const cacheData = JSON.parse(cached)
    const now = Date.now()

    // 检查是否过期（30分钟）
    if (now - cacheData.timestamp > TASK_CACHE_DURATION) {
      localStorage.removeItem(TASK_CACHE_KEY)
      console.log('🗑️ 缓存已过期，已清理')
      return null
    }

    console.log('📦 从缓存恢复任务:', cacheData.taskId)
    return cacheData
  } catch (error) {
    console.error('❌ 读取缓存失败:', error)
    localStorage.removeItem(TASK_CACHE_KEY)
    return null
  }
}

// 清除任务缓存
const clearTaskCache = () => {
  localStorage.removeItem(TASK_CACHE_KEY)
  console.log('🗑️ 任务缓存已清除')
}

// 恢复任务状态
const restoreTaskFromCache = async () => {
  const cached = getTaskFromCache()
  if (!cached) return false

  try {
    console.log('🔄 尝试恢复任务状态:', cached.taskId)

    // 查询任务当前状态
    const response = await analysisApi.getTaskStatus(cached.taskId)
    const status = response.data // 响应拦截器已返回 response.data

    console.log('📊 恢复的任务状态:', status)

    if (status.status === 'completed') {
      // 任务已完成，显示结果
      currentTaskId.value = cached.taskId
      analysisStatus.value = 'completed'
      showResults.value = true
      applyAnalysisResult(await loadCompletedAnalysisResult(cached.taskId, status))
      progressInfo.value.progress = 100
      progressInfo.value.currentStep = '分析完成'
      progressInfo.value.message = '分析已完成'

      // 恢复分析参数
      if (cached.taskData.parameters) {
        Object.assign(analysisForm, cached.taskData.parameters)
      }

      console.log('✅ 任务已完成，显示结果')
      return true

    } else if (status.status === 'pending' || status.status === 'running') {
      // 任务仍在运行，恢复进度显示
      currentTaskId.value = cached.taskId
      analysisStatus.value = 'running'
      showResults.value = false
      updateProgressInfo(status)

      // 恢复分析参数
      if (cached.taskData.parameters) {
        Object.assign(analysisForm, cached.taskData.parameters)
      }

      // 启动轮询
      startPollingTaskStatus()

      console.log('🔄 任务仍在运行，恢复进度显示')
      return true

    } else if (status.status === 'failed') {
      // 任务失败
      analysisStatus.value = 'failed'
      progressInfo.value.currentStep = '分析失败'
      progressInfo.value.message = status.error_message || '分析过程中发生错误'

      // 清除缓存
      clearTaskCache()

      console.log('❌ 任务失败')
      return true

    } else {
      // 其他状态，清除缓存
      clearTaskCache()
      console.log('🤔 未知任务状态，清除缓存')
      return false
    }

  } catch (error) {
    console.error('❌ 恢复任务状态失败:', error)
    // 如果查询失败，可能是任务不存在了，清除缓存
    clearTaskCache()
    return false
  }
}

// 🆕 模型能力相关辅助函数

/**
 * 获取能力等级文本
 */
const getCapabilityText = (level: number): string => {
  const texts: Record<number, string> = {
    1: '⚡基础',
    2: '📊标准',
    3: '🎯高级',
    4: '🔥专业',
    5: '👑旗舰'
  }
  return texts[level] || '📊标准'
}

/**
 * 获取能力等级标签类型
 */
const getCapabilityTagType = (level: number): 'success' | 'info' | 'warning' | 'danger' => {
  if (level >= 4) return 'danger'
  if (level >= 3) return 'warning'
  if (level >= 2) return 'success'
  return 'info'
}

/**
 * 判断是否适合快速分析
 */
const isQuickAnalysisRole = (roles: string[] | undefined): boolean => {
  if (!roles || !Array.isArray(roles)) return false
  return roles.includes('quick_analysis') || roles.includes('both')
}

/**
 * 判断是否适合深度分析
 */
/**
 * 显示分析深度的模型推荐说明
 */
const checkModelSuitability = async () => {
  const depthNames: Record<number, string> = {
    1: '快速',
    2: '基础',
    3: '标准',
    4: '深度',
    5: '全面'
  }
  const depthName = depthNames[analysisForm.researchDepth] || '标准'

  try {
    // 获取推荐模型
    const recommendRes = await recommendModels(depthName)
    const responseData = recommendRes?.data?.data

    if (responseData) {
      const quickModel = responseData.quick_model || '未知'
      const deepModel = responseData.deep_model || '未知'

      // 获取模型的显示名称
      const quickModelInfo = availableModels.value.find(m => m.model_name === quickModel)
      const deepModelInfo = availableModels.value.find(m => m.model_name === deepModel)

      const quickDisplayName = quickModelInfo?.model_display_name || quickModel
      const deepDisplayName = deepModelInfo?.model_display_name || deepModel

      // 获取推荐理由
      const reason = responseData.reason || ''

      // 构建推荐说明
      const depthDescriptions: Record<number, string> = {
        1: '快速浏览，获取基本信息',
        2: '基础分析，了解主要指标',
        3: '标准分析，全面评估股票',
        4: '深度研究，挖掘投资机会',
        5: '全面分析，专业投资决策'
      }

      const message = `${depthDescriptions[analysisForm.researchDepth] || '标准分析'}\n\n推荐模型配置：\n• 快速模型：${quickDisplayName}\n• 深度模型：${deepDisplayName}\n\n${reason}`

      modelRecommendation.value = {
        title: '💡 模型推荐',
        message,
        type: 'info',
        quickModel,
        deepModel
      }
    } else {
      // 如果没有推荐数据，显示通用说明
      const generalDescriptions: Record<number, string> = {
        1: '快速分析：使用基础模型即可，注重速度和成本',
        2: '基础分析：快速模型用基础级，深度模型用标准级',
        3: '标准分析：快速模型用基础级，深度模型用标准级以上',
        4: '深度分析：快速模型用标准级，深度模型用高级以上，需要推理能力',
        5: '全面分析：快速模型用标准级，深度模型用专业级以上，强推理能力'
      }

      modelRecommendation.value = {
        title: '💡 模型推荐',
        message: generalDescriptions[analysisForm.researchDepth] || generalDescriptions[3],
        type: 'info'
      }
    }
  } catch (error) {
    console.error('获取模型推荐失败:', error)
    // 显示通用说明
    const generalDescriptions: Record<number, string> = {
      1: '快速分析：使用基础模型即可，注重速度和成本',
      2: '基础分析：快速模型用基础级，深度模型用标准级',
      3: '标准分析：快速模型用基础级，深度模型用标准级以上',
      4: '深度分析：快速模型用标准级，深度模型用高级以上，需要推理能力',
      5: '全面分析：快速模型用标准级，深度模型用专业级以上，强推理能力'
    }

    modelRecommendation.value = {
      title: '💡 模型推荐',
      message: generalDescriptions[analysisForm.researchDepth] || generalDescriptions[3],
      type: 'info'
    }
  }
}

// 应用推荐的模型配置
const applyRecommendedModels = () => {
  if (modelRecommendation.value?.quickModel && modelRecommendation.value?.deepModel) {
    modelSettings.value.quickAnalysisModel = modelRecommendation.value.quickModel
    modelSettings.value.deepAnalysisModel = modelRecommendation.value.deepModel

    // 清除推荐提示
    modelRecommendation.value = null

    ElMessage.success('已应用推荐的模型配置')
  }
}

// 监听分析深度变化
import { watch } from 'vue'
watch(() => analysisForm.researchDepth, () => {
  checkModelSuitability()
})

// 监听模型选择变化
watch([() => modelSettings.value.quickAnalysisModel, () => modelSettings.value.deepAnalysisModel], () => {
  checkModelSuitability()
})

// 页面初始化
onMounted(async () => {
  initializeModelSettings()

  // 🆕 从用户偏好加载默认设置
  const authStore = useAuthStore()
  const appStore = useAppStore()

  // 优先从 authStore.user.preferences 读取，其次从 appStore.preferences 读取
  const userPrefs = authStore.user?.preferences
  if (userPrefs) {
    // 加载默认市场
    if (userPrefs.default_market) {
      analysisForm.market = userPrefs.default_market as MarketType
    }

    // 加载默认分析深度（转换为数字）
    if (userPrefs.default_depth) {
      analysisForm.researchDepth = parseInt(userPrefs.default_depth)
    }

    // 加载默认分析师
    if (userPrefs.default_analysts && userPrefs.default_analysts.length > 0) {
      analysisForm.selectedAnalysts = normalizeSelectedAnalystsForMarket(
        analysisForm.market,
        [...userPrefs.default_analysts]
      )
    }

    console.log('✅ 已加载用户偏好设置:', {
      market: analysisForm.market,
      depth: analysisForm.researchDepth,
      analysts: analysisForm.selectedAnalysts
    })
  } else {
    // 降级到 appStore.preferences
    if (appStore.preferences.defaultMarket) {
      analysisForm.market = appStore.preferences.defaultMarket as MarketType
    }
    if (appStore.preferences.defaultDepth) {
      analysisForm.researchDepth = parseInt(appStore.preferences.defaultDepth)
    }
    console.log('✅ 已加载应用偏好设置（降级）')
  }

  // 接收一次路由参数（从筛选页带入）- 路由参数优先级最高
  const q = route.query as any
  const hasNewStock = !!q?.stock
  if (hasNewStock) {
    analysisForm.stockCode = String(q.stock)
    // 🔥 关键修复：如果有新的股票代码，清除旧任务缓存
    clearTaskCache()
    console.log('🔄 检测到新股票代码，已清除旧任务缓存:', q.stock)

    // 🆕 自动识别市场类型（如果URL中没有明确指定market参数）
    if (!q?.market) {
      const detectedMarket = getMarketByStockCode(analysisForm.stockCode)
      analysisForm.market = detectedMarket as MarketType
      if (detectedMarket === 'ETF') {
        analysisForm.selectedAnalysts = [...ETF_ANALYST_NAMES]
      } else {
        analysisForm.selectedAnalysts = normalizeSelectedAnalystsForMarket(
          detectedMarket as MarketType,
          analysisForm.selectedAnalysts
        )
      }
      console.log('🔍 自动识别市场类型:', analysisForm.stockCode, '->', detectedMarket)
    }
  }
  if (q?.market) {
    analysisForm.market = normalizeMarketForAnalysis(q.market) as MarketType
    // 🔥 如果从路由参数设置市场类型，也需要同步分析师
    if (analysisForm.market === 'ETF') {
      analysisForm.selectedAnalysts = [...ETF_ANALYST_NAMES]
    } else {
      analysisForm.selectedAnalysts = normalizeSelectedAnalystsForMarket(
        analysisForm.market,
        analysisForm.selectedAnalysts
      )
    }
  }

  if (analysisForm.market === 'A股' && analysisForm.stockCode) {
    await fetchFactorPreview(analysisForm.stockCode)
  }

  // 尝试恢复任务状态（仅当没有新股票代码时）
  if (!hasNewStock) {
    await restoreTaskFromCache()
  }

  // 🆕 初始检查模型适用性
  await checkModelSuitability()
  try {
    workflows.value = await workflowApi.listAll()
    console.log('[SingleAnalysis] 加载的所有流程:', workflows.value)
    console.log('[SingleAnalysis] 过滤后的流程:', workflowsSorted.value)
    
    // 优先选择标记为 is_default 的流程
    const defaultWorkflow = workflowsSorted.value.find(w => w.is_default)
    if (defaultWorkflow) {
      selectedWorkflowId.value = defaultWorkflow.id
      console.log('[SingleAnalysis] 选中默认流程:', defaultWorkflow.id, defaultWorkflow.name)
    } else if (workflowsSorted.value.length > 0) {
      // 如果没有标记默认，选择第一个
      selectedWorkflowId.value = workflowsSorted.value[0].id
      console.log('[SingleAnalysis] 没有默认流程，选中第一个:', workflowsSorted.value[0].id, workflowsSorted.value[0].name)
    }
  } catch (error) {
    console.debug('[SingleAnalysis] 加载工作流失败，保留当前默认模板:', error)
  }
})

</script>

<style lang="scss" scoped>
.single-analysis {
  min-height: 100vh;
  background: var(--el-bg-color-page);
  padding: 24px;

  .page-header {
    margin-bottom: 32px;

    .header-content {
      background: var(--el-bg-color);
      padding: 32px;
      border-radius: 16px;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
    }

    .title-section {
      .page-title {
        display: flex;
        align-items: center;
        font-size: 32px;
        font-weight: 700;
        color: #1a202c;
        margin: 0 0 12px 0;

        .title-icon {
          margin-right: 12px;
          color: #3b82f6;
        }
      }

      .risk-disclaimer {
        margin: 0 0 12px 0;
      }

      .page-description {
        font-size: 16px;
        color: #64748b;
        margin: 0;
      }
    }
  }

  .analysis-container {
    .main-form-card, .config-card {
      border-radius: 16px;
      border: none;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);

      :deep(.el-card__header) {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 16px 16px 0 0;
        padding: 20px 24px;

        .card-header {
          display: flex;
          justify-content: space-between;
          align-items: center;

          h3 {
            margin: 0;
            font-size: 18px;
            font-weight: 600;
          }
        }
      }

      :deep(.el-card__body) {
        padding: 24px;
      }
    }

    .analysis-form {
      .form-section {
        margin-bottom: 32px;
        width: 100%;
        display: flex;
        flex-direction: column;

        .section-title {
          font-size: 16px;
          font-weight: 600;
          color: #1a202c;
          margin: 0 0 16px 0;
          padding-bottom: 8px;
          border-bottom: 2px solid #e2e8f0;
        }

        .factor-preview-card {
          padding: 16px;
          border: 1px solid #e2e8f0;
          border-radius: 12px;
          background: #f8fafc;
        }

        .factor-preview-meta {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          margin-bottom: 12px;
          font-size: 13px;
          color: #475569;
        }

        .factor-preview-tags {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
        }

        .factor-preview-tag {
          cursor: help;
        }

        .factor-preview-popover {
          display: flex;
          flex-direction: column;
          gap: 6px;
          line-height: 1.6;
        }

        .factor-preview-popover-title {
          font-weight: 600;
          color: #1e293b;
        }

        .factor-preview-line {
          font-size: 13px;
          color: #475569;
        }
      }

      .stock-input {
        :deep(.el-input__inner) {
          font-weight: 600;
          text-transform: uppercase;
        }

        &.is-error {
          :deep(.el-input__inner) {
            border-color: #f56c6c;
          }
        }
      }

      .error-message {
        display: flex;
        align-items: center;
        gap: 4px;
        margin-top: 8px;
        font-size: 12px;
        color: #f56c6c;

        .el-icon {
          font-size: 14px;
        }
      }

      .help-message {
        display: flex;
        align-items: center;
        gap: 4px;
        margin-top: 8px;
        font-size: 12px;
        color: #67c23a;

        .el-icon {
          font-size: 14px;
        }
      }

      .depth-selector {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 12px;

        .depth-option {
          display: flex;
          align-items: center;
          padding: 16px;
          border: 2px solid #e2e8f0;
          border-radius: 12px;
          cursor: pointer;
          transition: all 0.3s ease;

          &:hover {
            border-color: #3b82f6;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
          }

          &.active {
            border-color: #3b82f6;
            background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
            color: #1e40af;
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(59, 130, 246, 0.15);
          }

          .depth-icon {
            font-size: 24px;
            margin-right: 12px;
          }

          .depth-info {
            .depth-name {
              font-weight: 600;
              margin-bottom: 4px;
            }

            .depth-desc {
              font-size: 12px;
              opacity: 0.8;
              margin-bottom: 2px;
            }

            .depth-time {
              font-size: 11px;
              opacity: 0.7;
            }
          }
        }
      }

      .analysts-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 16px;

        .analyst-card {
          display: flex;
          align-items: center;
          padding: 16px;
          border: 2px solid #e2e8f0;
          border-radius: 12px;
          cursor: pointer;
          transition: all 0.3s ease;

          &:hover {
            border-color: #3b82f6;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
          }

          &.active {
            border-color: #3b82f6;
            background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
            color: #1e40af;
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(59, 130, 246, 0.15);
          }

          &.disabled {
            opacity: 0.5;
            cursor: not-allowed;

            &:hover {
              transform: none;
              box-shadow: none;
              border-color: #e2e8f0;
            }
          }

          .analyst-avatar {
            width: 48px;
            height: 48px;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.2);
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 16px;
            font-size: 20px;
          }

          .analyst-content {
            flex: 1;

            .analyst-name {
              font-weight: 600;
              margin-bottom: 4px;
            }

            .analyst-desc {
              font-size: 12px;
              opacity: 0.8;
            }
          }

          .analyst-check {
            .check-icon {
              font-size: 20px;
              color: #3b82f6;
            }
          }

          &.active .analyst-check .check-icon {
            color: #1e40af;
          }

          // 🔥 禁用状态样式
          &.disabled {
            opacity: 0.5;
            cursor: not-allowed;
            background-color: #f9fafb;
            border-color: #e5e7eb;

            &:hover {
              transform: none;
              box-shadow: none;
              border-color: #e5e7eb;
            }

            .analyst-name {
              color: #9ca3af;
            }

            .analyst-desc {
              color: #9ca3af;
            }

            .analyst-avatar {
              opacity: 0.5;
            }
          }
        }
      }
    }

    .config-card {
      .config-content {
        .config-section {
          margin-bottom: 24px;

          .config-title {
            font-size: 14px;
            font-weight: 600;
            color: #1a202c;
            margin: 0 0 12px 0;
            display: flex;
            align-items: center;
            gap: 8px;
          }

          .model-config {
            .model-item {
              margin-bottom: 16px;

              .model-label {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 8px;
                font-size: 13px;
                color: #374151;

                .help-icon {
                  color: #9ca3af;
                  cursor: help;
                }
              }
            }
          }

          .option-list {
            .option-item {
              display: flex;
              align-items: center;
              justify-content: space-between;
              padding: 12px 0;
              border-bottom: 1px solid #f3f4f6;

              &:last-child {
                border-bottom: none;
              }

              .option-info {
                .option-name {
                  font-size: 14px;
                  font-weight: 500;
                  color: #374151;
                  display: block;
                  margin-bottom: 2px;
                }

                .option-desc {
                  font-size: 12px;
                  color: #6b7280;
                }
              }
            }
          }

          .custom-input {
            :deep(.el-textarea__inner) {
              border-radius: 8px;
              border: 1px solid #d1d5db;

              &:focus {
                border-color: #3b82f6;
                box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
              }
            }
          }

          .input-help {
            font-size: 12px;
            color: #6b7280;
            margin-top: 8px;
          }

          .action-buttons {
            display: flex !important;
            justify-content: center !important;
            align-items: center !important;
            margin-top: 24px !important;
            width: 100% !important;
            text-align: center !important;

            .submit-btn.el-button {
              width: 280px !important;
              height: 56px !important;
              font-size: 18px !important;
              font-weight: 700 !important;
              background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%) !important;
              border: none !important;
              border-radius: 16px !important;
              transition: all 0.3s ease !important;
              box-shadow: 0 4px 15px rgba(59, 130, 246, 0.2) !important;
              min-width: 280px !important;
              max-width: 280px !important;

              &:hover {
                transform: translateY(-3px) !important;
                box-shadow: 0 12px 30px rgba(59, 130, 246, 0.4) !important;
                background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%) !important;
              }

              &:disabled {
                opacity: 0.6 !important;
                transform: none !important;
                box-shadow: 0 4px 15px rgba(59, 130, 246, 0.1) !important;
              }

              .el-icon {
                margin-right: 8px !important;
                font-size: 20px !important;
              }

              span {
                font-size: 18px !important;
                font-weight: 700 !important;
              }
            }
          }
        }
      }
    }

    .action-section {
      margin-top: 24px;
      display: flex;
      gap: 16px;

      .submit-btn {
        flex: 1;
        height: 48px;
        font-size: 16px;
        font-weight: 600;
        background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
        border: none;
        border-radius: 12px;
        transition: all 0.3s ease;

        &:hover {
          transform: translateY(-2px);
          box-shadow: 0 8px 25px rgba(59, 130, 246, 0.3);
        }

        &:disabled {
          opacity: 0.6;
          transform: none;
          box-shadow: none;
        }
      }

      .reset-btn {
        height: 48px;
        font-size: 16px;
        border-radius: 12px;
        border: 2px solid #e5e7eb;
        color: #6b7280;
        transition: all 0.3s ease;

        &:hover {
          border-color: #d1d5db;
          color: #374151;
          transform: translateY(-1px);
        }
      }
    }
  }
}

// 分析步骤样式
.step-item {
  display: flex;
  align-items: flex-start;
  padding: 12px 0;
  border-left: 3px solid #e5e7eb;
  margin-left: 15px;
  position: relative;
  transition: all 0.3s ease;

  &.step-completed {
    border-left-color: #10b981;

    .step-icon {
      background: linear-gradient(135deg, #10b981 0%, #059669 100%);
      color: white;
      box-shadow: 0 2px 8px rgba(16, 185, 129, 0.3);
    }

    .step-title {
      color: #10b981;
      font-weight: 600;
    }

    .step-description {
      color: #059669;
    }
  }

  &.step-current {
    border-left-color: #3b82f6;
    background: linear-gradient(90deg, rgba(59, 130, 246, 0.05) 0%, transparent 100%);

    .step-icon {
      background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
      color: white;
      box-shadow: 0 2px 12px rgba(59, 130, 246, 0.4);
    }

    .step-title {
      color: #3b82f6;
      font-weight: 700;
    }

    .step-description {
      color: #1d4ed8;
      font-weight: 500;
    }
  }

  &.step-pending {
    .step-icon {
      background: #f3f4f6;
      color: #9ca3af;
      border: 2px solid #e5e7eb;
    }

    .step-title {
      color: #6b7280;
    }

    .step-description {
      color: #9ca3af;
    }
  }
}

.step-icon {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-left: -16px;
  margin-right: 16px;
  font-size: 14px;
  flex-shrink: 0;
  z-index: 1;
  transition: all 0.3s ease;
}

.completed-icon {
  color: white;
}

.current-icon {
  color: white;
}

.pending-icon {
  color: #9ca3af;
}

.step-content {
  flex: 1;
  min-width: 0;
  padding-right: 16px;
}

.step-title {
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 4px;
  line-height: 1.4;
}

.step-description {
  font-size: 12px;
  line-height: 1.4;
  opacity: 0.9;
}

/* 脉冲动画 */
@keyframes pulse {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.8;
    transform: scale(1.05);
  }
}

/* 为当前步骤图标添加脉冲效果 */
.step-current .step-icon {
  animation: pulse 2s ease-in-out infinite;
}
</style>

<style>
/* 全局样式确保按钮样式生效 */
.action-buttons {
  display: flex !important;
  justify-content: center !important;
  align-items: center !important;
  width: 100% !important;
  text-align: center !important;
}


.large-analysis-btn.el-button {
  width: 280px !important;
  height: 56px !important;
  font-size: 18px !important;
  font-weight: 700 !important;
  background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%) !important;
  border: none !important;
  border-radius: 16px !important;
  transition: all 0.3s ease !important;
  box-shadow: 0 4px 15px rgba(59, 130, 246, 0.2) !important;
  min-width: 280px !important;
  max-width: 280px !important;
}

.large-analysis-btn.el-button:hover {
  transform: translateY(-3px) !important;
  box-shadow: 0 12px 30px rgba(59, 130, 246, 0.4) !important;
  background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%) !important;
}

.large-analysis-btn.el-button:disabled {
  opacity: 0.6 !important;
  transform: none !important;
  box-shadow: 0 4px 15px rgba(59, 130, 246, 0.1) !important;
}

.large-analysis-btn.el-button .el-icon {
  margin-right: 8px !important;
  font-size: 20px !important;
}

.large-analysis-btn.el-button span {
  font-size: 18px !important;
  font-weight: 700 !important;
}

/* 进度显示样式 */
.progress-section {
  margin-top: 24px;
}

.progress-card .progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.progress-card .progress-header h4 {
  margin: 0;
  color: #1f2937;
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
}

/* 旋转动画 */
.rotating-icon {
  animation: rotate 2s linear infinite;
}

@keyframes rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

/* 总体进度信息 */
.overall-progress-info {
  margin-bottom: 24px;
}

.progress-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 16px;
  margin-bottom: 20px;
}

.stat-item {
  text-align: center;
  padding: 12px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
  border: 1px solid var(--el-border-color);
}

.stat-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 4px;
  font-weight: 500;
}

.stat-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

/* 进度条区域 */
.progress-bar-section {
  margin-bottom: 24px;
}

.main-progress-bar {
  :deep(.el-progress-bar__outer) {
    background-color: var(--el-fill-color);
    border-radius: 8px;
  }

  :deep(.el-progress-bar__inner) {
    background: linear-gradient(90deg, #3b82f6 0%, #1d4ed8 100%);
    border-radius: 8px;
    transition: width 0.6s ease;
  }

  :deep(.el-progress__text) {
    font-weight: 600;
    color: var(--el-text-color-primary);
  }
}

/* 当前任务信息 */
.current-task-info {
  background: var(--el-fill-color-light);
  border: 1px solid #3b82f6;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 24px;
}

.task-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #1e40af;
  margin-bottom: 8px;
}

.task-icon {
  color: #3b82f6;
}

.task-description {
  font-size: 14px;
  color: #1e40af;
  line-height: 1.5;
}

/* 分析步骤 */
.analysis-steps {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color);
  border-radius: 12px;
  padding: 20px;
}

.steps-title {
  margin: 0 0 16px 0;
  color: #1e293b;
  font-size: 16px;
  font-weight: 600;
}

.steps-container {
  max-height: 300px;
  overflow-y: auto;
}

/* 结果显示样式 */
.results-section {
  margin-top: 24px;
}

.results-card .results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.results-card .results-header h3 {
  margin: 0;
  color: #1f2937;
}

.results-card .result-meta {
  display: flex;
  gap: 8px;
}

.overview-section {
  margin-bottom: 32px;
}

.overview-section h4 {
  color: #1f2937;
  margin-bottom: 16px;
}

.overview-card {
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  padding: 28px 32px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
}

.overview-summary {
  color: #1f2937;
}

.overview-summary :deep(.markdown-content > *:first-child) {
  margin-top: 0;
}

.overview-summary :deep(.markdown-content > *:last-child) {
  margin-bottom: 0;
}

/* 风险提示样式 */
.risk-disclaimer {
  margin-bottom: 24px;
  animation: fadeInDown 0.5s ease-out;
}

.title-section .risk-disclaimer {
  margin-bottom: 12px;
  margin-top: 0;
}

.risk-disclaimer :deep(.el-alert) {
  background: linear-gradient(135deg, #fff3cd 0%, #ffe69c 100%);
  border: 2px solid #ffc107;
  border-radius: 12px;
  padding: 16px 20px;
  box-shadow: 0 4px 12px rgba(255, 193, 7, 0.2);
}

.risk-disclaimer :deep(.el-alert__icon) {
  font-size: 24px;
  color: #ff6b00;
}

.disclaimer-content {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 15px;
  line-height: 1.6;
}

.disclaimer-icon {
  font-size: 24px;
  color: #ff6b00;
  flex-shrink: 0;
  animation: pulse 2s ease-in-out infinite;
}

.disclaimer-text {
  color: #856404;
  flex: 1;
}

.disclaimer-text strong {
  color: #d63031;
  font-size: 16px;
  font-weight: 700;
}

@keyframes pulse {
  0%, 100% {
    transform: scale(1);
    opacity: 1;
  }
  50% {
    transform: scale(1.1);
    opacity: 0.8;
  }
}

@keyframes fadeInDown {
  from {
    opacity: 0;
    transform: translateY(-20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.decision-section {
  margin-bottom: 32px;
}

.decision-section h4 {
  color: #1f2937;
  margin-bottom: 16px;
}

.decision-card {
  background: var(--el-fill-color-light);
  border: 1px solid var(--el-border-color);
  border-radius: 12px;
  padding: 20px;
}

.decision-main {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

.decision-action {
  display: flex;
  align-items: center;
  gap: 12px;
}

.decision-action .label {
  font-weight: 600;
  color: #374151;
}

.decision-metrics {
  display: flex;
  gap: 24px;
}

.metric-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.metric-item .label {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 4px;
}

.metric-item .value {
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
}

.decision-reasoning h5 {
  margin: 0 0 8px 0;
  color: #374151;
  font-size: 14px;
}

.decision-reasoning p {
  margin: 0;
  color: #6b7280;
  line-height: 1.6;
}

.reports-section {
  margin-bottom: 32px;
}

.reports-section h4 {
  color: #1f2937;
  margin-bottom: 16px;
}

.report-content {
  line-height: 1.6;
  color: #374151;
}

.report-content h1,
.report-content h2,
.report-content h3 {
  color: #1f2937;
  margin: 16px 0 8px 0;
}

.report-content strong {
  color: #1f2937;
}

.result-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  padding-top: 24px;
  border-top: 1px solid #e5e7eb;
}

/* 分析报告标签页样式 */
.analysis-tabs-container {
  margin-top: 16px;
}

.analysis-tabs {
  /* 标签页头部样式 */
  :deep(.el-tabs__header) {
    margin: 0 0 20px 0;
    background: var(--el-fill-color-light);
    padding: 12px;
    border-radius: 15px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    border: 1px solid var(--el-border-color);
  }

  /* 标签页导航 */
  :deep(.el-tabs__nav-wrap) {
    &::after {
      display: none; /* 隐藏默认的底部边框 */
    }
  }

  /* 单个标签页样式 */
  :deep(.el-tabs__item) {
    height: 55px !important;
    line-height: 55px !important;
    padding: 0 20px !important;
    margin-right: 8px !important;
    background: var(--el-bg-color) !important;
    border: 2px solid var(--el-border-color) !important;
    border-radius: 12px !important;
    color: var(--el-text-color-regular) !important;
    font-weight: 600 !important;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1) !important;
    position: relative !important;
    overflow: hidden !important;
    border-bottom: 2px solid var(--el-border-color) !important; /* 确保底部边框存在 */

    &:hover {
      background: var(--el-fill-color-light) !important;
      border-color: #2196f3 !important;
      transform: translateY(-2px) scale(1.02) !important;
      box-shadow: 0 4px 15px rgba(33,150,243,0.3) !important;
      color: #1976d2 !important;
    }

    &.is-active {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
      color: white !important;
      border-color: #667eea !important;
      box-shadow: 0 6px 20px rgba(102,126,234,0.4) !important;
      transform: translateY(-3px) scale(1.05) !important;

      &::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: linear-gradient(135deg, rgba(255,255,255,0.2) 0%, rgba(255,255,255,0.1) 100%);
        border-radius: 10px;
        pointer-events: none;
      }
    }
  }

  /* 标签页内容区域 */
  :deep(.el-tabs__content) {
    padding: 0;
  }

  :deep(.el-tab-pane) {
    padding: 25px;
    background: var(--el-bg-color);
    border-radius: 15px;
    border: 1px solid var(--el-border-color);
    box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    margin-top: 10px;
  }
}

/* 报告头部样式 */
.report-header {
  margin-bottom: 25px;
  padding: 20px;
  background: var(--el-fill-color-light);
  border-radius: 15px;
  border-left: 5px solid #667eea;
  box-shadow: 0 2px 10px rgba(0,0,0,0.1);

  .report-title {
    display: flex;
    align-items: center;
    margin-bottom: 8px;

    .report-icon {
      font-size: 24px;
      margin-right: 12px;
    }

    .report-name {
      font-size: 20px;
      font-weight: 700;
      color: #495057;
    }
  }

  .report-description {
    color: #6c757d;
    font-size: 16px;
    line-height: 1.5;
    margin-left: 36px; /* 对齐图标后的文字 */
  }
}

/* 报告内容包装器 */
.report-content-wrapper {
  background: var(--el-bg-color);
  padding: 25px;
  border-radius: 12px;
  border: 1px solid var(--el-border-color);
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

/* 报告内容样式增强 */
.report-content,
.markdown-content {
  line-height: 1.7;
  color: #495057;
  font-size: 16px;

  /* 标题样式 */
  h1, h2, h3, h4, h5, h6 {
    color: #1f2937 !important;
    margin: 20px 0 12px 0 !important;
    font-weight: 600 !important;
  }

  h1 { font-size: 30px !important; line-height: 1.3 !important; }
  h2 { font-size: 22px !important; line-height: 1.4 !important; }
  h3 { font-size: 18px !important; line-height: 1.5 !important; }
  h4 { font-size: 16px !important; }

  /* 段落样式 */
  p {
    margin: 12px 0 !important;
    line-height: 1.7 !important;
  }

  /* 强调文本 */
  strong, b {
    color: #1f2937 !important;
    font-weight: 600 !important;
  }

  /* 斜体文本 */
  em, i {
    color: #4b5563 !important;
    font-style: italic !important;
  }

  /* 列表样式 */
  ul, ol {
    margin: 12px 0 !important;
    padding-left: 24px !important;

    li {
      margin: 6px 0 !important;
      line-height: 1.6 !important;
    }
  }

  /* 代码样式 */
  code {
    background: var(--el-fill-color-light) !important;
    padding: 2px 6px !important;
    border-radius: 4px !important;
    font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace !important;
    font-size: 14px !important;
    color: #e11d48 !important;
  }

  /* 引用样式 */
  blockquote {
    border-left: 4px solid #3b82f6 !important;
    padding-left: 16px !important;
    margin: 16px 0 !important;
    background: var(--el-fill-color-light) !important;
    padding: 12px 16px !important;
    border-radius: 0 8px 8px 0 !important;
    font-style: italic !important;
    color: var(--el-text-color-regular) !important;
  }
}

/* 风险提示样式 */
.risk-disclaimer {
  margin-top: 24px;
  border-radius: 8px;

  :deep(.el-alert__content) {
    width: 100%;
  }

  :deep(.el-alert__title) {
    font-size: 14px;
    line-height: 1.6;
    color: #e6a23c;
  }
}

.growth-panel-section {
  margin-bottom: 24px;
}
</style>
