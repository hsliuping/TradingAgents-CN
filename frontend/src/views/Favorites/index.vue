<template>
  <div class="favorites">
    <div class="page-header">
      <h1 class="page-title">
        <el-icon><Star /></el-icon>
        我的自选股
      </h1>
      <p class="page-description">
        管理您关注的股票
      </p>
    </div>

    <!-- 操作栏 -->
    <el-card class="action-card" shadow="never">
      <el-row :gutter="16" align="middle" style="margin-bottom: 16px;">
        <el-col :span="8">
          <el-input
            v-model="searchKeyword"
            placeholder="搜索股票代码或名称"
            clearable
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </el-col>

        <el-col :span="4">
          <el-select v-model="selectedMarket" placeholder="市场" clearable>
            <el-option label="A股" value="A股" />
            <el-option label="港股" value="港股" />
            <el-option label="美股" value="美股" />
          </el-select>
        </el-col>

        <el-col :span="4">
          <el-select v-model="selectedBoard" placeholder="板块" clearable>
            <el-option
              v-for="board in availableBoards"
              :key="board"
              :label="board"
              :value="board"
            />
          </el-select>
        </el-col>

        <el-col :span="4">
          <el-select v-model="selectedExchange" placeholder="交易所" clearable>
            <el-option
              v-for="exchange in availableExchanges"
              :key="exchange"
              :label="exchange"
              :value="exchange"
            />
          </el-select>
        </el-col>

        <el-col :span="4">
          <el-select v-model="selectedTag" placeholder="标签" clearable>
            <el-option
              v-for="tag in userTags"
              :key="tag"
              :label="tag"
              :value="tag"
            >
              <span :style="{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }">
                <span>{{ tag }}</span>
                <span :style="{ display: 'flex', alignItems: 'center', gap: '8px', marginLeft: '8px' }">
                  <span style="font-size: 12px; color: #909399;">{{ getTagUsageCount(tag) }} 只</span>
                  <span :style="{ display:'inline-block', width:'12px', height:'12px', border:'1px solid #ddd', borderRadius:'2px', background: getTagColor(tag) }"></span>
                </span>
              </span>
            </el-option>
          </el-select>
        </el-col>
      </el-row>

      <el-row :gutter="16" align="middle">
        <el-col :span="24">
          <div class="action-buttons">
            <el-button @click="refreshData">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
            <!-- 只要有自选股就显示同步实时行情按钮 -->
            <el-button
              v-if="hasFavorites"
              type="success"
              @click="syncAllRealtime"
              :loading="syncRealtimeLoading"
            >
              <el-icon><Refresh /></el-icon>
              同步实时行情
            </el-button>
            <!-- 只有选中的股票都是A股时才显示批量同步按钮 -->
            <el-button
              v-if="selectedStocksAreAllAShares"
              type="primary"
              @click="showBatchSyncDialog"
            >
              <el-icon><Download /></el-icon>
              批量同步数据
            </el-button>
            <el-button @click="() => openSyncHistoryDialog()">
              同步历史
            </el-button>
            <el-button @click="openTagManager">
              标签管理
            </el-button>
            <el-button type="primary" @click="showAddDialog">
              <el-icon><Plus /></el-icon>
              添加自选股
            </el-button>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 自选股列表 -->
    <el-card class="favorites-list-card" shadow="never">
      <el-table
        :data="filteredFavorites"
        v-loading="loading"
        style="width: 100%"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="55" />
        <el-table-column prop="stock_code" label="股票代码" width="120">
          <template #default="{ row }">
            <el-link type="primary" @click="viewStockDetail(row)">
              {{ row.stock_code }}
            </el-link>
          </template>
        </el-table-column>

        <el-table-column prop="stock_name" label="股票名称" width="150" />
        <el-table-column prop="market" label="市场" width="80">
          <template #default="{ row }">
            {{ row.market || 'A股' }}
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

        <el-table-column prop="current_price" label="当前价格" width="150">
          <template #default="{ row }">
            <el-tooltip
              v-if="row.current_price !== null && row.current_price !== undefined"
              :disabled="!getPriceTooltip(row)"
              :content="getPriceTooltip(row) || ''"
              placement="top"
            >
              <div class="quote-cell">
                <span :class="getPriceClass(row)">
                  {{ getCurrencySymbol(row) }}{{ formatPrice(row.current_price) }}
                </span>
                <div v-if="getQuoteTimestampLabel(row)" class="quote-timestamp">
                  {{ getQuoteTimestampLabel(row) }}
                </div>
              </div>
            </el-tooltip>
            <span v-else>-</span>
          </template>
        </el-table-column>

        <el-table-column prop="change_percent" label="涨跌幅" width="150">
          <template #default="{ row }">
            <el-tooltip
              v-if="row.change_percent !== null && row.change_percent !== undefined"
              :disabled="!getChangeTooltip(row)"
              :content="getChangeTooltip(row) || ''"
              placement="top"
            >
              <div class="quote-cell">
                <span :class="getChangeClass(row.change_percent, row.change_display_mode)">
                  {{ formatPercent(row.change_percent) }}
                </span>
                <div v-if="getQuoteTimestampLabel(row)" class="quote-timestamp">
                  {{ getQuoteTimestampLabel(row) }}
                </div>
              </div>
            </el-tooltip>
            <span v-else>-</span>
          </template>
        </el-table-column>

        <el-table-column prop="tags" label="标签" width="150">
          <template #default="{ row }">
            <el-tag
              v-for="tag in row.tags"
              :key="tag"
              size="small"
              :color="getTagColor(tag)"
              effect="dark"
              :style="{ marginRight: '4px' }"
            >
              {{ tag }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="360" fixed="right">
          <template #default="{ row }">
            <div class="favorite-row-actions">
              <el-button
                type="text"
                size="small"
                @click="editFavorite(row)"
              >
                编辑
              </el-button>
              <el-button
                type="text"
                size="small"
                @click="openQuickTagEditor(row)"
              >
                快速标签
              </el-button>
              <el-button
                type="text"
                size="small"
                @click="showSingleSyncDialog(row)"
                style="color: #409EFF;"
              >
                同步
              </el-button>
              <el-button
                type="text"
                size="small"
                @click="analyzeFavorite(row)"
              >
                分析
              </el-button>
              <el-button
                type="text"
                size="small"
                @click="removeFavorite(row)"
                style="color: #f56c6c;"
              >
                移除
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <!-- 空状态 -->
      <div v-if="!loading && favorites.length === 0" class="empty-state">
        <el-empty description="暂无自选股">
          <el-button type="primary" @click="showAddDialog">
            添加第一只自选股
          </el-button>
        </el-empty>
      </div>
    </el-card>

    <!-- 添加自选股对话框 -->
    <el-dialog
      v-model="addDialogVisible"
      title="添加自选股"
      width="500px"
    >
      <el-form :model="addForm" :rules="addRules" ref="addFormRef" label-width="100px">
        <el-form-item label="市场类型" prop="market">
          <el-select v-model="addForm.market" @change="handleMarketChange">
            <el-option label="A股" value="A股" />
            <el-option label="港股" value="港股" />
            <el-option label="美股" value="美股" />
          </el-select>
        </el-form-item>

        <el-form-item label="股票代码" prop="stock_code">
          <el-input
            v-model="addForm.stock_code"
            :placeholder="getStockCodePlaceholder()"
            @blur="fetchStockInfo"
          />
          <div style="font-size: 12px; color: #909399; margin-top: 4px;">
            {{ getStockCodeHint() }}
          </div>
          <div v-if="detectedMarketMetaText" class="detected-market-meta">
            已识别：{{ detectedMarketMetaText }}
          </div>
        </el-form-item>

        <el-form-item label="股票名称" prop="stock_name">
          <el-input v-model="addForm.stock_name" placeholder="股票名称" />
          <div v-if="addForm.market !== 'A股'" style="font-size: 12px; color: #E6A23C; margin-top: 4px;">
            {{ addForm.market }}不支持自动获取，请手动输入股票名称
          </div>
        </el-form-item>

        <el-form-item label="标签">
          <el-select
            v-model="addForm.tags"
            multiple
            filterable
            allow-create
            placeholder="选择或创建标签"
          >
            <el-option v-for="tag in userTags" :key="tag" :label="tag" :value="tag">
              <span :style="{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }">
                <span>{{ tag }}</span>
                <span :style="{ display:'inline-block', width:'12px', height:'12px', border:'1px solid #ddd', borderRadius:'2px', marginLeft:'8px', background: getTagColor(tag) }"></span>
              </span>
            </el-option>
          </el-select>
        </el-form-item>

        <el-form-item label="备注">
          <el-input
            v-model="addForm.notes"
            type="textarea"
            :rows="2"
            placeholder="可选：添加备注信息"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="addDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleAddFavorite" :loading="addLoading">
          添加
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="quickTagDialogVisible"
      title="快速编辑标签"
      width="460px"
    >
      <el-form :model="quickTagForm" label-width="90px">
        <el-form-item label="股票">
          <div>{{ quickTagForm.stock_code }}｜{{ quickTagForm.stock_name }}</div>
        </el-form-item>
        <el-form-item label="标签">
          <el-select
            v-model="quickTagForm.tags"
            multiple
            filterable
            placeholder="选择或创建标签"
            style="width: 100%;"
          >
            <el-option v-for="tag in userTags" :key="tag" :label="tag" :value="tag">
              <span :style="{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }">
                <span>{{ tag }}</span>
                <span :style="{ display:'inline-block', width:'12px', height:'12px', border:'1px solid #ddd', borderRadius:'2px', marginLeft:'8px', background: getTagColor(tag) }"></span>
              </span>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="新标签">
          <div style="display:flex; gap:8px; align-items:center; width:100%;">
            <el-input v-model="quickNewTag.name" placeholder="输入新标签名" style="flex:1;" />
            <el-select v-model="quickNewTag.color" placeholder="颜色" style="width:160px;">
              <el-option v-for="c in COLOR_PALETTE" :key="c" :label="c" :value="c">
                <span :style="{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }">
                  <span>{{ c }}</span>
                  <span :style="{ display:'inline-block', width:'12px', height:'12px', border:'1px solid #ddd', borderRadius:'2px', marginLeft:'8px', background: c }"></span>
                </span>
              </el-option>
            </el-select>
            <span class="color-dot-preview" :style="{ background: quickNewTag.color }"></span>
            <el-button type="primary" plain :loading="quickTagCreating" @click="createQuickTag">
              新增
            </el-button>
          </div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="quickTagDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="quickTagLoading" @click="handleQuickTagUpdate">
          保存标签
        </el-button>
      </template>
    </el-dialog>
    <!-- 编辑自选股对话框 -->
    <el-dialog
      v-model="editDialogVisible"
      title="编辑自选股"
      width="520px"
    >
      <el-form :model="editForm" ref="editFormRef" label-width="100px">
        <el-form-item label="股票">
          <div>{{ editForm.stock_code }}｜{{ editForm.stock_name }}（{{ editForm.market }}）</div>
        </el-form-item>

        <el-form-item label="标签">
          <el-select v-model="editForm.tags" multiple filterable allow-create placeholder="选择或创建标签">
            <el-option v-for="tag in userTags" :key="tag" :label="tag" :value="tag">
              <span :style="{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }">
                <span>{{ tag }}</span>
                <span :style="{ display:'inline-block', width:'12px', height:'12px', border:'1px solid #ddd', borderRadius:'2px', marginLeft:'8px', background: getTagColor(tag) }"></span>
              </span>
            </el-option>
          </el-select>
        </el-form-item>

        <el-form-item label="备注">
          <el-input v-model="editForm.notes" type="textarea" :rows="2" placeholder="可选：添加备注信息" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="editLoading" @click="handleUpdateFavorite">保存</el-button>
      </template>
    </el-dialog>

    <!-- 标签管理对话框 -->
    <el-dialog v-model="tagDialogVisible" title="标签管理" width="560px">
      <el-table :data="tagList" v-loading="tagLoading" size="small" style="width: 100%; margin-bottom: 12px;">
        <el-table-column label="名称" min-width="220">
          <template #default="{ row }">
            <template v-if="row._editing">
              <el-input v-model="row._name" placeholder="标签名称" size="small" />
            </template>
            <template v-else>
              <el-tag :color="row.color" effect="dark" style="margin-right:6px"></el-tag>
              {{ row.name }}
            </template>
          </template>
        </el-table-column>
        <el-table-column label="颜色" width="140">
          <template #default="{ row }">
            <template v-if="row._editing">
              <el-select v-model="row._color" placeholder="选择颜色" size="small" style="width: 200px">
                <el-option v-for="c in COLOR_PALETTE" :key="c" :label="c" :value="c">
                  <span :style="{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }">
                    <span>{{ c }}</span>
                    <span :style="{ display: 'inline-block', width: '12px', height: '12px', border: '1px solid #ddd', borderRadius: '2px', marginLeft: '8px', background: c }"></span>
                  </span>
                </el-option>
              </el-select>
              <span class="color-dot-preview" :style="{ background: row._color }"></span>
            </template>
            <template v-else>
              <span :style="{display:'inline-block',width:'14px',height:'14px',background: row.color,border:'1px solid #ddd',marginRight:'6px'}"></span>
              {{ row.color }}

            </template>
          </template>
        </el-table-column>
        <el-table-column label="排序" width="100" align="center">
          <template #default="{ row }">
            <template v-if="row._editing">
              <el-input v-model.number="row._sort" type="number" size="small" />
            </template>
            <template v-else>
              {{ row.sort_order }}
            </template>
          </template>
        </el-table-column>
        <el-table-column label="使用中" width="90" align="center">
          <template #default="{ row }">
            {{ getTagUsageCount(row.name) }} 只
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <template v-if="row._editing">
              <el-button type="text" size="small" @click="saveTag(row)">保存</el-button>
              <el-button type="text" size="small" @click="cancelEditTag(row)">取消</el-button>
            </template>
            <template v-else>
              <el-button type="text" size="small" @click="editTag(row)">编辑</el-button>
              <el-button type="text" size="small" style="color:#f56c6c" @click="deleteTag(row)">删除</el-button>
            </template>
          </template>
        </el-table-column>
      </el-table>

      <div style="display:flex; gap:8px; align-items:center;">
        <el-input v-model="newTag.name" placeholder="新标签名" style="flex:1" />
        <el-select v-model="newTag.color" placeholder="选择颜色" style="width:200px">
          <el-option v-for="c in COLOR_PALETTE" :key="c" :label="c" :value="c">
            <span :style="{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }">
              <span>{{ c }}</span>
              <span :style="{ display: 'inline-block', width: '12px', height: '12px', border: '1px solid #ddd', borderRadius: '2px', marginLeft: '8px', background: c }"></span>
            </span>
          </el-option>
        </el-select>
        <span class="color-dot-preview" :style="{ background: newTag.color }"></span>
        <el-input v-model.number="newTag.sort_order" type="number" placeholder="排序" style="width:120px" />
        <el-button type="primary" @click="createTag" :loading="tagLoading">新增</el-button>
      </div>

      <template #footer>
        <el-button @click="tagDialogVisible=false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 批量同步对话框 -->
    <el-dialog
      v-model="batchSyncDialogVisible"
      title="批量同步股票数据"
      width="500px"
    >
      <el-alert
        type="info"
        :closable="false"
        style="margin-bottom: 16px;"
      >
        已选择 <strong>{{ selectedStocks.length }}</strong> 只股票
      </el-alert>

      <el-form :model="batchSyncForm" label-width="120px">
        <el-form-item label="同步内容">
          <el-checkbox-group v-model="batchSyncForm.syncTypes">
            <el-checkbox label="historical">历史行情数据</el-checkbox>
            <el-checkbox label="financial">财务数据</el-checkbox>
            <el-checkbox label="basic">基础数据</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="数据源">
          <el-radio-group v-model="batchSyncForm.dataSource">
            <el-radio label="tushare">Tushare</el-radio>
            <el-radio label="akshare">AKShare</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="历史数据天数" v-if="batchSyncForm.syncTypes.includes('historical')">
          <el-input-number v-model="batchSyncForm.days" :min="1" :max="3650" />
          <span style="margin-left: 10px; color: #909399; font-size: 12px;">
            (最多3650天，约10年)
          </span>
        </el-form-item>
      </el-form>

      <el-alert
        type="warning"
        :closable="false"
        style="margin-top: 16px;"
      >
        批量同步可能需要较长时间，请耐心等待
      </el-alert>

      <template #footer>
        <el-button @click="batchSyncDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleBatchSync" :loading="batchSyncLoading">
          开始同步
        </el-button>
      </template>
    </el-dialog>

    <!-- 单个股票同步对话框 -->
    <el-dialog
      v-model="singleSyncDialogVisible"
      title="同步股票数据"
      width="500px"
    >
      <el-form :model="singleSyncForm" label-width="120px">
        <el-form-item label="股票代码">
          <el-input v-model="currentSyncStock.stock_code" disabled />
        </el-form-item>
        <el-form-item label="股票名称">
          <el-input v-model="currentSyncStock.stock_name" disabled />
        </el-form-item>
        <el-form-item label="同步内容">
          <el-checkbox-group v-model="singleSyncForm.syncTypes">
            <el-checkbox label="realtime">实时行情</el-checkbox>
            <el-checkbox label="historical">历史行情数据</el-checkbox>
            <el-checkbox label="financial">财务数据</el-checkbox>
            <el-checkbox label="basic">基础数据</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="数据源">
          <el-radio-group v-model="singleSyncForm.dataSource">
            <el-radio v-if="singleSyncSourceMode === 'normal'" label="tushare">Tushare</el-radio>
            <el-radio label="akshare">AKShare</el-radio>
            <el-radio v-if="singleSyncSourceMode === 'mixed'" label="mixed">实时AKShare+其他Tushare</el-radio>
          </el-radio-group>
          <div
            v-if="singleSyncRealtimeRequiresAkshare"
            style="margin-top: 6px; color: #e6a23c; font-size: 12px; line-height: 1.5;"
          >
            {{ singleSyncSourceHint }}
          </div>
        </el-form-item>
        <el-form-item label="历史数据天数" v-if="singleSyncForm.syncTypes.includes('historical')">
          <el-input-number v-model="singleSyncForm.days" :min="1" :max="3650" />
          <span style="margin-left: 10px; color: #909399; font-size: 12px;">
            (最多3650天，约10年)
          </span>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="singleSyncDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSingleSync" :loading="singleSyncLoading">
          开始同步
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="syncHistoryDialogVisible"
      title="同步记录"
      width="1100px"
    >
      <div class="sync-history-toolbar">
        <el-input
          v-model="historyFilterSymbol"
          placeholder="按股票代码筛选，如 600519 或 09992"
          clearable
          style="width: 240px;"
          @keyup.enter="loadSyncHistory(1)"
        />
        <el-button @click="loadSyncHistory(1)">
          查询
        </el-button>
        <el-button @click="resetSyncHistoryFilter">
          重置
        </el-button>
        <el-button
          type="danger"
          plain
          :loading="clearSyncHistoryLoading"
          @click="handleClearSyncHistory"
        >
          删除当前列表记录
        </el-button>
        <el-button
          type="danger"
          @click="openDeleteSyncedDataDialog()"
        >
          打开数据清理
        </el-button>
      </div>

      <el-alert
        class="sync-section-alert"
        type="info"
        :closable="false"
        show-icon
        title="这里展示的是同步操作记录。删除记录不会删除真实行情/财务/基础数据；如果要清理真实数据，请使用右侧“打开数据清理”。"
      />

      <div v-if="hasHistoryLinkedContext" class="sync-linked-context">
        <div class="sync-linked-context__text">
          当前关联筛选：{{ historyLinkedContextText || '已带入关联条件' }}
        </div>
        <el-button size="small" @click="clearHistoryLinkedFilter">
          清除关联筛选
        </el-button>
      </div>

      <el-table
        :data="syncHistoryRecords"
        v-loading="syncHistoryLoading"
        style="width: 100%;"
      >
        <el-table-column label="开始时间" width="170">
          <template #default="{ row }">
            {{ formatDateTime(row.started_at) }}
          </template>
        </el-table-column>

        <el-table-column label="股票 / 范围" min-width="170">
          <template #default="{ row }">
            <div>{{ row.scope === 'single' ? (row.symbol || '-') : `${row.symbol_count} 只股票` }}</div>
            <div class="history-meta">{{ row.symbols.join(', ') }}</div>
          </template>
        </el-table-column>

        <el-table-column label="类型" width="180">
          <template #default="{ row }">
            <el-tag
              v-for="type in row.sync_types"
              :key="type"
              size="small"
              style="margin-right: 6px; margin-bottom: 4px;"
            >
              {{ formatSyncTypeLabel(type) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="时间段" width="180">
          <template #default="{ row }">
            {{ formatHistoryRange(row) }}
          </template>
        </el-table-column>

        <el-table-column label="来源" width="150">
          <template #default="{ row }">
            {{ formatDataSources(row.data_sources_used) }}
          </template>
        </el-table-column>

        <el-table-column label="结果摘要" min-width="240">
          <template #default="{ row }">
            <div class="history-summary">{{ row.summary || '-' }}</div>
            <div v-if="row.errors?.length" class="history-error">
              {{ row.errors[0] }}
            </div>
          </template>
        </el-table-column>

        <el-table-column label="耗时" width="90">
          <template #default="{ row }">
            {{ formatDuration(row.duration_seconds) }}
          </template>
        </el-table-column>

        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getHistoryStatusTagType(row.status)">
              {{ formatHistoryStatus(row.status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="170" fixed="right">
          <template #default="{ row }">
            <div class="table-action-group">
              <el-button
                type="text"
                size="small"
                @click="openDeleteDialogFromHistoryRow(row)"
              >
                查看对应数据
              </el-button>
              <el-button
                type="text"
                size="small"
                style="color: #f56c6c;"
                :loading="deletingHistoryId === row.id"
                @click="handleDeleteSyncHistory(row)"
              >
                删记录
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div class="sync-history-footer">
        <div class="history-meta">
          共 {{ historyTotal }} 条记录
        </div>
        <el-pagination
          background
          layout="total, sizes, prev, pager, next"
          :current-page="historyPage"
          :page-size="historyPageSize"
          :page-sizes="[10, 20, 50]"
          :total="historyTotal"
          @current-change="handleHistoryPageChange"
          @size-change="handleHistoryPageSizeChange"
        />
      </div>

      <template #footer>
        <el-button @click="syncHistoryDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="deleteSyncedDataDialogVisible"
      title="数据清理"
      width="1100px"
    >
      <div class="sync-history-toolbar">
        <el-input
          v-model="deleteSyncedDataForm.symbol"
          placeholder="请输入股票代码，如 600519 或 09992"
          clearable
          style="width: 240px;"
          @keyup.enter="loadSyncedDataSummary"
        />
        <el-button
          type="primary"
          :loading="syncedDataSummaryLoading"
          @click="() => loadSyncedDataSummary()"
        >
          {{ syncedDataSummaryLoading ? '查询中' : '查询数据' }}
        </el-button>
        <el-button @click="resetDeleteSyncedDataDialog">
          重置
        </el-button>
        <el-button
          type="danger"
          :disabled="selectedSyncedDataItems.length === 0"
          :loading="deleteSyncedDataLoading"
          @click="handleDeleteSelectedSyncedData"
        >
          删除选中项
        </el-button>
        <span v-if="deleteSelectionHint" class="delete-sync-hint">
          {{ deleteSelectionHint }}
        </span>
      </div>

      <el-alert
        class="sync-section-alert"
        type="warning"
        :closable="false"
        show-icon
        title="这里删除的是真实已同步数据。请先按股票代码查询，再按数据类型清理；这不会删除同步记录。"
      />

      <el-alert
        v-if="deleteDialogQueried && !syncedDataSummaryLoading && !hasExistingSyncedDataItems"
        class="sync-section-alert"
        type="info"
        :closable="false"
        show-icon
        title="当前股票没有可删除的已同步数据"
      />

      <div v-if="hasDeleteLinkedContext" class="sync-linked-context">
        <div class="sync-linked-context__text">
          当前来自同步记录的关联条件：{{ deleteLinkedContextText || '已带入关联条件' }}
        </div>
        <el-button size="small" @click="clearDeleteLinkedFilter">
          清除关联条件
        </el-button>
      </div>

      <el-form :model="deleteSyncedDataForm" label-width="160px" style="margin-bottom: 16px;">
        <el-form-item label="同时清理展示缓存">
          <el-switch v-model="deleteSyncedDataForm.deleteDisplayCache" />
          <span class="delete-sync-hint">删除自选股页使用的实时行情展示缓存</span>
        </el-form-item>
      </el-form>

      <el-table
        ref="syncedDataSummaryTableRef"
        :data="syncedDataSummaryItems"
        v-loading="syncedDataSummaryLoading"
        style="width: 100%;"
        @selection-change="handleSyncedDataSelectionChange"
      >
        <el-table-column
          type="selection"
          width="55"
          :selectable="isSyncedDataRowSelectable"
        />
        <el-table-column label="类型" width="130">
          <template #default="{ row }">
            <el-tag :type="row.exists ? 'success' : 'info'">
              {{ row.delete_type_label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态 / 数量" width="130">
          <template #default="{ row }">
            <div>{{ row.exists ? '已同步' : '无数据' }}</div>
            <div class="history-meta">{{ row.record_count }} 条</div>
          </template>
        </el-table-column>
        <el-table-column label="时间范围" width="220">
          <template #default="{ row }">
            {{ formatSummaryRange(row) }}
          </template>
        </el-table-column>
        <el-table-column label="最近更新时间" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.latest_update) }}
          </template>
        </el-table-column>
        <el-table-column label="来源" width="150">
          <template #default="{ row }">
            {{ formatDataSources(row.data_sources) }}
          </template>
        </el-table-column>
        <el-table-column label="影响说明" min-width="220">
          <template #default="{ row }">
            <div>{{ row.impact_hint }}</div>
            <div class="history-meta">{{ row.target_collections.join(' / ') }}</div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="170" fixed="right">
          <template #default="{ row }">
            <div class="table-action-group">
              <el-button
                type="text"
                size="small"
                @click="openHistoryDialogFromSummaryItem(row)"
              >
                查看对应记录
              </el-button>
              <el-button
                type="text"
                size="small"
                style="color: #f56c6c;"
                :disabled="!row.exists"
                :loading="deletingSyncedDataType === row.delete_type"
                @click="handleDeleteSingleSyncedData(row)"
              >
                删除
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <el-empty
        v-if="deleteDialogQueried && !syncedDataSummaryLoading && syncedDataSummaryItems.length === 0"
        description="未查询到数据概览"
      />

      <el-alert
        v-if="selectedSyncedDataItems.length > 0"
        type="warning"
        :closable="false"
        show-icon
        class="delete-sync-alert"
        :title="`当前将删除：${selectedSyncedDataItems.map(item => item.delete_type_label).join('、')}`"
      />

      <div v-if="deleteDialogQueried" class="related-history-panel">
        <div class="related-history-panel__header">
          <div class="related-history-panel__title">最近相关同步记录</div>
          <div class="history-meta">
            共匹配 {{ relatedSyncHistoryTotal }} 条，当前展示 {{ relatedSyncHistoryRecords.length }} 条
          </div>
        </div>

        <el-table
          :data="relatedSyncHistoryRecords"
          size="small"
          style="width: 100%;"
          empty-text="暂无相关同步记录"
        >
          <el-table-column label="开始时间" width="170">
            <template #default="{ row }">
              {{ formatDateTime(row.started_at) }}
            </template>
          </el-table-column>
          <el-table-column label="股票" width="120">
            <template #default="{ row }">
              {{ row.scope === 'single' ? (row.symbol || '-') : `${row.symbol_count} 只股票` }}
            </template>
          </el-table-column>
          <el-table-column label="类型" min-width="150">
            <template #default="{ row }">
              {{ formatSyncTypes(row.sync_types) }}
            </template>
          </el-table-column>
          <el-table-column label="时间段" width="180">
            <template #default="{ row }">
              {{ formatHistoryRange(row) }}
            </template>
          </el-table-column>
          <el-table-column label="来源" width="140">
            <template #default="{ row }">
              {{ formatDataSources(row.data_sources_used) }}
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="getHistoryStatusTagType(row.status)" size="small">
                {{ formatHistoryStatus(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="110" fixed="right">
            <template #default="{ row }">
              <el-button
                type="text"
                size="small"
                @click="openDeleteDialogFromHistoryRow(row)"
              >
                查看对应数据
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <template #footer>
        <el-button @click="deleteSyncedDataDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import {
  Star,
  Search,
  Refresh,
  Plus,
  Download
} from '@element-plus/icons-vue'
import { favoritesApi } from '@/api/favorites'
import { tagsApi } from '@/api/tags'
import { stockSyncApi } from '@/api/stockSync'
import { normalizeMarketForAnalysis } from '@/utils/market'
import { inferStockMarketMetadata } from '@/utils/stockValidator'
import { ApiClient } from '@/api/request'

import type { FavoriteItem } from '@/api/favorites'
import type {
  DeleteSyncedDataType,
  SyncHistoryQueryParams,
  SyncHistoryRecord,
  SyncedDataSummaryItem,
  SyncedDataSummaryQueryParams
} from '@/api/stockSync'
import { useAuthStore } from '@/stores/auth'


// 颜色可选项（20种预设颜色）
const COLOR_PALETTE = [
  '#409EFF', '#1677FF', '#2F88FF', '#52C41A', '#67C23A',
  '#13C2C2', '#FA8C16', '#E6A23C', '#F56C6C', '#EB2F96',
  '#722ED1', '#8E44AD', '#00BFBF', '#1F2D3D', '#606266',
  '#909399', '#C0C4CC', '#FF7F50', '#A0CFFF', '#2C3E50'
]

const router = useRouter()

interface SyncLinkContext {
  syncTypes: string[]
  dataSources: string[]
  rangeStart: string
  rangeEnd: string
  source: 'history' | 'data' | ''
}

interface LinkedLookupNoticeOptions {
  showEmptyTip?: boolean
}

// 响应式数据
const loading = ref(false)
const favorites = ref<FavoriteItem[]>([])
const userTags = ref<string[]>([])
const tagColorMap = ref<Record<string, string>>({})
const getTagColor = (name: string) => tagColorMap.value[name] || ''

const searchKeyword = ref('')
const selectedTag = ref('')
const selectedMarket = ref('')
const selectedBoard = ref('')
const selectedExchange = ref('')

// 批量选择
const selectedStocks = ref<FavoriteItem[]>([])

// 批量同步对话框
const batchSyncDialogVisible = ref(false)
const batchSyncLoading = ref(false)
const batchSyncForm = ref({
  syncTypes: ['historical', 'financial'],
  dataSource: 'akshare' as 'tushare' | 'akshare',
  days: 365
})

// 单个股票同步对话框
const singleSyncDialogVisible = ref(false)
const singleSyncLoading = ref(false)
type SingleSyncDataSource = 'tushare' | 'akshare' | 'mixed'
type SingleSyncSourceMode = 'normal' | 'realtime_only' | 'mixed'
const currentSyncStock = ref({
  stock_code: '',
  stock_name: ''
})
const singleSyncForm = ref({
  syncTypes: ['realtime'],  // 默认只选中实时行情（最常用）
  dataSource: 'akshare' as SingleSyncDataSource,
  days: 365
})
const singleSyncRealtimeRequiresAkshare = computed(() => singleSyncForm.value.syncTypes.includes('realtime'))
const singleSyncMixedMode = computed(
  () => singleSyncForm.value.syncTypes.includes('realtime') && singleSyncForm.value.syncTypes.some((type) => type !== 'realtime')
)
const singleSyncSourceMode = computed<SingleSyncSourceMode>(() => {
  if (!singleSyncRealtimeRequiresAkshare.value) {
    return 'normal'
  }
  return singleSyncMixedMode.value ? 'mixed' : 'realtime_only'
})
const singleSyncSourceHint = computed(() => (
  singleSyncMixedMode.value ? '实时 AKShare，其他 Tushare。' : '仅支持 AKShare。'
))

watch(
  () => singleSyncForm.value.syncTypes.slice(),
  (types) => {
    const hasRealtime = types.includes('realtime')
    const hasOtherTypes = types.some((type) => type !== 'realtime')

    if (hasRealtime && !hasOtherTypes) {
      singleSyncForm.value.dataSource = 'akshare'
      return
    }

    if (hasRealtime && hasOtherTypes) {
      if (singleSyncForm.value.dataSource === 'tushare') {
        singleSyncForm.value.dataSource = 'mixed'
      }
      return
    }

    if (!hasRealtime && singleSyncForm.value.dataSource === 'mixed') {
      singleSyncForm.value.dataSource = 'tushare'
    }
  },
  { deep: true }
)

// 同步历史
const syncHistoryDialogVisible = ref(false)
const syncHistoryLoading = ref(false)
const clearSyncHistoryLoading = ref(false)
const deletingHistoryId = ref('')
const syncHistoryRecords = ref<SyncHistoryRecord[]>([])
const historyPage = ref(1)
const historyPageSize = ref(10)
const historyTotal = ref(0)
const historyFilterSymbol = ref('')
const historyLinkedContext = ref<SyncLinkContext>({
  syncTypes: [],
  dataSources: [],
  rangeStart: '',
  rangeEnd: '',
  source: ''
})
const pendingHistoryLinkedLookupTip = ref(false)
const deleteSyncedDataDialogVisible = ref(false)
const deleteSyncedDataLoading = ref(false)
const deletingSyncedDataType = ref('')
const syncedDataSummaryLoading = ref(false)
const deleteDialogQueried = ref(false)
const syncedDataSummaryItems = ref<SyncedDataSummaryItem[]>([])
const selectedSyncedDataItems = ref<SyncedDataSummaryItem[]>([])
const relatedSyncHistoryRecords = ref<SyncHistoryRecord[]>([])
const relatedSyncHistoryTotal = ref(0)
const syncedDataSummaryTableRef = ref()
const deleteSyncedDataForm = ref({
  symbol: '',
  deleteDisplayCache: false
})
const deleteSyncedDataContext = ref<SyncLinkContext>({
  syncTypes: [],
  dataSources: [],
  rangeStart: '',
  rangeEnd: '',
  source: ''
})
const pendingDeleteLinkedLookupTip = ref(false)

// 添加对话框
const addDialogVisible = ref(false)
const addLoading = ref(false)
const addFormRef = ref()
const addForm = ref({
  stock_code: '',
  stock_name: '',
  market: 'A股',
  exchange: '',
  board: '',
  tags: [] as string[],
  notes: ''
})

const applyDetectedMarketMeta = (stockCode?: string, overrides?: { exchange?: string; board?: string }) => {
  const inferred = inferStockMarketMetadata(addForm.value.market as 'A股' | '美股' | '港股', stockCode || addForm.value.stock_code)
  addForm.value.exchange = overrides?.exchange || inferred.exchange || ''
  addForm.value.board = overrides?.board || inferred.board || ''
}

const detectedMarketMetaText = computed(() => {
  const parts = [addForm.value.exchange, addForm.value.board].filter(Boolean)
  return parts.join('｜')
})

// 股票代码验证器
const validateStockCode = (_rule: any, value: any, callback: any) => {
  if (!value) {
    callback(new Error('请输入股票代码'))
    return
  }

  const code = value.trim()
  const market = addForm.value.market

  if (market === 'A股') {
    // A股：6位数字
    if (!/^\d{6}$/.test(code)) {
      callback(new Error('A股代码必须是6位数字，如：000001'))
      return
    }
  } else if (market === '港股') {
    // 港股：4位数字 或 4-5位数字+.HK
    if (!/^\d{4,5}$/.test(code) && !/^\d{4,5}\.HK$/i.test(code)) {
      callback(new Error('港股代码格式：4位数字（如：0700）或带后缀（如：0700.HK）'))
      return
    }
  } else if (market === '美股') {
    // 美股：1-5个字母
    if (!/^[A-Z]{1,5}$/i.test(code)) {
      callback(new Error('美股代码必须是1-5个字母，如：AAPL'))
      return
    }
  }

  callback()
}

const addRules = {
  market: [
    { required: true, message: '请选择市场类型', trigger: 'change' }
  ],
  stock_code: [
    { required: true, message: '请输入股票代码', trigger: 'blur' },
    { validator: validateStockCode, trigger: 'blur' }
  ],
  stock_name: [
    { required: true, message: '请输入股票名称', trigger: 'blur' }
  ]
}

// 编辑对话框
const editDialogVisible = ref(false)
const editLoading = ref(false)
const editFormRef = ref()
const editForm = ref({
  stock_code: '',
  stock_name: '',
  market: 'A股',
  tags: [] as string[],
  notes: ''
})

const quickTagDialogVisible = ref(false)
const quickTagLoading = ref(false)
const quickTagCreating = ref(false)
const quickTagForm = ref({
  stock_code: '',
  stock_name: '',
  tags: [] as string[]
})
const quickNewTag = ref({
  name: '',
  color: '#409EFF'
})

const normalizeTagList = (tags: string[]) => {
  const normalized: string[] = []
  const seen = new Set<string>()

  for (const rawTag of tags || []) {
    const tag = String(rawTag || '').trim()
    if (!tag || seen.has(tag)) {
      continue
    }
    seen.add(tag)
    normalized.push(tag)
  }

  return normalized
}


// 计算属性
const filteredFavorites = computed<FavoriteItem[]>(() => {
  let result: FavoriteItem[] = favorites.value

  // 关键词搜索
  if (searchKeyword.value) {
    const keyword = searchKeyword.value.toLowerCase()
    result = result.filter((item: FavoriteItem) =>
      String(item.stock_code || '').toLowerCase().includes(keyword) ||
      String(item.stock_name || '').toLowerCase().includes(keyword)
    )
  }

  // 市场筛选
  if (selectedMarket.value) {
    result = result.filter((item: FavoriteItem) =>
      item.market === selectedMarket.value
    )
  }

  // 板块筛选
  if (selectedBoard.value) {
    result = result.filter((item: FavoriteItem) =>
      item.board === selectedBoard.value
    )
  }

  // 交易所筛选
  if (selectedExchange.value) {
    result = result.filter((item: FavoriteItem) =>
      item.exchange === selectedExchange.value
    )
  }

  // 标签筛选
  if (selectedTag.value) {
    result = result.filter((item: FavoriteItem) =>
      (item.tags || []).includes(selectedTag.value)
    )
  }

  return result
})

const availableBoards = computed(() => (
  Array.from(
    new Set(
      favorites.value
        .map(item => String(item.board || '').trim())
        .filter(board => board && board !== '-')
    )
  )
))

const availableExchanges = computed(() => (
  Array.from(
    new Set(
      favorites.value
        .map(item => String(item.exchange || '').trim())
        .filter(exchange => exchange && exchange !== '-')
    )
  )
))

const tagUsageCountMap = computed<Record<string, number>>(() => {
  return favorites.value.reduce((acc: Record<string, number>, item: FavoriteItem) => {
    const uniqueTags = new Set(
      (item.tags || [])
        .map(tag => String(tag || '').trim())
        .filter(Boolean)
    )

    uniqueTags.forEach(tag => {
      acc[tag] = (acc[tag] || 0) + 1
    })

    return acc
  }, {})
})

const getTagUsageCount = (tagName: string) => tagUsageCountMap.value[tagName] || 0

// 判断是否有任意自选股
const hasFavorites = computed(() => {
  return favorites.value.length > 0
})

// 判断选中的股票是否都是A股
const selectedStocksAreAllAShares = computed(() => {
  if (selectedStocks.value.length === 0) return false
  return selectedStocks.value.every(item => item.market === 'A股')
})

// 方法
const loadFavorites = async () => {
  loading.value = true
  try {
    const res = await favoritesApi.list()
    favorites.value = ((res as any)?.data || []) as FavoriteItem[]
  } catch (error: any) {
    console.error('加载自选股失败:', error)
    ElMessage.error(error.message || '加载自选股失败')
  } finally {
    loading.value = false
  }
}

// 同步实时行情
const syncRealtimeLoading = ref(false)
const syncAllRealtime = async () => {
  if (favorites.value.length === 0) {
    ElMessage.warning('没有自选股需要同步')
    return
  }

  syncRealtimeLoading.value = true
  try {
    const res = await favoritesApi.syncRealtime('akshare')
    const data = (res as any)?.data

    if ((res as any)?.success) {
      const summaryMessage = data?.message || `同步完成: 成功 ${data?.success_count} 只`
      if ((data?.failed_count || 0) > 0) {
        ElMessage.warning(`${summaryMessage}；部分股票未拿到最新源数据，已尽量回退缓存`)
      } else {
        ElMessage.success(summaryMessage)
      }
      // 重新加载自选股列表以获取最新价格
      await loadFavorites()
    } else {
      ElMessage.error((res as any)?.message || '同步失败')
    }
  } catch (error: any) {
    console.error('同步实时行情失败:', error)
    ElMessage.error(error.message || '同步失败，请稍后重试')
  } finally {
    syncRealtimeLoading.value = false
  }
}

const loadUserTags = async () => {
  try {
    const res = await tagsApi.list()
    const list = (res as any)?.data
    if (Array.isArray(list)) {
      userTags.value = list.map((t: any) => t.name)
      tagColorMap.value = list.reduce((acc: Record<string, string>, t: any) => {
        acc[t.name] = t.color
        return acc
      }, {})
      syncTagSelectionsWithUserTags()
      if (selectedTag.value && !userTags.value.includes(selectedTag.value)) {
        selectedTag.value = ''
      }
    } else {
      userTags.value = []
      tagColorMap.value = {}
      syncTagSelectionsWithUserTags()
      selectedTag.value = ''
    }
  } catch (error) {
    console.error('加载标签失败:', error)
    userTags.value = []
    tagColorMap.value = {}
    syncTagSelectionsWithUserTags()
    selectedTag.value = ''
  }
}

const syncTagSelectionsWithUserTags = () => {
  const allowedTags = new Set(userTags.value)
  addForm.value.tags = normalizeTagList((addForm.value.tags || []).filter(tag => allowedTags.has(tag)))
  editForm.value.tags = normalizeTagList((editForm.value.tags || []).filter(tag => allowedTags.has(tag)))
  quickTagForm.value.tags = normalizeTagList((quickTagForm.value.tags || []).filter(tag => allowedTags.has(tag)))
}

// 标签管理对话框 - 脚本
const tagDialogVisible = ref(false)
const tagLoading = ref(false)
const tagList = ref<any[]>([])
const newTag = ref({ name: '', color: '#409EFF', sort_order: 0 })

const loadTagList = async () => {
  tagLoading.value = true
  try {
    const res = await tagsApi.list()
    tagList.value = (res as any)?.data || []
  } catch (e) {
    console.error('加载标签列表失败:', e)
  } finally {
    tagLoading.value = false
  }
}

const openTagManager = async () => {
  tagDialogVisible.value = true
  await loadTagList()
}

const createTag = async () => {
  if (!newTag.value.name || !newTag.value.name.trim()) {
    ElMessage.warning('请输入标签名')
    return
  }
  tagLoading.value = true
  try {
    await tagsApi.create({ ...newTag.value })
    ElMessage.success('创建成功')
    newTag.value = { name: '', color: '#409EFF', sort_order: 0 }
    await loadTagList()
    await loadUserTags()
  } catch (e: any) {
    console.error('创建标签失败:', e)
    ElMessage.error(e?.message || '创建失败')
  } finally {
    tagLoading.value = false
  }
}

const editTag = (row: any) => {
  row._editing = true
  row._name = row.name
  row._color = row.color
  row._sort = row.sort_order
}

const cancelEditTag = (row: any) => {
  row._editing = false
}

const saveTag = async (row: any) => {
  tagLoading.value = true
  try {
    await tagsApi.update(row.id, {
      name: row._name ?? row.name,
      color: row._color ?? row.color,
      sort_order: row._sort ?? row.sort_order,
    })
    ElMessage.success('保存成功')
    row._editing = false
    await loadTagList()
    await loadUserTags()
    await loadFavorites()
  } catch (e: any) {
    console.error('保存标签失败:', e)
    ElMessage.error(e?.message || '保存失败')
  } finally {
    tagLoading.value = false
  }
}

const deleteTag = async (row: any) => {
  const usageCount = getTagUsageCount(row.name)
  try {
    await ElMessageBox.confirm(
      `确定删除标签 ${row.name} 吗？当前有 ${usageCount} 只股票在使用该标签，删除后会同步从这些股票的标签中移除。`,
      '删除标签',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    tagLoading.value = true
    await tagsApi.remove(row.id)
    ElMessage.success('已删除')
    await loadTagList()
    await loadUserTags()
    await loadFavorites()
  } catch (e) {
    // 用户取消或失败
  } finally {
    tagLoading.value = false
  }
}



const refreshData = () => {
  loadFavorites()
  loadUserTags()
}

const showAddDialog = () => {
  addForm.value = {
    stock_code: '',
    stock_name: '',
    market: 'A股',
    exchange: '',
    board: '',
    tags: [],
    notes: ''
  }
  addDialogVisible.value = true
}

// 市场类型切换时清空股票代码和名称
const handleMarketChange = () => {
  addForm.value.stock_code = ''
  addForm.value.stock_name = ''
  addForm.value.exchange = ''
  addForm.value.board = ''
  // 清除验证错误
  if (addFormRef.value) {
    addFormRef.value.clearValidate(['stock_code', 'stock_name'])
  }
}

// 获取股票代码输入提示
const getStockCodePlaceholder = () => {
  const market = addForm.value.market
  if (market === 'A股') {
    return '请输入6位数字代码，如：000001'
  } else if (market === '港股') {
    return '请输入4位数字代码，如：0700'
  } else if (market === '美股') {
    return '请输入股票代码，如：AAPL'
  }
  return '请输入股票代码'
}

// 获取股票代码输入提示文字
const getStockCodeHint = () => {
  const market = addForm.value.market
  if (market === 'A股') {
    return '输入代码后失焦，将自动填充股票名称'
  } else if (market === '港股') {
    return '港股不支持自动获取名称，请手动输入'
  } else if (market === '美股') {
    return '美股不支持自动获取名称，请手动输入'
  }
  return ''
}

const fetchStockInfo = async () => {
  if (!addForm.value.stock_code) return

  try {
    const symbol = addForm.value.stock_code.trim().toUpperCase()
    const market = addForm.value.market
    addForm.value.stock_code = symbol
    applyDetectedMarketMeta(symbol)

    // 🔥 只有A股支持自动获取股票名称
    if (market === 'A股') {
      // 从后台获取股票基础信息
      const res = await ApiClient.get(`/api/stock-data/basic-info/${symbol}`)

      if ((res as any)?.success && (res as any)?.data) {
        const stockInfo = (res as any).data
        // 自动填充股票名称
        if (stockInfo.name) {
          addForm.value.stock_name = stockInfo.name
          ElMessage.success(`已自动填充股票名称: ${stockInfo.name}`)
        }
        applyDetectedMarketMeta(symbol, {
          exchange: stockInfo.sse || stockInfo.exchange_name || stockInfo.exchange,
          board: stockInfo.market || stockInfo.board
        })
      } else {
        ElMessage.warning('未找到该股票信息，请手动输入股票名称')
      }
    }
    // 港股和美股不调用API，用户需要手动输入
  } catch (error: any) {
    console.error('获取股票信息失败:', error)
    ElMessage.warning('获取股票信息失败，请手动输入股票名称')
  }
}

const handleAddFavorite = async () => {
  try {
    await addFormRef.value.validate()
    addLoading.value = true
    const normalizedTags = normalizeTagList(addForm.value.tags || [])
    await ensureTagsExist(normalizedTags)
    const payload = {
      ...addForm.value,
      tags: normalizedTags
    }
    const res = await favoritesApi.add(payload as any)
    if ((res as any)?.success === false) throw new Error((res as any)?.message || '添加失败')
    ElMessage.success('添加成功')
    addDialogVisible.value = false
    await loadFavorites()
    await loadUserTags()
  } catch (error: any) {
    console.error('添加自选股失败:', error)
    ElMessage.error(error.message || '添加失败')
  } finally {
    addLoading.value = false
  }
}

const handleUpdateFavorite = async () => {
  try {
    editLoading.value = true
    const normalizedTags = normalizeTagList(editForm.value.tags || [])
    await ensureTagsExist(normalizedTags)
    const payload = {
      tags: normalizedTags,
      notes: editForm.value.notes
    }
    const res = await favoritesApi.update(editForm.value.stock_code, payload as any)
    if ((res as any)?.success === false) throw new Error((res as any)?.message || '更新失败')
    ElMessage.success('保存成功')
    editDialogVisible.value = false
    await loadFavorites()
    await loadUserTags()
  } catch (error: any) {
    console.error('更新自选股失败:', error)
    ElMessage.error(error.message || '保存失败')
  } finally {
    editLoading.value = false
  }
}

const ensureTagsExist = async (tags: string[], defaultColor = '#409EFF') => {
  const normalizedTags = normalizeTagList(tags || [])

  const missingTags = normalizedTags.filter(tag => !userTags.value.includes(tag))
  for (const tagName of missingTags) {
    await tagsApi.create({
      name: tagName,
      color: defaultColor,
      sort_order: 0
    })
  }

  if (missingTags.length > 0) {
    await loadTagList()
    await loadUserTags()
  }
}

const createQuickTag = async () => {
  const tagName = quickNewTag.value.name.trim()
  if (!tagName) {
    ElMessage.warning('请输入新标签名')
    return
  }

  quickTagCreating.value = true
  try {
    if (!userTags.value.includes(tagName)) {
      await tagsApi.create({
        name: tagName,
        color: quickNewTag.value.color,
        sort_order: 0
      })
      await loadTagList()
      await loadUserTags()
    }

    if (!quickTagForm.value.tags.includes(tagName)) {
      quickTagForm.value.tags = normalizeTagList([...quickTagForm.value.tags, tagName])
    }

    quickNewTag.value = {
      name: '',
      color: '#409EFF'
    }
    ElMessage.success('标签已加入并同步到标签管理')
  } catch (error: any) {
    console.error('快速创建标签失败:', error)
    ElMessage.error(error.message || '创建标签失败')
  } finally {
    quickTagCreating.value = false
  }
}

const handleQuickTagUpdate = async () => {
  try {
    quickTagLoading.value = true
    const normalizedTags = normalizeTagList(quickTagForm.value.tags || [])
    quickTagForm.value.tags = normalizedTags
    await ensureTagsExist(normalizedTags)
    const payload = {
      tags: normalizedTags
    }
    const res = await favoritesApi.update(quickTagForm.value.stock_code, payload as any)
    if ((res as any)?.success === false) throw new Error((res as any)?.message || '更新标签失败')
    ElMessage.success('标签已更新')
    quickTagDialogVisible.value = false
    await loadFavorites()
    await loadUserTags()
  } catch (error: any) {
    console.error('快速更新标签失败:', error)
    ElMessage.error(error.message || '更新标签失败')
  } finally {
    quickTagLoading.value = false
  }
}


const editFavorite = (row: any) => {
  editForm.value = {
    stock_code: row.stock_code,
    stock_name: row.stock_name,
    market: row.market || 'A股',
    tags: Array.isArray(row.tags) ? normalizeTagList(row.tags) : [],
    notes: row.notes || ''
  }
  editDialogVisible.value = true
}

const openQuickTagEditor = (row: any) => {
  quickTagForm.value = {
    stock_code: row.stock_code,
    stock_name: row.stock_name,
    tags: Array.isArray(row.tags) ? normalizeTagList(row.tags) : []
  }
  quickNewTag.value = {
    name: '',
    color: '#409EFF'
  }
  quickTagDialogVisible.value = true
}

const analyzeFavorite = (row: any) => {
  router.push({
    name: 'SingleAnalysis',
    query: { stock: row.stock_code, market: normalizeMarketForAnalysis(row.market || 'A股') }
  })
}

const removeFavorite = async (row: any) => {
  try {
    await ElMessageBox.confirm(
      `确定要从自选股中移除 ${row.stock_name} 吗？这会同时删除该股票的相关同步历史和已同步数据。`,
      '确认移除',
      {
        confirmButtonText: '确定移除并清理',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    const res = await favoritesApi.remove(row.stock_code, { cleanup_related: true })
    if ((res as any)?.success === false) throw new Error((res as any)?.message || '移除失败')
    const cleanup = (res as any)?.data?.cleanup
    if (cleanup?.success === false) {
      ElMessage.warning((res as any)?.message || '自选股已移除，但联动清理失败')
    } else {
      ElMessage.success((res as any)?.message || '移除成功，并已清理相关同步历史和数据')
    }
    await loadFavorites()
  } catch (e) {
    // 用户取消或失败
  }
}

const viewStockDetail = (row: any) => {
  router.push({
    name: 'StockDetail',
    params: { code: String(row.stock_code || '').toUpperCase() }
  })
}

// 处理表格选择变化
const handleSelectionChange = (selection: FavoriteItem[]) => {
  selectedStocks.value = selection
}

// 显示单个股票同步对话框
const showSingleSyncDialog = (row: FavoriteItem) => {
  currentSyncStock.value = {
    stock_code: row.stock_code || '',
    stock_name: row.stock_name || ''
  }
  singleSyncDialogVisible.value = true
}

// 执行单个股票同步
const handleSingleSync = async () => {
  if (singleSyncForm.value.syncTypes.length === 0) {
    ElMessage.warning('请至少选择一种同步内容')
    return
  }

  singleSyncLoading.value = true
  try {
    const res = await stockSyncApi.syncSingle({
      symbol: currentSyncStock.value.stock_code,
      sync_realtime: singleSyncForm.value.syncTypes.includes('realtime'),
      sync_historical: singleSyncForm.value.syncTypes.includes('historical'),
      sync_financial: singleSyncForm.value.syncTypes.includes('financial'),
      sync_basic: singleSyncForm.value.syncTypes.includes('basic'),
      data_source: singleSyncForm.value.dataSource,
      days: singleSyncForm.value.days
    })

    if (res.success) {
      const data = res.data
      let message = `股票 ${currentSyncStock.value.stock_code} 数据同步完成\n`

      if (data.realtime_sync) {
        if (data.realtime_sync.success) {
          message += `✅ 实时行情同步成功\n`
        } else {
          message += `❌ 实时行情同步失败: ${data.realtime_sync.error || '未知错误'}\n`
        }
      }

      if (data.historical_sync) {
        if (data.historical_sync.success) {
          message += `✅ 历史数据: ${data.historical_sync.records || 0} 条记录`
          if (data.historical_sync.data_source_used) {
            message += `（${String(data.historical_sync.data_source_used).toUpperCase()}）`
          }
          message += '\n'
        } else {
          message += `❌ 历史数据同步失败: ${data.historical_sync.error || '未知错误'}\n`
        }
      }

      if (data.financial_sync) {
        if (data.financial_sync.success) {
          message += '✅ 财务数据同步成功'
          if (data.financial_sync.data_source_used) {
            message += `（${String(data.financial_sync.data_source_used).toUpperCase()}）`
          }
          message += '\n'
        } else {
          message += `❌ 财务数据同步失败: ${data.financial_sync.error || '未知错误'}\n`
        }
      }

      if (data.basic_sync) {
        if (data.basic_sync.success) {
          message += '✅ 基础数据同步成功'
          if (data.basic_sync.data_source_used) {
            message += `（${String(data.basic_sync.data_source_used).toUpperCase()}）`
          }
          message += '\n'
        } else {
          message += `❌ 基础数据同步失败: ${data.basic_sync.error || '未知错误'}\n`
        }
      }

      ElMessage.success(message)
      singleSyncDialogVisible.value = false

      // 刷新列表
      await loadFavorites()
      if (syncHistoryDialogVisible.value) {
        await loadSyncHistory(1)
      }
    } else {
      ElMessage.error(res.message || '同步失败')
    }
  } catch (error: any) {
    console.error('同步失败:', error)
    ElMessage.error(error.message || '同步失败，请稍后重试')
  } finally {
    singleSyncLoading.value = false
  }
}

// 显示批量同步对话框
const showBatchSyncDialog = () => {
  if (selectedStocks.value.length === 0) {
    ElMessage.warning('请先选择要同步的股票')
    return
  }
  batchSyncDialogVisible.value = true
}

// 执行批量同步
const handleBatchSync = async () => {
  if (batchSyncForm.value.syncTypes.length === 0) {
    ElMessage.warning('请至少选择一种同步内容')
    return
  }

  batchSyncLoading.value = true
  try {
    const symbols = selectedStocks.value
      .map(stock => stock.stock_code)
      .filter((symbol): symbol is string => Boolean(symbol))

    const res = await stockSyncApi.syncBatch({
      symbols,
      sync_historical: batchSyncForm.value.syncTypes.includes('historical'),
      sync_financial: batchSyncForm.value.syncTypes.includes('financial'),
      sync_basic: batchSyncForm.value.syncTypes.includes('basic'),
      data_source: batchSyncForm.value.dataSource,
      days: batchSyncForm.value.days
    })

    if (res.success) {
      const data = res.data
      let message = `批量同步完成 (共 ${symbols.length} 只股票)\n`

      if (data.historical_sync) {
        message += `✅ 历史数据: ${data.historical_sync.success_count}/${data.historical_sync.success_count + data.historical_sync.error_count} 成功，共 ${data.historical_sync.total_records} 条记录\n`
      }

      if (data.financial_sync) {
        message += `✅ 财务数据: ${data.financial_sync.success_count}/${data.financial_sync.total_symbols} 成功\n`
      }

      if (data.basic_sync) {
        message += `✅ 基础数据: ${data.basic_sync.success_count}/${data.basic_sync.total_symbols} 成功\n`
      }

      ElMessage.success(message)
      batchSyncDialogVisible.value = false

      // 刷新列表
      await loadFavorites()
      if (syncHistoryDialogVisible.value) {
        await loadSyncHistory(1)
      }
    } else {
      ElMessage.error(res.message || '批量同步失败')
    }
  } catch (error: any) {
    console.error('批量同步失败:', error)
    ElMessage.error(error.message || '批量同步失败，请稍后重试')
  } finally {
    batchSyncLoading.value = false
  }
}

const isHistoricalFallbackMode = (mode?: string | null) => mode === 'historical_close_fallback'

const getChangeClass = (changePercent: number, displayMode?: string | null) => {
  const useSoftColor = isHistoricalFallbackMode(displayMode)
  if (changePercent > 0) return useSoftColor ? 'text-red-soft' : 'text-red'
  if (changePercent < 0) return useSoftColor ? 'text-green-soft' : 'text-green'
  return useSoftColor ? 'text-muted-soft' : ''
}

const getPriceClass = (row: FavoriteItem) => {
  if (!isHistoricalFallbackMode(row.price_display_mode)) {
    return ''
  }

  const changePercent = Number(row.change_percent)
  if (Number.isFinite(changePercent) && changePercent > 0) return 'text-red-soft'
  if (Number.isFinite(changePercent) && changePercent < 0) return 'text-green-soft'
  return 'text-muted-soft'
}


const formatPrice = (value: any): string => {
  const n = Number(value)
  return Number.isFinite(n) ? n.toFixed(2) : '-'
}

const getCurrencySymbol = (row: FavoriteItem): string => {
  const currency = String(row.currency || '').toUpperCase()
  if (currency === 'HKD' || row.market === '港股') return 'HK$'
  if (currency === 'USD' || row.market === '美股') return '$'
  return '¥'
}

const formatPercent = (value: any): string => {
  const n = Number(value)
  if (!Number.isFinite(n)) return '-'
  const sign = n > 0 ? '+' : ''
  return `${sign}${n.toFixed(2)}%`
}

const formatQuoteCaptureTime = (value?: string | null): string | null => {
  if (!value) return null
  return new Date(value).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  })
}

const getQuoteUpdatedDate = (row: FavoriteItem): string | null => {
  if (!row.quote_updated_at) return null
  const value = row.quote_updated_at.includes('T')
    ? row.quote_updated_at.split('T')[0]
    : row.quote_updated_at.split(' ')[0]
  return value.replace(/\//g, '-')
}

const getQuotePrimaryTimestamp = (row: FavoriteItem): string | null => {
  const updatedDate = getQuoteUpdatedDate(row)
  const captureTime = formatQuoteCaptureTime(row.quote_updated_at)

  if (row.quote_trade_date && updatedDate && row.quote_trade_date === updatedDate && captureTime) {
    return `行情 ${captureTime}`
  }

  if (row.quote_trade_date) {
    return `行情 ${row.quote_trade_date}`
  }

  if (captureTime) {
    return `抓取 ${captureTime}`
  }

  return null
}

const getQuoteSecondaryTimestamp = (row: FavoriteItem): string | null => {
  if (!row.quote_updated_at) return null

  const captureTime = formatQuoteCaptureTime(row.quote_updated_at)
  const updatedDate = getQuoteUpdatedDate(row)
  if (!captureTime) return null

  if (row.quote_trade_date && updatedDate && row.quote_trade_date === updatedDate) {
    return null
  }

  return `抓取 ${captureTime}`
}

const getPriceTooltip = (row: FavoriteItem): string | null => {
  const parts = [row.price_display_hint, getQuoteSecondaryTimestamp(row)].filter(Boolean)
  return parts.length ? parts.join(' | ') : null
}

const getChangeTooltip = (row: FavoriteItem): string | null => {
  const parts = [row.change_display_hint, getQuoteSecondaryTimestamp(row)].filter(Boolean)
  return parts.length ? parts.join(' | ') : null
}

const getQuoteTimestampLabel = (row: FavoriteItem): string | null => {
  return getQuotePrimaryTimestamp(row)
}

const formatDateTime = (dateStr?: string | null) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN', {
    hour12: false
  })
}

const formatDuration = (seconds?: number) => {
  if (seconds === null || seconds === undefined || Number.isNaN(Number(seconds))) return '-'
  const value = Number(seconds)
  if (value < 1) return `${Math.round(value * 1000)}ms`
  if (value < 60) return `${value.toFixed(1)}s`
  const minutes = Math.floor(value / 60)
  const remainSeconds = Math.round(value % 60)
  return `${minutes}m ${remainSeconds}s`
}

const formatSyncTypeLabel = (type: string) => {
  const map: Record<string, string> = {
    realtime: '实时行情',
    historical: '历史行情',
    financial: '财务数据',
    basic: '基础数据'
  }
  return map[type] || type
}

const formatHistoryRange = (row: SyncHistoryRecord) => {
  if (!row.historical_range) return '-'
  return `${row.historical_range.start_date} ~ ${row.historical_range.end_date}`
}

const formatDataSources = (sources: string[]) => {
  if (!Array.isArray(sources) || sources.length === 0) return '-'
  return sources.map(source => source.toUpperCase()).join(' / ')
}

const formatSyncTypes = (types: string[]) => {
  if (!Array.isArray(types) || types.length === 0) return '-'
  return types.map((type: string) => formatSyncTypeLabel(type)).join('、')
}

const formatHistoryStatus = (status: string) => {
  const map: Record<string, string> = {
    success: '成功',
    partial_success: '部分成功',
    failed: '失败'
  }
  return map[status] || status
}

const getHistoryStatusTagType = (status: string) => {
  if (status === 'success') return 'success'
  if (status === 'partial_success') return 'warning'
  if (status === 'failed') return 'danger'
  return 'info'
}

const mapDeleteTypeToSyncType = (deleteType: DeleteSyncedDataType) => {
  return deleteType === 'realtime_cache' ? 'realtime' : deleteType
}

const hasHistoryLinkedContext = computed(() => {
  const context = historyLinkedContext.value
  return context.syncTypes.length > 0 ||
    context.dataSources.length > 0 ||
    !!context.rangeStart ||
    !!context.rangeEnd
})

const hasDeleteLinkedContext = computed(() => {
  const context = deleteSyncedDataContext.value
  return context.syncTypes.length > 0 ||
    context.dataSources.length > 0 ||
    !!context.rangeStart ||
    !!context.rangeEnd
})

const hasExistingSyncedDataItems = computed(() => (
  syncedDataSummaryItems.value.some(item => item.exists)
))

const deleteSelectionHint = computed(() => {
  if (deleteSyncedDataLoading.value) {
    return '正在删除已选数据类型'
  }
  if (syncedDataSummaryLoading.value) {
    return '正在查询可删除的数据类型'
  }
  if (!deleteDialogQueried.value) {
    return '请先按股票代码查询'
  }
  if (!hasExistingSyncedDataItems.value) {
    return '当前股票没有可删除的已同步数据'
  }
  if (selectedSyncedDataItems.value.length === 0) {
    return '请先勾选有数据的类型'
  }
  return ''
})

const buildContextSummary = (context: SyncLinkContext) => {
  const parts: string[] = []
  if (context.syncTypes.length > 0) {
    parts.push(`类型：${context.syncTypes.map(type => formatSyncTypeLabel(type)).join('、')}`)
  }
  if (context.dataSources.length > 0) {
    parts.push(`来源：${formatDataSources(context.dataSources)}`)
  }
  if (context.rangeStart || context.rangeEnd) {
    parts.push(`时间段：${context.rangeStart || '-'} ~ ${context.rangeEnd || '-'}`)
  }
  return parts.join('；')
}

const historyLinkedContextText = computed(() => buildContextSummary(historyLinkedContext.value))
const deleteLinkedContextText = computed(() => buildContextSummary(deleteSyncedDataContext.value))

const resetHistoryLinkedContext = () => {
  historyLinkedContext.value = {
    syncTypes: [],
    dataSources: [],
    rangeStart: '',
    rangeEnd: '',
    source: ''
  }
}

const resetDeleteLinkedContext = () => {
  deleteSyncedDataContext.value = {
    syncTypes: [],
    dataSources: [],
    rangeStart: '',
    rangeEnd: '',
    source: ''
  }
}

const buildHistoryContextFromSummaryItem = (row: SyncedDataSummaryItem): SyncLinkContext => ({
  syncTypes: [mapDeleteTypeToSyncType(row.delete_type)],
  dataSources: row.data_sources || [],
  rangeStart: row.delete_type === 'historical' ? (row.range_start || '') : '',
  rangeEnd: row.delete_type === 'historical' ? (row.range_end || '') : '',
  source: 'data'
})

const buildDeleteContextFromHistoryRecord = (row: SyncHistoryRecord): SyncLinkContext => ({
  syncTypes: row.sync_types || [],
  dataSources: row.data_sources_used || [],
  rangeStart: row.historical_range?.start_date || '',
  rangeEnd: row.historical_range?.end_date || '',
  source: 'history'
})

const resolveHistoryRecordSymbol = (row: SyncHistoryRecord) => {
  return (row.symbol || row.symbols?.[0] || '').trim().toUpperCase()
}

const buildHistoryQueryParams = (page = historyPage.value): SyncHistoryQueryParams => {
  const symbol = historyFilterSymbol.value.trim().toUpperCase()
  const context = historyLinkedContext.value
  return {
    page,
    page_size: historyPageSize.value,
    symbol: symbol || undefined,
    sync_types: context.syncTypes.length > 0 ? context.syncTypes : undefined,
    data_sources: context.dataSources.length > 0 ? context.dataSources : undefined,
    range_start: context.rangeStart || undefined,
    range_end: context.rangeEnd || undefined
  }
}

const buildDeleteSummaryQueryParams = (): SyncedDataSummaryQueryParams => {
  const symbol = deleteSyncedDataForm.value.symbol.trim().toUpperCase()
  const context = deleteSyncedDataContext.value
  return {
    symbol,
    sync_types: context.syncTypes.length > 0 ? context.syncTypes : undefined,
    data_sources: context.dataSources.length > 0 ? context.dataSources : undefined,
    range_start: context.rangeStart || undefined,
    range_end: context.rangeEnd || undefined,
    related_history_limit: 6
  }
}

const applyDeleteDialogAutoSelection = async () => {
  const expectedTypes = deleteSyncedDataContext.value.syncTypes
  const matchedRows = syncedDataSummaryItems.value.filter(item =>
    item.exists && expectedTypes.includes(mapDeleteTypeToSyncType(item.delete_type))
  )

  selectedSyncedDataItems.value = matchedRows

  await nextTick()
  const table = syncedDataSummaryTableRef.value
  if (!table) return

  table.clearSelection?.()
  matchedRows.forEach(row => table.toggleRowSelection?.(row, true))
}

const loadSyncHistory = async (
  page = historyPage.value,
  options: LinkedLookupNoticeOptions = {}
) => {
  syncHistoryLoading.value = true
  try {
    historyPage.value = page
    const res = await stockSyncApi.getHistory(buildHistoryQueryParams(page))

    if (res.success) {
      syncHistoryRecords.value = res.data.records || []
      historyTotal.value = res.data.total || 0
      historyPage.value = res.data.page || page
      historyPageSize.value = res.data.page_size || historyPageSize.value

      if (options.showEmptyTip && syncHistoryRecords.value.length === 0) {
        ElMessage.info('未找到与当前数据项关联的同步记录')
      }
    } else {
      ElMessage.error(res.message || '加载同步历史失败')
    }
  } catch (error: any) {
    console.error('加载同步历史失败:', error)
    ElMessage.error(error.message || '加载同步历史失败')
  } finally {
    syncHistoryLoading.value = false
  }
}

const openSyncHistoryDialog = async (
  symbol = '',
  context?: Partial<SyncLinkContext>,
  options: LinkedLookupNoticeOptions = {}
) => {
  if (symbol) {
    historyFilterSymbol.value = symbol.trim().toUpperCase()
  }
  historyLinkedContext.value = {
    syncTypes: context?.syncTypes || [],
    dataSources: context?.dataSources || [],
    rangeStart: context?.rangeStart || '',
    rangeEnd: context?.rangeEnd || '',
    source: context?.source || ''
  }
  syncHistoryDialogVisible.value = true
  pendingHistoryLinkedLookupTip.value = !!options.showEmptyTip
  await loadSyncHistory(1, { showEmptyTip: pendingHistoryLinkedLookupTip.value })
  pendingHistoryLinkedLookupTip.value = false
}

const resetSyncHistoryFilter = async () => {
  historyFilterSymbol.value = ''
  resetHistoryLinkedContext()
  await loadSyncHistory(1)
}

const clearHistoryLinkedFilter = async () => {
  resetHistoryLinkedContext()
  await loadSyncHistory(1)
}

const handleHistoryPageChange = async (page: number) => {
  await loadSyncHistory(page)
}

const handleHistoryPageSizeChange = async (pageSize: number) => {
  historyPageSize.value = pageSize
  await loadSyncHistory(1)
}

const handleDeleteSyncHistory = async (row: SyncHistoryRecord) => {
  try {
    await ElMessageBox.confirm('确定删除这条同步历史吗？', '删除同步历史', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    deletingHistoryId.value = row.id
    const res = await stockSyncApi.deleteHistoryRecord(row.id)
    if (!res.success) {
      throw new Error(res.message || '删除失败')
    }

    ElMessage.success('同步历史已删除')
    const maxPage = Math.max(1, Math.ceil(Math.max(historyTotal.value - 1, 1) / historyPageSize.value))
    await loadSyncHistory(Math.min(historyPage.value, maxPage))
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('删除同步历史失败:', error)
      ElMessage.error(error.message || '删除同步历史失败')
    }
  } finally {
    deletingHistoryId.value = ''
  }
}

const handleClearSyncHistory = async () => {
  try {
    const params = buildHistoryQueryParams(1)
    const targetText = historyFilterSymbol.value.trim().toUpperCase()
      ? `当前筛选股票 ${historyFilterSymbol.value.trim().toUpperCase()} 的`
      : hasHistoryLinkedContext.value
        ? '当前关联筛选结果中的'
        : '当前列表的'
    await ElMessageBox.confirm(`确定删除${targetText}同步历史吗？`, '清空同步历史', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    clearSyncHistoryLoading.value = true
    const res = await stockSyncApi.clearHistory({
      symbol: params.symbol,
      sync_types: params.sync_types,
      data_sources: params.data_sources,
      range_start: params.range_start,
      range_end: params.range_end
    })
    if (!res.success) {
      throw new Error(res.message || '清空失败')
    }

    ElMessage.success(res.message || '同步历史已清空')
    await loadSyncHistory(1)
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('清空同步历史失败:', error)
      ElMessage.error(error.message || '清空同步历史失败')
    }
  } finally {
    clearSyncHistoryLoading.value = false
  }
}

const openDeleteSyncedDataDialog = (symbol = '', context?: Partial<SyncLinkContext>) => {
  deleteSyncedDataForm.value = {
    symbol: (symbol || historyFilterSymbol.value || '').trim().toUpperCase(),
    deleteDisplayCache: false
  }
  deleteSyncedDataContext.value = {
    syncTypes: context?.syncTypes || [],
    dataSources: context?.dataSources || [],
    rangeStart: context?.rangeStart || '',
    rangeEnd: context?.rangeEnd || '',
    source: context?.source || ''
  }
  deleteDialogQueried.value = false
  syncedDataSummaryItems.value = []
  selectedSyncedDataItems.value = []
  relatedSyncHistoryRecords.value = []
  relatedSyncHistoryTotal.value = 0
  deleteSyncedDataDialogVisible.value = true
}

const resetDeleteSyncedDataDialog = () => {
  deleteSyncedDataForm.value = {
    symbol: '',
    deleteDisplayCache: false
  }
  deleteDialogQueried.value = false
  syncedDataSummaryItems.value = []
  selectedSyncedDataItems.value = []
  relatedSyncHistoryRecords.value = []
  relatedSyncHistoryTotal.value = 0
  resetDeleteLinkedContext()
}

const clearDeleteLinkedFilter = async () => {
  resetDeleteLinkedContext()
  if (deleteSyncedDataForm.value.symbol.trim()) {
    await loadSyncedDataSummary()
    return
  }
  selectedSyncedDataItems.value = []
  relatedSyncHistoryRecords.value = []
  relatedSyncHistoryTotal.value = 0
}

const loadSyncedDataSummary = async (options: LinkedLookupNoticeOptions = {}) => {
  const symbol = deleteSyncedDataForm.value.symbol.trim().toUpperCase()
  if (!symbol) {
    ElMessage.warning('请输入股票代码')
    return
  }

  try {
    syncedDataSummaryLoading.value = true
    deleteDialogQueried.value = true
    const res = await stockSyncApi.getDataSummary(buildDeleteSummaryQueryParams())
    if (!res.success) {
      throw new Error(res.message || '查询失败')
    }
    syncedDataSummaryItems.value = res.data.items || []
    relatedSyncHistoryRecords.value = res.data.related_history || []
    relatedSyncHistoryTotal.value = res.data.related_history_total || 0
    await applyDeleteDialogAutoSelection()

    const hasMatchedData = syncedDataSummaryItems.value.some(item => item.exists)
    if (options.showEmptyTip && !hasMatchedData) {
      ElMessage.info('未找到与当前同步记录关联的已同步数据')
    }
  } catch (error: any) {
    console.error('加载已同步数据概览失败:', error)
    ElMessage.error(error.message || '加载已同步数据概览失败')
  } finally {
    syncedDataSummaryLoading.value = false
  }
}

const isSyncedDataRowSelectable = (row: SyncedDataSummaryItem) => row.exists

const handleSyncedDataSelectionChange = (selection: SyncedDataSummaryItem[]) => {
  selectedSyncedDataItems.value = selection
}

const formatSummaryRange = (row: SyncedDataSummaryItem) => {
  if (!row.range_start && !row.range_end) return '-'
  if (row.range_start && row.range_end) return `${row.range_start} ~ ${row.range_end}`
  return row.range_end || row.range_start || '-'
}

const openDeleteDialogFromHistoryRow = async (row: SyncHistoryRecord) => {
  const symbol = resolveHistoryRecordSymbol(row)
  if (!symbol) {
    ElMessage.warning('该同步记录未包含可用的股票代码')
    return
  }

  if (row.scope === 'batch' && row.symbol_count > 1) {
    ElMessage.warning(`该记录包含 ${row.symbol_count} 只股票，已默认带入第一只股票 ${symbol}`)
  }

  openDeleteSyncedDataDialog(symbol, buildDeleteContextFromHistoryRecord(row))
  pendingDeleteLinkedLookupTip.value = true
  await loadSyncedDataSummary({ showEmptyTip: pendingDeleteLinkedLookupTip.value })
  pendingDeleteLinkedLookupTip.value = false
}

const openHistoryDialogFromSummaryItem = async (row: SyncedDataSummaryItem) => {
  const symbol = deleteSyncedDataForm.value.symbol.trim().toUpperCase()
  if (!symbol) {
    ElMessage.warning('请先输入股票代码')
    return
  }

  await openSyncHistoryDialog(
    symbol,
    buildHistoryContextFromSummaryItem(row),
    { showEmptyTip: true }
  )
}

const handleDeleteSingleSyncedData = async (row: SyncedDataSummaryItem) => {
  const symbol = deleteSyncedDataForm.value.symbol.trim().toUpperCase()
  if (!symbol || !row.exists) {
    return
  }

  const willClearDisplayCache =
    row.delete_type === 'realtime_cache' || deleteSyncedDataForm.value.deleteDisplayCache

  try {
    await ElMessageBox.confirm(
      `确定删除 ${symbol} 的${row.delete_type_label}吗？` +
      (willClearDisplayCache && row.delete_type !== 'realtime_cache' ? ' 这次还会同时清理自选股页展示缓存。' : '') +
      ' 此操作不可恢复。',
      '删除已同步数据',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    deletingSyncedDataType.value = row.delete_type
    const res = await stockSyncApi.deleteSyncedData({
      symbol,
      delete_type: row.delete_type,
      delete_display_cache: deleteSyncedDataForm.value.deleteDisplayCache
    })

    if (!res.success) {
      throw new Error(res.message || '删除失败')
    }

    ElMessage.success(res.message || '已删除已同步数据')
    await loadSyncedDataSummary()
    await loadFavorites()
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('删除已同步数据失败:', error)
      ElMessage.error(error.message || '删除已同步数据失败')
    }
  } finally {
    deletingSyncedDataType.value = ''
  }
}

const handleDeleteSelectedSyncedData = async () => {
  const symbol = deleteSyncedDataForm.value.symbol.trim().toUpperCase()
  const deleteTypes = selectedSyncedDataItems.value.map(item => item.delete_type)
  if (!symbol || deleteTypes.length === 0) {
    ElMessage.warning('请先勾选要删除的数据类型')
    return
  }

  const labels = selectedSyncedDataItems.value.map(item => item.delete_type_label)
  const willClearDisplayCache =
    deleteSyncedDataForm.value.deleteDisplayCache && !deleteTypes.includes('realtime_cache')

  try {
    await ElMessageBox.confirm(
      `确定删除 ${symbol} 的${labels.join('、')}吗？` +
      (willClearDisplayCache ? ' 这次还会同时清理自选股页展示缓存。' : '') +
      ' 此操作不可恢复。',
      '批量删除已同步数据',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    deleteSyncedDataLoading.value = true
    const res = await stockSyncApi.deleteSyncedDataBatch({
      symbol,
      delete_types: deleteTypes,
      delete_display_cache: deleteSyncedDataForm.value.deleteDisplayCache
    })

    if (!res.success) {
      throw new Error(res.message || '删除失败')
    }

    ElMessage.success(res.message || '已批量删除已同步数据')
    await loadSyncedDataSummary()
    await loadFavorites()
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('批量删除已同步数据失败:', error)
      ElMessage.error(error.message || '批量删除已同步数据失败')
    }
  } finally {
    deleteSyncedDataLoading.value = false
  }
}

// 生命周期
onMounted(() => {
  const auth = useAuthStore()
  if (auth.isAuthenticated) {
    loadFavorites()
    loadUserTags()
  }
})
</script>

<style lang="scss" scoped>
.favorites {
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

  .action-card {
    margin-bottom: 24px;

    .action-buttons {
      display: flex;
      gap: 8px;
      justify-content: center;
    }
  }

  .sync-history-toolbar {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 16px;
  }

  .sync-history-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 16px;
  }

  .sync-section-alert {
    margin-bottom: 16px;
  }

  .sync-linked-context {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 10px 12px;
    margin-bottom: 16px;
    border-radius: 8px;
    background: var(--el-fill-color-light);
  }

  .sync-linked-context__text {
    color: var(--el-text-color-regular);
    font-size: 13px;
    line-height: 1.5;
  }

  .delete-sync-alert {
    margin-top: 8px;
  }

  .table-action-group {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .favorite-row-actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 4px 12px;
  }

  .favorite-row-actions :deep(.el-button) {
    margin-left: 0;
    min-width: auto;
    padding: 0;
  }

  .delete-sync-hint {
    margin-left: 12px;
    color: var(--el-text-color-secondary);
    font-size: 12px;
  }

  .history-meta {
    color: var(--el-text-color-secondary);
    font-size: 12px;
    line-height: 1.5;
    margin-top: 4px;
    word-break: break-all;
  }

  .history-summary {
    line-height: 1.5;
  }

  .history-error {
    color: #f56c6c;
    font-size: 12px;
    line-height: 1.5;
    margin-top: 4px;
    word-break: break-all;
  }

  .related-history-panel {
    margin-top: 16px;
    padding-top: 16px;
    border-top: 1px solid var(--el-border-color-lighter);
  }

  .related-history-panel__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 12px;
  }

  .related-history-panel__title {
    font-size: 14px;
    font-weight: 600;
    color: var(--el-text-color-primary);
  }

  .detected-market-meta {
    margin-top: 4px;
    font-size: 12px;
    color: #409eff;
  }

  /* 颜色选项样式 */
  .color-dot {
    display: inline-block;
    width: 12px;
    height: 12px;
    border: 1px solid #ddd;
    border-radius: 2px;
    margin-left: 8px;
    vertical-align: middle;
  }
  .color-option {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
  }
  .color-dot-preview {
    display: inline-block;
    width: 14px;
    height: 14px;
    border: 1px solid #ddd;
    border-radius: 2px;
    margin-left: 6px;
    vertical-align: middle;
  }

  .favorites-list-card {
    .quote-cell {
      display: flex;
      flex-direction: column;
      line-height: 1.35;
    }

    .quote-timestamp {
      margin-top: 2px;
      font-size: 12px;
      color: var(--el-text-color-secondary);
      white-space: nowrap;
    }

    .empty-state {
      padding: 40px;
      text-align: center;
    }

    .text-red {
      color: #f56c6c;
    }

    .text-green {
      color: #67c23a;
    }

    .text-red-soft {
      color: rgba(245, 108, 108, 0.7);
    }

    .text-green-soft {
      color: rgba(103, 194, 58, 0.72);
    }

    .text-muted-soft {
      color: rgba(144, 147, 153, 0.9);
    }
  }
}
</style>
