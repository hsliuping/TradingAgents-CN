<template>
  <div class="skill-create-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <el-button text @click="goBack">
          <el-icon><ArrowLeft /></el-icon>
          返回列表
        </el-button>
        <span class="header-divider">|</span>
        <h1>🛠️ 创建新 Skill</h1>
      </div>
      <div class="header-right">
        <el-button v-if="wizardStep < 2 && sessionId" text size="small" @click="goBack">
          保存草稿
        </el-button>
      </div>
    </div>

    <!-- 步骤条 -->
    <div class="steps-bar">
      <el-steps :active="wizardStep" finish-status="success" align-center>
        <el-step title="需求沟通" />
        <el-step title="规格确认" />
        <el-step title="代码生成" />
        <el-step title="完成" />
      </el-steps>
    </div>

    <!-- 主内容区：充分利用屏幕 -->
    <div class="main-content">
      <!-- 步骤 0: 需求沟通 -->
      <div v-if="wizardStep === 0" class="wizard-chat">
        <div v-if="handoffContext" class="handoff-card">
          <div class="handoff-title">来自上游工坊的交接</div>
          <div class="handoff-text">
            <span v-if="handoffContext.source === 'agent_workshop'">当前不是从零新建 Skill，而是在承接 Agent 工坊识别出的执行能力缺口。</span>
            <span v-else>当前会话来自上游流程交接。</span>
          </div>
          <div class="handoff-meta">
            <span v-if="handoffContext.source_name">上游对象：{{ handoffContext.source_name }}</span>
            <span v-if="handoffContext.target_capability">目标能力：{{ handoffContext.target_capability }}</span>
          </div>
          <div v-if="handoffContext.handoff_intent" class="handoff-note">{{ handoffContext.handoff_intent }}</div>
        </div>
        <div ref="chatContainer" class="chat-messages">
          <!-- 首次进入时的引导语 -->
          <div v-if="chatMessages.length === 0 && !chatLoading" class="requirement-guide">
            <div class="guide-header">
              <el-icon class="guide-icon"><MagicStick /></el-icon>
              <h3>如何描述你的需求？</h3>
              <p class="guide-desc">用自然语言描述你需要的工具，AI 会通过 1～3 轮对话帮你完善需求，然后自动生成代码并验证。</p>
            </div>
            <div class="guide-tips">
              <div class="tip-item">
                <span class="tip-label">💡 建议包含：</span>
                <ul>
                  <li><strong>数据来源</strong>：如东方财富、AKShare、财联社等</li>
                  <li><strong>输入参数</strong>：如股票代码、日期范围、条数限制</li>
                  <li><strong>期望输出</strong>：如新闻列表、行情数据、JSON 格式</li>
                </ul>
              </div>
              <div class="tip-item">
                <span class="tip-label">📝 示例：</span>
                <ul class="guide-examples">
                  <li>「用 AKShare 获取北向资金数据，按日期查询，返回 JSON」</li>
                  <li>「获取东方财富某只股票的最新新闻，需要标题、链接、时间」</li>
                  <li>「从财联社获取某股票的实时快讯，最多 20 条」</li>
                </ul>
              </div>
            </div>
            <p class="guide-footer">在下方输入框描述你的需求，按 <kbd>Ctrl+Enter</kbd> 或点击发送即可开始</p>
          </div>
          <div v-for="(msg, idx) in chatMessages" :key="idx"
               :class="['chat-msg', msg.role === 'user' ? 'chat-user' : 'chat-ai']">
            <div class="msg-avatar">
              <el-icon v-if="msg.role === 'user'"><User /></el-icon>
              <el-icon v-else><MagicStick /></el-icon>
            </div>
            <div class="msg-bubble">
              <div class="msg-text" v-html="renderMarkdown(msg.content)"></div>
            </div>
          </div>
          <div v-if="chatLoading" class="chat-msg chat-ai">
            <div class="msg-avatar"><el-icon><MagicStick /></el-icon></div>
            <div class="msg-bubble thinking">
              <span class="dot-animation">AI 正在分析<span>.</span><span>.</span><span>.</span></span>
            </div>
          </div>
        </div>

        <div v-if="boundaryWarning" class="boundary-alert boundary-collapsible">
          <div class="boundary-header" @click="boundaryExpanded = !boundaryExpanded">
            <el-icon class="boundary-icon"><WarningFilled /></el-icon>
            <span>复杂度提醒 ({{ boundaryCheck?.complexity_score }}/5)</span>
            <el-icon class="boundary-chevron" :class="{ expanded: boundaryExpanded }"><ArrowDown /></el-icon>
          </div>
          <div v-show="boundaryExpanded" class="boundary-content">
            <div v-for="c in boundaryCheck?.concerns" :key="c">• {{ c }}</div>
            <div v-if="boundaryCheck?.decomposition_suggestions?.length" style="margin-top: 6px">
              <strong>建议拆分为：</strong>
              <div v-for="s in boundaryCheck?.decomposition_suggestions" :key="s">→ {{ s }}</div>
            </div>
          </div>
        </div>

        <div class="chat-input-area">
          <el-input
            v-model="userInput"
            type="textarea"
            :rows="3"
            :autosize="{ minRows: 3, maxRows: 8 }"
            :placeholder="chatMessages.length === 0 ? '描述你需要的工具，例如：我需要获取东方财富个股新闻...' : (canConfirm ? '可输入方案选择（如：我选择方案C）或补充说明，确认时一并提交' : '回复 AI 的问题...')"
            :disabled="chatLoading"
            @keydown.enter.ctrl="handleChatSend"
          />
          <div class="chat-actions">
            <span class="tip">Ctrl+Enter 发送 · 第 {{ currentRound }}/{{ expectedRounds }} 轮</span>
            <div>
              <el-button v-if="canConfirm" type="success" @click="handleViewSpec" :loading="chatLoading">
                📄 查看规格
              </el-button>
              <el-button type="primary" @click="handleChatSend" :loading="chatLoading" :disabled="!userInput.trim()">
                发送
              </el-button>
            </div>
          </div>
        </div>
      </div>

      <!-- 步骤 1: 规格确认 -->
      <div v-if="wizardStep === 1" class="wizard-spec-confirm">
        <div class="spec-confirm-card">
          <h3>📄 工具规格确认</h3>
          <div v-if="handoffContext" class="handoff-inline-note">
            当前规格来自上游交接：先判断复用已有能力，再决定是否新增最小实现单元。
          </div>
          <el-descriptions v-if="specPreview" :column="1" border size="small">
            <el-descriptions-item label="工具 ID">{{ specPreview.tool_id }}</el-descriptions-item>
            <el-descriptions-item label="名称">{{ specPreview.display_name }}</el-descriptions-item>
            <el-descriptions-item label="分类">{{ specPreview.category }}</el-descriptions-item>
            <el-descriptions-item label="数据源">{{ specPreview.data_source }}</el-descriptions-item>
            <el-descriptions-item label="描述">{{ specPreview.description }}</el-descriptions-item>
          </el-descriptions>
          <div v-if="specPreview?.parameters?.length" class="spec-params-section">
            <h4>输入参数</h4>
            <el-table :data="specPreview.parameters" size="small" border stripe>
              <el-table-column prop="name" label="参数" width="120" />
              <el-table-column prop="type" label="类型" width="90" />
              <el-table-column prop="required" label="必填" width="70" align="center">
                <template #default="{ row }">{{ row.required ? '是' : '否' }}</template>
              </el-table-column>
              <el-table-column prop="description" label="说明" />
            </el-table>
          </div>
          <div v-if="boundaryWarning" class="spec-boundary-warn">
            <el-alert type="warning" :closable="false" show-icon>
              复杂度 {{ boundaryCheck?.complexity_score }}/5，在 Skill 范围内
            </el-alert>
          </div>
          <div
            v-if="backendRecommendations && (backendRecommendations.stock_collections?.length || backendRecommendations.external_sources?.length)"
            ref="recommendationCardRef"
            :class="['spec-recommendation-card', { 'spec-recommendation-card-highlight': highlightRecommendationCard } ]"
          >
            <div class="spec-catalog-header">
              <div>
                <h4>系统建议</h4>
                <p>这份建议由后端统一选择器生成，会和需求分析、规格确认、代码生成共用同一套命中逻辑。</p>
              </div>
            </div>
            <div class="recommendation-grid">
              <div class="recommendation-block">
                <div class="recommendation-label">推荐分类 / 主来源</div>
                <div class="recommendation-value">
                  {{ backendRecommendations.category_hint || '-' }}
                  <span v-if="backendRecommendations.data_source_hint"> · {{ backendRecommendations.data_source_hint }}</span>
                </div>
              </div>
              <div class="recommendation-block">
                <div class="recommendation-label">推荐复用本地集合</div>
                <div class="tag-wrap" v-if="backendRecommendations.stock_collections?.length">
                  <el-tag v-for="entry in backendRecommendations.stock_collections" :key="`rec-stock-${entry}`" class="tag-item" type="success" effect="plain">{{ entry }}</el-tag>
                </div>
                <div v-else class="recommendation-empty">当前没有明显命中的本地集合</div>
              </div>
              <div class="recommendation-block">
                <div class="recommendation-label">推荐外部来源</div>
                <div class="tag-wrap" v-if="backendRecommendations.external_sources?.length">
                  <el-tag v-for="entry in backendRecommendations.external_sources" :key="`rec-source-${entry}`" class="tag-item" type="warning" effect="plain">{{ entry }}</el-tag>
                </div>
                <div v-else class="recommendation-empty">当前优先本地即可，外部来源不是必需</div>
              </div>
              <div v-if="matchedStockCollections.length || matchedExternalSources.length" class="recommendation-block">
                <div class="recommendation-label">快速定位</div>
                <div class="recommendation-actions">
                  <el-button v-if="matchedStockCollections.length" size="small" type="success" plain @click="focusFirstMatchedStockCard">定位本地命中</el-button>
                  <el-button v-if="matchedExternalSources.length" size="small" type="warning" plain @click="focusFirstMatchedExternalCard">定位外部命中</el-button>
                </div>
              </div>
            </div>
          </div>
          <div class="spec-catalog-card">
            <div class="spec-catalog-header">
              <div>
                <h4>本地股票数据目录</h4>
                <p>这里展示当前 Skill 生成器参考的股票核心集合和关键字段，确认规格时可以直接核对是否优先复用数据库现有数据。</p>
              </div>
              <el-button text @click="loadStockDataCatalog" :loading="stockCatalogLoading">刷新目录</el-button>
            </div>
            <div v-if="stockCatalogDoc" class="catalog-summary">
              当前已整理 {{ stockCatalogCollections.length }} 个核心集合，建议优先复用封装函数，不要直接臆造字段名。
            </div>
            <div v-if="matchedStockCollections.length" class="catalog-match-summary">
              本次规格命中集合：{{ matchedStockCollections.map(item => item.collection).join('、') }}
            </div>
            <el-collapse v-model="stockCatalogExpanded">
              <el-collapse-item name="stock-data-catalog" title="查看集合与字段目录">
                <div v-if="stockCatalogCollections.length" class="catalog-collection-list">
                  <div
                    v-for="item in stockCatalogCollections"
                    :key="item.collection"
                    :ref="(el) => setStockCardRef(item.collection, el)"
                    :class="['catalog-collection-card', { 'catalog-collection-card-recommended': isStockCollectionMatched(item) } ]"
                  >
                    <div class="catalog-collection-topbar">
                      <div>
                        <div class="catalog-collection-title">{{ item.collection }}</div>
                        <div v-if="isStockCollectionMatched(item)" class="catalog-match-label">本次命中</div>
                      </div>
                      <div class="catalog-collection-actions">
                        <el-button size="small" text @click="insertCatalogIntoRequirement(item)">插入到需求</el-button>
                        <el-button size="small" text @click="copyCatalogCollectionName(item.collection)">复制集合名</el-button>
                        <el-button size="small" text @click="copyCatalogQueryKeys(item)">复制查询键</el-button>
                        <el-button size="small" text @click="copyCatalogPreferredAccess(item)">复制访问函数</el-button>
                        <el-button size="small" text @click="copyCatalogFieldNames(item)">复制字段名</el-button>
                        <el-button size="small" text @click="copyCatalogFieldDescriptions(item)">复制字段说明</el-button>
                      </div>
                    </div>
                    <div class="catalog-collection-purpose">{{ item.purpose }}</div>
                    <div class="tag-wrap" v-if="item.preferred_access?.length">
                      <el-tag v-for="entry in item.preferred_access" :key="`${item.collection}-access-${entry}`" class="tag-item" type="success" effect="plain">{{ entry }}</el-tag>
                    </div>
                    <div class="tag-wrap" v-if="item.query_keys?.length" style="margin-top: 8px;">
                      <el-tag v-for="entry in item.query_keys" :key="`${item.collection}-query-${entry}`" class="tag-item" type="info" effect="plain">{{ entry }}</el-tag>
                    </div>
                    <el-table :data="item.fields" size="small" border stripe class="catalog-field-table">
                      <el-table-column prop="name" label="字段" width="180" />
                      <el-table-column prop="type" label="类型" width="140" />
                      <el-table-column prop="description" label="说明" min-width="320" />
                    </el-table>
                    <div v-if="item.notes?.length" class="catalog-notes">
                      <div v-for="entry in item.notes" :key="`${item.collection}-note-${entry}`" class="catalog-note-item">{{ entry }}</div>
                    </div>
                  </div>
                </div>
                <el-empty v-else description="当前还没有加载到股票数据目录" />
              </el-collapse-item>
            </el-collapse>
          </div>
          <div class="spec-catalog-card">
            <div class="spec-catalog-header">
              <div>
                <h4>外部接口与数据源目录</h4>
                <p>这里只展示当前系统优先支持的外部来源。需要在线补数时，应先选最匹配的一两个来源，不要把所有 API 一起塞进需求。</p>
              </div>
              <el-button text @click="loadExternalDataSourceCatalog" :loading="externalSourceCatalogLoading">刷新目录</el-button>
            </div>
            <div v-if="externalSourceCatalogDoc" class="catalog-summary">
              当前已整理 {{ externalSourceCatalogSources.length }} 个核心外部来源，建议按需求精确选用，并保留本地优先、外部降级的策略。
            </div>
            <div v-if="matchedExternalSources.length" class="catalog-match-summary">
              本次规格命中来源：{{ matchedExternalSources.map(item => item.display_name).join('、') }}
            </div>
            <el-collapse v-model="externalSourceCatalogExpanded">
              <el-collapse-item name="external-data-source-catalog" title="查看外部来源目录">
                <div v-if="externalSourceCatalogSources.length" class="catalog-collection-list">
                  <div
                    v-for="item in externalSourceCatalogSources"
                    :key="item.source_id"
                    :ref="(el) => setExternalSourceCardRef(item.source_id, el)"
                    :class="['catalog-collection-card', { 'catalog-collection-card-recommended': isExternalSourceMatched(item) } ]"
                  >
                    <div class="catalog-collection-topbar">
                      <div>
                        <div class="catalog-collection-title">{{ item.display_name }}</div>
                        <div class="catalog-collection-purpose">{{ item.source_id }} · {{ item.source_type }}</div>
                        <div v-if="isExternalSourceMatched(item)" class="catalog-match-label">本次命中</div>
                      </div>
                      <div class="catalog-collection-actions">
                        <el-button size="small" text @click="insertExternalSourceIntoRequirement(item)">插入到需求</el-button>
                        <el-button size="small" text @click="copyExternalSourceName(item)">复制来源名</el-button>
                        <el-button size="small" text @click="copyExternalSourceInterfaces(item)">复制接口</el-button>
                        <el-button size="small" text @click="copyExternalSourcePreferredFor(item)">复制适用场景</el-button>
                        <el-button size="small" text @click="copyExternalSourceConstraints(item)">复制约束</el-button>
                      </div>
                    </div>
                    <div class="tag-wrap" v-if="item.markets?.length" style="margin-top: 10px;">
                      <el-tag v-for="entry in item.markets" :key="`${item.source_id}-market-${entry}`" class="tag-item" type="warning" effect="plain">{{ entry }}</el-tag>
                    </div>
                    <div class="tag-wrap" v-if="item.categories?.length" style="margin-top: 8px;">
                      <el-tag v-for="entry in item.categories" :key="`${item.source_id}-category-${entry}`" class="tag-item" type="info" effect="plain">{{ entry }}</el-tag>
                    </div>
                    <div v-if="item.preferred_for?.length" class="catalog-notes">
                      <div v-for="entry in item.preferred_for" :key="`${item.source_id}-preferred-${entry}`" class="catalog-note-item">推荐场景：{{ entry }}</div>
                    </div>
                    <div v-if="item.interfaces?.length" class="catalog-notes">
                      <div v-for="entry in item.interfaces" :key="`${item.source_id}-interface-${entry}`" class="catalog-note-item">推荐接口：{{ entry }}</div>
                    </div>
                    <div v-if="item.constraints?.length" class="catalog-notes">
                      <div v-for="entry in item.constraints" :key="`${item.source_id}-constraint-${entry}`" class="catalog-note-item">约束：{{ entry }}</div>
                    </div>
                    <div v-if="item.notes?.length" class="catalog-notes">
                      <div v-for="entry in item.notes" :key="`${item.source_id}-note-${entry}`" class="catalog-note-item">说明：{{ entry }}</div>
                    </div>
                  </div>
                </div>
                <el-empty v-else description="当前还没有加载到外部接口与数据源目录" />
              </el-collapse-item>
            </el-collapse>
          </div>
          <div v-if="specPreview" class="spec-preflight-card">
            <div class="spec-catalog-header">
              <div>
                <h4>生成前检查</h4>
                <p>当前生成会优先按下面的复用策略执行。确认无误后再进入代码生成与验证流程。</p>
              </div>
            </div>
            <div class="preflight-grid">
              <div class="recommendation-block">
                <div class="recommendation-label">优先复用本地集合</div>
                <div v-if="preflightLocalCollections.length" class="tag-wrap">
                  <el-tag v-for="entry in preflightLocalCollections" :key="`preflight-local-${entry}`" class="tag-item" type="success" effect="plain">{{ entry }}</el-tag>
                </div>
                <div v-else class="recommendation-empty">当前没有明确命中的本地集合，生成时会更多依赖需求描述和目录上下文。</div>
              </div>
              <div class="recommendation-block">
                <div class="recommendation-label">候选外部来源</div>
                <div v-if="preflightExternalSources.length" class="tag-wrap">
                  <el-tag v-for="entry in preflightExternalSources" :key="`preflight-source-${entry}`" class="tag-item" type="warning" effect="plain">{{ entry }}</el-tag>
                </div>
                <div v-else class="recommendation-empty">当前优先本地数据即可，外部来源不是必须项。</div>
              </div>
              <div class="recommendation-block">
                <div class="recommendation-label">生成提醒</div>
                <div class="preflight-notes">
                  <div v-for="entry in preflightNotes" :key="entry" class="catalog-note-item">{{ entry }}</div>
                </div>
              </div>
            </div>
          </div>
          <div ref="confirmActionsRef" :class="['spec-confirm-actions', { 'spec-confirm-actions-highlight': highlightConfirmActions } ]">
            <el-button @click="wizardStep = 0">✏️ 返回修改</el-button>
            <el-button type="primary" @click="handleConfirmAndGenerate" :loading="specConfirmLoading">
              ✅ 确认并生成
            </el-button>
          </div>
        </div>
      </div>

      <!-- 步骤 2: 生成进度 -->
      <div v-if="wizardStep === 2" class="wizard-generating">
        <div class="gen-status">
          <el-icon class="gen-spinner" :size="40"><Loading /></el-icon>
          <h3>正在生成 Skill...</h3>
          <p class="gen-desc">{{ pipelineMessage || 'AI 正在生成代码、验证语法、沙箱执行和质量评估' }}</p>
        </div>
        <el-progress :percentage="Math.round(genProgress * 100) / 100" :stroke-width="14" style="margin: 24px 0; max-width: 500px; margin-left: auto; margin-right: auto;" />
        <div class="gen-steps">
          <div v-for="(s, i) in genSteps" :key="i" :class="['gen-step', s.status]">
            <el-icon v-if="s.status === 'done'"><CircleCheck /></el-icon>
            <el-icon v-else-if="s.status === 'running'" class="is-loading"><Loading /></el-icon>
            <el-icon v-else><MoreFilled /></el-icon>
            <span>{{ s.label }}</span>
          </div>
        </div>
      </div>

      <!-- 步骤 3: 完成 -->
      <div v-if="wizardStep === 3" class="wizard-done">
        <el-result
          :icon="genResult?.success ? 'success' : 'error'"
          :title="genResult?.success ? '🎉 Skill 创建成功！' : '❌ 生成失败'"
          :sub-title="genResult?.success
            ? `工具 ID: ${genResult.skill_id} · 耗时 ${genResult.total_time}s · 评分 ${genResult.final_score ?? '-'}/10`
            : genResult?.error || '请根据下面的失败信息补充修正意见，然后重新生成'"
        >
          <template #extra>
            <el-button v-if="genResult?.success" type="primary" @click="goBack">
              查看 Skill 列表
            </el-button>
            <el-button v-else @click="wizardStep = 1">返回规格确认</el-button>
            <el-button @click="goBack">返回列表</el-button>
          </template>
        </el-result>
        <div v-if="!genResult?.success" class="repair-card">
          <div class="spec-catalog-header">
            <div>
              <h4>先让 AI 说明修正计划，再决定是否重跑</h4>
              <p>这里会自动带上静态验证、沙箱执行、评估阶段的失败信息。你先补充你认为不对的地方，AI 会先回复它理解到的问题和修正计划；确认没偏后，再按这份计划继续生成。</p>
            </div>
          </div>
          <div v-if="pipelineFailureSummary.length" class="repair-summary-list">
            <div v-for="entry in pipelineFailureSummary" :key="entry" class="catalog-note-item">{{ entry }}</div>
          </div>
          <el-input
            v-model="repairFeedback"
            type="textarea"
            :rows="4"
            resize="vertical"
            placeholder="例如：当前 price 被默默置为 0 还继续估值，这是错的；请优先用本地实时行情取价格，拿不到有效现价就直接返回 error。"
          />
          <div v-if="repairPlan" class="repair-plan-card">
            <div class="repair-plan-header">
              <h5>AI 理解的问题与修正计划</h5>
              <span v-if="repairPlanStale" class="repair-plan-stale">你已修改修正意见，请重新生成计划</span>
            </div>
            <div class="markdown-body repair-plan-markdown" v-html="renderMarkdown(repairPlan)" />
          </div>
          <div class="repair-actions">
            <el-button @click="wizardStep = 1">回到规格确认</el-button>
            <el-button :loading="repairPlanning" :disabled="!repairFeedback.trim() || !sessionId" @click="handlePreviewRepairPlan">
              {{ repairPlan ? '重新生成修正计划' : '让 AI 先给修正计划' }}
            </el-button>
            <el-button type="primary" :loading="repairing" :disabled="!canConfirmRepair" @click="handleRepairAndRegenerate">
              确认按这个计划重跑
            </el-button>
          </div>
        </div>
        <div v-if="genResult?.success" class="test-run-card">
          <div class="spec-catalog-header">
            <div>
              <h4>立即测试这个 Skill</h4>
              <p>这里会直接调用测试接口运行刚生成的 Skill，用当前规格里的默认 test_input 验证是否能执行、是否真的拿到数据。</p>
            </div>
          </div>
          <div v-if="generatedTestParams.length" class="test-run-form">
            <el-form label-width="120px" size="default">
              <el-form-item v-for="p in generatedTestParams" :key="p.name" :label="p.name" :required="p.required">
                <el-input
                  v-if="p.type === 'string' || !p.type"
                  v-model="generatedTestArgs[p.name]"
                  :placeholder="p.description || `请输入 ${p.name}`"
                  clearable
                />
                <el-input-number
                  v-else-if="p.type === 'integer' || p.type === 'int'"
                  v-model="generatedTestArgs[p.name]"
                  :placeholder="p.description"
                  controls-position="right"
                  style="width: 100%"
                />
                <el-input-number
                  v-else-if="p.type === 'float' || p.type === 'number'"
                  v-model="generatedTestArgs[p.name]"
                  :placeholder="p.description"
                  :precision="2"
                  controls-position="right"
                  style="width: 100%"
                />
                <el-switch v-else-if="p.type === 'boolean' || p.type === 'bool'" v-model="generatedTestArgs[p.name]" />
                <el-input
                  v-else
                  v-model="generatedTestArgs[p.name]"
                  :placeholder="p.description || `请输入 ${p.name}`"
                  clearable
                />
              </el-form-item>
            </el-form>
          </div>
          <div v-else class="test-params-empty">当前规格没有显式参数，将直接使用默认测试输入执行。</div>
          <div class="test-run-actions">
            <el-button @click="resetGeneratedTestArgs">恢复默认参数</el-button>
            <el-button type="primary" :loading="generatedTestLoading" :disabled="!generatedSkillId" @click="runGeneratedSkillTest">
              运行测试
            </el-button>
          </div>
          <div v-if="generatedTestResult" class="test-run-result">
            <div class="test-run-summary">
              <el-tag :type="generatedTestResult.success ? 'success' : 'danger'">{{ generatedTestResult.success ? '执行成功' : '执行失败' }}</el-tag>
              <el-tag :type="generatedTestDataState.type" effect="plain">{{ generatedTestDataState.label }}</el-tag>
            </div>
            <el-descriptions :column="1" border size="small">
              <el-descriptions-item label="执行时长">{{ generatedTestResult.execution_time }}s</el-descriptions-item>
              <el-descriptions-item label="结果说明">{{ generatedTestDataState.description }}</el-descriptions-item>
              <el-descriptions-item v-if="generatedTestResult.error" label="错误">
                <span class="test-run-error">{{ generatedTestResult.error }}</span>
              </el-descriptions-item>
              <el-descriptions-item label="输出">
                <pre class="test-run-pre">{{ generatedTestResultText }}</pre>
              </el-descriptions-item>
              <el-descriptions-item v-if="generatedTestResult.stdout" label="stdout">
                <pre class="test-run-pre">{{ generatedTestResult.stdout }}</pre>
              </el-descriptions-item>
              <el-descriptions-item v-if="generatedTestResult.stderr" label="stderr">
                <pre class="test-run-pre">{{ generatedTestResult.stderr }}</pre>
              </el-descriptions-item>
            </el-descriptions>
          </div>
        </div>
        <div v-if="genResult?.success && (preflightLocalCollections.length || preflightExternalSources.length)" class="done-context-card">
          <div class="spec-catalog-header">
            <div>
              <h4>本次生成采用的复用策略</h4>
              <p>以下内容来自生成前统一选择器，用于说明本次代码生成优先参考了哪些本地集合和外部来源。</p>
            </div>
          </div>
          <div class="preflight-grid">
            <div class="recommendation-block">
              <div class="recommendation-label">本地集合</div>
              <div v-if="preflightLocalCollections.length" class="tag-wrap">
                <el-tag v-for="entry in preflightLocalCollections" :key="`done-local-${entry}`" class="tag-item" type="success" effect="plain">{{ entry }}</el-tag>
              </div>
              <div v-else class="recommendation-empty">本次没有明确锁定本地集合。</div>
            </div>
            <div class="recommendation-block">
              <div class="recommendation-label">外部来源</div>
              <div v-if="preflightExternalSources.length" class="tag-wrap">
                <el-tag v-for="entry in preflightExternalSources" :key="`done-source-${entry}`" class="tag-item" type="warning" effect="plain">{{ entry }}</el-tag>
              </div>
              <div v-else class="recommendation-empty">本次策略偏向本地优先，外部来源非必需。</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted, computed, watch, type ComponentPublicInstance } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, ArrowDown, User, MagicStick, Loading, CircleCheck, MoreFilled, WarningFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { marked } from 'marked'
