<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

export interface ItemTrendPoint {
  date: string
  want: number | null
  view: number | null
}

const props = withDefaults(
  defineProps<{
    points: ItemTrendPoint[]
    dualAxis?: boolean
    connectNulls?: boolean
    title?: string
    /** 单点页可关闭「想要」系列，避免两个圆点重叠看不清 */
    showWant?: boolean
    showView?: boolean
  }>(),
  {
    dualAxis: false,
    connectNulls: false,
    title: '',
    showWant: true,
    showView: true,
  },
)

const { t } = useI18n()

const chartWidth = 720
const chartHeight = 220
const topPadding = 16
const bottomPadding = 28
// 至少保留一条曲线，避免传参写错时图表全空
const wantEnabled = computed(() => props.showWant || !props.showView)
const viewEnabled = computed(() => props.showView || !props.showWant)

const leftPadding = computed(() => (props.dualAxis ? 44 : 24))
const rightPadding = computed(() => (props.dualAxis ? 48 : 24))

const hoverIndex = ref<number | null>(null)

function hasValue(point: ItemTrendPoint | undefined) {
  if (!point) return false
  return (
    (wantEnabled.value && point.want !== null && point.want !== undefined) ||
    (viewEnabled.value && point.view !== null && point.view !== undefined)
  )
}

function seriesValue(
  point: ItemTrendPoint | null,
  picker: (point: ItemTrendPoint) => number | null | undefined,
) {
  if (!point) return null
  const value = picker(point)
  return value === null || value === undefined ? null : value
}

const hasAnyValue = computed(() => props.points.some((point) => hasValue(point)))

/** 只把有值的点纳入坐标轴范围，避免「想要 / 浏览」同为 0 时坐标轴退化成 0..1 */
function numericValues(picker: (point: ItemTrendPoint) => number | null | undefined) {
  return props.points
    .map(picker)
    .filter((value): value is number => typeof value === 'number')
}

function buildRange(values: number[]) {
  if (values.length === 0) {
    return { min: 0, max: 1 }
  }
  const min = Math.min(...values)
  const max = Math.max(...values)
  if (min === max) {
    const pad = Math.max(Math.abs(min) * 0.1, 1)
    return { min: min - pad, max: max + pad }
  }
  const pad = (max - min) * 0.08
  return { min: min - pad, max: max + pad }
}

const wantRange = computed(() => buildRange(numericValues((point) => point.want)))
const viewRange = computed(() => buildRange(numericValues((point) => point.view)))

const sharedRange = computed(() => {
  const values = props.points
    .flatMap((point) => [
      wantEnabled.value ? point.want : null,
      viewEnabled.value ? point.view : null,
    ])
    .filter((value): value is number => typeof value === 'number')
  return buildRange(values)
})

/** 单轴时每个系列共用一个量程；双轴时各用各的量程 */
const wantAxisRange = computed(() => (props.dualAxis ? wantRange.value : sharedRange.value))
const viewAxisRange = computed(() => (props.dualAxis ? viewRange.value : sharedRange.value))

function resolveX(index: number) {
  const count = props.points.length
  if (count <= 1) return chartWidth / 2
  const usableWidth = chartWidth - leftPadding.value - rightPadding.value
  return leftPadding.value + (usableWidth / (count - 1)) * index
}

function resolveY(value: number, range: { min: number; max: number }) {
  const usableHeight = chartHeight - topPadding - bottomPadding
  const span = range.max - range.min || 1
  const ratio = (value - range.min) / span
  return chartHeight - bottomPadding - ratio * usableHeight
}

function buildPath(
  getValue: (point: ItemTrendPoint) => number | null | undefined,
  range: { min: number; max: number },
) {
  let started = false
  const commands: string[] = []
  props.points.forEach((point, index) => {
    const value = getValue(point)
    if (value === null || value === undefined) {
      if (!props.connectNulls) {
        started = false
      }
      return
    }
    const prefix = started ? 'L' : 'M'
    started = true
    commands.push(`${prefix} ${resolveX(index)} ${resolveY(value, range)}`)
  })
  return commands.join(' ')
}

const wantPath = computed(() =>
  wantEnabled.value ? buildPath((point) => point.want, wantAxisRange.value) : '',
)
const viewPath = computed(() =>
  viewEnabled.value ? buildPath((point) => point.view, viewAxisRange.value) : '',
)

