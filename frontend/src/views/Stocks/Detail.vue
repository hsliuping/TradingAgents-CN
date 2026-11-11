<template>
  <div class="stock-detail-redesign">

    <!-- ════════ 1. 顶部：股票概览 + 操作入口 ════════ -->
    <StockOverview
      :code="code"
      :stock-name="stockName"
      :market-label="marketLabel"
      :is-etf="isEtf"
      :quote="quote"
      :etf-basics="etfBasics"
      :is-fav="isFav"
      :refresh-text="refreshText"
      :sync-status="syncStatus"
      :sync-loading="syncLoading"
      :clear-cache-loading="clearCacheLoading"
      @refresh="refreshMockQuote"
      @analyze="onAnalyze"
      @sync="showSyncDialog"
      @paper-trading="goPaperTrading"
      @toggle-favorite="onToggleFavorite"
      @clear-cache="clearCache"
      @go-position-analysis="goToPositionAnalysis"
      @add-position="showAddPositionDialog"
      @go-trade-review="goToTradeReview"
      @go-trade-review-history="goToReviewHistory"
      @go-api-guide="goToApiGuide"
    />

    <!-- ════════ 档案式 Tab 导航（7 Tab） ════════ -->
    <el-tabs v-model="activeDetailTab" class="stock-detail-tabs" type="border-card">

      <!-- ===== 概览 ===== -->
      <el-tab-pane label="概览" name="overview" lazy>
        <AssistantHero
          :code="code"
          :stock-name="stockName"
          :has-analysis="assistantHasAnalysis"
          :has-position="assistantHasPosition"
          :has-review="assistantHasReview"
          :has-fundamentals="assistantHasFundamentals"
          :has-kline="assistantHasKline"
          @ask="handleAssistantHeroAsk"
        />

        <!-- 关键指标条 + 风险提示（同一行） -->
        <OverviewTopStrip
          :basics="basics"
          :financial-snapshot="financialSnapshot"
          :quote="quote"
        >
          <!-- 猪周期专属风险：保险丝 / 期货升水灯（行业世界模型驱动，仅覆盖猪周期龙头） -->
          <template v-if="pigCovered" #industry-risks>
            <div v-for="(r, i) in pigRiskItems" :key="'p' + i" class="pig-risk-item">
              <span class="risk-dot" :class="'is-' + r.level"></span>
              <div class="ri-body">{{ r.text }}</div>
            </div>
          </template>
        </OverviewTopStrip>

        <!-- K线 + 核心指标 -->
        <div class="main-grid" id="kline-section">
          <KlineChart
            :title="klineCardTitle"
            :category="klineCategory"
            :values="klineValues"
            :volumes="klineVolumes"
            :period="period"
            :period-options="periodOptions"
            :kline-source="klineSource"
            :last-k-time="lastKTime"
            :last-k-close="lastKClose"
            @update-period="handlePeriodChange"
          />
          <CoreMetrics
            :basics="basics"
            :financial-snapshot="financialSnapshot"
            :factor-warning-entries="detailFactorWarningEntries"
            :factor-diagnostic-entries="detailFactorDiagnosticEntries"
          />
        </div>

        <!-- 我的持仓 -->
        <MyPositionCard
          :real="positionData.real"
          :is-etf="isEtf"
          :quote-price="quote.price"
          :position-summary="positionSummary"
          :first-buy-date="positionData.real.buy_date"
          :weight-pct="positionData.real.weight_pct"
          @add-position="showAddPositionDialog"
          @go-position-analysis="goToPositionAnalysis"
          @go-trade-review="goToTradeReview"
        />

        <!-- 最新单股分析结果 -->
        <AnalysisResultCard
          :analysis-status="analysisStatus"
          :analysis-progress="analysisProgress"
          :analysis-message="analysisMessage"
          :last-analysis="lastAnalysis"
          :last-task-info="lastTaskInfo"
          :one-sentence-conclusion="oneSentenceConclusion"
          :report-keys="reportKeys"
          :history-count="analysisHistoryCount"
          :last-judgment="lastJudgment"
          @analyze="onAnalyze"
          @view-reports="showReportsDialog = true"
          @open-report="openReport"
          @view-history="goToAnalysisHistory"
        />
      </el-tab-pane>

      <!-- ===== 行业面板（可选模块：有行业世界模型才展示详细内容） ===== -->
      <el-tab-pane label="行业面板" name="industry" lazy>
        <IndustryPanel :stock-name="stockName" />
      </el-tab-pane>

      <!-- ===== 事实层：基本面 + 财务 + 新闻公告 ===== -->
      <el-tab-pane label="事实层" name="facts" lazy>
        <BottomSection
          :is-etf="isEtf"
          :basics="basics"
          :financial-snapshot="financialSnapshot"
          :etf-basics="etfBasics"
          :financial-raw-sections="financialRawSections"
          :news-items="newsItems"
          :news-filter="newsFilter"
          :news-loading="newsLoading"
          :news-source="newsSource"
          @news-filter-change="(v: string) => newsFilter = v"
        />
      </el-tab-pane>

      <!-- ===== 概念关系（一期：行业世界模型派生 + 基础信息兜底） ===== -->
      <el-tab-pane label="概念关系" name="concept" lazy>
        <div class="concept-pane">
          <el-card shadow="never" class="concept-card">
            <template #header>
              <div class="concept-card-header">
                <span class="concept-card-title">所属概念与主题</span>
                <span v-if="conceptSubText" class="concept-sub">{{ conceptSubText }}</span>
              </div>
            </template>
            <template v-if="conceptTags.length">
              <div class="concept-tags">
                <el-tooltip
                  v-for="t in conceptTags"
                  :key="t.name"
                  :content="`来源：${t.source} · 强度：${t.strength === 'strong' ? '强（多源确认）' : '弱（单源待复核）'}`"
                  placement="top"
                >
                  <el-tag
                    size="large"
                    class="concept-tag"
                    :type="t.strength === 'strong' ? 'primary' : 'info'"
                    :effect="t.strength === 'strong' ? 'light' : 'plain'"
                  >
                    {{ t.strength === 'strong' ? '● ' : '○ ' }}{{ t.name }}
                  </el-tag>
                </el-tooltip>
              </div>
              <div class="concept-source-line">共 {{ conceptTags.length }} 项概念 · 强标记 = 多源确认 · 弱标记 = 单源待复核</div>
            </template>
            <el-empty v-else description="暂无概念数据：该股未接入行业世界模型，且基础信息中缺少行业分类">
              <template #image><el-icon :size="48" color="#C0C4CC"><Share /></el-icon></template>
            </el-empty>
          </el-card>

          <el-card v-if="conceptRelations.length" shadow="never" class="concept-card">
            <template #header>
              <div class="concept-card-header">
                <span class="concept-card-title">关联对象</span>
                <span class="concept-sub">点击卡片可跳转</span>
              </div>
            </template>
            <el-row :gutter="12">
              <el-col v-for="r in conceptRelations" :key="r.name" :xs="24" :sm="12" :md="8">
                <el-card shadow="hover" class="relation-card" @click="r.go && r.go()">
                  <div class="relation-head">
                    <span class="relation-name">{{ r.name }}</span>
                    <el-tag size="small" :type="r.tagType" effect="plain">{{ r.relation }}</el-tag>
                  </div>
                  <div v-if="r.code" class="relation-code">{{ r.code }}</div>
                  <div class="relation-note">{{ r.note }}</div>
                </el-card>
              </el-col>
            </el-row>
            <div class="concept-source-line">共 {{ conceptRelations.length }} 项关联 · 关系类型来自行业世界模型</div>
          </el-card>
        </div>
      </el-tab-pane>

      <!-- ===== 我的研究：持仓分析 + 交易复盘 + 留痕 ===== -->
      <el-tab-pane label="我的研究" name="mine" lazy>
        <!-- 【置顶·今日待办】P0 重组：待验证假设 + 最新每日结论摘要，一键去复盘 -->
        <el-card shadow="never" class="mine-tasks-card mine-todo-card">
          <template #header>
            <div class="mine-card-header">
              <span class="mine-card-title">今日待办</span>
              <span class="pig-plan-sub">假设待验证与最新结论 · 不构成投资建议</span>
            </div>
          </template>
          <div class="mine-todo-rows">
            <div class="mine-todo-row">
              <span class="mine-todo-icon">⚡</span>
              <span class="mine-todo-text">
                <template v-if="openHypothesisCount > 0">
                  <b>{{ openHypothesisCount }}</b> 条待验证假设等你复盘
                </template>
                <template v-else>暂无待验证假设</template>
              </span>
              <el-button
                v-if="openHypothesisCount > 0"
                size="small" type="primary" plain
                @click="scrollToJournal"
              >一键去复盘</el-button>
            </div>
            <div v-if="dailyReview" class="mine-todo-row">
              <span class="mine-todo-icon">📋</span>
              <span class="mine-todo-text">
                {{ dailyReview.date }} 每日结论已生成（{{ dailyReviewCoverageLabel }}）
                <span class="mine-todo-clip">{{ dailyReview.summary }}</span>
              </span>
              <el-button link type="primary" size="small" @click="scrollToDailyReview">看全文</el-button>
            </div>
          </div>
        </el-card>

        <!-- 【结论与计划】猪周期计划 + 最新每日结论 -->
        <div class="mine-section-label">结论与计划</div>

        <!-- 猪周期计划与规则提醒（行业世界模型 · 仅覆盖猪周期龙头） -->
        <el-card v-if="pigCovered" shadow="never" class="mine-tasks-card pig-plan-card">
          <template #header>
            <div class="mine-card-header">
              <span class="mine-card-title">猪周期计划与规则提醒</span>
              <span class="pig-plan-sub">来自行业世界模型 · 档位非操作建议，最终由你决定</span>
            </div>
          </template>
          <template v-if="pigPlan">
            <div class="pig-plan-head">
              <el-tag size="small" type="success" effect="light">进行中</el-tag>
              <span class="pig-plan-grade">
                当前定级 <b>{{ pigPlan.grade_snapshot?.grade || '—' }}</b>{{ pigPlan.grade_snapshot?.sub_tag ? ' · ' + pigPlan.grade_snapshot.sub_tag : '' }}
              </span>
              <span v-if="pigPlan.opened_at" class="pig-plan-date">开启于 {{ pigPlan.opened_at.slice(0, 10) }}</span>
            </div>
            <div class="pig-plan-rule">仓位规则参考：{{ pigPlan.grade_snapshot?.position_rule || '—' }}</div>
            <template v-if="pigPlan.lights">
              <div class="pig-plan-section">升级票（{{ pigPlan.lights.votes_yes }}/{{ pigPlan.lights.votes_available }}，需 {{ pigPlan.lights.votes_required }} 票）</div>
              <div v-for="t in pigPlan.lights.tickets" :key="t.key" class="pig-plan-item">
                <span class="pig-plan-dot" :class="'is-' + t.state"></span>
                <span class="pig-plan-name">{{ t.name }}</span>
                <span class="pig-plan-basis">{{ t.basis || (t.state === 'gap' ? '数据源暂缺，该票不计入' : '条件未满足') }}</span>
              </div>
              <el-alert v-if="pigPlan.lights.upgrade_ready" type="warning" :closable="false" show-icon class="pig-plan-ready">
                <template #title>升级票已凑齐（{{ pigPlan.lights.votes_yes }}/{{ pigPlan.lights.votes_available }}）· 不自动操作，是否升级由你决定</template>
              </el-alert>
              <div class="pig-plan-section">看错信号</div>
              <div class="pig-plan-item">
                <span class="pig-plan-dot" :class="pigPlan.lights.falsifier?.triggered ? 'is-triggered' : 'is-off'"></span>
                <span class="pig-plan-name">{{ pigPlan.lights.falsifier?.name || '看错信号（能繁回升）' }}</span>
                <span class="pig-plan-basis">
                  {{ pigPlan.lights.falsifier?.triggered ? '已触发，去化逻辑被推翻' : '未触发' }}
                  <template v-if="pigPlan.lights.falsifier?.rule">（{{ pigPlan.lights.falsifier.rule }}）</template>
                </span>
              </div>
            </template>
            <div v-if="pigPlan.note" class="pig-plan-note">计划备注：{{ pigPlan.note }}</div>
          </template>
          <div v-else class="pig-plan-empty">
            当前没有进行中的研究计划。可在「行业面板」按当前定级开启作战计划，开启后这里会显示定级快照、升级票与看错信号提醒。
          </div>
        </el-card>

        <!-- 最新每日结论（持仓视角闭环：每日 08:50 生成，规则事实 + AI 总结，只看不推） -->
        <el-card v-if="dailyReview" id="mine-daily-review-anchor" shadow="never" class="mine-tasks-card pig-plan-card">
          <template #header>
            <div class="mine-card-header">
              <span class="mine-card-title">最新每日结论</span>
              <el-tag
                v-if="dailyReview.risk_badge === 'restructuring'"
                size="small"
                type="warning"
                effect="plain"
              >重整股 · 信号参考性弱</el-tag>
              <el-tag
                v-else-if="dailyReview.risk_badge === 'small_cap'"
                size="small"
                type="info"
                effect="plain"
              >小盘股 · 信号参考性弱</el-tag>
              <span class="pig-plan-sub">
                {{ dailyReview.date }} 生成 · {{ dailyReviewCoverageLabel }} · {{ dailyReview.llm_used ? 'AI 总结' : '规则模板' }}
              </span>
            </div>
          </template>
          <div class="daily-review-summary">{{ dailyReview.summary }}</div>
          <div v-if="dailyReviewHasSignals" class="daily-review-fuses">
            <el-tag
              v-for="f in dailyReviewFuseRows"
              :key="f.key"
              size="small"
              :type="f.tag"
              effect="plain"
            >{{ f.key }}保险丝：{{ f.label }}</el-tag>
          </div>
          <div v-if="dailyReview.coverage === 'signals_mv'" class="pig-plan-sub" style="margin-top: 6px">
            成本锚点未覆盖，暂无隐含定价读数；周线/保险丝/头均市值分位正常提供。
          </div>
          <div v-if="dailyReview.coverage === 'signals_only'" class="pig-plan-sub" style="margin-top: 6px">
            估值数据暂缺（市值/出栏锚点未覆盖），仅提供周线读数。
          </div>
          <div v-if="dailyReview.coverage === 'partial'" class="pig-plan-empty">
            该标的不在猪周期信号覆盖清单（17 家 A 股猪企），结论只述事实，不给规则读数。
          </div>
        </el-card>

        <!-- 【我的判断】研究日志 + 复盘对照（研究闭环 4.1/4.2） -->
        <div id="mine-journal-anchor" class="mine-section-label">我的判断</div>
        <ResearchJournalPanel
          ref="journalPanelRef"
          :stock-code="code"
          :stock-name="stockName"
          @review-summary="onJournalReviewSummary"
        />

        <!-- 【持仓与任务】低频内容默认折叠（P0 重组） -->
        <el-collapse class="mine-collapse">
          <el-collapse-item name="position" title="持仓与任务">
            <PositionReviewTabs
          :position-summary="positionSummary"
          :review-summary="reviewSummary"
          :position-data="positionData"
          :review-history="reviewHistory"
          :position-history-count="positionHistoryCount"
          @go-position-analysis="goToPositionAnalysis"
          @go-trade-review="goToTradeReview"
          @view-position-task-detail="viewPositionTaskDetail"
          @view-review-task-detail="viewReviewTaskDetail"
          @view-position-history="goToPositionHistory"
          @view-review-history="goToReviewHistory"
          @select-review-item="selectReviewItem"
        />

        <!-- 该股相关研究任务与历史报告 -->
        <el-card shadow="never" class="mine-tasks-card">
          <template #header>
            <div class="mine-card-header">
              <span class="mine-card-title">研究任务与历史报告</span>
              <el-button link type="primary" size="small" @click="goToAnalysisHistory">查看全部 →</el-button>
            </div>
          </template>
          <div v-loading="stockTasksLoading">
            <el-table :data="stockTasks" size="small" empty-text="还没有针对此股票的研究任务">
              <el-table-column label="任务" min-width="260">
                <template #default="{ row }">
                  <el-link type="primary" :underline="false" @click="viewStockTask(row)">{{ stockTaskTitle(row) }}</el-link>
                </template>
              </el-table-column>
              <el-table-column label="类型" width="120">
                <template #default="{ row }">{{ stockTaskTypeText(row.task_type) }}</template>
              </el-table-column>
              <el-table-column label="状态" width="100">
                <template #default="{ row }">
                  <el-tag size="small" :type="stockTaskStatusType(row.status)" effect="light">{{ stockTaskStatusText(row.status) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="完成时间" width="170">
                <template #default="{ row }">{{ formatTaskTime(row.completed_at || row.created_at) }}</template>
              </el-table-column>
            </el-table>
          </div>
        </el-card>
          </el-collapse-item>
        </el-collapse>
      </el-tab-pane>

      <!-- ===== 我的资料（收藏链接 + 文字笔记 + 上传文件） ===== -->
      <el-tab-pane label="我的资料" name="materials" lazy>
        <div class="materials-pane">
          <div class="materials-toolbar">
            <span class="materials-hint">收藏链接、文字笔记与上传文件（PDF/Word/Excel/TXT/MD/CSV/PPT/图片，≤20MB），仅本人可见</span>
            <span class="materials-toolbar-btns">
              <el-button size="small" :loading="uploading" :icon="Upload" @click="triggerMaterialUpload">
                {{ uploading ? `上传中 ${uploadProgress}%` : '上传文件' }}
              </el-button>
              <el-button type="primary" size="small" @click="openMaterialDialog()">+ 新增资料</el-button>
            </span>
            <input ref="materialFileInput" type="file" class="materials-file-input" @change="onMaterialFileChosen" />
          </div>
          <!-- 分类/信源筛选（纯前端过滤） -->
          <div v-if="stockMaterials.length" class="materials-filters">
            <el-select v-model="materialCategoryFilter" size="small" class="materials-filter-select">
              <el-option label="全部分类" value="all" />
              <el-option v-for="c in MATERIAL_CATEGORY_OPTIONS" :key="c.value" :label="c.label" :value="c.value" />
            </el-select>
            <el-select v-model="materialTierFilter" size="small" class="materials-filter-select">
              <el-option label="全部信源" value="all" />
              <el-option v-for="t in MATERIAL_SOURCE_TIER_OPTIONS" :key="t.value" :label="t.label" :value="t.value" />
            </el-select>
            <span v-if="filteredStockMaterials.length !== stockMaterials.length" class="materials-filter-count">
              {{ filteredStockMaterials.length }}/{{ stockMaterials.length }} 条
            </span>
          </div>
          <div v-loading="materialsLoading">
            <template v-if="filteredStockMaterials.length">
              <el-card v-for="m in filteredStockMaterials" :key="m.id" shadow="never" class="material-item">
                <div class="material-head">
                  <el-tag size="small" :type="m.kind === 'url' ? 'primary' : m.kind === 'file' ? 'warning' : 'success'" effect="plain">
                    {{ m.kind === 'url' ? '链接' : m.kind === 'file' ? '文件' : '笔记' }}
                  </el-tag>
                  <span class="material-title" :title="m.source_note || m.title">{{ m.title }}</span>
                  <el-tag size="small" effect="plain" class="material-meta-tag">{{ materialCategoryLabel(m.category) }}</el-tag>
                  <el-tag
                    size="small"
                    effect="light"
                    class="material-meta-tag"
                    :type="materialSourceTierTagType(m.source_tier)"
                    :title="m.source_note ? `原始出处：${m.source_note}` : materialSourceTierLabel(m.source_tier)"
                  >
                    {{ materialSourceTierLabel(m.source_tier) }}
                  </el-tag>
                  <el-tag v-if="m.intel_card_id" size="small" type="success" effect="plain" class="material-meta-tag" title="已提炼知识卡进入猪周期知识库，AI 分析可引用">已提炼</el-tag>
                  <span class="material-actions">
                    <el-button v-if="m.kind === 'url'" link type="primary" size="small" @click="openMaterialLink(m.url)">打开</el-button>
                    <el-button v-if="m.kind === 'file'" link type="primary" size="small" @click="previewMaterialText(m)">预览</el-button>
                    <el-button v-if="m.kind !== 'url'" link type="primary" size="small" @click="openIntelCard(m)">知识卡</el-button>
                    <el-button link type="primary" size="small" @click="openMaterialDialog(m)">编辑</el-button>
                    <el-button link type="danger" size="small" @click="deleteMaterial(m)">删除</el-button>
                  </span>
                </div>
                <a v-if="m.kind === 'url' && m.url" class="material-url" :href="m.url" target="_blank" rel="noopener">{{ materialHost(m) }} · {{ m.url }}</a>
                <div v-if="m.kind === 'note' && m.content" class="material-content">{{ m.content }}</div>
                <template v-if="m.kind === 'file'">
                  <div class="material-file-meta">
                    <span class="material-file-name">{{ m.filename }} · {{ formatFileSize(m.file_size) }}</span>
                    <el-tag v-if="m.text_ok" size="small" type="success" effect="plain">已提取文本</el-tag>
                    <el-tag v-else size="small" type="info" effect="plain">{{ m.text_message || '未提取文本' }}</el-tag>
                  </div>
                  <div v-if="m.extracted_text" class="material-excerpt" title="点击查看提取全文" @click="previewMaterialText(m)">{{ m.extracted_text }}</div>
                </template>
              </el-card>
            </template>
            <el-empty
              v-else-if="!materialsLoading"
              :description="stockMaterials.length ? '没有符合筛选条件的资料' : '还没有收藏资料，点击右上角「新增资料」开始'"
            >
              <template #image><el-icon :size="48" color="#C0C4CC"><FolderOpened /></el-icon></template>
            </el-empty>
          </div>

          <!-- 文件提取文本预览对话框（拉全文 + 按【】标题分节展示 AI 解读） -->
          <el-dialog v-model="materialPreviewVisible" :title="materialPreviewItem?.title || '文件预览'" width="640px" append-to-body>
            <div v-loading="materialPreviewLoading" class="material-preview-body">
              <template v-if="materialPreviewSections.length">
                <div v-for="(sec, i) in materialPreviewSections" :key="i" class="material-preview-section">
                  <div v-if="sec.title" class="material-preview-section-title">{{ sec.title }}</div>
                  <div class="material-preview-section-body">{{ sec.body }}</div>
                </div>
              </template>
              <div v-else class="material-preview-text">未提取到文本</div>
              <div v-if="materialPreviewItem?.remark" class="material-preview-remark">备注：{{ materialPreviewItem.remark }}</div>
              <div v-if="materialPreviewItem?.text_message" class="material-preview-meta">{{ materialPreviewItem.text_message }}</div>
            </div>
            <template #footer>
              <el-button
                v-if="materialPreviewItem && canReextractMaterial(materialPreviewItem)"
                type="warning" plain :loading="materialReextracting"
                @click="reextractPreviewMaterial"
              >重新提取</el-button>
              <el-button v-if="materialPreviewItem" type="primary" plain @click="openMaterialFile(materialPreviewItem)">下载原文件</el-button>
              <el-button @click="materialPreviewVisible = false">关闭</el-button>
            </template>
          </el-dialog>

          <!-- 知识卡对话框（资料经大模型提炼的用户情报卡，写入猪周期知识库，可重新提炼覆盖） -->
          <el-dialog v-model="intelCardVisible" :title="intelCard?.title || '知识卡'" width="560px" append-to-body>
            <div v-loading="intelCardLoading" class="intel-card-body">
              <template v-if="intelCard">
                <div class="intel-card-meta">
                  <el-tag size="small" :type="materialSourceTierTagType(intelCard.body?.source_tier)" effect="light">
                    {{ materialSourceTierLabel(intelCard.body?.source_tier) }}
                  </el-tag>
                  <span v-if="intelCard.stock_code" class="intel-card-meta-text">{{ intelCard.stock_code }}</span>
                  <span v-if="intelCard.updated_at" class="intel-card-meta-text">{{ formatIntelTime(intelCard.updated_at) }}提炼</span>
                </div>
                <div class="intel-card-points">
                  <div v-for="(p, i) in intelCard.body?.points || []" :key="i" class="intel-card-point">
                    <span class="intel-card-point-no">{{ i + 1 }}</span>
                    <span class="intel-card-point-text">{{ p }}</span>
                  </div>
                </div>
                <div v-if="intelCard.body?.caveats" class="intel-card-caveats">
                  <span class="intel-card-caveats-label">注意</span>
                  <span>{{ intelCard.body.caveats }}</span>
                </div>
                <div v-if="intelCard.tag?.length" class="intel-card-tags">
                  <el-tag v-for="t in intelCard.tag" :key="t" size="small" effect="plain" type="info">{{ t }}</el-tag>
                </div>
                <div v-if="intelCard.source_ref" class="intel-card-source" :title="intelCard.source_ref">溯源：{{ intelCard.source_ref }}</div>
              </template>
              <el-empty v-else-if="!intelCardLoading" description="尚未提炼知识卡，点击下方按钮开始" :image-size="80" />
            </div>
            <template #footer>
              <el-button
                v-if="intelCardMaterial && intelCardMaterial.kind !== 'url'"
                type="primary" plain :loading="intelCardDistilling"
                @click="distillIntelCard"
              >{{ intelCard ? '重新提炼' : '提炼知识卡' }}</el-button>
              <el-button @click="intelCardVisible = false">关闭</el-button>
            </template>
          </el-dialog>

          <!-- 新增/编辑资料对话框 -->
          <el-dialog v-model="materialDialogVisible" :title="editingMaterialId ? '编辑资料' : '新增资料'" width="520px" append-to-body>
            <el-form label-width="70px">
              <el-form-item label="类型">
                <el-radio-group v-model="materialForm.kind" :disabled="!!editingMaterialId">
                  <el-radio-button label="url">收藏链接</el-radio-button>
                  <el-radio-button label="note">文字笔记</el-radio-button>
                  <el-radio-button label="file" disabled>上传文件</el-radio-button>
                </el-radio-group>
              </el-form-item>
              <el-form-item label="标题">
                <el-input v-model="materialForm.title" placeholder="给这条资料起个名字" maxlength="80" show-word-limit />
              </el-form-item>
              <el-form-item v-if="materialForm.kind === 'url'" label="链接">
                <el-input v-model="materialForm.url" placeholder="https://..." />
              </el-form-item>
              <el-form-item v-else-if="materialForm.kind === 'note'" label="内容">
                <el-input v-model="materialForm.content" type="textarea" :rows="5" placeholder="记录你的研究笔记…" maxlength="5000" show-word-limit />
              </el-form-item>
              <el-form-item v-else label=" ">
                <span class="material-file-hint">文件类型仅支持修改标题；如需替换文件请删除后重新上传</span>
              </el-form-item>
              <el-form-item label="分类">
                <el-select v-model="materialForm.category">
                  <el-option v-for="c in MATERIAL_CATEGORY_OPTIONS" :key="c.value" :label="c.label" :value="c.value" />
                </el-select>
              </el-form-item>
              <el-form-item label="信源等级">
                <el-select v-model="materialForm.source_tier">
                  <el-option
                    v-for="t in MATERIAL_SOURCE_TIER_OPTIONS"
                    :key="t.value"
                    :label="t.label"
                    :value="t.value"
                  />
                </el-select>
                <span class="material-meta-tip">信源等级影响 AI 分析与世界模型的证据权重</span>
              </el-form-item>
              <el-form-item label="原始出处">
                <el-input v-model="materialForm.source_note" placeholder="如：2025Q3 业绩会交流纪要（选填）" maxlength="120" />
              </el-form-item>
              <el-form-item label="备注">
                <el-input
                  v-model="materialForm.remark"
                  type="textarea" :autosize="{ minRows: 2, maxRows: 4 }"
                  placeholder="补充背景说明（选填），如资料背景、结论要点、使用注意事项等，供 AI 分析时参考"
                  maxlength="500" show-word-limit
                />
              </el-form-item>
            </el-form>
            <template #footer>
              <el-button @click="materialDialogVisible = false">取消</el-button>
              <el-button type="primary" :loading="materialSaving" @click="saveMaterial">保存</el-button>
            </template>
          </el-dialog>

          <!-- 上传设置对话框（选文件后确认元信息，信源等级影响证据权重） -->
          <el-dialog v-model="uploadSettingsVisible" title="上传设置" width="480px" append-to-body :close-on-click-modal="!uploading">
            <div v-if="pendingUploadFile" class="material-upload-file">
              {{ pendingUploadFile.name }} · {{ formatFileSize(pendingUploadFile.size) }}
            </div>
            <el-form label-width="70px">
              <el-form-item label="标题">
                <el-input v-model="uploadForm.title" placeholder="资料标题（默认文件名）" maxlength="80" show-word-limit />
              </el-form-item>
              <el-form-item label="分类">
                <el-select v-model="uploadForm.category">
                  <el-option v-for="c in MATERIAL_CATEGORY_OPTIONS" :key="c.value" :label="c.label" :value="c.value" />
                </el-select>
              </el-form-item>
              <el-form-item label="信源等级">
                <el-select v-model="uploadForm.source_tier">
                  <el-option
                    v-for="t in MATERIAL_SOURCE_TIER_OPTIONS"
                    :key="t.value"
                    :label="t.label"
                    :value="t.value"
                  />
                </el-select>
                <span class="material-meta-tip">调研纪要/内部数据请选「内部一手」，权重最高</span>
              </el-form-item>
              <el-form-item label="原始出处">
                <el-input v-model="uploadForm.source_note" placeholder="如：某券商 9 月深度报告（选填）" maxlength="120" />
              </el-form-item>
              <el-form-item label="备注">
                <el-input
                  v-model="uploadForm.remark"
                  type="textarea" :autosize="{ minRows: 2, maxRows: 4 }"
                  placeholder="补充背景说明（选填），如资料背景、结论要点、使用注意事项等，供 AI 分析时参考"
                  maxlength="500" show-word-limit
                />
              </el-form-item>
            </el-form>
            <template #footer>
              <el-button :disabled="uploading" @click="uploadSettingsVisible = false">取消</el-button>
              <el-button type="primary" :loading="uploading" @click="confirmMaterialUpload">
                {{ uploading ? `上传中 ${uploadProgress}%` : '开始上传' }}
              </el-button>
            </template>
          </el-dialog>
        </div>
      </el-tab-pane>

      <!-- ===== 完整时间线（一期：前端聚合已有数据，非新建数据源） ===== -->
      <el-tab-pane label="完整时间线" name="timeline" lazy>
        <div class="timeline-pane">
          <div class="timeline-toolbar">
            <span class="timeline-meta">行情异动 · 新闻公告 · 研究任务 · 交易复盘 · 操作留痕</span>
            <el-radio-group v-model="timelineRange" size="small">
              <el-radio-button label="60d">近 60 天</el-radio-button>
              <el-radio-button label="all">全部</el-radio-button>
            </el-radio-group>
          </div>
          <div v-loading="timelineMovesLoading">
            <el-timeline v-if="timelineItems.length" class="stock-timeline">
              <el-timeline-item
                v-for="(it, i) in timelineItems"
                :key="i"
                :timestamp="it.time"
                :type="it.kindType"
                placement="top"
              >
                <div class="tl-item">
                  <el-tag size="small" :type="it.kindType" effect="light" class="tl-kind">{{ it.kind }}</el-tag>
                  <span class="tl-title" :class="{ 'is-link': !!it.url }" @click="it.url && openExternal(it.url)">{{ it.title }}</span>
                </div>
                <div v-if="it.detail" class="tl-detail">{{ it.detail }}</div>
                <div v-if="it.source" class="tl-source">来源：{{ it.source }}</div>
              </el-timeline-item>
            </el-timeline>
            <el-empty v-else description="暂无时间线记录（行情异动、新闻公告、研究任务、操作留痕）">
              <template #image><el-icon :size="48" color="#C0C4CC"><Timer /></el-icon></template>
            </el-empty>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- ════════ 智能助手对话区（Tab 外常驻，任意 Tab 都可提问） ════════ -->
    <AssistantChat
      ref="assistantChatRef"
      v-model:messages="assistantMessages"
      :code="code"
      :stock-name="stockName"
      :loaded-modules="assistantLoadedModules"
      :initial-prompt="assistantInitialPrompt"
      :loading="assistantLoading"
      input-placeholder="输入问题，例如：结合分析和持仓，我下一步应该重点跟踪什么？"
      @ask="handleAssistantAsk"
    />

    <!-- 回到顶部 -->
    <BackToTop :show-after="600" />

    <!-- 添加持仓对话框 -->
    <AddPositionDialog
      v-model:visible="addPositionDialogVisible"
      :initial-data="addPositionInitialData"
      @success="onAddPositionSuccess"
    />

    <!-- ════════ 对话框（保留原有逻辑） ════════ -->

    <!-- 详细报告对话框 -->
    <el-dialog
      v-model="showReportsDialog"
      title="📊 详细分析报告"
      width="80%"
      :close-on-click-modal="false"
      class="reports-dialog"
    >
      <el-tabs v-model="activeReportTab" type="border-card">
        <el-tab-pane
          v-for="key in reportKeys"
          :key="key"
          :label="formatReportName(key)"
          :name="key"
        >
          <div class="report-content">
            <el-scrollbar height="500px">
              <div class="markdown-body" v-html="renderMarkdown(getReportContent(lastAnalysis?.reports?.[key]))"></div>
            </el-scrollbar>
          </div>
        </el-tab-pane>
      </el-tabs>

      <template #footer>
        <el-button @click="showReportsDialog = false">关闭</el-button>
        <el-button type="primary" @click="exportReport">导出报告</el-button>
      </template>
    </el-dialog>

    <!-- 数据同步对话框 -->
    <el-dialog
      v-model="syncDialogVisible"
      :title="syncDialogTitle"
      width="500px"
    >
      <el-form :model="syncForm" label-width="120px">
        <el-form-item :label="securityCodeLabel">
          <el-input v-model="code" disabled />
        </el-form-item>
        <el-form-item :label="isEtf ? 'ETF名称' : '股票名称'">
          <el-input v-model="stockName" disabled />
        </el-form-item>
        <el-form-item label="同步内容">
          <el-checkbox-group v-model="syncForm.syncTypes">
            <el-checkbox label="realtime">实时行情</el-checkbox>
            <el-checkbox label="historical">历史行情数据</el-checkbox>
            <el-checkbox v-if="!isEtf" label="financial">财务数据</el-checkbox>
            <el-checkbox label="basic">基础数据</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="数据源">
          <el-radio-group v-model="syncForm.dataSource">
            <el-radio label="tushare" :disabled="!availableSyncSources.tushare">Tushare</el-radio>
            <el-radio label="akshare" :disabled="!availableSyncSources.akshare">AKShare</el-radio>
            <el-radio v-if="!isJdyunMode()" label="qmt" :disabled="!availableSyncSources.qmt">QMT</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="历史数据天数" v-if="syncForm.syncTypes.includes('historical')">
          <el-input-number v-model="syncForm.days" :min="1" :max="3650" />
          <span style="margin-left: 10px; color: #909399; font-size: 12px;">
            (最多3650天，约10年)
          </span>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="syncDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSync" :loading="syncLoading">
          开始同步
        </el-button>
      </template>
    </el-dialog>

    <!-- 复盘详情对话框 -->
    <el-dialog
      v-model="reviewDetailVisible"
      title="复盘详情"
      width="800px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <div v-if="reviewDetailLoading" class="detail-loading">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>加载中...</span>
      </div>
      <div v-else-if="currentReviewDetail" class="review-detail-content">
        <!-- 交易摘要 -->
        <el-descriptions title="交易摘要" :column="3" border size="small" class="section">
          <el-descriptions-item label="股票代码">{{ currentReviewDetail.trade_info?.code }}</el-descriptions-item>
          <el-descriptions-item label="持仓天数">{{ currentReviewDetail.trade_info?.holding_days }}天</el-descriptions-item>
          <el-descriptions-item label="盈亏金额">
            <span :class="getTotalPnl() >= 0 ? 'positive' : 'negative'">
              {{ formatPnlValue(getTotalPnl()) }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="买入均价">{{ currentReviewDetail.trade_info?.avg_buy_price?.toFixed(2) }}</el-descriptions-item>
          <el-descriptions-item label="卖出均价">{{ currentReviewDetail.trade_info?.avg_sell_price?.toFixed(2) }}</el-descriptions-item>
          <el-descriptions-item label="收益率">
            <span :class="getTotalPnlPct() >= 0 ? 'positive' : 'negative'">
              {{ formatPct(getTotalPnlPct()) }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="手续费" :span="3">{{ currentReviewDetail.trade_info?.total_commission?.toFixed(2) }}元</el-descriptions-item>
        </el-descriptions>

        <!-- 复盘结论 -->
        <div class="section">
          <h4 class="section-title">复盘结论</h4>
          <div class="summary markdown-content" v-html="renderMarkdown(currentReviewDetail.ai_review?.summary)"></div>
        </div>

        <!-- 优缺点 -->
        <el-row :gutter="16" class="section">
          <el-col :span="12">
            <div class="analysis-card strengths">
              <h4><el-icon><CircleCheck /></el-icon> 做得好的地方</h4>
              <div class="markdown-content" v-html="renderMarkdown((currentReviewDetail.ai_review?.strengths || []).join('\n\n'))"></div>
            </div>
          </el-col>
          <el-col :span="12">
            <div class="analysis-card weaknesses">
              <h4><el-icon><Warning /></el-icon> 暴露的问题</h4>
              <div class="markdown-content" v-html="renderMarkdown((currentReviewDetail.ai_review?.weaknesses || []).join('\n\n'))"></div>
            </div>
          </el-col>
        </el-row>

        <!-- 复盘改进项 -->
        <div class="section" v-if="currentReviewDetail.ai_review?.suggestions?.length">
          <h4 class="section-title"><el-icon><Pointer /></el-icon> 后续改进重点</h4>
          <div class="suggestions markdown-content" v-html="renderMarkdown((currentReviewDetail.ai_review?.suggestions || []).join('\n\n'))"></div>
        </div>

        <!-- 详细分析 -->
        <el-collapse class="section">
          <el-collapse-item title="时机复盘" name="timing" v-if="currentReviewDetail.ai_review?.timing_analysis">
            <div class="markdown-content" v-html="renderMarkdown(currentReviewDetail.ai_review?.timing_analysis)"></div>
          </el-collapse-item>
          <el-collapse-item title="仓位复盘" name="position" v-if="currentReviewDetail.ai_review?.position_analysis">
            <div class="markdown-content" v-html="renderMarkdown(currentReviewDetail.ai_review?.position_analysis)"></div>
          </el-collapse-item>
          <el-collapse-item title="情绪复盘" name="emotion" v-if="currentReviewDetail.ai_review?.emotion_analysis">
            <div class="markdown-content" v-html="renderMarkdown(currentReviewDetail.ai_review?.emotion_analysis)"></div>
          </el-collapse-item>
          <el-collapse-item title="归因复盘" name="attribution" v-if="currentReviewDetail.ai_review?.attribution_analysis">
            <div class="markdown-content" v-html="renderMarkdown(currentReviewDetail.ai_review?.attribution_analysis)"></div>
          </el-collapse-item>
        </el-collapse>
      </div>
      <template #footer>
        <el-button @click="reviewDetailVisible = false">关闭</el-button>
      </template>
    </el-dialog>

  </div>
</template>


<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Loading, CircleCheck, Warning, Pointer, Share, FolderOpened, Timer, Upload } from '@element-plus/icons-vue'
import { renderMarkdown } from '@/utils/markdown'
import { stocksApi } from '@/api/stocks'
import { assistantApi, type AssistantThreadItem } from '@/api/assistant'
import { ApiClient } from '@/api/request'
import {
  stockSyncApi,
  type SingleStockSyncResponse,
  type StockSyncTaskStatus,
} from '@/api/stockSync'
import { clearAllCache } from '@/api/cache'
import { recordStockView } from '@/pro/utils/recentViews'
import { use as echartsUse } from 'echarts/core'
import { CandlestickChart } from 'echarts/charts'

import { GridComponent, TooltipComponent, DataZoomComponent, LegendComponent, TitleComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsOption } from 'echarts'
import { favoritesApi } from '@/api/favorites'
import { useAuthStore } from '@/stores/auth'
import type { StockInfo } from '@/types/analysis'
import { getFactorDiagnosticEntries, getFactorWarningEntries } from '@/utils/factorPresentation'
import { loadManualSyncSourceState, type ManualSyncDataSource } from '@/utils/dataSource'
import { isJdyunMode } from '@/utils/config'
import { getReportName } from '@/utils/reportPresentation'
import { getTaskList, getTaskDetail, TaskType, TaskStatus } from '@/api/unifiedTasks'
import { reviewApi } from '@/api/review'
import { portfolioApi } from '@/api/portfolio'
import {
  fetchStockMaterials,
  addStockMaterial,
  updateStockMaterial,
  deleteStockMaterial,
  uploadStockMaterial,
  fetchMaterialText,
  reextractMaterialText,
  distillMaterialIntel,
  fetchMaterialIntelCard,
  materialFileUrl,
  MATERIAL_FILE_EXTENSIONS,
  MAX_MATERIAL_FILE_SIZE,
  MATERIAL_CATEGORY_OPTIONS,
  MATERIAL_SOURCE_TIER_OPTIONS,
  materialCategoryLabel,
  materialSourceTierLabel,
  materialSourceTierTagType,
  type StockMaterial,
  type IntelCard,
  type MaterialKind,
  type MaterialCategory,
  type MaterialSourceTier
} from '@/pro/api/stockMaterials'
import {
  fetchPigCycleState,
  fetchPigCycleL0,
  fetchTermWarnings,
  fetchPigCyclePlanCurrent,
  fetchDailyReviews,
  type PigCycleState,
  type PigCycleL0State,
  type TermWarnings,
  type PigCyclePlan,
  type DailyReviewItem,
} from '@/pro/api/pigCycle'
import { fuseTriggered } from '@/pro/utils/pigCycleDisplay'
import {
  matchIndustryStock,
  PIG_RELATED_STOCKS,
  INSURANCE_RELATED_STOCKS,
  BATTERY_RELATED_STOCKS,
  AUTO_RELATED_STOCKS,
} from '@/pro/config/industryRegistry'

// 新版股票详情页子组件
import StockOverview from './components/StockOverview.vue'
import AssistantHero from './components/AssistantHero.vue'
import KlineChart from './components/KlineChart.vue'
import CoreMetrics from './components/CoreMetrics.vue'
import OverviewTopStrip from './components/OverviewTopStrip.vue'
import MyPositionCard from './components/MyPositionCard.vue'
import IndustryPanel from './components/IndustryPanel.vue'
import AnalysisResultCard from './components/AnalysisResultCard.vue'
import PositionReviewTabs from './components/PositionReviewTabs.vue'
import ResearchJournalPanel from '@/pro/components/ResearchJournalPanel.vue'
import { researchJournalApi, type ResearchJournalEntry } from '@/pro/api/researchJournal'
import AssistantChat from './components/AssistantChat.vue'
import BottomSection from './components/BottomSection.vue'
import BackToTop from './components/BackToTop.vue'
import AddPositionDialog from '@/views/Portfolio/components/AddPositionDialog.vue'


echartsUse([CandlestickChart, GridComponent, TooltipComponent, DataZoomComponent, LegendComponent, TitleComponent, CanvasRenderer])

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const STOCK_SYNC_POLL_INTERVAL_MS = 2000
const STOCK_SYNC_POLL_MAX_ATTEMPTS = 300
let stockDetailDisposed = false


// 分析状态
const analysisStatus = ref<'idle' | 'running' | 'completed' | 'failed'>('idle')
const analysisProgress = ref(0)
const analysisMessage = ref('')
const lastAnalysis = ref<any | null>(null)
const lastTaskInfo = ref<any | null>(null) // 保存任务信息（包含 end_time 等）

// 报告对话框
const showReportsDialog = ref(false)
const activeReportTab = ref('')

const reportKeys = computed(() => Object.keys(lastAnalysis.value?.reports || {}))
const oneSentenceConclusion = computed(() => {
  const traderPlan = getReportContent(lastAnalysis.value?.reports?.trader_investment_plan)
  const conclusion = extractMarkdownSection(traderPlan, '一句话结论')
  return conclusion || lastAnalysis.value?.summary || '-'
})

// 股票代码（从路由参数获取）
watch(
  () => route.params.code,
  (value) => {
    if (String(value || '').trim()) {
      return
    }
    ElMessage.error('股票代码不能为空')
    router.push({ name: 'Dashboard' })
  },
  { immediate: true }
)

const code = computed(() => String(route.params.code || '').toUpperCase())
const symbol = computed(() => code.value.split('.')[0])  // 提取6位代码
const stockName = ref('')

// 浏览足迹：进入个股页即记录（名称异步就绪后自动补全），供研究台「最近研究」按真实时间排序
watch([symbol, stockName], ([sym, name]) => {
  if (sym) recordStockView(sym, name || '')
}, { immediate: true })
const market = ref('')
const isFav = ref(false)

const ETF_CODE_PREFIXES = ['50', '51', '52', '56', '58', '15', '16', '18']

function isLikelyEtfCode(value: string): boolean {
  const text = String(value || '').trim()
  return /^\d{6}$/.test(text) && ETF_CODE_PREFIXES.some(prefix => text.startsWith(prefix))
}

const isEtf = computed(() => market.value === 'ETF' || isLikelyEtfCode(symbol.value))
const marketLabel = computed(() => isEtf.value ? 'ETF' : (market.value || '-'))
const securityName = computed(() => isEtf.value ? 'ETF' : '股票')
const securityCodeLabel = computed(() => `${securityName.value}代码`)
const syncDialogTitle = computed(() => `同步${securityName.value}数据`)
const klineCardTitle = computed(() => isEtf.value ? 'ETF价格走势' : '价格K线')

// ECharts K线配置
const kOption = ref<EChartsOption>({
  grid: { left: 40, right: 20, top: 20, bottom: 40 },
  tooltip: {
    trigger: 'axis',
    axisPointer: { type: 'cross' }
  },
  xAxis: {
    type: 'category',
    data: [],
    boundaryGap: true,
    axisLine: { onZero: false }
  },
  yAxis: {
    scale: true,
    type: 'value'
  },
  dataZoom: [
    { type: 'inside', start: 70, end: 100 },
    { start: 70, end: 100 }
  ],
  series: [
    {
      type: 'candlestick',
      name: 'K线',
      data: [],
      itemStyle: {
        color: '#ef4444',
        color0: '#16a34a',
        borderColor: '#ef4444',
        borderColor0: '#16a34a'
      }
    }
  ]
})

const lastKTime = ref<string | null>(null)
const lastKClose = ref<number | null>(null)

// 报价（初始化）
const quote = reactive({
  price: NaN,
  changePercent: NaN,
  open: NaN,
  high: NaN,
  low: NaN,
  prevClose: NaN,
  volume: NaN,
  amount: NaN,
  turnover: NaN,
  amplitude: NaN,
  tradeDate: null as string | null,
  turnoverDate: null as string | null,
  amplitudeDate: null as string | null,
  updatedAt: null as string | null
})

const lastRefreshAt = ref<Date | null>(null)
const refreshText = computed(() => lastRefreshAt.value ? `已刷新 ${lastRefreshAt.value.toLocaleTimeString()}` : '未刷新')

// 同步状态
const syncStatus = ref<any>(null)

// 数据同步对话框
const syncDialogVisible = ref(false)
const syncLoading = ref(false)

// 添加持仓对话框
const addPositionDialogVisible = ref(false)
const addPositionInitialData = computed(() => ({
  code: code.value,
  name: stockName.value,
  market: isEtf.value ? 'ETF' : 'CN',
  cost_price: Number(quote.price) || undefined
}))
const availableSyncSources = reactive<Record<ManualSyncDataSource, boolean>>({
  tushare: true,
  akshare: true,
  qmt: true
})
const syncForm = reactive({
  syncTypes: ['realtime'],  // 默认选中实时行情
  dataSource: 'tushare' as ManualSyncDataSource,
  days: 365
})

watch(isEtf, (value) => {
  if (value) {
    syncForm.syncTypes = syncForm.syncTypes.filter(type => type !== 'financial')
  }
}, { immediate: true })

// 清除缓存
const clearCacheLoading = ref(false)

// 显示同步对话框
function showSyncDialog() {
  syncDialogVisible.value = true
}

// 显示添加持仓对话框
function showAddPositionDialog() {
  addPositionDialogVisible.value = true
}

function onAddPositionSuccess() {
  addPositionDialogVisible.value = false
  // 刷新持仓相关数据
  fetchPositionAnalysisSummary()
  fetchPositionData()
}

async function loadPreferredSyncDataSource() {
  try {
    const sourceState = await loadManualSyncSourceState()
    availableSyncSources.tushare = sourceState.availableSources.tushare
    availableSyncSources.akshare = sourceState.availableSources.akshare
    availableSyncSources.qmt = isJdyunMode() ? false : sourceState.availableSources.qmt

    if (sourceState.preferredSource) {
      // 京东云模式下，若首选是 qmt 则回退
      if (isJdyunMode() && sourceState.preferredSource === 'qmt') {
        // fall through to default selection
      } else {
        syncForm.dataSource = sourceState.preferredSource
        return
      }
    }

    if (availableSyncSources.qmt) {
      syncForm.dataSource = 'qmt'
    } else if (availableSyncSources.akshare) {
      syncForm.dataSource = 'akshare'
    } else if (availableSyncSources.tushare) {
      syncForm.dataSource = 'tushare'
    }
  } catch (error) {
    console.warn('加载同步数据源优先级失败，保留当前默认值', error)
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
      if (dataSourceUsed && dataSourceUsed !== syncForm.dataSource) {
        parts.push(`实时行情同步成功（已自动切换到 ${String(dataSourceUsed).toUpperCase()} 数据源）`)
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

const waitForStockSyncTask = async (taskId: string): Promise<StockSyncTaskStatus> => {
  for (let attempt = 0; attempt < STOCK_SYNC_POLL_MAX_ATTEMPTS; attempt += 1) {
    if (stockDetailDisposed) {
      throw new Error('页面已离开，停止等待同步结果')
    }

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
    if (stockDetailDisposed) return

    const message = buildSingleSyncTaskMessage(task, symbol)
    if (task.status === 'success') {
      ElMessage.success(message)
    } else if (task.status === 'success_with_errors') {
      ElMessage.warning(message)
    } else {
      ElMessage.error(message)
    }

    await Promise.all([
      fetchQuote(),
      fetchFundamentals(),
      fetchFinancials(),
      fetchKline(),
      fetchSyncStatus(),
    ])
  } catch (error: any) {
    if (!stockDetailDisposed && error?.message !== '页面已离开，停止等待同步结果') {
      ElMessage.error(error?.message || '同步结果查询失败，请稍后刷新页面查看')
    }
  }
}
// 执行同步
async function handleSync() {
  if (syncForm.syncTypes.length === 0) {
    ElMessage.warning('请至少选择一种同步内容')
    return
  }

  syncLoading.value = true
  try {
    const res = await stockSyncApi.syncSingle({
      symbol: code.value,
      sync_realtime: syncForm.syncTypes.includes('realtime'),
      sync_historical: syncForm.syncTypes.includes('historical'),
      sync_financial: syncForm.syncTypes.includes('financial'),
      sync_basic: syncForm.syncTypes.includes('basic'),
      data_source: syncForm.dataSource,
      days: syncForm.days
    })

    if (res.success) {
      ElMessage.success(`股票 ${code.value} 同步任务已提交，后台执行中`)
      syncDialogVisible.value = false
      void monitorSingleSyncTask(res.data.task_id, code.value)
    } else {
      ElMessage.error(res.message || '同步失败')
    }
  } catch (error: any) {
    console.error('同步失败:', error)
    ElMessage.error(error.message || '同步失败，请稍后重试')
  } finally {
    syncLoading.value = false
  }
}

async function refreshMockQuote() {
  // 改为调用后端接口获取真实数据
  await fetchQuote()
}

// 清除缓存
async function clearCache() {
  try {
    await ElMessageBox.confirm(
      '确定要清除所有缓存吗？清除后需要重新从数据源获取数据。',
      '清除缓存',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    clearCacheLoading.value = true
    await clearAllCache()
    ElMessage.success('缓存已清除，正在刷新数据...')

    // 刷新当前页面数据
    await Promise.all([
      fetchQuote(),
      fetchFundamentals(),
      fetchFinancials(),
      fetchKline(),
      fetchNews()
    ])

    ElMessage.success('数据已刷新')
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('清除缓存失败:', error)
      ElMessage.error(error.message || '清除缓存失败')
    }
  } finally {
    clearCacheLoading.value = false
  }
}

async function fetchQuote() {
  // 🔥 参数验证：确保股票代码不为空
  if (!code.value) {
    console.warn('股票代码为空，跳过获取报价')
    return
  }

  try {
    const res = await stocksApi.getQuote(code.value)
    const d: any = (res as any)?.data || {}
    // 后端为 snake_case，前端状态为 camelCase，这里进行映射
    quote.price = Number(d.price ?? d.close ?? quote.price)
    quote.changePercent = Number(d.change_percent ?? quote.changePercent)
    quote.open = Number(d.open ?? quote.open)
    quote.high = Number(d.high ?? quote.high)
    quote.low = Number(d.low ?? quote.low)
    quote.prevClose = Number(d.prev_close ?? quote.prevClose)
    quote.volume = Number.isFinite(d.volume) ? Number(d.volume) : quote.volume
    quote.amount = Number.isFinite(d.amount) ? Number(d.amount) : quote.amount
    quote.turnover = Number.isFinite(d.turnover_rate) ? Number(d.turnover_rate) : quote.turnover
    quote.amplitude = Number.isFinite(d.amplitude) ? Number(d.amplitude) : quote.amplitude

    // 🔥 获取数据日期（用于标注非当天数据）
    quote.tradeDate = d.trade_date || null  // 交易日期（用于成交量、成交额）
    quote.turnoverDate = d.turnover_rate_date || d.trade_date || null
    quote.amplitudeDate = d.amplitude_date || d.trade_date || null
    quote.updatedAt = d.updated_at || null  // 🔥 数据更新时间

    if (d.name) stockName.value = d.name
    market.value = d.market || (isLikelyEtfCode(symbol.value) ? 'ETF' : market.value)
    lastRefreshAt.value = new Date()
  } catch (e) {
    console.error('获取报价失败', e)
  }
}

const etfBasics = reactive({
  fundType: '',
  trackIndex: '',
  fundScale: '' as string | number,
  fundShare: '' as string | number,
  fundShareDate: '',
  management: '',
  custodian: '',
  managementFee: null as string | number | null,
  custodianFee: null as string | number | null,
  unitNav: NaN,
  accumNav: NaN,
  navGrowthRate: null as string | number | null,
  premiumDiscountRate: null as string | number | null,
  latestNavDate: '',
  purchaseStatus: '',
  redemptionStatus: '',
  marketPrice: NaN,
  updatedAt: ''
})

async function fetchFundamentals() {
  try {
    const res = await stocksApi.getFundamentals(code.value)
    const f: any = (res as any)?.data || {}
    // 基本面快照映射（以后台为准）
    if (f.name) stockName.value = f.name
    market.value = f.market || (isLikelyEtfCode(symbol.value) ? 'ETF' : market.value)

    if (f.security_type === 'ETF' || market.value === 'ETF' || isLikelyEtfCode(symbol.value)) {
      detailFactorDiagnostics.value = {}
      detailFactorWarnings.value = {}
      etfBasics.fundType = f.fund_type || f.industry || ''
      etfBasics.trackIndex = f.track_index || f.sector || ''
      etfBasics.fundScale = f.fund_scale || ''
      etfBasics.fundShare = f.fund_share || ''
      etfBasics.fundShareDate = f.fund_share_date || ''
      etfBasics.management = f.management || ''
      etfBasics.custodian = f.custodian || ''
      etfBasics.managementFee = f.management_fee ?? null
      etfBasics.custodianFee = f.custodian_fee ?? null
      etfBasics.unitNav = Number.isFinite(f.unit_nav) ? Number(f.unit_nav) : NaN
      etfBasics.accumNav = Number.isFinite(f.accum_nav) ? Number(f.accum_nav) : NaN
      etfBasics.navGrowthRate = f.nav_growth_rate ?? null
      etfBasics.premiumDiscountRate = f.premium_discount_rate ?? null
      etfBasics.latestNavDate = f.latest_nav_date || ''
      etfBasics.purchaseStatus = f.purchase_status || ''
      etfBasics.redemptionStatus = f.redemption_status || ''
      etfBasics.marketPrice = Number.isFinite(f.market_price) ? Number(f.market_price) : NaN
      etfBasics.updatedAt = f.updated_at || ''
      return
    }

    basics.industry = f.industry || basics.industry
    basics.sector = f.sector || basics.sector || '—'
    // 后端 total_mv 单位：亿元，这里转为元以便与金额格式化函数配合
    basics.marketCap = Number.isFinite(f.total_mv) ? Number(f.total_mv) * 1e8 : basics.marketCap
    // 优先使用 pe_ttm，其次 pe；但 TTM 净利润为负（亏损期）时禁止回退静态 PE，
    // 否则会出现"公司 TTM 已亏损、PE(TTM) 却显示正倍数"的矛盾
    const ff: any = f
    const npTtm = Number(ff.net_profit_ttm)
    const ttmLoss = Number.isFinite(npTtm) && npTtm < 0
    if (Number.isFinite(f.pe_ttm)) {
      basics.pe = Number(f.pe_ttm)
    } else if (!ttmLoss && Number.isFinite(f.pe)) {
      basics.pe = Number(f.pe)
    }
    // 🔥 新增：PB（市净率）
    basics.pb = Number.isFinite(f.pb) ? Number(f.pb) : basics.pb
    // 🔥 新增：PS（市销率）- 优先使用 ps_ttm，其次 ps
    basics.ps = Number.isFinite(f.ps_ttm) ? Number(f.ps_ttm) : (Number.isFinite(f.ps) ? Number(f.ps) : basics.ps)
    // ROE 和负债率
    basics.roe = Number.isFinite(f.roe) ? Number(f.roe) : basics.roe
    basics.debtRatio = Number.isFinite(ff.debt_ratio) ? Number(ff.debt_ratio) : basics.debtRatio
    basics.dividendYield = Number.isFinite(ff.dividend_yield) ? Number(ff.dividend_yield) : basics.dividendYield
    basics.currentRatio = Number.isFinite(ff.current_ratio) ? Number(ff.current_ratio) : basics.currentRatio
    basics.reportPeriod = ff.report_period || basics.reportPeriod
    detailFactorDiagnostics.value = f.factor_diagnostics || {}
    detailFactorWarnings.value = f.factor_warnings || {}

    // 获取PE/PB的实时标识
    basics.peIsRealtime = ff.pe_is_realtime || false
    basics.peSource = ff.pe_source || ''
    basics.peUpdatedAt = ff.pe_updated_at || null
  } catch (e) {
    console.error('获取基本面失败', e)
  }
}

async function fetchFinancials() {
  if (isLikelyEtfCode(symbol.value) || market.value === 'ETF') {
    financialRawSections.value = []
    return
  }

  try {
    const res = await stocksApi.getFinancials(code.value, { includeRaw: true })
    const d: any = (res as any)?.data || {}
    const summary: any = d.summary || {}
    const rawData: Record<string, any[]> = d.raw_data || {}

    basics.dividendYield = Number.isFinite(summary.dividend_yield) ? Number(summary.dividend_yield) : basics.dividendYield
    basics.currentRatio = Number.isFinite(summary.current_ratio) ? Number(summary.current_ratio) : basics.currentRatio
    basics.reportPeriod = summary.report_period || d.report_period || basics.reportPeriod
    basics.roe = Number.isFinite(summary.roe) ? Number(summary.roe) : basics.roe
    basics.debtRatio = Number.isFinite(summary.debt_to_assets) ? Number(summary.debt_to_assets) : basics.debtRatio
    if (Object.keys(detailFactorDiagnostics.value || {}).length === 0 && d.factor_diagnostics) {
      detailFactorDiagnostics.value = d.factor_diagnostics
    }
    if (Object.keys(detailFactorWarnings.value || {}).length === 0 && d.factor_warnings) {
      detailFactorWarnings.value = d.factor_warnings
    }

    financialSnapshot.annDate = summary.ann_date || d.ann_date || ''
    financialSnapshot.dataSource = summary.data_source || d.data_source || ''
    financialSnapshot.grossMargin = Number.isFinite(summary.gross_margin) ? Number(summary.gross_margin) : NaN
    financialSnapshot.netprofitMargin = Number.isFinite(summary.netprofit_margin) ? Number(summary.netprofit_margin) : NaN
    financialSnapshot.revenue = Number.isFinite(summary.revenue) ? Number(summary.revenue) : NaN
    financialSnapshot.netProfit = Number.isFinite(summary.net_profit) ? Number(summary.net_profit) : NaN
    financialSnapshot.nCashflowAct = Number.isFinite(summary.n_cashflow_act) ? Number(summary.n_cashflow_act) : NaN
    financialSnapshot.totalAssets = Number.isFinite(summary.total_assets) ? Number(summary.total_assets) : NaN
    financialSnapshot.totalLiab = Number.isFinite(summary.total_liab) ? Number(summary.total_liab) : NaN

    financialRawSections.value = Object.entries(rawData)
      .filter(([, items]) => Array.isArray(items) && items.length > 0)
      .map(([key, items]) => ({
        key,
        label: financialRawLabels[key] || key,
        count: items.length,
      }))
  } catch (e: any) {
    const detail = e?.response?.data?.detail
    const msg = typeof detail === 'object' ? detail?.message : detail
    if (msg) {
      ElMessage.warning(`${msg}，请点击「同步数据」获取`)
    } else {
      console.error('获取财务明细失败', e)
    }
  }
}

async function fetchSyncStatus() {
  try {
    const res = await ApiClient.get('/api/stock-data/sync-status/quotes')
    const d: any = (res as any)?.data || {}
    syncStatus.value = d
  } catch (e) {
    console.warn('获取同步状态失败', e)
  }
}

let timer: any = null

let authReadyPromise: Promise<void> | null = null

async function ensureAuthReady() {
  if (authReadyPromise) {
    await authReadyPromise
    return
  }

  authReadyPromise = (async () => {
    const storedToken = localStorage.getItem('auth-token')
    const storedRefreshToken = localStorage.getItem('refresh-token')

    if (!authStore.token && storedToken) {
      authStore.token = storedToken
      authStore.isAuthenticated = true
    }

    if (!authStore.refreshToken && storedRefreshToken) {
      authStore.refreshToken = storedRefreshToken
    }

    if (authStore.token) {
      try {
        await authStore.checkAuthStatus()
      } catch (error) {
        console.warn('详情页认证状态恢复失败:', error)
      }
    }
  })()

  try {
    await authReadyPromise
  } finally {
    authReadyPromise = null
  }
}

async function checkFavorite() {
  try {
    const res: any = await favoritesApi.check(code.value)
    const d: any = (res as any)?.data || {}
    isFav.value = !!d.is_favorite
  } catch (e) {
    console.warn('检查关注失败', e)
  }
}
onMounted(async () => {
  stockDetailDisposed = false
  await ensureAuthReady()
  await loadPreferredSyncDataSource()

  // 首次加载：打通后端（并行）
  await Promise.all([
    fetchQuote(),
    fetchFundamentals(),
    fetchFinancials(),
    fetchKline(),
    fetchNews(),
    checkFavorite(),
    fetchLatestAnalysis(),  // 获取最新的历史分析报告
    fetchLastJudgment(),  // 获取该股最新研究判断（P4 报告与日志并置）
    fetchSyncStatus(),  // 获取同步状态
    fetchPositionAnalysisSummary(),  // 获取持仓分析摘要
    fetchTradeReviewSummary(),  // 获取交易复盘摘要
    fetchReviewHistory(),  // 获取复盘历史列表
    fetchPositionData(),  // 获取持仓数据
    fetchStockTasks(),  // 获取该股相关研究任务
    fetchMaterials(),  // 获取该股我的资料
    fetchDailyReview(),  // 获取最新每日结论（持仓视角闭环）
  ])
  // 每30秒刷新一次报价
  timer = setInterval(fetchQuote, 30000)

  // 初始化股票主题（依赖上面的报告数据，放在 Promise.all 之后）
  // 异步执行不阻塞页面渲染；失败时降级为默认主题
  void initStockAssistantThread()
})
onUnmounted(() => {
  stockDetailDisposed = true
  if (timer) clearInterval(timer)
})



// K线占位相关
const periodOptions = ['日K','周K','月K','3月','6月','1年','3年']
const period = ref('日K')

const klineSource = ref<string | undefined>(undefined)
// 🔥 K线原始数据（供新版 KlineChart 组件使用，含 MA5/MA20 + 成交量）
const klineCategory = ref<string[]>([])
const klineValues = ref<number[][]>([])   // [open, close, low, high]
const klineVolumes = ref<number[]>([])

// 长周期范围 →（K线周期, 根数）：3月/6月/1年用日K，3年用周K；其余固定周期统一取 200 根
const RANGE_KLINE: Record<string, { period: string; limit: number }> = {
  '3月': { period: 'day', limit: 70 },
  '6月': { period: 'day', limit: 140 },
  '1年': { period: 'day', limit: 250 },
  '3年': { period: 'week', limit: 160 },
}

function periodLabelToParam(p: string): string {
  if (RANGE_KLINE[p]) return RANGE_KLINE[p].period
  if (p.includes('5')) return '5m'
  if (p.includes('15')) return '15m'
  if (p.includes('60')) return '60m'
  if (p.includes('日')) return 'day'
  if (p.includes('周')) return 'week'
  if (p.includes('月')) return 'month'
  return '5m'
}

// 当周期切换时刷新K线
watch(period, () => { fetchKline() })

async function fetchKline() {
  await ensureAuthReady()

  try {
    const range = RANGE_KLINE[period.value]
    const param = periodLabelToParam(period.value)
    const limit = range?.limit ?? 200
    const res = await stocksApi.getKline(code.value, param as any, limit, 'none')
    const d: any = (res as any)?.data || {}
    klineSource.value = d.source
    const items: any[] = Array.isArray(d.items) ? d.items : []

    const category: string[] = []
    const values: number[][] = [] // [open, close, low, high]

    for (const it of items) {
      const t = String(it.time || it.trade_time || it.trade_date || '')
      const o = Number(it.open ?? NaN)
      const h = Number(it.high ?? NaN)
      const l = Number(it.low ?? NaN)
      const c = Number(it.close ?? NaN)
      if (!Number.isFinite(o) || !Number.isFinite(h) || !Number.isFinite(l) || !Number.isFinite(c) || !t) continue
      category.push(t)
      values.push([o, c, l, h])
    }

    if (category.length) {
      lastKTime.value = category[category.length - 1]
      lastKClose.value = values[values.length - 1][1]
    }

    // 🔥 填充新版 KlineChart 组件所需原始数据（含成交量）
    klineCategory.value = category
    klineValues.value = values
    klineVolumes.value = items
      .map((it: any) => Number(it.volume ?? it.vol ?? 0))
      .filter((_v: number, idx: number) => idx < values.length)

    kOption.value = {
      ...kOption.value,
      xAxis: { type: 'category', data: category, boundaryGap: true, axisLine: { onZero: false } },
      series: [
        {
          type: 'candlestick',
          name: 'K线',
          data: values,
          itemStyle: {
            color: '#ef4444',
            color0: '#16a34a',
            borderColor: '#ef4444',
            borderColor0: '#16a34a'
          }
        }
      ]
    }
  } catch (e) {
    console.error('获取K线失败', e)
  }
}


// 新闻
const newsFilter = ref('all')
const newsItems = ref<any[]>([])
const newsLoading = ref(true)
const newsSource = ref<string | undefined>(undefined)

function cleanTitle(s: any): string {
  const t = String(s || '')
  return t.replace(/<[^>]+>/g, '').replace(/&nbsp;/g, ' ').trim()
}

async function fetchNews() {
  newsLoading.value = true
  try {
    const res = await stocksApi.getNews(code.value, 30, 50, true)
    const d: any = (res as any)?.data || {}
    const itemsRaw: any[] = Array.isArray(d.items) ? d.items : []
    newsItems.value = itemsRaw.map((it: any) => {
      const title = cleanTitle(it.title || it.summary || it.name || '')
      const url = it.url || it.link || '#'
      const source = it.source || d.source || ''
      const time = it.time || it.pub_time || it.publish_time || it.pub_date || ''
      const type = it.type || 'news'
      return { title, url, source, time, type }
    })
    newsSource.value = d.source
  } catch (e) {
    console.error('获取新闻失败', e)
  } finally {
    newsLoading.value = false
  }
}

// 基本面（mock）
const basics = reactive({
  industry: '-',
  sector: '-',
  marketCap: NaN,
  pe: NaN,
  pb: NaN,              // 🔥 新增：市净率
  ps: NaN,              // 🔥 新增：市销率
  roe: NaN,
  debtRatio: NaN,
  dividendYield: NaN,
  currentRatio: NaN,
  reportPeriod: '',
  peIsRealtime: false,  // PE是否为实时数据
  peSource: '',         // PE数据来源
  peUpdatedAt: null     // PE更新时间
})

const financialSnapshot = reactive({
  annDate: '',
  dataSource: '',
  grossMargin: NaN,
  netprofitMargin: NaN,
  revenue: NaN,
  netProfit: NaN,
  nCashflowAct: NaN,
  totalAssets: NaN,
  totalLiab: NaN,
})

const financialRawSections = ref<Array<{ key: string; label: string; count: number }>>([])
const detailFactorDiagnostics = ref<StockInfo['factor_diagnostics']>({})
const detailFactorWarnings = ref<StockInfo['factor_warnings']>({})

const financialRawLabels: Record<string, string> = {
  income_statement: '利润表',
  balance_sheet: '资产负债表',
  cashflow_statement: '现金流量表',
  financial_indicators: '财务指标',
  main_business: '主营业务',
}

const detailFactorRow = computed<StockInfo>(() => ({
  symbol: symbol.value,
  name: stockName.value || code.value,
  market: market.value || 'CN',
  factor_diagnostics: detailFactorDiagnostics.value,
  factor_warnings: detailFactorWarnings.value,
}))

const detailFactorWarningEntries = computed(() => getFactorWarningEntries(detailFactorRow.value))
const detailFactorDiagnosticEntries = computed(() => getFactorDiagnosticEntries(detailFactorRow.value))

// 操作
function onAnalyze() {
  router.push({ name: 'SingleAnalysis', query: { stock: code.value } })
}
async function onToggleFavorite() {
  try {
    if (!isFav.value) {
      const payload = {
        symbol: symbol.value,
        stock_code: symbol.value,  // 兼容字段
        stock_name: stockName.value,
        market: market.value
      }
      await favoritesApi.add(payload)
      isFav.value = true
      ElMessage.success('已加入关注列表')
    } else {
      await favoritesApi.remove(code.value)
      isFav.value = false
      ElMessage.success('已移出关注')
    }
  } catch (e: any) {
    console.error('关注操作失败', e)
    ElMessage.error(e?.message || '关注操作失败')
  }
}

function goPaperTrading() {
  router.push({ name: 'PaperTradingHome', query: { code: code.value, market: market.value } })
}

// 获取最新的历史分析报告
async function fetchLatestAnalysis() {
  try {
    const resp = await getTaskList({
      task_type: TaskType.STOCK_ANALYSIS,
      status: TaskStatus.COMPLETED,
      symbol: symbol.value,
      limit: 1
    })

    const tasks = resp?.data?.tasks || []

    if (tasks && tasks.length > 0) {
      const latestTask = tasks[0]

      // 保存任务信息
      lastTaskInfo.value = latestTask

      // 通过 task_id 获取完整结果
      if (latestTask.task_id) {
        try {
          const detailResp = await getTaskDetail(latestTask.task_id)
          const result = detailResp?.data?.result
          if (result) {
            lastAnalysis.value = result
            analysisStatus.value = 'completed'
          }
        } catch (e) {
          console.warn('⚠️ 获取任务结果失败:', e)
        }
      }
    }
  } catch (e) {
    console.warn('⚠️ 获取历史分析报告失败:', e)
  }
}

// ============================================================================
// 持仓分析摘要 & 交易复盘摘要
// 在详情页展示与当前股票相关的最新持仓分析和交易复盘结论
// 数据来源：/api/v2/tasks/list（按 task_type 过滤）+ /api/v2/tasks/{task_id}（拿 result）
// ============================================================================

interface PositionSnapshot {
  cost_price?: number
  current_price?: number
  quantity?: number
  unrealized_pnl?: number
  unrealized_pnl_pct?: number
  holding_days?: number
  position_pct?: number
}

interface PositionSummaryState {
  has: boolean
  taskId: string
  completedAt: string
  snapshot: PositionSnapshot | null
  action: string  // hold/buy/sell/reduce
  confidence: number | null
  conclusion: string
  keyPoints: string[]
}

interface ReviewSummaryState {
  has: boolean
  taskId: string
  completedAt: string
  riskLevel: string
  confidenceScore: number | null
  summary: string
  recommendation: string
  tradeCount: number | null
}

const positionSummary = reactive<PositionSummaryState>({
  has: false,
  taskId: '',
  completedAt: '',
  snapshot: null,
  action: '',
  confidence: null,
  conclusion: '',
  keyPoints: []
})

const reviewSummary = reactive<ReviewSummaryState>({
  has: false,
  taskId: '',
  completedAt: '',
  riskLevel: '',
  confidenceScore: null,
  summary: '',
  recommendation: '',
  tradeCount: null
})

// 复盘历史列表状态
const reviewHistory = reactive<{
  loading: boolean
  items: any[]
  total: number
  selectedIndex: number
}>({
  loading: false,
  items: [],
  total: 0,
  selectedIndex: 0
})

// 复盘详情弹窗状态
const reviewDetailVisible = ref(false)
const reviewDetailLoading = ref(false)
const currentReviewDetail = ref<any>(null)

// 判断任务是否属于当前股票（先从 task 顶层 symbol/code 匹配，再从 task_params 匹配）
function taskMatchesCurrentStock(task: any): boolean {
  const targetCode = symbol.value  // 6位代码（已去掉后缀）
  const targetCodeUpper = code.value  // 完整代码（可能含后缀如 SH）
  const params = task?.task_params || task?.params || {}
  const candidates = [
    task.symbol,        // 从列表 API 的顶层字段匹配
    task.code,
    params.symbol,      // 从 task_params 匹配
    params.code,
    params.stock_code,
    params.symbol_code
  ].filter(Boolean).map((v: any) => String(v).toUpperCase())
  return candidates.some(c => c === targetCode.toUpperCase() || c === targetCodeUpper.toUpperCase() || c.startsWith(targetCode.toUpperCase()))
}

async function fetchPositionAnalysisSummary() {
  try {
    const resp: any = await getTaskList({
      task_type: TaskType.POSITION_ANALYSIS,
      status: TaskStatus.COMPLETED,
      limit: 50
    })
    const tasks = resp?.data?.tasks || resp?.tasks || []
    // 过滤出与当前股票相关的任务，并按完成时间倒序
    const matched = tasks
      .filter((t: any) => taskMatchesCurrentStock(t))
      .sort((a: any, b: any) => {
        const ta = new Date(a.completed_at || a.created_at).getTime()
        const tb = new Date(b.completed_at || b.created_at).getTime()
        return tb - ta
      })

    if (matched.length === 0) {
      positionSummary.has = false
      return
    }

    const latest = matched[0]
    positionSummary.taskId = latest.task_id
    positionSummary.completedAt = latest.completed_at || latest.created_at

    // 拉取任务详情拿 result
    try {
      const detail: any = await getTaskDetail(latest.task_id)
      const result = detail?.data?.result || detail?.result || {}
      const snapshot = result?.position_snapshot || null
      const ai = result?.ai_analysis || {}
      const userView = ai?.user_view || {}

      positionSummary.snapshot = snapshot ? {
        cost_price: snapshot.cost_price,
        current_price: snapshot.current_price,
        quantity: snapshot.quantity,
        unrealized_pnl: snapshot.unrealized_pnl,
        unrealized_pnl_pct: snapshot.unrealized_pnl_pct,
        holding_days: snapshot.holding_days,
        position_pct: snapshot.position_pct
      } : null
      positionSummary.action = ai.action || ''
      positionSummary.confidence = typeof ai.confidence === 'number' ? ai.confidence : null
      positionSummary.conclusion = userView.conclusion || ai.action_reason || ''
      positionSummary.keyPoints = Array.isArray(userView.key_points) ? userView.key_points : []
    } catch (e) {
      console.warn('⚠️ 获取持仓分析详情失败:', e)
    }

    positionSummary.has = true
  } catch (e) {
    console.warn('⚠️ 获取持仓分析摘要失败:', e)
    positionSummary.has = false
  }
}

async function fetchTradeReviewSummary() {
  try {
    const resp: any = await reviewApi.getTradeReviewSummary(code.value)
    const data = resp?.data || {}
    if (!data.has) {
      reviewSummary.has = false
      return
    }
    reviewSummary.taskId = data.task_id || ''
    reviewSummary.completedAt = data.completed_at || ''
    reviewSummary.summary = data.summary || ''
    reviewSummary.recommendation = data.recommendation || ''
    reviewSummary.riskLevel = data.risk_level || ''
    reviewSummary.confidenceScore = data.confidence_score ?? null
    reviewSummary.tradeCount = data.trade_count ?? null
    reviewSummary.has = true
  } catch (e) {
    console.warn('⚠️ 获取交易复盘摘要失败:', e)
    reviewSummary.has = false
  }
}

// 获取当前股票的复盘历史列表
async function fetchReviewHistory() {
  reviewHistory.loading = true
  try {
    const resp: any = await reviewApi.getReviewHistory({
      code: code.value,
      page: 1,
      pageSize: 20
    })
    reviewHistory.items = resp?.data?.items || []
    reviewHistory.total = resp?.data?.total || 0
    reviewHistory.selectedIndex = 0
  } catch (e) {
    console.warn('⚠️ 获取复盘历史失败:', e)
    reviewHistory.items = []
    reviewHistory.total = 0
  } finally {
    reviewHistory.loading = false
  }
}

// 持仓数据状态
const positionData = reactive<{
  loading: boolean
  real: {
    has: boolean
    quantity: number
    cost_price: number
    current_price: number
    market_value: number
    unrealized_pnl: number
    unrealized_pnl_pct: number
    buy_date: string | null
    weight_pct: number | null
  }
  paper: {
    has: boolean
    quantity: number
    cost_price: number
    current_price: number
    market_value: number
    unrealized_pnl: number
    unrealized_pnl_pct: number
  }
}>({
  loading: false,
  real: { has: false, quantity: 0, cost_price: 0, current_price: 0, market_value: 0, unrealized_pnl: 0, unrealized_pnl_pct: 0, buy_date: null, weight_pct: null },
  paper: { has: false, quantity: 0, cost_price: 0, current_price: 0, market_value: 0, unrealized_pnl: 0, unrealized_pnl_pct: 0 }
})

// 获取当前股票的持仓信息
async function fetchPositionData() {
  positionData.loading = true
  try {
    // 并行获取实盘和模拟持仓
    const [realRes, paperRes] = await Promise.all([
      portfolioApi.getPositions('real').catch(() => ({ success: false, data: { items: [] } })),
      portfolioApi.getPositions('paper').catch(() => ({ success: false, data: { items: [] } }))
    ])

    // 查找当前股票的实盘持仓
    const realPositions = realRes?.data?.items || []
    const realMatch = realPositions.find((p: any) => p.code === symbol.value || p.code === code.value)
    if (realMatch) {
      // 仓位占比 = 本股市值 / 组合持仓总市值（同一 API 内自洽口径）
      const totalMv = realPositions.reduce((s: number, p: any) => s + (Number(p.market_value) || 0), 0)
      const mv = Number(realMatch.market_value) || 0
      positionData.real = {
        has: true,
        quantity: realMatch.quantity || 0,
        cost_price: realMatch.cost_price || 0,
        current_price: realMatch.current_price || 0,
        market_value: mv,
        unrealized_pnl: realMatch.unrealized_pnl || 0,
        unrealized_pnl_pct: realMatch.unrealized_pnl_pct || 0,
        buy_date: realMatch.buy_date || null,
        weight_pct: totalMv > 0 ? (mv / totalMv) * 100 : null
      }
    }

    // 查找当前股票的模拟持仓
    const paperPositions = paperRes?.data?.items || []
    const paperMatch = paperPositions.find((p: any) => p.code === symbol.value || p.code === code.value)
    if (paperMatch) {
      positionData.paper = {
        has: true,
        quantity: paperMatch.quantity || 0,
        cost_price: paperMatch.cost_price || 0,
        current_price: paperMatch.current_price || 0,
        market_value: paperMatch.market_value || 0,
        unrealized_pnl: paperMatch.unrealized_pnl || 0,
        unrealized_pnl_pct: paperMatch.unrealized_pnl_pct || 0
      }
    }
  } catch (e) {
    console.warn('⚠️ 获取持仓数据失败:', e)
  } finally {
    positionData.loading = false
  }
}

// 选择复盘历史项
function selectReviewItem(index: number) {
  reviewHistory.selectedIndex = index
  const item = reviewHistory.items[index]
  if (item) {
    reviewSummary.taskId = item.review_id || item.task_id || ''
    reviewSummary.completedAt = item.completed_at || item.created_at || ''
    reviewSummary.summary = item.summary || ''
    reviewSummary.recommendation = item.recommendation || ''
    reviewSummary.riskLevel = item.risk_level || item.riskLevel || ''
    reviewSummary.confidenceScore = item.confidence_score ?? item.confidenceScore ?? null
    reviewSummary.tradeCount = item.trade_count ?? item.tradeCount ?? null
    reviewSummary.has = true
  }
}

// 查看复盘详情（弹窗展示）
async function viewReviewDetail(reviewId?: string) {
  const targetId = reviewId || reviewSummary.taskId
  if (!targetId) {
    ElMessage.warning('暂无复盘详情')
    return
  }
  
  reviewDetailVisible.value = true
  reviewDetailLoading.value = true
  currentReviewDetail.value = null
  
  try {
    const resp: any = await reviewApi.getReviewDetail(targetId)
    currentReviewDetail.value = resp?.data || resp
  } catch (e) {
    console.warn('⚠️ 获取复盘详情失败:', e)
    ElMessage.error('获取复盘详情失败')
  } finally {
    reviewDetailLoading.value = false
  }
}

// 跳转到持仓分析页面（通过 query 预填股票代码）
function goToPositionAnalysis() {
  router.push({
    path: '/portfolio',
    query: {
      symbol: symbol.value,
      code: code.value
    }
  })
}

// 跳转到交易复盘页面
function goToTradeReview() {
  router.push({
    path: '/review',
    query: {
      symbol: symbol.value,
      code: code.value
    }
  })
}

// 查看持仓分析任务详情（跳转到任务中心）
function viewPositionTaskDetail() {
  if (positionSummary.taskId) {
    router.push({ path: '/tasks/unified', query: { task_id: positionSummary.taskId } })
  }
}

function viewReviewTaskDetail() {
  // 改为本页弹窗展示，不跳转到任务中心
  viewReviewDetail()
}

// 持仓分析相关格式化函数（仅保留对话框所需）

// 格式化盈亏数值
function formatPnlValue(pnl: any): string {
  const n = Number(pnl)
  if (!Number.isFinite(n)) return '-'
  const sign = n > 0 ? '+' : ''
  return `${sign}¥${n.toFixed(2)}`
}

// 获取总盈亏
function getTotalPnl(): number {
  if (!currentReviewDetail.value?.trade_info) return 0
  const info = currentReviewDetail.value.trade_info
  return (info.realized_pnl || 0) + (info.unrealized_pnl || 0)
}

// 获取总收益率
function getTotalPnlPct(): number {
  if (!currentReviewDetail.value?.trade_info) return 0
  const info = currentReviewDetail.value.trade_info
  return info.total_pnl_pct || 0
}

// 格式化百分比
function formatPct(pct: any): string {
  const n = Number(pct)
  if (!Number.isFinite(n)) return '-'
  const sign = n > 0 ? '+' : ''
  return `${sign}${(n * 100).toFixed(2)}%`
}

// fmtConf 已移除：合规要求不展示信心度

// 格式化报告名称
function formatReportName(key: string): string {
  const isEtfAnalysis = Array.isArray(lastAnalysis.value?.analysts) && lastAnalysis.value.analysts.includes('etf_analyst')
  return getReportName(key, isEtfAnalysis)
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function extractMarkdownSection(content: string, heading: string): string {
  if (!content) return ''
  const headingPattern = escapeRegExp(heading)
  const match = content.match(new RegExp(`(?:^|\\n)#{1,6}\\s*${headingPattern}\\s*\\n([\\s\\S]*?)(?=\\n#{1,6}\\s+|$)`, 'i'))
  return match?.[1]?.trim() || ''
}

// 🔥 提取报告内容（支持对象中的 content 字段）
function getReportContent(reportData: any): string {
  if (!reportData) return ''
  
  // 如果是字符串，直接返回
  if (typeof reportData === 'string') {
    return reportData
  }
  
  // 如果是对象，优先提取 content 字段
  if (typeof reportData === 'object') {
    if (reportData.content && typeof reportData.content === 'string') {
      return reportData.content
    }
    if (reportData.markdown && typeof reportData.markdown === 'string') {
      return reportData.markdown
    }
    if (reportData.judge_decision && typeof reportData.judge_decision === 'string') {
      return reportData.judge_decision
    }
  }

  return String(reportData)
}

// 打开指定报告
function openReport(reportKey: string) {
  showReportsDialog.value = true
  activeReportTab.value = reportKey
}

// 导出报告
function exportReport() {
  if (!lastAnalysis.value?.reports) {
    ElMessage.warning('暂无报告可导出')
    return
  }

  // 生成Markdown格式的完整报告
  let fullReport = `# ${code.value} 股票分析报告\n\n`

  // 格式化分析时间用于报告（兼容 completed_at / created_at / end_time）
  const reportTimeSrc = lastTaskInfo.value?.completed_at || lastTaskInfo.value?.created_at || lastTaskInfo.value?.end_time
  const reportTime = reportTimeSrc
    ? new Date(reportTimeSrc).toLocaleString('zh-CN', {
        timeZone: 'Asia/Shanghai',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false
      })
    : lastAnalysis.value?.analysis_date

  fullReport += `**分析时间**: ${reportTime}\n`
  fullReport += `**研究观察**: ${lastAnalysis.value.recommendation}\n\n`
  fullReport += `---\n\n`

  for (const [key, content] of Object.entries(lastAnalysis.value.reports)) {
    fullReport += `## ${formatReportName(key)}\n\n`
    fullReport += `${content}\n\n`
    fullReport += `---\n\n`
  }

  // 创建下载链接
  const blob = new Blob([fullReport], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url

  // 使用分析日期作为文件名（简化格式）
  const fileDate = lastAnalysis.value.analysis_date || new Date().toISOString().slice(0, 10)
  link.download = `${code.value}_分析报告_${fileDate}.md`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)

  ElMessage.success('报告已导出')
}

// ============================================================================
// 新版详情页：档案式 Tab / 智能助手 / 历史导航
// ============================================================================

// 档案式 Tab：概览 / 行业面板 / 事实层 / 概念关系 / 我的研究 / 我的资料 / 完整时间线
const activeDetailTab = ref<'overview' | 'industry' | 'facts' | 'concept' | 'mine' | 'materials' | 'timeline'>('overview')

// 智能助手聊天状态
const assistantMessages = ref<Array<{ role: 'user' | 'bot'; content: string }>>([])
const assistantLoading = ref(false)
const assistantInitialPrompt = ref('')
const assistantChatRef = ref<any>(null)

// 股票主题（thread）状态
const stockAssistantThreadId = ref<string>('')
const stockAssistantThreadReady = ref(false)
const stockAssistantStreamController = ref<AbortController | null>(null)

// 已加载模块（用于助手头部展示）
const assistantLoadedModules = computed(() => {
  const mods: string[] = []
  if (klineValues.value.length) mods.push('K线')
  if (lastAnalysis.value) mods.push('单股分析')
  if (positionSummary.has) mods.push('持仓')
  if (reviewSummary.has) mods.push('复盘')
  if (Number.isFinite(basics.pe) || Number.isFinite(financialSnapshot.revenue)) mods.push('基本面')
  return mods
})

// 助手是否已加载各模块（用于 AssistantHero 展示）
const assistantHasAnalysis = computed(() => !!lastAnalysis.value)
const assistantHasPosition = computed(() => positionSummary.has)
const assistantHasReview = computed(() => reviewSummary.has)
const assistantHasFundamentals = computed(() => Number.isFinite(basics.pe) || Number.isFinite(financialSnapshot.revenue))
const assistantHasKline = computed(() => klineValues.value.length > 0)

// 处理助手快捷问题（来自 AssistantHero）
function handleAssistantHeroAsk(prompt: string) {
  assistantInitialPrompt.value = prompt
}

// ════════ 股票主题初始化（对接现有智能助手模块） ════════

const STALE_THRESHOLD_HOURS = 24

// 单股分析报告可用模块目录（用于注入 stock_scope，供 LLM 按需调工具获取完整内容）
// 与后端 core/tools/implementations/assistant_ops/report_query.py 的 _ANALYST_LABELS 保持一致
const STOCK_REPORT_MODULES = [
  { key: 'market_report', title: '市场技术分析', desc: 'K线形态、技术指标、支撑压力位' },
  { key: 'fundamentals_report', title: '基本面研究', desc: '财务数据、估值、行业地位' },
  { key: 'news_report', title: '新闻研究', desc: '近期公告、行业新闻、事件驱动' },
  { key: 'sentiment_report', title: '情绪分析', desc: '社交媒体舆情、机构观点' },
  { key: 'trader_investment_plan', title: '研究整合意见', desc: '多情景研究结论 + 研究观察' },
  { key: 'research_team_decision', title: '研究团队结论', desc: '多情景研究后的团队研究观察汇总' },
  { key: 'risk_management_decision', title: '风险审阅结论', desc: '风险边界 + 后续观察' },
  { key: 'final_trade_decision', title: '综合研究结论', desc: '最终研究观察汇总' },
]

/** 初始化股票主题：创建/获取主题 + 加载历史消息 + 自动关联报告 */
async function initStockAssistantThread() {
  if (!code.value) return
  try {
    const title = `股票研究 · ${code.value} ${stockName.value || ''}`.trim()
    const thread = await assistantApi.createThread(title)
    stockAssistantThreadId.value = thread.thread_id

    // 加载历史消息（若之前已有对话）
    const historyRes = await assistantApi.getThreadMessages(thread.thread_id)
    const hasHistory = !!(historyRes.messages && historyRes.messages.length > 0)
    if (hasHistory) {
      assistantMessages.value = historyRes.messages.map(m => ({
        role: m.role === 'user' ? 'user' as const : 'bot' as const,
        content: m.content,
      }))
    }

    // 自动关联报告（不阻塞主流程）
    void autoLinkReports(thread)
    stockAssistantThreadReady.value = true

    // 仅当首次进入（无历史消息）时，检查报告时效性并主动提醒用户
    if (!hasHistory) {
      checkStaleReportsAndRemind()
    }
  } catch (e) {
    console.warn('初始化股票助手主题失败', e)
    // 失败时降级：仍然允许用户发消息，conversation_id 为空走默认主题
  }
}

/** 检查报告时效性，若有过期报告则主动推一条 bot 消息提醒用户重新分析 */
function checkStaleReportsAndRemind() {
  const scope = buildStockScopeContext()
  const staleItems: string[] = []

  const stockReport = scope.reports?.stock_report
  if (stockReport?.is_stale) {
    staleItems.push(`单股分析报告（${stockReport.completed_at || '未知时间'} 生成，已过期约 ${stockReport.stale_hours} 小时）`)
  }

  const positionReport = scope.reports?.position_report
  if (positionReport?.is_stale) {
    staleItems.push(`持仓分析报告（${positionReport.completed_at || '未知时间'} 生成，已过期约 ${positionReport.stale_hours} 小时）`)
  }

  const reviewData = scope.review_summary
  if (reviewData?.is_stale) {
    staleItems.push(`交易复盘报告（${reviewData.completed_at || '未知时间'} 生成，已过期约 ${reviewData.stale_hours} 小时）`)
  }

  if (staleItems.length === 0) return

  const reminder = [
    `⚠️ 检测到以下报告已过期（超过 ${STALE_THRESHOLD_HOURS} 小时），我不会基于旧报告给出结论：`,
    '',
    ...staleItems.map(s => `• ${s}`),
    '',
    '如果你希望我基于最新数据解读，请点击对应模块的「重新分析」按钮；或在下方回复「重新分析」，我会引导你发起。'
  ].join('\n')

  assistantMessages.value.push({ role: 'bot', content: reminder })
}

/** 自动关联单股分析报告、持仓分析报告、交易复盘报告到主题 */
async function autoLinkReports(thread: AssistantThreadItem) {
  const threadId = thread.thread_id
  const existingKeys = new Set(
    (thread.report_refs || []).map(r => `${r.ref_type}:${r.report_key}`),
  )

  // 关联单股分析报告
  if (lastTaskInfo.value?.task_id) {
    const key = `stock_report:${lastTaskInfo.value.task_id}`
    if (!existingKeys.has(key)) {
      try {
        await assistantApi.attachThreadReport(threadId, 'stock_report', lastTaskInfo.value.task_id)
      } catch (e) {
        console.warn('关联单股分析报告失败', e)
      }
    }
  }

  // 关联持仓分析报告（需要先搜索 candidates 拿到 analysis_id）
  if (positionSummary.has) {
    try {
      const candidates = await assistantApi.getThreadReportCandidates(
        threadId,
        'position_report',
        code.value,
        5,
      )
      const matched = candidates.items.find(
        item => (item.symbol || '').toUpperCase() === code.value.toUpperCase(),
      )
      if (matched) {
        const key = `position_report:${matched.report_key}`
        if (!existingKeys.has(key)) {
          await assistantApi.attachThreadReport(threadId, 'position_report', matched.report_key)
        }
      }
    } catch (e) {
      console.warn('关联持仓分析报告失败', e)
    }
  }

  // 关联交易复盘报告（task_id 即 review_id，直接用 task_id 作为 report_key）
  if (reviewSummary.has && reviewSummary.taskId) {
    const key = `review_report:${reviewSummary.taskId}`
    if (!existingKeys.has(key)) {
      try {
        await assistantApi.attachThreadReport(threadId, 'review_report', reviewSummary.taskId)
      } catch (e) {
        console.warn('关联交易复盘报告失败', e)
      }
    }
  }
}

/** 构建股票上下文（通过 user_context.stock_scope 注入到后端 system prompt） */
function buildStockScopeContext() {
  const now = Date.now()
  const parseTime = (s: string) => (s ? new Date(s).getTime() : 0)
  const calcStale = (ts: number) => {
    if (!ts) return { is_stale: false }
    const hours = Math.round((now - ts) / 3_600_000)
    return { is_stale: hours > STALE_THRESHOLD_HOURS, stale_hours: hours }
  }

  const scope: Record<string, any> = {
    code: code.value,
    stock_name: stockName.value,
    thread_id: stockAssistantThreadId.value,
    reports: {},
  }

  if (lastTaskInfo.value?.task_id) {
    const ts = parseTime(lastTaskInfo.value.completed_at || lastTaskInfo.value.created_at || '')
    // 注入报告目录而非截断摘要正文，LLM 通过 get_report_detail(task_id, module_key) 按需获取完整内容
    const existingKeys = Object.keys(lastAnalysis.value?.reports || {})
    scope.reports.stock_report = {
      task_id: lastTaskInfo.value.task_id,
      completed_at: lastTaskInfo.value.completed_at || lastTaskInfo.value.created_at || '',
      ...calcStale(ts),
      available_modules: STOCK_REPORT_MODULES,
      existing_modules: existingKeys,
    }
  }

  if (positionSummary.has && positionSummary.taskId) {
    const ts = parseTime(positionSummary.completedAt)
    // 持仓报告不注入正文，LLM 通过 get_position_analysis(code, market) 获取完整内容
    scope.reports.position_report = {
      analysis_id: positionSummary.taskId,
      completed_at: positionSummary.completedAt,
      ...calcStale(ts),
    }
  }

  if (reviewSummary.has) {
    const ts = parseTime(reviewSummary.completedAt)
    // 复盘报告不注入正文，LLM 通过 get_trade_review_detail(review_id) 获取完整内容
    // 注意：后端 task_id 即 review_id（见 trade_review_service.py:1908 注释）
    scope.review_summary = {
      task_id: reviewSummary.taskId,
      review_id: reviewSummary.taskId,  // task_id 即 review_id
      completed_at: reviewSummary.completedAt,
      ...calcStale(ts),
      trade_count: reviewSummary.tradeCount ?? undefined,
    }
  }

  if (Number.isFinite(quote.price)) {
    scope.current_quote = {
      price: quote.price,
      change_percent: quote.changePercent,
    }
  }

  return scope
}

// 处理助手发送问题（流式 LLM 对话，对接现有智能助手模块）
async function handleAssistantAsk(prompt: string) {
  if (!prompt.trim() || assistantLoading.value) return

  const conversationId = stockAssistantThreadId.value || undefined
  const stockScope = buildStockScopeContext()

  assistantLoading.value = true

  // 占位一条空的 bot 消息，用于流式追加
  const botMsgIdx = assistantMessages.value.push({ role: 'bot', content: '' }) - 1
  let firstTokenReceived = false

  stockAssistantStreamController.value = assistantApi.chatStream(
    prompt,
    conversationId,
    undefined, // model，使用系统默认
    undefined, // model_config_id
    {
      onToken(content: string) {
        if (!firstTokenReceived) firstTokenReceived = true
        assistantMessages.value[botMsgIdx].content += content
      },
      onDone(data) {
        assistantLoading.value = false
        stockAssistantStreamController.value = null
        // 若服务端返回了 conversation_id（首次创建主题），更新本地
        if (data.conversation_id && !stockAssistantThreadId.value) {
          stockAssistantThreadId.value = data.conversation_id
        }
        // 若回复为空（罕见），给一个友好提示
        if (!assistantMessages.value[botMsgIdx].content.trim()) {
          assistantMessages.value[botMsgIdx].content =
            '抱歉，我暂时无法回答这个问题。请稍后重试。'
        }
      },
      onError(msg: string) {
        assistantLoading.value = false
        stockAssistantStreamController.value = null
        if (!firstTokenReceived) {
          assistantMessages.value[botMsgIdx].content =
            `抱歉，处理您的请求时出错：${msg}\n\n你可以稍后重试，或前往「智能助手」主页面继续对话。`
        } else {
          assistantMessages.value[botMsgIdx].content +=
            `\n\n---\n⚠️ 响应中断：${msg}`
        }
      },
    },
    {
      // extraPayload: 通过 user_context 注入股票上下文
      assistant_role: 'general',
      user_context: {
        stock_scope: stockScope,
      },
    },
  )
}

// 历史记录导航
function goToAnalysisHistory() {
  router.push({ path: '/tasks/unified', query: { type: 'stock_analysis', symbol: code.value } })
}

function goToPositionHistory() {
  router.push({ path: '/tasks/unified', query: { type: 'position_analysis', symbol: code.value } })
}

function goToReviewHistory() {
  router.push({ path: '/tasks/unified', query: { type: 'trade_review', symbol: code.value } })
}

// 「我的研究」该股相关研究任务聚合（单股分析 + 持仓分析 + 交易复盘）
const stockTasks = ref<any[]>([])
const stockTasksLoading = ref(false)

async function fetchStockTasks() {
  stockTasksLoading.value = true
  try {
    const resp: any = await getTaskList({ limit: 100 })
    const all = resp?.data?.tasks || resp?.tasks || []
    stockTasks.value = all
      .filter((t: any) => taskMatchesCurrentStock(t)
        && [TaskType.STOCK_ANALYSIS, TaskType.POSITION_ANALYSIS, TaskType.TRADE_REVIEW].includes(t.task_type))
      .sort((a: any, b: any) =>
        new Date(b.completed_at || b.created_at).getTime() - new Date(a.completed_at || a.created_at).getTime())
      .slice(0, 20)
  } catch {
    stockTasks.value = []
  } finally {
    stockTasksLoading.value = false
  }
}

function stockTaskTitle(task: any): string {
  return task?.title || task?.task_name
    || `${stockTaskTypeText(task?.task_type)} · ${stockName.value || code.value}`
}
function stockTaskTypeText(t: string): string {
  return ({
    [TaskType.STOCK_ANALYSIS]: '单股分析',
    [TaskType.POSITION_ANALYSIS]: '持仓分析',
    [TaskType.TRADE_REVIEW]: '交易复盘',
  } as Record<string, string>)[t] || t || '研究任务'
}
function stockTaskStatusText(s: string): string {
  const map: Record<string, string> = {
    [TaskStatus.COMPLETED]: '已完成',
    [TaskStatus.PROCESSING]: '进行中',
    [TaskStatus.PENDING]: '排队中',
    [TaskStatus.FAILED]: '失败',
    [TaskStatus.CANCELLED]: '已取消',
    [TaskStatus.SUSPENDED]: '已挂起',
  }
  return map[s] || s || '-'
}
function stockTaskStatusType(s: string): any {
  if (s === TaskStatus.COMPLETED) return 'success'
  if (s === TaskStatus.PROCESSING || s === TaskStatus.PENDING) return 'primary'
  if (s === TaskStatus.FAILED) return 'danger'
  return 'info'
}
function formatTaskTime(v: string): string {
  if (!v) return '—'
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return v
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}
function viewStockTask(task: any) {
  const typeQuery = ({
    [TaskType.STOCK_ANALYSIS]: 'stock_analysis',
    [TaskType.POSITION_ANALYSIS]: 'position_analysis',
    [TaskType.TRADE_REVIEW]: 'trade_review',
  } as Record<string, string>)[task?.task_type] || ''
  router.push({ path: '/tasks/unified', query: { type: typeQuery, symbol: code.value } })
}

// 「我的资料」（收藏链接 + 文字笔记 + 上传文件，按用户+股票隔离）
const stockMaterials = ref<StockMaterial[]>([])
const materialsLoading = ref(false)
const materialDialogVisible = ref(false)
const materialSaving = ref(false)
const editingMaterialId = ref<string | null>(null)
const materialForm = reactive({
  kind: 'url' as MaterialKind,
  title: '',
  url: '',
  content: '',
  category: 'other' as MaterialCategory,
  source_tier: 'public_news' as MaterialSourceTier,
  source_note: '',
  remark: '',
})
// 列表筛选（纯前端过滤）
const materialCategoryFilter = ref('all')
const materialTierFilter = ref('all')
const filteredStockMaterials = computed(() =>
  stockMaterials.value.filter(m =>
    (materialCategoryFilter.value === 'all' || (m.category || 'other') === materialCategoryFilter.value)
    && (materialTierFilter.value === 'all' || (m.source_tier || 'public_news') === materialTierFilter.value)
  )
)

/** 按 kind 给出元信息默认值（url→资讯/公开；note→其他/内部一手；file→其他/公开） */
function defaultMaterialMeta(kind: MaterialKind): { category: MaterialCategory; source_tier: MaterialSourceTier } {
  if (kind === 'url') return { category: 'news', source_tier: 'public_news' }
  if (kind === 'note') return { category: 'other', source_tier: 'internal_firsthand' }
  return { category: 'other', source_tier: 'public_news' }
}

async function fetchMaterials() {
  materialsLoading.value = true
  try {
    const resp: any = await fetchStockMaterials(code.value)
    stockMaterials.value = resp?.data?.items || []
  } catch {
    stockMaterials.value = []
  } finally {
    materialsLoading.value = false
  }
}

function openMaterialDialog(m?: StockMaterial) {
  editingMaterialId.value = m?.id || null
  materialForm.kind = m?.kind || 'url'
  materialForm.title = m?.title || ''
  materialForm.url = m?.url || ''
  materialForm.content = m?.content || ''
  const defaults = defaultMaterialMeta(materialForm.kind)
  materialForm.category = m?.category || defaults.category
  materialForm.source_tier = m?.source_tier || defaults.source_tier
  materialForm.source_note = m?.source_note || ''
  materialForm.remark = m?.remark || ''
  materialDialogVisible.value = true
}

async function saveMaterial() {
  const title = materialForm.title.trim()
  const url = materialForm.url.trim()
  const content = materialForm.content.trim()
  if (!title) { ElMessage.warning('请填写标题'); return }
  if (materialForm.kind === 'url' && !url) { ElMessage.warning('请填写链接地址'); return }
  if (materialForm.kind === 'note' && !content) { ElMessage.warning('请填写笔记内容'); return }
  materialSaving.value = true
  try {
    const meta = {
      category: materialForm.category,
      source_tier: materialForm.source_tier,
      source_note: materialForm.source_note.trim(),
      remark: materialForm.remark.trim(),
    }
    if (editingMaterialId.value) {
      await updateStockMaterial(
        editingMaterialId.value,
        materialForm.kind === 'file' ? { title, ...meta } : { title, url, content, ...meta }
      )
      ElMessage.success('资料已更新')
    } else {
      await addStockMaterial({
        stock_code: code.value,
        stock_name: stockName.value,
        kind: materialForm.kind,
        title,
        url,
        content,
        ...meta,
      })
      ElMessage.success('资料已收藏')
    }
    materialDialogVisible.value = false
    await fetchMaterials()
  } catch (e: any) {
    ElMessage.error(e?.message || '保存失败')
  } finally {
    materialSaving.value = false
  }
}

async function deleteMaterial(m: StockMaterial) {
  try {
    await ElMessageBox.confirm('确定删除这条资料吗？', '删除确认', { type: 'warning' })
  } catch { return }
  try {
    await deleteStockMaterial(m.id)
    ElMessage.success('已删除')
    await fetchMaterials()
  } catch (e: any) {
    ElMessage.error(e?.message || '删除失败')
  }
}

function openMaterialLink(url?: string) {
  if (url) window.open(url, '_blank', 'noopener')
}

// 「我的资料」文件上传（GridFS 存档 + 后端自动提取文本；选文件后先确认元信息再上传）
const materialFileInput = ref<HTMLInputElement | null>(null)
const uploading = ref(false)
const uploadProgress = ref(0)
// 上传设置弹窗（信源等级影响世界模型证据权重，上传前让用户确认）
const uploadSettingsVisible = ref(false)
const pendingUploadFile = ref<File | null>(null)
const uploadForm = reactive({
  title: '',
  category: 'other' as MaterialCategory,
  source_tier: 'public_news' as MaterialSourceTier,
  source_note: '',
  remark: '',
})

function triggerMaterialUpload() {
  materialFileInput.value?.click()
}

function onMaterialFileChosen(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = '' // 允许重复选择同一文件
  if (!file) return
  const dot = file.name.lastIndexOf('.')
  const ext = dot >= 0 ? file.name.slice(dot).toLowerCase() : ''
  if (!MATERIAL_FILE_EXTENSIONS.includes(ext)) {
    ElMessage.warning('不支持的文件格式，支持 PDF/Word/Excel/TXT/MD/CSV/PPT/图片')
    return
  }
  if (file.size > MAX_MATERIAL_FILE_SIZE) {
    ElMessage.warning('文件超过 20MB 上限')
    return
  }
  pendingUploadFile.value = file
  uploadForm.title = dot > 0 ? file.name.slice(0, dot) : file.name
  const defaults = defaultMaterialMeta('file')
  uploadForm.category = defaults.category
  uploadForm.source_tier = defaults.source_tier
  uploadForm.source_note = ''
  uploadForm.remark = ''
  uploadSettingsVisible.value = true
}

async function confirmMaterialUpload() {
  const file = pendingUploadFile.value
  if (!file) { uploadSettingsVisible.value = false; return }
  uploading.value = true
  uploadProgress.value = 0
  try {
    const resp: any = await uploadStockMaterial(code.value, file, {
      stockName: stockName.value,
      title: uploadForm.title.trim() || undefined,
      category: uploadForm.category,
      sourceTier: uploadForm.source_tier,
      sourceNote: uploadForm.source_note.trim(),
      remark: uploadForm.remark.trim() || undefined,
      onProgress: (p) => { uploadProgress.value = p },
    })
    const saved = resp?.data
    ElMessage.success(saved?.text_ok ? '上传成功，已提取文本供 AI 使用' : (saved?.text_message || '上传成功'))
    uploadSettingsVisible.value = false
    await fetchMaterials()
  } catch (e: any) {
    ElMessage.error(e?.message || '上传失败')
  } finally {
    uploading.value = false
  }
}

function openMaterialFile(m: StockMaterial) {
  window.open(materialFileUrl(m.id), '_blank', 'noopener')
}

const materialPreviewVisible = ref(false)
const materialPreviewItem = ref<StockMaterial | null>(null)
const materialPreviewText = ref('')
const materialPreviewLoading = ref(false)
const materialReextracting = ref(false)

// 按【】标题把全文拆节展示（如【提取文字】【图表解读】【内容要点】），无标题时整段显示
// 兼容模型输出 "### 【提取文字】" 这类 markdown 标题前缀，避免残留 "###" 杂段
const materialPreviewSections = computed(() => {
  const text = materialPreviewText.value || ''
  if (!text) return []
  const matches = [...text.matchAll(/(?:^|\n)[ \t]*#{0,6}[ \t]*【([^【】]{1,20})】/g)]
  if (!matches.length) return [{ title: '', body: text }]
  const sections: Array<{ title: string; body: string }> = []
  const head = text.slice(0, matches[0].index ?? 0).trim()
  if (head) sections.push({ title: '', body: head })
  matches.forEach((m, i) => {
    const start = (m.index ?? 0) + m[0].length
    const end = i + 1 < matches.length ? (matches[i + 1].index ?? text.length) : text.length
    const body = text.slice(start, end).trim()
    if (body || !sections.length) sections.push({ title: m[1], body })
  })
  return sections
})

async function previewMaterialText(m: StockMaterial) {
  materialPreviewItem.value = m
  materialPreviewText.value = m.extracted_text || ''
  materialPreviewVisible.value = true
  if (m.kind !== 'file') return
  // 列表只带 300 字预览，弹窗内拉取全文
  materialPreviewLoading.value = true
  try {
    const resp: any = await fetchMaterialText(m.id)
    const data = resp?.data
    if (typeof data?.text === 'string' && data.text) {
      materialPreviewText.value = data.text
      materialPreviewItem.value = { ...m, text_ok: !!data.text_ok, text_message: data.text_message || m.text_message }
    }
  } catch {
    // 拉取全文失败时回退列表预览文本
  } finally {
    materialPreviewLoading.value = false
  }
}

// 可重新提取的文件格式（图片走视觉大模型三节解读，文档重跑文本提取）
const MATERIAL_REEXTRACT_EXTS = new Set([
  '.png', '.jpg', '.jpeg', '.webp',
  '.pdf', '.docx', '.txt', '.md', '.csv', '.xlsx', '.xls', '.pptx'
])

function canReextractMaterial(m: StockMaterial): boolean {
  return m.kind === 'file' && MATERIAL_REEXTRACT_EXTS.has((m.ext || '').toLowerCase())
}

async function reextractPreviewMaterial() {
  const m = materialPreviewItem.value
  if (!m || materialReextracting.value) return
  materialReextracting.value = true
  try {
    const resp: any = await reextractMaterialText(m.id)
    const saved = resp?.data
    ElMessage.success(saved?.text_message || '重新提取完成')
    // 同步列表条目与预览内容（reextract 接口返回全文，无需再拉）
    const idx = stockMaterials.value.findIndex(x => x.id === m.id)
    if (idx >= 0 && saved) stockMaterials.value[idx] = { ...stockMaterials.value[idx], ...saved }
    if (saved) {
      materialPreviewItem.value = { ...m, ...saved }
      materialPreviewText.value = saved.extracted_text || ''
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '重新提取失败')
  } finally {
    materialReextracting.value = false
  }
}

// ═══ 知识卡（资料经大模型提炼为用户情报卡，写入猪周期知识库，一资料一卡覆盖更新） ═══
const intelCardVisible = ref(false)
const intelCardLoading = ref(false)
const intelCardDistilling = ref(false)
const intelCard = ref<IntelCard | null>(null)
const intelCardMaterial = ref<StockMaterial | null>(null)

function formatIntelTime(iso?: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  return isNaN(d.getTime()) ? iso : d.toLocaleString('zh-CN', { hour12: false })
}

async function openIntelCard(m: StockMaterial) {
  intelCardMaterial.value = m
  intelCard.value = null
  intelCardVisible.value = true
  intelCardLoading.value = true
  try {
    const resp: any = await fetchMaterialIntelCard(m.id)
    intelCard.value = resp?.data?.card ?? null
  } catch (e: any) {
    ElMessage.error(e?.message || '知识卡读取失败')
    intelCardVisible.value = false
  } finally {
    intelCardLoading.value = false
  }
}

async function distillIntelCard() {
  const m = intelCardMaterial.value
  if (!m || intelCardDistilling.value) return
  intelCardDistilling.value = true
  try {
    const resp: any = await distillMaterialIntel(m.id)
    const data = resp?.data
    if (data?.card) intelCard.value = data.card
    // 同步列表条目（distilled_at/intel_card_id → 已提炼标记）
    if (data?.material) {
      const idx = stockMaterials.value.findIndex(x => x.id === m.id)
      if (idx >= 0) stockMaterials.value[idx] = { ...stockMaterials.value[idx], ...data.material }
    }
    ElMessage.success('已提炼为知识卡，AI 分析可引用')
  } catch (e: any) {
    ElMessage.error(e?.message || '知识卡提炼失败')
  } finally {
    intelCardDistilling.value = false
  }
}

function formatFileSize(size?: number): string {
  if (!size && size !== 0) return ''
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

function materialHost(m: StockMaterial): string {
  try { return new URL(m.url || '').hostname } catch { return '' }
}

// ═══ 猪周期专属风险（概览风险栏插槽 · 行业世界模型驱动，仅覆盖猪周期龙头） ═══
// 清单模式：命中判定走行业注册表关联个股清单（原 PIG_COMPANY_KEYS 迁移至 industryRegistry）
const pigStock = computed(() => matchIndustryStock(PIG_RELATED_STOCKS, stockName.value))
const pigCovered = computed(() => !!pigStock.value)
const pigState = ref<PigCycleState | null>(null)
const pigL0 = ref<PigCycleL0State | null>(null)
const pigTerm = ref<TermWarnings | null>(null)

async function fetchPigRisks() {
  if (!pigCovered.value) return
  const [s, l, t] = await Promise.all([
    fetchPigCycleState({}).catch(() => null),
    fetchPigCycleL0({}).catch(() => null),
    fetchTermWarnings().catch(() => null),
  ])
  pigState.value = (s as any)?.data ?? s ?? null
  pigL0.value = (l as any)?.data ?? l ?? null
  pigTerm.value = (t as any)?.data ?? t ?? null
}

interface PigRiskItem { level: 'red' | 'orange' | 'gray'; text: string }
const pigRiskItems = computed<PigRiskItem[]>(() => {
  const items: PigRiskItem[] = []
  if (!pigCovered.value) return items
  // 保险丝（L0 规则层：触发即红灯，note 为后端给出的解释，缺失时用语义兜底）
  const f = pigL0.value?.fuses
  if (f) {
    const fuseDefs: Array<{ key: 'time' | 'space' | 'behavior' | 'falsify'; name: string; fallback: string }> = [
      { key: 'time', name: '时间保险丝', fallback: '上涨时长触及历史极值区间' },
      { key: 'space', name: '空间保险丝（估值分位）', fallback: '头均市值估值分位触及高位' },
      { key: 'behavior', name: '行为保险丝（情绪过热）', fallback: '龙头个股的持仓盈利已大量兑现、上方套牢盘形成反弹阻力（行业级情绪读数，非本股读数）' },
      { key: 'falsify', name: '看错信号（能繁回升）', fallback: '能繁母猪回升，去化逻辑被推翻' },
    ]
    for (const d of fuseDefs) {
      const it = f[d.key]
      if (it && fuseTriggered(it.status)) {
        // 行为保险丝的读数取自龙头个股（牧原）的筹码分布/持仓盈亏，属【行业级】情绪信号。
        // 个股页只给行业级结论，不复述龙头个股的成本价、股东人数等运营明细（完整 note 见猪周期工作台）。
        const note = d.key === 'behavior' ? '' : String(it.note || '').trim()
        items.push({ level: 'red', text: note ? `${d.name}已触发：${note}` : `${d.name}已触发：${d.fallback}。` })
      }
    }
  }
  // 期货升水警示灯（期限结构 live 才亮；degraded 诚实说明，不编造）
  const term = pigTerm.value
  if (term && term.status === 'live' && Array.isArray(term.warnings)) {
    for (const w of term.warnings) {
      items.push({
        level: w.code === 'deep_contango_overpriced' ? 'red' : 'orange',
        text: `${w.title} · ${w.detail}`,
      })
    }
  } else if (term && term.status === 'degraded' && term.reason) {
    items.push({ level: 'gray', text: `期货升水风险灯数据暂不可用（${term.reason}），该灯停用、不臆测。` })
  }
  // 猪粮比低于预警线（全行业亏损信号）
  const hgr = pigState.value?.cost_profit?.hog_grain_ratio
  if (hgr != null && Number(hgr) < 5) {
    items.push({ level: 'orange', text: `猪粮比 ${Number(hgr).toFixed(2)}，低于 5:1 预警线，全行业亏损中，关注产能去化节奏。` })
  }
  return items
})

// 「我的研究」· 猪周期计划与规则提醒（作战计划 + 实时亮灯）
const pigPlan = ref<PigCyclePlan | null>(null)

async function fetchPigPlan() {
  if (!pigCovered.value) return
  try {
    const resp: any = await fetchPigCyclePlanCurrent()
    pigPlan.value = resp?.data?.plan ?? null
  } catch {
    pigPlan.value = null
  }
}

// 「我的研究」· 最新每日结论（持仓视角闭环，股票×日期共享，每日 08:50 生成）
const dailyReview = ref<DailyReviewItem | null>(null)

async function fetchDailyReview() {
  try {
    const digits = code.value.replace(/\D/g, '').slice(-6)
    if (!digits) return
    const resp: any = await fetchDailyReviews({ code: digits, limit: 1 })
    dailyReview.value = resp?.data?.reviews?.[0] ?? null
  } catch {
    dailyReview.value = null
  }
}

// 「我的研究」P0 重组：置顶今日待办（待验证假设数 + 最新每日结论），一键去「我的判断」复盘
const journalPanelRef = ref<InstanceType<typeof ResearchJournalPanel> | null>(null)
const openHypothesisCount = ref(0)

// P4 报告与日志并置：分析结果卡「系统结论」旁对照展示该股最新一条研究判断
const lastJudgment = ref<ResearchJournalEntry | null>(null)

async function fetchLastJudgment() {
  try {
    const resp: any = await researchJournalApi.list(symbol.value)
    const items = resp?.items ?? resp?.data?.items ?? []
    lastJudgment.value = items.length ? items[0] : null
  } catch {
    lastJudgment.value = null  // 日志加载失败不影响分析结果卡
  }
}

function onJournalReviewSummary(payload: { openCount: number; openItems: unknown[] }) {
  openHypothesisCount.value = payload.openCount
  // 用户刚记录/编辑过日志（面板重载会重新 emit），同步刷新「我上次的判断」
  fetchLastJudgment()
}

function scrollToJournal() {
  const el = document.getElementById('mine-journal-anchor')
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function scrollToDailyReview() {
  const el = document.getElementById('mine-daily-review-anchor')
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const DAILY_REVIEW_FUSE_TAG: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
  safe: 'success', intact: 'success', waiting: 'info', armed: 'warning',
  warning: 'warning', triggered: 'danger', broken: 'danger', alarm: 'danger',
  'n/a': 'info'
}
const DAILY_REVIEW_FUSE_LABEL: Record<string, string> = {
  safe: '安全', intact: '依据还成立', armed: '已上膛', warning: '警戒',
  waiting: '拐点未现', pending_data: '数据待建', triggered: '已触发',
  broken: '依据已破', alarm: '已到期', 'n/a': '不适用'
}
const DAILY_REVIEW_FUSE_KEY: Record<string, string> = {
  time: '时间', space: '空间', behavior: '行为', falsify: '看错信号'
}
const dailyReviewHasSignals = computed(() => {
  const c = dailyReview.value?.coverage
  return c === 'full' || c === 'signals_mv' || c === 'signals_only'
})
const dailyReviewCoverageLabel = computed(() => {
  switch (dailyReview.value?.coverage) {
    case 'full': return '深度覆盖'
    case 'signals_mv': return '信号+估值'
    case 'signals_only': return '仅信号'
    case 'partial': return '清单外'
    default: return '覆盖度未知'
  }
})
const dailyReviewFuseRows = computed(() =>
  Object.entries(dailyReview.value?.facts?.fuses || {}).map(([key, status]) => ({
    key: DAILY_REVIEW_FUSE_KEY[key] || key,
    label: DAILY_REVIEW_FUSE_LABEL[status || ''] || status || '—',
    tag: DAILY_REVIEW_FUSE_TAG[status || ''] || 'info'
  })))

// stockName 异步就绪后才 covered，watch 首次变 true 时拉取（immediate 处理已就绪场景）
watch(pigCovered, (v) => {
  if (!v) return
  if (!pigL0.value) fetchPigRisks()
  if (!pigPlan.value) fetchPigPlan()
}, { immediate: true })

// ═══ 概念关系（一期：行业世界模型派生 + 基础信息兜底，非新建数据源） ═══
const falsifyTriggered = computed(() => {
  const fz = (pigL0.value?.fuses as any)?.falsify
  return fuseTriggered(fz?.status)
})

// 行业 universe 匹配（名称匹配，与行业面板 IndustryPanel 同款做法；清单统一在行业注册表维护）
const insHit = computed(() => matchIndustryStock(INSURANCE_RELATED_STOCKS, stockName.value))
const batHit = computed(() => matchIndustryStock(BATTERY_RELATED_STOCKS, stockName.value))
const autoHit = computed(() => matchIndustryStock(AUTO_RELATED_STOCKS, stockName.value))

const conceptSubText = computed(() => {
  const parts: string[] = []
  if (pigCovered.value) parts.push('猪周期研究体系')
  if (insHit.value) parts.push('保险行业工作台')
  if (batHit.value) parts.push('电池产业链工作台')
  if (autoHit.value) parts.push('汽车产业链工作台')
  return parts.length ? '来自行业世界模型 · ' + parts.join(' + ') : ''
})

interface ConceptTag { name: string; source: string; strength: 'strong' | 'weak' }
const conceptTags = computed<ConceptTag[]>(() => {
  if (pigCovered.value) {
    const tags: ConceptTag[] = [
      { name: '生猪养殖', source: '行业世界模型', strength: 'strong' },
      { name: '猪周期', source: '行业世界模型 + 猪周期研究体系', strength: 'strong' },
      { name: '头均市值估值', source: '猪周期 L0 规则层（估值分位保险丝）', strength: 'strong' },
      { name: '能繁母猪去化', source: '猪周期 L0 规则层（产能锚）', strength: 'strong' },
      { name: '饲料成本（玉米/豆粕）', source: '成本链拆解', strength: 'weak' },
      { name: '猪肉消费', source: '消费端观察', strength: 'weak' },
    ]
    // 动态概念：看错信号触发时补充（与概览风险栏同一判断口径）
    if (falsifyTriggered.value) {
      tags.push({ name: '去化逻辑被推翻（当前）', source: '猪周期 L0 规则层 · 看错信号', strength: 'strong' })
    }
    return tags
  }
  // 保险：派生自保险行业工作台口径（利率象限 / NBV 矩阵 / 浮盈池 / 保费月度）
  if (insHit.value) {
    const tags: ConceptTag[] = [
      { name: '保险', source: '行业归属（保险行业工作台）', strength: 'strong' },
      { name: '利率敏感', source: '利率象限 · 10Y 60 日方向（±15bp）', strength: 'strong' },
      { name: '负债景气（NBV）', source: 'NBV 矩阵 · 四家寿险同比均值', strength: 'strong' },
      { name: '权益浮盈池', source: '沪深300 60 日 ±10% 代理', strength: 'weak' },
      { name: '保费增长', source: '金融监管总局月度口径', strength: 'weak' },
    ]
    if (insHit.value.segment) tags.push({ name: insHit.value.segment, source: '本股板块（关联登记）', strength: 'strong' })
    return tags
  }
  // 电池：派生自电池产业链工作台口径（锂价三档 / 出清带 / 装机榜）
  if (batHit.value) {
    const tags: ConceptTag[] = [
      { name: '电池产业链', source: '行业归属（电池产业链工作台）', strength: 'strong' },
      { name: '碳酸锂价格周期', source: '锂价三档 · A 过热 / B 出清带 / C 深亏', strength: 'strong' },
      { name: '产能出清', source: '出清带分档（行业世界模型）', strength: 'strong' },
      { name: '动力电池装机', source: '月度装机榜（工作台读数）', strength: 'strong' },
    ]
    if (batHit.value.segment) tags.push({ name: batHit.value.segment, source: '本股环节（产业链登记）', strength: 'strong' })
    return tags
  }
  // 汽车：派生自汽车产业链工作台口径（乘联会渗透率 / 总量增速）
  if (autoHit.value) {
    const tags: ConceptTag[] = [
      { name: '汽车产业链', source: '行业归属（汽车产业链工作台）', strength: 'strong' },
      { name: 'NEV 渗透率', source: '乘联会狭义乘用车 · 月度', strength: 'strong' },
      { name: '总量增速', source: '乘联会月度同比（工作台读数）', strength: 'strong' },
    ]
    if (autoHit.value.segment) tags.push({ name: autoHit.value.segment, source: '本股环节（产业链登记）', strength: 'strong' })
    return tags
  }
  const ind = String((basics as any).industry || '').trim()
  return ind && ind !== '-' ? [{ name: ind, source: '股票基础信息', strength: 'weak' }] : []
})

interface ConceptRelation { name: string; code?: string; relation: string; tagType: 'primary' | 'success' | 'warning' | 'info'; note: string; go?: () => void }
// 通用同业关联：从行业 universe 清单派生同业对比卡片（排除本股，剩余成员逐个可跳转）
function peerRelations(list: Array<{ code: string; name: string; role: string }>, hit: { name: string } | null): ConceptRelation[] {
  const n = String(stockName.value || '').trim()
  return list
    .filter(s => s !== hit && !(n && n.includes(s.name)))
    .map(s => ({
      name: s.name,
      code: s.code,
      relation: '同业对比',
      tagType: 'primary',
      note: s.role,
      go: () => router.push({ name: 'StockDetail', params: { code: s.code } }),
    }))
}
const conceptRelations = computed<ConceptRelation[]>(() => {
  if (pigCovered.value) {
    // 同业对比（猪周期三龙头中的另两家，清单模式：从注册表清单派生，note 取登记角色）
    const rels: ConceptRelation[] = [
      ...peerRelations(PIG_RELATED_STOCKS, pigStock.value),
    ]
    rels.push({
      name: '生猪期货（LH）',
      relation: '价格锚定',
      tagType: 'warning',
      note: '远期合约升贴水反映市场对猪价的预期，期货升水过深是风险信号（见概览风险灯）。',
      go: () => { activeDetailTab.value = 'industry' },
    })
    rels.push({
      name: '能繁母猪存栏',
      relation: '周期锚',
      tagType: 'success',
      note: '产能端核心数据，去化进度决定周期反转节奏（行业面板 · 猪周期系列数据）。',
      go: () => { activeDetailTab.value = 'industry' },
    })
    return rels
  }
  // 保险：同业 NBV 矩阵 + 利率/权益双锚（派生自保险行业工作台口径）
  if (insHit.value) {
    return [
      ...peerRelations(INSURANCE_RELATED_STOCKS, insHit.value),
      {
        name: '10Y 国债收益率',
        relation: '利率锚',
        tagType: 'warning',
        note: '保险股核心定价锚：利率象限按 10Y 60 日方向 ±15bp 分档，利率趋势走弱压制投资端与估值（行业面板 · 利率象限读数）。',
        go: () => { activeDetailTab.value = 'industry' },
      },
      {
        name: '沪深300',
        relation: '权益市场',
        tagType: 'success',
        note: '投资端权益浮盈代理：沪深300 60 日 ±10% 分档观察保险资金权益浮盈池（行业面板 · 浮盈读数）。',
        go: () => { activeDetailTab.value = 'industry' },
      },
    ]
  }
  // 电池：产业链同业 + 锂价/装机双锚（派生自电池产业链工作台口径）
  if (batHit.value) {
    return [
      ...peerRelations(BATTERY_RELATED_STOCKS, batHit.value),
      {
        name: '碳酸锂价格',
        relation: '价格锚',
        tagType: 'warning',
        note: '产业链核心价格信号：锂价三档（A 过热 / B 出清带 / C 深亏）决定上下游盈利再分配（行业面板 · 锂价周期读数）。',
        go: () => { activeDetailTab.value = 'industry' },
      },
      {
        name: '动力电池装机',
        relation: '需求锚',
        tagType: 'success',
        note: '月度装机榜份额反映电芯厂竞争格局，装机动能决定中游排产（行业面板 · 装机榜读数）。',
        go: () => { activeDetailTab.value = 'industry' },
      },
    ]
  }
  // 汽车：同业 + 渗透率锚（派生自汽车产业链工作台口径）
  if (autoHit.value) {
    return [
      ...peerRelations(AUTO_RELATED_STOCKS, autoHit.value),
      {
        name: 'NEV 渗透率',
        relation: '需求锚',
        tagType: 'success',
        note: '乘联会狭义乘用车口径 · 月度：渗透率斜率决定电动化进度，总量增速决定行业蛋糕（行业面板 · 乘联会读数）。',
        go: () => { activeDetailTab.value = 'industry' },
      },
    ]
  }
  return []
})

// ═══ 完整时间线（一期：前端聚合已有数据，非新建数据源） ═══
const timelineRange = ref<'60d' | 'all'>('60d')
const timelineMoves = ref<Array<{ time: string; pct: number; close: number; prev: number; volume: number }>>([])
const timelineMovesLoading = ref(false)
const timelineMovesLoaded = ref(false)

async function fetchTimelineMoves() {
  if (timelineMovesLoaded.value || timelineMovesLoading.value) return
  timelineMovesLoading.value = true
  try {
    // 独立拉半年日K计算异动，与概览 K 线当前所选周期解耦
    const res = await stocksApi.getKline(code.value, 'day', 120, 'none')
    const d: any = (res as any)?.data || {}
    const items: any[] = Array.isArray(d.items) ? d.items : []
    const rows = items
      .map((it: any) => ({
        time: String(it.time || it.trade_time || it.trade_date || ''),
        close: Number(it.close ?? NaN),
        volume: Number(it.volume ?? it.vol ?? 0),
      }))
      .filter((r: any) => r.time && Number.isFinite(r.close))
    // ETF 波动小，用 2% 阈值；个股 5%
    const threshold = isEtf.value ? 2 : 5
    const moves: typeof timelineMoves.value = []
    for (let i = 1; i < rows.length; i++) {
      const prev = rows[i - 1].close
      const pct = prev > 0 ? ((rows[i].close - prev) / prev) * 100 : 0
      if (Math.abs(pct) >= threshold) moves.push({ ...rows[i], prev, pct })
    }
    timelineMoves.value = moves.slice(-40)
    timelineMovesLoaded.value = true
  } catch (e) {
    console.warn('⚠️ 计算行情异动失败:', e)
  } finally {
    timelineMovesLoading.value = false
  }
}

function timelineTs(v: unknown): number {
  const t = new Date(String(v || '')).getTime()
  return Number.isNaN(t) ? 0 : t
}

function formatTimelineVol(v: number): string {
  if (!Number.isFinite(v) || v <= 0) return ''
  if (v >= 1e8) return `${(v / 1e8).toFixed(2)}亿`
  if (v >= 1e4) return `${(v / 1e4).toFixed(2)}万`
  return String(v)
}

interface TimelineItem { time: string; ts: number; kind: string; kindType: 'primary' | 'success' | 'warning' | 'danger' | 'info'; title: string; detail: string; source: string; url?: string }

const timelineItems = computed<TimelineItem[]>(() => {
  const items: TimelineItem[] = []
  // 1) 行情异动（|涨跌幅| ≥ 阈值的交易日）
  for (const m of timelineMoves.value) {
    const vol = formatTimelineVol(m.volume)
    items.push({
      time: m.time, ts: timelineTs(m.time), kind: '行情异动',
      kindType: m.pct > 0 ? 'danger' : 'success',
      title: `单日${m.pct > 0 ? '上涨' : '下跌'} ${Math.abs(m.pct).toFixed(2)}%`,
      detail: `收盘 ${m.close.toFixed(2)}（前收 ${m.prev.toFixed(2)}）${vol ? ` · 成交量 ${vol}` : ''}`,
      source: '行情数据',
    })
  }
  // 2) 新闻公告
  for (const n of newsItems.value) {
    const isAnn = n.type === 'announcement'
    items.push({
      time: String(n.time || ''), ts: timelineTs(n.time),
      kind: isAnn ? '公告' : '新闻', kindType: isAnn ? 'warning' : 'info',
      title: n.title || '(无标题)', detail: '', source: n.source || '', url: n.url,
    })
  }
  // 3) 研究任务
  for (const t of stockTasks.value) {
    const tm = t.completed_at || t.created_at || ''
    items.push({
      time: formatTaskTime(tm), ts: timelineTs(tm), kind: '研究任务', kindType: 'primary',
      title: stockTaskTitle(t),
      detail: `${stockTaskTypeText(t.task_type)} · ${stockTaskStatusText(t.status)}`,
      source: '研究任务系统',
    })
  }
  // 4) 交易复盘
  for (const r of reviewHistory.items) {
    const tm = r.completed_at || r.created_at || ''
    const summary = String(r.summary || '').trim()
    items.push({
      time: formatTaskTime(tm), ts: timelineTs(tm), kind: '交易复盘', kindType: 'success',
      title: summary ? summary.slice(0, 60) : '交易复盘完成',
      detail: String(r.recommendation || '').trim(),
      source: '复盘系统',
    })
  }
  // 5) 操作留痕：首次买入
  if (positionData.real.has && positionData.real.buy_date) {
    const cost = Number(positionData.real.cost_price)
    items.push({
      time: String(positionData.real.buy_date), ts: timelineTs(positionData.real.buy_date),
      kind: '操作留痕', kindType: 'warning',
      title: '首次买入记录',
      detail: Number.isFinite(cost) && cost > 0 ? `买入成本 ${cost.toFixed(2)}` : '',
      source: '持仓记录',
    })
  }
  const valid = items.filter(x => x.ts > 0).sort((a, b) => b.ts - a.ts)
  if (timelineRange.value === '60d') {
    const cutoff = Date.now() - 60 * 24 * 3600 * 1000
    return valid.filter(x => x.ts >= cutoff)
  }
  return valid
})

// 时间线 Tab 激活时才计算行情异动（lazy 数据）
watch(activeDetailTab, (tab) => {
  if (tab === 'timeline') void fetchTimelineMoves()
})

function openExternal(url?: string) {
  if (url) window.open(url, '_blank', 'noopener')
}

function goToApiGuide() {
  router.push({ name: 'StockDataApiGuide', query: { code: code.value } })
}

// 分析历史记录数量（简化：基于已有报告推断）
const analysisHistoryCount = computed(() => {
  // 实际可从后端获取，这里先用 lastAnalysis 是否存在作为提示
  return lastAnalysis.value ? 1 : 0
})

// 持仓分析历史数量
const positionHistoryCount = computed(() => {
  return positionSummary.has ? 1 : 0
})

// K线周期切换
function handlePeriodChange(p: string) {
  // 仅更新 period，由 watch(period) 自动触发 fetchKline，避免重复请求
  period.value = p
}

</script>

<style scoped lang="scss">
.stock-detail {
  display: flex; flex-direction: column; gap: 16px;
}

/* ════════ 新版详情页布局 ════════ */
.stock-detail-redesign {
  display: flex;
  flex-direction: column;
  gap: 0; /* 子组件自带 margin-bottom */
  padding: 0;
  max-width: 1400px;
  margin: 0 auto;
}

.main-grid {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
  align-items: start;
}

/* 档案式 Tab 内容区 */
.stock-detail-tabs {
  margin-bottom: 16px;
}
.stock-detail-tabs :deep(.el-tabs__content) {
  padding: 16px;
}
.mine-tasks-card {
  margin-top: 16px;
}
.mine-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.mine-card-title {
  font-weight: 700;
  color: #1e293b;
}

/* 我的资料（收藏链接 + 文字笔记 + 上传文件） */
.materials-pane {
  min-height: 200px;
}
.materials-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.materials-toolbar-btns {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.materials-file-input {
  display: none;
}
.materials-hint {
  font-size: 13px;
  color: #64748b;
}
.materials-filters {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.materials-filter-select {
  width: 110px;
}
.materials-filter-count {
  font-size: 12px;
  color: #94a3b8;
}
.material-meta-tag {
  flex-shrink: 0;
}
.material-meta-tip {
  margin-left: 10px;
  font-size: 12px;
  color: #94a3b8;
}
.material-upload-file {
  margin-bottom: 12px;
  padding: 8px 12px;
  background: #f1f5f9;
  border-radius: 6px;
  font-size: 13px;
  color: #475569;
  word-break: break-all;
}
.material-item {
  margin-bottom: 10px;
  border-radius: 8px;
}
.material-item :deep(.el-card__body) {
  padding: 12px 14px;
}
.material-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.material-title {
  flex: 1;
  font-weight: 600;
  color: #1e293b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.material-actions {
  flex-shrink: 0;
}
.intel-card-body {
  min-height: 120px;
}
.intel-card-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.intel-card-meta-text {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.intel-card-points {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.intel-card-point {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  font-size: 13px;
  line-height: 1.6;
}
.intel-card-point-no {
  flex-shrink: 0;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 3px;
}
.intel-card-caveats {
  margin-top: 12px;
  padding: 8px 10px;
  border-radius: 6px;
  background: var(--el-color-warning-light-9);
  font-size: 12px;
  line-height: 1.6;
  color: var(--el-text-color-regular);
}
.intel-card-caveats-label {
  font-weight: 600;
  color: var(--el-color-warning);
  margin-right: 6px;
}
.intel-card-tags {
  margin-top: 12px;
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.intel-card-source {
  margin-top: 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.material-url {
  display: block;
  margin-top: 6px;
  margin-left: 44px;
  font-size: 12px;
  color: #2563eb;
  text-decoration: none;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.material-url:hover {
  text-decoration: underline;
}
.material-content {
  margin-top: 6px;
  margin-left: 44px;
  font-size: 13px;
  color: #475569;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}
.material-excerpt {
  margin-top: 6px;
  margin-left: 44px;
  font-size: 12px;
  color: #94a3b8;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  cursor: pointer;
}
.material-excerpt:hover {
  color: #3b82f6;
}
.material-preview-body {
  max-height: 60vh;
  overflow: auto;
  min-height: 60px;
}
.material-preview-section {
  margin-bottom: 16px;
}
.material-preview-section:last-child {
  margin-bottom: 0;
}
.material-preview-section-title {
  margin-bottom: 6px;
  padding-left: 8px;
  border-left: 3px solid #3b82f6;
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
}
.material-preview-section-body {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  line-height: 1.7;
  color: #475569;
}
.material-preview-remark {
  margin-top: 12px;
  padding: 8px 10px;
  background: #f8fafc;
  border-radius: 6px;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  line-height: 1.6;
  color: #64748b;
}
.material-preview-meta {
  margin-top: 14px;
  padding-top: 8px;
  border-top: 1px dashed #e2e8f0;
  font-size: 12px;
  color: #94a3b8;
}
.material-preview-text {
  max-height: 60vh;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  line-height: 1.7;
  color: #475569;
}
.material-file-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
  margin-left: 44px;
  font-size: 12px;
  color: #64748b;
}
.material-file-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.material-file-hint {
  font-size: 12px;
  color: #64748b;
}

@media (max-width: 1024px) {
  .main-grid {
    grid-template-columns: 1fr;
  }
}

/* 复盘详情对话框样式（保留） */
.review-detail-content {
  .section {
    margin-bottom: 16px;
  }
  .section-title {
    font-size: 15px;
    font-weight: 700;
    margin-bottom: 8px;
    color: var(--el-text-color-primary);
  }
  .summary {
    font-size: 14px;
    line-height: 1.7;
    color: var(--el-text-color-regular);
  }
  .analysis-card {
    padding: 12px;
    border-radius: 8px;
    background: var(--el-fill-color-light);
    h4 {
      font-size: 14px;
      margin-bottom: 8px;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    &.strengths h4 { color: #16a34a; }
    &.weaknesses h4 { color: #ef4444; }
  }
  .suggestions {
    font-size: 13px;
    line-height: 1.7;
    color: var(--el-text-color-regular);
  }
  .positive { color: #ef4444; font-weight: 600; }
  .negative { color: #16a34a; font-weight: 600; }
}

.detail-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 40px;
  font-size: 14px;
  color: var(--el-text-color-secondary);
}

.reports-dialog {
  .report-content {
    min-height: 500px;
  }
}

.header { display: flex; justify-content: space-between; align-items: center; }
.title { display: flex; flex-direction: column; gap: 8px; }
.title-main { display: flex; align-items: center; gap: 12px; }
.title-meta { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.meta-text { font-size: 12px; color: var(--el-text-color-secondary); }
.code { font-size: 22px; font-weight: 700; }
.name { font-size: 18px; color: var(--el-text-color-regular); }
.actions { display: flex; gap: 8px; }

.quote-card { border-radius: 12px; }
.quote { display: flex; flex-direction: column; gap: 8px; }
.price-row { display: flex; align-items: center; gap: 12px; }
.price { font-size: 32px; font-weight: 800; }
.change { font-size: 16px; font-weight: 700; }
.up { color: #e53935; }
.down { color: #16a34a; }
.stats { display: grid; grid-template-columns: repeat(8, 1fr); gap: 10px; margin-top: 6px; }
.stats .item { display: flex; flex-direction: column; font-size: 12px; color: var(--el-text-color-secondary); }
.stats .item b { color: var(--el-text-color-primary); font-size: 14px; }

.factor-hints {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--el-border-color-lighter);
}

.factor-hints-title {
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.factor-hints-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.factor-hint-tag {
  cursor: help;
}

.factor-hint-popover {
  display: flex;
  flex-direction: column;
  gap: 6px;
  line-height: 1.6;
}

.factor-hint-popover-title {
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.factor-hint-line {
  color: var(--el-text-color-regular);
  font-size: 13px;
}

.body { margin-top: 4px; }
.card-hd { display: flex; align-items: center; justify-content: space-between; }
.k-chart { height: 320px; }
.legend { margin-top: 8px; font-size: 12px; color: var(--el-text-color-secondary); }

.news-card .news-list { display: flex; flex-direction: column; }
.news-item { padding: 10px 12px; border-bottom: 1px solid var(--el-border-color-lighter); transition: background-color .2s ease; }
.news-item:last-child { border-bottom: none; }
.news-item:hover { background: var(--el-fill-color-light); border-radius: 8px; }
.news-item .row { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }
.news-item .left { display: flex; align-items: flex-start; gap: 8px; flex: 1 1 auto; min-width: 0; }
.news-item .tag { flex: 0 0 auto; }
.news-item .title { font-weight: 600; display: flex; align-items: center; gap: 6px; flex: 1 1 auto; min-width: 0; }
.news-item .title a, .news-item .title span { color: var(--el-text-color-primary); text-decoration: none; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; overflow: hidden; }
.news-item .title a:hover { text-decoration: underline; }
.news-item .ext { color: var(--el-text-color-placeholder); font-size: 14px; }
.news-item .title:hover .ext { color: var(--el-color-primary); }
.news-item .right { color: var(--el-text-color-secondary); font-size: 12px; white-space: nowrap; margin-left: 8px; }
.news-item .meta { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 4px; }

.facts { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.fact { display: flex; flex-direction: column; font-size: 12px; }
.fact b { font-size: 14px; color: var(--el-text-color-primary); }
.financial-card { margin-top: 12px; }
.raw-section-summary { margin-top: 12px; display: flex; flex-direction: column; gap: 8px; }
.raw-title { font-size: 12px; color: var(--el-text-color-secondary); }
.raw-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.raw-hint { font-size: 12px; color: var(--el-text-color-secondary); line-height: 1.5; }

.quick-actions { display: flex; flex-direction: column; gap: 8px; }

@media (max-width: 1024px) {
  .stats { grid-template-columns: repeat(4, 1fr); }
  .header { flex-direction: column; align-items: flex-start; gap: 12px; }
  .actions { flex-wrap: wrap; }
}

/* 报告相关样式 */
.reports-section {
  margin-top: 8px;
}

.reports-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  margin-top: 8px;
}

.reports-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  display: flex;
  align-items: center;
  gap: 6px;
}

.reports-preview {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  padding: 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
}

.report-tag {
  cursor: pointer;
  transition: all 0.2s ease;
  font-size: 13px;
  padding: 6px 12px;
}

.report-tag:hover {
  transform: translateY(-2px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

/* 报告对话框样式 */
.reports-dialog :deep(.el-dialog__body) {
  padding: 0;
}

.report-content {
  padding: 20px;
}

.markdown-body {
  font-size: 14px;
  line-height: 1.8;
  color: var(--el-text-color-primary);
}

.markdown-body h1 {
  font-size: 24px;
  font-weight: 700;
  margin: 20px 0 16px;
  padding-bottom: 8px;
  border-bottom: 2px solid var(--el-border-color);
}

.markdown-body h2 {
  font-size: 20px;
  font-weight: 600;
  margin: 16px 0 12px;
}

.markdown-body h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 12px 0 8px;
}

.markdown-body p {
  margin: 8px 0;
}

.markdown-body ul, .markdown-body ol {
  margin: 8px 0;
  padding-left: 24px;
}

.markdown-body li {
  margin: 4px 0;
}

.markdown-body code {
  background: var(--el-fill-color-light);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'Courier New', monospace;
}

.markdown-body pre {
  background: var(--el-fill-color-light);
  padding: 12px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 12px 0;
}

.markdown-body blockquote {
  border-left: 4px solid var(--el-color-primary);
  padding-left: 12px;
  margin: 12px 0;
  color: var(--el-text-color-secondary);
}

.markdown-body table {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
}

.markdown-body th, .markdown-body td {
  border: 1px solid var(--el-border-color);
  padding: 8px 12px;
  text-align: left;
}

.markdown-body th {
  background: var(--el-fill-color-light);
  font-weight: 600;
}

.analysis-detail-card .detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 分析时间元信息 */
.analysis-meta {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 8px 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.analysis-meta .analysis-time {
  display: flex;
  align-items: center;
  gap: 6px;
}

.analysis-meta .el-icon {
  font-size: 14px;
}

/* 同步状态提示 */
.sync-status {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 12px;
  padding: 8px 12px;
  background: #f0f9ff;
  border-radius: 6px;
  border: 1px solid #bae6fd;
  font-size: 13px;
  color: #0369a1;
}

.sync-status .el-icon {
  font-size: 14px;
  color: #0284c7;
}

.sync-info {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

// ============================================================================
// 持仓分析摘要卡片
// ============================================================================
.position-analysis-card {
  margin-top: 16px;
  border-left: 3px solid var(--el-color-primary);

  .card-hd {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
  }

  .card-hd-title {
    display: flex;
    align-items: center;
    gap: 6px;
    font-weight: 600;
    color: var(--el-text-color-primary);
  }

  .card-hd-tag {
    margin-left: 4px;
    font-weight: normal;
  }

  .card-hd-actions {
    display: flex;
    gap: 4px;
  }

  .position-summary {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .snapshot-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    padding: 12px;
    background: var(--el-fill-color-lighter);
    border-radius: 6px;
  }

  .snap-item {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .snap-label {
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }

  .snap-value {
    font-size: 15px;
    color: var(--el-text-color-primary);
  }

  .pnl-positive {
    color: var(--el-color-success);
  }

  .pnl-negative {
    color: var(--el-color-danger);
  }

  .ai-advice {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .advice-row {
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 14px;
  }

  .advice-label {
    color: var(--el-text-color-secondary);
  }

  .advice-conclusion {
    display: flex;
    align-items: flex-start;
    gap: 6px;
    padding: 10px 12px;
    background: var(--el-color-primary-light-9);
    border-left: 3px solid var(--el-color-primary);
    border-radius: 4px;
    font-size: 14px;
    line-height: 1.5;
    color: var(--el-text-color-primary);
  }

  .advice-icon {
    color: var(--el-color-primary);
    flex-shrink: 0;
    margin-top: 2px;
  }

  .advice-keypoints {
    padding: 10px 12px;
    background: var(--el-color-warning-light-9);
    border-left: 3px solid var(--el-color-warning);
    border-radius: 4px;
  }

  .keypoints-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--el-color-warning-dark);
    margin-bottom: 6px;
  }

  .keypoints-list {
    margin: 0;
    padding-left: 20px;
    font-size: 13px;
    line-height: 1.6;
    color: var(--el-text-color-regular);
  }
}

// ============================================================================
// 交易复盘摘要卡片
// ============================================================================
.trade-review-card {
  margin-top: 16px;
  border-left: 3px solid var(--el-color-success);

  .card-hd {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
  }

  .card-hd-title {
    display: flex;
    align-items: center;
    gap: 6px;
    font-weight: 600;
    color: var(--el-text-color-primary);
  }

  .card-hd-tag {
    margin-left: 4px;
    font-weight: normal;
  }

  .card-hd-actions {
    display: flex;
    gap: 4px;
  }

  .review-summary {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .review-meta {
    display: flex;
    gap: 24px;
    padding: 10px 12px;
    background: var(--el-fill-color-lighter);
    border-radius: 6px;
  }

  .meta-item {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 14px;
  }

  .meta-label {
    color: var(--el-text-color-secondary);
  }

  .meta-value {
    color: var(--el-text-color-primary);
  }

  .review-conclusion,
  .review-recommendation {
    padding: 10px 12px;
    background: var(--el-fill-color-lighter);
    border-radius: 6px;
  }

  .review-recommendation {
    background: var(--el-color-success-light-9);
  }

  .conclusion-title {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    font-weight: 600;
    color: var(--el-text-color-secondary);
    margin-bottom: 6px;
  }

  .conclusion-text {
    font-size: 14px;
    line-height: 1.6;
    color: var(--el-text-color-primary);
  }
}

// ============================================================================
// 复盘详情弹窗
// ============================================================================
.detail-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
  gap: 8px;
  color: var(--el-text-color-secondary);
}

.review-detail-content {
  .detail-section {
    margin-bottom: 24px;

    &:last-child {
      margin-bottom: 0;
    }
  }

  .section-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--el-text-color-primary);
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--el-border-color-lighter);
  }

  .content-box {
    padding: 12px;
    background: var(--el-fill-color-lighter);
    border-radius: 6px;
  }

  .review-list {
    padding-left: 20px;
    margin: 0;

    li {
      margin-bottom: 8px;
      font-size: 14px;
      line-height: 1.6;
      color: var(--el-text-color-primary);

      &:last-child {
        margin-bottom: 0;
      }
    }
  }
}

.pnl-positive {
  color: var(--el-color-success) !important;
}

.pnl-negative {
  color: var(--el-color-danger) !important;
}

.positive {
  color: var(--el-color-success) !important;
}

.negative {
  color: var(--el-color-danger) !important;
}

// 复盘详情完整样式
.review-detail-content {
  .section {
    margin-bottom: 20px;

    .section-title {
      font-size: 15px;
      font-weight: 600;
      color: var(--el-text-color-primary);
      margin-bottom: 12px;
      display: flex;
      align-items: center;
      gap: 6px;
    }
  }

  .summary {
    padding: 12px;
    background: var(--el-fill-color-light);
    border-radius: 8px;
  }

  .analysis-card {
    padding: 16px;
    border-radius: 8px;
    background: var(--el-bg-color-page);

    h4 {
      margin: 0 0 12px;
      font-size: 14px;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 6px;
    }

    &.strengths {
      background: var(--el-color-success-light-9);
      border: 1px solid var(--el-color-success-light-8);
    }

    &.weaknesses {
      background: var(--el-color-danger-light-9);
      border: 1px solid var(--el-color-danger-light-8);
    }
  }

  .suggestions {
    padding: 12px;
    background: var(--el-color-primary-light-9);
    border-radius: 8px;
  }

  .markdown-content {
    :deep(p) {
      margin: 0 0 8px;
      line-height: 1.6;
      color: var(--el-text-color-primary);

      &:last-child {
        margin-bottom: 0;
      }
    }

    :deep(ul), :deep(ol) {
      padding-left: 20px;
      margin: 0 0 8px;
    }

    :deep(li) {
      margin-bottom: 4px;
      line-height: 1.6;
    }
  }
}

// ============================================================================
// 持仓信息卡片
// ============================================================================
.position-card {
  margin-bottom: 16px;

  .position-info {
    .position-section {
      margin-bottom: 16px;

      &:last-child {
        margin-bottom: 0;
      }
    }

    .position-section-title {
      margin-bottom: 10px;
    }

    .position-grid {
      display: grid;
      grid-template-columns: repeat(5, 1fr);
      gap: 12px;

      .pos-item {
        text-align: center;

        .pos-label {
          display: block;
          font-size: 12px;
          color: var(--el-text-color-secondary);
          margin-bottom: 4px;
        }

        .pos-value {
          font-size: 14px;
          font-weight: 600;
          color: var(--el-text-color-primary);

          &.positive {
            color: #f56c6c;
          }

          &.negative {
            color: #67c23a;
          }
        }
      }
    }
  }
}

/* 概览风险栏 · 猪周期专属风险（父组件传入插槽，子组件 scoped 样式不生效，需在本组件定义） */
.pig-risk-item {
  display: flex;
  gap: 8px;
  padding: 7px 0;
  border-top: 1px dashed var(--el-border-color-lighter, #eef2f7);
  align-items: flex-start;

  &:first-child {
    border-top: none;
  }

  .risk-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-top: 5px;
    flex: none;

    &.is-red {
      background: #f56c6c;
      box-shadow: 0 0 0 3px rgba(245, 108, 108, .15);
    }

    &.is-orange {
      background: #e6a23c;
      box-shadow: 0 0 0 3px rgba(230, 162, 60, .15);
    }

    &.is-gray {
      background: #909399;
    }
  }

  .ri-body {
    font-size: 12px;
    line-height: 1.6;
    color: var(--el-text-color-regular, #606266);
  }
}

/* 我的研究 P0 重组：分区标签 + 置顶待办 + 折叠区 */
.mine-section-label {
  margin: 14px 0 8px;
  padding-left: 8px;
  border-left: 3px solid var(--el-color-primary);
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.mine-todo-rows {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.mine-todo-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.mine-todo-icon {
  flex: 0 0 auto;
  font-size: 16px;
}
.mine-todo-text {
  flex: 1;
  font-size: 13px;
  color: var(--el-text-color-regular);
  min-width: 0;
}
.mine-todo-text b {
  color: var(--el-color-primary);
}
.mine-todo-clip {
  display: block;
  margin-top: 2px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mine-collapse {
  margin-top: 14px;
  border-top: none;
}
.mine-collapse :deep(.el-collapse-item__header) {
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.mine-collapse :deep(.el-collapse-item__content) {
  padding-bottom: 8px;
}

/* 我的研究 · 猪周期计划与规则提醒 */
.pig-plan-sub {
  font-size: 11px;
  color: var(--el-text-color-placeholder, #c0c4cc);
}

.pig-plan-head {
  display: flex;
  gap: 10px;
  align-items: center;
}

.pig-plan-grade {
  font-size: 13px;
  color: var(--el-text-color-primary, #1e293b);
}

.pig-plan-date {
  margin-left: auto;
  font-size: 12px;
  color: var(--el-text-color-secondary, #94a3b8);
}

.pig-plan-rule {
  font-size: 13px;
  color: var(--el-text-color-regular, #4b5563);
  margin: 10px 0 0;
}

.pig-plan-section {
  font-size: 12px;
  font-weight: 600;
  color: var(--el-text-color-secondary, #94a3b8);
  margin: 14px 0 4px;
}

.pig-plan-item {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  padding: 5px 0;
  font-size: 13px;
  line-height: 1.6;
}

.pig-plan-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-top: 6px;
  flex: none;

  &.is-on {
    background: #67c23a;
    box-shadow: 0 0 0 3px rgba(103, 194, 58, .15);
  }

  &.is-off {
    background: #c0c4cc;
  }

  &.is-gap {
    background: #e6a23c;
    box-shadow: 0 0 0 3px rgba(230, 162, 60, .15);
  }

  &.is-triggered {
    background: #f56c6c;
    box-shadow: 0 0 0 3px rgba(245, 108, 108, .15);
  }
}

.pig-plan-name {
  font-weight: 500;
  color: var(--el-text-color-primary, #1e293b);
  flex: none;
}

.pig-plan-basis {
  color: var(--el-text-color-secondary, #94a3b8);
  font-size: 12px;
}

.pig-plan-ready {
  margin-top: 10px;
}

.pig-plan-note {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed var(--el-border-color-lighter, #eef2f7);
  font-size: 12px;
  color: var(--el-text-color-secondary, #94a3b8);
}

.pig-plan-empty {
  font-size: 13px;
  color: var(--el-text-color-secondary, #94a3b8);
  line-height: 1.8;
  padding: 8px 0;
}

.daily-review-summary {
  font-size: 13px;
  line-height: 1.9;
  white-space: pre-wrap;
  word-break: break-word;
}

.daily-review-fuses {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

/* ════════ 概念关系 Tab ════════ */
.concept-pane {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.concept-card-header {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.concept-card-title {
  font-weight: 600;
  font-size: 14px;
}

.concept-sub {
  font-size: 12px;
  color: var(--el-text-color-secondary, #94a3b8);
}

.concept-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.concept-tag {
  cursor: default;
}

.concept-source-line {
  margin-top: 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary, #94a3b8);
}

.relation-card {
  cursor: pointer;
  margin-bottom: 12px;
}

.relation-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.relation-name {
  font-weight: 600;
}

.relation-code {
  margin: 4px 0;
  font-size: 12px;
  color: var(--el-text-color-secondary, #94a3b8);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}

.relation-note {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--el-text-color-regular, #606266);
}

/* ════════ 完整时间线 Tab ════════ */
.timeline-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.timeline-meta {
  font-size: 12px;
  color: var(--el-text-color-secondary, #94a3b8);
}

.stock-timeline {
  padding: 8px 4px 8px 8px;
}

.tl-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tl-kind {
  flex-shrink: 0;
}

.tl-title {
  font-weight: 500;
}

.tl-title.is-link {
  cursor: pointer;
  color: var(--el-color-primary, #409eff);
}

.tl-title.is-link:hover {
  text-decoration: underline;
}

.tl-detail {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-regular, #606266);
}

.tl-source {
  margin-top: 2px;
  font-size: 12px;
  color: var(--el-text-color-secondary, #94a3b8);
}
</style>
