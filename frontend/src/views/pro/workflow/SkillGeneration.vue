<template>
  <div class="skill-generation-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <h1>
          <el-icon class="header-icon"><MagicStick /></el-icon>
          Skill 能力中心
        </h1>
        <span class="subtitle">管理 AI 生成与 Agent Studio 自动补齐的可复用能力</span>
      </div>
      <div class="header-right">
        <el-button type="primary" @click="() => goToCreate()">
          <el-icon><Plus /></el-icon>
          手动创建 Skill
        </el-button>
        <el-button @click="loadSkills">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- 未完成的草稿 -->
    <div v-if="draftSessions.length > 0" class="draft-section">
      <div class="section-header">
        <div class="draft-section-title">
          <h2>📝 未完成的草稿</h2>
          <span class="draft-section-subtitle">按系统推荐的分类与来源筛选，默认优先展示命中更明确的草稿</span>
        </div>
        <div class="draft-toolbar">
          <el-select v-model="draftCategoryFilter" clearable placeholder="推荐分类" size="small" style="width: 130px">
            <el-option v-for="item in availableDraftCategoryHints" :key="`draft-category-${item}`" :label="item" :value="item" />
          </el-select>
          <el-select v-model="draftSourceFilter" clearable placeholder="推荐来源" size="small" style="width: 140px">
            <el-option v-for="item in availableDraftSourceHints" :key="`draft-source-${item}`" :label="item" :value="item" />
          </el-select>
          <el-switch v-model="draftHighMatchOnly" inline-prompt active-text="高匹配" inactive-text="全部" size="small" />
          <el-button text size="small" @click="resetDraftFilters" :disabled="!draftCategoryFilter && !draftSourceFilter">清空筛选</el-button>
          <el-button text size="small" @click="loadDrafts">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </div>
      <div v-if="displayedDraftSessions.length !== draftSessions.length" class="draft-filter-summary">
        当前显示 {{ displayedDraftSessions.length }} / {{ draftSessions.length }} 个草稿
      </div>
      <div class="draft-cards">
        <div v-for="draft in displayedDraftSessions" :key="draft.session_id" class="draft-card">
          <div class="draft-card-header">
            <div class="draft-card-statuses">
              <el-tag :type="draft.status === 'gathering' ? 'warning' : 'info'" size="small">
                {{ draft.status === 'gathering' ? '需求沟通中' : draft.status === 'confirmed' ? '已确认待生成' : draft.status }}
              </el-tag>
              <el-tooltip :content="getDraftMatchTooltip(draft)" placement="top" :show-after="200">
                <el-tag :type="getDraftMatchTagType(draft)" size="small" effect="plain" class="draft-match-tag">
                  {{ getDraftMatchLabel(draft) }}
                </el-tag>
              </el-tooltip>
            </div>
            <span class="draft-time">{{ formatTime(draft.updated_at) }}</span>
          </div>
          <div class="draft-card-body">
            <p class="draft-preview">{{ getDraftPreview(draft) }}</p>
            <div class="draft-meta">
              <span>已对话 {{ draft.rounds?.length || 0 }} 轮</span>
              <span v-if="draft.clarity_level">· 清晰度: {{ draft.clarity_level }}</span>
            </div>
            <div v-if="draft.recommendations?.stock_collections?.length || draft.recommendations?.external_sources?.length" class="draft-recommendations">
              <div v-if="draft.recommendations?.stock_collections?.length" class="draft-recommendation-row">
                <span class="draft-recommendation-label">本地:</span>
                <el-tag v-for="entry in draft.recommendations.stock_collections.slice(0, 2)" :key="`${draft.session_id}-stock-${entry}`" size="small" type="success" effect="plain">{{ entry }}</el-tag>
              </div>
              <div v-if="draft.recommendations?.external_sources?.length" class="draft-recommendation-row">
                <span class="draft-recommendation-label">外部:</span>
                <el-tag v-for="entry in draft.recommendations.external_sources.slice(0, 2)" :key="`${draft.session_id}-source-${entry}`" size="small" type="warning" effect="plain">{{ entry }}</el-tag>
              </div>
            </div>
          </div>
          <div class="draft-card-footer">
            <el-button :type="draft.status === 'confirmed' ? 'success' : 'primary'" size="small" @click="() => goToCreate(draft.session_id)">
              {{ getDraftPrimaryActionLabel(draft) }}
            </el-button>
            <el-button
              v-if="draft.status === 'confirmed' && isHighMatchDraft(draft)"
              type="warning"
              size="small"
              plain
              @click="() => goToCreateWithFocus(draft.session_id, 'recommendations')"
            >
              聚焦建议
            </el-button>
            <el-button
              v-if="draft.status === 'confirmed' && isHighMatchDraft(draft)"
              type="success"
              size="small"
              plain
              @click="() => goToCreateWithFocus(draft.session_id, 'confirm')"
            >
              继续生成
            </el-button>
            <el-button type="danger" size="small" text @click="handleDeleteDraft(draft)">
              删除
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- Skill 列表 -->
    <div class="skill-list-section">
      <div class="section-header skill-list-header">
        <div>
          <h2>能力资产</h2>
          <span class="section-subtitle">查看来源、被哪些 Agent 使用，以及当前运行状态</span>
        </div>
        <div class="skill-filters">
          <el-select v-model="filterSource" placeholder="来源" size="small" style="width: 180px" @change="loadSkills">
            <el-option label="全部来源" value="" />
            <el-option label="Agent Studio 自动补齐" value="agent_studio_auto_gap_resolution" />
            <el-option label="手动/其它创建" value="manual_or_other" />
          </el-select>
          <el-radio-group v-model="filterStatus" size="small" @change="loadSkills">
            <el-radio-button label="">全部</el-radio-button>
            <el-radio-button label="active">已启用</el-radio-button>
            <el-radio-button label="disabled">已禁用</el-radio-button>
          </el-radio-group>
        </div>
      </div>

      <el-table v-loading="listLoading" :data="skills" style="width: 100%" border stripe empty-text="还没有生成任何 Skill，点击上方按钮创建" :row-class-name="getSkillRowClassName">
        <el-table-column prop="display_name" label="名称" min-width="160">
          <template #default="{ row }">
            <span class="skill-name-cell">
              <strong>{{ row.display_name || row.tool_id }}</strong>
              <el-tag size="small" type="info" style="margin-left: 6px">{{ row.category }}</el-tag>
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="240" show-overflow-tooltip />
        <el-table-column label="来源" min-width="210">
          <template #default="{ row }">
            <div class="source-cell">
              <el-tag :type="getSkillSourceTagType(row)" size="small" effect="plain">
                {{ getSkillSourceLabel(row) }}
              </el-tag>
              <span v-if="row.origin_agent_name" class="source-agent">{{ row.origin_agent_name }}</span>
              <span v-else-if="row.origin_spec_id" class="source-agent">{{ row.origin_spec_id }}</span>
              <span v-if="row.origin_gap_id" class="source-gap">{{ row.origin_gap_id }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="使用关系" min-width="220">
          <template #default="{ row }">
            <div v-if="row.used_by_agents?.length" class="usage-cell">
              <el-tag v-for="usage in row.used_by_agents.slice(0, 2)" :key="usage.version_id" size="small" effect="plain" type="success">
                {{ usage.agent_name || usage.spec_id }} v{{ usage.version || '-' }}
              </el-tag>
              <el-tooltip v-if="row.used_by_agents.length > 2" :content="getSkillUsageTooltip(row)" placement="top">
                <span class="usage-more">+{{ row.used_by_agents.length - 2 }}</span>
              </el-tooltip>
            </div>
            <span v-else class="strategy-empty">暂未绑定 Agent</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : row.status === 'disabled' ? 'info' : 'warning'" size="small">
              {{ row.status === 'active' ? '启用' : row.status === 'disabled' ? '禁用' : row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="final_score" label="评分" width="80" align="center">
          <template #default="{ row }">
            <span v-if="row.final_score != null">{{ row.final_score }}/10</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="复用策略" min-width="220">
          <template #default="{ row }">
            <div v-if="hasGenerationContext(row)" class="strategy-cell">
              <div class="strategy-head">
                <el-tag v-if="row.generation_context?.category_hint" size="small" type="success" effect="plain">
                  {{ row.generation_context.category_hint }}
                </el-tag>
                <el-tag v-if="row.generation_context?.data_source_hint" size="small" type="warning" effect="plain">
                  {{ row.generation_context.data_source_hint }}
                </el-tag>
              </div>
              <el-popover placement="top-start" :width="340" trigger="hover">
                <template #reference>
                  <el-button text size="small" class="strategy-trigger">
                    {{ getGenerationStrategySummary(row) }}
                  </el-button>
                </template>
                <div class="strategy-popover">
                  <div v-if="row.generation_context?.stock_collections?.length" class="strategy-popover-row">
                    <span class="strategy-popover-label">本地集合</span>
                    <el-tag
                      v-for="entry in row.generation_context.stock_collections"
                      :key="`${row.tool_id}-stock-${entry}`"
                      size="small"
                      type="success"
                      effect="plain"
                    >
                      {{ entry }}
                    </el-tag>
                  </div>
                  <div v-if="row.generation_context?.external_sources?.length" class="strategy-popover-row">
                    <span class="strategy-popover-label">外部来源</span>
                    <el-tag
                      v-for="entry in row.generation_context.external_sources"
                      :key="`${row.tool_id}-source-${entry}`"
                      size="small"
                      type="warning"
                      effect="plain"
                    >
                      {{ entry }}
                    </el-tag>
                  </div>
                </div>
              </el-popover>
            </div>
            <span v-else class="strategy-empty">未记录</span>
          </template>
        </el-table-column>
        <el-table-column prop="generation_rounds" label="轮次" width="70" align="center" />
        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="340" fixed="right">
          <template #default="{ row }">
            <el-button type="info" link size="small" @click="showHistoryDialog(row)">沟通记录</el-button>
            <el-button type="primary" link size="small" @click="showCodeDialog(row)">代码</el-button>
            <el-button type="primary" link size="small" @click="handleTest(row)">测试</el-button>
            <el-button type="warning" link size="small" @click="showOptimizeDialog(row)">优化</el-button>
            <el-button v-if="row.status === 'active'" type="warning" link size="small" @click="handleStatusToggle(row, 'disabled')">禁用</el-button>
            <el-button v-else type="success" link size="small" @click="handleStatusToggle(row, 'active')">启用</el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 代码查看对话框 -->
    <el-dialog v-model="codeDialogVisible" :title="'源代码: ' + codeDialogTitle" width="750px" destroy-on-close>
      <div class="code-viewer-header">
        <el-button size="small" @click="copyCode" :disabled="!codeContent">
          <el-icon><DocumentCopy /></el-icon>
          复制代码
        </el-button>
      </div>
      <pre class="code-viewer"><code v-html="highlightedCode"></code></pre>
    </el-dialog>

    <!-- 测试对话框：参数输入 + 结果 -->
    <el-dialog v-model="testDialogVisible" :title="'🧪 测试: ' + (testSkillRow?.display_name || testSkillRow?.tool_id || '')" width="640px" destroy-on-close>
      <!-- 参数输入区 -->
      <div v-if="testSkillRow" class="test-params-section">
        <div class="test-params-header">输入测试参数</div>
        <el-form v-if="testParamsList.length > 0" label-width="120px" size="default">
          <el-form-item v-for="p in testParamsList" :key="p.name" :label="p.name" :required="p.required">
            <el-input
              v-if="p.type === 'string' || !p.type"
              v-model="testArgs[p.name]"
              :placeholder="p.description || `请输入 ${p.name}`"
              clearable
            />
            <el-input-number
              v-else-if="p.type === 'integer' || p.type === 'int'"
              v-model="testArgs[p.name]"
              :placeholder="p.description"
              controls-position="right"
              style="width: 100%"
            />
            <el-input-number
              v-else-if="p.type === 'float' || p.type === 'number'"
              v-model="testArgs[p.name]"
              :placeholder="p.description"
              :precision="2"
              controls-position="right"
              style="width: 100%"
            />
            <el-switch v-else-if="p.type === 'boolean' || p.type === 'bool'" v-model="testArgs[p.name]" />
            <el-input
              v-else
              v-model="testArgs[p.name]"
              :placeholder="p.description || `请输入 ${p.name}`"
              clearable
            />
          </el-form-item>
        </el-form>
        <p v-else class="test-params-empty">该 Skill 无参数，将使用默认测试输入</p>
        <div class="test-actions">
          <el-button type="primary" @click="runTest" :loading="testLoading">
            执行测试
          </el-button>
        </div>
      </div>
      <!-- 测试结果区 -->
      <div class="test-result-section">
        <div v-if="testResult" class="test-result-content">
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="执行结果">
              <el-tag :type="testResult.success ? 'success' : 'danger'">{{ testResult.success ? '成功' : '失败' }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="耗时">{{ testResult.execution_time }}s</el-descriptions-item>
            <el-descriptions-item v-if="testResult.error" label="错误">
              <span style="color: var(--el-color-danger)">{{ testResult.error }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="输出">
              <pre style="max-height: 280px; overflow: auto; white-space: pre-wrap; font-size: 12px;">{{ JSON.stringify(testResult.output, null, 2) }}</pre>
            </el-descriptions-item>
          </el-descriptions>
        </div>
        <div v-else-if="testLoading" style="text-align: center; padding: 24px">
          <el-icon class="is-loading" :size="24"><Loading /></el-icon>
          <p>测试执行中...</p>
        </div>
        <div v-else-if="testSkillRow && !testResult" style="text-align: center; padding: 24px; color: var(--el-text-color-placeholder); font-size: 13px">
          填写参数后点击「执行测试」
        </div>
      </div>
    </el-dialog>

    <!-- 沟通记录对话框 -->
    <el-dialog v-model="historyDialogVisible" :title="'💬 沟通记录: ' + historyDialogTitle" width="700px" destroy-on-close top="5vh">
      <div v-if="historyLoading" style="text-align: center; padding: 40px">
        <el-icon class="is-loading" :size="24"><Loading /></el-icon>
        <p>加载中...</p>
      </div>
      <div v-else>
        <div v-if="historySkillRow && (hasGenerationContext(historySkillRow) || historySkillRow.origin_source || historySkillRow.used_by_agents?.length)" class="history-strategy-panel">
          <div class="history-strategy-title">治理与追溯信息</div>
          <div v-if="historySkillRow.origin_source || historySkillRow.origin_agent_name || historySkillRow.origin_gap_id" class="strategy-detail-row">
            <span class="strategy-detail-label">来源</span>
            <el-tag :type="getSkillSourceTagType(historySkillRow)" size="small" effect="plain">{{ getSkillSourceLabel(historySkillRow) }}</el-tag>
            <span v-if="historySkillRow.origin_agent_name" class="source-agent">{{ historySkillRow.origin_agent_name }}</span>
            <span v-if="historySkillRow.origin_gap_id" class="source-gap">{{ historySkillRow.origin_gap_id }}</span>
          </div>
          <div v-if="historySkillRow.used_by_agents?.length" class="strategy-detail-row">
            <span class="strategy-detail-label">被使用</span>
            <el-tag v-for="usage in historySkillRow.used_by_agents" :key="usage.version_id" size="small" type="success" effect="plain">
              {{ usage.agent_name || usage.spec_id }} v{{ usage.version || '-' }}
            </el-tag>
          </div>
          <div v-if="hasGenerationContext(historySkillRow)" class="history-strategy-title">本次生成采用的复用策略</div>
          <div class="history-strategy-tags">
            <el-tag v-if="historySkillRow.generation_context?.category_hint" size="small" type="success" effect="plain">
              {{ historySkillRow.generation_context.category_hint }}
            </el-tag>
            <el-tag v-if="historySkillRow.generation_context?.data_source_hint" size="small" type="warning" effect="plain">
              {{ historySkillRow.generation_context.data_source_hint }}
            </el-tag>
          </div>
          <div v-if="historySkillRow.generation_context?.stock_collections?.length" class="strategy-detail-row">
            <span class="strategy-detail-label">本地集合</span>
            <el-tag
              v-for="entry in historySkillRow.generation_context.stock_collections"
              :key="`history-stock-${entry}`"
              size="small"
              type="success"
              effect="plain"
            >
              {{ entry }}
            </el-tag>
          </div>
          <div v-if="historySkillRow.generation_context?.external_sources?.length" class="strategy-detail-row">
            <span class="strategy-detail-label">外部来源</span>
            <el-tag
              v-for="entry in historySkillRow.generation_context.external_sources"
              :key="`history-source-${entry}`"
              size="small"
              type="warning"
              effect="plain"
            >
              {{ entry }}
            </el-tag>
          </div>
        </div>
        <div v-if="historySections.length === 0" style="text-align: center; padding: 40px; color: var(--el-text-color-secondary);">
          暂无沟通记录
        </div>
        <div v-else class="history-chat-messages">
          <div v-for="(section, sIdx) in historySections" :key="sIdx" class="history-section">
            <!-- 分段标题 -->
            <div class="history-section-header">
              <el-tag :type="section.type === 'creation' ? 'primary' : 'warning'" size="small">{{ section.label }}</el-tag>
              <span class="history-section-time" v-if="section.created_at">{{ section.created_at.replace('T', ' ').slice(0, 19) }}</span>
            </div>
            <div v-if="section.feedback" class="history-section-feedback">
              <strong>优化需求：</strong>{{ section.feedback }}
            </div>
            <!-- 各轮对话 -->
            <div v-for="(r, idx) in section.rounds" :key="idx" class="history-round">
              <!-- 用户消息 -->
              <div class="chat-msg chat-user">
                <div class="msg-avatar"><el-icon><User /></el-icon></div>
                <div class="msg-bubble">
                  <div class="msg-meta">用户 · 第{{ r.round_number }}轮</div>
                  <div class="msg-text" v-html="renderMarkdown(r.user_message)"></div>
                </div>
              </div>
              <!-- AI 回复 -->
              <div class="chat-msg chat-ai">
                <div class="msg-avatar"><el-icon><MagicStick /></el-icon></div>
                <div class="msg-bubble">
                  <div class="msg-meta">AI · 第{{ r.round_number }}轮</div>
                  <div class="msg-text" v-html="renderMarkdown(r.ai_message)"></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </el-dialog>

    <!-- 优化对话框 -->
    <el-dialog v-model="optimizeDialogVisible" :title="'🔧 优化 Skill: ' + optimizeSkillName" width="640px" :close-on-click-modal="false" destroy-on-close>
      <div v-if="optimizeStep === 'input'">
        <el-alert type="info" :closable="false" style="margin-bottom: 16px">
          <template #title>描述你希望改进的地方，AI 将基于原始需求和当前代码重新生成</template>
        </el-alert>
        <div v-if="optimizeSkillRow && hasGenerationContext(optimizeSkillRow)" class="optimize-strategy-panel">
          <div class="history-strategy-title">当前复用策略</div>
          <div class="history-strategy-tags">
            <el-tag v-if="optimizeSkillRow.generation_context?.category_hint" size="small" type="success" effect="plain">
              {{ optimizeSkillRow.generation_context.category_hint }}
            </el-tag>
            <el-tag v-if="optimizeSkillRow.generation_context?.data_source_hint" size="small" type="warning" effect="plain">
              {{ optimizeSkillRow.generation_context.data_source_hint }}
            </el-tag>
          </div>
          <div v-if="optimizeSkillRow.generation_context?.stock_collections?.length" class="strategy-detail-row">
            <span class="strategy-detail-label">本地集合</span>
            <el-tag
              v-for="entry in optimizeSkillRow.generation_context.stock_collections"
              :key="`optimize-stock-${entry}`"
              size="small"
              type="success"
              effect="plain"
            >
              {{ entry }}
            </el-tag>
          </div>
          <div v-if="optimizeSkillRow.generation_context?.external_sources?.length" class="strategy-detail-row">
            <span class="strategy-detail-label">外部来源</span>
            <el-tag
              v-for="entry in optimizeSkillRow.generation_context.external_sources"
              :key="`optimize-source-${entry}`"
              size="small"
              type="warning"
              effect="plain"
            >
              {{ entry }}
            </el-tag>
          </div>
        </div>
        <el-input
          v-model="optimizeFeedback"
          type="textarea"
          :rows="5"
          placeholder="例如：增加错误重试机制、返回数据增加时间戳字段、优化数据解析逻辑..."
        />
        <div style="text-align: right; margin-top: 12px">
          <el-button @click="optimizeDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleOptimize" :disabled="!optimizeFeedback.trim()">
            🚀 开始优化
          </el-button>
        </div>
      </div>
      <div v-else-if="optimizeStep === 'running'" style="text-align: center; padding: 30px 0">
        <el-icon class="gen-spinner" :size="32"><Loading /></el-icon>
        <h3 style="margin: 12px 0 4px">正在优化 Skill...</h3>
        <p style="color: var(--el-text-color-secondary); font-size: 13px">AI 正在重新生成代码并验证</p>
        <el-progress :percentage="Math.round(optimizeProgress * 100) / 100" :stroke-width="12" style="margin: 20px 40px" />
      </div>
      <div v-else-if="optimizeStep === 'done'">
        <el-result
          :icon="optimizeResult?.success ? 'success' : 'error'"
          :title="optimizeResult?.success ? '✅ 优化成功！' : '❌ 优化失败'"
          :sub-title="optimizeResult?.success
            ? `版本: v${optimizeResult.version} · 耗时 ${optimizeResult.total_time}s · 评分 ${optimizeResult.final_score ?? '-'}/10`
            : optimizeResult?.error || '请修改反馈后重试'"
        >
          <template v-if="optimizeResult?.success && hasRecommendationContext(optimizeResult.generation_context)" #default>
            <div class="optimize-result-strategy-panel">
              <div class="history-strategy-title">本轮优化采用的复用策略</div>
              <div class="history-strategy-tags">
                <el-tag v-if="optimizeResult.generation_context?.category_hint" size="small" type="success" effect="plain">
                  {{ optimizeResult.generation_context.category_hint }}
                </el-tag>
                <el-tag v-if="optimizeResult.generation_context?.data_source_hint" size="small" type="warning" effect="plain">
                  {{ optimizeResult.generation_context.data_source_hint }}
                </el-tag>
              </div>
              <div v-if="optimizeResult.generation_context?.stock_collections?.length" class="strategy-detail-row">
                <span class="strategy-detail-label">本地集合</span>
                <el-tag
                  v-for="entry in optimizeResult.generation_context.stock_collections"
                  :key="`optimize-result-stock-${entry}`"
                  size="small"
                  type="success"
                  effect="plain"
                >
                  {{ entry }}
                </el-tag>
              </div>
              <div v-if="optimizeResult.generation_context?.external_sources?.length" class="strategy-detail-row">
                <span class="strategy-detail-label">外部来源</span>
                <el-tag
                  v-for="entry in optimizeResult.generation_context.external_sources"
                  :key="`optimize-result-source-${entry}`"
                  size="small"
                  type="warning"
                  effect="plain"
                >
                  {{ entry }}
                </el-tag>
              </div>
            </div>
          </template>
          <template #extra>
            <el-button v-if="optimizeResult?.success" type="primary" @click="optimizeDialogVisible = false; loadSkills()">
              完成
            </el-button>
            <el-button v-if="!optimizeResult?.success" @click="optimizeStep = 'input'">返回修改</el-button>
            <el-button @click="optimizeDialogVisible = false">关闭</el-button>
          </template>
        </el-result>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onActivated } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Plus, Refresh, User, MagicStick, Loading, DocumentCopy } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { renderMarkdown as safeMarkdown } from '@/utils/markdown'
import hljs from 'highlight.js/lib/core'
import python from 'highlight.js/lib/languages/python'
import 'highlight.js/styles/github.min.css'
import { skillGenerationApi } from '@/api/skillGeneration'

hljs.registerLanguage('python', python)
import type { ExternalSkill, TestResult, OptimizeResult, SessionDetail, HistorySection } from '@/api/skillGeneration'

// marked 配置已由 @/utils/markdown 统一管理
const renderMarkdown = (content: string): string => {
  if (!content?.trim()) return ''
  try { return safeMarkdown(content) } catch { return content }
}

const formatTime = (t: string): string => {
  if (!t) return '-'
  try { return new Date(t).toLocaleString('zh-CN') } catch { return t }
}

const router = useRouter()
const route = useRoute()

// ==================== 状态 ====================

// Skill 列表
const skills = ref<ExternalSkill[]>([])
const listLoading = ref(false)
const filterStatus = ref('')
const filterSource = ref('')
const highlightedSkillId = ref('')

// 代码查看
const codeDialogVisible = ref(false)
const codeDialogTitle = ref('')
const codeContent = ref('')
const highlightedCode = computed(() => {
  const code = codeContent.value
  if (!code?.trim()) return ''
  try {
    return hljs.highlight(code, { language: 'python' }).value
  } catch {
    return code.replace(/</g, '&lt;').replace(/>/g, '&gt;')
  }
})

// 测试
const testDialogVisible = ref(false)
const testSkillRow = ref<ExternalSkill | null>(null)
const testArgs = ref<Record<string, any>>({})
const testResult = ref<TestResult | null>(null)
const testLoading = ref(false)
const testParamsList = computed(() => {
  const row = testSkillRow.value
  if (!row) return []
  const params = row.parameters || []
  return Array.isArray(params) ? params : []
})

// 沟通记录
const historyDialogVisible = ref(false)
const historyDialogTitle = ref('')
const historyLoading = ref(false)
const historySections = ref<HistorySection[]>([])
const historySkillRow = ref<ExternalSkill | null>(null)

// 优化
const optimizeDialogVisible = ref(false)
const optimizeSkillName = ref('')
const optimizeSkillId = ref('')
const optimizeFeedback = ref('')
const optimizeStep = ref<'input' | 'running' | 'done'>('input')
const optimizeProgress = ref(0)
const optimizeResult = ref<OptimizeResult | null>(null)
const optimizeSkillRow = ref<ExternalSkill | null>(null)

// 草稿
const draftSessions = ref<SessionDetail[]>([])
const draftCategoryFilter = ref('')
const draftSourceFilter = ref('')
const draftHighMatchOnly = ref(false)

const clarityScoreMap: Record<string, number> = {
  high: 3,
  medium: 2,
  low: 1,
}

const getDraftRecommendationWeight = (draft: SessionDetail) => {
  const recommendationCount = (draft.recommendations?.stock_collections?.length || 0)
    + (draft.recommendations?.external_sources?.length || 0)
  const clarityScore = clarityScoreMap[String(draft.clarity_level || '').toLowerCase()] || 0
  const confirmedScore = draft.status === 'confirmed' ? 4 : 0
  return confirmedScore + recommendationCount * 2 + clarityScore
}

const getDraftMatchLabel = (draft: SessionDetail) => {
  const score = getDraftRecommendationWeight(draft)
  if (score >= 10) return '高匹配'
  if (score >= 6) return '中匹配'
  return '低匹配'
}

const getDraftMatchTagType = (draft: SessionDetail): 'success' | 'warning' | 'info' => {
  const score = getDraftRecommendationWeight(draft)
  if (score >= 10) return 'success'
  if (score >= 6) return 'warning'
  return 'info'
}

const getDraftMatchTooltip = (draft: SessionDetail) => {
  const stockCount = draft.recommendations?.stock_collections?.length || 0
  const sourceCount = draft.recommendations?.external_sources?.length || 0
  const clarity = String(draft.clarity_level || '未知')
  const score = getDraftRecommendationWeight(draft)
  return `匹配度 ${score} 分：状态=${draft.status}，清晰度=${clarity}，本地推荐=${stockCount}，外部推荐=${sourceCount}`
}

const getDraftPrimaryActionLabel = (draft: SessionDetail) => {
  if (draft.status === 'confirmed') {
    return isHighMatchDraft(draft) ? '进入确认' : '查看规格'
  }
  return isHighMatchDraft(draft) ? '继续沟通' : '继续完善'
}

const isHighMatchDraft = (draft: SessionDetail) => getDraftRecommendationWeight(draft) >= 10

const availableDraftCategoryHints = computed(() => {
  return Array.from(new Set(
    draftSessions.value
      .map(item => item.recommendations?.category_hint)
      .filter((item): item is string => !!item)
  ))
})

const availableDraftSourceHints = computed(() => {
  return Array.from(new Set(
    draftSessions.value
      .map(item => item.recommendations?.data_source_hint)
      .filter((item): item is string => !!item)
  ))
})

const displayedDraftSessions = computed(() => {
  return [...draftSessions.value]
    .filter(draft => {
      const categoryMatched = !draftCategoryFilter.value
        || draft.recommendations?.category_hint === draftCategoryFilter.value
      const sourceMatched = !draftSourceFilter.value
        || draft.recommendations?.data_source_hint === draftSourceFilter.value
      const matchLevelMatched = !draftHighMatchOnly.value || isHighMatchDraft(draft)
      return categoryMatched && sourceMatched && matchLevelMatched
    })
    .sort((left, right) => {
      const scoreDiff = getDraftRecommendationWeight(right) - getDraftRecommendationWeight(left)
      if (scoreDiff !== 0) return scoreDiff
      return new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime()
    })
})

const hasGenerationContext = (row: ExternalSkill | null | undefined) => {
  return !!(
    row?.generation_context?.category_hint
    || row?.generation_context?.data_source_hint
    || row?.generation_context?.stock_collections?.length
    || row?.generation_context?.external_sources?.length
  )
}

const hasRecommendationContext = (context?: OptimizeResult['generation_context'] | null) => {
  return !!(
    context?.category_hint
    || context?.data_source_hint
    || context?.stock_collections?.length
    || context?.external_sources?.length
  )
}

const getGenerationStrategySummary = (row: ExternalSkill) => {
  const stockCount = row.generation_context?.stock_collections?.length || 0
  const sourceCount = row.generation_context?.external_sources?.length || 0
  const parts: string[] = []
  if (stockCount) parts.push(`${stockCount} 个本地集合`)
  if (sourceCount) parts.push(`${sourceCount} 个外部来源`)
  return parts.join(' · ') || '已记录策略'
}

const getSkillSourceLabel = (row: ExternalSkill) => {
  if (row.origin_source === 'agent_studio_auto_gap_resolution') return 'Agent Studio 自动补齐'
  if (row.source === 'generated') return '手动创建'
  return row.source || '未知来源'
}

const getSkillSourceTagType = (row: ExternalSkill): 'success' | 'warning' | 'info' | 'primary' => {
  if (row.origin_source === 'agent_studio_auto_gap_resolution') return 'success'
  if (row.source === 'generated') return 'primary'
  return 'info'
}

const getSkillUsageTooltip = (row: ExternalSkill) => {
  return (row.used_by_agents || [])
    .map(item => `${item.agent_name || item.spec_id} v${item.version || '-'}（${item.status || '未知'}）`)
    .join('\n')
}

const getSkillRowClassName = ({ row }: { row: ExternalSkill }) => {
  return row.tool_id === highlightedSkillId.value ? 'highlight-skill-row' : ''
}

const applyRouteFilters = () => {
  const source = typeof route.query.source === 'string' ? route.query.source.trim() : ''
  const skillId = typeof route.query.skill_id === 'string' ? route.query.skill_id.trim() : ''
  if (source) filterSource.value = source
  if (skillId) highlightedSkillId.value = skillId
}

// ==================== 方法 ====================

/** 跳转到创建页（新建或恢复草稿） */
const goToCreate = (sessionId?: string) => {
  if (sessionId) {
    router.push({ path: '/workflow/skill-generation/create', query: { sessionId } })
  } else {
    router.push('/workflow/skill-generation/create')
  }
}

const goToCreateWithFocus = (sessionId: string, focus: 'recommendations' | 'confirm') => {
  router.push({ path: '/workflow/skill-generation/create', query: { sessionId, focus } })
}

/** 加载 Skill 列表 */
const loadSkills = async () => {
  listLoading.value = true
  try {
    const res = await skillGenerationApi.listSkills({
      status: filterStatus.value || undefined,
      source: filterSource.value || undefined,
      page: 1,
      page_size: 100,
    })
    skills.value = res.items || []
  } catch (e: any) {
    ElMessage.error('加载列表失败')
  } finally {
    listLoading.value = false
  }
}

/** 查看代码 */
const showCodeDialog = async (row: ExternalSkill) => {
  try {
    const res = await skillGenerationApi.getSkillCode(row.tool_id)
    codeContent.value = res.code
    codeDialogTitle.value = row.display_name || row.tool_id
    codeDialogVisible.value = true
  } catch {
    ElMessage.error('获取代码失败')
  }
}

/** 复制代码 */
const copyCode = async () => {
  if (!codeContent.value) return
  try {
    await navigator.clipboard.writeText(codeContent.value)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败')
  }
}

/** 打开测试对话框 */
const handleTest = (row: ExternalSkill) => {
  testSkillRow.value = row
  testResult.value = null
  testLoading.value = false
  // 初始化参数：从 test_input 或 parameters 的 default
  const params = row.parameters || []
  const defaults = (row as any).test_input || {}
  const init: Record<string, any> = {}
  for (const p of Array.isArray(params) ? params : []) {
    init[p.name] = defaults[p.name] ?? p.default ?? (p.type === 'boolean' || p.type === 'bool' ? false : '')
  }
  testArgs.value = init
  testDialogVisible.value = true
}

/** 执行测试 */
const runTest = async () => {
  if (!testSkillRow.value) return
  testLoading.value = true
  testResult.value = null
  try {
    // 转换类型：number/boolean
    const params = testParamsList.value
    const args: Record<string, any> = {}
    for (const p of params) {
      let v = testArgs.value[p.name]
      if (v === '' || v === undefined) v = p.default
      if (p.type === 'integer' || p.type === 'int') args[p.name] = v != null ? Number(v) : undefined
      else if (p.type === 'float' || p.type === 'number') args[p.name] = v != null ? Number(v) : undefined
      else if (p.type === 'boolean' || p.type === 'bool') args[p.name] = !!v
      else args[p.name] = v
    }
    testResult.value = await skillGenerationApi.testSkill(testSkillRow.value.tool_id, args)
  } catch (e: any) {
    testResult.value = {
      success: false, output: null, stdout: '', stderr: '',
      execution_time: 0, error: e?.message || '测试请求失败',
    }
  } finally {
    testLoading.value = false
  }
}

/** 切换状态 */
const handleStatusToggle = async (row: ExternalSkill, newStatus: string) => {
  try {
    await skillGenerationApi.updateSkillStatus(row.tool_id, newStatus)
    ElMessage.success(`已${newStatus === 'active' ? '启用' : '禁用'}`)
    loadSkills()
  } catch {
    ElMessage.error('操作失败')
  }
}

/** 删除 Skill */
const handleDelete = (row: ExternalSkill) => {
  ElMessageBox.confirm(`确定删除 Skill「${row.display_name || row.tool_id}」吗？此操作不可恢复。`, '确认删除', {
    confirmButtonText: '删除',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(async () => {
    try {
      await skillGenerationApi.deleteSkill(row.tool_id)
      ElMessage.success('已删除')
      loadSkills()
    } catch {
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}

/** 查看沟通记录 */
const showHistoryDialog = async (row: ExternalSkill) => {
  historyDialogTitle.value = row.display_name || row.tool_id
  historySkillRow.value = row
  historySections.value = []
  historyLoading.value = true
  historyDialogVisible.value = true
  try {
    const history = await skillGenerationApi.getSkillHistory(row.tool_id)
    historySections.value = history.sections || []
  } catch {
    ElMessage.error('获取沟通记录失败')
  } finally {
    historyLoading.value = false
  }
}

/** 打开优化对话框 */
const showOptimizeDialog = (row: ExternalSkill) => {
  optimizeSkillId.value = row.tool_id
  optimizeSkillName.value = row.display_name || row.tool_id
  optimizeSkillRow.value = row
  optimizeFeedback.value = ''
  optimizeStep.value = 'input'
  optimizeProgress.value = 0
  optimizeResult.value = null
  optimizeDialogVisible.value = true
}

/** 执行优化 */
const handleOptimize = async () => {
  if (!optimizeFeedback.value.trim()) return
  optimizeStep.value = 'running'
  optimizeProgress.value = 0

  const progressTimer = setInterval(() => {
    if (optimizeProgress.value < 90) {
      optimizeProgress.value = Math.round((optimizeProgress.value + Math.random() * 12) * 100) / 100
    }
  }, 800)

  try {
    const res = await skillGenerationApi.optimizeSkill(optimizeSkillId.value, optimizeFeedback.value)
    clearInterval(progressTimer)
    optimizeProgress.value = 100
    optimizeResult.value = res
    optimizeStep.value = 'done'
  } catch (e: any) {
    clearInterval(progressTimer)
    optimizeResult.value = {
      status: 'failed', skill_id: optimizeSkillId.value,
      optimize_session_id: '', success: false, version: 0,
      total_rounds: 0, total_time: 0, final_score: null,
      generation_context: null,
      error: e?.message || '优化失败',
    }
    optimizeStep.value = 'done'
  }
}

// ==================== 草稿管理 ====================

/** 加载草稿会话 */
const loadDrafts = async () => {
  try {
    const res = await skillGenerationApi.listSessions({ status: 'gathering,confirmed', page_size: 50 })
    draftSessions.value = res.items || []
  } catch {
    // 静默失败，不影响主流程
    draftSessions.value = []
  }
}

const resetDraftFilters = () => {
  draftCategoryFilter.value = ''
  draftSourceFilter.value = ''
  draftHighMatchOnly.value = false
}

/** 获取草稿预览文字 */
const getDraftPreview = (draft: SessionDetail): string => {
  if (draft.rounds && draft.rounds.length > 0) {
    const firstMsg = draft.rounds[0].user_message
    return firstMsg.length > 80 ? firstMsg.slice(0, 80) + '...' : firstMsg
  }
  return '(无内容)'
}

/** 删除草稿 */
const handleDeleteDraft = (draft: SessionDetail) => {
  ElMessageBox.confirm(
    `确定删除这个草稿吗？删除后无法恢复。`,
    '确认删除',
    { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
  ).then(async () => {
    try {
      await skillGenerationApi.deleteSession(draft.session_id)
      ElMessage.success('草稿已删除')
      loadDrafts()
    } catch {
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}

onMounted(() => { applyRouteFilters(); loadSkills(); loadDrafts() })
onActivated(() => { applyRouteFilters(); loadSkills(); loadDrafts() })
</script>


<style lang="scss" scoped>
.skill-generation-page {
  padding: 16px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
  flex-wrap: wrap;
  gap: 12px;

  h1 {
    font-size: 20px;
    margin: 0;
    display: flex;
    align-items: center;
    gap: 6px;
    .header-icon { font-size: 24px; }
  }
  .subtitle { color: var(--el-text-color-secondary); font-size: 13px; margin-left: 8px; }
  .header-left { display: flex; align-items: center; }
  .header-right { display: flex; gap: 8px; }
}

/* ========== 草稿区域 ========== */
.draft-section {
  margin-bottom: 24px;

  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 12px;
    h2 { font-size: 16px; margin: 0; }
  }
}

.draft-section-title {
  display: grid;
  gap: 4px;
}

.draft-section-subtitle {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.draft-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.draft-card-statuses {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.draft-match-tag {
  cursor: help;
}

.draft-filter-summary {
  margin-bottom: 10px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.draft-cards {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.draft-card {
  width: 280px;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  padding: 12px;
  background: var(--el-bg-color);
  transition: box-shadow 0.2s;
  &:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
}

.draft-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  .draft-time { font-size: 11px; color: var(--el-text-color-placeholder); }
}

.draft-card-body {
  margin-bottom: 10px;
  .draft-preview {
    font-size: 13px;
    color: var(--el-text-color-regular);
    margin: 0 0 6px;
    line-height: 1.5;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .draft-meta {
    font-size: 11px;
    color: var(--el-text-color-placeholder);
    span + span { margin-left: 4px; }
  }
}

.draft-recommendations {
  margin-top: 10px;
  display: grid;
  gap: 6px;
}

.draft-recommendation-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.draft-recommendation-label {
  font-size: 11px;
  color: var(--el-text-color-secondary);
}

.draft-card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* ========== Skill 列表 ========== */
.skill-list-section {
  margin-top: 20px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;

  h2 { font-size: 16px; margin: 0; }
}

.section-subtitle {
  display: inline-block;
  margin-top: 4px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.skill-list-header {
  gap: 12px;
  flex-wrap: wrap;
}

.skill-filters {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.skill-name-cell {
  display: flex;
  align-items: center;
}

.source-cell,
.usage-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.source-agent,
.source-gap,
.usage-more {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.usage-more {
  cursor: default;
}

:deep(.highlight-skill-row) {
  --el-table-tr-bg-color: #f0f9ff;
  box-shadow: inset 4px 0 0 var(--el-color-primary);
}

.strategy-cell {
  display: grid;
  gap: 6px;
}

.strategy-head {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.strategy-trigger {
  justify-content: flex-start;
  padding: 0;
  height: auto;
  color: var(--el-text-color-regular);
}

.strategy-empty {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}

.strategy-popover {
  display: grid;
  gap: 10px;
}

.strategy-popover-row,
.strategy-detail-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.strategy-popover-label,
.strategy-detail-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  min-width: 56px;
}

/* ========== 沟通记录（复用 chat-msg 样式） ========== */
.chat-msg {
  display: flex;
  gap: 10px;
  margin-bottom: 14px;
  &.chat-user { flex-direction: row-reverse; }
  .msg-avatar {
    width: 32px; height: 32px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center; flex-shrink: 0;
    background: var(--el-color-primary-light-8); color: var(--el-color-primary); font-size: 16px;
  }
  &.chat-user .msg-avatar {
    background: var(--el-color-success-light-8); color: var(--el-color-success);
  }
  .msg-bubble {
    max-width: 80%; padding: 10px 14px; border-radius: 12px;
    background: var(--el-bg-color); border: 1px solid var(--el-border-color-lighter); line-height: 1.6;
  }
  &.chat-user .msg-bubble {
    background: var(--el-color-primary-light-9); border-color: var(--el-color-primary-light-7);
  }
}
.msg-text { :deep(p) { margin: 0 0 4px; } :deep(ul), :deep(ol) { margin: 4px 0; padding-left: 20px; } }

.history-chat-messages {
  max-height: 60vh;
  overflow-y: auto;
  padding: 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-lighter);
}

.history-strategy-panel,
.optimize-strategy-panel {
  margin-bottom: 14px;
  padding: 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-lighter);
  display: grid;
  gap: 10px;
}

.optimize-result-strategy-panel {
  margin-top: 16px;
  padding: 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-lighter);
  display: grid;
  gap: 10px;
  text-align: left;
}

.history-strategy-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-regular);
}

.history-strategy-tags {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.history-section {
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 2px solid var(--el-border-color);
  &:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
}

.history-section-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.history-section-time {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}

.history-section-feedback {
  background: var(--el-color-warning-light-9);
  border-left: 3px solid var(--el-color-warning);
  padding: 8px 12px;
  margin-bottom: 12px;
  border-radius: 4px;
  font-size: 13px;
  color: var(--el-text-color-regular);
}

.history-round {
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px dashed var(--el-border-color-lighter);
  &:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
}

.msg-meta {
  font-size: 11px;
  color: var(--el-text-color-placeholder);
  margin-bottom: 4px;
}

/* ========== 测试对话框 ========== */
.test-params-section {
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.test-params-header {
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 12px;
  color: var(--el-text-color-regular);
}
.test-params-empty {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin: 0 0 12px;
}
.test-actions {
  margin-top: 12px;
}
.test-result-section {
  min-height: 80px;
}
.test-result-content {
  padding: 8px 0;
}

/* ========== 代码查看 ========== */
.code-viewer-header {
  margin-bottom: 8px;
}
.code-viewer {
  margin: 0;
  padding: 12px 16px;
  background: #f6f8fa;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.5;
  overflow: auto;
  max-height: 60vh;
  white-space: pre;
}
.code-viewer code {
  padding: 0;
  background: none;
}
</style>