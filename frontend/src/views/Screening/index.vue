<template>
  <div class="stock-screening">
    <!-- 页面标题 -->
    <div class="page-header">
      <h1 class="page-title">
        <el-icon><Search /></el-icon>
        股票筛选
      </h1>
      <p class="page-description">
        默认通过智能对话引导你完成选股；只有在需要精细手动配置时，再进入高级模式
      </p>
    </div>

    <!-- Tab 切换 -->
    <el-tabs v-model="activeTab" class="screening-tabs">
      <el-tab-pane label="智能筛选" name="intelligent">

        <div class="intelligent-screening">
          <div class="chat-layout">
            <aside class="history-panel" v-loading="aiHistoryLoading">
              <div class="history-header">
                <div>
                  <div class="history-title">筛选历史</div>
                  <div class="history-subtitle">按会话查看之前的智能筛选记录</div>
                </div>
                <el-button type="primary" size="small" @click="startNewAiConversation">新建</el-button>
              </div>
              <div v-if="aiConversationList.length === 0" class="history-empty">
                暂无历史会话
              </div>
              <div v-else class="history-list">
                <div
                  v-for="item in aiConversationList"
                  :key="item.conversation_id"
                  :class="['history-item', { active: item.conversation_id === aiCurrentConversationId }]"
                  @click="openAiConversation(item.conversation_id)"
                  @keydown.enter="openAiConversation(item.conversation_id)"
                  @keydown.space.prevent="openAiConversation(item.conversation_id)"
                  role="button"
                  tabindex="0"
                >
                  <div class="history-item-header">
                    <div class="history-item-title">{{ item.title || '未命名筛选' }}</div>
                    <div class="history-item-actions" @click.stop>
                      <el-tooltip content="删除会话" placement="top">
                        <el-button type="danger" link size="small" @click.stop="handleDeleteAiConversation(item)">
                          <el-icon><Delete /></el-icon>
                        </el-button>
                      </el-tooltip>
                    </div>
                  </div>
                </div>
              </div>
            </aside>

            <div class="chat-body">
              <div ref="aiMessagesContainer" class="messages-container">
              <el-empty
                v-if="aiMessages.length === 0 && !aiLoading"
                description="输入选股需求开始对话，例如：帮我选几只低估值的银行股"
                :image-size="80"
              />
              <div v-else class="messages-list">
                <div v-for="(msg, idx) in aiMessages" :key="idx"
                  :class="['message-item', msg.role === 'user' ? 'message-user' : 'message-assistant']">
                  <template v-if="msg.role === 'user'">
                    <div class="message-content"><div class="message-text">{{ msg.content }}</div></div>
                    <div class="message-avatar"><el-icon><User /></el-icon></div>
                  </template>
                  <template v-else>
                    <div class="message-avatar"><el-icon><TrendCharts /></el-icon></div>
                    <div class="message-content">
                      <div v-if="msg.progressSteps?.length" class="progress-timeline">
                        <div class="timeline-header">
                          <span class="timeline-title">{{ getPhaseLabel(msg.phase) }}</span>
                          <span v-if="aiLoading && idx === aiPendingAssistantIndex" class="timeline-status">处理中</span>
                        </div>
                        <div v-for="(step, stepIdx) in msg.progressSteps" :key="`${idx}-${stepIdx}`" class="timeline-step">
                          <span class="step-dot" :class="[{ success: step.tone === 'success' }, { active: aiLoading && idx === aiPendingAssistantIndex && stepIdx === msg.progressSteps.length - 1 }]"></span>
                          <div class="step-content">
                            <span class="step-text">{{ step.text }}</span>
                            <span v-if="step.meta" class="step-meta">{{ step.meta }}</span>
                          </div>
                        </div>
                      </div>
                      <div v-if="msg.content" class="message-text markdown-content" v-html="renderScreeningMarkdown(msg.content)"></div>
                      <div v-if="msg.tools_used?.length" class="message-tools">
                        <el-tag v-for="t in msg.tools_used" :key="t" size="small" type="info">{{ t }}</el-tag>
                      </div>
                      <div v-if="msg.phase === 'confirmation' && idx === aiMessages.length - 1 && !aiLoading" class="confirmation-actions">
                        <el-button type="primary" size="small" @click="sendAiMessage('按原需求筛选')">按原需求筛选</el-button>
                        <el-button type="success" size="small" @click="sendAiMessage('采纳建议后筛选')">采纳建议后筛选</el-button>
                      </div>
                      <div v-if="msg.phase === 'planning' && idx === aiMessages.length - 1 && !aiLoading" class="confirmation-actions">
                        <el-button type="primary" size="small" @click="sendAiMessage('执行筛选方案')">执行筛选方案</el-button>
                        <el-button type="default" size="small" @click="sendAiMessage('重新描述需求')">重新描述需求</el-button>
                      </div>
                      <div v-if="msg.stocks?.length" class="stock-cards">
                        <el-alert v-if="msg.is_fallback" type="warning" :closable="false" show-icon
                          title="以下为优质股替代候选，不代表满足您原始筛选条件；如需继续精确筛选，请补充更明确条件" style="margin-bottom:8px;" />
                        <el-card v-for="s in msg.stocks" :key="s.code" class="stock-card" shadow="hover">
                          <div class="stock-card-header">
                            <span class="stock-name">{{ s.name }}</span>
                            <span class="stock-code">{{ s.code }}</span>
                            <el-tag size="small" type="info">{{ s.industry }}</el-tag>
                          </div>
                          <div class="stock-card-metrics">
                            <span v-if="s.price != null">价格: {{ s.price?.toFixed(2) }}</span>
                            <span v-if="s.pe != null">{{ s.pe_display_label || 'PE' }}: {{ s.pe?.toFixed(1) }}</span>
                            <span v-if="s.pb != null">{{ s.pb_display_label || 'PB' }}: {{ s.pb?.toFixed(2) }}</span>
                            <span v-if="s.roe != null">ROE: {{ s.roe?.toFixed(2) }}%</span>
                            <span v-if="s.roa != null">ROA: {{ s.roa?.toFixed(2) }}%</span>
                            <span v-if="s.gross_margin != null">毛利率: {{ s.gross_margin?.toFixed(1) }}%</span>
                            <span v-if="s.netprofit_margin != null">净利率: {{ s.netprofit_margin?.toFixed(1) }}%</span>
                            <span v-if="s.dividend_yield != null">股息率: {{ s.dividend_yield?.toFixed(2) }}%</span>
                            <span v-if="s.debt_to_assets != null">负债率: {{ s.debt_to_assets?.toFixed(2) }}%</span>
                            <span v-if="s.assets_to_eqt != null">权益乘数: {{ s.assets_to_eqt?.toFixed(2) }}</span>
                            <span v-if="s.current_ratio != null">流动比率: {{ s.current_ratio?.toFixed(2) }}</span>
                            <span v-if="s.quick_ratio != null">速动比率: {{ s.quick_ratio?.toFixed(2) }}</span>
                            <span v-if="s.cash_ratio != null">现金比率: {{ s.cash_ratio?.toFixed(2) }}</span>
                            <span v-if="s.revenue_ttm != null">营收TTM: {{ formatAiAmountYi(s.revenue_ttm) }}</span>
                            <span v-if="s.net_profit_ttm != null">净利TTM: {{ formatAiAmountYi(s.net_profit_ttm) }}</span>
                            <span v-if="s.n_cashflow_act != null">经营现金流: {{ formatAiAmountYi(s.n_cashflow_act) }}</span>
                            <span v-if="s.report_period">财报期: {{ s.report_period }}</span>
                            <span v-if="s.pct_change != null" :class="(s.pct_change ?? 0) >= 0 ? 'text-red' : 'text-green'">
                              {{ (s.pct_change ?? 0) >= 0 ? '+' : '' }}{{ s.pct_change?.toFixed(2) }}%
                            </span>
                          </div>
                          <div class="stock-card-reason">{{ s.reason }}</div>
                          <div class="stock-card-actions">
                            <el-button size="small" :type="isFavorited(s.code) ? 'warning' : 'primary'" plain @click="toggleAiFavorite(s)">
                              {{ isFavorited(s.code) ? '取消关注' : '加入关注列表' }}
                            </el-button>
                          </div>
                        </el-card>
                      </div>
                    </div>
                  </template>
                </div>
              </div>
            </div>
              <div class="input-area">
                <div class="input-row">
                  <el-input v-model="aiInput" type="textarea" :rows="2" :autosize="{ minRows: 2, maxRows: 5 }"
                    placeholder="输入选股需求，如：帮我选几只低估值的银行股、PE低于20的消费股"
                    :disabled="aiLoading" @keydown.enter.ctrl="handleAiSend" />
                  <el-button type="primary" :loading="aiLoading" :disabled="!aiInput.trim()" class="send-btn" @click="handleAiSend">发送</el-button>
                </div>
                <div class="input-tip-row">
                  <span class="input-tip">Ctrl+Enter 发送</span>
                  <el-button v-if="aiMessages.length > 0 && !aiLoading" type="default" size="small" link @click="handleClearAi">清空当前会话</el-button>
                </div>
              </div>
            </div>
          </div>
        </div>

      </el-tab-pane>

      <el-tab-pane label="高级模式" name="traditional">

    <!-- 筛选条件面板 -->
    <el-card class="filter-panel" shadow="never" v-loading="fieldsLoading">
      <template #header>
        <div class="card-header">
          <div style="display: flex; align-items: center; gap: 12px;">
            <span>筛选条件</span>
            <el-tag v-if="currentDataSource" type="info" size="small" effect="plain">
              <el-icon style="vertical-align: middle; margin-right: 4px;"><Connection /></el-icon>
              当前数据源: {{ currentDataSource.name }}
              <span v-if="currentDataSource.token_source_display" style="margin-left: 4px; opacity: 0.8;">
                ({{ currentDataSource.token_source_display }})
              </span>
            </el-tag>
            <el-tag v-else type="warning" size="small">
              <el-icon style="vertical-align: middle; margin-right: 4px;"><Warning /></el-icon>
              无可用数据源
            </el-tag>
          </div>
          <div class="header-actions">
            <el-select
              v-model="selectedPresetId"
              placeholder="选择筛选方案"
              clearable
              :loading="presetsLoading"
              style="width: 180px"
              @change="handlePresetSelect"
            >
              <el-option
                v-for="preset in savedFilterPresets"
                :key="preset.id"
                :label="preset.name"
                :value="preset.id"
              />
            </el-select>
            <el-button type="text" :loading="presetsLoading" @click="saveCurrentPreset">
              保存方案
            </el-button>
            <el-button type="text" :disabled="!selectedPresetId || presetsLoading" @click="deleteCurrentPreset">
              删除方案
            </el-button>
            <el-button type="text" @click="resetFilters">
              <el-icon><Refresh /></el-icon>
              重置
            </el-button>
          </div>
        </div>
      </template>

      <el-form :model="basicFilters" label-width="120px" class="filter-form">
        <el-row :gutter="24" class="filter-summary-row">
          <el-col :span="24">
            <div class="registry-hint">
              默认先展示常用筛选参数；需要更细条件时，再从高级字段里按需添加。全部可用字段共 {{ totalVisibleFieldCount }} 个。
            </div>
          </el-col>
        </el-row>

        <el-empty
          v-if="!filterCategorySections.length && !fieldsLoading"
          description="暂无可用筛选字段"
          :image-size="80"
        />

        <div v-if="activeConditionSummaries.length" class="active-summary-panel">
          <div class="active-summary-header">
            <span>当前生效条件</span>
            <el-tag size="small" type="success" effect="plain">{{ activeConditionSummaries.length }}项</el-tag>
          </div>
          <div class="active-summary-tags">
            <el-tag
              v-for="summary in activeConditionSummaries"
              :key="summary"
              size="small"
              effect="plain"
            >
              {{ summary }}
            </el-tag>
          </div>
        </div>

        <div v-if="hasLegacyCommonFilters" class="common-filter-panel">
          <div class="common-filter-header">
            <div>
              <div class="common-filter-title">常用条件</div>
              <div class="common-filter-subtitle">先用最常筛的 {{ commonFieldCount }} 个参数快速缩小范围；不常用字段放到下面的高级字段里再补。</div>
            </div>
          </div>

          <el-row :gutter="24" class="common-field-grid">
            <el-col :span="8">
              <el-form-item label="股票代码/名称" class="dynamic-field-item">
                <el-input
                  v-model="fieldFilters.keyword.scalarValue"
                  placeholder="请输入股票代码或名称"
                  clearable
                />
              </el-form-item>
            </el-col>

            <el-col :span="8">
              <el-form-item label="行业分类" class="dynamic-field-item">
                <el-select
                  v-model="fieldFilters.industry.selectedValues"
                  placeholder="选择行业"
                  multiple
                  filterable
                  clearable
                  collapse-tags
                  collapse-tags-tooltip
                >
                  <el-option
                    v-for="industry in industryOptions"
                    :key="industry.value"
                    :label="industry.label"
                    :value="industry.value"
                  />
                </el-select>
              </el-form-item>
            </el-col>

            <el-col :span="8">
              <el-form-item label="市场类型" class="dynamic-field-item">
                <el-select v-model="basicFilters.market" placeholder="选择市场" disabled>
                  <el-option label="A股" value="A股" />
                </el-select>
              </el-form-item>
            </el-col>

            <el-col :span="8">
              <el-form-item label="市值范围" class="dynamic-field-item">
                <el-select
                  v-model="basicFilters.marketCapRange"
                  placeholder="选择市值范围"
                  clearable
                >
                  <el-option
                    v-for="option in marketCapRangeOptions"
                    :key="option.value"
                    :label="option.label"
                    :value="option.value"
                  />
                </el-select>
              </el-form-item>
            </el-col>

            <el-col :span="8">
              <el-form-item label="市盈率 (PE)" class="dynamic-field-item">
                <div class="range-inputs">
                  <el-input-number
                    v-model="fieldFilters.pe.min"
                    placeholder="最小值"
                    :controls="false"
                    style="width: 45%"
                  />
                  <span class="range-separator">-</span>
                  <el-input-number
                    v-model="fieldFilters.pe.max"
                    placeholder="最大值"
                    :controls="false"
                    style="width: 45%"
                  />
                </div>
              </el-form-item>
            </el-col>

            <el-col :span="8">
              <el-form-item label="市净率 (PB)" class="dynamic-field-item">
                <div class="range-inputs">
                  <el-input-number
                    v-model="fieldFilters.pb.min"
                    placeholder="最小值"
                    :controls="false"
                    style="width: 45%"
                  />
                  <span class="range-separator">-</span>
                  <el-input-number
                    v-model="fieldFilters.pb.max"
                    placeholder="最大值"
                    :controls="false"
                    style="width: 45%"
                  />
                </div>
              </el-form-item>
            </el-col>

            <el-col :span="8">
              <el-form-item label="ROE (%)" class="dynamic-field-item">
                <div class="range-inputs">
                  <el-input-number
                    v-model="fieldFilters.roe.min"
                    placeholder="最小值"
                    :controls="false"
                    style="width: 45%"
                  />
                  <span class="range-separator">-</span>
                  <el-input-number
                    v-model="fieldFilters.roe.max"
                    placeholder="最大值"
                    :controls="false"
                    style="width: 45%"
                  />
                </div>
              </el-form-item>
            </el-col>

            <el-col :span="8">
              <el-form-item label="涨跌幅 (%)" class="dynamic-field-item">
                <div class="range-inputs">
                  <el-input-number
                    v-model="fieldFilters.pct_chg.min"
                    placeholder="最小值"
                    :controls="false"
                    style="width: 45%"
                  />
                  <span class="range-separator">-</span>
                  <el-input-number
                    v-model="fieldFilters.pct_chg.max"
                    placeholder="最大值"
                    :controls="false"
                    style="width: 45%"
                  />
                </div>
              </el-form-item>
            </el-col>

            <el-col :span="8">
              <el-form-item label="成交量" class="dynamic-field-item">
                <el-select
                  v-model="basicFilters.volumeLevel"
                  placeholder="选择成交量水平"
                  clearable
                >
                  <el-option
                    v-for="option in volumeLevelOptions"
                    :key="option.value"
                    :label="option.label"
                    :value="option.value"
                  />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
        </div>

        <div v-if="availableAdvancedFieldCount" class="advanced-filter-panel">
          <div class="advanced-filter-header">
            <div>
              <div class="advanced-filter-title">高级字段</div>
              <div class="advanced-filter-subtitle">不常用字段不默认铺开；需要时再主动添加到过滤条件里。</div>
            </div>
            <el-tag size="small" type="info" effect="plain">可选 {{ availableAdvancedFieldCount }} 项</el-tag>
          </div>

          <el-form-item label="添加字段" class="advanced-picker-item">
            <el-select
              v-model="selectedAdvancedFieldNames"
              placeholder="选择要追加的高级字段"
              multiple
              filterable
              clearable
              collapse-tags
              collapse-tags-tooltip
            >
              <el-option-group
                v-for="group in advancedFieldOptionGroups"
                :key="group.key"
                :label="group.label"
              >
                <el-option
                  v-for="field in group.fields"
                  :key="field.name"
                  :label="field.display_name"
                  :value="field.name"
                />
              </el-option-group>
            </el-select>
            <div class="field-help">只显示你主动添加的字段；移除字段会同时清空对应条件。</div>
          </el-form-item>

          <div v-if="selectedAdvancedFields.length" class="advanced-selected-tags">
            <el-tag
              v-for="field in selectedAdvancedFields"
              :key="field.name"
              closable
              effect="plain"
              @close="removeAdvancedField(field.name)"
            >
              {{ buildFieldLabel(field) }}
            </el-tag>
          </div>

          <div v-if="advancedFieldSections.length">
            <div
              v-for="category in advancedFieldSections"
              :key="category.key"
              class="condition-section"
            >
              <div class="condition-section-header">
                <span>{{ category.label }}</span>
                <el-tag size="small" type="info" effect="plain">{{ category.fields.length }}项</el-tag>
              </div>

              <el-row :gutter="24">
                <el-col
                  v-for="field in category.fields"
                  :key="field.name"
                  :span="8"
                >
                  <el-form-item :label="buildFieldLabel(field)" class="dynamic-field-item">
                    <template v-if="field.name === 'industry'">
                      <el-select
                        v-model="fieldFilters[field.name].selectedValues"
                        placeholder="选择行业"
                        multiple
                        filterable
                        clearable
                        collapse-tags
                        collapse-tags-tooltip
                      >
                        <el-option
                          v-for="industry in industryOptions"
                          :key="industry.value"
                          :label="industry.label"
                          :value="industry.value"
                        />
                      </el-select>
                    </template>

                    <template v-else-if="isBooleanField(field)">
                      <el-select
                        v-model="fieldFilters[field.name].booleanValue"
                        placeholder="不限"
                        clearable
                      >
                        <el-option label="否" value="false" />
                        <el-option label="是" value="true" />
                      </el-select>
                    </template>

                    <template v-else-if="isNumericField(field)">
                      <div class="range-inputs">
                        <el-input-number
                          v-model="fieldFilters[field.name].min"
                          placeholder="最小值"
                          :controls="false"
                          style="width: 45%"
                        />
                        <span class="range-separator">-</span>
                        <el-input-number
                          v-model="fieldFilters[field.name].max"
                          placeholder="最大值"
                          :controls="false"
                          style="width: 45%"
                        />
                      </div>
                    </template>

                    <template v-else>
                      <div class="string-inputs">
                        <el-select v-model="fieldFilters[field.name].operator" style="width: 120px">
                          <el-option
                            v-for="operator in getTextOperators(field)"
                            :key="operator"
                            :label="formatOperatorLabel(operator)"
                            :value="operator"
                          />
                        </el-select>
                        <el-input
                          v-model="fieldFilters[field.name].scalarValue"
                          :placeholder="buildFieldPlaceholder(field, fieldFilters[field.name].operator)"
                          clearable
                        />
                      </div>
                    </template>

                    <div v-if="buildFieldHelp(field)" class="field-help">{{ buildFieldHelp(field) }}</div>
                  </el-form-item>
                </el-col>
              </el-row>
            </div>
          </div>

          <div v-else class="advanced-empty-state">
            还没有添加高级字段。需要更细条件时，再从上方选择要补充的字段。
          </div>
        </div>

        <!-- 筛选按钮 -->
        <el-row>
          <el-col :span="24">
            <div class="filter-actions">
              <el-button
                type="primary"
                @click="performScreening"
                :loading="screeningLoading"
                size="large"
              >
                <el-icon><Search /></el-icon>
                开始筛选
              </el-button>
              <el-button @click="resetFilters" size="large">
                重置条件
              </el-button>
            </div>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <!-- 筛选结果 -->
    <el-card v-if="screeningResults.length > 0" class="results-panel" shadow="never">
      <template #header>
        <div class="card-header">
          <span>筛选结果 ({{ screeningResults.length }}只股票)</span>
          <div class="header-actions">
            <el-button
              type="primary"
              @click="batchAnalyze"
              :disabled="selectedStocks.length === 0"
            >
              <el-icon><TrendCharts /></el-icon>
              批量分析 ({{ selectedStocks.length }})
            </el-button>
            <el-button type="text" @click="exportResults">
              <el-icon><Download /></el-icon>
              导出结果
            </el-button>
          </div>
        </div>
      </template>

      <!-- 结果表格 -->
      <el-table
        :data="paginatedResults"
        @selection-change="handleSelectionChange"
        stripe
        style="width: 100%"
      >
        <el-table-column type="selection" width="55" />

        <el-table-column prop="code" label="股票代码" width="120">
          <template #default="{ row }">
            <el-link type="primary" @click="viewStockDetail(row)">
              {{ row.symbol }}
            </el-link>
          </template>
        </el-table-column>

        <el-table-column prop="name" label="股票名称" width="150" />

        <el-table-column prop="industry" label="行业" width="120" />

        <el-table-column prop="close" label="当前价格" width="100" align="right">
          <template #default="{ row }">
            <span v-if="row.close">¥{{ row.close?.toFixed(2) }}</span>
            <span v-else class="text-gray-400">-</span>
          </template>
        </el-table-column>

        <el-table-column prop="pct_chg" label="涨跌幅" width="100" align="right">
          <template #default="{ row }">
            <span v-if="row.pct_chg !== null && row.pct_chg !== undefined" :class="getChangeClass(row.pct_chg)">
              {{ row.pct_chg > 0 ? '+' : '' }}{{ row.pct_chg?.toFixed(2) }}%
            </span>
            <span v-else class="text-gray-400">-</span>
          </template>
        </el-table-column>

        <el-table-column prop="total_mv" label="市值" width="120" align="right">
          <template #default="{ row }">
            {{ formatMarketCap(row.total_mv) }}
          </template>
        </el-table-column>

        <el-table-column prop="pe" label="市盈率" width="130" align="right">
          <template #default="{ row }">
            <span v-if="row.pe">
              {{ row.pe?.toFixed(2) }}
              <el-tag v-if="row.pe_is_realtime" type="success" size="small" style="margin-left: 4px">实时</el-tag>
            </span>
            <span v-else class="text-gray-400">-</span>
          </template>
        </el-table-column>

        <el-table-column prop="pb" label="市净率" width="130" align="right">
          <template #default="{ row }">
            <span v-if="row.pb">
              {{ row.pb?.toFixed(2) }}
              <el-tag v-if="row.pe_is_realtime" type="success" size="small" style="margin-left: 4px">实时</el-tag>
            </span>
            <span v-else class="text-gray-400">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="roe" label="ROE(%)" width="110" align="right">
          <template #default="{ row }">
            <span v-if="row.roe !== null && row.roe !== undefined">{{ row.roe?.toFixed(2) }}%</span>
            <span v-else class="text-gray-400">-</span>
          </template>
        </el-table-column>

        <el-table-column label="提示信息" min-width="260">
          <template #default="{ row }">
            <div v-if="getFactorWarningEntries(row).length || getFactorDiagnosticEntries(row).length" class="warning-cell">
              <el-tooltip
                v-for="warning in getFactorWarningEntries(row)"
                :key="warning.key"
                effect="light"
                placement="top"
              >
                <template #content>
                  <div class="warning-tooltip">
                    <div class="warning-tooltip-title">{{ warning.label }}</div>
                    <div
                      v-for="condition in warning.conditions"
                      :key="condition"
                      class="warning-tooltip-line"
                    >
                      {{ condition }}
                    </div>
                  </div>
                </template>
                <el-tag :type="warning.tagType" size="small" effect="plain">
                  {{ warning.label }}
                </el-tag>
              </el-tooltip>
              <el-tooltip
                v-for="diagnostic in getFactorDiagnosticEntries(row)"
                :key="diagnostic.key"
                effect="light"
                placement="top"
              >
                <template #content>
                  <div class="warning-tooltip">
                    <div class="warning-tooltip-title">{{ diagnostic.label }}</div>
                    <div class="warning-tooltip-line">状态：{{ diagnostic.state }}</div>
                    <div v-if="diagnostic.reason" class="warning-tooltip-line">原因：{{ diagnostic.reason }}</div>
                    <div v-if="diagnostic.missingInputs.length" class="warning-tooltip-line">
                      缺失输入：{{ diagnostic.missingInputs.join('、') }}
                    </div>
                  </div>
                </template>
                <el-tag :type="diagnostic.tagType" size="small" effect="plain">
                  {{ diagnostic.label }}
                </el-tag>
              </el-tooltip>
            </div>
            <span v-else class="text-gray-400">-</span>
          </template>
        </el-table-column>

        <el-table-column prop="board" label="板块" width="100">
          <template #default="{ row }">
            {{ row.board || '-' }}
          </template>
        </el-table-column>

        <el-table-column prop="exchange" label="交易所" width="140">
          <template #default="{ row }">
            {{ row.exchange || '-' }}
          </template>
        </el-table-column>

        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button type="text" size="small" @click="analyzeSingle(row)">
              分析
            </el-button>
            <el-button type="text" size="small" @click="toggleFavorite(row)">
              <el-icon><Star /></el-icon>
              {{ isFavorited(row.symbol) ? '取消关注' : '加入关注列表' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[20, 50, 100]"
          :total="screeningResults.length"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>

    <!-- 空状态 -->
    <el-empty
      v-else-if="!screeningLoading && hasSearched"
      description="未找到符合条件的股票"
      :image-size="200"
    >
      <el-button type="primary" @click="resetFilters">
        重新筛选
      </el-button>
    </el-empty>

      </el-tab-pane>

    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, TrendCharts, Download, Star, Connection, Warning, User, Delete } from '@element-plus/icons-vue'
import { renderMarkdown } from '@/utils/markdown'
import type { StockInfo } from '@/types/analysis'
import { screeningApi, type FieldConfigResponse, type FieldInfo, type ScreeningConditionItem, type ScreeningConversationSummary, type ScreeningMessageItem, type ScreeningPreset, type ScreeningWsEnvelope, type ScreeningWsProgressData, type StockRecommendation } from '@/api/screening'
import { favoritesApi } from '@/api/favorites'
import { useAuthStore } from '@/stores/auth'
import { createWebSocket, type ManagedWebSocket } from '@/utils/createWebSocket'
import { getFactorDiagnosticEntries, getFactorWarningEntries } from '@/utils/factorPresentation'
import { loadCurrentDataSourceInfo } from '@/utils/dataSource'
import { normalizeMarketForAnalysis, exchangeCodeToMarket, getMarketByStockCode } from '@/utils/market'

// Markdown 渲染
// marked 配置已由 @/utils/markdown 统一管理
const renderScreeningMarkdown = (content: string): string => {
  if (!content?.trim()) return ''
  try {
    // 移除JSON代码块（股票数据已经通过msg.stocks渲染成卡片了）
    let cleanContent = content
      .replace(/```json\s*\{[\s\S]*?\}\s*```/g, '')
      .replace(/```\s*\{[\s\S]*?\}\s*```/g, '')
    return renderMarkdown(cleanContent)
  } catch {
    return content
  }
}

// Tab 状态
const activeTab = ref('intelligent')

// ---- 智能筛选 ----
interface AiDisplayMessage {
  role: 'user' | 'assistant'
  content: string
  tools_used?: string[]
  stocks?: StockRecommendation[]
  phase?: 'confirmation' | 'planning' | 'result'
  is_fallback?: boolean
  progressSteps?: Array<{ text: string; tone?: 'info' | 'success'; meta?: string }>
}
const aiMessages = ref<AiDisplayMessage[]>([])
const aiInput = ref('')
const aiLoading = ref(false)
const aiHistoryLoading = ref(false)
const aiMessagesContainer = ref<HTMLElement | null>(null)
const aiSocket = ref<ManagedWebSocket | null>(null)
const aiSocketConnected = ref(false)
const aiPendingAssistantIndex = ref<number | null>(null)
const aiConversationList = ref<ScreeningConversationSummary[]>([])
const aiCurrentConversationId = ref<string | null>(null)
const authStore = useAuthStore()

const scrollAiToBottom = () => {
  nextTick(() => {
    if (aiMessagesContainer.value) {
      aiMessagesContainer.value.scrollTop = aiMessagesContainer.value.scrollHeight
    }
  })
}

const getPhaseLabel = (phase?: AiDisplayMessage['phase']) => {
  if (phase === 'confirmation') return '需求分析中'
  if (phase === 'planning') return '执行规划中'
  if (phase === 'result') return '筛选执行中'
  return '处理中'
}

const formatAiAmountYi = (value?: number | null) => {
  if (value == null || Number.isNaN(value)) return ''
  return `${(value / 100000000).toFixed(2)}亿`
}

const createAiConversationId = () => `screening-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`

const unwrapApiPayload = <T,>(response: T | { data?: T } | null | undefined): T | null => {
  if (!response) return null
  if (typeof response === 'object' && response !== null && 'data' in response) {
    return ((response as { data?: T }).data ?? null) as T | null
  }
  return response as T
}

const buildToolSummaryText = (tool?: string, summary?: Record<string, number>) => {
  if (!tool || !summary) return ''

  if (tool === 'screen_stocks_by_criteria') {
    const total = summary.total_candidates
    const shown = summary.displayed_candidates
    if (typeof total === 'number' && typeof shown === 'number') {
      return `${total} 只候选，展示 ${shown} 只`
    }
  }

  if (tool === 'batch_check_profit_consistency') {
    const parts: string[] = []
    if (typeof summary.stable_count === 'number') parts.push(`稳定 ${summary.stable_count}`)
    if (typeof summary.volatile_count === 'number') parts.push(`不稳定 ${summary.volatile_count}`)
    if (typeof summary.no_data_count === 'number') parts.push(`无数据 ${summary.no_data_count}`)
    return parts.join(' / ')
  }

  if (tool === 'add_stocks_to_favorites') {
    const parts: string[] = []
    if (typeof summary.added_count === 'number') parts.push(`新增 ${summary.added_count}`)
    if (typeof summary.existing_count === 'number') parts.push(`已存在 ${summary.existing_count}`)
    if (typeof summary.failed_count === 'number') parts.push(`失败 ${summary.failed_count}`)
    return parts.join(' / ')
  }

  return ''
}

const loadAiConversation = async (conversationId?: string | null) => {
  try {
    const res = await screeningApi.getIntelligentConversation(conversationId || undefined)
    const payload = unwrapApiPayload(res as any)
    const resolvedConversationId = payload?.conversation_id || null
    const msgs = payload?.messages ?? []
    aiCurrentConversationId.value = resolvedConversationId
    if (msgs.length) {
      aiMessages.value = msgs.map((m: ScreeningMessageItem) => ({
        role: m.role,
        content: m.content,
        tools_used: m.tools_used,
        stocks: m.stocks,
        phase: m.phase,
        is_fallback: m.is_fallback,
        progressSteps: undefined,
      }))
      scrollAiToBottom()
      return
    }
    aiMessages.value = []
  } catch { /* 静默 */ }
}

const loadAiConversationList = async (preferredConversationId?: string | null) => {
  aiHistoryLoading.value = true
  try {
    const res = await screeningApi.listIntelligentConversations()
    const payload = unwrapApiPayload(res as any)
    const items = payload?.items ?? []
    aiConversationList.value = items

    const targetConversationId = preferredConversationId
      || aiCurrentConversationId.value
      || items[0]?.conversation_id
      || null

    if (targetConversationId) {
      await loadAiConversation(targetConversationId)
    } else {
      aiCurrentConversationId.value = null
      aiMessages.value = []
    }
  } catch {
    aiConversationList.value = []
  } finally {
    aiHistoryLoading.value = false
  }
}

const openAiConversation = async (conversationId: string) => {
  if (!conversationId || conversationId === aiCurrentConversationId.value) return
  await loadAiConversation(conversationId)
}

const startNewAiConversation = () => {
  aiCurrentConversationId.value = createAiConversationId()
  aiMessages.value = []
  aiInput.value = ''
  aiPendingAssistantIndex.value = null
}

const handleDeleteAiConversation = async (conversation: ScreeningConversationSummary) => {
  const conversationId = conversation.conversation_id
  if (!conversationId) return

  const title = conversation.title || '未命名筛选'
  const isCurrentConversation = conversationId === aiCurrentConversationId.value

  try {
    await ElMessageBox.confirm(`确定删除「${title}」吗？相关筛选对话会一起删除。`, '删除筛选会话', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
      confirmButtonClass: 'el-button--danger',
    })

    await screeningApi.clearIntelligentConversation(conversationId)

    if (isCurrentConversation) {
      aiCurrentConversationId.value = null
      aiMessages.value = []
      aiPendingAssistantIndex.value = null
      aiLoading.value = false
    }

    await loadAiConversationList(isCurrentConversation ? null : aiCurrentConversationId.value)
    ElMessage.success('筛选会话已删除')
  } catch {
    // 用户取消时忽略
  }
}

