<template>
  <div class="workflow-canvas" ref="canvasRef"
       @wheel.prevent="onWheel"
       @mousedown="startPan"
       @mousemove="onPan"
       @mouseup="stopPan"
       @mouseleave="stopPan">
    <svg class="canvas-svg"
         :width="canvasWidth"
         :height="canvasHeight"
         :viewBox="`0 0 ${canvasWidth} ${canvasHeight}`"
         :style="{ transform: `scale(${zoom}) translate(${panX}px, ${panY}px)`, transformOrigin: 'top left' }">
      <!-- 网格背景 -->
      <defs>
        <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
          <path d="M 20 0 L 0 0 0 20" fill="none" stroke="var(--el-border-color-extra-light)" stroke-width="0.5"/>
        </pattern>
      </defs>
      <rect :width="canvasWidth" :height="canvasHeight" fill="url(#grid)" />

      <!-- 连接线 -->
      <g class="edges-layer">
        <g v-for="edge in edges" :key="edge.id" class="edge-group">
          <path
            :d="getEdgePath(edge)"
            class="edge-path"
            :class="{ animated: edge.animated }"
            @click="onEdgeClick(edge)"
          />
          <text v-if="edge.label" :x="getEdgeMidpoint(edge).x" :y="getEdgeMidpoint(edge).y - 8" class="edge-label">
            {{ edge.label }}
          </text>
        </g>
      </g>

      <!-- 节点 -->
      <g class="nodes-layer">
        <g v-for="node in nodes" :key="node.id"
           class="node-group"
           :transform="`translate(${node.position.x}, ${node.position.y})`"
           @mousedown.stop="startDrag($event, node)">

          <!-- 节点背景 -->
          <rect
            :width="nodeWidth"
            :height="nodeHeight"
            :rx="8"
            :ry="8"
            class="node-bg"
            :class="[`node-type-${node.type}`, { selected: selectedNodeId === node.id }]"
          />

          <!-- 节点图标 -->
          <text :x="16" :y="nodeHeight / 2 + 5" class="node-icon">
            {{ getNodeIcon(node) }}
          </text>

          <!-- 节点标签 -->
          <text :x="40" :y="nodeHeight / 2 + 5" class="node-label">
            {{ node.label }}
          </text>

          <!-- 输入连接点 -->
          <circle v-if="node.type !== 'start'" :cx="0" :cy="nodeHeight / 2" :r="6" class="connector input" />

          <!-- 输出连接点 -->
          <circle v-if="node.type !== 'end'" :cx="nodeWidth" :cy="nodeHeight / 2" :r="6" class="connector output"
                  @mousedown.stop="startConnection($event, node)" />
        </g>
      </g>

      <!-- 正在创建的连接线 -->
      <path v-if="connectingLine" :d="connectingLine" class="connecting-line" />
    </svg>

    <!-- 工具栏 -->
    <div class="canvas-toolbar">
      <el-button-group>
        <el-button size="small" @click="zoomOut" title="缩小 (滚轮下)">
          <el-icon><ZoomOut /></el-icon>
        </el-button>
        <el-button size="small" class="zoom-display" disabled>
          {{ Math.round(zoom * 100) }}%
        </el-button>
        <el-button size="small" @click="zoomIn" title="放大 (滚轮上)">
          <el-icon><ZoomIn /></el-icon>
        </el-button>
      </el-button-group>
      <el-button-group style="margin-left: 8px">
        <el-button size="small" @click="resetView" title="重置视图">
          <el-icon><Aim /></el-icon>
        </el-button>
        <el-button size="small" @click="fitToScreen" title="适应屏幕">
          <el-icon><FullScreen /></el-icon>
        </el-button>
      </el-button-group>
      <el-button-group style="margin-left: 8px">
        <el-button size="small" @click="setZoom(0.5)" :type="zoom === 0.5 ? 'primary' : 'default'">50%</el-button>
        <el-button size="small" @click="setZoom(0.75)" :type="zoom === 0.75 ? 'primary' : 'default'">75%</el-button>
        <el-button size="small" @click="setZoom(1)" :type="zoom === 1 ? 'primary' : 'default'">100%</el-button>
        <el-button size="small" @click="setZoom(1.5)" :type="zoom === 1.5 ? 'primary' : 'default'">150%</el-button>
        <el-button size="small" @click="setZoom(2)" :type="zoom === 2 ? 'primary' : 'default'">200%</el-button>
      </el-button-group>
    </div>

    <!-- 缩略图 -->
    <div class="canvas-minimap" @click="onMinimapClick">
      <svg :viewBox="`0 0 ${canvasWidth} ${canvasHeight}`">
        <!-- 可视区域 -->
        <rect :x="-panX / zoom" :y="-panY / zoom"
              :width="viewportWidth / zoom" :height="viewportHeight / zoom"
              class="viewport-rect" />
        <!-- 节点 -->
        <rect v-for="node in nodes" :key="node.id"
              :x="node.position.x" :y="node.position.y"
              :width="nodeWidth" :height="nodeHeight"
              class="minimap-node" />
      </svg>
    </div>

    <!-- 快捷键提示 -->
    <div class="canvas-help">
      <span>滚轮缩放 | 空格+拖动平移 | 点击选中</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { ZoomIn, ZoomOut, Aim, FullScreen } from '@element-plus/icons-vue'
