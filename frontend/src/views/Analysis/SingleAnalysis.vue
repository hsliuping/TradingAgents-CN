<template>
  <div class="single-analysis">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">
            <el-icon class="title-icon"><Document /></el-icon>
            单股研究
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
                  <strong>⚠️ 重要提示：</strong>本次研究仅用于学习、研究和公开信息整理，不提供个股交易指导。
                </span>
              </template>
            </el-alert>
          </div>
          
          <p class="page-description">
            AI驱动的单股研究工作台，聚合多维证据、风险与后续观察线索
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
              <!-- 股票信息 -->
              <div class="form-section">
                <h4 class="section-title">📊 股票信息</h4>
                <el-row :gutter="16">
                  <el-col :span="12">
                    <el-form-item label="股票代码" required>
                      <el-input
                        v-model="analysisForm.stockCode"
                        placeholder="如：000001、AAPL、700、1810"
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
                        <el-option label="🇺🇸 美股市场" value="美股">
                          <span>🇺🇸 美股市场</span>
                          <span style="color: #909399; font-size: 12px; margin-left: 8px;">（1-5个字母）</span>
                        </el-option>
                        <el-option label="🇭🇰 港股市场" value="港股">
                          <span>🇭🇰 港股市场</span>
                          <span style="color: #909399; font-size: 12px; margin-left: 8px;">（1-5位数字）</span>
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
                      <el-tooltip content="用于研究管理者综合决策、风险管理者最终评估" placement="top">
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

              <!-- 分析引擎选择 - 已隐藏，默认使用 v2.0 引擎 -->
              <!-- 旧版引擎已移除，统一使用 v2.0 工作流引擎 -->

              <!-- 分析选项 -->
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
                            <li><strong>平台性质：</strong>本平台为 AI 辅助投研技术学习平台，专注于 AI 技术在股票研究领域的应用验证和技术学习。</li>
                            <li><strong>研究目的：</strong>所有研究结论仅用于学习、研究和公开信息整理，不提供个股交易指导或投资依据。</li>
                            <li><strong>非投资建议：</strong>所有研究结果、评分、研究结论仅为技术验证参考，不构成任何买卖建议或投资决策依据。</li>
                            <li><strong>数据局限性：</strong>研究基于历史数据和公开信息，可能存在延迟、不完整或不准确的情况，无法预测未来市场走势。</li>
                            <li><strong>投资风险：</strong>股票投资存在市场风险、流动性风险、政策风险等多种风险，可能导致本金损失。</li>
                            <li><strong>独立决策：</strong>投资者应基于自身风险承受能力、投资目标和财务状况独立做出投资决策。</li>
                            <li><strong>责任声明：</strong>使用本平台产生的任何投资决策及其后果由使用者自行承担，本平台不承担任何责任。</li>
                          </ul>
                        </div>
                      </div>
                    </template>
                  </el-alert>
                </div>

                <!-- 分析概览 -->
                <div v-if="analysisResults" class="overview-section">
                  <h4>📊 分析概览</h4>
                  <div class="overview-card">
  
                    <div v-if="overviewBriefContent" class="overview-summary">
                      <h5>研究简报:</h5>
                      <div class="markdown-content" v-html="renderMarkdown(overviewBriefContent)"></div>
                    </div>

                    <!-- 🔥 移除重复的"分析依据"，因为上面决策卡片中已经有完整的 decision.reasoning -->
                    <!-- recommendation 字段通常包含"分析观点：xxx；分析依据：xxx"，与 decision.reasoning 重复 -->
                    <!-- 如果需要显示 recommendation，可以只显示"分析观点"部分，但为了简洁，这里直接移除 -->
                  </div>
                </div>

                <!-- 详细研究报告 -->
                <div v-if="analysisResults.state || analysisResults.reports" class="reports-section">
                  <h4>📋 详细研究报告</h4>

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
                        v-for="report in getAnalysisReports(analysisResults)"
                        :key="report.key"
                        :name="report.key"
                        :label="report.title"
                        class="report-tab-pane"
                      >
                        <!-- 标签页内容头部 -->
                        <div class="report-header">
                          <div class="report-title">
                            <span class="report-icon">{{ report.icon }}</span>
                            <span class="report-name">{{ report.name }}</span>
                          </div>
                          <div class="report-description">{{ report.description }}</div>
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
                                ⚠️ 重要提示：本报告由 AI 基于有限资料与公开信息整理生成，仅供研究参考，不构成投资建议。
                              </span>
                            </template>
                          </el-alert>
                          
                          <div
                            class="report-content"
                            v-html="renderMarkdown(report.content)"
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
                    <span style="font-weight: bold;">报告基于真实市场数据与公开信息生成，仅供研究参考，不构成任何投资建议。</span>
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
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
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
  PieChart,
  Grid,
  Plus,
  DocumentChecked,
} from '@element-plus/icons-vue'
import { analysisApi, type SingleAnalysisRequest } from '@/api/analysis'
import { workflowApi, type WorkflowDefinition } from '@/api/workflow'
import { stocksApi } from '@/api/stocks'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import { configApi } from '@/api/config'
import DeepModelSelector from '@/components/DeepModelSelector.vue'
import { ANALYSTS, convertAnalystNamesToIds } from '@/constants/analysts'
import { marked } from 'marked'
import { recommendModels, validateModels, type ModelRecommendationResponse } from '@/api/modelCapabilities'
import { validateStockCode, getStockCodeFormatHelp, getStockCodeExamples } from '@/utils/stockValidator'
import { normalizeMarketForAnalysis, getMarketByStockCode } from '@/utils/market'

