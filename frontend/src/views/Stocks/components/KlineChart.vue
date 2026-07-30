<template>
  <div class="card kline-card">
    <div class="card-header">
      <div class="section-title">
        <span>📈</span>
        <span>{{ title }}</span>
      </div>
      <div class="header-controls">
        <!-- 技术指标切换 -->
        <div class="indicator-tabs">
          <button
            v-for="ind in indicatorOptions"
            :key="ind.key"
            class="indicator-tab"
            :class="{ active: ind.key === activeIndicator }"
            @click="activeIndicator = ind.key"
          >
            {{ ind.label }}
          </button>
        </div>
        <!-- 周期切换 -->
        <div class="period-tabs">
          <button
            v-for="p in periodOptions"
            :key="p"
            class="period-tab"
            :class="{ active: p === period }"
            @click="$emit('updatePeriod', p)"
          >
            {{ p }}
          </button>
        </div>
      </div>
    </div>
    <div class="card-body">
      <div class="kline-container">
        <v-chart class="k-chart" :option="kOption" autoresize />
        <div class="kline-legend">
          <!-- 动态图例 -->
          <template v-if="activeIndicator === 'ma'">
            <div class="kline-legend-item"><span class="kline-legend-dot ma5"></span> MA5</div>
            <div class="kline-legend-item"><span class="kline-legend-dot ma20"></span> MA20</div>
          </template>
          <template v-else-if="activeIndicator === 'boll'">
            <div class="kline-legend-item"><span class="kline-legend-dot boll-up"></span> BOLL 上轨</div>
            <div class="kline-legend-item"><span class="kline-legend-dot boll-mid"></span> 中轨</div>
            <div class="kline-legend-item"><span class="kline-legend-dot boll-low"></span> 下轨</div>
          </template>
          <template v-else-if="activeIndicator === 'macd'">
            <div class="kline-legend-item"><span class="kline-legend-dot macd-dif"></span> DIF</div>
            <div class="kline-legend-item"><span class="kline-legend-dot macd-dea"></span> DEA</div>
            <div class="kline-legend-item"><span class="kline-legend-dot macd-bar"></span> MACD</div>
          </template>
          <template v-else-if="activeIndicator === 'kdj'">
            <div class="kline-legend-item"><span class="kline-legend-dot kdj-k"></span> K</div>
            <div class="kline-legend-item"><span class="kline-legend-dot kdj-d"></span> D</div>
            <div class="kline-legend-item"><span class="kline-legend-dot kdj-j"></span> J</div>
          </template>
          <template v-else-if="activeIndicator === 'rsi'">
            <div class="kline-legend-item"><span class="kline-legend-dot rsi-6"></span> RSI6</div>
            <div class="kline-legend-item"><span class="kline-legend-dot rsi-12"></span> RSI12</div>
            <div class="kline-legend-item"><span class="kline-legend-dot rsi-24"></span> RSI24</div>
          </template>
          <div class="kline-legend-item"><span class="kline-legend-dot vol"></span> 成交量</div>
          <span class="kline-meta">
            数据源：{{ klineSource || '-' }} · 最近：{{ lastKTime || '-' }} · 收：{{ fmtPrice(lastKClose) }}
          </span>
        </div>
        <div v-if="!category.length" class="kline-empty">
          <el-empty description="暂无K线数据" :image-size="80" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import VChart from 'vue-echarts'