const updatePendingAssistantMessage = (patch: Partial<AiDisplayMessage>) => {
  const idx = aiPendingAssistantIndex.value
  if (idx == null || !aiMessages.value[idx]) return
  aiMessages.value[idx] = {
    ...aiMessages.value[idx],
    ...patch,
  }
  scrollAiToBottom()
}

const appendPendingAssistantLine = (line: string) => {
  const idx = aiPendingAssistantIndex.value
  if (idx == null || !aiMessages.value[idx] || !line) return
  const steps = [...(aiMessages.value[idx].progressSteps || [])]
  if (steps[steps.length - 1]?.text === line) return
  steps.push({ text: line, tone: 'info' })
  aiMessages.value[idx] = {
    ...aiMessages.value[idx],
    progressSteps: steps,
  }
  scrollAiToBottom()
}

const appendPendingAssistantStep = (step: { text: string; tone?: 'info' | 'success'; meta?: string }) => {
  const idx = aiPendingAssistantIndex.value
  if (idx == null || !aiMessages.value[idx] || !step.text) return
  const steps = [...(aiMessages.value[idx].progressSteps || [])]
  const prev = steps[steps.length - 1]
  if (prev?.text === step.text && prev?.meta === step.meta) return
  steps.push(step)
  aiMessages.value[idx] = {
    ...aiMessages.value[idx],
    progressSteps: steps,
  }
  scrollAiToBottom()
}

