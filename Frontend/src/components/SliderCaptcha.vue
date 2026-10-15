<template>
  <div class="slider-captcha">
    <div class="captcha-canvas-wrap">
      <canvas ref="canvasRef" width="300" height="150"></canvas>
      <div v-if="state === 'success'" class="captcha-flag success">
        <el-icon><CircleCheck /></el-icon>验证通过
      </div>
      <div v-else-if="state === 'error'" class="captcha-flag error">
        <el-icon><CircleClose /></el-icon>未对准缺口，正在刷新…
      </div>
      <button class="captcha-refresh" type="button" title="换一张" @click="loadChallenge">
        <el-icon><Refresh /></el-icon>
      </button>
      <div v-if="loading" class="captcha-loading" v-loading="true" />
    </div>
    <div class="captcha-track" :class="{ 'is-active': state === 'dragging', 'is-success': state === 'success' }">
      <div class="captcha-progress" :style="{ width: progress }" />
      <div
        class="captcha-handle"
        :style="{ left: progress }"
        @pointerdown.prevent="onPointerDown"
        @touchstart.prevent="onPointerDown"
      >
        <el-icon v-if="state === 'success'"><CircleCheck /></el-icon>
        <el-icon v-else><Right /></el-icon>
      </div>
      <span class="captcha-hint">{{ hintText }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onBeforeUnmount } from 'vue'
import { CircleCheck, CircleClose, Refresh, Right } from '@element-plus/icons-vue'

import http from '@/api/http'

const emit = defineEmits(['verified', 'expired'])

// 后端逻辑分辨率 300x150，前端等比缩放显示，坐标按比例换算
const BG_W = 300
const BG_H = 150
// 滑块拼图外接尺寸（BLOCK 44 + 上/右凸起余量 22），需与后端 _MASK_W/_MASK_H 一致
const MASK_W = 66
const MASK_H = 66

const canvasRef = ref()
const loading = ref(false)
const state = ref('idle') // idle | dragging | verifying | success | error
const challenge = ref(null)
const dragX = ref(0)

let dragging = false
let startX = 0
let startDragX = 0
let bgImage = null
let sliderImage = null

const progress = computed(() => `${(dragX.value / BG_W) * 100}%`)
const hintText = computed(() => {
  if (state.value === 'success') return '验证成功'
  if (state.value === 'dragging' || state.value === 'verifying') return ''
  return '按住滑块拖动，填充拼图完成验证'
})

async function loadImage(src) {
  return new Promise((resolve) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = () => resolve(null)
    img.src = src
  })
}

async function loadChallenge() {
  loading.value = true
  state.value = 'idle'
  dragX.value = 0
  bgImage = null
  sliderImage = null
  try {
    const data = await http.post('/captcha/new')
    challenge.value = data
    const [bg, slider] = await Promise.all([loadImage(data.background), loadImage(data.slider)])
    bgImage = bg
    sliderImage = slider
    draw()
  } catch {
    challenge.value = null
  } finally {
    loading.value = false
  }
}

function draw() {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  ctx.clearRect(0, 0, BG_W, BG_H)
  if (bgImage) ctx.drawImage(bgImage, 0, 0, BG_W, BG_H)
  if (sliderImage) {
    const y = challenge.value?.slider_y ?? 0
    ctx.drawImage(sliderImage, dragX.value, y)
  }
}

function onPointerDown(event) {
  if (state.value === 'success' || state.value === 'verifying' || !challenge.value) return
  dragging = true
  startX = event.clientX ?? event.touches?.[0]?.clientX ?? 0
  startDragX = dragX.value
  state.value = 'dragging'
  window.addEventListener('pointermove', onPointerMove)
  window.addEventListener('pointerup', onPointerUp)
  window.addEventListener('pointercancel', onPointerUp)
}

function onPointerMove(event) {
  if (!dragging) return
  const canvas = canvasRef.value
  const clientX = event.clientX ?? event.touches?.[0]?.clientX ?? 0
  const scale = canvas ? canvas.clientWidth / BG_W : 1
  const delta = (clientX - startX) / (scale || 1)
  dragX.value = Math.min(Math.max(startDragX + delta, 0), BG_W - MASK_W)
  draw()
}

async function onPointerUp() {
  if (!dragging) return
  dragging = false
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', onPointerUp)
  window.removeEventListener('pointercancel', onPointerUp)
  await verify()
}

async function verify() {
  state.value = 'verifying'
  try {
    const data = await http.post('/captcha/verify', {
      challenge_id: challenge.value.challenge_id,
      x: Math.round(dragX.value),
    })
    state.value = 'success'
    draw()
    emit('verified', data.ticket)
  } catch {
    state.value = 'error'
    emit('expired')
    setTimeout(() => loadChallenge(), 900)
  }
}

function reset() {
  loadChallenge()
}

defineExpose({ reset })

loadChallenge()

onBeforeUnmount(() => {
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', onPointerUp)
  window.removeEventListener('pointercancel', onPointerUp)
})
</script>

<style scoped>
.slider-captcha {
  width: 100%;
  user-select: none;
}

.captcha-canvas-wrap {
  position: relative;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid var(--sl-border);
  background: #f3f4f6;
}

.captcha-canvas-wrap canvas {
  display: block;
  width: 100%;
  height: auto;
  touch-action: none;
}

.captcha-refresh {
  position: absolute;
  top: 8px;
  right: 8px;
  border: none;
  cursor: pointer;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: rgba(17, 24, 39, 0.55);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
}

.captcha-flag {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 6px 12px;
  font-size: 12px;
  color: #fff;
  display: flex;
  align-items: center;
  gap: 6px;
}

.captcha-flag.success {
  background: rgba(22, 163, 74, 0.85);
}

.captcha-flag.error {
  background: rgba(220, 38, 38, 0.85);
}

.captcha-loading {
  position: absolute;
  inset: 0;
}

.captcha-track {
  position: relative;
  margin-top: 10px;
  height: 42px;
  border-radius: 10px;
  background: #eef0f5;
  border: 1px solid var(--sl-border);
  overflow: hidden;
}

.captcha-progress {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  background: rgba(79, 70, 229, 0.16);
}

.captcha-track.is-success .captcha-progress {
  background: rgba(22, 163, 74, 0.18);
}

.captcha-handle {
  position: absolute;
  top: 0;
  width: 42px;
  height: 42px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fff;
  border: 1px solid var(--sl-border);
  border-radius: 10px;
  box-shadow: 0 2px 8px rgba(31, 36, 48, 0.14);
  cursor: grab;
  color: var(--sl-primary);
  touch-action: none;
  transition: color 0.2s;
}

.captcha-track.is-success .captcha-handle {
  color: #16a34a;
}

.captcha-hint {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: var(--sl-text-sub);
  pointer-events: none;
}
</style>