import type { NodeDefinition, EdgeDefinition } from '@/api/workflow'

const props = defineProps<{
  nodes: NodeDefinition[]
  edges: EdgeDefinition[]
  readonly?: boolean
}>()

const emit = defineEmits<{
  (e: 'nodes-change', nodes: NodeDefinition[]): void
  (e: 'edges-change', edges: EdgeDefinition[]): void
  (e: 'node-click', node: NodeDefinition): void
}>()

// 常量
const nodeWidth = 160
const nodeHeight = 48
const canvasWidth = 3000  // 增大画布宽度
const canvasHeight = 2000 // 增大画布高度

// 状态
const canvasRef = ref<HTMLElement | null>(null)
const selectedNodeId = ref<string | null>(null)
const draggingNode = ref<NodeDefinition | null>(null)
const dragOffset = ref({ x: 0, y: 0 })
const connectingFrom = ref<NodeDefinition | null>(null)
const connectingLine = ref<string | null>(null)
const zoom = ref(1)
const panX = ref(0)
const panY = ref(0)
const isPanning = ref(false)
const panStart = ref({ x: 0, y: 0 })
const viewportWidth = ref(800)
const viewportHeight = ref(600)

// 节点图标
const nodeIcons: Record<string, string> = {
  start: '▶️',
  end: '⏹️',
  analyst: '📊',
  researcher: '🔬',
  trader: '💹',
  risk: '🛡️',
  manager: '👔',
  condition: '🔀',
  parallel: '⚡',
  merge: '🔗',
  debate: '⚔️'
}

const getNodeIcon = (node: NodeDefinition) => {
  return nodeIcons[node.type] || '📦'
}

// 边路径计算
const getEdgePath = (edge: EdgeDefinition) => {
  const sourceNode = props.nodes.find(n => n.id === edge.source)
  const targetNode = props.nodes.find(n => n.id === edge.target)
  
  if (!sourceNode || !targetNode) return ''
  
  const sx = sourceNode.position.x + nodeWidth
  const sy = sourceNode.position.y + nodeHeight / 2
  const tx = targetNode.position.x
  const ty = targetNode.position.y + nodeHeight / 2
  
  // 贝塞尔曲线
  const cx = (sx + tx) / 2
  return `M ${sx} ${sy} C ${cx} ${sy}, ${cx} ${ty}, ${tx} ${ty}`
}