// 配置marked选项
marked.setOptions({
  breaks: true,        // 支持换行符转换为<br>
  gfm: true           // 启用GitHub风格的Markdown
})

// 市场类型定义
type MarketType = 'A股' | '美股' | '港股'

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
}

// 使用store
const appStore = useAppStore()
const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()

const submitting = ref(false)
const validatingData = ref(false)
const showValidationDialog = ref(false)
const validationResult = ref<any>(null)

// 分析进度和结果相关状态
const currentTaskId = ref('')
const analysisStatus = ref('idle') // 'idle', 'running', 'completed', 'failed'
const showResults = ref(false)
const analysisResults = ref<any>(null)
const activeReportTab = ref('') // 当前激活的报告标签页
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
const completedResultRetryCount = ref(0)

// 分析步骤定义（动态生成）
const analysisSteps = ref<any[]>([])

const progressTextReplacements: Array<[string, string]> = [
  ['bull_researcher_v2', '乐观情景研究员'],
  ['bear_researcher_v2', '审慎情景研究员'],
  ['risky_analyst_v2', '高弹性情景分析师'],
  ['safe_analyst_v2', '防御情景分析师'],
  ['neutral_analyst_v2', '基准情景分析师'],
  ['bull_researcher', '乐观情景研究员'],
  ['bear_researcher', '审慎情景研究员'],
  ['risky_analyst', '高弹性情景分析师'],
  ['safe_analyst', '防御情景分析师'],
  ['neutral_analyst', '基准情景分析师'],
  ['看多研究员', '乐观情景研究员'],
  ['看空研究员', '审慎情景研究员'],
  ['激进分析师', '高弹性情景分析师'],
  ['保守分析师', '防御情景分析师'],
  ['中性分析师', '基准情景分析师'],
  ['构建看多观点', '构建乐观情景观点'],
  ['构建看空观点', '构建审慎情景观点'],
  ['激进风险观点', '高弹性情景观点'],
  ['保守风险观点', '防御情景观点'],
  ['中性风险观点', '基准情景观点']
]

const normalizeProgressText = (text: unknown, fallback = '') => {
  if (typeof text !== 'string' || !text.trim()) {
    return fallback
  }

  return progressTextReplacements.reduce((normalized, [from, to]) => {
    return normalized.split(from).join(to)
  }, text)
}

