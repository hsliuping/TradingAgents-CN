<template>
  <div class="favorites">
    <div class="page-header">
      <h1 class="page-title">
        <el-icon><Star /></el-icon>
        股票关注列表
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
          </el-select>
        </el-col>

        <el-col :span="4">
          <el-select v-model="selectedBoard" placeholder="板块" clearable>
            <el-option label="主板" value="主板" />
            <el-option label="创业板" value="创业板" />
            <el-option label="科创板" value="科创板" />
            <el-option label="北交所" value="北交所" />
            <el-option label="ETF" value="ETF" />
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
            <!-- 只有有A股股票关注列表时才显示同步实时行情按钮 -->
            <el-button
              v-if="hasAStocks"
              type="success"
              @click="syncAllRealtime"
              :loading="syncRealtimeLoading"
            >
              <el-icon><Refresh /></el-icon>
              同步实时行情
            </el-button>
            <!-- 批量同步按钮始终显示 -->
            <el-button
              type="primary"
              @click="showBatchSyncDialog"
            >
              <el-icon><Download /></el-icon>
              批量同步数据
            </el-button>
            <el-button @click="openTagManager">
              标签管理
            </el-button>
            <el-button type="primary" @click="showAddDialog">
              <el-icon><Plus /></el-icon>
              添加
            </el-button>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 股票关注列表列表 -->
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
        <el-empty description="暂无股票关注列表">
          <el-button type="primary" @click="showAddDialog">
            添加第一只股票关注列表
          </el-button>
        </el-empty>
      </div>
    </el-card>

    <!-- 添加到研究列表对话框 -->
    <el-dialog
      v-model="addDialogVisible"
      title="添加到研究列表"
      width="500px"
    >
      <el-form :model="addForm" :rules="addRules" ref="addFormRef" label-width="100px">
        <el-form-item label="市场类型" prop="market">
          <el-select v-model="addForm.market" @change="handleMarketChange">
            <el-option label="A股" value="A股" />
          </el-select>
        </el-form-item>

        <el-form-item label="股票代码" prop="stock_code">
          <el-autocomplete
            v-model="addForm.stock_code"
            :fetch-suggestions="searchStocks"
            placeholder="输入股票代码或名称搜索，如：000001 或 平安银行"
            clearable
            class="w-full"
            value-key="code"
            :debounce="300"
            @select="handleStockSelect"
            @blur="fetchStockInfo"
          >
            <template #default="{ item }">
              <div style="display: flex; justify-content: space-between; align-items: center; padding: 5px 0;">
                <span style="font-weight: 600; color: #303133;">{{ item.code }}</span>
                <span style="color: #606266; font-size: 13px;">{{ item.name }}</span>
              </div>
            </template>
          </el-autocomplete>
          <div style="font-size: 12px; color: #909399; margin-top: 4px;">
            支持股票代码或名称搜索，选择后自动填充
          </div>
        </el-form-item>

        <el-form-item label="股票名称" prop="stock_name">
          <el-input v-model="addForm.stock_name" placeholder="股票名称" />
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
    <!-- 编辑股票关注列表对话框 -->
    <el-dialog
      v-model="editDialogVisible"
      title="编辑股票关注列表"
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
        <template v-if="syncAllStocks">
          将同步研究列表中所有 <strong>{{ favorites.filter(item => item.market === 'A股').length }}</strong> 只A股股票
        </template>
        <template v-else>
          已选择 <strong>{{ selectedStocks.length }}</strong> 只股票
        </template>
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
            <el-radio label="tushare" :disabled="!availableSyncSources.tushare">Tushare</el-radio>
            <el-radio label="akshare" :disabled="!availableSyncSources.akshare">AKShare</el-radio>
            <el-radio v-if="!isJdyunMode()" label="qmt" :disabled="!availableSyncSources.qmt">QMT</el-radio>
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
        <el-button @click="batchSyncDialogVisible = false; syncAllStocks = false">取消</el-button>
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
            <el-radio label="tushare" :disabled="!availableSyncSources.tushare">Tushare</el-radio>
            <el-radio label="akshare" :disabled="!availableSyncSources.akshare">AKShare</el-radio>
            <el-radio v-if="!isJdyunMode()" label="qmt" :disabled="!availableSyncSources.qmt">QMT</el-radio>
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

  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import { isJdyunMode } from '@/utils/config'
