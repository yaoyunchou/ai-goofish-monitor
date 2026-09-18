<script setup lang="ts">
import WantViewTrendChart from '@/components/charts/WantViewTrendChart.vue'

export interface ItemTrendPoint {
  date: string
  want: number | null
  view: number | null
}

withDefaults(
  defineProps<{
    points: ItemTrendPoint[]
    /**
     * 单商品页「想要」常在个位数、「浏览」上万，同轴会把想要压成一条平线，
     * 因此默认拆成两张独立的单系列图，各自带 hover 提示。
     */
    isolateSeries?: boolean
  }>(),
  {
    isolateSeries: true,
  },
)
</script>

<template>
  <div v-if="isolateSeries" class="flex flex-col gap-4">
    <WantViewTrendChart
      :points="points"
      :dual-axis="false"
      :connect-nulls="false"
      :show-view="false"
      :title="$t('sellerSubscription.trendTitleWant')"
    />
    <WantViewTrendChart
      :points="points"
      :dual-axis="false"
      :connect-nulls="false"
      :show-want="false"
      :title="$t('sellerSubscription.trendTitleView')"
    />
  </div>
  <WantViewTrendChart v-else :points="points" :dual-axis="false" :connect-nulls="false" />
</template>
