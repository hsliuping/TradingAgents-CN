<template>
  <div class="stock-detail">
    <!-- 顶部：代码 / 名称 / 操作 -->
    <div class="header">
      <div class="title">
        <div class="title-main">
          <div class="code">{{ code }}</div>
          <div class="name">{{ stockName || '-' }}</div>
          <el-tag size="small">{{ marketLabel }}</el-tag>
        </div>
        <div v-if="isEtf" class="title-meta">
          <el-tag v-if="etfBasics.fundType" size="small" effect="plain" type="success">{{ etfBasics.fundType }}</el-tag>
          <el-tag v-if="etfBasics.trackIndex" size="small" effect="plain" type="info">跟踪 {{ etfBasics.trackIndex }}</el-tag>
          <span v-if="etfBasics.management" class="meta-text">管理人：{{ etfBasics.management }}</span>
        </div>
      </div>
      <div class="actions">
        <el-button @click="onToggleFavorite">
          <el-icon><Star /></el-icon> {{ favoriteButtonText }}
        </el-button>
        <el-button
          type="primary"
          @click="showSyncDialog"
          :loading="syncLoading"
        >
          <el-icon><Refresh /></el-icon> {{ syncButtonText }}
        </el-button>
        <el-button type="warning" @click="clearCache" :loading="clearCacheLoading">
          <el-icon><Delete /></el-icon> 清除缓存
        </el-button>
        <el-button type="success" @click="goPaperTrading">
          <el-icon><CreditCard /></el-icon> 模拟交易
        </el-button>
      </div>
    </div>

    <!-- 报价条 -->
    <el-card class="quote-card" shadow="hover">
      <div class="quote">
        <div class="price-row">
          <div class="price" :class="changeClass">{{ fmtPrice(quote.price) }}</div>
          <div class="change" :class="changeClass">
            <span>{{ fmtPercent(quote.changePercent) }}</span>
          </div>
          <el-tag type="info" size="small">{{ refreshText }}</el-tag>
          <el-button text size="small" @click="refreshMockQuote" :icon="Refresh">刷新</el-button>
        </div>
        <div class="stats">
          <div class="item"><span>今开</span><b>{{ fmtPrice(quote.open) }}</b></div>
          <div class="item"><span>最高</span><b>{{ fmtPrice(quote.high) }}</b></div>
          <div class="item"><span>最低</span><b>{{ fmtPrice(quote.low) }}</b></div>
          <div class="item"><span>昨收</span><b>{{ fmtPrice(quote.prevClose) }}</b></div>
          <div class="item">
            <span>成交量</span>
            <b>
              {{ fmtVolume(quote.volume) }}
              <el-tooltip v-if="quote.tradeDate && !isToday(quote.tradeDate)" :content="`数据日期: ${quote.tradeDate}`" placement="top">
                <el-tag size="small" type="warning" style="margin-left: 4px;">{{ formatDateTag(quote.tradeDate) }}</el-tag>
              </el-tooltip>
            </b>
          </div>
          <div class="item">
            <span>成交额</span>
            <b>
              {{ fmtAmount(quote.amount) }}
              <el-tooltip v-if="quote.tradeDate && !isToday(quote.tradeDate)" :content="`数据日期: ${quote.tradeDate}`" placement="top">
                <el-tag size="small" type="warning" style="margin-left: 4px;">{{ formatDateTag(quote.tradeDate) }}</el-tag>
              </el-tooltip>
            </b>
          </div>
          <div class="item">
            <span>换手率</span>
            <b>
              {{ fmtPercent(quote.turnover) }}
              <el-tooltip v-if="quote.turnoverDate && !isToday(quote.turnoverDate)" :content="`数据日期: ${quote.turnoverDate}`" placement="top">
                <el-tag size="small" type="warning" style="margin-left: 4px;">{{ formatDateTag(quote.turnoverDate) }}</el-tag>
              </el-tooltip>
            </b>
          </div>
          <div class="item">
            <span>振幅</span>
            <b>
              {{ Number.isFinite(quote.amplitude) ? quote.amplitude.toFixed(2) + '%' : '-' }}
              <el-tooltip v-if="quote.amplitudeDate && !isToday(quote.amplitudeDate)" :content="`数据日期: ${quote.amplitudeDate}`" placement="top">
                <el-tag size="small" type="warning" style="margin-left: 4px;">{{ formatDateTag(quote.amplitudeDate) }}</el-tag>
              </el-tooltip>
            </b>
          </div>
        </div>
        <!-- 同步状态提示 -->
        <div class="sync-status" v-if="quote.updatedAt || syncStatus">
          <el-icon><Clock /></el-icon>
          <span class="sync-info">
            <!-- 🔥 优先显示股票自己的更新时间 -->
            <template v-if="quote.updatedAt">
              数据更新: {{ formatQuoteUpdateTime(quote.updatedAt) }}
            </template>
            <template v-else-if="syncStatus">
              后端同步: {{ formatSyncTime(syncStatus.last_sync_time) }}
              <span v-if="syncStatus.interval_seconds">{{ formatSyncInterval(syncStatus.interval_seconds) }}</span>
            </template>
            <el-tag
              v-if="syncStatus?.data_source"
              size="small"
              type="success"
              style="margin-left: 4px"
            >
              {{ syncStatus.data_source }}
            </el-tag>
          </span>
        </div>
      </div>
    </el-card>

    <el-row :gutter="16" class="body">
      <el-col :span="18">
        <!-- K线蜡烛图 -->
        <el-card shadow="hover">
          <template #header>
            <div class="card-hd">
              <div>{{ klineCardTitle }}</div>
              <div class="periods">
                <el-segmented v-model="period" :options="periodOptions" size="small" />
              </div>
            </div>
          </template>
          <div class="kline-container">
            <v-chart class="k-chart" :option="kOption" autoresize />
            <div class="legend">当前周期：{{ period }} · 数据源：{{ klineSource || '-' }} · 最近：{{ lastKTime || '-' }} · 收：{{ fmtPrice(lastKClose) }}</div>
          </div>
        </el-card>

        <!-- 详细分析结果（方案B）：仅在进行中或有结果时显示 -->
        <el-card v-if="analysisStatus==='running' || lastAnalysis" shadow="hover" class="analysis-detail-card" id="analysis-detail">
          <template #header><div class="card-hd">详细分析结果</div></template>
          <div v-if="analysisStatus==='running'" class="running">
            <el-progress :percentage="analysisProgress" :text-inside="true" style="width:100%" />
            <div class="hint">{{ analysisMessage || '正在生成分析报告…' }}</div>
          </div>
          <div v-else class="detail">
            <!-- 分析时间和信心度 -->
            <div class="analysis-meta">
              <span class="analysis-time">
                <el-icon><Clock /></el-icon>
                分析时间：{{ formatAnalysisTime(lastTaskInfo?.end_time) }}
              </span>
              <span class="confidence">
                <el-icon><TrendCharts /></el-icon>
                信心度：{{ fmtConf(lastAnalysis?.confidence_score ?? lastAnalysis?.overall_score) }}
              </span>
            </div>

            <!-- 一句话分析 -->
            <div class="recommendation-box">
              <div class="recommendation-header">
                <el-icon class="icon"><TrendCharts /></el-icon>
                <span class="title">一句话分析</span>
              </div>
              <div class="recommendation-content">
                <div class="recommendation-text markdown-body" v-html="renderMarkdown(oneSentenceConclusion)"></div>
              </div>
            </div>

            <!-- 详细报告展示 -->
            <div v-if="lastAnalysis?.reports && Object.keys(lastAnalysis.reports).length > 0" class="reports-section">
              <el-divider />
              <div class="reports-header">
                <span class="reports-title">📊 详细分析报告 ({{ Object.keys(lastAnalysis.reports).length }})</span>
                <el-button
                  type="primary"
                  plain
                  @click="showReportsDialog = true"
                  :icon="Document"
                >
                  查看完整报告
                </el-button>
              </div>

              <!-- 报告列表预览 -->
              <div class="reports-preview">
                <el-tag
                  v-for="key in reportKeys"
                  :key="key"
                  size="small"
                  effect="plain"
                  class="report-tag"
                  @click="openReport(key)"
                >
                  {{ formatReportName(key) }}
                </el-tag>
              </div>
            </div>
          </div>
        </el-card>

        <!-- 持仓分析摘要：仅在该股有持仓分析记录时显示 -->
        <el-card v-if="positionSummary.has" shadow="hover" class="position-analysis-card">
          <template #header>
            <div class="card-hd">
              <div class="card-hd-title">
                <el-icon><PieChart /></el-icon>
                <span>持仓分析摘要</span>
                <el-tag size="small" type="info" effect="plain" class="card-hd-tag">
                  {{ formatAnalysisTime(positionSummary.completedAt) }}
                </el-tag>
              </div>
              <div class="card-hd-actions">
                <el-button text size="small" @click="goToPositionAnalysis">
                  <el-icon><Plus /></el-icon> 重新分析
                </el-button>
                <el-button text size="small" @click="viewPositionTaskDetail">
                  <el-icon><View /></el-icon> 查看详情
                </el-button>
              </div>
            </div>
          </template>
          <div class="position-summary">
            <!-- 持仓快照 -->
            <div v-if="positionSummary.snapshot" class="snapshot-grid">
              <div class="snap-item">
                <span class="snap-label">成本价</span>
                <b class="snap-value">¥{{ fmtPrice(positionSummary.snapshot.cost_price) }}</b>
              </div>
              <div class="snap-item">
                <span class="snap-label">现价</span>
                <b class="snap-value">¥{{ fmtPrice(positionSummary.snapshot.current_price) }}</b>
              </div>
              <div class="snap-item">
                <span class="snap-label">持仓</span>
                <b class="snap-value">{{ positionSummary.snapshot.quantity }} 股</b>
              </div>
              <div class="snap-item">
                <span class="snap-label">浮动盈亏</span>
                <b class="snap-value" :class="pnlClass(positionSummary.snapshot.unrealized_pnl)">
                  {{ formatPnl(positionSummary.snapshot.unrealized_pnl, positionSummary.snapshot.unrealized_pnl_pct) }}
                </b>
              </div>
              <div class="snap-item">
                <span class="snap-label">持仓天数</span>
                <b class="snap-value">{{ positionSummary.snapshot.holding_days || '-' }} 天</b>
              </div>
              <div class="snap-item">
                <span class="snap-label">仓位占比</span>
                <b class="snap-value">{{ formatPercent(positionSummary.snapshot.position_pct) }}</b>
              </div>
            </div>

            <!-- AI 建议 -->
            <div class="ai-advice">
              <div class="advice-row">
                <span class="advice-label">AI 建议</span>
                <el-tag :type="actionTagType(positionSummary.action)" effect="dark" size="small">
                  {{ actionLabel(positionSummary.action) }}
                </el-tag>
                <span class="advice-confidence">信心度 {{ positionSummary.confidence || '-' }}%</span>
              </div>
              <div v-if="positionSummary.conclusion" class="advice-conclusion">
                <el-icon class="advice-icon"><InfoFilled /></el-icon>
                <span>{{ positionSummary.conclusion }}</span>
              </div>
              <div v-if="positionSummary.keyPoints?.length" class="advice-keypoints">
                <div class="keypoints-title">⚠ 关键风险点</div>
                <ul class="keypoints-list">
                  <li v-for="(point, idx) in positionSummary.keyPoints.slice(0, 3)" :key="idx">{{ point }}</li>
                </ul>
              </div>
            </div>
          </div>
        </el-card>

        <!-- 交易复盘摘要：仅在该股有复盘记录时显示 -->
        <el-card v-if="reviewSummary.has" shadow="hover" class="trade-review-card">
          <template #header>
            <div class="card-hd">
              <div class="card-hd-title">
                <el-icon><TrendCharts /></el-icon>
                <span>交易复盘摘要</span>
                <el-tag size="small" type="info" effect="plain" class="card-hd-tag">
                  {{ formatAnalysisTime(reviewSummary.completedAt) }}
                </el-tag>
              </div>
              <div class="card-hd-actions">
                <el-button text size="small" @click="goToTradeReview">
                  <el-icon><Plus /></el-icon> 重新复盘
                </el-button>
                <el-button text size="small" @click="viewReviewTaskDetail">
                  <el-icon><View /></el-icon> 查看详情
                </el-button>
              </div>
            </div>
          </template>
          <div class="review-summary">
            <!-- 复盘评分 -->
            <div class="review-meta">
              <div class="meta-item">
                <span class="meta-label">风险等级</span>
                <el-tag :type="riskLevelTagType(reviewSummary.riskLevel)" effect="plain" size="small">
                  {{ reviewSummary.riskLevel || '-' }}
                </el-tag>
              </div>
              <div class="meta-item">
                <span class="meta-label">信心度</span>
                <b class="meta-value">{{ formatConfidenceScore(reviewSummary.confidenceScore) }}</b>
              </div>
              <div class="meta-item">
                <span class="meta-label">交易次数</span>
                <b class="meta-value">{{ reviewSummary.tradeCount || '-' }} 次</b>
              </div>
            </div>
            <!-- 复盘结论 -->
            <div v-if="reviewSummary.summary" class="review-conclusion">
              <div class="conclusion-title">
                <el-icon><Document /></el-icon>
                <span>复盘结论</span>
              </div>
              <div class="conclusion-text markdown-body" v-html="renderMarkdown(reviewSummary.summary)"></div>
            </div>
            <!-- 建议 -->
            <div v-if="reviewSummary.recommendation" class="review-recommendation">
              <div class="conclusion-title">
                <el-icon><Opportunity /></el-icon>
                <span>操作建议</span>
              </div>
              <div class="conclusion-text markdown-body" v-html="renderMarkdown(reviewSummary.recommendation)"></div>
            </div>
          </div>
        </el-card>

        <!-- 新闻与公告：位于详细分析结果下方 -->
        <el-card shadow="hover" class="news-card">
          <template #header>
            <div class="card-hd">
              <div>{{ newsCardTitle }}</div>
              <el-select v-model="newsFilter" size="small" style="width: 160px">
                <el-option label="全部" value="all" />
                <el-option label="新闻" value="news" />
                <el-option label="公告" value="announcement" />
              </el-select>
            </div>
          </template>
          <div v-if="newsLoading" v-loading="true" style="min-height: 120px" />
          <el-empty v-else-if="newsItems.length === 0" description="暂无新闻" />
          <div v-else class="news-list">
            <div v-for="(n, i) in filteredNews" :key="i" class="news-item">
              <div class="row">
                <div class="left">
                  <el-tag size="small" effect="plain" :type="n.type==='announcement' ? 'warning' : 'info'" class="tag">{{ n.type==='announcement' ? '公告' : '新闻' }}</el-tag>
                  <div class="title">
                    <template v-if="n.url && n.url !== '#'">
                      <a :href="n.url" target="_blank" rel="noopener">{{ n.title || '查看详情' }}</a>
                      <el-icon class="ext"><Link /></el-icon>
                    </template>
                    <template v-else>
                      <span>{{ n.title || '（无标题）' }}</span>
                    </template>
                  </div>
                </div>
                <div class="right">{{ formatNewsTime(n.time) }}</div>
              </div>
              <div class="meta">{{ n.source || '-' }} · {{ newsSource || '-' }}</div>
            </div>
          </div>
        </el-card>




      </el-col>

      <el-col :span="6">
        <!-- 基础快照 -->
        <el-card shadow="hover">
          <template #header><div class="card-hd">{{ isEtf ? 'ETF基础快照' : '基本面快照' }}</div></template>
          <div v-if="isEtf" class="facts">
            <div class="fact"><span>基金类型</span><b>{{ etfBasics.fundType || '-' }}</b></div>
            <div class="fact"><span>跟踪指数</span><b>{{ etfBasics.trackIndex || '-' }}</b></div>
            <div class="fact"><span>基金规模</span><b>{{ fmtText(etfBasics.fundScale) }}</b></div>
            <div class="fact"><span>基金份额</span><b>{{ fmtText(etfBasics.fundShare) }}</b></div>
            <div class="fact"><span>份额日期</span><b>{{ formatDateValue(etfBasics.fundShareDate) }}</b></div>
            <div class="fact"><span>管理人</span><b>{{ etfBasics.management || '-' }}</b></div>
            <div class="fact"><span>托管人</span><b>{{ etfBasics.custodian || '-' }}</b></div>
            <div class="fact"><span>管理费</span><b>{{ fmtLoosePercent(etfBasics.managementFee) }}</b></div>
            <div class="fact"><span>托管费</span><b>{{ fmtLoosePercent(etfBasics.custodianFee) }}</b></div>
            <div class="fact"><span>数据更新时间</span><b>{{ formatDateValue(etfBasics.updatedAt) }}</b></div>
          </div>
          <div v-else class="facts">
            <div class="fact"><span>行业</span><b>{{ basics.industry }}</b></div>
            <div class="fact"><span>板块</span><b>{{ basics.sector }}</b></div>
            <div class="fact"><span>总市值</span><b>{{ fmtAmount(basics.marketCap) }}</b></div>
            <div class="fact">
              <span>PE(TTM)</span>
              <b>
                {{ Number.isFinite(basics.pe) ? basics.pe.toFixed(2) : '-' }}
                <el-tag v-if="basics.peIsRealtime" type="success" size="small" style="margin-left: 4px">实时</el-tag>
              </b>
            </div>
            <div class="fact">
              <span>PB(市净率)</span>
              <b>
                {{ Number.isFinite(basics.pb) ? basics.pb.toFixed(2) : '-' }}
                <el-tag v-if="basics.peIsRealtime" type="success" size="small" style="margin-left: 4px">实时</el-tag>
              </b>
            </div>
            <div class="fact"><span>PS(TTM)</span><b>{{ Number.isFinite(basics.ps) ? basics.ps.toFixed(2) : '-' }}</b></div>
            <div class="fact"><span>ROE</span><b>{{ fmtPercent(basics.roe) }}</b></div>
            <div class="fact"><span>负债率</span><b>{{ fmtPercent(basics.debtRatio) }}</b></div>
            <div class="fact"><span>股息率</span><b>{{ fmtPercent(basics.dividendYield) }}</b></div>
            <div class="fact"><span>流动比率</span><b>{{ fmtRatio(basics.currentRatio) }}</b></div>
            <div class="fact"><span>最新财报期</span><b>{{ basics.reportPeriod || '-' }}</b></div>
          </div>
          <div v-if="!isEtf && (detailFactorWarningEntries.length || detailFactorDiagnosticEntries.length)" class="factor-hints">
            <div class="factor-hints-title">提示信息</div>
            <div class="factor-hints-list">
              <el-popover
                v-for="warning in detailFactorWarningEntries"
                :key="warning.key"
                placement="top-start"
                width="320"
                trigger="hover"
              >
                <template #reference>
                  <el-tag :type="warning.tagType" effect="plain" class="factor-hint-tag">{{ warning.label }}</el-tag>
                </template>
                <div class="factor-hint-popover">
                  <div class="factor-hint-popover-title">{{ warning.label }}</div>
                  <div v-for="condition in warning.conditions" :key="condition" class="factor-hint-line">{{ condition }}</div>
                </div>
              </el-popover>
              <el-popover
                v-for="diagnostic in detailFactorDiagnosticEntries"
                :key="diagnostic.key"
                placement="top-start"
                width="340"
                trigger="hover"
              >
                <template #reference>
                  <el-tag :type="diagnostic.tagType" effect="plain" class="factor-hint-tag">{{ diagnostic.label }}</el-tag>
                </template>
                <div class="factor-hint-popover">
                  <div class="factor-hint-popover-title">{{ diagnostic.label }}</div>
                  <div class="factor-hint-line">状态：{{ diagnostic.state }}</div>
                  <div v-if="diagnostic.reason" class="factor-hint-line">原因：{{ diagnostic.reason }}</div>
                  <div v-if="diagnostic.missingInputs.length" class="factor-hint-line">缺失输入：{{ diagnostic.missingInputs.join('、') }}</div>
                </div>
              </el-popover>
            </div>
          </div>
        </el-card>

        <el-card shadow="hover" class="financial-card">
          <template #header><div class="card-hd">{{ isEtf ? 'ETF估值快照' : '财务明细快照' }}</div></template>
          <div v-if="isEtf" class="facts">
            <div class="fact"><span>场内价格</span><b>{{ fmtPrice(etfBasics.marketPrice ?? quote.price) }}</b></div>
            <div class="fact"><span>单位净值</span><b>{{ fmtPrice(etfBasics.unitNav) }}</b></div>
            <div class="fact"><span>累计净值</span><b>{{ fmtPrice(etfBasics.accumNav) }}</b></div>
            <div class="fact"><span>净值增长率</span><b>{{ fmtLoosePercent(etfBasics.navGrowthRate) }}</b></div>
            <div class="fact"><span>折溢价率</span><b>{{ fmtLoosePercent(etfBasics.premiumDiscountRate) }}</b></div>
            <div class="fact"><span>净值日期</span><b>{{ formatDateValue(etfBasics.latestNavDate) }}</b></div>
            <div class="fact"><span>申购状态</span><b>{{ etfBasics.purchaseStatus || '-' }}</b></div>
            <div class="fact"><span>赎回状态</span><b>{{ etfBasics.redemptionStatus || '-' }}</b></div>
          </div>
          <div v-else class="facts">
            <div class="fact"><span>公告日期</span><b>{{ financialSnapshot.annDate || '-' }}</b></div>
            <div class="fact"><span>数据源</span><b>{{ financialSnapshot.dataSource || '-' }}</b></div>
            <div class="fact"><span>毛利率</span><b>{{ fmtPercent(financialSnapshot.grossMargin) }}</b></div>
            <div class="fact"><span>净利率</span><b>{{ fmtPercent(financialSnapshot.netprofitMargin) }}</b></div>
            <div class="fact"><span>营收</span><b>{{ fmtAmount(financialSnapshot.revenue) }}</b></div>
            <div class="fact"><span>净利润</span><b>{{ fmtAmount(financialSnapshot.netProfit) }}</b></div>
            <div class="fact"><span>经营现金流</span><b>{{ fmtAmount(financialSnapshot.nCashflowAct) }}</b></div>
            <div class="fact"><span>总资产</span><b>{{ fmtAmount(financialSnapshot.totalAssets) }}</b></div>
            <div class="fact"><span>总负债</span><b>{{ fmtAmount(financialSnapshot.totalLiab) }}</b></div>
          </div>
          <div v-if="!isEtf && financialRawSections.length" class="raw-section-summary">
            <div class="raw-title">raw_data 分组</div>
            <div class="raw-tags">
              <el-tag v-for="section in financialRawSections" :key="section.key" size="small" type="info" effect="plain">
                {{ section.label }} {{ section.count }} 条
              </el-tag>
            </div>
            <div class="raw-hint">这些原始分组已经通过主股票接口暴露，后续页面或智能工具可以直接下钻调用。</div>
          </div>
        </el-card>



        <!-- 快捷操作 -->
        <el-card shadow="hover" class="actions-card">
          <template #header><div class="card-hd">{{ quickActionTitle }}</div></template>
          <div class="quick-actions">
            <el-button type="primary" @click="onAnalyze" :icon="TrendCharts" plain>{{ analyzeButtonText }}</el-button>
            <el-button @click="onToggleFavorite" :icon="Star">{{ quickFavoriteButtonText }}</el-button>
            <el-button type="success" :icon="CreditCard" @click="goPaperTrading">模拟交易</el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

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
            <el-radio label="qmt" :disabled="!availableSyncSources.qmt">QMT</el-radio>
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
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { TrendCharts, Star, Refresh, Link, Document, Clock, CreditCard, Delete } from '@element-plus/icons-vue'
import { PieChart, Plus, View, InfoFilled, Opportunity } from '@element-plus/icons-vue'
import { renderMarkdown as safeMarkdown } from '@/utils/markdown'
import { stocksApi } from '@/api/stocks'
import { analysisApi } from '@/api/analysis'
import { fetchTaskResultWithRetry, hasTaskResultContent, mergeTaskResult } from '@/utils/taskResult'
import { ApiClient } from '@/api/request'
import {
  stockSyncApi,
  type SingleStockSyncResponse,
  type StockSyncTaskStatus,
} from '@/api/stockSync'
import { clearAllCache } from '@/api/cache'
import { use as echartsUse } from 'echarts/core'
import { CandlestickChart } from 'echarts/charts'

