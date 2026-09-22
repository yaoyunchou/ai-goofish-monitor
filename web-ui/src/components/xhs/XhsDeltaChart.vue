<script setup lang="ts">
const props = defineProps<{
  points: { label: string; delta: number | null; incomplete: boolean }[]
}>()

function barHeight(delta: number | null): string {
  const values = props.points
    .map((point) => point.delta)
    .filter((value): value is number => typeof value === 'number')
  if (delta === null || values.length === 0) return '0%'
  const max = Math.max(...values.map((value) => Math.abs(value)), 1)
  return `${Math.max(8, Math.round((Math.abs(delta) / max) * 100))}%`
}
</script>

<template>
  <div class="flex h-44 items-end gap-1 overflow-x-auto">
    <div
      v-for="point in points"
      :key="point.label"
      class="flex h-full min-w-8 flex-1 flex-col items-center justify-end gap-1"
    >
      <span class="text-[10px] text-muted-foreground">
        {{ point.delta === null ? '—' : point.delta }}
      </span>
      <div
        class="w-full rounded-sm"
        :class="point.incomplete ? 'bg-amber-400/80' : 'bg-rose-500/80'"
        :style="{ height: barHeight(point.delta) }"
      />
      <span class="text-[10px] text-muted-foreground">{{ point.label }}</span>
    </div>
  </div>
</template>