import { skillGenerationApi } from '@/api/skillGeneration'
import type {
  BoundaryCheck,
  ConfirmResult,
  ExternalDataSourceCatalogItem,
  PipelineResultDetail,
  SkillHandoffContext,
  SkillGenerationRecommendations,
  StockDataCatalogCollection,
  TestResult,
} from '@/api/skillGeneration'

marked.setOptions({ breaks: true, gfm: true })

const renderMarkdown = (content: string): string => {
  if (!content?.trim()) return ''
  try { return marked.parse(content) as string } catch { return content }
}

const route = useRoute()
const router = useRouter()

// ==================== 状态 ====================

const wizardStep = ref(0)

interface ChatMsg { role: 'user' | 'ai'; content: string }
const chatMessages = ref<ChatMsg[]>([])
const chatLoading = ref(false)
const userInput = ref('')
const chatContainer = ref<HTMLElement | null>(null)
const recommendationCardRef = ref<HTMLElement | null>(null)
const confirmActionsRef = ref<HTMLElement | null>(null)
const stockCardRefs = ref<Record<string, HTMLElement | null>>({})
const externalSourceCardRefs = ref<Record<string, HTMLElement | null>>({})
const sessionId = ref('')
const currentRound = ref(0)
const expectedRounds = ref(3)
const boundaryCheck = ref<BoundaryCheck | null>(null)
const boundaryExpanded = ref(false)
const boundaryWarning = computed(() => boundaryCheck.value && !boundaryCheck.value.within_boundary)