/** 只有一个有效点时画不出线段，单独补一个圆点 */
const wantPointCount = computed(() =>
  numericValues((point) => (wantEnabled.value ? point.want : null)).length,
)
const viewPointCount = computed(() =>
  numericValues((point) => (viewEnabled.value ? point.view : null)).length,
)

const chartTitle = computed(() => props.title || t('sellerSubscription.metricTrend'))

function formatTick(value: number) {
  const abs = Math.abs(value)
  if (abs >= 10000) return `${Math.round(value / 1000)}k`
  if (abs >= 1000) return `${(value / 1000).toFixed(1).replace(/\.0$/, '')}k`
  return String(Math.round(value))
}

function axisTicks(range: { min: number; max: number }) {
  return [0, 1, 2, 3].map((index) => {
    const ratio = index / 3
    const value = range.max - (range.max - range.min) * ratio
    const y = topPadding + ((chartHeight - topPadding - bottomPadding) / 3) * index
    return { value, y }
  })
}

function formatAxisDate(value: string) {
  if (value.length >= 10) return value.slice(5, 10)
  return value.slice(5)
}

function formatValue(value: number | null) {
  if (value === null) return t('sellerSubscription.metricEmpty')
  return value.toLocaleString()
}

/** X 轴标签过密时按步长抽稀，避免文字糊成一片 */
const dateLabelStep = computed(() => {
  const count = props.points.length
  if (count <= 8) return 1
  return Math.ceil(count / 8)
})

const gridYs = computed(() =>
  [0, 1, 2, 3].map((index) => topPadding + ((chartHeight - topPadding - bottomPadding) / 4) * index),
)

const svgRef = ref<SVGSVGElement | null>(null)

/** 最近的系列点：同一 X 上「想要」与「浏览」可能重合，取离鼠标更近的那个 */
const activePoint = computed(() => {
  const index = hoverIndex.value
  if (index === null) return null
  const point = props.points[index]
  if (!point) return null
  const x = resolveX(index)
  const wantY = wantEnabled.value ? seriesValue(point, (item) => item.want) : null
  const viewY = viewEnabled.value ? seriesValue(point, (item) => item.view) : null
  return {
    index,
    x,
    date: point.date,
    want: point.want ?? null,
    view: point.view ?? null,
    wantY: wantY === null ? null : resolveY(wantY, wantAxisRange.value),
    viewY: viewY === null ? null : resolveY(viewY, viewAxisRange.value),
  }
})

const activeY = computed(() => {
  const active = activePoint.value
  if (!active) return null
  if (active.wantY !== null && active.viewY !== null) {
    return (active.wantY + active.viewY) / 2
  }
  return active.wantY ?? active.viewY
})

function pickNearestIndex(clientX: number, clientY: number) {
  const svg = svgRef.value
  const count = props.points.length
  if (!svg || count === 0) return null
  const rect = svg.getBoundingClientRect()
  if (!rect.width) return null
  const localX = ((clientX - rect.left) / rect.width) * chartWidth
  const localY = ((clientY - rect.top) / rect.height) * chartHeight

  let best: number | null = null
  let bestScore = Number.POSITIVE_INFINITY
  for (let index = 0; index < count; index += 1) {
    const point = props.points[index]
    if (!point || !hasValue(point)) continue
    const dx = resolveX(index) - localX
    let dy = Number.POSITIVE_INFINITY
    if (wantEnabled.value && point.want !== null && point.want !== undefined) {
      dy = Math.min(dy, Math.abs(resolveY(point.want, wantAxisRange.value) - localY))
    }
    if (viewEnabled.value && point.view !== null && point.view !== undefined) {
      dy = Math.min(dy, Math.abs(resolveY(point.view, viewAxisRange.value) - localY))
    }
    if (!Number.isFinite(dy)) dy = 0
    // X 距离权重高，避免鼠标纵向移动时横向跳点
    const score = Math.abs(dx) * 2.4 + dy
    if (score < bestScore) {
      bestScore = score
      best = index
    }
  }
  return best
}

function handlePointerMove(event: PointerEvent) {
  const index = pickNearestIndex(event.clientX, event.clientY)
  if (index !== hoverIndex.value) {
    hoverIndex.value = index
  }
}

function handlePointerLeave() {
  hoverIndex.value = null
}

function handleTouch(event: TouchEvent) {
  const touch = event.touches[0]
  if (!touch) return
  const index = pickNearestIndex(touch.clientX, touch.clientY)
  if (index !== hoverIndex.value) {
    hoverIndex.value = index
  }
}

