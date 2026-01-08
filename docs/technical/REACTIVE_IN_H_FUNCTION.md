# Vue 3 响应式在 h() 函数中的正确使用

## 🎯 核心问题

**为什么在 `h()` 函数中使用 `ref.value` 不会自动更新？**

## 📚 原理解析

### 问题代码

```typescript
import { ref, h } from 'vue'

const count = ref(0)

// ❌ 这样不会响应式更新
const vnode = h('div', [
  h('button', { onClick: () => count.value++ }, '+1'),
  h('span', `Count: ${count.value}`)  // 静态内容！
])
```

**现象**：
- 点击按钮，`count.value` 确实变成了 1、2、3...
- 但是页面显示永远是 "Count: 0"

**原因**：
1. `h()` 函数创建的是 **VNode（虚拟节点）**
2. VNode 创建时，`count.value` 被**立即求值**为 `0`
3. 之后 `count.value` 改变，VNode **不会重新创建**
4. 所以页面显示不会更新

### 类比理解

```typescript
// 这就像：
const message = `Count: ${count.value}`  // message = "Count: 0"
count.value++  // count.value 变成 1
console.log(message)  // 仍然是 "Count: 0"
```

字符串模板在创建时就固定了，之后变量改变不会影响已经创建的字符串。

VNode 也是一样的道理！

## ✅ 解决方案

### 方案1：使用组件（推荐）

```typescript
import { ref, h } from 'vue'

const count = ref(0)

// ✅ 创建一个组件
const CounterComponent = {
  setup() {
    // 返回渲染函数
    return () => h('div', [
      h('button', { onClick: () => count.value++ }, '+1'),
      h('span', `Count: ${count.value}`)  // 现在是响应式的！
    ])
  }
}

// 使用组件
h(CounterComponent)
```

**为什么这样可以？**
- 组件的 `setup` 返回的是**渲染函数**（函数）
- 当响应式数据变化时，Vue 会**重新调用渲染函数**
- 每次调用都会创建新的 VNode，所以能看到最新的值

### 方案2：使用 reactive

```typescript
import { reactive, h } from 'vue'

const state = reactive({
  count: 0
})

const CounterComponent = {
  setup() {
    return () => h('div', [
      h('button', { onClick: () => state.count++ }, '+1'),
      h('span', `Count: ${state.count}`)
    ])
  }
}
```

**优点**：
- 不需要 `.value`
- 适合多个相关的值

### 方案3：使用 computed

```typescript
import { reactive, computed, h } from 'vue'

const state = reactive({
  price: 10,
  quantity: 100
})

const Component = {
  setup() {
    // 计算派生值
    const total = computed(() => state.price * state.quantity)
    
    return () => h('div', [
      h('input', {
        type: 'number',
        value: state.price,
        onInput: (e) => state.price = Number(e.target.value)
      }),
      h('input', {
        type: 'number',
        value: state.quantity,
        onInput: (e) => state.quantity = Number(e.target.value)
      }),
      h('p', `Total: ${total.value}`)  // 自动更新！
    ])
  }
}
```

## 🔍 实际案例：交易确认对话框

### 问题场景

用户在对话框中修改交易价格和数量，但是：
- 输入框的值会自动还原
- 预计金额不会更新

### 错误代码

```typescript
const tradePrice = ref(6.67)
const tradeQuantity = ref(28800)

await ElMessageBox({
  message: h('div', [
    h(ElInputNumber, {
      modelValue: tradePrice.value,
      'onUpdate:modelValue': (val) => { tradePrice.value = val }
    }),
    h(ElInputNumber, {
      modelValue: tradeQuantity.value,
      'onUpdate:modelValue': (val) => { tradeQuantity.value = val }
    }),
    h('p', `预计金额：${(tradePrice.value * tradeQuantity.value).toFixed(2)}元`)
  ])
})
```

**问题**：
- `tradePrice.value` 和 `tradeQuantity.value` 确实会改变
- 但是 `h('div', [...])` 创建的是静态 VNode
- 所以输入框显示的值不会更新

### 正确代码