import { GridComponent, TooltipComponent, DataZoomComponent, LegendComponent, TitleComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import type { EChartsOption } from 'echarts'
import { favoritesApi } from '@/api/favorites'
import { useAuthStore } from '@/stores/auth'
import type { StockInfo } from '@/types/analysis'
import { getFactorDiagnosticEntries, getFactorWarningEntries } from '@/utils/factorPresentation'
import { loadManualSyncSourceState, type ManualSyncDataSource } from '@/utils/dataSource'
import { getReportName } from '@/utils/reportPresentation'
import { getTaskList, getTaskDetail, TaskType, TaskStatus } from '@/api/unifiedTasks'


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
const syncButtonText = computed(() => isEtf.value ? '同步ETF数据' : '同步数据')
const favoriteButtonText = computed(() => {
  if (isEtf.value) return isFav.value ? '已关注ETF' : '关注ETF'
  return isFav.value ? '已自选' : '加自选'
})
const quickFavoriteButtonText = computed(() => {
  if (isEtf.value) return isFav.value ? '取消ETF关注' : '加入ETF关注'
  return isFav.value ? '移出自选' : '股票关注列表'
})
const analyzeButtonText = computed(() => isEtf.value ? '发起ETF分析' : '发起分析')
const quickActionTitle = computed(() => isEtf.value ? 'ETF快捷操作' : '快捷操作')
const newsCardTitle = computed(() => isEtf.value ? 'ETF新闻与公告' : '近期新闻与公告')
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
const changeClass = computed(() => quote.changePercent > 0 ? 'up' : quote.changePercent < 0 ? 'down' : '')

// 🔥 日期判断和格式化函数
function isToday(dateStr: string | null): boolean {
  if (!dateStr) return false
  const today = new Date().toISOString().split('T')[0].replace(/-/g, '')
  const targetDate = dateStr.replace(/-/g, '')
  return today === targetDate
}

function formatDateTag(dateStr: string | null): string {
  if (!dateStr) return ''
  // 将 YYYYMMDD 或 YYYY-MM-DD 格式转换为 MM-DD
  const cleaned = dateStr.replace(/-/g, '')
  if (cleaned.length === 8) {
    return `${cleaned.substring(4, 6)}-${cleaned.substring(6, 8)}`
  }
  return dateStr
}

// 同步状态
const syncStatus = ref<any>(null)

// 数据同步对话框
const syncDialogVisible = ref(false)
const syncLoading = ref(false)
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

async function loadPreferredSyncDataSource() {
  try {
    const sourceState = await loadManualSyncSourceState()
    availableSyncSources.tushare = sourceState.availableSources.tushare
    availableSyncSources.akshare = sourceState.availableSources.akshare
    availableSyncSources.qmt = sourceState.availableSources.qmt

    if (sourceState.preferredSource) {
      syncForm.dataSource = sourceState.preferredSource
      return
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
    // 优先使用 pe_ttm，其次 pe
    basics.pe = Number.isFinite(f.pe_ttm) ? Number(f.pe_ttm) : (Number.isFinite(f.pe) ? Number(f.pe) : basics.pe)
    // 🔥 新增：PB（市净率）
    basics.pb = Number.isFinite(f.pb) ? Number(f.pb) : basics.pb
    // 🔥 新增：PS（市销率）- 优先使用 ps_ttm，其次 ps
    basics.ps = Number.isFinite(f.ps_ttm) ? Number(f.ps_ttm) : (Number.isFinite(f.ps) ? Number(f.ps) : basics.ps)
    // ROE 和负债率
    basics.roe = Number.isFinite(f.roe) ? Number(f.roe) : basics.roe
    const ff: any = f
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
  } catch (e) {
    console.error('获取财务明细失败', e)
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
    console.warn('检查自选失败', e)
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
    fetchSyncStatus(),  // 获取同步状态
    fetchPositionAnalysisSummary(),  // 获取持仓分析摘要
    fetchTradeReviewSummary()  // 获取交易复盘摘要
  ])
  // 每30秒刷新一次报价
  timer = setInterval(fetchQuote, 30000)
})
onUnmounted(() => {
  stockDetailDisposed = true
  if (timer) clearInterval(timer)
})