const handleAiWebSocketMessage = (envelope: ScreeningWsEnvelope<any>) => {
  if (envelope.type === 'connected' || envelope.type === 'pong') return

  if (envelope.type === 'started') {
    updatePendingAssistantMessage({ phase: 'result' })
    appendPendingAssistantLine('已收到请求，开始处理')
    return
  }

  if (envelope.type === 'progress') {
    const data = envelope.data as ScreeningWsProgressData
    if (data.phase) {
      updatePendingAssistantMessage({ phase: data.phase })
    }

    if (data.event === 'tool_started' && data.tool) {
      appendPendingAssistantStep({ text: `正在查询：${data.tool}`, tone: 'info' })
      return
    }

    if (data.event === 'tool_completed' && data.tool) {
      appendPendingAssistantStep({
        text: `已完成：${data.tool}`,
        tone: 'success',
        meta: buildToolSummaryText(data.tool, data.summary),
      })
      return
    }

    if (data.message) {
      appendPendingAssistantLine(data.message)
    }
    return
  }

  if (envelope.type === 'final') {
    const data = envelope.data
    aiCurrentConversationId.value = data.conversation_id || aiCurrentConversationId.value
    updatePendingAssistantMessage({
      content: data.reply,
      tools_used: data.tools_used?.length ? data.tools_used : undefined,
      stocks: data.stocks?.length ? data.stocks : undefined,
      phase: data.phase,
      is_fallback: data.is_fallback ?? false,
    })
    aiPendingAssistantIndex.value = null
    aiLoading.value = false
    void loadAiConversationList(aiCurrentConversationId.value)
    return
  }

  if (envelope.type === 'error') {
    const message = envelope.data?.message || '智能筛选连接异常'
    updatePendingAssistantMessage({ content: `抱歉，处理您的请求时出错：${message}` })
    aiPendingAssistantIndex.value = null
    aiLoading.value = false
    ElMessage.error(message)
  }
}

