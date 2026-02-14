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
            <el-option label="主板" value="主板" />
            <el-option label="创业板" value="创业板" />
            <el-option label="科创板" value="科创板" />
            <el-option label="北交所" value="北交所" />
          </el-select>
        </el-col>

        <el-col :span="4">
          <el-select v-model="selectedExchange" placeholder="交易所" clearable>
            <el-option label="上海证券交易所" value="上海证券交易所" />
            <el-option label="深圳证券交易所" value="深圳证券交易所" />
            <el-option label="北京证券交易所" value="北京证券交易所" />
          </el-select>
        </el-col>

        <el-col :span="4">
          <el-select v-model="selectedTag" placeholder="标签" clearable>
            <el-option
              v-for="tag in userTags"
              :key="tag"
              :label="tag"
              :value="tag"
            />
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
            <!-- 只有有A股自选股时才显示同步实时行情按钮 -->
            <el-button
              v-if="hasAStocks"
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
            <!-- 批量分析按钮 -->
            <el-button
              v-if="selectedStocks.length > 0"
              type="primary"
              @click="batchAnalysis"
            >
              <el-icon><Document /></el-icon>
              批量分析 ({{ selectedStocks.length }})
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

        <el-table-column prop="current_price" label="当前价格" width="100">
          <template #default="{ row }">
            <span v-if="row.current_price !== null && row.current_price !== undefined">¥{{ formatPrice(row.current_price) }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>

        <el-table-column prop="change_percent" label="涨跌幅" width="100">
          <template #default="{ row }">
            <span
              v-if="row.change_percent !== null && row.change_percent !== undefined"
              :class="getChangeClass(row.change_percent)"
            >
              {{ formatPercent(row.change_percent) }}
            </span>
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

        <el-table-column prop="added_at" label="添加时间" width="120">
          <template #default="{ row }">
            {{ formatDate(row.added_at) }}
          </template>
        </el-table-column>

        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button
              type="text"
              size="small"
              @click="editFavorite(row)"
            >
              编辑
            </el-button>
            <!-- 只有A股显示同步按钮 -->
            <el-button
              v-if="row.market === 'A股'"
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
            <el-radio label="tushare">Tushare</el-radio>
            <el-radio label="akshare">AKShare</el-radio>
          </el-radio-group>
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

    <!-- 批量分析弹窗 -->
    <el-dialog
      v-model="batchAnalysisDialog"
      title="批量分析配置"
      width="500px"
    >
      <el-form :model="batchAnalysisForm" label-width="120px">
        <el-form-item label="分析标题">
          <el-input v-model="batchAnalysisForm.title" placeholder="请输入分析标题" />
        </el-form-item>
        <el-form-item label="分析描述">
          <el-input
            v-model="batchAnalysisForm.description"
            type="textarea"
            :rows="2"
            placeholder="请输入分析描述（可选）"
          />
        </el-form-item>
        <el-form-item label="分析深度">
          <el-select v-model="batchAnalysisForm.research_depth" placeholder="请选择分析深度">
            <el-option label="快速" value="快速" />
            <el-option label="标准" value="标准" />
            <el-option label="深度" value="深度" />
          </el-select>
        </el-form-item>
        <el-form-item label="分析师团队">
          <div class="analysts-selection">
            <el-checkbox-group v-model="batchAnalysisForm.selectedAnalysts" class="analysts-group">
              <el-checkbox :label="analyst.name" class="analyst-checkbox" v-for="analyst in analysts" :key="analyst.name" />
            </el-checkbox-group>
          </div>
        </el-form-item>
        <el-form-item label="包含情绪分析">
          <el-switch v-model="batchAnalysisForm.include_sentiment" />
        </el-form-item>
        <el-form-item label="包含风险分析">
          <el-switch v-model="batchAnalysisForm.include_risk" />
        </el-form-item>
        <el-form-item label="语言">
          <el-select v-model="batchAnalysisForm.language" placeholder="请选择语言">
            <el-option label="中文" value="zh" />
            <el-option label="英文" value="en" />
          </el-select>
        </el-form-item>
        <el-form-item label="快速分析模型">
          <el-select v-model="batchAnalysisForm.quick_analysis_model" placeholder="请选择快速分析模型（可选）" filterable>
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
                    :type="model.capability_level >= 4 ? 'danger' : model.capability_level >= 3 ? 'warning' : model.capability_level >= 2 ? 'success' : 'info'"
                    size="small"
                    effect="plain"
                  >
                    {{ model.capability_level === 1 ? '⚡基础' : model.capability_level === 2 ? '📊标准' : model.capability_level === 3 ? '🎯高级' : model.capability_level === 4 ? '🔥专业' : '👑旗舰' }}
                  </el-tag>
                  <!-- 角色标签 -->
                  <el-tag
                    v-if="model.suitable_roles?.includes('quick_analysis') || model.suitable_roles?.includes('both')"
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
        </el-form-item>
        <el-form-item label="深度分析模型">
          <el-select v-model="batchAnalysisForm.deep_analysis_model" placeholder="请选择深度分析模型（可选）" filterable>
            <el-option
              v-for="model in availableModels"
              :key="`deep-${model.provider}/${model.model_name}`"
              :label="model.model_display_name || model.model_name"
              :value="model.model_name"
            >
              <div style="display: flex; justify-content: space-between; align-items: center; gap: 8px;">
                <span style="flex: 1;">{{ model.model_display_name || model.model_name }}</span>
                <div style="display: flex; align-items: center; gap: 4px;">
                  <!-- 能力等级徽章 -->
                  <el-tag
                    v-if="model.capability_level"
                    :type="model.capability_level >= 4 ? 'danger' : model.capability_level >= 3 ? 'warning' : model.capability_level >= 2 ? 'success' : 'info'"
                    size="small"
                    effect="plain"
                  >
                    {{ model.capability_level === 1 ? '⚡基础' : model.capability_level === 2 ? '📊标准' : model.capability_level === 3 ? '🎯高级' : model.capability_level === 4 ? '🔥专业' : '👑旗舰' }}
                  </el-tag>
                  <!-- 角色标签 -->
                  <el-tag
                    v-if="model.suitable_roles?.includes('deep_analysis') || model.suitable_roles?.includes('both')"
                    type="warning"
                    size="small"
                    effect="plain"
                  >
                    🧠深度
                  </el-tag>
                  <span style="font-size: 12px; color: #909399;">{{ model.provider }}</span>
                </div>
              </div>
            </el-option>
          </el-select>
        </el-form-item>
        
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
      </el-form>

      <template #footer>
        <el-button @click="batchAnalysisDialog = false">取消</el-button>
        <el-button type="primary" @click="submitBatchAnalysis">提交分析</el-button>
      </template>
    </el-dialog>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import {
  Star,
  Search,
  Refresh,
  Plus,
  Download,
  Document
} from '@element-plus/icons-vue'
import { favoritesApi } from '@/api/favorites'
import { tagsApi } from '@/api/tags'
import { stockSyncApi } from '@/api/stockSync'
import { analysisApi } from '@/api/analysis'
import { configApi } from '@/api/config'
import { recommendModels } from '@/api/modelCapabilities'
import { normalizeMarketForAnalysis } from '@/utils/market'
import { ApiClient } from '@/api/request'
import { convertAnalystNamesToIds } from '@/constants/analysts'

import type { FavoriteItem } from '@/api/favorites'
import { useAuthStore } from '@/stores/auth'


// 颜色可选项（20种预设颜色）
const COLOR_PALETTE = [
  '#409EFF', '#1677FF', '#2F88FF', '#52C41A', '#67C23A',
  '#13C2C2', '#FA8C16', '#E6A23C', '#F56C6C', '#EB2F96',
  '#722ED1', '#8E44AD', '#00BFBF', '#1F2D3D', '#606266',
  '#909399', '#C0C4CC', '#FF7F50', '#A0CFFF', '#2C3E50'
]

const router = useRouter()

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
  dataSource: 'tushare' as 'tushare' | 'akshare',
  days: 365
})