watch(boundaryCheck, () => { boundaryExpanded.value = false })
const canConfirm = computed(() => chatMessages.value.length >= 2)

const specPreview = ref<Record<string, any> | null>(null)
const specConfirmLoading = ref(false)
const pipelineMessage = ref('')
const stockCatalogLoading = ref(false)
const stockCatalogDoc = ref('')
const stockCatalogCollections = ref<StockDataCatalogCollection[]>([])
const stockCatalogExpanded = ref<string[]>(['stock-data-catalog'])
const externalSourceCatalogLoading = ref(false)
const externalSourceCatalogDoc = ref('')
const externalSourceCatalogSources = ref<ExternalDataSourceCatalogItem[]>([])
const externalSourceCatalogExpanded = ref<string[]>(['external-data-source-catalog'])
const backendRecommendations = ref<SkillGenerationRecommendations | null>(null)
const handoffContext = ref<SkillHandoffContext | null>(null)
const highlightRecommendationCard = ref(false)
const highlightConfirmActions = ref(false)

const getRouteHandoffContext = (): SkillHandoffContext | null => {
  const sourceSpecId = typeof route.query.from_agent_workshop === 'string' ? route.query.from_agent_workshop.trim() : ''
  const targetCapability = typeof route.query.target_capability === 'string'
    ? route.query.target_capability.trim()
    : (typeof route.query.skill_name === 'string' ? route.query.skill_name.trim() : '')
  const sourceName = typeof route.query.source_name === 'string' ? route.query.source_name.trim() : ''
  const handoffIntent = typeof route.query.handoff_intent === 'string' ? route.query.handoff_intent.trim() : ''
  if (!sourceSpecId && !targetCapability) return null

  return {
    source: sourceSpecId ? 'agent_workshop' : '',
    source_spec_id: sourceSpecId,
    source_name: sourceName,
    target_capability: targetCapability,
    handoff_intent: handoffIntent || '当前是从 Agent 创建流程里补能力缺口，不是普通 Skill 脑暴。必须优先保留上游目标能力；若需要拆成 Skill，只能定义成该 Agent 能力里的最小确定性子能力。',
  }
}