const ensureAiSocket = async (): Promise<ManagedWebSocket> => {
  if (aiSocket.value && aiSocket.value.isConnected()) {
    return aiSocket.value
  }

  return await new Promise<ManagedWebSocket>((resolve, reject) => {
    try {
      if (aiSocket.value) {
        try {
          aiSocket.value.close()
        } catch (error) {
          console.debug('[Screening] 关闭旧 AI Socket 失败:', error)
        }
      }

      const token = authStore.token || localStorage.getItem('auth-token') || ''

      // 非京东云模式：必须有 JWT token（京东云模式由 createWebSocket 内部处理）
      if (!token) {
        // 交给 createWebSocket 内部判断京东云模式，这里不提前 reject
        // 但如果既无 token 又非京东云模式，WS 连接会失败，onError 会 reject
      }

      const ws = createWebSocket('/api/screening/intelligent/ws', {
        autoReconnect: true,
        maxReconnectAttempts: 5,
        heartbeatInterval: 0, // 筛选 WS 有自己的 ping/pong 机制
        onOpen: () => {
          aiSocketConnected.value = true
          resolve(ws)
        },
        onMessage: (data) => {
          handleAiWebSocketMessage(data as ScreeningWsEnvelope<any>)
        },
        onError: () => {
          aiSocketConnected.value = false
          // 首次连接失败时 reject
          if (!aiSocket.value) {
            reject(new Error('智能筛选 WebSocket 连接失败'))
          }
        },
        onClose: () => {
          aiSocketConnected.value = false
          if (aiLoading.value && aiPendingAssistantIndex.value != null) {
            updatePendingAssistantMessage({ content: '抱歉，智能筛选流式连接已断开，请重试。' })
            aiPendingAssistantIndex.value = null
            aiLoading.value = false
          }
        },
      })

      aiSocket.value = ws
    } catch (error) {
      reject(error instanceof Error ? error : new Error('智能筛选连接失败'))
    }
  })
}

const sendAiMessage = async (text: string) => {
  if (!text.trim() || aiLoading.value) return
  aiMessages.value.push({ role: 'user', content: text })
  aiInput.value = ''
  scrollAiToBottom()
  aiLoading.value = true
  try {
    aiMessages.value.push({
      role: 'assistant',
      content: '',
      tools_used: undefined,
      stocks: undefined,
      phase: 'result',
      is_fallback: false,
      progressSteps: [{ text: '正在建立智能筛选流式连接', tone: 'info' }],
    })
    aiPendingAssistantIndex.value = aiMessages.value.length - 1
    scrollAiToBottom()

    const socket = await ensureAiSocket()
    socket.send(JSON.stringify({
      type: 'chat',
      message: text,
      conversation_id: aiCurrentConversationId.value,
    }))
  } catch (e: unknown) {
    const errMsg = e instanceof Error ? e.message : '请求失败，请稍后重试'
    ElMessage.error(errMsg)
    updatePendingAssistantMessage({ content: `抱歉，处理您的请求时出错：${errMsg}` })
    aiPendingAssistantIndex.value = null
    aiLoading.value = false
  } finally {
    if (!aiLoading.value) {
      scrollAiToBottom()
    }
  }
}

const handleAiSend = () => sendAiMessage(aiInput.value)

const handleClearAi = () => {
  ElMessageBox.confirm('确定清空当前筛选会话吗？', '提示', {
    confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning'
  }).then(async () => {
    try {
      const clearedConversationId = aiCurrentConversationId.value
      await screeningApi.clearIntelligentConversation(clearedConversationId || undefined)
      aiMessages.value = []
      aiCurrentConversationId.value = null
      await loadAiConversationList()
      ElMessage.success('已清空当前会话')
    } catch (e: unknown) {
      ElMessage.error(e instanceof Error ? e.message : '清空失败')
    }
  }).catch(() => {})
}

type FavoriteCandidate = {
  symbol: string
  name?: string
  market?: string
}

// ---- 传统筛选 ----
// 响应式数据
const screeningLoading = ref(false)
const hasSearched = ref(false)
const screeningResults = ref<StockInfo[]>([])
const selectedStocks = ref<StockInfo[]>([])
const currentPage = ref(1)
const pageSize = ref(20)

// 路由 & 自选集
const router = useRouter()
const favoriteSet = ref<Set<string>>(new Set())

// 当前数据源
const currentDataSource = ref<{
  name: string
  priority: number
  description: string
  token_source?: 'database' | 'env'
  token_source_display?: string
} | null>(null)

// 字段配置
const fieldConfig = ref<FieldConfigResponse | null>(null)
const fieldsLoading = ref(false)

type DynamicFieldState = {
  operator: string
  scalarValue: string
  min: number | null
  max: number | null
  selectedValues: string[]
  booleanValue: '' | 'true' | 'false'
}

type SavedFilterPreset = ScreeningPreset

const FILTER_PRESET_STORAGE_KEY = 'screening-filter-presets'

const fieldFilters = reactive<Record<string, DynamicFieldState>>({})
const savedFilterPresets = ref<SavedFilterPreset[]>([])
const selectedPresetId = ref<string>('')
const presetsLoading = ref(false)

type BasicFiltersState = {
  market: string
  marketCapRange: '' | 'small' | 'medium' | 'large'
  volumeLevel: '' | 'high' | 'medium' | 'low'
}

const createDefaultBasicFilters = (): BasicFiltersState => ({
  market: 'A股',
  marketCapRange: '',
  volumeLevel: '',
})

const basicFilters = reactive<BasicFiltersState>(createDefaultBasicFilters())

// 行业选项（动态加载）
const industryOptions = ref<Array<{label: string, value: string, count?: number}>>([])

const marketCapRangeOptions = [
  { label: '小盘股 (< 100亿)', value: 'small' as const },
  { label: '中盘股 (100-500亿)', value: 'medium' as const },
  { label: '大盘股 (> 500亿)', value: 'large' as const },
]

const volumeLevelOptions = [
  { label: '活跃 (高成交量)', value: 'high' as const },
  { label: '正常 (中等成交量)', value: 'medium' as const },
  { label: '清淡 (低成交量)', value: 'low' as const },
]

const marketCapRangeLabels: Record<Exclude<BasicFiltersState['marketCapRange'], ''>, string> = {
  small: '小盘股 (< 100亿)',
  medium: '中盘股 (100-500亿)',
  large: '大盘股 (> 500亿)',
}