import type { EChartsOption } from 'echarts'
import { use as echartsUse } from 'echarts/core'
import { CandlestickChart, LineChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, DataZoomComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

// 注册 K 线图所需的所有 ECharts 组件
echartsUse([
  CandlestickChart,
  LineChart,
  BarChart,
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
  LegendComponent,
  CanvasRenderer,
])

type IndicatorKey = 'ma' | 'macd' | 'kdj' | 'rsi' | 'boll'

const props = defineProps<{
  title: string
  category: string[]
  values: number[][] // [open, close, low, high]
  volumes: number[]
  period: string
  periodOptions: string[]
  klineSource?: string
  lastKTime?: string | null
  lastKClose?: number | null
}>()

defineEmits<{
  (e: 'updatePeriod', period: string): void
}>()

// 当前选中的技术指标
const activeIndicator = ref<IndicatorKey>('ma')

const indicatorOptions: { key: IndicatorKey; label: string }[] = [
  { key: 'ma', label: 'MA' },
  { key: 'macd', label: 'MACD' },
  { key: 'kdj', label: 'KDJ' },
  { key: 'rsi', label: 'RSI' },
  { key: 'boll', label: 'BOLL' },
]

function fmtPrice(v: any) {
  const n = Number(v)
  return Number.isFinite(n) ? n.toFixed(2) : '-'
}

// ════════ 技术指标计算函数 ════════

/** 移动平均线 MA */
function calcMA(data: number[][], period: number): (number | null)[] {
  const result: (number | null)[] = []
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      result.push(null)
      continue
    }
    let sum = 0
    for (let j = 0; j < period; j++) {
      sum += data[i - j][1] // 收盘价
    }
    result.push(Number((sum / period).toFixed(2)))
  }
  return result
}

/** KDJ(9,3,3) 随机指标 */
function calcKDJ(values: number[][], n = 9, m1 = 3, m2 = 3) {
  const kArr: (number | null)[] = []
  const dArr: (number | null)[] = []
  const jArr: (number | null)[] = []
  let prevK = 50, prevD = 50
  for (let i = 0; i < values.length; i++) {
    const close = values[i][1]
    const high = values[i][3]
    const low = values[i][2]
    if (i < n - 1) {
      kArr.push(null); dArr.push(null); jArr.push(null)
      continue
    }
    let hh = high, ll = low
    for (let x = 1; x < n; x++) {
      hh = Math.max(hh, values[i - x][3])
      ll = Math.min(ll, values[i - x][2])
    }
    const rsv = hh === ll ? 0 : ((close - ll) / (hh - ll)) * 100
    const curK = (2 * prevK + rsv) / m1
    const curD = (2 * prevD + curK) / m2
    const curJ = 3 * curK - 2 * curD
    kArr.push(Number(curK.toFixed(2)))
    dArr.push(Number(curD.toFixed(2)))
    jArr.push(Number(curJ.toFixed(2)))
    prevK = curK
    prevD = curD
  }
  return { k: kArr, d: dArr, j: jArr }
}

/** MACD(12,26,9) 指数平滑异同移动平均线 */
function calcMACD(values: number[][], short = 12, long = 26, m = 9) {
  const difArr: (number | null)[] = []
  const deaArr: (number | null)[] = []
  const macdArr: (number | null)[] = []
  let emaShort = 0, emaLong = 0, prevDea = 0
  for (let i = 0; i < values.length; i++) {
    const close = values[i][1]
    if (i === 0) {
      emaShort = close
      emaLong = close
    } else {
      emaShort = (close * 2 + emaShort * (short - 1)) / (short + 1)
      emaLong = (close * 2 + emaLong * (long - 1)) / (long + 1)
    }
    const curDif = emaShort - emaLong
    const curDea = i === 0 ? curDif : (curDif * 2 + prevDea * (m - 1)) / (m + 1)
    const curMacd = 2 * (curDif - curDea)
    if (i < long - 1) {
      difArr.push(null); deaArr.push(null); macdArr.push(null)
    } else {
      difArr.push(Number(curDif.toFixed(3)))
      deaArr.push(Number(curDea.toFixed(3)))
      macdArr.push(Number(curMacd.toFixed(3)))
    }
    prevDea = curDea
  }
  return { dif: difArr, dea: deaArr, macd: macdArr }
}