const preflightLocalCollections = computed(() => backendRecommendations.value?.stock_collections || [])
const preflightExternalSources = computed(() => backendRecommendations.value?.external_sources || [])
const preflightNotes = computed(() => {
  const notes: string[] = []
  if (preflightLocalCollections.value.length) {
    notes.push(`优先复用本地集合：${preflightLocalCollections.value.join('、')}`)
  } else {
    notes.push('当前没有明确命中的本地集合，生成器会根据需求描述和目录信息决定是否直连外部来源。')
  }

  if (preflightExternalSources.value.length) {
    notes.push(`如本地数据不足，将优先考虑这些外部来源：${preflightExternalSources.value.join('、')}`)
  } else {
    notes.push('当前推荐策略偏向本地优先，外部来源更多作为可选补充。')
  }

  notes.push('本次仍会经过代码生成、静态校验、沙箱执行和质量评估，不会跳过验证。')
  return notes
})

const normalizeSpecText = (spec: Record<string, any> | null) => {
  if (!spec) return ''
  const parts = [
    spec.category,
    spec.description,
    spec.data_source,
    ...(Array.isArray(spec.constraints) ? spec.constraints : []),
    ...((spec.parameters || []).map((item: any) => item?.name).filter(Boolean)),
    ...((spec.expected_output?.fields || []).filter(Boolean)),
  ]
  return parts.join('\n').toLowerCase()
}

const specPreviewText = computed(() => normalizeSpecText(specPreview.value))
const recommendedStockCollectionSet = computed(() => new Set((backendRecommendations.value?.stock_collections || []).map(item => item.toLowerCase())))
const recommendedExternalSourceSet = computed(() => new Set((backendRecommendations.value?.external_sources || []).map(item => item.toLowerCase())))

const isStockCollectionMatched = (item: StockDataCatalogCollection) => {
  if (recommendedStockCollectionSet.value.has(item.collection.toLowerCase())) return true

  const spec = specPreview.value
  const text = specPreviewText.value
  if (!spec || !text) return false

  if (text.includes(item.collection.toLowerCase())) return true
  if ((item.preferred_access || []).some(entry => text.includes(entry.toLowerCase()))) return true
  if ((item.query_keys || []).some(entry => text.includes(entry.toLowerCase()) && !['symbol', 'code'].includes(entry.toLowerCase()))) return true

  const category = String(spec.category || '').toLowerCase()
  const purpose = String(item.purpose || '').toLowerCase()
  if (category && purpose.includes(category)) return true

  if (item.collection === 'stock_news' && (category === 'news' || text.includes('新闻') || text.includes('publish_time'))) return true
  if (item.collection === 'stock_financial_data' && (category === 'fundamentals' || text.includes('财务') || text.includes('report_period'))) return true
  if (item.collection === 'stock_daily_quotes' && (category === 'technical' || text.includes('日线') || text.includes('trade_date'))) return true
  if (item.collection === 'market_quotes' && (category === 'market' || text.includes('实时') || text.includes('snapshot'))) return true
  if (item.collection === 'stock_basic_info' && ['fundamentals', 'market', 'technical', 'news'].includes(category)) return true

  return false
}

const isExternalSourceMatched = (item: ExternalDataSourceCatalogItem) => {
  if (recommendedExternalSourceSet.value.has(item.source_id.toLowerCase())) return true

  const spec = specPreview.value
  const text = specPreviewText.value
  if (!spec || !text) return false

  if (text.includes(item.source_id.toLowerCase()) || text.includes(item.display_name.toLowerCase())) return true
  if ((item.categories || []).some(entry => text.includes(entry.toLowerCase()))) return true
  if ((item.interfaces || []).some(entry => text.includes(entry.toLowerCase()))) return true

  const category = String(spec.category || '').toLowerCase()
  if (item.source_id === 'tushare' && (category === 'fundamentals' || text.includes('分红') || text.includes('report_period'))) return true
  if (item.source_id === 'akshare' && ((category === 'technical' || category === 'market') || text.includes('免费'))) return true
  if (item.source_id === 'google_news' && (text.includes('港股') || text.includes('google news'))) return true
  if (item.source_id === 'finnhub' && (text.includes('美股') || text.includes('company news'))) return true
  if (item.source_id === 'eastmoney_via_akshare' && (text.includes('东方财富') || text.includes('东财'))) return true

  return false
}

const matchedStockCollections = computed(() => stockCatalogCollections.value.filter(item => isStockCollectionMatched(item)))
const matchedExternalSources = computed(() => externalSourceCatalogSources.value.filter(item => isExternalSourceMatched(item)))

const genProgress = ref(0)
const genSteps = ref([
  { label: '生成代码', status: 'pending' },
  { label: '语法检查', status: 'pending' },
  { label: '安全扫描', status: 'pending' },
  { label: '沙箱执行', status: 'pending' },
  { label: '质量评估', status: 'pending' },
])
const genResult = ref<ConfirmResult | null>(null)
const repairing = ref(false)
const repairPlanning = ref(false)
const repairFeedback = ref('')
const repairPlan = ref('')
const repairPlanFeedback = ref('')
const generatedTestLoading = ref(false)
const generatedTestArgs = ref<Record<string, any>>({})
const generatedTestResult = ref<TestResult | null>(null)

const sessionPipelineResult = ref<PipelineResultDetail | null>(null)

const repairPlanStale = computed(() => {
  const feedback = repairFeedback.value.trim()
  return !!repairPlan.value.trim() && !!feedback && repairPlanFeedback.value !== feedback
})

const canConfirmRepair = computed(() => {
  return !!sessionId.value && !!repairPlan.value.trim() && !repairPlanStale.value
})