const volumeLevelLabels: Record<Exclude<BasicFiltersState['volumeLevel'], ''>, string> = {
  high: '活跃 (高成交量)',
  medium: '正常 (中等成交量)',
  low: '清淡 (低成交量)',
}

const marketCapRangeMap: Record<Exclude<BasicFiltersState['marketCapRange'], ''>, { min: number | null; max: number | null }> = {
  small: { min: null, max: 100 },
  medium: { min: 100, max: 500 },
  large: { min: 500, max: null },
}

const volumeLevelMap: Record<Exclude<BasicFiltersState['volumeLevel'], ''>, { min: number | null; max: number | null }> = {
  high: { min: 1000000000, max: null },
  medium: { min: 300000000, max: 1000000000 },
  low: { min: null, max: 300000000 },
}

const commonControlledFieldNames = new Set(['keyword', 'symbol', 'name', 'industry', 'total_mv', 'pe', 'pb', 'roe', 'pct_chg', 'amount'])

const fieldEnglishMeta: Record<string, string> = {
  keyword: 'Keyword Search',
  symbol: 'Stock Code (Ticker)',
  name: 'Stock Name',
  industry: 'Industry',
  area: 'Region',
  total_mv: 'Total Market Value (Market Cap)',
  circ_mv: 'Circulating Market Value (Float Cap)',
  pe: 'Price-to-Earnings Ratio (P/E)',
  pb: 'Price-to-Book Ratio (P/B)',
  pe_ttm: 'Trailing Price-to-Earnings (P/E TTM)',
  pb_mrq: 'Price-to-Book, Most Recent Quarter (P/B MRQ)',
  ps: 'Price-to-Sales Ratio (P/S)',
  ps_ttm: 'Trailing Price-to-Sales (P/S TTM)',
  roe: 'Return on Equity (ROE)',
  roa: 'Return on Assets (ROA)',
  gross_margin: 'Gross Margin (GM)',
  netprofit_margin: 'Net Profit Margin (NPM)',
  revenue: 'Revenue',
  revenue_ttm: 'Trailing Twelve-Month Revenue (Revenue TTM)',
  net_profit: 'Net Profit',
  net_profit_ttm: 'Trailing Twelve-Month Net Profit (Net Profit TTM)',
  n_cashflow_act: 'Operating Cash Flow (OCF)',
  debt_to_assets: 'Debt-to-Assets Ratio (D/A)',
  assets_to_eqt: 'Equity Multiplier (EM)',
  current_ratio: 'Current Ratio (CR)',
  quick_ratio: 'Quick Ratio (QR)',
  cash_ratio: 'Cash Ratio',
  dividend_yield: 'Dividend Yield',
  close: 'Closing Price',
  pct_chg: 'Percentage Change (Pct Change)',
  amount: 'Trading Amount',
  turnover_rate: 'Turnover Rate',
  volume_ratio: 'Volume Ratio (VR)',
  ma20: '20-Day Moving Average (MA20)',
  ma60: '60-Day Moving Average (MA60)',
  rsi14: 'Relative Strength Index (RSI14)',
  kdj_k: 'KDJ K Value (KDJ-K)',
  kdj_d: 'KDJ D Value (KDJ-D)',
  kdj_j: 'KDJ J Value (KDJ-J)',
  dif: 'MACD Difference Line (DIF)',
  dea: 'MACD Signal Line (DEA)',
  macd_hist: 'MACD Histogram (MACD Hist)',
}

const selectedAdvancedFieldNames = ref<string[]>([])

// 计算属性
const paginatedResults = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return screeningResults.value.slice(start, end)
})

const categoryOrder = computed(() => fieldConfig.value?.ui_metadata?.category_order || ['basic', 'market_value', 'financial', 'trading', 'price', 'technical'])
const categoryLabels = computed(() => fieldConfig.value?.ui_metadata?.category_labels || {})
const hiddenFieldNames = computed(() => new Set(fieldConfig.value?.ui_metadata?.hidden_fields || ['code', 'market']))

const isFieldVisible = (fieldName: string) => !hiddenFieldNames.value.has(fieldName)

const hasLegacyCommonFilters = computed(() =>
  ['keyword', 'industry', 'total_mv', 'pe', 'pb', 'roe', 'pct_chg', 'amount'].every((fieldName) => !!fieldFilters[fieldName])
)

const commonFieldCount = computed(() => hasLegacyCommonFilters.value ? 9 : 0)
let suppressQuickSelectionSync = false

const createEmptyFieldState = (field: FieldInfo): DynamicFieldState => {
  let operator = field.supported_operators[0] || 'contains'
  if (field.name === 'keyword') operator = 'contains'
  if (field.name === 'industry') operator = 'in'
  if (field.name === 'is_st') operator = '=='
  if (field.data_type === 'string' && field.supported_operators.includes('contains')) operator = 'contains'

  return {
    operator,
    scalarValue: '',
    min: null,
    max: null,
    selectedValues: [],
    booleanValue: '',
  }
}

const resetFieldFilters = (config: FieldConfigResponse | null = fieldConfig.value) => {
  Object.keys(fieldFilters).forEach((key) => {
    delete fieldFilters[key]
  })

  selectedAdvancedFieldNames.value = []
  basicFilters.marketCapRange = ''
  basicFilters.volumeLevel = ''

  if (!config) return

  Object.values(config.fields)
    .filter((field) => isFieldVisible(field.name))
    .forEach((field) => {
      fieldFilters[field.name] = createEmptyFieldState(field)
    })
}

const setRangeFieldState = (
  fieldName: 'total_mv' | 'amount',
  range: { min: number | null; max: number | null } | null,
) => {
  const state = fieldFilters[fieldName]
  if (!state) return

  state.min = range?.min ?? null
  state.max = range?.max ?? null
}

const normalizeRangeValue = (value: unknown) => value == null ? null : Number(value)

const matchRangeSelection = <T extends string>(
  state: Partial<DynamicFieldState> | undefined,
  options: Record<T, { min: number | null; max: number | null }>,
): T | '' => {
  const min = normalizeRangeValue(state?.min)
  const max = normalizeRangeValue(state?.max)

  for (const [key, range] of Object.entries(options) as Array<[T, { min: number | null; max: number | null }]>) {
    if (min === range.min && max === range.max) {
      return key
    }
  }

  return ''
}

const syncQuickSelectionsFromFieldFilters = () => {
  suppressQuickSelectionSync = true
  basicFilters.marketCapRange = matchRangeSelection(fieldFilters.total_mv, marketCapRangeMap)
  basicFilters.volumeLevel = matchRangeSelection(fieldFilters.amount, volumeLevelMap)
  void nextTick(() => {
    suppressQuickSelectionSync = false
  })
}

const filterCategorySections = computed(() => {
  if (!fieldConfig.value) return [] as Array<{ key: string; label: string; fields: FieldInfo[] }>

  const visibleFieldsByCategory = fieldConfig.value.ui_metadata?.visible_fields_by_category || fieldConfig.value.categories

  return categoryOrder.value
    .map((categoryKey) => {
      const fieldNames = visibleFieldsByCategory[categoryKey] || []
      const fields = fieldNames
        .map((fieldName) => fieldConfig.value?.fields[fieldName])
        .filter((field): field is FieldInfo => {
          if (!field) return false
          return isFieldVisible(field.name)
        })

      return {
        key: categoryKey,
        label: categoryLabels.value[categoryKey] || categoryKey,
        fields,
      }
    })
    .filter((section) => section.fields.length > 0)
})

const advancedCandidateSections = computed(() =>
  filterCategorySections.value
    .map((section) => ({
      ...section,
      fields: section.fields.filter((field) => !commonControlledFieldNames.has(field.name)),
    }))
    .filter((section) => section.fields.length > 0)
)

const availableAdvancedFieldCount = computed(() =>
  advancedCandidateSections.value.reduce((total, section) => total + section.fields.length, 0)
)

const totalVisibleFieldCount = computed(() =>
  filterCategorySections.value.reduce((total, section) => total + section.fields.length, 0)
)

const isFieldStateActive = (field: FieldInfo, state?: Partial<DynamicFieldState> | null) => {
  if (!state) return false

  if (field.name === 'industry') {
    return Array.isArray(state.selectedValues) && state.selectedValues.length > 0
  }

  if (isBooleanField(field)) {
    return state.booleanValue === 'true' || state.booleanValue === 'false'
  }

  if (isNumericField(field)) {
    return state.min != null || state.max != null
  }

  return !!String(state.scalarValue || '').trim()
}

const collectActiveAdvancedFieldNames = (filters: Record<string, Partial<DynamicFieldState>> = fieldFilters) => {
  const names: string[] = []

  advancedCandidateSections.value.forEach((section) => {
    section.fields.forEach((field) => {
      if (isFieldStateActive(field, filters[field.name])) {
        names.push(field.name)
      }
    })
  })

  return Array.from(new Set(names))
}

const advancedFieldOptionGroups = computed(() => advancedCandidateSections.value)

const advancedFieldSections = computed(() => {
  const selectedNames = new Set(selectedAdvancedFieldNames.value)

  return advancedCandidateSections.value
    .map((section) => ({
      ...section,
      fields: section.fields.filter((field) => selectedNames.has(field.name)),
    }))
    .filter((section) => section.fields.length > 0)
})

const selectedAdvancedFields = computed(() =>
  advancedFieldSections.value.flatMap((section) => section.fields)
)

const availableAdvancedFieldNameSet = computed(() => new Set(
  advancedCandidateSections.value.flatMap((section) => section.fields.map((field) => field.name))
))

const activeConditionSummaries = computed(() => {
  if (!fieldConfig.value) return [] as string[]

  return buildDynamicConditions().map((condition) => {
    const field = fieldConfig.value?.fields[condition.field]
    const label = field?.display_name || condition.field
    const value = condition.value

    if (condition.field === 'total_mv' && basicFilters.marketCapRange) {
      return `市值范围: ${marketCapRangeLabels[basicFilters.marketCapRange]}`
    }

    if (condition.field === 'amount' && basicFilters.volumeLevel) {
      return `成交量水平: ${volumeLevelLabels[basicFilters.volumeLevel]}`
    }

    if (Array.isArray(value)) {
      if (condition.operator === 'between') {
        return `${label}: ${value[0]} - ${value[1]}`
      }
      return `${label} ${formatOperatorLabel(condition.operator)} ${value.join('、')}`
    }

    if (typeof value === 'boolean') {
      return `${label}: ${value ? '是' : '否'}`
    }

    return `${label} ${formatOperatorLabel(condition.operator)} ${value}`
  })
})

const isNumericField = (field: FieldInfo) => field.data_type === 'number'
const isBooleanField = (field: FieldInfo) => field.data_type === 'boolean' || field.name === 'is_st'

const getTextOperators = (field: FieldInfo) => {
  const operators = field.supported_operators.filter((operator) => ['contains', '==', '!=', 'in', 'not_in'].includes(operator))
  return operators.length ? operators : field.supported_operators
}