import request from '@/api/request'
import {
  Star,
  Search,
  Refresh,
  Plus,
  Download
} from '@element-plus/icons-vue'
import { favoritesApi } from '@/api/favorites'
import { tagsApi } from '@/api/tags'
import {
  stockSyncApi,
  type BatchStockSyncResponse,
  type SingleStockSyncResponse,
  type StockSyncTaskStatus,
} from '@/api/stockSync'
import { loadManualSyncSourceState, type ManualSyncDataSource } from '@/utils/dataSource'
import { normalizeMarketForAnalysis } from '@/utils/market'
import { ApiClient } from '@/api/request'

import type { FavoriteItem, FavoritesRealtimeSyncTaskStatus } from '@/api/favorites'
import { useAuthStore } from '@/stores/auth'


// 颜色可选项（20种预设颜色）
const COLOR_PALETTE = [
  '#409EFF', '#1677FF', '#2F88FF', '#52C41A', '#67C23A',
  '#13C2C2', '#FA8C16', '#E6A23C', '#F56C6C', '#EB2F96',
  '#722ED1', '#8E44AD', '#00BFBF', '#1F2D3D', '#606266',
  '#909399', '#C0C4CC', '#FF7F50', '#A0CFFF', '#2C3E50'
]

const router = useRouter()
const STOCK_SYNC_POLL_INTERVAL_MS = 2000
const STOCK_SYNC_POLL_MAX_ATTEMPTS = 300
let favoritesViewDisposed = false

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
const syncAllStocks = ref(false)  // 标记是否同步所有A股股票
const availableSyncSources = ref<Record<ManualSyncDataSource, boolean>>({
  tushare: true,
  akshare: true,
  qmt: true
})
const batchSyncForm = ref({
  syncTypes: ['historical', 'financial'],
  dataSource: 'tushare' as ManualSyncDataSource,
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
  dataSource: 'tushare' as ManualSyncDataSource,
  days: 365
})

const loadPreferredAvailableSyncSource = async (): Promise<ManualSyncDataSource | null> => {
  try {
    const sourceState = await loadManualSyncSourceState()
    availableSyncSources.value = sourceState.availableSources
    return sourceState.preferredSource
  } catch (error) {
    console.warn('加载可用同步数据源失败，保留当前默认值', error)
    return null
  }
}

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