const generatedSkillSpec = computed(() => genResult.value?.spec || specPreview.value || null)
const generatedSkillId = computed(() => genResult.value?.skill_id || '')
const generatedTestParams = computed(() => {
  const spec = generatedSkillSpec.value
  return Array.isArray(spec?.parameters) ? spec.parameters : []
})
const generatedTestDefaults = computed(() => {
  const spec = generatedSkillSpec.value
  return spec?.test_input && typeof spec.test_input === 'object' ? spec.test_input : {}
})
const generatedTestResultText = computed(() => {
  if (!generatedTestResult.value) return ''
  return JSON.stringify(generatedTestResult.value.output, null, 2)
})
const generatedTestDataState = computed(() => {
  const result = generatedTestResult.value
  if (!result) {
    return {
      label: '尚未测试',
      type: 'info' as const,
      description: '运行一次测试后，这里会告诉你是否真正拿到了有效数据。',
    }
  }

  if (!result.success) {
    return {
      label: '未拿到数据',
      type: 'danger' as const,
      description: result.error || '测试执行失败，当前无法确认是否能正常拿到数据。',
    }
  }

  const output = result.output
  const hasData = (
    output !== null &&
    output !== undefined &&
    (!(Array.isArray(output)) || output.length > 0) &&
    (typeof output !== 'object' || Array.isArray(output) || Object.keys(output).length > 0) &&
    (typeof output !== 'string' || output.trim().length > 0)
  )

  return hasData
    ? {
        label: '已拿到数据',
        type: 'success' as const,
        description: '测试已跑通，返回结果中包含有效输出。',
      }
    : {
        label: '执行成功但无数据',
        type: 'warning' as const,
        description: '代码已经执行成功，但当前输出为空，需要继续确认查询参数或数据来源是否正确。',
      }
})

const pipelineFailureSummary = computed(() => {
  const result = sessionPipelineResult.value
  if (!result) return []

  const lines: string[] = []
  if (result.error) {
    lines.push(`最终错误：${result.error}`)
  }

  for (const iteration of result.iterations || []) {
    const prefix = `第${iteration.round_number}轮`
    if (iteration.validation?.errors?.length) {
      for (const error of iteration.validation.errors.slice(0, 5)) {
        lines.push(`${prefix} 静态验证：${error}`)
      }
    }
    if (iteration.sandbox && iteration.sandbox.success === false && iteration.sandbox.error) {
      lines.push(`${prefix} 沙箱执行：${iteration.sandbox.error}`)
    }
    if (iteration.eval_score && typeof iteration.eval_score.total === 'number') {
      lines.push(
        `${prefix} 评估分数不足：total=${iteration.eval_score.total}，` +
        `executability=${iteration.eval_score.executability ?? '-'}，` +
        `authenticity=${iteration.eval_score.authenticity ?? '-'}，` +
        `completeness=${iteration.eval_score.completeness ?? '-'}，` +
        `relevance=${iteration.eval_score.relevance ?? '-'}，` +
        `format_quality=${iteration.eval_score.format_quality ?? '-'}`
      )
    }
    if (iteration.feedback) {
      lines.push(`${prefix} 系统反馈：${iteration.feedback}`)
    }
  }

  return Array.from(new Set(lines))
})

const buildGeneratedTestArgs = () => {
  const defaults = generatedTestDefaults.value || {}
  const init: Record<string, any> = {}
  for (const p of generatedTestParams.value) {
    init[p.name] = defaults[p.name] ?? p.default ?? (p.type === 'boolean' || p.type === 'bool' ? false : '')
  }
  for (const [key, value] of Object.entries(defaults)) {
    if (!(key in init)) init[key] = value
  }
  return init
}

const resetGeneratedTestArgs = () => {
  generatedTestArgs.value = buildGeneratedTestArgs()
}

const prepareGeneratedTestPanel = () => {
  generatedTestResult.value = null
  generatedTestLoading.value = false
  resetGeneratedTestArgs()
}

// ==================== 方法 ====================

const scrollChat = () => {
  nextTick(() => {
    if (chatContainer.value) chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  })
}

const goBack = () => {
  router.push('/workflow/skill-generation')
}

const copyText = async (text: string, successMessage: string) => {
  const normalized = text.trim()
  if (!normalized) return

  try {
    if (navigator?.clipboard?.writeText) {
      await navigator.clipboard.writeText(normalized)
    } else {
      const textarea = document.createElement('textarea')
      textarea.value = normalized
      textarea.setAttribute('readonly', 'true')
      textarea.style.position = 'absolute'
      textarea.style.left = '-9999px'
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
    }
    ElMessage.success(successMessage)
  } catch (e: any) {
    ElMessage.error(e?.message || '复制失败')
  }
}

const copyCatalogCollectionName = async (collectionName: string) => {
  await copyText(collectionName, `已复制集合名：${collectionName}`)
}

const copyCatalogFieldNames = async (item: StockDataCatalogCollection) => {
  const fieldNames = (item.fields || []).map(field => field.name).filter(Boolean)
  await copyText(fieldNames.join(', '), `已复制 ${item.collection} 的字段名`)
}

const copyCatalogQueryKeys = async (item: StockDataCatalogCollection) => {
  const queryKeys = (item.query_keys || []).filter(Boolean)
  await copyText(queryKeys.join(', '), `已复制 ${item.collection} 的查询键`)
}

const copyCatalogPreferredAccess = async (item: StockDataCatalogCollection) => {
  const preferredAccess = (item.preferred_access || []).filter(Boolean)
  await copyText(preferredAccess.join(', '), `已复制 ${item.collection} 的推荐访问函数`)
}

const copyCatalogFieldDescriptions = async (item: StockDataCatalogCollection) => {
  const fieldDescriptions = (item.fields || [])
    .filter(field => field?.name)
    .map(field => `${field.name} (${field.type}): ${field.description}`)
  await copyText(fieldDescriptions.join('\n'), `已复制 ${item.collection} 的字段说明`)
}

const copyExternalSourceName = async (item: ExternalDataSourceCatalogItem) => {
  await copyText(item.display_name, `已复制来源名：${item.display_name}`)
}

const copyExternalSourceInterfaces = async (item: ExternalDataSourceCatalogItem) => {
  await copyText((item.interfaces || []).join('\n'), `已复制 ${item.display_name} 的推荐接口`)
}

const copyExternalSourcePreferredFor = async (item: ExternalDataSourceCatalogItem) => {
  await copyText((item.preferred_for || []).join('\n'), `已复制 ${item.display_name} 的适用场景`)
}

const copyExternalSourceConstraints = async (item: ExternalDataSourceCatalogItem) => {
  await copyText((item.constraints || []).join('\n'), `已复制 ${item.display_name} 的约束说明`)
}

const buildCatalogRequirementSnippet = (item: StockDataCatalogCollection) => {
  const queryKeys = (item.query_keys || []).filter(Boolean)
  const preferredAccess = (item.preferred_access || []).filter(Boolean)
  const fieldDescriptions = (item.fields || [])
    .filter(field => field?.name)
    .map(field => `- ${field.name} (${field.type}): ${field.description}`)

  return [
    `请优先复用本地股票数据集合 ${item.collection}。`,
    preferredAccess.length ? `推荐访问函数：${preferredAccess.join('、')}。` : '',
    queryKeys.length ? `常用查询键：${queryKeys.join('、')}。` : '',
    fieldDescriptions.length ? `关键字段：\n${fieldDescriptions.join('\n')}` : '',
  ].filter(Boolean).join('\n')
}

const insertCatalogIntoRequirement = async (item: StockDataCatalogCollection) => {
  const snippet = buildCatalogRequirementSnippet(item)
  if (!snippet.trim()) return

  userInput.value = userInput.value.trim()
    ? `${userInput.value.trim()}\n\n${snippet}`
    : snippet

  if (wizardStep.value !== 0) {
    wizardStep.value = 0
    await nextTick()
  }

  ElMessage.success(`已将 ${item.collection} 的目录信息插入到需求输入框`)
}

const buildExternalSourceRequirementSnippet = (item: ExternalDataSourceCatalogItem) => {
  const markets = (item.markets || []).filter(Boolean)
  const categories = (item.categories || []).filter(Boolean)
  const preferredFor = (item.preferred_for || []).filter(Boolean)
  const interfaces = (item.interfaces || []).filter(Boolean)
  const constraints = (item.constraints || []).filter(Boolean)

  return [
    `若需要外部在线数据，请优先使用 ${item.display_name}（${item.source_id}）。`,
    markets.length ? `覆盖市场：${markets.join('、')}。` : '',
    categories.length ? `适用分类：${categories.join('、')}。` : '',
    preferredFor.length ? `推荐场景：${preferredFor.join('；')}。` : '',
    interfaces.length ? `优先接口：${interfaces.join('；')}。` : '',
    constraints.length ? `使用约束：${constraints.join('；')}。` : '',
  ].filter(Boolean).join('\n')
}

const insertExternalSourceIntoRequirement = async (item: ExternalDataSourceCatalogItem) => {
  const snippet = buildExternalSourceRequirementSnippet(item)
  if (!snippet.trim()) return

  userInput.value = userInput.value.trim()
    ? `${userInput.value.trim()}\n\n${snippet}`
    : snippet

  if (wizardStep.value !== 0) {
    wizardStep.value = 0
    await nextTick()
  }

  ElMessage.success(`已将 ${item.display_name} 的目录信息插入到需求输入框`)
}

const loadStockDataCatalog = async () => {
  stockCatalogLoading.value = true
  try {
    const res = await skillGenerationApi.getStockDataCatalog()
    stockCatalogCollections.value = res.collections || []
    stockCatalogDoc.value = res.doc || ''
  } catch (e: any) {
    ElMessage.error(e?.message || '加载股票数据目录失败')
  } finally {
    stockCatalogLoading.value = false
  }
}