const formatOperatorLabel = (operator: string) => {
  const labels: Record<string, string> = {
    contains: '包含',
    '==': '等于',
    '!=': '不等于',
    in: '属于',
    not_in: '不属于',
  }
  return labels[operator] || operator
}

const resetFieldFilter = (fieldName: string) => {
  const field = fieldConfig.value?.fields[fieldName]
  if (!field || !fieldFilters[fieldName]) return
  fieldFilters[fieldName] = createEmptyFieldState(field)
}

const removeAdvancedField = (fieldName: string) => {
  selectedAdvancedFieldNames.value = selectedAdvancedFieldNames.value.filter((name) => name !== fieldName)
  resetFieldFilter(fieldName)
}

const buildFieldLabel = (field: FieldInfo) => field.unit ? `${field.display_name} (${field.unit})` : field.display_name

const buildFieldHelp = (field: FieldInfo) => {
  const parts: string[] = []
  const description = String(field.description || '').trim()
  const englishMeta = fieldEnglishMeta[field.name]

  if (description) {
    parts.push(description)
  }

  if (englishMeta) {
    parts.push(`英文：${englishMeta}`)
  }

  return parts.join(' ')
}

const buildFieldPlaceholder = (field: FieldInfo, operator: string) => {
  if (operator === 'in' || operator === 'not_in') {
    return `请输入${field.display_name}，多个值用逗号分隔`
  }
  if (field.name === 'keyword') {
    return '请输入股票代码或名称'
  }
  return `请输入${field.display_name}`
}

const parseMultiValueText = (value: string) =>
  value
    .split(/[\n,，、]+/)
    .map((item) => item.trim())
    .filter(Boolean)

const cloneFieldFilters = (): Record<string, DynamicFieldState> => {
  const snapshot: Record<string, DynamicFieldState> = {}
  Object.entries(fieldFilters).forEach(([fieldName, state]) => {
    snapshot[fieldName] = {
      operator: state.operator,
      scalarValue: state.scalarValue,
      min: state.min,
      max: state.max,
      selectedValues: [...state.selectedValues],
      booleanValue: state.booleanValue,
    }
  })
  return snapshot
}

const buildPresetBasicFilters = () => ({
  market: basicFilters.market,
  marketCapRange: basicFilters.marketCapRange,
  volumeLevel: basicFilters.volumeLevel,
  selectedAdvancedFieldNames: [...selectedAdvancedFieldNames.value],
})

const resolvePresetAdvancedFieldNames = (preset: SavedFilterPreset) => {
  const savedFieldNames = Array.isArray(preset.basicFilters?.selectedAdvancedFieldNames)
    ? preset.basicFilters.selectedAdvancedFieldNames
    : []

  const activeFieldNames = collectActiveAdvancedFieldNames(preset.fieldFilters || {})

  return Array.from(new Set([...savedFieldNames, ...activeFieldNames]))
    .filter((fieldName): fieldName is string => typeof fieldName === 'string' && availableAdvancedFieldNameSet.value.has(fieldName))
}

const sortSavedPresets = (presets: SavedFilterPreset[]) =>
  [...presets].sort((a, b) => {
    const timeA = new Date(a.updatedAt || a.createdAt || 0).getTime()
    const timeB = new Date(b.updatedAt || b.createdAt || 0).getTime()
    return timeB - timeA
  })

const normalizeSavedPreset = (preset: Partial<SavedFilterPreset> | null | undefined): SavedFilterPreset | null => {
  if (!preset?.id || !preset?.name) return null

  return {
    id: preset.id,
    name: preset.name,
    basicFilters: {
      ...createDefaultBasicFilters(),
      ...(preset.basicFilters || {}),
    },
    fieldFilters: preset.fieldFilters || {},
    createdAt: preset.createdAt,
    updatedAt: preset.updatedAt,
  }
}

const upsertSavedPreset = (preset: SavedFilterPreset) => {
  const existingIndex = savedFilterPresets.value.findIndex((item) => item.id === preset.id)
  if (existingIndex >= 0) {
    savedFilterPresets.value.splice(existingIndex, 1, preset)
  } else {
    savedFilterPresets.value.unshift(preset)
  }
  savedFilterPresets.value = sortSavedPresets(savedFilterPresets.value)
}