const getEdgeMidpoint = (edge: EdgeDefinition) => {
  const sourceNode = props.nodes.find(n => n.id === edge.source)
  const targetNode = props.nodes.find(n => n.id === edge.target)

  if (!sourceNode || !targetNode) return { x: 0, y: 0 }

  return {
    x: (sourceNode.position.x + nodeWidth + targetNode.position.x) / 2,
    y: (sourceNode.position.y + targetNode.position.y + nodeHeight) / 2
  }
}

// 拖拽节点
const hasDragged = ref(false)
const clickedNode = ref<NodeDefinition | null>(null)

const startDrag = (event: MouseEvent, node: NodeDefinition) => {
  if (props.readonly) {
    // 只读模式下直接触发点击
    onNodeClick(node)
    return
  }

  draggingNode.value = node
  clickedNode.value = node
  hasDragged.value = false
  dragOffset.value = {
    x: event.clientX - node.position.x,
    y: event.clientY - node.position.y
  }

  window.addEventListener('mousemove', onDrag)
  window.addEventListener('mouseup', stopDrag)
}

const onDrag = (event: MouseEvent) => {
  if (!draggingNode.value) return

  hasDragged.value = true  // 标记发生了拖拽

  const newNodes = props.nodes.map(n => {
    if (n.id === draggingNode.value!.id) {
      return {
        ...n,
        position: {
          x: Math.max(0, event.clientX - dragOffset.value.x),
          y: Math.max(0, event.clientY - dragOffset.value.y)
        }
      }
    }
    return n
  })

  emit('nodes-change', newNodes)
}

const stopDrag = () => {
  console.log('stopDrag called, hasDragged:', hasDragged.value, 'clickedNode:', clickedNode.value?.id)
  // 如果没有拖拽，则视为点击事件
  if (!hasDragged.value && clickedNode.value) {
    console.log('Triggering node click from stopDrag')
    onNodeClick(clickedNode.value)
  }

  draggingNode.value = null
  clickedNode.value = null
  hasDragged.value = false
  window.removeEventListener('mousemove', onDrag)
  window.removeEventListener('mouseup', stopDrag)
}

// 创建连接
const startConnection = (event: MouseEvent, node: NodeDefinition) => {
  if (props.readonly) return

  connectingFrom.value = node
  window.addEventListener('mousemove', onConnecting)
  window.addEventListener('mouseup', stopConnection)
}

const onConnecting = (event: MouseEvent) => {
  if (!connectingFrom.value || !canvasRef.value) return

  const rect = canvasRef.value.getBoundingClientRect()
  const sx = connectingFrom.value.position.x + nodeWidth
  const sy = connectingFrom.value.position.y + nodeHeight / 2
  const tx = event.clientX - rect.left
  const ty = event.clientY - rect.top

  const cx = (sx + tx) / 2
  connectingLine.value = `M ${sx} ${sy} C ${cx} ${sy}, ${cx} ${ty}, ${tx} ${ty}`
}

const stopConnection = (event: MouseEvent) => {
  if (connectingFrom.value && canvasRef.value) {
    const rect = canvasRef.value.getBoundingClientRect()
    const x = event.clientX - rect.left
    const y = event.clientY - rect.top

    // 检查是否放在某个节点的输入连接点上
    const targetNode = props.nodes.find(n => {
      const nx = n.position.x
      const ny = n.position.y + nodeHeight / 2
      return Math.abs(x - nx) < 15 && Math.abs(y - ny) < 15 && n.id !== connectingFrom.value!.id
    })

    if (targetNode) {
      const newEdge: EdgeDefinition = {
        id: `e_${connectingFrom.value.id}_${targetNode.id}`,
        source: connectingFrom.value.id,
        target: targetNode.id
      }

      // 检查是否已存在
      const exists = props.edges.some(e => e.source === newEdge.source && e.target === newEdge.target)
      if (!exists) {
        emit('edges-change', [...props.edges, newEdge])
      }
    }
  }

  connectingFrom.value = null
  connectingLine.value = null
  window.removeEventListener('mousemove', onConnecting)
  window.removeEventListener('mouseup', stopConnection)
}