const addRules = {
  market: [
    { required: true, message: '请选择市场类型', trigger: 'change' }
  ],
  stock_code: [
    { required: true, message: '请选择或输入股票代码', trigger: 'blur' }
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
      String(item.stock_code || item.symbol || '').toLowerCase().includes(keyword) ||
      item.stock_name.toLowerCase().includes(keyword)
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

// 判断是否有A股股票关注列表
const hasAStocks = computed(() => {
  return favorites.value.some(item => item.market === 'A股')
})

// 方法
const loadFavorites = async () => {
  loading.value = true
  try {
    const res = await favoritesApi.list()
    favorites.value = ((res as any)?.data || []) as FavoriteItem[]
  } catch (error: any) {
    console.error('加载股票关注列表失败:', error)
    ElMessage.error(error.message || '加载股票关注列表失败')
  } finally {
    loading.value = false
  }
}

// 同步实时行情
const syncRealtimeLoading = ref(false)
const waitForFavoritesRealtimeTask = async (taskId: string): Promise<FavoritesRealtimeSyncTaskStatus> => {
  for (let attempt = 0; attempt < STOCK_SYNC_POLL_MAX_ATTEMPTS; attempt += 1) {
    if (favoritesViewDisposed) {
      throw new Error('页面已离开，停止等待同步结果')
    }

    const res = await favoritesApi.getRealtimeSyncTaskStatus(taskId)
    if (res.success && ['success', 'success_with_errors', 'failed'].includes(res.data.status)) {
      return res.data
    }

    await sleep(STOCK_SYNC_POLL_INTERVAL_MS)
  }

  throw new Error('股票关注列表实时行情同步超时，请稍后刷新列表查看结果')
}

const monitorFavoritesRealtimeTask = async (taskId: string) => {
  try {
    const task = await waitForFavoritesRealtimeTask(taskId)
    if (favoritesViewDisposed) return

    const message = task.result?.message || task.error || task.message || '股票关注列表实时行情同步失败'
    if (task.status === 'success') {
      ElMessage.success(message)
    } else if (task.status === 'success_with_errors') {
      ElMessage.warning(message)
    } else {
      ElMessage.error(message)
    }

    await loadFavorites()
  } catch (error: any) {
    if (!favoritesViewDisposed && error?.message !== '页面已离开，停止等待同步结果') {
      ElMessage.error(error?.message || '股票关注列表实时行情结果查询失败，请稍后刷新列表查看')
    }
  }
}

const syncAllRealtime = async () => {
  if (favorites.value.length === 0) {
    ElMessage.warning('没有股票关注列表需要同步')
    return
  }

  syncRealtimeLoading.value = true
  try {
    const preferredSource = await loadPreferredAvailableSyncSource()
    const realtimeSource = preferredSource || (!isJdyunMode() && availableSyncSources.value.qmt ? 'qmt' : availableSyncSources.value.akshare ? 'akshare' : 'tushare')
    const res = await favoritesApi.syncRealtime(realtimeSource)

    if ((res as any)?.success) {
      ElMessage.success('股票关注列表实时行情同步任务已提交，后台执行中')
      void monitorFavoritesRealtimeTask(res.data.task_id)
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

// 搜索股票（支持代码和名称）
// 注意：不能声明为 async——el-autocomplete 的 fetch-suggestions 要求同步返回
// void 的函数签名，async 函数返回 Promise<void> 会触发 vue-tsc 类型错误
const searchStocks = (queryString: string, cb: (results: any[]) => void) => {
  const q = queryString?.trim()
  if (!q || q.length < 1) {
    cb([])
    return
  }
  // 正确路径是 /api/markets/CN/stocks/search
  request
    .get(`/api/markets/CN/stocks/search`, { params: { q, limit: 20 } })
    .then((res: any) => {
      const stocks = res?.data?.stocks || []
      cb(stocks.map((s: any) => ({
        value: s.code || s.symbol || '',
        code: s.code || s.symbol || '',
        name: s.name || '',
      })))
    })
    .catch((err: any) => {
      console.error('搜索失败:', err)
      cb([])
    })
}

// 选择搜索结果后自动填充
const handleStockSelect = (item: any) => {
  console.log('选中项:', item)
  // el-autocomplete 会自动把 item.value 填到 v-model，只需填 name
  addForm.value.stock_name = item.name
  addFormRef.value?.clearValidate()
}

const fetchStockInfo = async () => {
  if (!addForm.value.stock_code) return

  try {
    const symbol = addForm.value.stock_code.trim()
    const market = addForm.value.market

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
    console.error('添加到研究列表失败:', error)
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
    console.error('更新股票关注列表失败:', error)
    ElMessage.error(error.message || '保存失败')
  } finally {
    editLoading.value = false
  }
}


const editFavorite = (row: any) => {
  editForm.value = {
    stock_code: row.stock_code || row.symbol || '',
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
      `确定要从股票关注列表中移除 ${row.stock_name} 吗？`,
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
    stock_code: row.stock_code || row.symbol || '',
    stock_name: row.stock_name || ''
  }
  void loadPreferredAvailableSyncSource().then(preferredSource => {
    if (preferredSource) {
      singleSyncForm.value.dataSource = preferredSource
    }
  })
  singleSyncDialogVisible.value = true
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
    parts.push(result.realtime_sync.success ? '实时行情同步成功' : `实时行情同步失败: ${result.realtime_sync.error || '未知错误'}`)
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

const buildBatchSyncTaskMessage = (task: StockSyncTaskStatus, symbols: string[]): string => {
  const result = task.result as BatchStockSyncResponse | null | undefined
  if (!result) {
    return task.error || task.message || '批量同步失败'
  }

  const parts = [`批量同步完成（共 ${symbols.length} 只股票）`]

  if (result.historical_sync) {
    parts.push(`历史数据 ${result.historical_sync.success_count}/${result.historical_sync.success_count + result.historical_sync.error_count} 成功，共 ${result.historical_sync.total_records} 条`)
  }
  if (result.financial_sync) {
    parts.push(`财务数据 ${result.financial_sync.success_count}/${result.financial_sync.total_symbols} 成功`)
  }
  if (result.basic_sync) {
    parts.push(`基础数据 ${result.basic_sync.success_count}/${result.basic_sync.total_symbols} 成功`)
  }

  return parts.join('；')
}

const waitForStockSyncTask = async (taskId: string): Promise<StockSyncTaskStatus> => {
  for (let attempt = 0; attempt < STOCK_SYNC_POLL_MAX_ATTEMPTS; attempt += 1) {
    if (favoritesViewDisposed) {
      throw new Error('页面已离开，停止等待同步结果')
    }

    const res = await stockSyncApi.getTaskStatus(taskId)
    if (res.success && isTerminalStockSyncStatus(res.data.status)) {
      return res.data
    }

    await sleep(STOCK_SYNC_POLL_INTERVAL_MS)
  }

  throw new Error('同步任务执行超时，请稍后刷新列表查看结果')
}

const monitorSingleSyncTask = async (taskId: string, symbol: string) => {
  try {
    const task = await waitForStockSyncTask(taskId)
    if (favoritesViewDisposed) return

    const message = buildSingleSyncTaskMessage(task, symbol)
    if (task.status === 'success') {
      ElMessage.success(message)
    } else if (task.status === 'success_with_errors') {
      ElMessage.warning(message)
    } else {
      ElMessage.error(message)
    }

    await loadFavorites()
  } catch (error: any) {
    if (!favoritesViewDisposed && error?.message !== '页面已离开，停止等待同步结果') {
      ElMessage.error(error?.message || '同步结果查询失败，请稍后刷新列表查看')
    }
  }
}

const monitorBatchSyncTask = async (taskId: string, symbols: string[]) => {
  try {
    const task = await waitForStockSyncTask(taskId)
    if (favoritesViewDisposed) return

    const message = buildBatchSyncTaskMessage(task, symbols)
    if (task.status === 'success') {
      ElMessage.success(message)
    } else if (task.status === 'success_with_errors') {
      ElMessage.warning(message)
    } else {
      ElMessage.error(message)
    }

    await loadFavorites()
  } catch (error: any) {
    if (!favoritesViewDisposed && error?.message !== '页面已离开，停止等待同步结果') {
      ElMessage.error(error?.message || '批量同步结果查询失败，请稍后刷新列表查看')
    }
  }
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
      ElMessage.success(`股票 ${currentSyncStock.value.stock_code} 同步任务已提交，后台执行中`)
      singleSyncDialogVisible.value = false
      void monitorSingleSyncTask(res.data.task_id, currentSyncStock.value.stock_code)
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
const showBatchSyncDialog = async () => {
  const applyPreferredSource = async () => {
    const preferredSource = await loadPreferredAvailableSyncSource()
    if (preferredSource) {
      batchSyncForm.value.dataSource = preferredSource
    }
  }

  if (selectedStocks.value.length === 0) {
    // 提示用户选择股票或全部同步
    try {
      await ElMessageBox.confirm(
        '请先选择要同步的股票，或者选择"全部同步"来同步研究列表中所有A股股票。',
        '提示',
        {
          confirmButtonText: '全部同步',
          cancelButtonText: '取消',
          type: 'info',
          distinguishCancelAndClose: true
        }
      )
      // 用户选择"全部同步"：同步研究列表中所有A股股票
      const aStocks = favorites.value.filter(item => item.market === 'A股')
      if (aStocks.length === 0) {
        ElMessage.warning('研究列表中没有A股股票可以同步')
        return
      }
      syncAllStocks.value = true  // 标记为全部同步
      await applyPreferredSource()
      batchSyncDialogVisible.value = true
    } catch (action: any) {
      // 用户选择"取消"，不做任何操作
      if (action === 'cancel') {
        return
      }
    }
  } else {
    syncAllStocks.value = false  // 标记为选中同步
    await applyPreferredSource()
    batchSyncDialogVisible.value = true
  }
}

// 执行批量同步
const handleBatchSync = async () => {
  if (batchSyncForm.value.syncTypes.length === 0) {
    ElMessage.warning('请至少选择一种同步内容')
    return
  }

  // 根据 syncAllStocks 标记决定同步哪些股票
  let symbols: string[]
  if (syncAllStocks.value) {
    // 全部同步：使用所有A股股票
    const aStocks = favorites.value.filter(item => item.market === 'A股')
    if (aStocks.length === 0) {
      ElMessage.warning('没有A股股票可以同步')
      return
    }
    symbols = aStocks.map(stock => stock.stock_code || stock.symbol || '').filter((symbol): symbol is string => Boolean(symbol))
  } else {
    // 选中同步：使用选中的股票
    if (selectedStocks.value.length === 0) {
      ElMessage.warning('请先选择要同步的股票')
      return
    }
    symbols = selectedStocks.value.map(stock => stock.stock_code || stock.symbol || '').filter((symbol): symbol is string => Boolean(symbol))
  }

  batchSyncLoading.value = true
  try {

    const res = await stockSyncApi.syncBatch({
      symbols,
      sync_historical: batchSyncForm.value.syncTypes.includes('historical'),
      sync_financial: batchSyncForm.value.syncTypes.includes('financial'),
      data_source: batchSyncForm.value.dataSource,
      days: batchSyncForm.value.days
    })

    if (res.success) {
      ElMessage.success(`批量同步任务已提交（共 ${symbols.length} 只股票），后台执行中`)
      batchSyncDialogVisible.value = false
      syncAllStocks.value = false  // 重置全部同步标记
      void monitorBatchSyncTask(res.data.task_id, symbols)
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

// 生命周期
onMounted(() => {
  const auth = useAuthStore()
  if (auth.isAuthenticated) {
    loadFavorites()
    loadUserTags()
  }
})

onUnmounted(() => {
  favoritesViewDisposed = true
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
}
</style>