const loadExternalDataSourceCatalog = async () => {
  externalSourceCatalogLoading.value = true
  try {
    const res = await skillGenerationApi.getExternalDataSourceCatalog()
    externalSourceCatalogSources.value = res.sources || []
    externalSourceCatalogDoc.value = res.doc || ''
  } catch (e: any) {
    ElMessage.error(e?.message || '加载外部接口与数据源目录失败')
  } finally {
    externalSourceCatalogLoading.value = false
  }
}

const getPrefillDescription = () => {
  const raw = route.query.description
  if (typeof raw === 'string') return raw.trim()
  return ''
}

const shouldFocusRecommendations = () => route.query.focus === 'recommendations'
const shouldFocusConfirmActions = () => route.query.focus === 'confirm'

const setStockCardRef = (collection: string, el: Element | ComponentPublicInstance | null) => {
  const htmlEl = el instanceof HTMLElement ? el : (el as any)?.$el instanceof HTMLElement ? (el as any).$el : null
  stockCardRefs.value[collection] = htmlEl
}

const setExternalSourceCardRef = (sourceId: string, el: Element | ComponentPublicInstance | null) => {
  const htmlEl = el instanceof HTMLElement ? el : (el as any)?.$el instanceof HTMLElement ? (el as any).$el : null
  externalSourceCardRefs.value[sourceId] = htmlEl
}

const scrollElementIntoView = async (element: HTMLElement | null) => {
  await nextTick()
  if (!element) return
  element.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

const focusFirstMatchedStockCard = async () => {
  if (!matchedStockCollections.value.length) return
  stockCatalogExpanded.value = ['stock-data-catalog']
  await nextTick()
  const firstMatch = matchedStockCollections.value[0]
  await scrollElementIntoView(stockCardRefs.value[firstMatch.collection] || null)
}

const focusFirstMatchedExternalCard = async () => {
  if (!matchedExternalSources.value.length) return
  externalSourceCatalogExpanded.value = ['external-data-source-catalog']
  await nextTick()
  const firstMatch = matchedExternalSources.value[0]
  await scrollElementIntoView(externalSourceCardRefs.value[firstMatch.source_id] || null)
}

const focusRecommendationCard = async () => {
  if (!shouldFocusRecommendations()) return
  await nextTick()
  if (!recommendationCardRef.value) return

  recommendationCardRef.value.scrollIntoView({ behavior: 'smooth', block: 'start' })
  highlightRecommendationCard.value = true
  window.setTimeout(() => {
    highlightRecommendationCard.value = false
  }, 2200)
}

const focusConfirmActions = async () => {
  if (!shouldFocusConfirmActions()) return
  await nextTick()
  if (!confirmActionsRef.value) return

  confirmActionsRef.value.scrollIntoView({ behavior: 'smooth', block: 'center' })
  highlightConfirmActions.value = true
  window.setTimeout(() => {
    highlightConfirmActions.value = false
  }, 2200)
}

const focusRecommendationFlow = async () => {
  if (!shouldFocusRecommendations()) return
  stockCatalogExpanded.value = ['stock-data-catalog']
  externalSourceCatalogExpanded.value = ['external-data-source-catalog']
  await focusRecommendationCard()
  if (matchedStockCollections.value.length) {
    window.setTimeout(() => {
      void focusFirstMatchedStockCard()
    }, 450)
    return
  }
  if (matchedExternalSources.value.length) {
    window.setTimeout(() => {
      void focusFirstMatchedExternalCard()
    }, 450)
  }
}

const focusConfirmFlow = async () => {
  if (!shouldFocusConfirmActions()) return
  await focusConfirmActions()
}

/** 初始化：新建或恢复草稿 */
const initFromRoute = async () => {
  const sid = route.query.sessionId as string
  if (sid) {
    try {
      const session = await skillGenerationApi.getSession(sid)
      sessionId.value = session.session_id
      currentRound.value = session.current_round
      expectedRounds.value = Math.max(3, session.rounds?.length || 0)
      boundaryCheck.value = session.boundary_check || null
      handoffContext.value = session.handoff_context || getRouteHandoffContext()

      chatMessages.value = []
      for (const round of (session.rounds || [])) {
        chatMessages.value.push({ role: 'user', content: round.user_message })
        chatMessages.value.push({ role: 'ai', content: round.ai_message })
      }

      genResult.value = null
      genProgress.value = 0
      genSteps.value.forEach(s => s.status = 'pending')
      userInput.value = ''

      if (session.status === 'confirmed') {
        wizardStep.value = 1
        specPreview.value = session.spec || null
        backendRecommendations.value = session.recommendations || null
        if (shouldFocusConfirmActions()) {
          await focusConfirmFlow()
        } else {
          await focusRecommendationFlow()
        }
      } else {
        wizardStep.value = 0
      }
      scrollChat()
      ElMessage.success('已恢复草稿')
    } catch (e: any) {
      ElMessage.error('恢复草稿失败: ' + (e?.message || ''))
      wizardStep.value = 0
    }
  } else {
    wizardStep.value = 0
    handoffContext.value = getRouteHandoffContext()
    const prefillDescription = getPrefillDescription()
    if (prefillDescription) {
      userInput.value = prefillDescription
      await nextTick()
      await handleChatSend()
    }
  }
}

const handleChatSend = async () => {
  const text = userInput.value?.trim()
  if (!text || chatLoading.value) return

  chatMessages.value.push({ role: 'user', content: text })
  userInput.value = ''
  scrollChat()
  chatLoading.value = true

  try {
    if (!sessionId.value) {
      const res = await skillGenerationApi.startSession({
        description: text,
        handoff_context: handoffContext.value || undefined,
      })
      sessionId.value = res.session_id
      currentRound.value = res.current_round
      expectedRounds.value = res.expected_rounds
      boundaryCheck.value = res.boundary_check
      chatMessages.value.push({ role: 'ai', content: res.ai_message })
    } else {
      const res = await skillGenerationApi.respondToSession(sessionId.value, text)
      currentRound.value = res.current_round
      expectedRounds.value = res.expected_rounds
      if (res.boundary_check != null) boundaryCheck.value = res.boundary_check
      chatMessages.value.push({ role: 'ai', content: res.ai_message })
    }
    scrollChat()
  } catch (e: any) {
    const msg = e?.message || e?.response?.data?.message || '请求失败'
    ElMessage.error(msg)
    chatMessages.value.push({ role: 'ai', content: `❌ 出错了：${msg}` })
    scrollChat()
  } finally {
    chatLoading.value = false
  }
}

/** 查看规格：调用 previewSpec，进入步骤 1 */
const handleViewSpec = async () => {
  if (!sessionId.value) return
  const confirmMessage = userInput.value?.trim() || '确认'
  if (userInput.value?.trim()) {
    chatMessages.value.push({ role: 'user', content: userInput.value.trim() })
    userInput.value = ''
    scrollChat()
  }
  chatLoading.value = true
  try {
    const res = await skillGenerationApi.previewSpec(sessionId.value, confirmMessage)
    specPreview.value = res.spec
    backendRecommendations.value = res.recommendations || null
    wizardStep.value = 1
  } catch (e: any) {
    ElMessage.error(e?.message || '获取规格失败')
  } finally {
    chatLoading.value = false
  }
}

/** 确认并生成：调用 confirmSpec，若返回 generating 则轮询 */
const handleConfirmAndGenerate = async () => {
  if (!sessionId.value) return
  const confirmationText = [
    preflightLocalCollections.value.length
      ? `优先复用本地集合：${preflightLocalCollections.value.join('、')}`
      : '当前没有明确命中的本地集合。',
    preflightExternalSources.value.length
      ? `候选外部来源：${preflightExternalSources.value.join('、')}`
      : '当前优先本地数据，外部来源不是必须项。',
    '确认后将开始代码生成、静态校验、沙箱执行和质量评估。',
  ].join('\n')

  try {
    await ElMessageBox.confirm(confirmationText, '生成前确认', {
      confirmButtonText: '继续生成',
      cancelButtonText: '返回检查',
      type: 'warning',
    })
  } catch {
    return
  }

  specConfirmLoading.value = true
  wizardStep.value = 2
  repairFeedback.value = ''
  sessionPipelineResult.value = null
  genSteps.value.forEach(s => s.status = 'pending')
  genProgress.value = 0
  pipelineMessage.value = ''

  const stageToStep: Record<string, number> = {
    code_generation: 0,
    static_validation: 1,
    sandbox_execution: 2,
    output_evaluation: 3,
  }

  try {
    const res = await skillGenerationApi.confirmSpec(sessionId.value, '确认')
    if (res.status === 'generating') {
      const pollInterval = 1500
      const poll = async () => {
        const session = await skillGenerationApi.getSession(sessionId.value)
        sessionPipelineResult.value = (session.pipeline_result || null) as PipelineResultDetail | null
        const stage = session.pipeline_stage
        const msg = session.pipeline_message
        const prog = session.pipeline_progress ?? 0
        if (stage && stageToStep[stage] !== undefined) {
          pipelineMessage.value = msg || stage
          genProgress.value = Math.round(prog * 100) / 100
          const idx = stageToStep[stage]
          genSteps.value.forEach((s, i) => {
            s.status = i < idx ? 'done' : i === idx ? 'running' : 'pending'
          })
        }
        if (session.status === 'completed' || session.status === 'failed') {
          const pr = session.pipeline_result
          const lastIter = pr?.iterations?.[pr.iterations.length - 1]
          const es = lastIter?.eval_score
          const finalScore = es ? Math.round(
            (es.executability || 0) * 0.25 + (es.authenticity || 0) * 0.25 +
            (es.completeness || 0) * 0.2 + (es.relevance || 0) * 0.2 +
            (es.format_quality || 0) * 0.1
          ) : null
          genProgress.value = 100
          genSteps.value.forEach(s => s.status = 'done')
          genResult.value = {
            status: session.status,
            session_id: sessionId.value,
            skill_id: pr?.tool_id ?? null,
            spec: session.spec ?? null,
            success: session.status === 'completed',
            total_rounds: pr?.total_rounds ?? 0,
            total_time: pr?.total_time ?? 0,
            final_score: finalScore,
            error: pr?.error ?? null,
          }
          if (session.status === 'completed') prepareGeneratedTestPanel()
          wizardStep.value = 3
          return
        }
        setTimeout(poll, pollInterval)
      }
      setTimeout(poll, pollInterval)
    } else {
      genProgress.value = 100
      genSteps.value.forEach(s => s.status = 'done')
      genResult.value = res
      if (res.success) prepareGeneratedTestPanel()
      wizardStep.value = 3
    }
  } catch (e: any) {
    genResult.value = {
      status: 'failed', session_id: sessionId.value, skill_id: null,
      spec: null, success: false, total_rounds: 0, total_time: 0,
      final_score: null, error: e?.message || '生成失败'
    }
    wizardStep.value = 3
  } finally {
    specConfirmLoading.value = false
  }
}

const handleRepairAndRegenerate = async () => {
  if (!sessionId.value || !repairFeedback.value.trim() || !canConfirmRepair.value) return
  repairing.value = true
  try {
    await skillGenerationApi.repairSession(
      sessionId.value,
      repairFeedback.value.trim(),
      repairPlan.value.trim(),
    )
    wizardStep.value = 2
    genProgress.value = 0
    pipelineMessage.value = '已确认修正计划，正在重新生成...'
    genSteps.value.forEach(s => s.status = 'pending')
    sessionPipelineResult.value = null
    repairPlan.value = ''
    repairPlanFeedback.value = ''

    const pollInterval = 1500
    const poll = async () => {
      const session = await skillGenerationApi.getSession(sessionId.value)
      sessionPipelineResult.value = (session.pipeline_result || null) as PipelineResultDetail | null
      const stage = session.pipeline_stage
      const msg = session.pipeline_message
      const prog = session.pipeline_progress ?? 0
      const stageToStep: Record<string, number> = {
        code_generation: 0,
        static_validation: 1,
        sandbox_execution: 2,
        output_evaluation: 3,
      }
      if (stage && stageToStep[stage] !== undefined) {
        pipelineMessage.value = msg || stage
        genProgress.value = Math.round(prog * 100) / 100
        const idx = stageToStep[stage]
        genSteps.value.forEach((s, i) => {
          s.status = i < idx ? 'done' : i === idx ? 'running' : 'pending'
        })
      }

      if (session.status === 'completed' || session.status === 'failed') {
        const pr = session.pipeline_result as PipelineResultDetail | null
        const lastIter = pr?.iterations?.[pr.iterations.length - 1]
        const score = lastIter?.eval_score
        const finalScore = typeof score?.total === 'number' ? score.total : null
        genProgress.value = 100
        genSteps.value.forEach(s => s.status = 'done')
        genResult.value = {
          status: session.status,
          session_id: sessionId.value,
          skill_id: pr?.tool_id ?? null,
          spec: session.spec ?? null,
          success: session.status === 'completed',
          total_rounds: pr?.total_rounds ?? 0,
          total_time: pr?.total_time ?? 0,
          final_score: finalScore,
          error: pr?.error ?? null,
        }
        if (session.status === 'completed') prepareGeneratedTestPanel()
        wizardStep.value = 3
        return
      }
      setTimeout(poll, pollInterval)
    }

    setTimeout(poll, 1500)
  } catch (e: any) {
    ElMessage.error(e?.message || '重新生成失败')
  } finally {
    repairing.value = false
  }
}

const runGeneratedSkillTest = async () => {
  if (!generatedSkillId.value) return
  generatedTestLoading.value = true
  generatedTestResult.value = null
  try {
    const args: Record<string, any> = {}
    for (const p of generatedTestParams.value) {
      let value = generatedTestArgs.value[p.name]
      if (value === '' || value === undefined) value = p.default
      if (p.type === 'integer' || p.type === 'int') args[p.name] = value != null ? Number(value) : undefined
      else if (p.type === 'float' || p.type === 'number') args[p.name] = value != null ? Number(value) : undefined
      else if (p.type === 'boolean' || p.type === 'bool') args[p.name] = !!value
      else args[p.name] = value
    }
    for (const [key, value] of Object.entries(generatedTestDefaults.value || {})) {
      if (!(key in args) || args[key] === undefined || args[key] === '') args[key] = value
    }
    generatedTestResult.value = await skillGenerationApi.testSkill(generatedSkillId.value, args)
  } catch (e: any) {
    generatedTestResult.value = {
      success: false,
      output: null,
      stdout: '',
      stderr: '',
      execution_time: 0,
      error: e?.message || '测试请求失败',
    }
  } finally {
    generatedTestLoading.value = false
  }
}

const handlePreviewRepairPlan = async () => {
  if (!sessionId.value || !repairFeedback.value.trim()) return
  repairPlanning.value = true
  try {
    const res = await skillGenerationApi.previewRepairSession(sessionId.value, repairFeedback.value.trim())
    repairPlan.value = res.ai_message || ''
    repairPlanFeedback.value = repairFeedback.value.trim()
  } catch (e: any) {
    ElMessage.error(e?.message || '生成修正计划失败')
  } finally {
    repairPlanning.value = false
  }
}

onMounted(async () => {
  await loadStockDataCatalog()
  await loadExternalDataSourceCatalog()
  initFromRoute()
})
</script>

<style lang="scss" scoped>
.skill-create-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 60px);
  min-height: 500px;
  padding: 16px 24px;
  background: var(--el-bg-color-page);
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  margin-bottom: 16px;

  .header-left {
    display: flex;
    align-items: center;
    gap: 12px;

    .header-divider {
      color: var(--el-border-color);
      font-size: 14px;
    }

    h1 {
      font-size: 18px;
      margin: 0;
      font-weight: 600;
    }
  }
}