// 事件处理
const onNodeClick = (node: NodeDefinition) => {
  console.log('WorkflowCanvas onNodeClick:', node.id, node.label)
  selectedNodeId.value = node.id
  emit('node-click', node)
}

const onEdgeClick = (edge: EdgeDefinition) => {
  if (props.readonly) return

  // 删除边
  const newEdges = props.edges.filter(e => e.id !== edge.id)
  emit('edges-change', newEdges)
}

// 缩放
const zoomIn = () => {
  zoom.value = Math.min(3, zoom.value + 0.25)
}

const zoomOut = () => {
  zoom.value = Math.max(0.25, zoom.value - 0.25)
}

const setZoom = (value: number) => {
  zoom.value = value
}

const resetView = () => {
  zoom.value = 1
  panX.value = 0
  panY.value = 0
}

const fitToScreen = () => {
  if (!props.nodes.length) return

  // 计算所有节点的边界
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
  for (const node of props.nodes) {
    minX = Math.min(minX, node.position.x)
    minY = Math.min(minY, node.position.y)
    maxX = Math.max(maxX, node.position.x + nodeWidth)
    maxY = Math.max(maxY, node.position.y + nodeHeight)
  }

  // 添加边距
  const padding = 50
  minX -= padding
  minY -= padding
  maxX += padding
  maxY += padding

  // 计算适合的缩放比例
  const contentWidth = maxX - minX
  const contentHeight = maxY - minY
  const scaleX = viewportWidth.value / contentWidth
  const scaleY = viewportHeight.value / contentHeight
  zoom.value = Math.min(Math.max(0.25, Math.min(scaleX, scaleY)), 2)

  // 居中
  panX.value = -minX + (viewportWidth.value / zoom.value - contentWidth) / 2
  panY.value = -minY + (viewportHeight.value / zoom.value - contentHeight) / 2
}

// 滚轮缩放
const onWheel = (event: WheelEvent) => {
  const delta = event.deltaY > 0 ? -0.1 : 0.1
  const newZoom = Math.min(3, Math.max(0.25, zoom.value + delta))
  zoom.value = newZoom
}

// 平移
const startPan = (event: MouseEvent) => {
  // 只有按住空格键或中键才平移
  if (event.button === 1 || event.shiftKey) {
    isPanning.value = true
    panStart.value = { x: event.clientX - panX.value * zoom.value, y: event.clientY - panY.value * zoom.value }
    event.preventDefault()
  }
}

const onPan = (event: MouseEvent) => {
  if (!isPanning.value) return
  panX.value = (event.clientX - panStart.value.x) / zoom.value
  panY.value = (event.clientY - panStart.value.y) / zoom.value
}

const stopPan = () => {
  isPanning.value = false
}

// 小地图点击
const onMinimapClick = (event: MouseEvent) => {
  const target = event.currentTarget as HTMLElement
  const rect = target.getBoundingClientRect()
  const x = (event.clientX - rect.left) / rect.width * canvasWidth
  const y = (event.clientY - rect.top) / rect.height * canvasHeight
  panX.value = -(x - viewportWidth.value / zoom.value / 2)
  panY.value = -(y - viewportHeight.value / zoom.value / 2)
}

// 更新视口大小
const updateViewport = () => {
  if (canvasRef.value) {
    viewportWidth.value = canvasRef.value.clientWidth
    viewportHeight.value = canvasRef.value.clientHeight
  }
}

// 生命周期
onMounted(() => {
  updateViewport()
  window.addEventListener('resize', updateViewport)
})

onUnmounted(() => {
  window.removeEventListener('resize', updateViewport)
  window.removeEventListener('mousemove', onDrag)
  window.removeEventListener('mouseup', stopDrag)
  window.removeEventListener('mousemove', onConnecting)
  window.removeEventListener('mouseup', stopConnection)
})
</script>