const loadLegacyLocalPresets = (): SavedFilterPreset[] => {
  try {
    const raw = localStorage.getItem(FILTER_PRESET_STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch (error) {
    console.warn('加载筛选方案失败:', error)
    return []
  }
}

const migrateLegacyLocalPresets = async () => {
  const legacyPresets = loadLegacyLocalPresets()
  if (!legacyPresets.length) return

  let migratedCount = 0
  for (const legacyPreset of legacyPresets) {
    const normalizedPreset = normalizeSavedPreset(legacyPreset)
    if (!normalizedPreset) continue

    const payload = {
      name: normalizedPreset.name,
      basicFilters: normalizedPreset.basicFilters,
      fieldFilters: normalizedPreset.fieldFilters,
    }

    const existing = savedFilterPresets.value.find((item) => item.name === normalizedPreset.name)
    const response = existing
      ? await screeningApi.updatePreset(existing.id, payload)
      : await screeningApi.createPreset(payload)

    const migratedPreset = normalizeSavedPreset(unwrapApiPayload((response as any))?.preset)
    if (migratedPreset) {
      upsertSavedPreset(migratedPreset)
      migratedCount += 1
    }
  }

  localStorage.removeItem(FILTER_PRESET_STORAGE_KEY)
  if (migratedCount > 0) {
    ElMessage.success(`已迁移 ${migratedCount} 个本地筛选方案到账号`) 
  }
}

const loadSavedPresets = async () => {
  presetsLoading.value = true
  try {
    const response = await screeningApi.listPresets()
    const payload = unwrapApiPayload(response as any)
    savedFilterPresets.value = sortSavedPresets(
      (payload?.items || [])
        .map((item: SavedFilterPreset) => normalizeSavedPreset(item))
        .filter((item: SavedFilterPreset | null): item is SavedFilterPreset => !!item)
    )

    try {
      await migrateLegacyLocalPresets()
    } catch (migrationError) {
      console.warn('迁移本地筛选方案失败:', migrationError)
    }
  } catch (error) {
    console.warn('加载账号筛选方案失败:', error)
    savedFilterPresets.value = []
  } finally {
    presetsLoading.value = false
  }
}

const applyPreset = (preset: SavedFilterPreset) => {
  basicFilters.market = preset.basicFilters.market || 'A股'
  resetFieldFilters()

  Object.entries(preset.fieldFilters || {}).forEach(([fieldName, state]) => {
    if (!fieldFilters[fieldName]) return
    fieldFilters[fieldName] = {
      operator: fieldName === 'keyword' ? 'contains' : (state.operator || fieldFilters[fieldName].operator),
      scalarValue: state.scalarValue || '',
      min: state.min ?? null,
      max: state.max ?? null,
      selectedValues: Array.isArray(state.selectedValues) ? [...state.selectedValues] : [],
      booleanValue: state.booleanValue || '',
    }
  })

  syncQuickSelectionsFromFieldFilters()

  if (!basicFilters.marketCapRange && preset.basicFilters.marketCapRange in marketCapRangeMap) {
    basicFilters.marketCapRange = preset.basicFilters.marketCapRange as BasicFiltersState['marketCapRange']
    setRangeFieldState('total_mv', marketCapRangeMap[basicFilters.marketCapRange as Exclude<BasicFiltersState['marketCapRange'], ''>])
  }

  if (!basicFilters.volumeLevel && preset.basicFilters.volumeLevel in volumeLevelMap) {
    basicFilters.volumeLevel = preset.basicFilters.volumeLevel as BasicFiltersState['volumeLevel']
    setRangeFieldState('amount', volumeLevelMap[basicFilters.volumeLevel as Exclude<BasicFiltersState['volumeLevel'], ''>])
  }

  selectedAdvancedFieldNames.value = resolvePresetAdvancedFieldNames(preset)
}

const handlePresetSelect = (presetId?: string) => {
  if (!presetId) return
  const preset = savedFilterPresets.value.find((item) => item.id === presetId)
  if (!preset) return
  applyPreset(preset)
  ElMessage.success(`已加载筛选方案：${preset.name}`)
}

const saveCurrentPreset = async () => {
  try {
    const { value } = await ElMessageBox.prompt('请输入筛选方案名称', '保存筛选方案', {
      confirmButtonText: '保存',
      cancelButtonText: '取消',
      inputValue: selectedPresetId.value
        ? savedFilterPresets.value.find((item) => item.id === selectedPresetId.value)?.name || ''
        : '',
      inputPlaceholder: '例如：低估值高ROE',
    })

    const name = String(value || '').trim()
    if (!name) return

    const existing = savedFilterPresets.value.find((item) => item.name === name)
    const response = existing
      ? await screeningApi.updatePreset(existing.id, {
        name,
        basicFilters: buildPresetBasicFilters(),
        fieldFilters: cloneFieldFilters(),
      })
      : await screeningApi.createPreset({
        name,
        basicFilters: buildPresetBasicFilters(),
        fieldFilters: cloneFieldFilters(),
      })

    const preset = normalizeSavedPreset(unwrapApiPayload((response as any))?.preset)
    if (!preset) {
      throw new Error('筛选方案保存失败')
    }

    upsertSavedPreset({
      id: preset.id,
      name,
      basicFilters: buildPresetBasicFilters(),
      fieldFilters: cloneFieldFilters(),
      createdAt: preset.createdAt,
      updatedAt: preset.updatedAt,
    })
    selectedPresetId.value = preset.id
    ElMessage.success(`已保存筛选方案：${name}`)
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(error instanceof Error ? error.message : '保存筛选方案失败')
  }
}

const deleteCurrentPreset = async () => {
  const preset = savedFilterPresets.value.find((item) => item.id === selectedPresetId.value)
  if (!preset) return

  try {
    await ElMessageBox.confirm(`确定删除筛选方案“${preset.name}”吗？`, '删除筛选方案', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })

    await screeningApi.deletePreset(preset.id)
    savedFilterPresets.value = savedFilterPresets.value.filter((item) => item.id !== preset.id)
    selectedPresetId.value = ''
    ElMessage.success(`已删除筛选方案：${preset.name}`)
  } catch {
    // 用户取消
  }
}

const buildDynamicConditions = (): ScreeningConditionItem[] => {
  if (!fieldConfig.value) return []

  const conditions: ScreeningConditionItem[] = []
  for (const field of Object.values(fieldConfig.value.fields).filter((item) => isFieldVisible(item.name))) {
    const state = fieldFilters[field.name]
    if (!state) continue

    if (field.name === 'industry') {
      if (state.selectedValues.length) {
        conditions.push({ field: field.name, operator: 'in', value: state.selectedValues })
      }
      continue
    }

    if (field.name === 'keyword') {
      const rawValue = state.scalarValue.trim()
      if (rawValue) {
        conditions.push({ field: field.name, operator: 'contains', value: rawValue })
      }
      continue
    }

    if (isBooleanField(field)) {
      if (state.booleanValue !== '') {
        conditions.push({ field: field.name, operator: '==', value: state.booleanValue === 'true' })
      }
      continue
    }

    if (isNumericField(field)) {
      if (state.min != null && state.max != null) {
        conditions.push({ field: field.name, operator: 'between', value: [state.min, state.max] })
      } else if (state.min != null) {
        conditions.push({ field: field.name, operator: '>=', value: state.min })
      } else if (state.max != null) {
        conditions.push({ field: field.name, operator: '<=', value: state.max })
      }
      continue
    }

    const rawValue = state.scalarValue.trim()
    if (!rawValue) continue

    if (state.operator === 'in' || state.operator === 'not_in') {
      const values = parseMultiValueText(rawValue)
      if (values.length) {
        conditions.push({ field: field.name, operator: state.operator, value: values })
      }
      continue
    }

    conditions.push({ field: field.name, operator: state.operator, value: rawValue })
  }

  return conditions
}

// 方法
const performScreening = async () => {
  screeningLoading.value = true
  hasSearched.value = true

  try {
    const conditions = buildDynamicConditions()

    const payload = {
      market: 'CN' as const,
      date: undefined,
      adj: 'qfq' as const,
      conditions,
      order_by: [{ field: 'total_mv', direction: 'desc' as const }],
      limit: 500,
      offset: 0,
      use_database_optimization: true,
    }

    // 调试日志：打印请求payload
    console.log('🔍 筛选请求 payload:', JSON.stringify(payload, null, 2))
    console.log('🔍 筛选条件 conditions:', conditions)

    const res = await screeningApi.runEnhanced(payload, { timeout: 120000 })
    const data = (res as any)?.data || res // ApiClient封装会返回 {success,data} 格式
    const items = data?.items || []

    // 直接使用后端返回的数据，字段名已统一
    screeningResults.value = items.map((it: any) => ({
      symbol: it.symbol || it.code,  // 主字段
      code: it.symbol || it.code,    // 兼容字段
      name: it.name || it.symbol || it.code,  // 使用股票名称，如果没有则用代码
      market: it.market || 'A股',
      industry: it.industry,
      area: it.area,
      board: it.board,  // 板块（主板、创业板、科创板等）
      exchange: it.exchange,  // 交易所（上海证券交易所、深圳证券交易所等）

      // 市值信息
      total_mv: it.total_mv,
      circ_mv: it.circ_mv,

      // 财务指标
      pe: it.pe,
      pb: it.pb,
      pe_ttm: it.pe_ttm,
      pb_mrq: it.pb_mrq,
      roe: it.roe,

      // 交易数据
      close: it.close,
      pct_chg: it.pct_chg,
      amount: it.amount,
      turnover_rate: it.turnover_rate,
      volume_ratio: it.volume_ratio,

      // 技术指标
      ma20: it.ma20,
      rsi14: it.rsi14,
      kdj_k: it.kdj_k,
      kdj_d: it.kdj_d,
      kdj_j: it.kdj_j,
      dif: it.dif,
      dea: it.dea,
      macd_hist: it.macd_hist,
      factor_diagnostics: it.factor_diagnostics,
      factor_warnings: it.factor_warnings,
    }))

    ElMessage.success(`筛选完成，找到 ${screeningResults.value.length} 只股票`)
  } catch (error) {
    ElMessage.error('筛选失败，请重试')
  } finally {
    screeningLoading.value = false
  }
}

const resetFilters = () => {
  basicFilters.market = 'A股'
  resetFieldFilters()

  screeningResults.value = []
  selectedStocks.value = []
  hasSearched.value = false
  currentPage.value = 1
}

watch(selectedAdvancedFieldNames, (next, prev) => {
  const nextSet = new Set(next)
  prev
    .filter((fieldName) => !nextSet.has(fieldName))
    .forEach((fieldName) => resetFieldFilter(fieldName))
})

watch(() => basicFilters.marketCapRange, (value) => {
  if (suppressQuickSelectionSync) return
  setRangeFieldState('total_mv', value ? marketCapRangeMap[value] : null)
})

watch(() => basicFilters.volumeLevel, (value) => {
  if (suppressQuickSelectionSync) return
  setRangeFieldState('amount', value ? volumeLevelMap[value] : null)
})

const handleSelectionChange = (selection: StockInfo[]) => {
  selectedStocks.value = selection
}

const batchAnalyze = async () => {
  if (selectedStocks.value.length === 0) {
    ElMessage.warning('请先选择要分析的股票')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定要对选中的 ${selectedStocks.value.length} 只股票进行批量分析吗？`,
      '确认批量分析',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'info'
      }
    )

    // 跳转到批量分析页面（携带统一市场参数）
    router.push({
      name: 'BatchAnalysis',
      query: {
        stocks: selectedStocks.value.map(s => s.symbol).join(','),
        market: normalizeMarketForAnalysis(basicFilters.market)
      }
    })
  } catch {
    // 用户取消
  }
}


const analyzeSingle = (stock: StockInfo) => {
  router.push({
    name: 'SingleAnalysis',
    query: {
      stock: stock.symbol,
      market: normalizeMarketForAnalysis((stock as any).market || basicFilters.market)
    }
  })
}

const viewStockDetail = (stock: StockInfo) => {
  // 跳转到股票详情页面
  router.push({
    name: 'StockDetail',
    params: { code: stock.symbol }
  })
}

const isFavorited = (code: string) => favoriteSet.value.has(code)

const toggleFavorite = async (stock: FavoriteCandidate) => {
  try {
    const code = stock.symbol
    if (favoriteSet.value.has(code)) {
      // 取消关注
      const res = await favoritesApi.remove(code)
      if ((res as any)?.success === false) throw new Error((res as any)?.message || '取消失败')
      favoriteSet.value.delete(code)
      ElMessage.success(`已取消关注：${stock.name || code}`)
    } else {
      // 加入关注列表
      // 根据股票代码判断市场类型
      let marketType = 'A股'
      if ((stock as any).market) {
        marketType = exchangeCodeToMarket((stock as any).market)
      } else {
        marketType = getMarketByStockCode(code) || 'A股'
      }

      const payload = {
        symbol: code,
        stock_code: code,  // 兼容字段
        stock_name: stock.name || code,
        market: marketType
      }
      const res = await favoritesApi.add(payload)
      if ((res as any)?.success === false) throw new Error((res as any)?.message || '添加失败')
      favoriteSet.value.add(code)
      ElMessage.success(`已加入关注列表：${stock.name || code}`)
    }
  } catch (error: any) {
    ElMessage.error(error?.message || '自选操作失败')
  }
}

const toggleAiFavorite = async (stock: StockRecommendation) => {
  await toggleFavorite({
    symbol: stock.code,
    name: stock.name,
    market: 'A股',
  })
}

const exportResults = () => {
  // 导出筛选结果
  ElMessage.info('导出功能开发中...')
}

const getChangeClass = (changePercent: number) => {
  if (changePercent > 0) return 'text-red'
  if (changePercent < 0) return 'text-green'
  return ''
}

const formatMarketCap = (marketCap: number) => {
  if (marketCap >= 10000) {
    return `${(marketCap / 10000).toFixed(2)}万亿`
  } else {
    return `${marketCap.toFixed(2)}亿`
  }
}

const handleSizeChange = (size: number) => {
  pageSize.value = size
  currentPage.value = 1
}

const handleCurrentChange = (page: number) => {
  currentPage.value = page
}

// 获取字段配置
const loadFieldConfig = async () => {
  fieldsLoading.value = true
  try {
    const response = await screeningApi.getFields()
    fieldConfig.value = response
    resetFieldFilters(fieldConfig.value)
    syncQuickSelectionsFromFieldFilters()
    console.log('因子注册表字段配置加载成功:', fieldConfig.value)
  } catch (error) {
    console.error('加载因子注册表字段配置失败:', error)
    ElMessage.error('加载字段配置失败')
  } finally {
    fieldsLoading.value = false
  }
}

// 加载行业列表
const loadIndustries = async () => {
  try {
    const response = await screeningApi.getIndustries()
    const data = response.data || response
    industryOptions.value = data.industries || []
    console.log('行业列表加载成功:', industryOptions.value.length, '个行业')
  } catch (error) {
    console.error('加载行业列表失败:', error)
    ElMessage.error('加载行业列表失败')
    // 如果加载失败，使用默认的行业列表
    industryOptions.value = [
      { label: '银行', value: '银行' },
      { label: '证券', value: '证券' },
      { label: '保险', value: '保险' },
      { label: '房地产', value: '房地产' },
      { label: '医药生物', value: '医药生物' }
    ]
  }
}

// 加载自选列表，初始化 favoriteSet
const loadFavorites = async () => {
  try {
    const resp = await favoritesApi.list()
    const list = (resp as any)?.data || resp
    const set = new Set<string>()
    ;(list || []).forEach((item: any) => {
      // 兼容新旧字段
      const code = item.symbol || item.stock_code || item.code
      if (code) set.add(code)
    })
    favoriteSet.value = set
  } catch (e) {
    console.warn('加载自选列表失败，可能未登录或接口不可用。', e)
  }
}

// 获取当前数据源
const loadCurrentDataSource = async () => {
  try {
    const currentSource = await loadCurrentDataSourceInfo()
    if (currentSource) {
      currentDataSource.value = currentSource
    }
  } catch (e) {
    console.warn('获取当前数据源失败', e)
  }
}

// 生命周期
onMounted(() => {
  // 加载字段配置和行业列表
  void loadSavedPresets()
  loadFieldConfig()
  loadIndustries()
  // 初始化自选状态
  loadFavorites()
  // 加载当前数据源
  loadCurrentDataSource()
  // 加载智能筛选会话历史
  loadAiConversationList()
})

onUnmounted(() => {
  if (aiSocket.value) {
    try {
      aiSocket.value.close()
    } catch (error) {
      console.debug('[Screening] 页面卸载时关闭 AI Socket 失败:', error)
    }
    aiSocket.value = null
    aiSocketConnected.value = false
  }
})
</script>

<style lang="scss" scoped>
.stock-screening {
  .page-header {
    margin-bottom: 24px;

    .page-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 24px;
      font-weight: 600;
      color: var(--el-text-color-primary);
      margin: 0 0 8px 0;
    }

    .page-description {
      color: var(--el-text-color-regular);
      margin: 0;
    }
  }

  .filter-panel {
    margin-bottom: 24px;

    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;

      .header-actions {
        display: flex;
        gap: 8px;
      }
    }

    .filter-form {
      .filter-summary-row {
        margin-bottom: 8px;
      }

      .active-summary-panel {
        margin-bottom: 16px;
        padding: 12px;
        border: 1px solid var(--el-border-color-lighter);
        border-radius: 10px;
        background: var(--el-fill-color-extra-light);
      }

      .active-summary-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 10px;
        color: var(--el-text-color-primary);
        font-weight: 600;
      }

      .active-summary-tags {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }

      .registry-hint {
        min-height: 32px;
        display: flex;
        align-items: center;
        padding: 0 12px;
        border-radius: 8px;
        background: var(--el-fill-color-light);
        color: var(--el-text-color-regular);
      }

      .common-filter-panel,
      .advanced-filter-panel {
        margin-bottom: 16px;
        padding: 16px;
        border: 1px solid var(--el-border-color-lighter);
        border-radius: 12px;
        background: var(--el-bg-color-page);
      }

      .common-filter-header,
      .advanced-filter-header {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 16px;
        margin-bottom: 14px;
      }

      .common-filter-title,
      .advanced-filter-title {
        font-size: 15px;
        font-weight: 600;
        color: var(--el-text-color-primary);
      }

      .common-filter-subtitle,
      .advanced-filter-subtitle {
        margin-top: 4px;
        color: var(--el-text-color-secondary);
        font-size: 13px;
        line-height: 1.6;
      }

      .condition-section + .condition-section {
        margin-top: 16px;
      }

      .condition-section-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 12px;
        font-weight: 600;
        color: var(--el-text-color-primary);
      }

      .advanced-picker-item {
        margin-bottom: 16px;
      }

      .advanced-selected-tags {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-bottom: 12px;
      }

      .advanced-empty-state {
        color: var(--el-text-color-secondary);
        font-size: 13px;
        line-height: 1.6;
      }

      .dynamic-field-item {
        :deep(.el-form-item__content) {
          display: flex;
          flex-direction: column;
          align-items: stretch;
          gap: 8px;
        }
      }

      .range-inputs,
      .string-inputs {
        display: flex;
        align-items: center;
        gap: 8px;
        width: 100%;
      }

      .range-separator {
        color: var(--el-text-color-secondary);
      }

      .field-help {
        font-size: 12px;
        line-height: 1.5;
        color: var(--el-text-color-secondary);
      }

      .filter-actions {
        display: flex;
        justify-content: center;
        gap: 16px;
        margin-top: 24px;
      }

      @media (max-width: 768px) {
        .common-filter-header,
        .advanced-filter-header {
          flex-direction: column;
          align-items: stretch;
        }
      }
    }
  }

  .results-panel {
    .warning-cell {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }

    .warning-tooltip {
      max-width: 320px;
    }

    .warning-tooltip-title {
      font-weight: 600;
      margin-bottom: 4px;
      color: var(--el-text-color-primary);
    }

    .warning-tooltip-line {
      font-size: 12px;
      line-height: 1.5;
      color: var(--el-text-color-regular);
    }

    .pagination-wrapper {
      display: flex;
      justify-content: center;
      margin-top: 24px;
    }
  }

  .text-red {
    color: #f56c6c;
  }

  .text-green {
    color: #67c23a;
  }

  // ---- 智能筛选样式 ----
  .screening-tabs {
    :deep(.el-tabs__content) {
      overflow: visible;
    }
  }

  .intelligent-screening {
    .chat-layout {
      display: grid;
      grid-template-columns: 280px minmax(0, 1fr);
      gap: 16px;
      min-height: 0;
      height: calc(100vh - 220px);
    }

    .history-panel {
      display: flex;
      flex-direction: column;
      min-width: 0;
      min-height: 0;
      border: 1px solid var(--el-border-color-lighter);
      border-radius: 8px;
      background: var(--el-bg-color);
      padding: 14px;
    }

    .history-header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 12px;
    }

    .history-title {
      font-size: 15px;
      font-weight: 600;
      color: var(--el-text-color-primary);
    }

    .history-subtitle {
      margin-top: 4px;
      font-size: 12px;
      color: var(--el-text-color-secondary);
      line-height: 1.5;
    }

    .history-empty {
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 120px;
      color: var(--el-text-color-secondary);
      font-size: 13px;
    }

    .history-list {
      display: flex;
      flex-direction: column;
      gap: 10px;
      min-width: 0;
      min-height: 0;
      overflow-x: hidden;
      overflow-y: auto;
      padding-right: 2px;
    }

    .history-item {
      appearance: none;
      width: 100%;
      min-width: 0;
      border: 1px solid var(--el-border-color-lighter);
      border-radius: 10px;
      background: var(--el-fill-color-extra-light);
      padding: 12px;
      overflow: hidden;
      text-align: left;
      cursor: pointer;
      transition: border-color 0.2s ease, background-color 0.2s ease, transform 0.2s ease;

      &:hover {
        border-color: var(--el-color-primary-light-5);
        background: var(--el-color-primary-light-9);
      }

      &.active {
        border-color: var(--el-color-primary);
        background: rgba(64, 158, 255, 0.08);
      }
    }

    .history-item-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      min-width: 0;
    }

    .history-item-title {
      font-size: 13px;
      font-weight: 600;
      color: var(--el-text-color-primary);
      line-height: 1.5;
      min-width: 0;
      flex: 1;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .history-item-actions {
      display: flex;
      align-items: center;
      flex-shrink: 0;

      :deep(.el-button) {
        margin: 0;
        padding: 0;
        min-width: auto;
      }
    }

    .chat-body {
      display: flex;
      flex-direction: column;
      min-height: 0;
      height: 100%;
      border: 1px solid var(--el-border-color-lighter);
      border-radius: 8px;
      background: var(--el-bg-color);
    }

    .messages-container {
      flex: 1;
      overflow-y: auto;
      padding: 20px 24px;
      min-height: 0;
    }

    .messages-list {
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .message-item {
      display: flex;
      gap: 12px;
      align-items: flex-start;
      max-width: 92%;

      &.message-user {
        align-self: flex-end;
        flex-direction: row-reverse;

        .message-avatar {
          background: var(--el-color-primary-light-9);
          color: var(--el-color-primary);
        }
        .message-content {
          background: var(--el-color-primary);
          color: #fff;
          border-radius: 12px;
          padding: 10px 16px;
        }
        .message-text { color: inherit; }
      }

      &.message-assistant {
        align-self: flex-start;

        .message-avatar {
          background: var(--el-fill-color-light);
          color: var(--el-text-color-regular);
        }
        .message-content {
          background: var(--el-fill-color-lighter);
          border-radius: 12px;
          padding: 12px 20px;
        }
      }
    }

    .message-avatar {
      width: 32px;
      height: 32px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      font-size: 16px;
    }

    .message-text {
      word-break: break-word;
      line-height: 1.7;
      font-size: 14px;

      &.markdown-content {
        :deep(h1), :deep(h2), :deep(h3), :deep(h4) { margin: 12px 0 8px; font-weight: 600; }
        :deep(h1:first-child), :deep(h2:first-child), :deep(h3:first-child) { margin-top: 0; }
        :deep(h1) { font-size: 18px; }
        :deep(h2) { font-size: 16px; }
        :deep(h3) { font-size: 15px; }
        :deep(p) { margin: 6px 0; }
        :deep(ul), :deep(ol) { margin: 6px 0; padding-left: 24px; }
        :deep(li) { margin: 3px 0; }
        :deep(strong) { font-weight: 600; }
        :deep(code) { background: var(--el-fill-color); padding: 2px 6px; border-radius: 4px; font-size: 0.9em; }
        :deep(table) { border-collapse: collapse; margin: 8px 0; font-size: 13px; }
        :deep(th), :deep(td) { border: 1px solid var(--el-border-color-lighter); padding: 4px 10px; }
        :deep(th) { background: var(--el-fill-color-light); font-weight: 600; }
      }
    }

    .message-tools {
      margin-top: 8px;
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
    }

    .progress-timeline {
      margin-bottom: 10px;
      padding: 10px 12px;
      background: linear-gradient(180deg, rgba(255,255,255,0.55) 0%, rgba(255,255,255,0.2) 100%);
      border: 1px solid var(--el-border-color-lighter);
      border-radius: 10px;

      .timeline-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        margin-bottom: 8px;
      }

      .timeline-title {
        font-size: 12px;
        font-weight: 600;
        color: var(--el-text-color-primary);
        letter-spacing: 0.02em;
      }

      .timeline-status {
        font-size: 12px;
        color: var(--el-color-primary);
      }

      .timeline-step {
        display: flex;
        align-items: flex-start;
        gap: 10px;
        position: relative;
        padding: 0 0 8px 0;

        &:last-child {
          padding-bottom: 0;
        }

        &:not(:last-child)::after {
          content: '';
          position: absolute;
          left: 5px;
          top: 14px;
          width: 1px;
          height: calc(100% - 6px);
          background: var(--el-border-color);
        }
      }

      .step-dot {
        width: 10px;
        height: 10px;
        margin-top: 4px;
        border-radius: 50%;
        background: var(--el-border-color-dark);
        flex-shrink: 0;

        &.success {
          background: var(--el-color-success);
        }

        &.active {
          background: var(--el-color-primary);
          box-shadow: 0 0 0 4px rgba(64, 158, 255, 0.14);
        }
      }

      .step-content {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 8px;
      }

      .step-text {
        font-size: 13px;
        line-height: 1.55;
        color: var(--el-text-color-regular);
      }

      .step-meta {
        display: inline-flex;
        align-items: center;
        padding: 2px 8px;
        border-radius: 999px;
        background: rgba(64, 158, 255, 0.08);
        color: var(--el-color-primary-dark-2);
        font-size: 12px;
        line-height: 1.4;
      }
    }

    .confirmation-actions {
      margin-top: 10px;
      display: flex;
      gap: 8px;
    }

    .stock-cards {
      margin-top: 12px;
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
      gap: 12px;
    }

    .stock-card {
      :deep(.el-card__body) { padding: 12px 16px; }

      .stock-card-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 8px;

        .stock-name { font-weight: 600; font-size: 15px; }
        .stock-code { color: var(--el-text-color-secondary); font-size: 13px; }
      }

      .stock-card-metrics {
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        font-size: 13px;
        color: var(--el-text-color-regular);
        margin-bottom: 8px;
      }

      .stock-card-reason {
        font-size: 13px;
        color: var(--el-text-color-secondary);
        line-height: 1.5;
      }

      .stock-card-actions {
        margin-top: 10px;
        display: flex;
        justify-content: flex-end;
      }
    }

    .input-area {
      flex-shrink: 0;
      padding: 12px 16px;
      border-top: 1px solid var(--el-border-color-lighter);

      .input-row {
        display: flex;
        gap: 12px;
        align-items: flex-end;
      }

      .send-btn {
        flex-shrink: 0;
        height: 56px;
        padding: 0 24px;
      }

      .input-tip-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-top: 4px;
      }

      .input-tip {
        font-size: 12px;
        color: var(--el-text-color-placeholder);
      }

      :deep(.el-textarea__inner) { resize: none; }
    }

    @media (max-width: 1100px) {
      .chat-layout {
        grid-template-columns: 1fr;
        height: auto;
      }

      .history-panel {
        max-height: 240px;
      }

      .chat-body {
        height: calc(100vh - 340px);
      }
    }
  }
}

@keyframes screening-blink {
  0%, 60%, 100% { opacity: 0.2; }
  30% { opacity: 1; }
}
</style>