/** RSI(6,12,24) 相对强弱指数 */
function calcRSI(values: number[][], periods: number[] = [6, 12, 24]) {
  const closes = values.map(v => v[1])
  const result: Record<number, (number | null)[]> = {}
  for (const period of periods) {
    const rsi: (number | null)[] = []
    let avgGain = 0, avgLoss = 0
    for (let i = 0; i < closes.length; i++) {
      if (i === 0) {
        rsi.push(null)
        continue
      }
      const change = closes[i] - closes[i - 1]
      const gain = change > 0 ? change : 0
      const loss = change < 0 ? -change : 0
      if (i < period) {
        avgGain += gain
        avgLoss += loss
        rsi.push(null)
      } else if (i === period) {
        avgGain = (avgGain + gain) / period
        avgLoss = (avgLoss + loss) / period
        const rs = avgLoss === 0 ? 100 : avgGain / avgLoss
        rsi.push(Number((100 - 100 / (1 + rs)).toFixed(2)))
      } else {
        avgGain = (avgGain * (period - 1) + gain) / period
        avgLoss = (avgLoss * (period - 1) + loss) / period
        const rs = avgLoss === 0 ? 100 : avgGain / avgLoss
        rsi.push(Number((100 - 100 / (1 + rs)).toFixed(2)))
      }
    }
    result[period] = rsi
  }
  return result
}

/** BOLL(20,2) 布林带 */
function calcBOLL(values: number[][], n = 20, k = 2) {
  const up: (number | null)[] = []
  const mid: (number | null)[] = []
  const low: (number | null)[] = []
  for (let i = 0; i < values.length; i++) {
    if (i < n - 1) {
      up.push(null); mid.push(null); low.push(null)
      continue
    }
    let sum = 0
    for (let x = 0; x < n; x++) sum += values[i - x][1]
    const ma = sum / n
    let variance = 0
    for (let x = 0; x < n; x++) {
      const diff = values[i - x][1] - ma
      variance += diff * diff
    }
    const sd = Math.sqrt(variance / n)
    up.push(Number((ma + k * sd).toFixed(2)))
    mid.push(Number(ma.toFixed(2)))
    low.push(Number((ma - k * sd).toFixed(2)))
  }
  return { up, mid, low }
}

// ════════ 预计算各指标 ════════
const ma5Data = computed(() => calcMA(props.values, 5))
const ma20Data = computed(() => calcMA(props.values, 20))
const kdjData = computed(() => calcKDJ(props.values))
const macdData = computed(() => calcMACD(props.values))
const rsiData = computed(() => calcRSI(props.values))
const bollData = computed(() => calcBOLL(props.values))

// 是否有指标副图（MA 和 BOLL 叠加在主图，其他指标需要独立副图）
const hasSubChart = computed(() => activeIndicator.value === 'macd' || activeIndicator.value === 'kdj' || activeIndicator.value === 'rsi')

