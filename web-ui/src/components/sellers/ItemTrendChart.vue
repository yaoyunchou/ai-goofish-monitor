<script setup lang="ts">
import WantViewTrendChart from '@/components/charts/WantViewTrendChart.vue'

export interface ItemTrendPoint {
  date: string
  want: number | null
  view: number | null
}

defineProps<{
  points: ItemTrendPoint[]
}>()
</script>

<template>
  <WantViewTrendChart :points="points" :dual-axis="false" :connect-nulls="false" />
</template>