function handleFocus() {
  if (hoverIndex.value === null) {
    hoverIndex.value = firstValueIndex()
  }
}

function handleBlur() {
  hoverIndex.value = null
}

function stepHover(delta: number) {
  const count = props.points.length
  if (count === 0) return
  const current = hoverIndex.value ?? firstValueIndex()
  if (current === null) return
  let next = current
  for (let attempt = 0; attempt < count; attempt += 1) {
    next += delta
    if (next < 0 || next >= count) return
    if (hasValue(props.points[next])) break
  }
  hoverIndex.value = next
}

function firstValueIndex() {
  const index = props.points.findIndex((point) => hasValue(point))
  return index === -1 ? null : index
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'ArrowLeft') {
    event.preventDefault()
    stepHover(-1)
    return
  }
  if (event.key === 'ArrowRight') {
    event.preventDefault()
    stepHover(1)
    return
  }
  if (event.key === 'Home') {
    event.preventDefault()
    hoverIndex.value = firstValueIndex()
    return
  }
  if (event.key === 'End') {
    event.preventDefault()
    const count = props.points.length
    for (let index = count - 1; index >= 0; index -= 1) {
      if (hasValue(props.points[index])) {
        hoverIndex.value = index
        return
      }
    }
    return
  }
  if (event.key === 'Escape') {
    hoverIndex.value = null
  }
}

const tooltipWraps = computed(() => {
  const active = activePoint.value
  if (!active) return { alignLeft: false, alignTop: false }
  const xRatio = active.x / chartWidth
  const yRatio = (activeY.value ?? chartHeight / 2) / chartHeight
  return {
    alignLeft: xRatio < 0.18,
    alignTop: yRatio < 0.42,
  }
})

const activeDateRaw = computed(() => activePoint.value?.date ?? '')

function formatFullDate(value: string) {
  if (!value) return ''
  const date = value.length >= 10 ? value.slice(0, 10) : value
  const time = value.includes('T') ? value.slice(11, 16) : ''
  return time ? `${date} ${time}` : date
}
</script>