// 单个股票同步对话框
const singleSyncDialogVisible = ref(false)
const singleSyncLoading = ref(false)
const currentSyncStock = ref({
  stock_code: '',
  stock_name: ''
})
const singleSyncForm = ref({
  syncTypes: ['realtime'],  // 默认只选中实时行情（最常用）
  dataSource: 'tushare' as 'tushare' | 'akshare',
  days: 365
})

// 批量分析弹窗相关
const batchAnalysisDialog = ref(false)
const batchAnalysisForm = ref({
  title: '自选股批量分析',
  description: '',
  research_depth: '快速',
  include_sentiment: true,
  include_risk: true,
  language: 'zh',
  quick_analysis_model: '',
  deep_analysis_model: '',
  selectedAnalysts: ['市场分析师', '基本面分析师', '新闻分析师', '社媒分析师']
})

// 模型推荐提示
const modelRecommendation = ref<{
  title: string
  message: string
  type: 'success' | 'warning' | 'info' | 'error'
  quickModel?: string
  deepModel?: string
} | null>(null)

// 分析师团队选项
const analysts = ref([
  { name: '市场分析师', description: '分析市场趋势、行业动态和宏观经济环境' },
  { name: '基本面分析师', description: '分析公司财务状况、业务模式和竞争优势' },
  { name: '新闻分析师', description: '分析相关新闻、公告和市场事件的影响' },
  { name: '社媒分析师', description: '分析社交媒体情绪、投资者心理和舆论导向' }
])

