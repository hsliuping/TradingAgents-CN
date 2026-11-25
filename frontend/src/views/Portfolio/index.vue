<template>
  <div class="portfolio-page">
    <div class="header">
      <div class="title">
        <el-icon style="margin-right:8px"><PieChart /></el-icon>
        <span>持仓分析</span>
        <el-tag type="success" size="small" style="margin-left: 8px;">高级</el-tag>
      </div>
      <div class="actions">
        <el-button :icon="Refresh" text size="small" @click="refreshData">刷新</el-button>
        <el-button v-if="activeTab === 'real' && !isJdyunMode()" type="success" plain :loading="qmtSyncing" @click="syncPositionsFromQmt">QMT同步</el-button>
        <el-button v-if="activeTab === 'real'" type="primary" :icon="Plus" @click="showAddDialog = true">添加持仓</el-button>
        <el-button v-if="activeTab === 'real'" type="info" :icon="List" @click="showChangesDialog = true">变动记录</el-button>
        <el-button v-if="activeTab === 'real'" type="warning" :icon="Clock" @click="showHistoryDialog = true">历史持仓</el-button>
        <el-button v-if="activeTab === 'real'" type="danger" plain size="small" @click="confirmResetAll">清零全部持仓</el-button>
        <!-- 暂时隐藏，功能未完善 -->
        <!-- <el-button type="success" :icon="DataAnalysis" @click="startAnalysis" :loading="analyzing">
          AI分析
        </el-button>
        <el-button type="info" :icon="Document" @click="showAnalysisHistoryDialog = true">分析历史</el-button> -->
      </div>
    </div>

    <!-- 合规免责声明 -->
    <el-alert
      title="本功能仅为个人持仓管理工具"
      type="info"
      description="持仓数据、盈亏统计和操作建议均由您自行录入或同步，系统仅做记录与展示，不构成任何投资建议。实际投资决策请结合多方信息独立判断。"
      show-icon
      :closable="false"
      style="margin-bottom: 16px;"
    />

    <!-- 主 Tab 页：用户持仓 vs 模拟持仓 -->
    <el-tabs v-model="activeTab" type="card" class="main-tabs" @tab-change="handleTabChange">
      <!-- ==================== 用户持仓 Tab ==================== -->
      <el-tab-pane label="💰 用户持仓" name="real">
        <!-- 资金账户卡片 -->
        <AccountCard ref="accountCardRef" @updated="refreshData" />

        <!-- 统计卡片 -->
        <el-row :gutter="16" class="stats-row">
          <el-col :span="6">
            <el-card shadow="hover" class="stat-card">
              <div class="stat-label">持仓总市值</div>
              <div class="stat-value">¥{{ formatNumber(realStats.total_value) }}</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="hover" class="stat-card">
              <div class="stat-label">持仓成本</div>
              <div class="stat-value">¥{{ formatNumber(realStats.total_cost) }}</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="hover" class="stat-card">
              <div class="stat-label">浮动盈亏</div>
              <div class="stat-value" :class="pnlClass(realStats.unrealized_pnl)">
                {{ formatPnl(realStats.unrealized_pnl) }}
                <span class="pnl-pct">({{ formatPct(realStats.unrealized_pnl_pct) }})</span>
              </div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="hover" class="stat-card">
              <div class="stat-label">持仓数量</div>
              <div class="stat-value">{{ realStats.total_positions }} 只</div>
            </el-card>
          </el-col>
        </el-row>

        <!-- 持仓列表 -->
        <el-row :gutter="16" class="main-content">
          <el-col :span="16">
            <el-card shadow="hover">
              <template #header>
                <div class="card-header">
                  <span>用户持仓明细</span>
                  <el-radio-group v-model="selectedMarket" size="small" @change="filterPositions">
                    <el-radio-button value="all">全部</el-radio-button>
                    <el-radio-button value="CN">A股</el-radio-button>
                    <el-radio-button value="ETF">ETF</el-radio-button>
                  </el-radio-group>
                </div>
              </template>

              <!-- 按市场分组展示 -->
              <div v-if="paperSelectedMarket === 'all'" class="market-groups">
                <template v-for="market in ['CN']" :key="market">
                  <div v-if="getPositionsByMarket(realPositions, market).length > 0" class="market-group">
                    <div class="market-group-header">
                      <el-tag :type="getMarketTagType(market)" size="small">{{ getMarketName(market) }}</el-tag>
                      <span class="market-summary">
                        {{ getPositionsByMarket(realPositions, market).length }}只 |
                        <template v-if="getEtfCountByMarket(realPositions, market) > 0">
                          ETF {{ getEtfCountByMarket(realPositions, market) }}只 |
                        </template>
                        市值: {{ getCurrencySymbol(market) }}{{ formatNumber(getMarketValue(realPositions, market)) }}
                      </span>
                    </div>
                    <el-table :data="getPositionsByMarket(realPositions, market)" stripe size="small">
                      <el-table-column label="代码" width="100">
                        <template #default="{ row }">
                          <el-button link type="primary" @click="goToStockDetail(row.code)">{{ row.code }}</el-button>
                        </template>
                      </el-table-column>
                      <el-table-column label="名称" width="170">
                        <template #default="{ row }">
                          <div class="name-cell">
                            <el-button link type="primary" @click="goToStockDetail(row.code)">{{ row.name }}</el-button>
                            <el-tag v-if="isEtfPosition(row)" type="success" size="small" effect="plain">ETF</el-tag>
                          </div>
                        </template>
                      </el-table-column>
                      <el-table-column prop="quantity" label="数量" width="80" align="right" />
                      <el-table-column label="原始成本" width="110" align="right">
                        <template #default="{ row }">
                          <span v-if="(row as any).price_adjust_type === 'none' && (row as any).original_cost_price">
                            {{ (row as any).original_cost_price?.toFixed(2) }}
                            <el-tag size="small" type="warning" effect="plain" style="margin-left:2px;font-size:10px">不复权</el-tag>
                          </span>
                          <span v-else>{{ ((row as any).original_avg_cost ?? row.cost_price)?.toFixed(2) }}</span>
                        </template>
                      </el-table-column>
                      <el-table-column label="摊薄成本" width="100" align="right">
                        <template #default="{ row }">{{ row.cost_price?.toFixed(2) }}</template>
                      </el-table-column>
                      <el-table-column label="现价" width="100" align="right">
                        <template #default="{ row }">{{ row.current_price?.toFixed(2) || '-' }}</template>
                      </el-table-column>
                      <el-table-column label="市值" width="120" align="right">
                        <template #default="{ row }">{{ formatNumber(row.market_value) }}</template>
                      </el-table-column>
                      <el-table-column label="盈亏" width="120" align="right">
                        <template #default="{ row }">
                          <span :class="pnlClass(row.unrealized_pnl)">{{ formatPnl(row.unrealized_pnl) }}</span>
                        </template>
                      </el-table-column>
                      <el-table-column label="盈亏%" width="80" align="right">
                        <template #default="{ row }">
                          <span :class="pnlClass(row.unrealized_pnl_pct)">{{ formatPct(row.unrealized_pnl_pct) }}</span>
                        </template>
                      </el-table-column>
                      <el-table-column label="操作" width="280" fixed="right">
                        <template #default="{ row }">
                          <el-button link type="warning" size="small" @click="quickAddPosition(row)">加仓</el-button>
                          <el-button link type="danger" size="small" @click="quickSellPosition(row)">卖出</el-button>
                          <el-button link type="success" size="small" @click="analyzePosition(row)">分析</el-button>
                          <el-button v-if="row.position_count > 1" link type="info" size="small" @click="showPositionDetails(row)">明细</el-button>
                          <el-dropdown trigger="click" @command="(cmd: string) => handleMoreAction(cmd, row)">
                            <el-button link type="info" size="small">更多<el-icon class="el-icon--right"><ArrowDown /></el-icon></el-button>
                            <template #dropdown>
                              <el-dropdown-menu>
                                <el-dropdown-item command="history">操作历史</el-dropdown-item>
                                <!-- 暂时隐藏，功能未完善 -->
                                <!-- <el-dropdown-item command="analysisHistory">分析历史</el-dropdown-item> -->
                                <el-dropdown-item command="edit" divided>编辑</el-dropdown-item>
                                <el-dropdown-item command="dividend">分红</el-dropdown-item>
                                <el-dropdown-item command="split">拆股</el-dropdown-item>
                                <el-dropdown-item command="merge">合股</el-dropdown-item>
                                <el-dropdown-item command="adjust">调整成本</el-dropdown-item>
                                <el-dropdown-item command="reset" divided>重置持仓</el-dropdown-item>
                                <el-dropdown-item command="delete">删除</el-dropdown-item>
                              </el-dropdown-menu>
                            </template>
                          </el-dropdown>
                        </template>
                      </el-table-column>
                    </el-table>
                  </div>
                </template>
                <el-empty v-if="realPositions.length === 0" description="暂无用户持仓" />
              </div>

              <!-- 单市场展示 -->
              <div v-else>
                <el-table :data="filteredPositions" v-loading="loading" stripe>
                  <el-table-column label="代码" width="100">
                    <template #default="{ row }">
                      <el-button link type="primary" @click="goToStockDetail(row.code)">{{ row.code }}</el-button>
                    </template>
                  </el-table-column>
                  <el-table-column label="名称" width="170">
                    <template #default="{ row }">
                      <div class="name-cell">
                        <el-button link type="primary" @click="goToStockDetail(row.code)">{{ row.name }}</el-button>
                        <el-tag v-if="isEtfPosition(row)" type="success" size="small" effect="plain">ETF</el-tag>
                      </div>
                    </template>
                  </el-table-column>
                  <el-table-column label="市场" width="90">
                    <template #default="{ row }">
                      <el-tag :type="getDisplayMarketTagType(row.market, row.code)" size="small">{{ getDisplayMarketName(row.market, row.code) }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="quantity" label="数量" width="80" align="right" />
                  <el-table-column label="原始成本" width="110" align="right">
                    <template #default="{ row }">
                      <span v-if="(row as any).price_adjust_type === 'none' && (row as any).original_cost_price">
                        {{ (row as any).original_cost_price?.toFixed(2) }}
                        <el-tag size="small" type="warning" effect="plain" style="margin-left:2px;font-size:10px">不复权</el-tag>
                      </span>
                      <span v-else>{{ ((row as any).original_avg_cost ?? row.cost_price)?.toFixed(2) }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="摊薄成本" width="100" align="right">
                    <template #default="{ row }">{{ row.cost_price?.toFixed(2) }}</template>
                  </el-table-column>
                  <el-table-column label="现价" width="100" align="right">
                    <template #default="{ row }">{{ row.current_price?.toFixed(2) || '-' }}</template>
                  </el-table-column>
                  <el-table-column label="市值" width="120" align="right">
                    <template #default="{ row }">{{ formatNumber(row.market_value) }}</template>
                  </el-table-column>
                  <el-table-column label="盈亏" width="120" align="right">
                    <template #default="{ row }">
                      <span :class="pnlClass(row.unrealized_pnl)">{{ formatPnl(row.unrealized_pnl) }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="盈亏%" width="80" align="right">
                    <template #default="{ row }">
                      <span :class="pnlClass(row.unrealized_pnl_pct)">{{ formatPct(row.unrealized_pnl_pct) }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="280" fixed="right">
                    <template #default="{ row }">
                      <el-button link type="warning" size="small" @click="quickAddPosition(row)">加仓</el-button>
                      <el-button link type="danger" size="small" @click="quickSellPosition(row)">卖出</el-button>
                      <el-button link type="success" size="small" @click="analyzePosition(row)">分析</el-button>
                      <el-button v-if="row.position_count > 1" link type="info" size="small" @click="showPositionDetails(row)">明细</el-button>
                      <el-dropdown trigger="click" @command="(cmd: string) => handleMoreAction(cmd, row)">
                        <el-button link type="info" size="small">更多<el-icon class="el-icon--right"><ArrowDown /></el-icon></el-button>
                        <template #dropdown>
                          <el-dropdown-menu>
                            <el-dropdown-item command="history">操作历史</el-dropdown-item>
                            <!-- 暂时隐藏，功能未完善 -->
                            <!-- <el-dropdown-item command="analysisHistory">分析历史</el-dropdown-item> -->
                            <el-dropdown-item command="edit" divided>编辑</el-dropdown-item>
                            <el-dropdown-item command="dividend">分红</el-dropdown-item>
                            <el-dropdown-item command="split">拆股</el-dropdown-item>
                            <el-dropdown-item command="merge">合股</el-dropdown-item>
                            <el-dropdown-item command="adjust">调整成本</el-dropdown-item>
                            <el-dropdown-item command="reset" divided>重置持仓</el-dropdown-item>
                            <el-dropdown-item command="delete">删除</el-dropdown-item>
                          </el-dropdown-menu>
                        </template>
                      </el-dropdown>
                    </template>
                  </el-table-column>
                </el-table>
                <el-empty v-if="filteredPositions.length === 0" description="该市场暂无持仓" />
              </div>
            </el-card>
          </el-col>

          <!-- 行业分布 -->
          <el-col :span="8">
            <el-card shadow="hover" class="industry-card">
              <template #header><span>行业分布</span></template>
              <div v-if="realIndustryDistribution.length" class="industry-list">
                <div v-for="item in realIndustryDistribution" :key="item.industry" class="industry-item">
                  <div class="industry-name">{{ item.industry }}</div>
                  <div class="industry-bar">
                    <el-progress :percentage="item.percentage" :stroke-width="12" :show-text="false" />
                  </div>
                  <div class="industry-pct">{{ item.percentage.toFixed(1) }}%</div>
                </div>
              </div>
              <el-empty v-else description="暂无数据" />
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>

      <!-- ==================== 模拟持仓 Tab ==================== -->
      <el-tab-pane label="📊 模拟持仓" name="paper">
        <!-- 模拟账户资金 -->
        <el-card shadow="hover" class="paper-account-card">
          <template #header>
            <div class="card-header">
              <span>模拟账户资金</span>
              <el-tag type="info" size="small">仅供参考</el-tag>
            </div>
          </template>
          <el-row :gutter="20">
            <el-col :span="6">
              <div class="account-item">
                <div class="account-label">模拟总资产</div>
                <div class="account-value">¥{{ formatNumber(paperStats.total_assets) }}</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="account-item">
                <div class="account-label">持仓市值</div>
                <div class="account-value">¥{{ formatNumber(paperStats.total_value) }}</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="account-item">
                <div class="account-label">浮动盈亏</div>
                <div class="account-value" :class="pnlClass(paperStats.unrealized_pnl)">
                  {{ formatPnl(paperStats.unrealized_pnl) }}
                </div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="account-item">
                <div class="account-label">持仓数量</div>
                <div class="account-value">{{ paperStats.total_positions }} 只</div>
              </div>
            </el-col>
          </el-row>
        </el-card>

        <!-- 模拟持仓列表 -->
        <el-row :gutter="16" class="main-content">
          <el-col :span="16">
            <el-card shadow="hover">
              <template #header>
                <div class="card-header">
                  <span>模拟持仓明细</span>
                  <el-radio-group v-model="paperSelectedMarket" size="small">
                    <el-radio-button value="all">全部</el-radio-button>
                    <el-radio-button value="CN">A股</el-radio-button>
                    <el-radio-button value="ETF">ETF</el-radio-button>
                  </el-radio-group>
                </div>
              </template>

              <!-- 按市场分组展示 -->
              <div v-if="paperSelectedMarket === 'all'" class="market-groups">
                <template v-for="market in ['CN']" :key="market">
                  <div v-if="getPositionsByMarket(paperPositions, market).length > 0" class="market-group">
                    <div class="market-group-header">
                      <el-tag :type="getMarketTagType(market)" size="small">{{ getMarketName(market) }}</el-tag>
                      <span class="market-summary">
                        {{ getPositionsByMarket(paperPositions, market).length }}只 |
                        <template v-if="getEtfCountByMarket(paperPositions, market) > 0">
                          ETF {{ getEtfCountByMarket(paperPositions, market) }}只 |
                        </template>
                        市值: {{ getCurrencySymbol(market) }}{{ formatNumber(getMarketValue(paperPositions, market)) }}
                      </span>
                    </div>
                    <el-table :data="getPositionsByMarket(paperPositions, market)" stripe size="small">
                      <el-table-column label="代码" width="100">
                        <template #default="{ row }">
                          <el-button link type="primary" @click="goToStockDetail(row.code)">{{ row.code }}</el-button>
                        </template>
                      </el-table-column>
                      <el-table-column label="名称" width="170">
                        <template #default="{ row }">
                          <div class="name-cell">
                            <el-button link type="primary" @click="goToStockDetail(row.code)">{{ row.name }}</el-button>
                            <el-tag v-if="isEtfPosition(row)" type="success" size="small" effect="plain">ETF</el-tag>
                          </div>
                        </template>
                      </el-table-column>
                      <el-table-column prop="quantity" label="数量" width="80" align="right" />
                      <el-table-column label="成本价" width="100" align="right">
                        <template #default="{ row }">{{ row.cost_price?.toFixed(2) }}</template>
                      </el-table-column>
                      <el-table-column label="现价" width="100" align="right">
                        <template #default="{ row }">{{ row.current_price?.toFixed(2) || '-' }}</template>
                      </el-table-column>
                      <el-table-column label="市值" width="120" align="right">
                        <template #default="{ row }">{{ formatNumber(row.market_value) }}</template>
                      </el-table-column>
                      <el-table-column label="盈亏" width="120" align="right">
                        <template #default="{ row }">
                          <span :class="pnlClass(row.unrealized_pnl)">{{ formatPnl(row.unrealized_pnl) }}</span>
                        </template>
                      </el-table-column>
                      <el-table-column label="盈亏%" width="80" align="right">
                        <template #default="{ row }">
                          <span :class="pnlClass(row.unrealized_pnl_pct)">{{ formatPct(row.unrealized_pnl_pct) }}</span>
                        </template>
                      </el-table-column>
                      <el-table-column label="操作" width="160" fixed="right">
                        <template #default="{ row }">
                          <el-button link type="success" size="small" @click="analyzePosition(row)">分析</el-button>
                          <el-button v-if="row.position_count > 1" link type="info" size="small" @click="showPositionDetails(row)">明细</el-button>
                        </template>
                      </el-table-column>
                    </el-table>
                  </div>
                </template>
                <el-empty v-if="paperPositions.length === 0" description="暂无模拟持仓" />
              </div>

              <!-- 单市场展示 -->
              <div v-else>
                <el-table :data="filteredPaperPositions" v-loading="loading" stripe>
                  <el-table-column label="代码" width="100">
                    <template #default="{ row }">
                      <el-button link type="primary" @click="goToStockDetail(row.code)">{{ row.code }}</el-button>
                    </template>
                  </el-table-column>
                  <el-table-column label="名称" width="170">
                    <template #default="{ row }">
                      <div class="name-cell">
                        <el-button link type="primary" @click="goToStockDetail(row.code)">{{ row.name }}</el-button>
                        <el-tag v-if="isEtfPosition(row)" type="success" size="small" effect="plain">ETF</el-tag>
                      </div>
                    </template>
                  </el-table-column>
                  <el-table-column label="市场" width="90">
                    <template #default="{ row }">
                      <el-tag :type="getDisplayMarketTagType(row.market, row.code)" size="small">{{ getDisplayMarketName(row.market, row.code) }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="quantity" label="数量" width="80" align="right" />
                  <el-table-column label="成本价" width="100" align="right">
                    <template #default="{ row }">{{ row.cost_price?.toFixed(2) }}</template>
                  </el-table-column>
                  <el-table-column label="现价" width="100" align="right">
                    <template #default="{ row }">{{ row.current_price?.toFixed(2) || '-' }}</template>
                  </el-table-column>
                  <el-table-column label="市值" width="120" align="right">
                    <template #default="{ row }">{{ formatNumber(row.market_value) }}</template>
                  </el-table-column>
                  <el-table-column label="盈亏" width="120" align="right">
                    <template #default="{ row }">
                      <span :class="pnlClass(row.unrealized_pnl)">{{ formatPnl(row.unrealized_pnl) }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="盈亏%" width="80" align="right">
                    <template #default="{ row }">
                      <span :class="pnlClass(row.unrealized_pnl_pct)">{{ formatPct(row.unrealized_pnl_pct) }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="160" fixed="right">
                    <template #default="{ row }">
                      <el-button link type="success" size="small" @click="analyzePosition(row)">分析</el-button>
                      <el-button v-if="row.position_count > 1" link type="info" size="small" @click="showPositionDetails(row)">明细</el-button>
                    </template>
                  </el-table-column>
                </el-table>
                <el-empty v-if="filteredPaperPositions.length === 0" description="该市场暂无模拟持仓" />
              </div>
            </el-card>
          </el-col>

          <!-- 模拟盘行业分布 -->
          <el-col :span="8">
            <el-card shadow="hover" class="industry-card">
              <template #header><span>行业分布</span></template>
              <div v-if="paperIndustryDistribution.length" class="industry-list">
                <div v-for="item in paperIndustryDistribution" :key="item.industry" class="industry-item">
                  <div class="industry-name">{{ item.industry }}</div>
                  <div class="industry-bar">
                    <el-progress :percentage="item.percentage" :stroke-width="12" :show-text="false" />
                  </div>
                  <div class="industry-pct">{{ item.percentage.toFixed(1) }}%</div>
                </div>
              </div>
              <el-empty v-else description="暂无数据" />
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>
    </el-tabs>

    <!-- 添加持仓对话框 -->
    <AddPositionDialog 
      v-model:visible="showAddDialog" 
      :edit-data="editingPosition"
      @success="onPositionSaved" 
    />

    <!-- 分析结果对话框 -->
    <AnalysisResultDialog
      v-model:visible="showAnalysisDialog"
      :report="analysisReport"
    />

    <!-- 单股持仓分析对话框 -->
    <PositionAnalysisDialog
      v-model="showPositionAnalysisDialog"
      :position="selectedPosition"
      :workflow-id="selectedWorkflowId"
    />

    <!-- 持仓变动记录对话框 -->
    <PositionChangesDialog v-model="showChangesDialog" @refresh="refreshData" />

    <!-- 历史持仓对话框 -->
    <HistoryPositionsDialog v-model="showHistoryDialog" />

    <!-- 持仓分析历史对话框 -->
    <AnalysisHistoryDialog v-model="showAnalysisHistoryDialog" />

    <!-- 单股分析历史对话框 -->
    <PositionAnalysisHistoryDialog
      v-model="showPositionAnalysisHistoryDialog"
      :position="selectedPositionForAnalysisHistory"
    />

    <!-- 持仓明细对话框 -->
    <PositionDetailsDialog
      v-model="showPositionDetailsDialog"
      :position="selectedAggregatedPosition"
      @edit="handleEditFromDetails"
      @refresh="refreshData"
      @operation="handlePositionOperation"
    />

    <!-- 持仓操作对话框 -->
    <PositionOperationDialog
      v-model="showPositionOperationDialog"
      :position="selectedAggregatedPosition"
      :operation-type="operationType"
      @refresh="refreshData"
    />

    <!-- 单股操作历史对话框 -->
    <StockOperationHistoryDialog
      v-model="showStockHistoryDialog"
      :stock="selectedStockForHistory"
      source="real"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { isJdyunMode } from '@/utils/config'
import { Refresh, Plus, PieChart, List, Clock, ArrowDown } from '@element-plus/icons-vue'
import type { TabPaneName } from 'element-plus'
import { portfolioApi, type PositionItem, type PortfolioStats, type PortfolioAnalysisReport, type QMTPositionSyncPreview } from '@/api/portfolio'
import AddPositionDialog from './components/AddPositionDialog.vue'
import AnalysisResultDialog from './components/AnalysisResultDialog.vue'
import PositionAnalysisDialog from './components/PositionAnalysisDialog.vue'
import PositionChangesDialog from './components/PositionChangesDialog.vue'
import HistoryPositionsDialog from './components/HistoryPositionsDialog.vue'
import AnalysisHistoryDialog from './components/AnalysisHistoryDialog.vue'
import PositionAnalysisHistoryDialog from './components/PositionAnalysisHistoryDialog.vue'
import PositionDetailsDialog from './components/PositionDetailsDialog.vue'
import PositionOperationDialog from './components/PositionOperationDialog.vue'
import StockOperationHistoryDialog from './components/StockOperationHistoryDialog.vue'
import AccountCard from './components/AccountCard.vue'
import { getMarketByStockCode } from '@/utils/market'

// Router
const router = useRouter()

// 状态
const loading = ref(false)
const positions = ref<PositionItem[]>([])
const stats = ref<PortfolioStats | null>(null)
const accountCardRef = ref<InstanceType<typeof AccountCard> | null>(null)
const activeTab = ref<'real' | 'paper'>('real')
const selectedMarket = ref<'all' | 'CN' | 'ETF'>('all')
const paperSelectedMarket = ref<'all' | 'CN' | 'ETF'>('all')
const showAddDialog = ref(false)
const showAnalysisDialog = ref(false)
const showPositionAnalysisDialog = ref(false)
const showChangesDialog = ref(false)
const showHistoryDialog = ref(false)
const showAnalysisHistoryDialog = ref(false)
const showPositionAnalysisHistoryDialog = ref(false)
const showPositionDetailsDialog = ref(false)
const showPositionOperationDialog = ref(false)
const showStockHistoryDialog = ref(false)
const editingPosition = ref<PositionItem | null>(null)
const selectedPosition = ref<PositionItem | null>(null)
const selectedWorkflowId = ref<string>('')
const selectedAggregatedPosition = ref<AggregatedPosition | null>(null)
const selectedStockForHistory = ref<{ code: string; name?: string; market: string } | null>(null)
const selectedPositionForAnalysisHistory = ref<PositionItem | null>(null)
const operationType = ref<'add' | 'reduce' | 'dividend' | 'split' | 'merge' | 'adjust' | 'other'>('add')
const analysisReport = ref<PortfolioAnalysisReport | null>(null)
const qmtSyncing = ref(false)

const QMT_ACCOUNT_ID_STORAGE_KEY = 'portfolio:qmt-account-id'

// 用户持仓和模拟持仓
const realPositions = ref<PositionItem[]>([])
const paperPositions = ref<PositionItem[]>([])
const filteredPositions = ref<PositionItem[]>([])
const filteredPaperPositions = ref<PositionItem[]>([])

// 统计数据
interface StatsData {
  total_value: number
  total_cost: number
  unrealized_pnl: number
  unrealized_pnl_pct: number
  total_positions: number
  total_assets: number
}
const realStats = ref<StatsData>({
  total_value: 0,
  total_cost: 0,
  unrealized_pnl: 0,
  unrealized_pnl_pct: 0,
  total_positions: 0,
  total_assets: 0
})
const paperStats = ref<StatsData>({
  total_value: 0,
  total_cost: 0,
  unrealized_pnl: 0,
  unrealized_pnl_pct: 0,
  total_positions: 0,
  total_assets: 0
})

// 行业分布
interface IndustryItem {
  industry: string
  percentage: number
}
const realIndustryDistribution = ref<IndustryItem[]>([])
const paperIndustryDistribution = ref<IndustryItem[]>([])

// 格式化方法
const formatNumber = (val?: number) => {
  // 🔥 修复：处理 NaN 和非数字值
  if (val === undefined || val === null || Number.isNaN(val) || typeof val !== 'number') return '-'
  return val.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const formatPnl = (val?: number) => {
  if (val === undefined || val === null || Number.isNaN(val) || typeof val !== 'number') return '-'
  const prefix = val >= 0 ? '+' : ''
  return prefix + formatNumber(val)
}

const formatPct = (val?: number) => {
  if (val === undefined || val === null || Number.isNaN(val) || typeof val !== 'number') return '-'
  const prefix = val >= 0 ? '+' : ''
  return prefix + val.toFixed(2) + '%'
}

const formatSyncMoney = (val?: number | null, symbol = '¥') => {
  if (val === undefined || val === null || Number.isNaN(val) || typeof val !== 'number') return '-'
  return `${symbol}${formatNumber(val)}`
}

const pnlClass = (val?: number) => {
  if (val === undefined || val === null) return ''
  return val >= 0 ? 'profit' : 'loss'
}

const isEtfCode = (code?: string) => getMarketByStockCode(code || '') === 'ETF'

const isEtfPosition = (position: Pick<PositionItem, 'code' | 'market'>) => {
  return position.market === 'CN' && isEtfCode(position.code)
}

const getDisplayMarketName = (market: string, code?: string) => {
  if (market === 'CN' && isEtfCode(code)) return 'ETF'
  return getMarketName(market)
}

const getDisplayMarketTagType = (market: string, code?: string) => {
  if (market === 'CN' && isEtfCode(code)) return 'success'
  return getMarketTagType(market)
}

const getEtfCountByMarket = (positions: PositionItem[], market: string) => {
  return positions.filter(p => p.market === market && isEtfPosition(p)).length
}

const getIndustryCategory = (position: PositionItem) => {
  if (isEtfPosition(position)) return 'ETF/基金'
  return position.industry || '未知'
}

const matchesSelectedMarket = (position: PositionItem, selected: string) => {
  if (selected === 'all') return true
  if (selected === 'ETF') return isEtfPosition(position)
  if (selected === 'CN') return position.market === 'CN' && !isEtfPosition(position)
  return position.market === selected
}

// 市场相关方法
const getMarketName = (market: string) => {
  const map: Record<string, string> = {
    CN: 'A股'
  }
  return map[market] || market
}

const getMarketTagType = (market: string) => {
  const map: Record<string, any> = {
    CN: 'danger'
  }
  return map[market] || 'info'
}

// 币种符号
const getCurrencySymbol = (market: string) => {
  const map: Record<string, string> = {
    CN: '¥'
  }
  return map[market] || '¥'
}

// 获取持仓有效市值：有行情用 market_value，无行情用成本价*数量（避免显示 -100% 浮亏）
const getPositionValue = (p: PositionItem): number => {
  if (p.market_value != null && p.market_value !== undefined) return p.market_value
  return (p.cost_price ?? 0) * (p.quantity ?? 0)
}

// 聚合相同代码的持仓（按股票代码合并）
interface AggregatedPosition extends PositionItem {
  position_count: number  // 该股票的持仓记录数
  positions: PositionItem[]  // 该股票的所有持仓记录
}

const aggregatePositionsByCode = (positions: PositionItem[]): AggregatedPosition[] => {
  const map = new Map<string, PositionItem[]>()

  // 按代码分组
  for (const pos of positions) {
    const key = pos.code
    if (!map.has(key)) {
      map.set(key, [])
    }
    map.get(key)!.push(pos)
  }

  // 合并每组的数据
  const aggregated: AggregatedPosition[] = []
  for (const [, positionList] of map.entries()) {
    const totalQuantity = positionList.reduce((sum, p) => sum + p.quantity, 0)
    const totalCostDiluted = positionList.reduce((sum, p) => sum + (p.cost_price * p.quantity), 0)
    const totalCostOriginal = positionList.reduce((sum, p) => {
      const cost = (p.original_avg_cost ?? p.cost_price) * p.quantity
      return sum + cost
    }, 0)
    const avgCostPrice = totalQuantity > 0 ? totalCostDiluted / totalQuantity : 0
    const avgCostOriginal = totalQuantity > 0 ? totalCostOriginal / totalQuantity : 0
    const totalMarketValue = positionList.reduce((sum, p) => sum + getPositionValue(p), 0)
    const totalUnrealizedPnl = totalMarketValue - totalCostDiluted
    const totalUnrealizedPnlPct = totalCostDiluted > 0 ? (totalUnrealizedPnl / totalCostDiluted) * 100 : 0

    // 使用第一条记录作为基础，更新聚合数据
    const basePos = positionList[0]
    const aggregated_pos: AggregatedPosition = {
      ...basePos,
      quantity: totalQuantity,
      cost_price: avgCostPrice,
      original_avg_cost: avgCostOriginal,
      market_value: totalMarketValue,
      unrealized_pnl: totalUnrealizedPnl,
      unrealized_pnl_pct: totalUnrealizedPnlPct,
      position_count: positionList.length,
      positions: positionList
    }
    aggregated.push(aggregated_pos)
  }

  return aggregated
}

// 按市场获取持仓（聚合版本）
const getPositionsByMarket = (positions: PositionItem[], market: string) => {
  const filtered = positions.filter(p => p.market === market)
  return aggregatePositionsByCode(filtered)
}

// 获取市场总市值
const getMarketValue = (positions: PositionItem[], market: string) => {
  return positions
    .filter(p => p.market === market)
    .reduce((sum, p) => sum + getPositionValue(p), 0)
}

// 计算统计数据
const calculateStats = (positions: PositionItem[]): StatsData => {
  const total_value = positions.reduce((sum, p) => sum + getPositionValue(p), 0)
  const total_cost = positions.reduce((sum, p) => sum + (p.cost_price || 0) * (p.quantity || 0), 0)
  const unrealized_pnl = total_value - total_cost
  const unrealized_pnl_pct = total_cost > 0 ? (unrealized_pnl / total_cost) * 100 : 0
  return {
    total_value,
    total_cost,
    unrealized_pnl,
    unrealized_pnl_pct,
    total_positions: positions.length,
    total_assets: total_value
  }
}

// 计算行业分布
const calculateIndustryDistribution = (positions: PositionItem[]): IndustryItem[] => {
  const total = positions.reduce((sum, p) => sum + getPositionValue(p), 0)
  if (total === 0) return []

  const industryMap: Record<string, number> = {}
  positions.forEach(p => {
    const industry = getIndustryCategory(p)
    industryMap[industry] = (industryMap[industry] || 0) + getPositionValue(p)
  })

  return Object.entries(industryMap)
    .map(([industry, value]) => ({
      industry,
      percentage: (value / total) * 100
    }))
    .sort((a, b) => b.percentage - a.percentage)
}

// 数据加载
const loadPositions = async () => {
  loading.value = true
  try {
    const res = await portfolioApi.getPositions('all')
    positions.value = res.data?.items || []

    // 分离用户持仓和模拟持仓
    realPositions.value = positions.value.filter(p => p.source !== 'paper')
    paperPositions.value = positions.value.filter(p => p.source === 'paper')

    // 计算统计数据
    realStats.value = calculateStats(realPositions.value)
    paperStats.value = calculateStats(paperPositions.value)

    // 计算行业分布
    realIndustryDistribution.value = calculateIndustryDistribution(realPositions.value)
    paperIndustryDistribution.value = calculateIndustryDistribution(paperPositions.value)

    // 应用市场筛选
    filterPositions()
    filterPaperPositions()
  } catch (e: any) {
    ElMessage.error(e.message || '加载持仓失败')
  } finally {
    loading.value = false
  }
}

const loadStats = async () => {
  try {
    const res = await portfolioApi.getStatistics()
    stats.value = res.data || null
  } catch (e: any) {
    console.error('加载统计失败:', e)
  }
}

// Tab 切换
const handleTabChange = (_tabName: TabPaneName) => {
  selectedMarket.value = 'all'
  paperSelectedMarket.value = 'all'
  filterPositions()
  filterPaperPositions()
}

// 市场筛选 - 用户持仓
const filterPositions = () => {
  let filtered: PositionItem[]
  if (selectedMarket.value === 'all') {
    filtered = realPositions.value
  } else {
    filtered = realPositions.value.filter(p => matchesSelectedMarket(p, selectedMarket.value))
  }
  // 单市场显示时也需要聚合
  filteredPositions.value = aggregatePositionsByCode(filtered) as any
}

// 市场筛选 - 模拟持仓
const filterPaperPositions = () => {
  let filtered: PositionItem[]
  if (paperSelectedMarket.value === 'all') {
    filtered = paperPositions.value
  } else {
    filtered = paperPositions.value.filter(p => matchesSelectedMarket(p, paperSelectedMarket.value))
  }
  // 单市场显示时也需要聚合
  filteredPaperPositions.value = aggregatePositionsByCode(filtered) as any
}

// 监听市场筛选变化
watch(paperSelectedMarket, filterPaperPositions)
watch(selectedMarket, filterPositions)

const refreshData = () => {
  loadPositions()
  loadStats()
  accountCardRef.value?.loadData()
}

const getLastQmtAccountId = () => {
  if (typeof window === 'undefined') return ''
  return window.localStorage.getItem(QMT_ACCOUNT_ID_STORAGE_KEY) || ''
}

const setLastQmtAccountId = (accountId: string) => {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(QMT_ACCOUNT_ID_STORAGE_KEY, accountId)
}

const buildQmtPreviewMessage = (preview: QMTPositionSyncPreview) => {
  const lines = [
    `QMT账号：${preview.account_id}`,
    '',
    `本地将覆盖持仓：${preview.will_replace_position_count} 个`,
    `本地将清空变动记录：${preview.will_clear_change_count} 条`,
    `本地当前 CNY 现金：${formatSyncMoney(preview.local_cash)}`,
    `本地当前 CNY 总资产：${formatSyncMoney(preview.local_total_assets)}`,
    '',
    `QMT 返回持仓：${preview.qmt_position_count} 条`,
    `可导入持仓：${preview.qmt_importable_count} 条`,
    `QMT 可用现金：${formatSyncMoney(preview.qmt_cash)}`,
    `QMT 持仓市值：${formatSyncMoney(preview.qmt_market_value)}`,
    `QMT 总资产：${formatSyncMoney(preview.qmt_total_asset)}`,
    '',
    `说明：${preview.sync_note}`
  ]
  return `<div style="white-space: pre-line; line-height: 1.7;">${lines.join('\n')}</div>`
}

const syncPositionsFromQmt = async () => {
  try {
    const { value } = await ElMessageBox.prompt(
      '请输入 QMT 资金账号。系统会先展示覆盖预览，确认后再执行同步。',
      'QMT 持仓同步',
      {
        confirmButtonText: '查看预览',
        cancelButtonText: '取消',
        inputValue: getLastQmtAccountId(),
        inputPattern: /^\d{4,}$/,
        inputErrorMessage: '请输入数字资金账号'
      }
    )

    const accountId = String(value || '').trim()
    if (!accountId) {
      ElMessage.warning('请输入 QMT 资金账号')
      return
    }

    qmtSyncing.value = true

    const previewRes = await portfolioApi.previewQmtPositionImport({
      account_id: accountId,
      account_type: 'STOCK'
    })
    const preview = previewRes.data
    if (!preview) {
      ElMessage.error('未获取到 QMT 同步预览')
      return
    }

    await ElMessageBox.confirm(
      buildQmtPreviewMessage(preview),
      '确认覆盖同步',
      {
        type: 'warning',
        confirmButtonText: '开始同步',
        cancelButtonText: '取消',
        dangerouslyUseHTMLString: true
      }
    )

    const syncRes = await portfolioApi.importPositionsFromQmt({
      account_id: accountId,
      account_type: 'STOCK'
    })
    const syncResult = syncRes.data

    setLastQmtAccountId(accountId)

    const cashHint = syncResult?.cash_synced
      ? `，CNY 现金同步为 ${formatSyncMoney(syncResult.synced_cash)}`
      : ''
    ElMessage.success(
      `QMT 同步完成：覆盖 ${syncResult?.deleted_positions ?? 0} 个旧持仓，导入 ${syncResult?.imported_count ?? 0} 条${cashHint}`
    )
    refreshData()
  } catch (e: any) {
    if (e !== 'cancel' && e !== 'close') {
      ElMessage.error(e?.message || 'QMT 同步失败')
    }
  } finally {
    qmtSyncing.value = false
  }
}

// 持仓操作
const editPosition = (row: AggregatedPosition) => {
  // 如果有多条持仓记录，打开明细对话框让用户选择
  if (row.position_count > 1) {
    selectedAggregatedPosition.value = row
    showPositionDetailsDialog.value = true
    ElMessage.info('请在明细中选择要编辑的持仓记录')
    return
  }
  // 只有一条记录，直接编辑
  editingPosition.value = row.positions ? row.positions[0] : row
  showAddDialog.value = true
}

const deletePosition = async (row: AggregatedPosition) => {
  try {
    // 如果有多条持仓记录，需要确认是否删除全部
    if (row.position_count > 1) {
      await ElMessageBox.confirm(
        `${row.code} ${row.name || ''} 有 ${row.position_count} 条建仓记录，确定全部删除吗？`,
        '确认删除',
        { type: 'warning' }
      )
      // 删除所有持仓记录
      for (const pos of row.positions) {
        await portfolioApi.deletePosition(pos.id)
      }
      ElMessage.success('删除成功')
    } else {
      await ElMessageBox.confirm(`确定删除持仓 ${row.code} ${row.name || ''} ?`, '确认删除', { type: 'warning' })
      const posId = row.positions ? row.positions[0].id : row.id
      await portfolioApi.deletePosition(posId)
      ElMessage.success('删除成功')
    }
    refreshData()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e.message || '删除失败')
    }
  }
}

const resetPosition = async (row: AggregatedPosition) => {
  try {
    await ElMessageBox.confirm(
      `确定重置 ${row.code} ${row.name || ''} 的整个持仓？将删除该股票的所有变动记录和持仓，此操作不可恢复。`,
      '确认重置',
      { type: 'warning' }
    )
    const res = await portfolioApi.resetPosition(row.code, row.market)
    ElMessage.success(`重置成功，已删除 ${res.data?.deleted_changes ?? 0} 条记录`)
    refreshData()
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error(e.message || '重置失败')
  }
}

const confirmResetAll = async () => {
  try {
    await ElMessageBox.confirm(
      '确定清零全部持仓？将删除所有持仓和变动记录，并完全清零资金账户（总资产、可用资金、初始资金等全部归零），此操作不可恢复。清零后需重新设置初始资金才能继续使用。',
      '确认清零',
      { type: 'warning' }
    )
    const res = await portfolioApi.resetAllPositions()
    ElMessage.success(`清零成功，已删除 ${res.data?.deleted_positions ?? 0} 个持仓、${res.data?.deleted_changes ?? 0} 条记录`)
    refreshData()
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error(e.message || '清零失败')
  }
}

const onPositionSaved = () => {
  showAddDialog.value = false
  editingPosition.value = null
  refreshData()
}

// 跳转到股票详情页面
const goToStockDetail = (code: string) => {
  const market = getMarketByStockCode(code)
  router.push({
    name: 'StockDetail',
    params: { code },
    query: market === 'ETF' ? { market: 'ETF' } : undefined
  })
}

// 单股持仓分析
const analyzePosition = (row: PositionItem) => {
  selectedPosition.value = row
  showPositionAnalysisDialog.value = true
}

// 查看持仓明细
const showPositionDetails = (row: AggregatedPosition) => {
  selectedAggregatedPosition.value = row
  showPositionDetailsDialog.value = true
}

// 从明细对话框编辑持仓
const handleEditFromDetails = (position: PositionItem) => {
  editingPosition.value = position
  showAddDialog.value = true
}

// 处理持仓操作（增仓、减仓、分红等）
const handlePositionOperation = (data: { type: string; position: AggregatedPosition }) => {
  operationType.value = data.type as 'add' | 'reduce' | 'other'
  selectedAggregatedPosition.value = data.position
  showPositionDetailsDialog.value = false
  showPositionOperationDialog.value = true
}

// 快捷加仓
const quickAddPosition = (row: AggregatedPosition) => {
  operationType.value = 'add'
  selectedAggregatedPosition.value = row
  showPositionOperationDialog.value = true
}

// 快捷卖出
const quickSellPosition = (row: AggregatedPosition) => {
  operationType.value = 'reduce'
  selectedAggregatedPosition.value = row
  showPositionOperationDialog.value = true
}

// 更多操作菜单
const handleMoreAction = (command: string, row: AggregatedPosition) => {
  selectedAggregatedPosition.value = row
  switch (command) {
    case 'history':
      // 显示该股票的操作历史
      selectedStockForHistory.value = {
        code: row.code,
        name: row.name,
        market: row.market
      }
      showStockHistoryDialog.value = true
      break
    case 'analysisHistory':
      // 显示该股票的分析历史
      selectedPositionForAnalysisHistory.value = {
        code: row.code,
        name: row.name,
        market: row.market,
        quantity: row.quantity,
        cost_price: row.cost_price,
        current_price: row.current_price,
        market_value: row.market_value,
        unrealized_pnl: row.unrealized_pnl,
        unrealized_pnl_pct: row.unrealized_pnl_pct,
        industry: row.industry
      } as PositionItem
      showPositionAnalysisHistoryDialog.value = true
      break
    case 'edit':
      editPosition(row)
      break
    case 'delete':
      deletePosition(row)
      break
    case 'dividend':
      operationType.value = 'dividend'
      showPositionOperationDialog.value = true
      break
    case 'split':
      operationType.value = 'split'
      showPositionOperationDialog.value = true
      break
    case 'merge':
      operationType.value = 'merge'
      showPositionOperationDialog.value = true
      break
    case 'adjust':
      operationType.value = 'adjust'
      showPositionOperationDialog.value = true
      break
    case 'reset':
      resetPosition(row)
      break
  }
}

onMounted(() => {
  refreshData()
})
</script>

<style scoped>
.portfolio-page {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.title {
  display: flex;
  align-items: center;
  font-size: 20px;
  font-weight: 600;
}

.stats-row {
  margin-bottom: 20px;
}

.stat-card {
  text-align: center;
  padding: 10px 0;
}

.stat-label {
  color: #909399;
  font-size: 14px;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}

.stat-value .pnl-pct {
  font-size: 14px;
  margin-left: 4px;
}

.profit {
  color: #F56C6C; /* 红色表示盈利（中国股市规范） */
}

.loss {
  color: #67C23A; /* 绿色表示亏损（中国股市规范） */
}

.main-content {
  margin-top: 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.industry-card {
  height: 100%;
}

.industry-list {
  max-height: 400px;
  overflow-y: auto;
}

.industry-item {

.name-cell {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
  display: flex;
  align-items: center;
  margin-bottom: 12px;
}

.industry-name {
  width: 80px;
  font-size: 13px;
  color: #606266;
}

.industry-bar {
  flex: 1;
  margin: 0 12px;
}

.industry-pct {
  width: 50px;
  text-align: right;
  font-size: 13px;
  color: #909399;
}

/* 主 Tab 页样式 */
.main-tabs {
  margin-top: 16px;
}

.main-tabs :deep(.el-tabs__header) {
  margin-bottom: 16px;
}

.main-tabs :deep(.el-tabs__item) {
  font-size: 15px;
  font-weight: 500;
}

/* 模拟账户卡片 */
.paper-account-card {
  margin-bottom: 16px;
}

.account-item {
  text-align: center;
  padding: 12px 0;
}

.account-label {
  font-size: 13px;
  color: #909399;
  margin-bottom: 8px;
}

.account-value {
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}

/* 市场分组 */
.market-groups {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.market-group {
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 12px;
}

.market-group-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #ebeef5;
}

.market-summary {
  font-size: 13px;
  color: #909399;
}
</style>