<template>
  <div class="app-surface-subtle p-4">
    <div class="mb-3 flex flex-col gap-3 text-xs uppercase tracking-[0.22em] text-slate-500 sm:flex-row sm:items-center sm:justify-between">
      <span>{{ chartTitle }}</span>
      <div class="flex items-center gap-3">
        <span v-if="wantEnabled" class="inline-flex items-center gap-1 normal-case tracking-normal">
          <span class="h-2.5 w-2.5 rounded-full bg-sky-600" />
          {{ t('sellerSubscription.colWant') }}
        </span>
        <span v-if="viewEnabled" class="inline-flex items-center gap-1 normal-case tracking-normal">
          <span class="h-2.5 w-2.5 rounded-full bg-amber-500" />
          {{ t('sellerSubscription.colView') }}
        </span>
      </div>
    </div>

    <div
      v-if="!hasAnyValue"
      class="rounded-2xl border border-dashed border-slate-200 bg-white/70 px-4 py-10 text-center text-sm text-slate-500"
    >
      {{ t('sellerSubscription.noTrend') }}
    </div>

    <div v-else>
      <div class="relative">
        <svg
          ref="svgRef"
          :viewBox="`0 0 ${chartWidth} ${chartHeight}`"
          class="h-[220px] w-full cursor-crosshair touch-none"
          role="img"
          tabindex="0"
          :aria-label="chartTitle"
          @pointermove="handlePointerMove"
          @pointerleave="handlePointerLeave"
          @touchstart.passive="handleTouch"
          @touchmove.passive="handleTouch"
          @touchend="handlePointerLeave"
          @focus="handleFocus"
          @blur="handleBlur"
          @keydown="handleKeydown"
        >
          <g>
            <line
              v-for="(y, index) in gridYs"
              :key="`grid-${index}`"
              :x1="leftPadding"
              :x2="chartWidth - rightPadding"
              :y1="y"
              :y2="y"
              stroke="#cbd5e1"
              stroke-dasharray="4 6"
            />
          </g>

          <g v-if="dualAxis">
            <text
              v-for="tick in axisTicks(wantRange)"
              :key="`want-${tick.y}`"
              :x="leftPadding - 8"
              :y="tick.y + 4"
              text-anchor="end"
              fill="#0284c7"
              font-size="10"
            >
              {{ formatTick(tick.value) }}
            </text>
            <text
              v-for="tick in axisTicks(viewRange)"
              :key="`view-${tick.y}`"
              :x="chartWidth - rightPadding + 8"
              :y="tick.y + 4"
              text-anchor="start"
              fill="#d97706"
              font-size="10"
            >
              {{ formatTick(tick.value) }}
            </text>
          </g>

          <!-- hover 时的竖向准星，明确告诉用户「当前锁定的是一天」 -->
          <line
            v-if="activePoint"
            :x1="activePoint.x"
            :x2="activePoint.x"
            :y1="topPadding - 6"
            :y2="chartHeight - bottomPadding + 6"
            stroke="#94a3b8"
            stroke-width="1"
            stroke-dasharray="3 3"
          />

          <path
            v-if="wantEnabled"
            :d="wantPath"
            fill="none"
            stroke="#0284c7"
            stroke-width="3"
            stroke-linecap="round"
          />
          <path
            v-if="viewEnabled"
            :d="viewPath"
            fill="none"
            stroke="#f59e0b"
            stroke-width="3"
            stroke-dasharray="8 6"
            stroke-linecap="round"
          />

          <g v-for="(point, index) in points" :key="`${point.date}-${index}`">
            <template v-if="wantEnabled && point.want !== null">
              <circle
                v-if="wantPointCount === 1"
                :cx="resolveX(index)"
                :cy="resolveY(point.want, wantAxisRange)"
                r="4"
                fill="#0284c7"
              />
              <circle
                :cx="resolveX(index)"
                :cy="resolveY(point.want, wantAxisRange)"
                :r="hoverIndex === index ? 7 : 5"
                :fill="hoverIndex === index ? '#0284c7' : '#ffffff'"
                stroke="#0284c7"
                stroke-width="2.5"
              />
            </template>
            <template v-if="viewEnabled && point.view !== null">
              <circle
                v-if="viewPointCount === 1"
                :cx="resolveX(index)"
                :cy="resolveY(point.view, viewAxisRange)"
                r="4"
                fill="#f59e0b"
              />
              <circle
                :cx="resolveX(index)"
                :cy="resolveY(point.view, viewAxisRange)"
                :r="hoverIndex === index ? 7 : 5"
                :fill="hoverIndex === index ? '#f59e0b' : '#ffffff'"
                stroke="#f59e0b"
                stroke-width="2.5"
              />
            </template>
            <text
              v-if="index % dateLabelStep === 0"
              :x="resolveX(index)"
              :y="chartHeight - 8"
              text-anchor="middle"
              :fill="hoverIndex === index ? '#0f172a' : '#64748b'"
              font-size="11"
            >
              {{ formatAxisDate(point.date) }}
            </text>
          </g>
        </svg>

        <div
          v-if="activePoint"
          data-testid="trend-tooltip"
          class="pointer-events-none absolute z-10 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow-lg"
          :style="{
            left: tooltipWraps.alignLeft ? '8px' : `calc(${(activePoint.x / chartWidth) * 100}% )`,
            top: `${((activeY ?? chartHeight / 2) / chartHeight) * 100}%`,
            transform: `translate(${tooltipWraps.alignLeft ? '0' : '-50%'}, ${tooltipWraps.alignTop ? '8px' : 'calc(-100% - 8px)'})`,
            minWidth: '176px',
          }"
        >
          <p class="mb-1 font-medium text-slate-700">{{ formatFullDate(activeDateRaw) }}</p>
          <p v-if="wantEnabled" class="flex items-center justify-between gap-4 text-slate-600">
            <span class="inline-flex items-center gap-1.5">
              <span class="h-2 w-2 rounded-full bg-sky-600" />
              {{ t('sellerSubscription.colWant') }}
            </span>
            <span class="font-semibold text-slate-900">{{ formatValue(activePoint.want) }}</span>
          </p>
          <p v-if="viewEnabled" class="flex items-center justify-between gap-4 text-slate-600">
            <span class="inline-flex items-center gap-1.5">
              <span class="h-2 w-2 rounded-full bg-amber-500" />
              {{ t('sellerSubscription.colView') }}
            </span>
            <span class="font-semibold text-slate-900">{{ formatValue(activePoint.view) }}</span>
          </p>
        </div>
      </div>

      <p class="mt-2 text-[11px] text-slate-400">{{ t('sellerSubscription.trendHoverHint') }}</p>
    </div>
  </div>
</template>