// 可用模型列表
const availableModels = ref<any[]>([])

// 添加对话框
const addDialogVisible = ref(false)
const addLoading = ref(false)
const addFormRef = ref()
const addForm = ref({
  stock_code: '',
  stock_name: '',
  market: 'A股',
  tags: [],
  notes: ''
})

// 股票代码验证器
const validateStockCode = (rule: any, value: any, callback: any) => {
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


// 计算属性
const filteredFavorites = computed<FavoriteItem[]>(() => {
  let result: FavoriteItem[] = favorites.value

  // 关键词搜索
  if (searchKeyword.value) {
    const keyword = searchKeyword.value.toLowerCase()
    result = result.filter((item: FavoriteItem) =>
      (item.stock_code && item.stock_code.toLowerCase().includes(keyword)) ||
      (item.stock_name && item.stock_name.toLowerCase().includes(keyword))
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

// 判断是否有A股自选股
const hasAStocks = computed(() => {
  return favorites.value.some(item => item.market === 'A股')
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
    const res = await favoritesApi.syncRealtime('tushare')
    const data = (res as any)?.data

    if ((res as any)?.success) {
      ElMessage.success(data?.message || `同步完成: 成功 ${data?.success_count} 只`)
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
    } else {
      userTags.value = []
      tagColorMap.value = {}
    }
  } catch (error) {
    console.error('加载标签失败:', error)
    userTags.value = []
    tagColorMap.value = {}
  }
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
  } catch (e: any) {
    console.error('保存标签失败:', e)
    ElMessage.error(e?.message || '保存失败')
  } finally {
    tagLoading.value = false
  }
}

const deleteTag = async (row: any) => {
  try {
    await ElMessageBox.confirm(`确定删除标签 ${row.name} 吗？`, '删除标签', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    tagLoading.value = true
    await tagsApi.remove(row.id)
    ElMessage.success('已删除')
    await loadTagList()
    await loadUserTags()
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
    tags: [],
    notes: ''
  }
  addDialogVisible.value = true
}

// 市场类型切换时清空股票代码和名称
const handleMarketChange = () => {
  addForm.value.stock_code = ''
  addForm.value.stock_name = ''
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
    const symbol = addForm.value.stock_code.trim()
    const market = addForm.value.market

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
    const payload = { ...addForm.value }
    const res = await favoritesApi.add(payload as any)
    if ((res as any)?.success === false) throw new Error((res as any)?.message || '添加失败')
    ElMessage.success('添加成功')
    addDialogVisible.value = false
    await loadFavorites()
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
    const payload = {
      tags: editForm.value.tags,
      notes: editForm.value.notes
    }
    const res = await favoritesApi.update(editForm.value.stock_code, payload as any)
    if ((res as any)?.success === false) throw new Error((res as any)?.message || '更新失败')
    ElMessage.success('保存成功')
    editDialogVisible.value = false
    await loadFavorites()
  } catch (error: any) {
    console.error('更新自选股失败:', error)
    ElMessage.error(error.message || '保存失败')
  } finally {
    editLoading.value = false
  }
}


const editFavorite = (row: any) => {
  editForm.value = {
    stock_code: row.stock_code,
    stock_name: row.stock_name,
    market: row.market || 'A股',
    tags: Array.isArray(row.tags) ? [...row.tags] : [],
    notes: row.notes || ''
  }
  editDialogVisible.value = true
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
      `确定要从自选股中移除 ${row.stock_name} 吗？`,
      '确认移除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    const res = await favoritesApi.remove(row.stock_code)
    if ((res as any)?.success === false) throw new Error((res as any)?.message || '移除失败')
    ElMessage.success('移除成功')
    await loadFavorites()
  } catch (e) {
    // 用户取消或失败
  }
}

const viewStockDetail = (row: any) => {
  const stockCode = row.stock_code
  if (!stockCode) return
  router.push({
    name: 'StockDetail',
    params: { code: String(stockCode).toUpperCase() }
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
          message += `✅ 历史数据: ${data.historical_sync.records || 0} 条记录\n`
        } else {
          message += `❌ 历史数据同步失败: ${data.historical_sync.error || '未知错误'}\n`
        }
      }

      if (data.financial_sync) {
        if (data.financial_sync.success) {
          message += `✅ 财务数据同步成功\n`
        } else {
          message += `❌ 财务数据同步失败: ${data.financial_sync.error || '未知错误'}\n`
        }
      }

      if (data.basic_sync) {
        if (data.basic_sync.success) {
          message += `✅ 基础数据同步成功\n`
        } else {
          message += `❌ 基础数据同步失败: ${data.basic_sync.error || '未知错误'}\n`
        }
      }

      ElMessage.success(message)
      singleSyncDialogVisible.value = false

      // 刷新列表
      await loadFavorites()
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

// 批量同步
const handleBatchSync = async () => {
  if (batchSyncForm.value.syncTypes.length === 0) {
    ElMessage.warning('请至少选择一种同步内容')
    return
  }

  batchSyncLoading.value = true
  try {
    const symbols = selectedStocks.value
      .map(stock => stock.stock_code)
      .filter((code): code is string => code !== undefined && code !== null && code.trim() !== '')

    if (symbols.length === 0) {
      ElMessage.warning('请选择有效的股票')
      batchSyncLoading.value = false
      return
    }

    const res = await stockSyncApi.syncBatch({
      symbols,
      sync_historical: batchSyncForm.value.syncTypes.includes('historical'),
      sync_financial: batchSyncForm.value.syncTypes.includes('financial'),
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

// 打开批量分析弹窗
const batchAnalysis = async () => {
  if (selectedStocks.value.length === 0) {
    ElMessage.warning('请先选择要分析的股票')
    return
  }

  // 设置默认描述
  batchAnalysisForm.value.description = `对${selectedStocks.value.length}只自选股进行批量分析`
  
  // 确保可用模型已经获取
  if (availableModels.value.length === 0) {
    await loadAvailableModels()
  }
  
  // 打开弹窗
  batchAnalysisDialog.value = true
}

// 提交批量分析任务
const submitBatchAnalysis = async () => {
  if (selectedStocks.value.length === 0) {
    ElMessage.warning('请先选择要分析的股票')
    return
  }

  try {
    // 获取选中的股票代码，过滤掉undefined值
    const stockCodes = selectedStocks.value
      .map(stock => stock.stock_code)
      .filter((code): code is string => code !== undefined && code !== null && code.trim() !== '')
    
    if (stockCodes.length === 0) {
      ElMessage.warning('请选择有效的股票')
      return
    }
    
    // 构建请求参数
    const requestParams = {
      title: batchAnalysisForm.value.title,
      description: batchAnalysisForm.value.description,
      symbols: stockCodes,
      parameters: {
        market_type: 'A股', // 默认使用A股市场，实际可以根据股票代码自动判断
        research_depth: batchAnalysisForm.value.research_depth,
        include_sentiment: batchAnalysisForm.value.include_sentiment,
        include_risk: batchAnalysisForm.value.include_risk,
        language: batchAnalysisForm.value.language,
        quick_analysis_model: batchAnalysisForm.value.quick_analysis_model,
        deep_analysis_model: batchAnalysisForm.value.deep_analysis_model,
        selected_analysts: convertAnalystNamesToIds(batchAnalysisForm.value.selectedAnalysts)
      }
    }
    
    // 输出调试信息
    console.log('批量分析请求参数:', requestParams)
    
    // 使用现有的批量分析API提交任务
    const response = await analysisApi.startBatchAnalysis(requestParams)
    
    // 输出响应信息
    console.log('批量分析响应:', response)
    
    if (response.success) {
      ElMessage.success(`批量分析任务已提交，共${stockCodes.length}只股票，正在并发执行`)
      // 关闭弹窗
      batchAnalysisDialog.value = false
      // 清空选择
      selectedStocks.value = []
    } else {
      ElMessage.error(response.message || '批量分析提交失败')
    }
  } catch (error: any) {
    console.error('批量分析失败:', error)
    ElMessage.error(error?.message || '批量分析失败')
  }
}

const getChangeClass = (changePercent: number) => {
  if (changePercent > 0) return 'text-red'
  if (changePercent < 0) return 'text-green'
  return ''
}


const formatPrice = (value: any): string => {
  const n = Number(value)
  return Number.isFinite(n) ? n.toFixed(2) : '-'
}

const formatPercent = (value: any): string => {
  const n = Number(value)
  if (!Number.isFinite(n)) return '-'
  const sign = n > 0 ? '+' : ''
  return `${sign}${n.toFixed(2)}%`
}

const formatDate = (dateStr: string) => {
  return new Date(dateStr).toLocaleDateString('zh-CN')
}

// 获取可用模型列表
const loadAvailableModels = async () => {
  try {
    const llmConfigs = await configApi.getLLMConfigs()
    availableModels.value = llmConfigs.filter((config: any) => config.enabled)
    
    // 设置默认模型（从可用模型中选择第一个适合的模型）
    if (availableModels.value.length > 0) {
      // 设置快速分析模型默认值
      const defaultQuickModel = availableModels.value.find(
        (model: any) => model.suitable_roles?.includes('quick_analysis') || model.suitable_roles?.includes('both')
      )
      if (defaultQuickModel) {
        batchAnalysisForm.value.quick_analysis_model = defaultQuickModel.model_name
      }
      
      // 设置深度分析模型默认值
      const defaultDeepModel = availableModels.value.find(
        (model: any) => model.suitable_roles?.includes('deep_analysis') || model.suitable_roles?.includes('both')
      )
      if (defaultDeepModel) {
        batchAnalysisForm.value.deep_analysis_model = defaultDeepModel.model_name
      }
    }
    
    // 检查模型适配性并提供推荐
    await checkModelSuitability()
  } catch (error) {
    console.error('获取可用模型失败:', error)
    ElMessage.error('获取可用模型失败')
  }
}

/**
 * 检查模型适配性并提供推荐
 */
async function checkModelSuitability() {
  // 将分析深度转换为标准格式
  let depthName: string = batchAnalysisForm.value.research_depth
  
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
      const depthDescriptions: Record<string, string> = {
        '快速': '快速浏览，获取基本信息',
        '标准': '标准分析，全面评估股票',
        '深度': '深度研究，挖掘投资机会'
      }
      
      const message = `${depthDescriptions[depthName] || '标准分析'}\n\n推荐模型配置：\n• 快速模型：${quickDisplayName}\n• 深度模型：${deepDisplayName}\n\n${reason}`
      
      modelRecommendation.value = {
        title: '💡 模型推荐',
        message,
        type: 'info',
        quickModel,
        deepModel
      }
      
      // 如果表单中没有选择模型，自动应用推荐模型
      if (!batchAnalysisForm.value.quick_analysis_model || !batchAnalysisForm.value.deep_analysis_model) {
        batchAnalysisForm.value.quick_analysis_model = quickModel
        batchAnalysisForm.value.deep_analysis_model = deepModel
      }
    }
  } catch (error) {
    console.error('获取模型推荐失败:', error)
  }
}

/**
 * 应用推荐的模型配置
 */
function applyRecommendedModels() {
  if (modelRecommendation.value?.quickModel && modelRecommendation.value?.deepModel) {
    batchAnalysisForm.value.quick_analysis_model = modelRecommendation.value.quickModel
    batchAnalysisForm.value.deep_analysis_model = modelRecommendation.value.deepModel
    
    // 清除推荐提示
    modelRecommendation.value = null
    
    ElMessage.success('已应用推荐的模型配置')
  }
}

/**
 * 监听分析深度变化
 */
watch(() => batchAnalysisForm.value.research_depth, () => {
  checkModelSuitability()
})

/**
 * 监听模型选择变化
 */
watch([
  () => batchAnalysisForm.value.quick_analysis_model,
  () => batchAnalysisForm.value.deep_analysis_model
], () => {
  checkModelSuitability()
})

// 生命周期
onMounted(() => {
  const auth = useAuthStore()
  if (auth.isAuthenticated) {
    loadFavorites()
    loadUserTags()
    // 获取可用模型列表
    loadAvailableModels()
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
      justify-content: flex-end;
    }
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
  }

  /* 分析师团队选择样式 */
  .analysts-selection {
    .analysts-group {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 12px;
    }
    
    .analyst-checkbox {
      margin: 0 !important;
      padding: 0 !important;
    }
  }
}
</style>