// ════════ ECharts option 构建 ════════
const kOption = computed<EChartsOption>(() => {
  if (!props.category.length) {
    return {
      grid: { left: 40, right: 20, top: 20, bottom: 40 },
      xAxis: { type: 'category', data: [] },
      yAxis: { type: 'value', scale: true },
      series: [],
    }
  }

  const ind = activeIndicator.value
  const hasSub = hasSubChart.value

  // 布局：主图 + 成交量 + (可选)指标副图
  // 有副图时：主图 48%, 成交量 16%, 指标 20%, dataZoom 底部
  // 无副图时：主图 62%, 成交量 18%, dataZoom 底部
  const grids: any[] = []
  const xAxes: any[] = []
  const yAxes: any[] = []
  const series: any[] = []

  if (hasSub) {
    grids.push({ left: 55, right: 20, top: 15, height: '48%' })       // 主图
    grids.push({ left: 55, right: 20, top: '68%', height: '14%' })    // 成交量
    grids.push({ left: 55, right: 20, top: '85%', height: '12%' })    // 指标副图
  } else {
    grids.push({ left: 55, right: 20, top: 15, height: '62%' })       // 主图
    grids.push({ left: 55, right: 20, top: '80%', height: '14%' })    // 成交量
  }

  const subCount = hasSub ? 3 : 2
  for (let i = 0; i < subCount; i++) {
    xAxes.push({
      type: 'category',
      data: props.category,
      boundaryGap: true,
      gridIndex: i,
      axisLine: { lineStyle: { color: '#94a3b8' } },
      axisLabel: { show: i === subCount - 1, color: '#64748b', fontSize: 11 },
    })
  }

  // 主图 Y 轴
  yAxes.push({
    scale: true,
    type: 'value',
    gridIndex: 0,
    axisLine: { lineStyle: { color: '#94a3b8' } },
    splitLine: { lineStyle: { color: '#f1f5f9' } },
    axisLabel: { color: '#64748b', fontSize: 11 },
  })
  // 成交量 Y 轴
  yAxes.push({
    scale: true,
    type: 'value',
    gridIndex: 1,
    axisLine: { show: false },
    axisTick: { show: false },
    splitLine: { show: false },
    axisLabel: {
      color: '#94a3b8',
      fontSize: 10,
      formatter: (v: number) => {
        if (v >= 1e8) return (v / 1e8).toFixed(0) + '亿'
        if (v >= 1e4) return (v / 1e4).toFixed(0) + '万'
        return String(v)
      },
    },
  })
  // 指标副图 Y 轴
  if (hasSub) {
    const indLabel: Record<string, string> = {
      macd: 'MACD',
      kdj: 'KDJ',
      rsi: 'RSI',
    }
    yAxes.push({
      scale: true,
      type: 'value',
      gridIndex: 2,
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: '#f8fafc' } },
      axisLabel: { color: '#94a3b8', fontSize: 10 },
      name: indLabel[ind] || '',
      nameTextStyle: { color: '#64748b', fontSize: 10, align: 'right', padding: [0, 0, 0, 0] },
    })
  }

  // ── 主图 series ──
  // K 线
  series.push({
    type: 'candlestick',
    name: 'K线',
    xAxisIndex: 0,
    yAxisIndex: 0,
    data: props.values,
    itemStyle: {
      color: '#ef4444',
      color0: '#16a34a',
      borderColor: '#ef4444',
      borderColor0: '#16a34a',
    },
  })

  // 主图叠加指标
  if (ind === 'ma') {
    series.push({
      type: 'line', name: 'MA5', xAxisIndex: 0, yAxisIndex: 0,
      data: ma5Data.value, smooth: true, symbol: 'none',
      lineStyle: { color: '#f59e0b', width: 1.5 },
    })
    series.push({
      type: 'line', name: 'MA20', xAxisIndex: 0, yAxisIndex: 0,
      data: ma20Data.value, smooth: true, symbol: 'none',
      lineStyle: { color: '#8b5cf6', width: 1.5 },
    })
  } else if (ind === 'boll') {
    series.push({
      type: 'line', name: 'BOLL上轨', xAxisIndex: 0, yAxisIndex: 0,
      data: bollData.value.up, symbol: 'none',
      lineStyle: { color: '#ef4444', width: 1, type: 'dashed' },
    })
    series.push({
      type: 'line', name: 'BOLL中轨', xAxisIndex: 0, yAxisIndex: 0,
      data: bollData.value.mid, symbol: 'none',
      lineStyle: { color: '#6b5ce7', width: 1.5 },
    })
    series.push({
      type: 'line', name: 'BOLL下轨', xAxisIndex: 0, yAxisIndex: 0,
      data: bollData.value.low, symbol: 'none',
      lineStyle: { color: '#16a34a', width: 1, type: 'dashed' },
    })
  }

  // ── 成交量 series ──
  series.push({
    type: 'bar',
    name: '成交量',
    xAxisIndex: 1,
    yAxisIndex: 1,
    data: props.volumes.map((v, idx) => {
      const item = props.values[idx]
      const isUp = item && item[1] >= item[0]
      return {
        value: v,
        itemStyle: { color: isUp ? '#ef4444' : '#16a34a' },
      }
    }),
  })

  // ── 指标副图 series ──
  if (ind === 'macd') {
    const m = macdData.value
    // MACD 柱状图（红绿）
    series.push({
      type: 'bar',
      name: 'MACD',
      xAxisIndex: 2,
      yAxisIndex: 2,
      data: m.macd.map(v => v === null ? null : ({
        value: v,
        itemStyle: { color: v >= 0 ? '#ef4444' : '#16a34a' },
      })),
    })
    series.push({
      type: 'line', name: 'DIF', xAxisIndex: 2, yAxisIndex: 2,
      data: m.dif, symbol: 'none',
      lineStyle: { color: '#f59e0b', width: 1.2 },
    })
    series.push({
      type: 'line', name: 'DEA', xAxisIndex: 2, yAxisIndex: 2,
      data: m.dea, symbol: 'none',
      lineStyle: { color: '#3b82f6', width: 1.2 },
    })
  } else if (ind === 'kdj') {
    const k = kdjData.value
    series.push({
      type: 'line', name: 'K', xAxisIndex: 2, yAxisIndex: 2,
      data: k.k, symbol: 'none',
      lineStyle: { color: '#3b82f6', width: 1.2 },
    })
    series.push({
      type: 'line', name: 'D', xAxisIndex: 2, yAxisIndex: 2,
      data: k.d, symbol: 'none',
      lineStyle: { color: '#f59e0b', width: 1.2 },
    })
    series.push({
      type: 'line', name: 'J', xAxisIndex: 2, yAxisIndex: 2,
      data: k.j, symbol: 'none',
      lineStyle: { color: '#8b5cf6', width: 1.2 },
    })
  } else if (ind === 'rsi') {
    const r = rsiData.value
    series.push({
      type: 'line', name: 'RSI6', xAxisIndex: 2, yAxisIndex: 2,
      data: r[6], symbol: 'none',
      lineStyle: { color: '#ef4444', width: 1.2 },
    })
    series.push({
      type: 'line', name: 'RSI12', xAxisIndex: 2, yAxisIndex: 2,
      data: r[12], symbol: 'none',
      lineStyle: { color: '#f59e0b', width: 1.2 },
    })
    series.push({
      type: 'line', name: 'RSI24', xAxisIndex: 2, yAxisIndex: 2,
      data: r[24], symbol: 'none',
      lineStyle: { color: '#8b5cf6', width: 1.2 },
    })
  }

  // tooltip
  const tooltipFormatter = (params: any) => {
    if (!Array.isArray(params) || !params.length) return ''
    const p = params[0]
    const idx = p.dataIndex
    const v = props.values[idx]
    if (!v) return p.name
    const vol = props.volumes[idx] ?? 0
    const fmt = (x: any) => (typeof x === 'number' ? x.toFixed(2) : '-')
    const lines: string[] = [
      p.name,
      `开：${fmt(v[0])} 收：${fmt(v[1])}`,
      `低：${fmt(v[2])} 高：${fmt(v[3])}`,
      `成交量：${Number(vol).toLocaleString()} 手`,
    ]
    // 追加当前指标数值
    if (ind === 'ma') {
      lines.push(`MA5：${fmt(ma5Data.value[idx])} MA20：${fmt(ma20Data.value[idx])}`)
    } else if (ind === 'boll') {
      const b = bollData.value
      lines.push(`BOLL 上：${fmt(b.up[idx])} 中：${fmt(b.mid[idx])} 下：${fmt(b.low[idx])}`)
    } else if (ind === 'macd') {
      const m = macdData.value
      lines.push(`DIF：${fmt(m.dif[idx])} DEA：${fmt(m.dea[idx])} MACD：${fmt(m.macd[idx])}`)
    } else if (ind === 'kdj') {
      const k = kdjData.value
      lines.push(`K：${fmt(k.k[idx])} D：${fmt(k.d[idx])} J：${fmt(k.j[idx])}`)
    } else if (ind === 'rsi') {
      const r = rsiData.value
      lines.push(`RSI6：${fmt(r[6][idx])} RSI12：${fmt(r[12][idx])} RSI24：${fmt(r[24][idx])}`)
    }
    return lines.join('<br/>')
  }

  const xAxisIndices = hasSub ? [0, 1, 2] : [0, 1]

  return {
    grid: grids,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      formatter: tooltipFormatter,
    },
    xAxis: xAxes,
    yAxis: yAxes,
    dataZoom: [
      { type: 'inside', xAxisIndex: xAxisIndices, start: 60, end: 100 },
      { type: 'slider', xAxisIndex: xAxisIndices, start: 60, end: 100, height: 14, bottom: 4 },
    ],
    series,
  } as EChartsOption
})
</script>