```typescript
const tradeForm = reactive({
  price: 6.67,
  quantity: 28800
})

const MessageComponent = {
  setup() {
    const estimatedAmount = computed(() => {
      return (tradeForm.price * tradeForm.quantity).toFixed(2)
    })

    return () => h('div', [
      h(ElInputNumber, {
        modelValue: tradeForm.price,
        'onUpdate:modelValue': (val) => { tradeForm.price = val }
      }),
      h(ElInputNumber, {
        modelValue: tradeForm.quantity,
        'onUpdate:modelValue': (val) => { tradeForm.quantity = val }
      }),
      h('p', `预计金额：${estimatedAmount.value}元`)
    ])
  }
}

await ElMessageBox({
  message: h(MessageComponent)  // 传入组件！
})
```

**效果**：
- ✅ 修改价格，预计金额实时更新
- ✅ 修改数量，预计金额实时更新
- ✅ 输入框的值不会还原

## 📊 对比总结

| 方法 | 响应式 | 复杂度 | 适用场景 |
|------|--------|--------|----------|
| 直接 h() + ref.value | ❌ | 低 | 静态内容 |
| 组件 + ref | ✅ | 中 | 单个响应式值 |
| 组件 + reactive | ✅ | 中 | 多个相关值 |
| 组件 + computed | ✅ | 高 | 需要计算派生值 |

## 💡 记忆口诀

**在 `h()` 函数中使用响应式数据：**

1. **直接用 = 静态** ❌
   ```typescript
   h('span', count.value)  // 静态
   ```

2. **组件包 = 动态** ✅
   ```typescript
   const C = { setup() { return () => h('span', count.value) } }
   h(C)  // 响应式
   ```

3. **记住公式**：
   ```
   响应式数据 + h() = 静态 ❌
   响应式数据 + 组件 + h() = 响应式 ✅
   ```

## 🎓 深入理解

### Vue 的响应式原理

```typescript
// Vue 内部大致流程：

// 1. 创建响应式数据
const count = ref(0)

// 2. 在组件的渲染函数中使用
const Component = {
  setup() {
    return () => h('span', count.value)  // 收集依赖
  }
}

// 3. 当 count.value 改变时
count.value++

// 4. Vue 触发更新
// - 重新调用渲染函数
// - 创建新的 VNode
// - 对比新旧 VNode
// - 更新 DOM
```

### 为什么需要组件？

**组件提供了一个"容器"**：
- 在这个容器中，Vue 可以**追踪依赖**
- 当依赖变化时，Vue 知道要**重新渲染**
- 重新渲染 = 重新调用渲染函数 = 创建新的 VNode

**没有组件**：
- Vue 不知道这个 VNode 依赖了哪些响应式数据
- 所以数据变化时，Vue 不会更新这个 VNode

## 🚀 最佳实践

### 1. 在 ElMessageBox 中使用响应式数据

```typescript
// ✅ 推荐
const form = reactive({ name: '', age: 0 })

const FormComponent = {
  setup() {
    return () => h('div', [
      h('input', {
        value: form.name,
        onInput: (e) => form.name = e.target.value
      }),
      h('p', `Hello, ${form.name}!`)
    ])
  }
}

await ElMessageBox({
  message: h(FormComponent)
})
```

### 2. 在 ElDialog 中使用响应式数据

```typescript
// ✅ 推荐
const dialogVisible = ref(false)
const form = reactive({ name: '' })

// 在模板中
<el-dialog v-model="dialogVisible">
  <el-input v-model="form.name" />
  <p>Hello, {{ form.name }}!</p>
</el-dialog>
```

### 3. 在自定义渲染函数中使用响应式数据

```typescript
// ✅ 推荐
export default {
  setup() {
    const count = ref(0)
    
    return () => h('div', [
      h('button', { onClick: () => count.value++ }, '+1'),
      h('span', count.value)
    ])
  }
}
```

## 🎯 总结

1. **`h()` 函数创建的是静态 VNode**
2. **要让 VNode 响应式，必须包装成组件**
3. **组件的渲染函数会在数据变化时重新执行**
4. **使用 `reactive` 比 `ref` 更适合对象**
5. **使用 `computed` 计算派生值**

记住：**响应式数据 + 组件 = 响应式 UI** ✅

