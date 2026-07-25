<template>
  <div class="card kline-card">
    <div class="card-header">
      <div class="section-title">
        <span>📈</span>
        <span>{{ title }}</span>
      </div>
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
    <div class="card-body">
      <div class="kline-container">
        <v-chart class="k-chart" :option="kOption" autoresize />
        <div class="kline-legend">
          <div class="kline-legend-item">
            <span class="kline-legend-dot ma5"></span> MA5
          </div>
          <div class="kline-legend-item">
            <span class="kline-legend-dot ma20"></span> MA20
          </div>
          <div class="kline-legend-item">
            <span class="kline-legend-dot vol"></span> 成交量
          </div>
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
import { computed } from 'vue'
import VChart from 'vue-echarts'
import type { EChartsOption } from 'echarts'
import { use as echartsUse } from 'echarts/core'
import { CandlestickChart, LineChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, DataZoomComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

// 注册 K 线图所需的所有 ECharts 组件（含 MA 均线 + 成交量柱状图）
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

function fmtPrice(v: any) {
  const n = Number(v)
  return Number.isFinite(n) ? n.toFixed(2) : '-'
}

// 计算移动平均线
function calcMA(data: number[][], period: number): (number | string)[] {
  const result: (number | string)[] = []
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      result.push('-')
      continue
    }
    let sum = 0
    for (let j = 0; j < period; j++) {
      // 收盘价是 values[i][1]
      sum += data[i - j][1]
    }
    result.push(Number((sum / period).toFixed(2)))
  }
  return result
}

const ma5Data = computed(() => calcMA(props.values, 5))
const ma20Data = computed(() => calcMA(props.values, 20))

const kOption = computed<EChartsOption>(() => {
  if (!props.category.length) {
    return {
      grid: { left: 40, right: 20, top: 20, bottom: 40 },
      xAxis: { type: 'category', data: [] },
      yAxis: { type: 'value', scale: true },
      series: [],
    }
  }

  return {
    grid: [
      { left: 50, right: 20, top: 20, height: '60%' },
      { left: 50, right: 20, top: '72%', height: '18%' },
    ],
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      formatter: (params: any) => {
        if (!Array.isArray(params) || !params.length) return ''
        const p = params[0]
        const idx = p.dataIndex
        const v = props.values[idx]
        if (!v) return p.name
        const vol = props.volumes[idx] ?? 0
        const ma5 = ma5Data.value[idx]
        const ma20 = ma20Data.value[idx]
        const fmt = (x: any) => (typeof x === 'number' ? x.toFixed(2) : '-')
        return [
          p.name,
          `开：${fmt(v[0])} 收：${fmt(v[1])}`,
          `低：${fmt(v[2])} 高：${fmt(v[3])}`,
          `成交量：${Number(vol).toLocaleString()} 手`,
          `MA5：${fmt(ma5)} MA20：${fmt(ma20)}`,
        ].join('<br/>')
      },
    },
    xAxis: [
      {
        type: 'category',
        data: props.category,
        boundaryGap: true,
        axisLine: { lineStyle: { color: '#94a3b8' } },
        axisLabel: { color: '#64748b', fontSize: 11 },
        gridIndex: 0,
      },
      {
        type: 'category',
        data: props.category,
        boundaryGap: true,
        axisLine: { lineStyle: { color: '#94a3b8' } },
        axisLabel: { show: false },
        gridIndex: 1,
      },
    ],
    yAxis: [
      {
        scale: true,
        type: 'value',
        gridIndex: 0,
        axisLine: { lineStyle: { color: '#94a3b8' } },
        splitLine: { lineStyle: { color: '#f1f5f9' } },
        axisLabel: { color: '#64748b', fontSize: 11 },
      },
      {
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
      },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 60, end: 100 },
      { type: 'slider', xAxisIndex: [0, 1], start: 60, end: 100, height: 14, bottom: 4 },
    ],
    series: [
      {
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
      },
      {
        type: 'line',
        name: 'MA5',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: ma5Data.value,
        smooth: true,
        lineStyle: { color: '#f59e0b', width: 1.5 },
        symbol: 'none',
      },
      {
        type: 'line',
        name: 'MA20',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: ma20Data.value,
        smooth: true,
        lineStyle: { color: '#8b5cf6', width: 1.5 },
        symbol: 'none',
      },
      {
        type: 'bar',
        name: '成交量',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: props.volumes.map((v, idx) => {
          const item = props.values[idx]
          // 涨红跌绿（item[1]收盘 >= item[0]开盘 为涨）
          const isUp = item && item[1] >= item[0]
          return {
            value: v,
            itemStyle: { color: isUp ? '#ef4444' : '#16a34a' },
          }
        }),
      },
    ],
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
}

.section-title {
  font-size: 15px;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 8px;
  color: #1e293b;
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
  height: 400px;
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
  gap: 16px;
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
}

.kline-legend-dot.ma5 {
  background: #f59e0b;
}

.kline-legend-dot.ma20 {
  background: #8b5cf6;
}

.kline-legend-dot.vol {
  background: #cbd5e1;
}

.kline-meta {
  margin-left: auto;
}
</style>