// K线占位相关
const periodOptions = ['日K','周K','月K']
const period = ref('日K')

const klineSource = ref<string | undefined>(undefined)

function periodLabelToParam(p: string): string {
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
    const param = periodLabelToParam(period.value)
    const res = await stocksApi.getKline(code.value, param as any, 200, 'none')
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

const filteredNews = computed(() => {
  if (newsFilter.value === 'news') return newsItems.value.filter(x => x.type === 'news')
  if (newsFilter.value === 'announcement') return newsItems.value.filter(x => x.type === 'announcement')
  return newsItems.value
})

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
      ElMessage.success('已股票关注列表')
    } else {
      await favoritesApi.remove(code.value)
      isFav.value = false
      ElMessage.success('已移出自选')
    }
  } catch (e: any) {
    console.error('自选操作失败', e)
    ElMessage.error(e?.message || '自选操作失败')
  }
}

function goPaperTrading() {
  router.push({ name: 'PaperTradingHome', query: { code: code.value, market: market.value } })
}

// 获取最新的历史分析报告
async function fetchLatestAnalysis() {
  try {
    console.log('🔍 [fetchLatestAnalysis] 开始获取历史分析报告, symbol:', symbol.value)

    const resp: any = await analysisApi.getHistory({
      symbol: symbol.value,
      stock_code: symbol.value,  // 兼容字段
      page: 1,
      page_size: 1,
      status: 'completed'
    })

    console.log('🔍 [fetchLatestAnalysis] API响应:', resp)
    console.log('🔍 [fetchLatestAnalysis] resp.data:', resp?.data)
    console.log('🔍 [fetchLatestAnalysis] resp.data.data:', resp?.data?.data)

    // 修复：API返回格式是 { success: true, data: { tasks: [...] } }
    // 所以需要先取 resp.data，再取 data.tasks
    const responseData = resp?.data || resp
    console.log('🔍 [fetchLatestAnalysis] responseData:', responseData)

    // 如果responseData有success字段，说明是标准响应格式，需要再取一层data
    const actualData = responseData?.success ? responseData.data : responseData
    console.log('🔍 [fetchLatestAnalysis] actualData:', actualData)

    const tasks = actualData?.tasks || actualData?.analyses || []
    console.log('🔍 [fetchLatestAnalysis] tasks:', tasks)
    console.log('🔍 [fetchLatestAnalysis] tasks.length:', tasks?.length)
    console.log('🔍 [fetchLatestAnalysis] tasks && tasks.length > 0:', tasks && tasks.length > 0)

    if (tasks && tasks.length > 0) {
      const latestTask = tasks[0]
      console.log('✅ [fetchLatestAnalysis] 找到任务:', latestTask)
      console.log('🔍 [fetchLatestAnalysis] latestTask.result_data:', latestTask.result_data)
      console.log('🔍 [fetchLatestAnalysis] latestTask.result:', latestTask.result)
      console.log('🔍 [fetchLatestAnalysis] latestTask.task_id:', latestTask.task_id)
      console.log('🔍 [fetchLatestAnalysis] latestTask.end_time:', latestTask.end_time)

      // 保存任务信息（包含 end_time 等）
      lastTaskInfo.value = latestTask

      const seedResult = mergeTaskResult(latestTask.result_data, latestTask.result)

      if (latestTask.task_id && !hasTaskResultContent(seedResult)) {
        console.log('🔍 [fetchLatestAnalysis] 通过task_id获取结果:', latestTask.task_id)
        try {
          lastAnalysis.value = await fetchTaskResultWithRetry(latestTask.task_id, {
            seedData: seedResult
          })
          analysisStatus.value = 'completed'
          console.log('✅ 通过 task_id 加载分析报告成功:', lastAnalysis.value)
          console.log('🔍 [fetchLatestAnalysis] lastAnalysis.value.reports:', lastAnalysis.value?.reports)
        } catch (e) {
          console.warn('⚠️ 获取任务结果失败:', e)
        }
      } else if (hasTaskResultContent(seedResult)) {
        lastAnalysis.value = seedResult
        analysisStatus.value = 'completed'
        console.log('✅ 加载历史分析报告成功:', seedResult)
        console.log('🔍 [fetchLatestAnalysis] lastAnalysis.value.reports:', lastAnalysis.value?.reports)
      }
    } else {
      console.log('ℹ️ 该股票暂无历史分析报告')
      console.log('🔍 [fetchLatestAnalysis] 判断条件: tasks=', tasks, ', tasks.length=', tasks?.length)
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

// 判断任务是否属于当前股票（task_params 中的 symbol/code/stock_code 任一匹配）
function taskMatchesCurrentStock(task: any): boolean {
  const targetCode = symbol.value  // 6位代码（已去掉后缀）
  const targetCodeUpper = code.value  // 完整代码（可能含后缀如 SH）
  const params = task?.task_params || task?.params || {}
  const candidates = [
    params.symbol,
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
    const resp: any = await getTaskList({
      task_type: TaskType.TRADE_REVIEW,
      status: TaskStatus.COMPLETED,
      limit: 50
    })
    const tasks = resp?.data?.tasks || resp?.tasks || []
    const matched = tasks
      .filter((t: any) => taskMatchesCurrentStock(t))
      .sort((a: any, b: any) => {
        const ta = new Date(a.completed_at || a.created_at).getTime()
        const tb = new Date(b.completed_at || b.created_at).getTime()
        return tb - ta
      })

    if (matched.length === 0) {
      reviewSummary.has = false
      return
    }

    const latest = matched[0]
    reviewSummary.taskId = latest.task_id
    reviewSummary.completedAt = latest.completed_at || latest.created_at

    try {
      const detail: any = await getTaskDetail(latest.task_id)
      const result = detail?.data?.result || detail?.result || {}
      reviewSummary.riskLevel = result?.risk_level || ''
      reviewSummary.confidenceScore = typeof result?.confidence_score === 'number' ? result.confidence_score : null
      reviewSummary.summary = result?.summary || ''
      reviewSummary.recommendation = result?.recommendation || ''
      // 交易次数从 detailed_analysis.trade_info.trades 提取
      const trades = result?.detailed_analysis?.trade_info?.trades
      reviewSummary.tradeCount = Array.isArray(trades) ? trades.length : null
    } catch (e) {
      console.warn('⚠️ 获取交易复盘详情失败:', e)
    }

    reviewSummary.has = true
  } catch (e) {
    console.warn('⚠️ 获取交易复盘摘要失败:', e)
    reviewSummary.has = false
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
  if (reviewSummary.taskId) {
    router.push({ path: '/tasks/unified', query: { task_id: reviewSummary.taskId } })
  }
}

// 持仓分析相关格式化函数
function formatPnl(pnl: any, pct: any): string {
  const n = Number(pnl)
  const p = Number(pct)
  if (!Number.isFinite(n)) return '-'
  const sign = n > 0 ? '+' : ''
  const pnlStr = `${sign}¥${n.toFixed(2)}`
  if (Number.isFinite(p)) {
    return `${pnlStr} (${sign}${p.toFixed(2)}%)`
  }
  return pnlStr
}

function pnlClass(pnl: any): string {
  const n = Number(pnl)
  if (!Number.isFinite(n) || n === 0) return ''
  return n > 0 ? 'pnl-positive' : 'pnl-negative'
}

function actionLabel(action: string): string {
  const map: Record<string, string> = {
    hold: '持有观望',
    buy: '加仓',
    sell: '清仓',
    reduce: '减仓',
    add: '加仓',
    wait: '观望',
    stop_loss: '止损'
  }
  return map[action?.toLowerCase()] || action || '-'
}

function actionTagType(action: string): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  switch (action?.toLowerCase()) {
    case 'buy':
    case 'add':
      return 'success'
    case 'sell':
      return 'danger'
    case 'reduce':
    case 'stop_loss':
      return 'warning'
    case 'hold':
      return 'primary'
    default:
      return 'info'
  }
}

function riskLevelTagType(level: string): 'success' | 'warning' | 'danger' | 'info' {
  const l = (level || '').toLowerCase()
  if (l.includes('低')) return 'success'
  if (l.includes('中')) return 'warning'
  if (l.includes('高')) return 'danger'
  return 'info'
}

function formatConfidenceScore(score: any): string {
  const n = Number(score)
  if (!Number.isFinite(n)) return '-'
  // 兼容 0-1 和 0-100 两种格式
  const pct = n <= 1 ? n * 100 : n
  return `${pct.toFixed(0)}%`
}

function formatPercent(v: any): string {
  const n = Number(v)
  if (!Number.isFinite(n)) return '-'
  return `${n.toFixed(2)}%`
}

// 格式化
function fmtPrice(v: any) { const n = Number(v); return Number.isFinite(n) ? n.toFixed(2) : '-' }
function fmtPercent(v: any) { const n = Number(v); return Number.isFinite(n) ? `${n>0?'+':''}${n.toFixed(2)}%` : '-' }
function fmtRatio(v: any) { const n = Number(v); return Number.isFinite(n) ? n.toFixed(2) : '-' }
function fmtText(v: any) {
  if (v === null || v === undefined || v === '') return '-'
  return String(v)
}
function fmtLoosePercent(v: any) {
  if (v === null || v === undefined || v === '') return '-'
  if (typeof v === 'string' && v.includes('%')) return v
  const n = Number(v)
  return Number.isFinite(n) ? `${n > 0 ? '+' : ''}${n.toFixed(2)}%` : String(v)
}
function formatDateValue(v: any) {
  if (v === null || v === undefined || v === '') return '-'
  return String(v)
}
function fmtVolume(v: any) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '-'

  // 🔥 数据库存储的是"股"，直接显示为"万股"或"亿股"
  if (n >= 1e8) return (n/1e8).toFixed(2) + '亿股'
  if (n >= 1e4) return (n/1e4).toFixed(2) + '万股'
  return n.toFixed(0) + '股'
}
function fmtAmount(v: any) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '-'
  if (n >= 1e12) return (n/1e12).toFixed(2) + '万亿'
  if (n >= 1e8) return (n/1e8).toFixed(2) + '亿'
  if (n >= 1e4) return (n/1e4).toFixed(2) + '万'
  return n.toFixed(0)
}
// 🔥 新增：格式化同步时间（添加时区标识）
function formatSyncTime(timeStr: string | null | undefined): string {
  if (!timeStr) return '未同步'
  // 后端返回的时间已经是 UTC+8 时区，添加时区标识
  return `${timeStr} (UTC+8)`
}

// 🔥 新增：格式化股票更新时间
function formatQuoteUpdateTime(timeStr: string | null | undefined): string {
  if (!timeStr) return '未更新'
  try {
    // 后端返回的时间已经是 UTC+8 时区，但没有时区标识
    // 需要手动添加 +08:00 时区标识，然后转换为本地时间显示
    let isoString = timeStr
    if (!timeStr.includes('+') && !timeStr.includes('Z')) {
      // 如果没有时区标识，添加 +08:00
      isoString = timeStr.replace(/(\.\d+)?$/, '+08:00')
    }
    const date = new Date(isoString)
    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    const hours = String(date.getHours()).padStart(2, '0')
    const minutes = String(date.getMinutes()).padStart(2, '0')
    const seconds = String(date.getSeconds()).padStart(2, '0')
    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
  } catch (e) {
    return timeStr
  }
}

// 🔥 新增：格式化同步间隔
function formatSyncInterval(seconds: number): string {
  if (!seconds || seconds <= 0) return ''

  if (seconds < 60) {
    // 小于60秒，显示秒数
    return `(每${seconds}秒)`
  } else if (seconds < 3600) {
    // 小于1小时，显示分钟数
    const minutes = Math.round(seconds / 60)
    return `(每${minutes}分钟)`
  } else {
    // 大于等于1小时，显示小时数
    const hours = Math.round(seconds / 3600)
    return `(每${hours}小时)`
  }
}
function fmtConf(v: any) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '-'
  const pct = n <= 1 ? n * 100 : n
  return `${Math.round(pct)}%`
}

