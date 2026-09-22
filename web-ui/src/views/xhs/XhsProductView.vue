<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { getXhsProduct, getXhsSeries, type XhsProduct, type XhsSeriesPoint } from '@/api/xhs'
import XhsDeltaChart from '@/components/xhs/XhsDeltaChart.vue'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

const route = useRoute()
const { t } = useI18n()
const product = ref<XhsProduct | null>(null)
const points = ref<XhsSeriesPoint[]>([])
const kind = ref<'hourly' | 'daily'>('hourly')
const errorText = ref('')

const productId = computed(() => String(route.params.productId || ''))

function showDelta(value: number | null | undefined, incomplete?: boolean) {
  if (value === null || value === undefined) return '—'
  const text = value > 0 ? `+${value}` : String(value)
  return incomplete ? `${text}*` : text
}

async function load() {
  errorText.value = ''
  try {
    const [detail, series] = await Promise.all([
      getXhsProduct(productId.value),
      getXhsSeries(productId.value, kind.value),
    ])
    product.value = detail
    points.value = series
  } catch (error) {
    errorText.value = error instanceof Error ? error.message : t('xhs.loadFailed')
  }
}

onMounted(load)
watch([productId, kind], load)
</script>

<template>
  <div class="space-y-4 p-4">
    <div>
      <h1 class="text-xl font-semibold">{{ product?.title || productId }}</h1>
      <p class="text-sm text-muted-foreground">
        {{ product?.assigned_shop_name || t('xhs.unassigned') }}
        <span v-if="product?.shop_name"> · {{ t('xhs.pageShop') }} {{ product.shop_name }}</span>
        <span v-if="product?.category"> · {{ product.category }}</span>
      </p>
      <p v-if="product?.tags?.length" class="text-sm text-muted-foreground">{{ product.tags.join('、') }}</p>
    </div>
    <p v-if="errorText" class="text-sm text-destructive">{{ errorText }}</p>
    <div class="grid gap-3 sm:grid-cols-4">
      <Card>
        <CardHeader><CardTitle>{{ t('xhs.colSold') }}</CardTitle></CardHeader>
        <CardContent>{{ product?.sold_total ?? '—' }}</CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>{{ t('xhs.colToday') }}</CardTitle></CardHeader>
        <CardContent>{{ showDelta(product?.today, product?.today_incomplete) }}</CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>{{ t('xhs.colYesterday') }}</CardTitle></CardHeader>
        <CardContent>{{ showDelta(product?.yesterday, product?.yesterday_incomplete) }}</CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>{{ t('xhs.colHour') }}</CardTitle></CardHeader>
        <CardContent>{{ showDelta(product?.last_hour, product?.last_hour_incomplete) }}</CardContent>
      </Card>
    </div>
    <Card>
      <CardHeader class="flex flex-row items-center justify-between">
        <CardTitle>{{ t('xhs.seriesTitle') }}</CardTitle>
        <div class="flex gap-2 text-sm">
          <button type="button" :class="kind === 'hourly' ? 'font-semibold' : ''" @click="kind = 'hourly'">
            {{ t('xhs.hourly') }}
          </button>
          <button type="button" :class="kind === 'daily' ? 'font-semibold' : ''" @click="kind = 'daily'">
            {{ t('xhs.daily') }}
          </button>
        </div>
      </CardHeader>
      <CardContent>
        <XhsDeltaChart :points="points" />
        <p class="mt-2 text-xs text-muted-foreground">{{ t('xhs.fuzzyHint') }}</p>
      </CardContent>
    </Card>
  </div>
</template>