<style scoped>
.card {
  background: var(--el-bg-color, #fff);
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  border: 1px solid #f1f5f9;
  overflow: hidden;
}

.card-header {
  padding: 14px 20px;
  border-bottom: 1px solid #f1f5f9;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.section-title {
  font-size: 15px;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 8px;
  color: #1e293b;
}

.header-controls {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.indicator-tabs {
  display: flex;
  gap: 2px;
  padding: 2px;
  background: #f1f5f9;
  border-radius: 6px;
}

.indicator-tab {
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
  color: #64748b;
  border: none;
  background: transparent;
  font-family: inherit;
  font-weight: 500;
  transition: all 0.2s;
}

.indicator-tab.active {
  background: #fff;
  color: #6b5ce7;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08);
}

.indicator-tab:not(.active):hover {
  color: #6b5ce7;
}

.period-tabs {
  display: flex;
  gap: 4px;
}

.period-tab {
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  color: #64748b;
  border: 1px solid transparent;
  background: transparent;
  font-family: inherit;
}

.period-tab.active {
  background: #6b5ce7;
  color: #fff;
}

.period-tab:not(.active):hover {
  background: #f5f3ff;
  color: #6b5ce7;
}

.card-body {
  padding: 16px 20px;
}

.kline-container {
  width: 100%;
  position: relative;
}

.k-chart {
  width: 100%;
  height: 480px;
}

.kline-empty {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.kline-legend {
  display: flex;
  gap: 14px;
  align-items: center;
  margin-top: 8px;
  font-size: 11px;
  color: #94a3b8;
  flex-wrap: wrap;
}

.kline-legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.kline-legend-dot {
  width: 12px;
  height: 2px;
  border-radius: 1px;
  display: inline-block;
}

/* MA */
.kline-legend-dot.ma5 { background: #f59e0b; }
.kline-legend-dot.ma20 { background: #8b5cf6; }

/* BOLL */
.kline-legend-dot.boll-up { background: #ef4444; }
.kline-legend-dot.boll-mid { background: #6b5ce7; }
.kline-legend-dot.boll-low { background: #16a34a; }

/* MACD */
.kline-legend-dot.macd-dif { background: #f59e0b; }
.kline-legend-dot.macd-dea { background: #3b82f6; }
.kline-legend-dot.macd-bar { background: #cbd5e1; }

/* KDJ */
.kline-legend-dot.kdj-k { background: #3b82f6; }
.kline-legend-dot.kdj-d { background: #f59e0b; }
.kline-legend-dot.kdj-j { background: #8b5cf6; }

/* RSI */
.kline-legend-dot.rsi-6 { background: #ef4444; }
.kline-legend-dot.rsi-12 { background: #f59e0b; }
.kline-legend-dot.rsi-24 { background: #8b5cf6; }

/* 成交量 */
.kline-legend-dot.vol { background: #cbd5e1; }

.kline-meta {
  margin-left: auto;
}
</style>
