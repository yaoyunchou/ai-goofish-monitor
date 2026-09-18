<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  getShopAnalyticsDashboard,
  type ShopAnalyticsDashboard,
  type ShopAnalyticsPeriod,
} from '@/api/shopAnalytics'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { toast } from '@/components/ui/toast'
import { formatShanghaiTime } from '@/lib/datetime'
import WantViewTrendChart from '@/components/charts/WantViewTrendChart.vue'
import ShopRankingTable from '@/components/shop-analytics/ShopRankingTable.vue'
import HotItemsTable from '@/components/shop-analytics/HotItemsTable.vue'

const { t } = useI18n()
const period = ref<ShopAnalyticsPeriod>('today')
const dashboard = ref<ShopAnalyticsDashboard | null>(null)
const isLoading = ref(false)
const loadError = ref('')

const hasData = computed(() => Boolean(dashboard.value?.has_data))
const cards = computed(() => dashboard.value?.cards)
const shopsMismatch = computed(() => {
  const current = cards.value
  if (!current) return false
  return current.enabled_shop_count !== current.shops_with_data
})
const todayEmpty = computed(() => {
  if (!dashboard.value?.has_data || period.value !== 'today') return false
  return (cards.value?.item_count ?? 0) === 0
})
const freshnessText = computed(() => {
  const freshness = dashboard.value?.freshness
  const time = freshness?.last_captured_at || freshness?.last_run_at
  if (!time) return ''
  return t('shopAnalytics.freshness', { time: formatShanghaiTime(time) })
})

function formatCount(value: number | null | undefined) {
  if (value === null || value === undefined) return '—'
  return value.toLocaleString('zh-CN')
}

const metricCards = computed(() => {
  const current = cards.value
  const isRange = period.value === '7d'
  const anchor = dashboard.value?.anchor_day
  const anchorHint = isRange && anchor ? t('shopAnalytics.cardAnchor', { date: anchor }) : ''
  return [
    {
      key: 'shops',
      label: t('shopAnalytics.cardShops'),
      value: formatCount(current?.enabled_shop_count),
      hint: t('shopAnalytics.tooltipShops'),
      sub: '',
    },
    {
      key: 'items',
      label: isRange ? t('shopAnalytics.cardItemsRange') : t('shopAnalytics.cardItems'),
      value: formatCount(current?.item_count),
      hint: t('shopAnalytics.tooltipItems'),
      sub: isRange && dashboard.value ? `${dashboard.value.range_start} ~ ${dashboard.value.range_end}` : '',
    },
    {
      key: 'want',
      label: isRange ? t('shopAnalytics.cardWantRange') : t('shopAnalytics.cardWant'),
      value: formatCount(current?.want_sum),
      hint: t('shopAnalytics.tooltipWant'),
      sub: anchorHint,
    },
    {
      key: 'view',
      label: isRange ? t('shopAnalytics.cardViewRange') : t('shopAnalytics.cardView'),
      value: formatCount(current?.view_sum),
      hint: t('shopAnalytics.tooltipView'),
      sub: anchorHint,
    },
  ]
})

async function load() {
  isLoading.value = true
  loadError.value = ''
  try {
    dashboard.value = await getShopAnalyticsDashboard(period.value)
  } catch (e) {
    dashboard.value = null
    const message = (e as Error).message || t('shopAnalytics.empty')
    loadError.value = message
    toast({ title: t('common.error'), description: message, variant: 'destructive' })
  } finally {
    isLoading.value = false
  }
}

function setPeriod(next: ShopAnalyticsPeriod) {
  if (period.value === next) return
  period.value = next
  load()
}

onMounted(load)
</script>