<style scoped lang="scss">
.workflow-canvas {
  width: 100%;
  height: 100%;
  position: relative;
  overflow: hidden;
}

.canvas-svg {
  /* SVG 尺寸由属性控制，CSS 不限制 */
  max-width: none;
  max-height: none;
}

.edges-layer {
  .edge-path {
    fill: none;
    stroke: var(--el-border-color);
    stroke-width: 2;
    cursor: pointer;
    transition: stroke 0.2s;

    &:hover {
      stroke: var(--el-color-danger);
    }

    &.animated {
      stroke-dasharray: 5;
      animation: dash 0.5s linear infinite;
    }
  }

  .edge-label {
    font-size: 12px;
    fill: var(--el-text-color-secondary);
    text-anchor: middle;
  }
}

@keyframes dash {
  to {
    stroke-dashoffset: -10;
  }
}

.nodes-layer {
  .node-group {
    cursor: move;
  }

  .node-bg {
    fill: var(--el-bg-color-overlay);
    stroke: var(--el-border-color);
    stroke-width: 2;
    transition: all 0.2s;

    &.selected {
      stroke: var(--el-color-primary);
      stroke-width: 3;
    }

    &.node-type-start { stroke: var(--el-color-success); }
    &.node-type-end { stroke: var(--el-color-info); }
    &.node-type-analyst { stroke: var(--el-color-primary); }
    &.node-type-researcher { stroke: #9c27b0; }
    &.node-type-trader { stroke: var(--el-color-warning); }
    &.node-type-risk { stroke: var(--el-color-danger); }
    &.node-type-manager { stroke: #607d8b; }
    &.node-type-condition { stroke: #ff9800; }
    &.node-type-parallel { stroke: #00bcd4; }
    &.node-type-merge { stroke: #009688; }
    &.node-type-debate { stroke: #e91e63; }
  }

  .node-icon {
    font-size: 18px;
  }

  .node-label {
    font-size: 13px;
    fill: var(--el-text-color-primary);
  }

  .connector {
    fill: var(--el-bg-color);
    stroke: var(--el-border-color);
    stroke-width: 2;
    cursor: crosshair;
    transition: all 0.2s;

    &:hover {
      fill: var(--el-color-primary);
      stroke: var(--el-color-primary);
    }
  }
}

.connecting-line {
  fill: none;
  stroke: var(--el-color-primary);
  stroke-width: 2;
  stroke-dasharray: 5;
  animation: dash 0.5s linear infinite;
}

.canvas-toolbar {
  position: absolute;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--el-bg-color-overlay);
  border-radius: 8px;
  padding: 6px 8px;
  box-shadow: var(--el-box-shadow);
  display: flex;
  align-items: center;
  gap: 4px;
  z-index: 10;

  .zoom-display {
    min-width: 50px;
    font-weight: 500;
  }
}

.canvas-minimap {
  position: absolute;
  bottom: 20px;
  right: 20px;
  width: 180px;
  height: 120px;
  background: var(--el-bg-color-overlay);
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  padding: 8px;
  cursor: pointer;
  z-index: 10;

  svg {
    width: 100%;
    height: 100%;
  }

  .minimap-node {
    fill: var(--el-color-primary-light-7);
    stroke: var(--el-color-primary);
    stroke-width: 1;
  }

  .viewport-rect {
    fill: rgba(var(--el-color-primary-rgb), 0.1);
    stroke: var(--el-color-primary);
    stroke-width: 2;
    stroke-dasharray: 4;
  }
}

.canvas-help {
  position: absolute;
  bottom: 20px;
  left: 20px;
  background: var(--el-bg-color-overlay);
  border-radius: 6px;
  padding: 6px 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  box-shadow: var(--el-box-shadow-light);
  z-index: 10;
}
</style>

