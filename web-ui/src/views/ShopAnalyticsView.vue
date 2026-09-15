<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { collectShopAnalytics, getShopDistribution, getShopOverview, getShopTrend } from '@/api/shopAnalytics'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { toast } from '@/components/ui/toast'

const { t } = useI18n()
const cycle = ref('1d')
const overview = ref<any>(null)
const distributionType = ref('source')
const distribution = ref<any[]>([])
const trend = ref<any[]>([])
const isLoading = ref(false)
const loadError = ref('')

const hasData = computed(() => Boolean(overview.value?.metrics && Object.keys(overview.value.metrics).length))

const metricCards = computed(() => {
  const metrics = overview.value?.metrics || {}
  const pick = (key: string) => metrics[key]?.value ?? metrics[key]?.display ?? '-'
  return [
    { label: t('shopAnalytics.showPv'), value: pick('showPv') },
    { label: t('shopAnalytics.ipv'), value: pick('ipv') },
    { label: t('shopAnalytics.vstUv'), value: pick('vstUv') },
    { label: t('shopAnalytics.payOrdCnt'), value: pick('payOrdCnt') },
    { label: t('shopAnalytics.onlCnt'), value: pick('onlCnt') },
    { label: t('shopAnalytics.uctr'), value: pick('uctr') },
  ]
})

async function load() {
  isLoading.value = true
  loadError.value = ''
  try {
    const overviewRes = await getShopOverview(cycle.value)
    overview.value = overviewRes
    if (!overviewRes?.has_data) {
      loadError.value = overviewRes?.empty_message || t('shopAnalytics.empty')
      distribution.value = []
      trend.value = []
      return
    }
    const dist = await getShopDistribution(cycle.value, distributionType.value)
    distribution.value = dist.items || []
    const trendRes = await getShopTrend('showPv', 30, cycle.value)
    trend.value = trendRes.points || []
  } catch (e) {
    overview.value = null
    distribution.value = []
    trend.value = []
    const message = (e as Error).message || t('shopAnalytics.empty')
    loadError.value = message
    toast({ title: t('common.error'), description: message, variant: 'destructive' })
  } finally {
    isLoading.value = false
  }
}

async function collect() {
  try {
    const result = await collectShopAnalytics()
    toast({ title: result.message || t('shopAnalytics.collectStarted') })
  } catch (e) {
    toast({ title: t('common.error'), description: (e as Error).message, variant: 'destructive' })
  }
}

onMounted(load)
</script>

<template>
  <div class="space-y-6">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 class="text-2xl font-black text-slate-900">{{ t('shopAnalytics.title') }}</h1>
        <p class="text-sm text-slate-500">{{ t('shopAnalytics.description') }}</p>
      </div>
      <div class="flex gap-2">
        <Button variant="outline" @click="collect">{{ t('shopAnalytics.collect') }}</Button>
        <Button @click="load">{{ t('common.refresh') }}</Button>
      </div>
    </div>
    <div class="flex gap-2">
      <Button v-for="item in ['1d', '7d', '30d']" :key="item" :variant="cycle === item ? 'default' : 'outline'" @click="cycle = item; load()">
        {{ t(`shopAnalytics.cycle.${item}`) }}
      </Button>
    </div>
    <Card v-if="loadError" class="app-surface border border-amber-200 bg-amber-50">
      <CardContent class="p-5 text-sm text-amber-900">
        {{ loadError }}
      </CardContent>
    </Card>
    <div v-else-if="hasData" class="grid gap-4 md:grid-cols-3">
      <Card v-for="card in metricCards" :key="card.label" class="app-surface border-none">
        <CardContent class="p-5">
          <p class="text-xs uppercase tracking-widest text-slate-400">{{ card.label }}</p>
          <p class="mt-2 text-2xl font-black text-slate-800">{{ card.value }}</p>
        </CardContent>
      </Card>
    </div>
    <Card v-else class="app-surface border-none">
      <CardContent class="py-10 text-center text-sm text-slate-400">
        {{ isLoading ? t('common.loading') : t('shopAnalytics.empty') }}
      </CardContent>
    </Card>
    <Card class="app-surface border-none">
      <CardHeader class="flex flex-row items-center justify-between">
        <CardTitle>{{ t('shopAnalytics.distribution') }}</CardTitle>
        <select v-model="distributionType" class="h-9 rounded-md border px-2 text-sm" @change="load">
          <option value="source">{{ t('shopAnalytics.source') }}</option>
          <option value="category">{{ t('shopAnalytics.category') }}</option>
          <option value="time">{{ t('shopAnalytics.time') }}</option>
          <option value="region">{{ t('shopAnalytics.region') }}</option>
        </select>
      </CardHeader>
      <CardContent>
        <p v-if="isLoading" class="text-sm text-slate-500">{{ t('common.loading') }}</p>
        <ul v-else class="space-y-2 text-sm">
          <li v-for="item in distribution" :key="item.label" class="flex justify-between border-b border-slate-100 py-2">
            <span>{{ item.label }}</span>
            <span>{{ item.ratio_format || item.count }}</span>
          </li>
          <li v-if="!distribution.length" class="py-6 text-center text-slate-400">{{ t('shopAnalytics.empty') }}</li>
        </ul>
      </CardContent>
    </Card>
    <Card class="app-surface border-none">
      <CardHeader>
        <CardTitle>{{ t('shopAnalytics.trend') }}</CardTitle>
      </CardHeader>
      <CardContent class="text-sm text-slate-600">
        <p v-for="point in trend" :key="point.date">{{ point.date }} · showPv {{ point.value ?? '-' }}</p>
        <p v-if="!trend.length" class="py-6 text-center text-slate-400">{{ t('shopAnalytics.empty') }}</p>
      </CardContent>
    </Card>
  </div>
</template>