<template>
  <div class="space-y-6">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 class="text-2xl font-black text-slate-900">{{ t('shopAnalytics.title') }}</h1>
        <p class="text-sm text-slate-500">{{ t('shopAnalytics.description') }}</p>
        <p v-if="freshnessText" class="mt-1 text-xs text-slate-400">{{ freshnessText }}</p>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <Button
          v-for="item in (['today', '7d'] as ShopAnalyticsPeriod[])"
          :key="item"
          :variant="period === item ? 'default' : 'outline'"
          @click="setPeriod(item)"
        >
          {{ item === 'today' ? t('shopAnalytics.periodToday') : t('shopAnalytics.period7d') }}
        </Button>
        <Button @click="load">{{ t('common.refresh') }}</Button>
      </div>
    </div>

    <Card v-if="loadError" class="app-surface border border-amber-200 bg-amber-50">
      <CardContent class="p-5 text-sm text-amber-900">
        {{ loadError }}
      </CardContent>
    </Card>

    <Card v-else-if="isLoading && !dashboard" class="app-surface border-none">
      <CardContent class="py-10 text-center text-sm text-slate-400">
        {{ t('common.loading') }}
      </CardContent>
    </Card>

    <Card v-else-if="!hasData" class="app-surface border-none">
      <CardContent class="space-y-4 py-10 text-center">
        <p class="text-base font-semibold text-slate-800">{{ t('shopAnalytics.empty') }}</p>
        <p class="text-sm text-slate-500">{{ t('shopAnalytics.emptyHint') }}</p>
        <div class="flex flex-wrap items-center justify-center gap-3">
          <Button as-child>
            <RouterLink to="/seller-subscriptions/collection">
              {{ t('shopAnalytics.goCollection') }}
            </RouterLink>
          </Button>
          <RouterLink
            to="/seller-subscriptions/sellers"
            class="text-sm text-primary underline-offset-4 hover:underline"
          >
            {{ t('shopAnalytics.goSellers') }}
          </RouterLink>
        </div>
      </CardContent>
    </Card>

    <template v-else>
      <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card v-for="card in metricCards" :key="card.key" class="app-surface border-none" :title="card.hint">
          <CardContent class="p-5">
            <p class="text-xs uppercase tracking-widest text-slate-400">{{ card.label }}</p>
            <p class="mt-2 text-2xl font-black text-slate-800">{{ card.value }}</p>
            <p v-if="card.sub" class="mt-1 text-xs text-slate-400">{{ card.sub }}</p>
          </CardContent>
        </Card>
      </div>
      <p v-if="shopsMismatch" class="text-xs text-slate-500">
        {{
          t('shopAnalytics.shopsMismatch', {
            enabled: cards?.enabled_shop_count ?? 0,
            withData: cards?.shops_with_data ?? 0,
          })
        }}
      </p>
      <p v-if="todayEmpty" class="text-xs text-amber-700">{{ t('shopAnalytics.todayEmpty') }}</p>

      <Card class="app-surface border-none">
        <CardHeader>
          <CardTitle>{{ t('shopAnalytics.trendTitle') }}</CardTitle>
          <p class="text-xs font-normal text-slate-400">{{ t('shopAnalytics.trendHint') }}</p>
        </CardHeader>
        <CardContent>
          <WantViewTrendChart
            :points="dashboard?.trend || []"
            :dual-axis="true"
            :connect-nulls="false"
            :title="t('shopAnalytics.trendTitle')"
          />
        </CardContent>
      </Card>

      <Card class="app-surface border-none">
        <CardHeader>
          <CardTitle>{{ t('shopAnalytics.rankingTitle') }}</CardTitle>
          <p class="text-xs font-normal text-slate-400">{{ t('shopAnalytics.rankingHint') }}</p>
        </CardHeader>
        <CardContent>
          <ShopRankingTable :rows="dashboard?.shops || []" />
        </CardContent>
      </Card>

      <Card class="app-surface border-none">
        <CardHeader>
          <CardTitle>{{ t('shopAnalytics.hotTitle') }}</CardTitle>
          <p class="text-xs font-normal text-slate-400">{{ t('shopAnalytics.hotHint') }}</p>
        </CardHeader>
        <CardContent>
          <HotItemsTable :rows="dashboard?.hot_items || []" />
        </CardContent>
      </Card>
    </template>
  </div>
</template>