.steps-bar {
  flex-shrink: 0;
  margin-bottom: 20px;
  padding: 12px 24px;
  background: var(--el-bg-color);
  border-radius: 8px;
  border: 1px solid var(--el-border-color-lighter);
}

.main-content {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: var(--el-bg-color);
  border-radius: 8px;
  border: 1px solid var(--el-border-color-lighter);
  padding: 20px;
  overflow: hidden;
}

/* ========== 需求沟通（全屏利用） ========== */
.wizard-chat {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-lighter);
  margin-bottom: 12px;
}

.handoff-card {
  margin-bottom: 16px;
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px solid #d7e3f7;
  background: linear-gradient(135deg, #f7fbff 0%, #eef5ff 100%);
}

.handoff-title {
  margin-bottom: 6px;
  font-size: 14px;
  font-weight: 700;
  color: #1f3b63;
}

.handoff-text {
  font-size: 14px;
  color: #30445f;
  line-height: 1.7;
}

.handoff-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 8px;
  font-size: 13px;
  color: #58708f;
}

.handoff-note {
  margin-top: 8px;
  font-size: 13px;
  color: #405a7d;
  line-height: 1.6;
}

/* 需求提交引导语 */
.requirement-guide {
  padding: 24px 20px;
  color: var(--el-text-color-regular);
  font-size: 14px;
  line-height: 1.7;

  .guide-header {
    text-align: center;
    margin-bottom: 24px;

    .guide-icon {
      font-size: 48px;
      color: var(--el-color-primary);
      margin-bottom: 12px;
    }

    h3 {
      font-size: 18px;
      margin: 0 0 8px;
      font-weight: 600;
      color: var(--el-text-color-primary);
    }

    .guide-desc {
      margin: 0;
      color: var(--el-text-color-secondary);
      font-size: 14px;
    }
  }

  .guide-tips {
    background: var(--el-bg-color);
    border: 1px solid var(--el-border-color-lighter);
    border-radius: 8px;
    padding: 16px 20px;
    margin-bottom: 20px;
  }

  .tip-item {
    margin-bottom: 16px;

    &:last-child {
      margin-bottom: 0;
    }

    .tip-label {
      display: block;
      font-weight: 500;
      margin-bottom: 8px;
      color: var(--el-text-color-primary);
    }

    ul {
      margin: 0;
      padding-left: 20px;
      color: var(--el-text-color-regular);

      li {
        margin-bottom: 6px;
      }
    }

    .guide-examples li {
      color: var(--el-text-color-secondary);
      font-style: italic;
    }
  }

  .guide-footer {
    text-align: center;
    margin: 0;
    font-size: 13px;
    color: var(--el-text-color-placeholder);

    kbd {
      display: inline-block;
      padding: 2px 6px;
      font-size: 12px;
      background: var(--el-fill-color);
      border: 1px solid var(--el-border-color);
      border-radius: 4px;
      font-family: inherit;
    }
  }
}

