<template>
  <transition name="fade">
    <button
      v-show="visible"
      class="back-to-top"
      @click="scrollToTop"
      aria-label="回到顶部"
    >
      ↑
    </button>
  </transition>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

const props = withDefaults(defineProps<{
  showAfter?: number
}>(), {
  showAfter: 600,
})

const visible = ref(false)

function handleScroll() {
  visible.value = window.scrollY > props.showAfter
}

function scrollToTop() {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

onMounted(() => {
  window.addEventListener('scroll', handleScroll, { passive: true })
  handleScroll()
})

onUnmounted(() => {
  window.removeEventListener('scroll', handleScroll)
})
</script>

<style scoped>
.back-to-top {
  position: fixed;
  bottom: 30px;
  right: 30px;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: #6b5ce7;
  color: #fff;
  border: none;
  cursor: pointer;
  font-size: 18px;
  box-shadow: 0 4px 12px rgba(107, 92, 231, 0.35);
  z-index: 200;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.2s, box-shadow 0.2s;
}

.back-to-top:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(107, 92, 231, 0.45);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s, transform 0.3s;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(20px);
}
</style>