// 从后端步骤数据生成前端步骤
const generateStepsFromBackend = (backendSteps: any[]) => {
  if (!backendSteps || !Array.isArray(backendSteps)) {
    return []
  }

  return backendSteps.map((step: any, index: number) => ({
    key: `step_${index}`,
    title: normalizeProgressText(step.name, `步骤 ${index + 1}`),
    description: normalizeProgressText(step.description, '处理中...'),
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
const workflows = ref<WorkflowDefinition[]>([])
const workflowsSorted = computed(() => {
  const arr = [...workflows.value]
  const score = (t: WorkflowDefinition) => {
    const v = t.version
    let major = 0
    if (typeof v === 'string') {
      const m = parseInt(v.split('.')[0] || '0', 10)
      if (!Number.isNaN(m)) major = m
    } else if (typeof v === 'number') {
      major = v
    }
    const tags = Array.isArray(t.tags) ? t.tags : []
    const isV2Tag = tags.some(tag => String(tag).toLowerCase().includes('v2'))
    return (isV2Tag ? 1 : 0) * 100 + major
  }
  arr.sort((a, b) => score(b) - score(a))
  return arr
})
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
  engine: 'v2'  // 固定使用 v2.0 引擎
})

// 股票代码验证相关
const stockCodeError = ref<string>('')
const stockCodeHelp = ref<string>('')

// 深度选项（5个级别，基于实际测试数据更新）
const depthOptions = [
  { icon: '⚡', name: '1级 - 快速分析', description: '基础数据概览，快速了解', time: '2-5分钟' },
  { icon: '📈', name: '2级 - 基础分析', description: '常规维度分析', time: '3-6分钟' },
  { icon: '🎯', name: '3级 - 标准分析', description: '技术+基本面，推荐', time: '4-8分钟' },
  { icon: '🔍', name: '4级 - 深度分析', description: '多轮辩论，深度研究', time: '6-11分钟' },
  { icon: '🏆', name: '5级 - 全面研究', description: '最全面的研究报告', time: '8-16分钟' }
]

// 禁用日期
const disabledDate = (time: Date) => {
  return time.getTime() > Date.now()
}

// 股票代码输入时的处理
const onStockCodeInput = () => {
  // 清除错误信息
  stockCodeError.value = ''
  // 显示格式提示
  stockCodeHelp.value = getStockCodeFormatHelp(analysisForm.market)
}

// 🔥 根据市场类型过滤可用的分析师（大盘和板块分析师仅支持A股）
const availableAnalysts = computed(() => {
  const isAStock = analysisForm.market === 'A股'
  return ANALYSTS.map(analyst => {
    // 大盘分析师和板块分析师仅在A股市场可用
    const isMacroAnalyst = analyst.id === 'index_analyst' || analyst.id === 'sector_analyst'
    return {
      ...analyst,
      disabled: !isAStock && isMacroAnalyst
    }
  })
})

// 市场类型变更时的处理
const onMarketChange = () => {
  // 重新验证股票代码
  if (analysisForm.stockCode.trim()) {
    validateStockCodeInput()
  } else {
    // 显示新市场的格式提示
    stockCodeHelp.value = getStockCodeFormatHelp(analysisForm.market)
  }
  
  // 🔥 如果切换到港股或美股，自动移除大盘和板块分析师
  if (analysisForm.market !== 'A股') {
    const macroAnalysts = ['大盘分析师', '板块分析师']
    analysisForm.selectedAnalysts = analysisForm.selectedAnalysts.filter(
      name => !macroAnalysts.includes(name)
    )
  }
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
  const validation = validateStockCode(code, analysisForm.market)

  if (!validation.valid) {
    stockCodeError.value = validation.message || '股票代码格式不正确'
    stockCodeHelp.value = ''
  } else {
    stockCodeError.value = ''
    stockCodeHelp.value = `✓ ${validation.market}代码格式正确`

    // 自动更新市场类型（如果识别出的市场与当前选择不同）
    if (validation.market && validation.market !== analysisForm.market) {
      analysisForm.market = validation.market
      ElMessage.success(`已自动识别为${validation.market}`)
    }

    // 标准化代码
    if (validation.normalizedCode) {
      analysisForm.stockCode = validation.normalizedCode
    }
  }

  // 获取股票信息
  fetchStockInfo()
}

// 获取股票信息
const fetchStockInfo = () => {
  // TODO: 实现股票信息获取
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
  const validation = validateStockCode(stockCode, analysisForm.market)
  if (!validation.valid) {
    ElMessage.error(validation.message || '股票代码格式不正确')
    return
  }

  // 使用标准化后的代码
  const normalizedCode = validation.normalizedCode || stockCode.toUpperCase()

  // 确定市场类型（用于API调用）
  const marketTypeMap: Record<string, string> = {
    'A股': 'cn',
    '港股': 'hk',
    '美股': 'us'
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
        { label: '股票名称', value: basicInfo.name || '-' },
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

// 显示校验结果对话框
const showValidationResultDialog = (result: any) => {
  validationResult.value = result
  showValidationDialog.value = true
}

// 提交分析
const submitAnalysis = async () => {
  const stockCode = analysisForm.stockCode.trim()
  if (!stockCode) {
    ElMessage.warning('请输入股票代码')
    return
  }

  // 验证股票代码格式
  const validation = validateStockCode(stockCode, analysisForm.market)
  if (!validation.valid) {
    ElMessage.error(validation.message || '股票代码格式不正确')
    stockCodeError.value = validation.message || '股票代码格式不正确'
    return
  }

  // 使用标准化后的代码
  analysisForm.symbol = validation.normalizedCode || stockCode.toUpperCase()

  if (analysisForm.selectedAnalysts.length === 0) {
    ElMessage.warning('请至少选择一个分析师')
    return
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
        engine: 'v2'  // 🔥 固定使用 v2.0 引擎（旧版引擎已隐藏）
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
        if (status.status === 'running') {
          analysisStatus.value = 'running'
          console.log('✅ 设置 analysisStatus 为 running')
          updateProgressInfo(status)
        }
      } catch (error) {
        console.error('立即查询状态失败:', error)
      }
    }, 1000) // 1秒后查询

  } catch (error: any) {
    ElMessage.error(error.message || '提交研究失败')
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
        // 研究完成后继续短重试拉取结果，避免 completed 先于完整结果可读的短窗口
        console.log('🎉 研究完成，正在获取完整结果...')

        analysisStatus.value = 'completed'
        progressInfo.value.progress = 100
        progressInfo.value.currentStep = '研究完成'
        progressInfo.value.message = '研究已完成，正在同步结果...'

        let resolvedResult: any = null
        try {
          resolvedResult = await fetchCompletedAnalysisResult(currentTaskId.value, status.result_data)
        } catch (error) {
          console.error('❌ 获取完整研究结果异常:', error)
          resolvedResult = pickBestAnalysisResult(null, status.result_data)
        }

        if (hasMeaningfulAnalysisResult(resolvedResult)) {
          analysisResults.value = resolvedResult
          showResults.value = true
          progressInfo.value.message = '研究已完成！'
          completedResultRetryCount.value = 0

          if (pollingTimer.value) {
            clearInterval(pollingTimer.value)
            pollingTimer.value = null
          }

          ElMessage.success('研究完成！')
        } else {
          completedResultRetryCount.value += 1
          analysisResults.value = null
          showResults.value = false

          console.warn('⚠️ 研究结果尚未完成同步，等待下一次轮询:', {
            taskId: currentTaskId.value,
            retryCount: completedResultRetryCount.value
          })

          if (completedResultRetryCount.value >= maxCompletedResultPollRetries) {
            progressInfo.value.message = '研究已完成，但结果同步较慢，请稍后刷新页面查看'
            if (pollingTimer.value) {
              clearInterval(pollingTimer.value)
              pollingTimer.value = null
            }
            ElMessage.warning('研究已完成，但结果同步较慢，请稍后刷新页面查看')
          }
        }

      } else if (status.status === 'failed') {
        // 研究失败
        analysisStatus.value = 'failed'
        progressInfo.value.currentStep = '研究失败'

        // 格式化错误消息（保留换行符）
        const errorMessage = status.error_message || '研究过程中发生错误'
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

      } else if (status.status === 'running') {
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
    progressInfo.value.currentStep = normalizeProgressText(status.current_step_name)
  }

  if (status.current_step_description) {
    console.log('📝 更新步骤描述:', status.current_step_description)
    progressInfo.value.currentStepDescription = normalizeProgressText(status.current_step_description)
  }

  if (status.message) {
    console.log('💬 更新消息:', status.message)
    progressInfo.value.message = normalizeProgressText(status.message)
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
    analysisSteps.value = generateStepsFromBackend(status.steps)
    console.log('📋 从后端同步步骤列表:', analysisSteps.value.length, '个步骤')
  }

  console.log('🔄 更新后进度信息:', progressInfo.value)

  // 更新分析步骤状态
  updateAnalysisSteps(status)

  // 前端不进行估算，只展示后端返回的数据
  progressInfo.value.message = normalizeProgressText(status.message, '分析正在进行中...')
}

// 重新开始分析
const restartAnalysis = () => {
  // 清除任务缓存
  clearTaskCache()

  analysisStatus.value = 'idle'
  showResults.value = false
  analysisResults.value = null
  currentTaskId.value = ''
  completedResultRetryCount.value = 0
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
  completedResultRetryCount.value = 0
  
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


// 获取研究报告
const getAnalysisReports = (data: any) => {
  console.log('📊 getAnalysisReports 输入数据:', data)
  const reportsData = extractReportsSource(data)
  console.log('📊 解析后的 reports 键:', Object.keys(reportsData || {}))
  const reports: Array<{ key: string; title: string; name: string; icon: string; description: string; content: string }> = []

  const availableModules = Object.keys(reportsData).filter(
    key => key !== 'trader_investment_plan' && !!getModuleContent(reportsData[key])
  )
  const orderedModules = analysisModuleOrder.filter(key => availableModules.includes(key))
  const remainingModules = availableModules.filter(key => !analysisModuleOrder.includes(key))

  for (const moduleKey of [...orderedModules, ...remainingModules]) {
    const content = getModuleContent(reportsData[moduleKey])
    if (!content) {
      continue
    }

    const meta = getAnalysisReportMeta(moduleKey)
    reports.push({
      key: moduleKey,
      title: `${meta.icon} ${meta.title}`,
      name: meta.title,
      icon: meta.icon,
      description: meta.description,
      content
    })
  }

  console.log(`📊 总共找到 ${reports.length} 个报告`)

  // 设置第一个报告为默认激活标签页
  if (reports.length > 0 && (!activeReportTab.value || !reports.some(report => report.key === activeReportTab.value))) {
    activeReportTab.value = reports[0].key
  } else if (reports.length === 0) {
    activeReportTab.value = ''
  }

  return reports
}

const analysisModuleOrder = [
  'index_report',
  'sector_report',
  'market_report',
  'fundamentals_report',
  'sentiment_report',
  'news_report',
  'bull_researcher',
  'bull_report',
  'bear_researcher',
  'bear_report',
  'research_team_decision',
  'investment_plan',
  'trader_investment_plan',
  'risky_analyst',
  'risky_opinion',
  'safe_analyst',
  'safe_opinion',
  'neutral_analyst',
  'neutral_opinion',
  'risk_management_decision',
  'risk_assessment',
  'final_trade_decision',
  'investment_debate_state',
  'risk_debate_state',
  'detailed_analysis'
]

const analysisModuleMeta: Record<string, { title: string; icon: string; description: string }> = {
  index_report: { title: '大盘环境研究', icon: '📊', description: '市场环境、流动性条件与系统性风险观察' },
  sector_report: { title: '行业板块研究', icon: '🏭', description: '行业景气度、结构变化与同业对比' },
  market_report: { title: '市场技术研究', icon: '📈', description: '趋势结构、波动状态与量价配合观察' },
  fundamentals_report: { title: '基本面研究', icon: '💰', description: '财务质量、估值背景与经营弹性分析' },
  sentiment_report: { title: '情绪研究', icon: '💭', description: '情绪方向、热度变化与噪音识别' },
  news_report: { title: '新闻研究', icon: '📰', description: '公告、新闻事件与催化风险脉络' },
  bull_researcher: { title: '乐观情景研究员', icon: '🌤️', description: '乐观情景下的主要论点与论证' },
  bull_report: { title: '乐观情景论证', icon: '🌤️', description: '乐观情景研究的展开论证内容' },
  bear_researcher: { title: '审慎情景研究员', icon: '🌧️', description: '审慎情景下的主要论点与论证' },
  bear_report: { title: '审慎情景论证', icon: '🌧️', description: '审慎情景研究的展开论证内容' },
  research_team_decision: { title: '研究结论汇总', icon: '🔬', description: '研究团队综合多方观点后的汇总结论' },
  investment_plan: { title: '研究经理简报', icon: '📋', description: '研究经理对多维分析的整合摘要' },
  trader_investment_plan: { title: '研究简报', icon: '🧩', description: '面向用户阅读的精简研究简报' },
  risky_analyst: { title: '高弹性情景分析师', icon: '⚡', description: '高弹性情景下的主要风险与机会评估' },
  risky_opinion: { title: '高弹性情景审阅', icon: '⚡', description: '高弹性情景的补充审阅意见' },
  safe_analyst: { title: '防御情景分析师', icon: '🛡️', description: '防御情景下的主要风险与稳健性评估' },
  safe_opinion: { title: '防御情景审阅', icon: '🛡️', description: '防御情景的补充审阅意见' },
  neutral_analyst: { title: '基准情景分析师', icon: '⚖️', description: '基准情景下的平衡分析与条件判断' },
  neutral_opinion: { title: '基准情景审阅', icon: '⚖️', description: '基准情景的补充审阅意见' },
  risk_management_decision: { title: '风险治理结论', icon: '⚠️', description: '整体风险、约束条件与后续观察要求' },
  risk_assessment: { title: '风险评估摘要', icon: '⚠️', description: '整体风险暴露、约束条件与关注点' },
  final_trade_decision: { title: '综合研究结论', icon: '📝', description: '融合研究与风险结论后的综合结论' },
  investment_debate_state: { title: '研究辩论状态', icon: '🔬', description: '研究辩论过程中的关键状态信息' },
  risk_debate_state: { title: '风险辩论状态', icon: '🛡️', description: '风险辩论过程中的关键状态信息' },
  detailed_analysis: { title: '详细分析', icon: '📄', description: '补充的详细过程或扩展分析内容' }
}

const getAnalysisReportMeta = (moduleKey: string) => {
  const fallbackTitle = moduleKey.replace(/_/g, ' ')
  return analysisModuleMeta[moduleKey] || {
    title: fallbackTitle,
    icon: '📄',
    description: '详细研究报告'
  }
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

const normalizeDisplayedResearchText = (content: string) => {
  if (!content) return ''

  const replacements: Array<[RegExp, string]> = [
    [/交易分析计划/g, '研究整合意见'],
    [/交易员计划/g, '研究整合意见'],
    [/初步投资计划/g, '研究团队结论'],
    [/投资计划/g, '研究结论'],
    [/投资建议/g, '研究结论'],
    [/操作建议/g, '研究观点'],
    [/大盘指数分析/g, '大盘环境研究'],
    [/行业板块分析/g, '行业板块研究'],
    [/市场情绪分析/g, '情绪研究'],
    [/新闻事件分析/g, '新闻研究'],
    [/风险治理摘要/g, '风险治理结论'],
    [/综合研究简报/g, '综合研究结论'],
    [/风险管理决策/g, '风险治理结论'],
    [/最终分析结果/g, '最终研究结论']
  ]

  return replacements.reduce((text, [pattern, replacement]) => text.replace(pattern, replacement), content)
}

const extractStructuredText = (value: any): string | null => {
  if (!value) return null

  if (typeof value === 'object') {
    for (const key of ['content', 'markdown', 'text', 'message', 'report', 'judge_decision']) {
      const item = value[key]
      if (typeof item === 'string' && item.trim()) {
        return item
      }
    }
    return null
  }

  if (typeof value !== 'string') {
    return null
  }

  let candidate = value.trim()
  for (let i = 0; i < 3; i += 1) {
    if (!candidate) break

    try {
      const parsed = JSON.parse(candidate)
      if (typeof parsed === 'string') {
        candidate = parsed.trim()
        continue
      }

      const extracted = extractStructuredText(parsed)
      if (extracted) {
        candidate = extracted.trim()
        continue
      }
    } catch {
      // 不是 JSON，继续使用原文本
    }

    break
  }

  if (
    ((candidate.startsWith('"') && candidate.endsWith('"')) ||
      (candidate.startsWith("'") && candidate.endsWith("'"))) &&
    candidate.length >= 2
  ) {
    candidate = candidate.slice(1, -1).trim()
  }

  return candidate || null
}

const prepareMarkdownContent = (content: string) => {
  if (!content) return ''

  const rawContent = extractStructuredText(content) || content

  const normalizedText = normalizeDisplayedResearchText(rawContent)
    .replace(/\u001b\[[0-9;]*m/g, '')
    .replace(/\r\n/g, '\n')
    .replace(/\\r\\n/g, '\n')
    .replace(/\\n/g, '\n')
    .replace(/\\t/g, '\t')
    .replace(/\\"/g, '"')
    .replace(/^\uFEFF/, '')

  const lines = normalizedText.split('\n')
  const nonEmptyLines = lines.filter(line => line.trim())

  if (nonEmptyLines.length === 0) {
    return normalizedText.trim()
  }

  const commonIndent = Math.min(
    ...nonEmptyLines.map(line => {
      const match = line.match(/^[\t ]*/)
      return match ? match[0].length : 0
    })
  )

  const dedentedLines = commonIndent > 0
    ? lines.map(line => line.slice(Math.min(commonIndent, line.length)))
    : lines

  let preparedText = dedentedLines.join('\n').trim()

  if (!preparedText) {
    return ''
  }

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
  if (!moduleData) return null

  const extractedText = extractStructuredText(moduleData)
  if (extractedText) {
    return normalizeDisplayedResearchText(extractedText)
  }

  if (typeof moduleData === 'string') {
    return normalizeDisplayedResearchText(moduleData)
  }

  if (typeof moduleData === 'object') {
    if (moduleData.content && typeof moduleData.content === 'string') {
      return normalizeDisplayedResearchText(moduleData.content)
    }
    if (moduleData.markdown && typeof moduleData.markdown === 'string') {
      return normalizeDisplayedResearchText(moduleData.markdown)
    }
    if (moduleData.judge_decision && typeof moduleData.judge_decision === 'string') {
      return normalizeDisplayedResearchText(moduleData.judge_decision)
    }
  }

  return null
}

const extractReportsSource = (data: any): Record<string, any> => {
  const directReports = data?.reports
  if (directReports && typeof directReports === 'object' && Object.keys(directReports).length > 0) {
    return directReports
  }

  const stateReports = data?.state?.reports
  if (stateReports && typeof stateReports === 'object' && Object.keys(stateReports).length > 0) {
    return stateReports
  }

  const state = data?.state && typeof data.state === 'object' ? data.state : null
  const root = data && typeof data === 'object' ? data : null
  const extracted: Record<string, any> = {}

  for (const key of analysisModuleOrder) {
    if (state && state[key] != null) {
      extracted[key] = state[key]
      continue
    }
    if (root && root[key] != null) {
      extracted[key] = root[key]
    }
  }

  return extracted
}

const completedResultRetryDelays = [0, 1200, 2500, 4000]
const maxCompletedResultPollRetries = 3

const waitForResultSync = (delayMs: number) => {
  return new Promise<void>((resolve) => {
    window.setTimeout(resolve, delayMs)
  })
}

const hasMeaningfulText = (value: any) => {
  const text = extractStructuredText(value)
  return typeof text === 'string' && text.trim().length > 0
}

const hasMeaningfulAnalysisResult = (result: any) => {
  if (!result || typeof result !== 'object') {
    return false
  }

  const reports = extractReportsSource(result)
  if (Object.values(reports).some(report => !!getModuleContent(report)?.trim())) {
    return true
  }

  if (hasMeaningfulText(result.summary) || hasMeaningfulText(result.recommendation)) {
    return true
  }

  if (Array.isArray(result.key_points) && result.key_points.some(point => hasMeaningfulText(point))) {
    return true
  }

  const decision = result.decision
  if (decision && typeof decision === 'object') {
    for (const key of ['analysis_view', 'reasoning', 'judge_decision', 'action']) {
      if (hasMeaningfulText(decision[key])) {
        return true
      }
    }
  }

  return false
}

const pickBestAnalysisResult = (primaryResult: any, fallbackResult: any) => {
  if (hasMeaningfulAnalysisResult(primaryResult)) {
    return primaryResult
  }

  if (hasMeaningfulAnalysisResult(fallbackResult)) {
    return fallbackResult
  }

  return primaryResult ?? fallbackResult ?? null
}

const fetchCompletedAnalysisResult = async (taskId: string, fallbackResultData: any = null) => {
  let bestResult = hasMeaningfulAnalysisResult(fallbackResultData) ? fallbackResultData : null
  let lastError: unknown = null

  for (let attempt = 0; attempt < completedResultRetryDelays.length; attempt += 1) {
    const delayMs = completedResultRetryDelays[attempt]
    if (delayMs > 0) {
      await waitForResultSync(delayMs)
    }

    try {
      const response = await analysisApi.getTaskResult(taskId)
      const resultPayload = response?.data ?? null

      console.log('📦 研究结果同步尝试:', {
        taskId,
        attempt: attempt + 1,
        hasPayload: !!resultPayload,
        keys: Object.keys(resultPayload || {})
      })

      bestResult = pickBestAnalysisResult(resultPayload, bestResult)
      if (hasMeaningfulAnalysisResult(bestResult)) {
        return bestResult
      }
    } catch (error) {
      lastError = error
      console.warn('⚠️ 研究结果同步尝试失败:', {
        taskId,
        attempt: attempt + 1,
        error
      })
    }
  }

  if (bestResult) {
    return bestResult
  }

  if (lastError) {
    throw lastError
  }

  return fallbackResultData
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
      ElMessage.error('研究报告尚未生成，无法下载')
      return
    }

    // 显示加载提示
    const loadingMsg = ElMessage({
      message: `正在生成${getFormatName(format)}格式研究报告...`,
      type: 'info',
      duration: 0
    })

    const reportId = (analysisResults.value?.id as any) || currentTaskId.value
    const res = await fetch(`/api/reports/${reportId}/download?format=${format}`, {
      headers: {
        'Authorization': `Bearer ${authStore.token}`
      }
    })

    loadingMsg.close()

    if (!res.ok) {
      const errorText = await res.text()
      throw new Error(errorText || `HTTP ${res.status}`)
    }

    const blob = await res.blob()
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
    a.download = `${String(code)}_研究报告_${String(dateStr).slice(0, 10)}.${ext}`

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
          if (status.status === 'running') {
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
      progressInfo.value.progress = 100
      progressInfo.value.currentStep = '研究完成'
      progressInfo.value.message = '研究已完成，正在同步结果...'

      let restoredResult: any = null
      try {
        restoredResult = await fetchCompletedAnalysisResult(cached.taskId, status.result_data)
      } catch (error) {
        console.warn('⚠️ 恢复任务时同步研究结果失败，继续轮询等待:', error)
        restoredResult = pickBestAnalysisResult(null, status.result_data)
      }

      if (hasMeaningfulAnalysisResult(restoredResult)) {
        analysisResults.value = restoredResult
        showResults.value = true
        progressInfo.value.message = '研究已完成'
        completedResultRetryCount.value = 0
      } else {
        analysisResults.value = null
        showResults.value = false
        completedResultRetryCount.value = 0
        startPollingTaskStatus()
      }

      // 恢复分析参数
      if (cached.taskData.parameters) {
        Object.assign(analysisForm, cached.taskData.parameters)
      }

      console.log('✅ 任务已完成，显示结果')
      return true

    } else if (status.status === 'running') {
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
      progressInfo.value.currentStep = '研究失败'
      progressInfo.value.message = status.error_message || '研究过程中发生错误'

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
const isDeepAnalysisRole = (roles: string[] | undefined): boolean => {
  if (!roles || !Array.isArray(roles)) return false
  return roles.includes('deep_analysis') || roles.includes('both')
}

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
        5: '全面分析，形成系统研究结论'
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
      analysisForm.selectedAnalysts = [...userPrefs.default_analysts]
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
      console.log('🔍 自动识别市场类型:', analysisForm.stockCode, '->', detectedMarket)
    }
  }
  if (q?.market) {
    analysisForm.market = normalizeMarketForAnalysis(q.market) as MarketType
    // 🔥 如果从路由参数设置市场类型，也需要过滤分析师
    if (analysisForm.market !== 'A股') {
      const macroAnalysts = ['大盘分析师', '板块分析师']
      analysisForm.selectedAnalysts = analysisForm.selectedAnalysts.filter(
        name => !macroAnalysts.includes(name)
      )
    }
  }

  // 尝试恢复任务状态（仅当没有新股票代码时）
  if (!hasNewStock) {
    await restoreTaskFromCache()
  }

  // 🆕 初始检查模型适用性
  await checkModelSuitability()
  try {
    workflows.value = await workflowApi.getTemplates()
    const exists = workflows.value.some(w => w.id === selectedWorkflowId.value)
    if (!exists && workflows.value.length > 0) {
      selectedWorkflowId.value = workflowsSorted.value[0]?.id || workflows.value[0].id
    }
  } catch {}
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

/* 研究报告标签页样式 */
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
.report-content {
  line-height: 1.7;
  color: #495057;
  font-size: 16px;

  /* 标题样式 */
  h1, h2, h3, h4, h5, h6 {
    color: #1f2937 !important;
    margin: 20px 0 12px 0 !important;
    font-weight: 600 !important;
  }

  h1 { font-size: 24px !important; }
  h2 { font-size: 20px !important; }
  h3 { font-size: 18px !important; }
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
</style>