import { formatDateTimeWithRelative, formatDateTime } from '@/utils/datetime'

// 格式化分析时间（处理UTC时间转换为中国本地时间）
function formatAnalysisTime(dateStr: any): string {
  return formatDateTimeWithRelative(dateStr)
}

// 格式化新闻时间（简洁格式：MM-DD HH:mm）
function formatNewsTime(dateStr: string | null | undefined): string {
  if (!dateStr) return '-'

  try {
    // 使用 formatDateTime 工具函数，自定义格式
    return formatDateTime(dateStr, {
      timeZone: 'Asia/Shanghai',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false
    }).replace(/\//g, '-').replace(/,/g, '')  // 移除逗号和斜杠
  } catch (e) {
    console.error('新闻时间格式化错误:', e, dateStr)
    return String(dateStr)
  }
}

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

// 渲染Markdown
function renderMarkdown(content: string): string {
  if (!content) return '<p>暂无内容</p>'
  try {
    return marked.parse(content, { async: false }) as string
  } catch (e) {
    console.error('Markdown渲染失败:', e)
    return `<pre>${content}</pre>`
  }
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

  // 格式化分析时间用于报告
  const reportTime = lastTaskInfo.value?.end_time
    ? new Date(lastTaskInfo.value.end_time).toLocaleString('zh-CN', {
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
  fullReport += `**投资建议**: ${lastAnalysis.value.recommendation}\n`
  fullReport += `**信心度**: ${fmtConf(lastAnalysis.value.confidence_score)}\n\n`
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

</script>

<style scoped lang="scss">
.stock-detail {
  display: flex; flex-direction: column; gap: 16px;
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

.sentiment { font-size: 12px; }
.sentiment.pos { color: #ef4444; }
.sentiment.neu { color: #64748b; }
.sentiment.neg { color: #10b981; }

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

.analysis-meta .analysis-time,
.analysis-meta .confidence {
  display: flex;
  align-items: center;
  gap: 6px;
}

.analysis-meta .el-icon {
  font-size: 14px;
}

/* 投资建议盒子 - 重点突出 */
.recommendation-box {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 12px;
  padding: 20px 24px;
  box-shadow: 0 4px 16px rgba(102, 126, 234, 0.25);
  transition: all 0.3s ease;
  margin: 16px 0;
}

.recommendation-box:hover {
  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.35);
  transform: translateY(-2px);
}

.recommendation-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  color: rgba(255, 255, 255, 0.95);
  font-size: 15px;
  font-weight: 600;
}

.recommendation-header .icon {
  font-size: 20px;
}

.recommendation-content {
  background: rgba(255, 255, 255, 0.98);
  border-radius: 8px;
  padding: 16px 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.recommendation-text {
  color: #1f2937;
  font-size: 15px;
  line-height: 1.8;
  font-weight: 500;
  word-wrap: break-word;
  word-break: break-word;
  white-space: pre-wrap;
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

  .advice-confidence {
    color: var(--el-text-color-secondary);
    font-size: 13px;
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
</style>

