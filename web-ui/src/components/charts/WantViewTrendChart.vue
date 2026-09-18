<script setup lang="ts">
import { computed } from 'vue'
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
  }>(),
  {
    dualAxis: false,
    connectNulls: false,
    title: '',
  },
)

const { t } = useI18n()

const chartWidth = 720
const chartHeight = 220
const topPadding = 16
const bottomPadding = 28
const leftPadding = computed(() => (props.dualAxis ? 44 : 24))
const rightPadding = computed(() => (props.dualAxis ? 48 : 24))

const hasAnyValue = computed(() =>
  props.points.some((point) => point.want !== null || point.view !== null),
)

function numericValues(picker: (point: ItemTrendPoint) => number | null) {
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
    return { min: min - 1, max: max + 1 }
  }
  return { min, max }
}

const wantRange = computed(() => buildRange(numericValues((point) => point.want)))
const viewRange = computed(() => buildRange(numericValues((point) => point.view)))
const sharedRange = computed(() =>
  buildRange(
    props.points.flatMap((point) => [point.want, point.view]).filter((value): value is number => typeof value === 'number'),
  ),
)

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
  buildPath((point) => point.want, props.dualAxis ? wantRange.value : sharedRange.value),
)
const viewPath = computed(() =>
  buildPath((point) => point.view, props.dualAxis ? viewRange.value : sharedRange.value),
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

const gridYs = computed(() =>
  [0, 1, 2, 3].map((index) => topPadding + ((chartHeight - topPadding - bottomPadding) / 4) * index),
)
</script>

<template>
  <div class="app-surface-subtle p-4">
    <div class="mb-3 flex flex-col gap-3 text-xs uppercase tracking-[0.22em] text-slate-500 sm:flex-row sm:items-center sm:justify-between">
      <span>{{ chartTitle }}</span>
      <div class="flex items-center gap-3">
        <span class="inline-flex items-center gap-1">
          <span class="h-2.5 w-2.5 rounded-full bg-sky-600" />
          {{ t('sellerSubscription.colWant') }}
        </span>
        <span class="inline-flex items-center gap-1">
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
      <svg :viewBox="`0 0 ${chartWidth} ${chartHeight}`" class="h-[220px] w-full" role="img" :aria-label="chartTitle">
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

        <path :d="wantPath" fill="none" stroke="#0284c7" stroke-width="3" stroke-linecap="round" />
        <path :d="viewPath" fill="none" stroke="#f59e0b" stroke-width="3" stroke-dasharray="8 6" stroke-linecap="round" />

        <g v-for="(point, index) in points" :key="`${point.date}-${index}`">
          <circle
            v-if="point.want !== null"
            :cx="resolveX(index)"
            :cy="resolveY(point.want, dualAxis ? wantRange : sharedRange)"
            r="4"
            fill="#0284c7"
          />
          <circle
            v-if="point.view !== null"
            :cx="resolveX(index)"
            :cy="resolveY(point.view, dualAxis ? viewRange : sharedRange)"
            r="4"
            fill="#f59e0b"
          />
          <text
            :x="resolveX(index)"
            :y="chartHeight - 8"
            text-anchor="middle"
            fill="#64748b"
            font-size="11"
          >
            {{ formatAxisDate(point.date) }}
          </text>
        </g>
      </svg>
    </div>
  </div>
</template>