.chat-msg {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;

  &.chat-user { flex-direction: row-reverse; }

  .msg-avatar {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    background: var(--el-color-primary-light-8);
    color: var(--el-color-primary);
    font-size: 18px;
  }

  &.chat-user .msg-avatar {
    background: var(--el-color-success-light-8);
    color: var(--el-color-success);
  }

  .msg-bubble {
    max-width: 75%;
    padding: 12px 16px;
    border-radius: 12px;
    background: var(--el-bg-color);
    border: 1px solid var(--el-border-color-lighter);
    line-height: 1.7;
    font-size: 14px;

    &.thinking {
      color: var(--el-text-color-secondary);
      font-style: italic;
    }
  }

  &.chat-user .msg-bubble {
    background: var(--el-color-primary-light-9);
    border-color: var(--el-color-primary-light-7);
  }
}

.msg-text {
  :deep(p) { margin: 0 0 6px; }
  :deep(ul), :deep(ol) { margin: 6px 0; padding-left: 24px; }
  :deep(table) {
    border-collapse: collapse;
    width: 100%;
    font-size: 13px;
    th, td { border: 1px solid var(--el-border-color); padding: 8px 12px; }
    th { background: var(--el-fill-color-light); }
  }
}

.dot-animation span {
  animation: blink 1.4s infinite both;
  &:nth-child(2) { animation-delay: 0.2s; }
  &:nth-child(3) { animation-delay: 0.4s; }
}
@keyframes blink { 0%, 80%, 100% { opacity: 0; } 40% { opacity: 1; } }

.boundary-alert {
  flex-shrink: 0;
  margin-bottom: 12px;
}

.boundary-collapsible {
  border: 1px solid var(--el-color-warning-light-5);
  border-radius: 8px;
  background: var(--el-color-warning-light-9);
  overflow: hidden;
}

.boundary-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  cursor: pointer;
  user-select: none;
  font-size: 14px;
  color: var(--el-color-warning-dark-2);
  &:hover { background: var(--el-color-warning-light-8); }

  .boundary-icon { font-size: 18px; color: var(--el-color-warning); }
  .boundary-chevron {
    margin-left: auto;
    transition: transform 0.2s;
    &.expanded { transform: rotate(180deg); }
  }
}

.boundary-content {
  padding: 0 12px 12px 36px;
  font-size: 13px;
  color: var(--el-text-color-regular);
  line-height: 1.6;
}

.chat-input-area {
  flex-shrink: 0;
}

.chat-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 10px;

  .tip { color: var(--el-text-color-placeholder); font-size: 12px; }
}

/* ========== 规格确认 ========== */
.wizard-spec-confirm {
  flex: 1;
  min-height: 0;
  display: flex;
  justify-content: center;
  align-items: flex-start;
  overflow-y: auto;
  padding: 24px;
}
.spec-confirm-card {
  max-width: 640px;
  width: 100%;
  margin: 0 auto;
  padding: 20px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-bg-color);
}
.spec-confirm-card h3 {
  margin: 0 0 16px;
  font-size: 16px;
}

.handoff-inline-note {
  margin-bottom: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  background: #f6f8fc;
  color: #52627a;
  font-size: 13px;
  line-height: 1.6;
}

.spec-params-section {
  margin-top: 16px;
}
.spec-params-section h4 {
  margin: 0 0 8px;
  font-size: 14px;
}
.spec-boundary-warn {
  margin-top: 16px;
}

.spec-catalog-card {
  margin-top: 20px;
  padding: 18px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  background: var(--el-fill-color-lighter);
}

.spec-recommendation-card {
  margin-top: 20px;
  padding: 18px;
  border: 1px solid var(--el-color-primary-light-5);
  border-radius: 10px;
  background: linear-gradient(180deg, var(--el-color-primary-light-9), var(--el-bg-color));
}

.spec-recommendation-card-highlight {
  box-shadow: 0 0 0 2px var(--el-color-warning-light-5), 0 10px 24px rgba(0, 0, 0, 0.08);
  transition: box-shadow 0.3s ease;
}

.recommendation-grid {
  display: grid;
  gap: 14px;
  margin-top: 12px;
}

.recommendation-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.recommendation-block {
  padding: 12px 14px;
  border-radius: 8px;
  border: 1px solid var(--el-border-color-lighter);
  background: var(--el-bg-color);
}

.recommendation-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
}

.recommendation-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.recommendation-empty {
  font-size: 13px;
  color: var(--el-text-color-placeholder);
}

.spec-catalog-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;

  h4 {
    margin: 0;
    font-size: 15px;
  }

  p {
    margin: 6px 0 0;
    color: var(--el-text-color-secondary);
    line-height: 1.6;
    font-size: 13px;
  }
}

.catalog-summary {
  margin: 12px 0 0;
  color: var(--el-text-color-regular);
  font-size: 13px;
}

.catalog-match-summary {
  margin-top: 10px;
  font-size: 13px;
  color: var(--el-color-primary);
  font-weight: 500;
}

.catalog-collection-list {
  display: grid;
  gap: 16px;
}

.catalog-collection-card {
  padding: 16px;
  border-radius: 10px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
}

.catalog-collection-card-recommended {
  border-color: var(--el-color-primary-light-5);
  box-shadow: 0 0 0 1px var(--el-color-primary-light-8) inset;
}

.catalog-collection-topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.catalog-collection-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
  flex-shrink: 0;
  justify-content: flex-end;
}

.catalog-collection-title {
  font-size: 15px;
  font-weight: 600;
}

.catalog-match-label {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-color-primary);
  font-weight: 500;
}

.catalog-collection-purpose {
  margin-top: 8px;
  color: var(--el-text-color-secondary);
  line-height: 1.6;
}

.catalog-field-table {
  margin-top: 12px;
}

.catalog-notes {
  margin-top: 12px;
  display: grid;
  gap: 8px;
}

.catalog-note-item {
  color: var(--el-text-color-secondary);
  font-size: 13px;
  line-height: 1.6;
}
.spec-confirm-actions {
  margin-top: 20px;
  padding-bottom: 8px;
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}

.spec-confirm-actions-highlight {
  padding: 12px;
  border-radius: 10px;
  background: var(--el-color-success-light-9);
  box-shadow: 0 0 0 2px var(--el-color-success-light-5);
  transition: box-shadow 0.3s ease, background 0.3s ease;
}

.spec-preflight-card {
  margin-top: 20px;
  padding: 18px;
  border: 1px solid var(--el-color-warning-light-5);
  border-radius: 10px;
  background: linear-gradient(180deg, var(--el-color-warning-light-9), var(--el-bg-color));
}

.preflight-grid {
  display: grid;
  gap: 14px;
  margin-top: 12px;
}

.preflight-notes {
  display: grid;
  gap: 8px;
}

.done-context-card {
  margin: 20px auto 0;
  max-width: 760px;
  padding: 18px;
  border: 1px solid var(--el-color-success-light-5);
  border-radius: 10px;
  background: linear-gradient(180deg, var(--el-color-success-light-9), var(--el-bg-color));
}

/* ========== 生成进度 ========== */
.wizard-generating {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;

  .gen-status {
    text-align: center;
    h3 { margin: 16px 0 8px; font-size: 18px; }
    .gen-desc { color: var(--el-text-color-secondary); font-size: 14px; }
  }
}

.gen-spinner { animation: spin 1.5s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.gen-steps {
  display: flex;
  justify-content: center;
  flex-wrap: wrap;
  gap: 24px;
  margin-top: 24px;
}

.gen-step {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  color: var(--el-text-color-secondary);

  &.done { color: var(--el-color-success); }
  &.running { color: var(--el-color-primary); font-weight: 500; }
}

/* ========== 完成 ========== */
.wizard-done {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  width: 100%;
  padding: 40px;
  overflow-y: auto;
  overflow-x: hidden;
}

.test-run-card {
  margin: 20px auto 0;
  max-width: 760px;
  width: 100%;
  padding: 18px;
  border: 1px solid var(--el-color-primary-light-5);
  border-radius: 10px;
  background: linear-gradient(180deg, var(--el-color-primary-light-9), var(--el-bg-color));
}

.test-run-form {
  margin-top: 12px;
}

.test-run-actions {
  display: flex;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 16px;
}

.test-run-result {
  margin-top: 18px;
}

.test-run-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 12px;
}

.test-run-pre {
  margin: 0;
  max-height: 280px;
  overflow: auto;
  white-space: pre-wrap;
  font-size: 12px;
  line-height: 1.6;
}

.test-run-error {
  color: var(--el-color-danger);
}

.test-params-empty {
  margin-top: 12px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.repair-card {
  margin: 20px auto 0;
  max-width: 760px;
  padding: 18px;
  border: 1px solid var(--el-color-danger-light-5);
  border-radius: 10px;
  background: linear-gradient(180deg, var(--el-color-danger-light-9), var(--el-bg-color));
}

.repair-summary-list {
  display: grid;
  gap: 8px;
  margin: 14px 0;
}

.repair-actions {
  display: flex;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 16px;
}

.repair-plan-card {
  margin-top: 16px;
  padding: 16px 18px;
  border-radius: 14px;
  border: 1px solid rgba(36, 99, 235, 0.18);
  background: linear-gradient(180deg, rgba(239, 246, 255, 0.92) 0%, rgba(248, 250, 252, 0.98) 100%);
}

.repair-plan-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.repair-plan-header h5 {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
  color: #1e3a8a;
}

.repair-plan-stale {
  font-size: 12px;
  color: #b45309;
}

.repair-plan-markdown {
  color: #1f2937;
}
</style>
