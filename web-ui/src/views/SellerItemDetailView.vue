<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  getSellerItemDetail,
  type SellerItemDetailResponse,
  type SellerMetricHistoryPoint,
} from '@/api/sellerSubscriptions'
import { buildGoofishItemUrl } from '@/lib/goofish'
import { formatShanghaiTime } from '@/lib/datetime'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import ItemTrendChart, { type ItemTrendPoint } from '@/components/sellers/ItemTrendChart.vue'
import { ArrowLeft, Copy, ExternalLink } from 'lucide-vue-next'
import { toast } from '@/components/ui/toast'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const itemId = computed(() => String(route.params.itemId || ''))
const detail = ref<SellerItemDetailResponse | null>(null)
const isLoading = ref(true)
const loadError = ref('')
const showRawJson = ref(true)

const productInfo = computed(() => {
  const info = detail.value?.record?.['商品信息']
  return info && typeof info === 'object' ? (info as Record<string, unknown>) : null
})

const sellerInfo = computed(() => {
  const info = detail.value?.record?.['卖家信息']
  return info && typeof info === 'object' ? (info as Record<string, unknown>) : null
})

const itemUrl = computed(() => {
  const link = productInfo.value?.['商品链接']
  if (typeof link === 'string' && link) return link
  return itemId.value ? buildGoofishItemUrl(itemId.value) : ''
})

const imageUrls = computed(() => {
  const images = productInfo.value?.['商品图片列表']
  if (!Array.isArray(images)) return []
  return images.filter((url): url is string => typeof url === 'string' && url.length > 0)
})

const coverImage = computed(() => {
  const main = productInfo.value?.['商品主图链接']
  if (typeof main === 'string' && main) return main
  return imageUrls.value[0] || ''
})

const historyPoints = computed(() => detail.value?.metrics || [])

const latestSnapshot = computed(() => {
  if (!historyPoints.value.length) return null
  return [...historyPoints.value].sort((a, b) => {
    const ta = a.snapshot_time ? new Date(a.snapshot_time).getTime() : 0
    const tb = b.snapshot_time ? new Date(b.snapshot_time).getTime() : 0
    return tb - ta
  })[0] as SellerMetricHistoryPoint
})

const displayTitle = computed(() => {
  const fromRecord = productInfo.value?.['商品标题']
  if (typeof fromRecord === 'string' && fromRecord) return fromRecord
  return latestSnapshot.value?.title || itemId.value
})

const displayPrice = computed(() => {
  const fromRecord = productInfo.value?.['当前售价']
  if (fromRecord !== undefined && fromRecord !== null && fromRecord !== '') return String(fromRecord)
  const price = latestSnapshot.value?.price
  if (price === null || price === undefined) return '-'
  return Number.isInteger(price) ? String(price) : price.toFixed(2)
})

const displayDescription = computed(() => {
  const desc = productInfo.value?.['商品描述']
  return typeof desc === 'string' ? desc : ''
})

const trendPoints = computed<ItemTrendPoint[]>(() =>
  [...historyPoints.value]
    .sort((a, b) => {
      const ta = a.snapshot_time ? new Date(a.snapshot_time).getTime() : 0
      const tb = b.snapshot_time ? new Date(b.snapshot_time).getTime() : 0
      return ta - tb
    })
    .map((point) => ({
      date: point.snapshot_time || '',
      want: point.want_count ?? null,
      view: point.view_count ?? null,
    })),
)

const rawJsonText = computed(() => {
  if (!detail.value?.record) return ''
  return JSON.stringify(detail.value.record, null, 2)
})

const detailApiJsonText = computed(() => {
  const raw = detail.value?.detail_api?.raw_json
  if (!raw) return ''
  return JSON.stringify(raw, null, 2)
})

const dataSummary = computed(() => detail.value?.data_summary)
const detailApiSummary = computed(() => detail.value?.detail_api_summary)

function goBack() {
  const from = String(route.query.from || '')
  const sellerUserId = String(route.query.sellerUserId || '')
  if (from === 'seller' && sellerUserId) {
    router.push({
      name: 'SellerDetail',
      params: { sellerUserId },
      query: { tab: 'items' },
    })
    return
  }
  router.push({ name: 'SellerItems' })
}

function openSellerDetail() {
  const sellerUserId =
    latestSnapshot.value?.seller_user_id ||
    (typeof sellerInfo.value?.['卖家ID'] === 'string' ? sellerInfo.value['卖家ID'] : '')
  if (!sellerUserId) return
  router.push({
    name: 'SellerDetail',
    params: { sellerUserId },
    query: { tab: 'items' },
  })
}

async function copyText(text: string, successTitle: string) {
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    toast({ title: successTitle })
  } catch {
    toast({ title: t('common.error'), variant: 'destructive' })
  }
}

async function loadItem() {
  if (!itemId.value) {
    loadError.value = t('sellerSubscription.itemNotFound')
    isLoading.value = false
    return
  }
  isLoading.value = true
  loadError.value = ''
  try {
    detail.value = await getSellerItemDetail(itemId.value)
    if (!detail.value.metrics?.length && !detail.value.record) {
      loadError.value = t('sellerSubscription.noHistory')
    }
  } catch (e) {
    detail.value = null
    loadError.value = (e as Error).message
  } finally {
    isLoading.value = false
  }
}

onMounted(loadItem)
</script>

<template>
  <div class="space-y-6">
    <div class="flex flex-wrap items-center gap-3">
      <Button variant="outline" size="sm" class="gap-1" @click="goBack">
        <ArrowLeft class="h-4 w-4" />
        {{ t('common.back') }}
      </Button>
      <h1 class="text-2xl font-black text-slate-900">{{ t('sellerSubscription.itemDetailTitle') }}</h1>
      <div class="ml-auto flex gap-2">
        <Button v-if="itemUrl" variant="default" size="sm" as-child>
          <a :href="itemUrl" target="_blank" rel="noopener noreferrer">
            <ExternalLink class="mr-1 h-4 w-4" />
            {{ t('sellerSubscription.viewOriginalPage') }}
          </a>
        </Button>
      </div>
    </div>

    <p v-if="loadError && !isLoading" class="text-sm text-rose-600">{{ loadError }}</p>

    <Card v-if="isLoading" class="app-surface border-none">
      <CardContent class="py-10 text-center text-sm text-slate-400">{{ t('common.loading') }}</CardContent>
    </Card>

    <template v-else-if="detail">
      <Card class="app-surface border-none">
        <CardContent class="space-y-4 p-5">
          <div class="flex flex-col gap-4 md:flex-row">
            <div v-if="coverImage" class="shrink-0">
              <img
                :src="coverImage"
                :alt="displayTitle"
                class="h-40 w-40 rounded-xl border border-slate-100 object-cover"
              />
            </div>
            <div class="min-w-0 flex-1 space-y-3">
              <div>
                <h2 class="text-lg font-semibold leading-snug text-slate-900">{{ displayTitle }}</h2>
                <p class="mt-1 text-xs text-slate-500">ID: {{ itemId }}</p>
              </div>

              <div class="flex flex-wrap gap-4 text-sm">
                <div>
                  <span class="text-slate-500">{{ t('sellerSubscription.colPrice') }}：</span>
                  <span class="font-semibold text-rose-600">¥{{ displayPrice }}</span>
                </div>
                <div>
                  <span class="text-slate-500">{{ t('sellerSubscription.colWant') }}：</span>
                  <span class="font-medium">{{ latestSnapshot?.want_count ?? productInfo?.['“想要”人数'] ?? '-' }}</span>
                </div>
                <div>
                  <span class="text-slate-500">{{ t('sellerSubscription.colView') }}：</span>
                  <span class="font-medium">{{ latestSnapshot?.view_count ?? productInfo?.['浏览量'] ?? '-' }}</span>
                </div>
                <div>
                  <span class="text-slate-500">{{ t('sellerSubscription.colStatus') }}：</span>
                  <Badge v-if="latestSnapshot?.item_status || productInfo?.['商品状态']" variant="secondary">
                    {{ latestSnapshot?.item_status || productInfo?.['商品状态'] }}
                  </Badge>
                  <span v-else>-</span>
                </div>
                <div>
                  <span class="text-slate-500">{{ t('sellerSubscription.colSnapshot') }}：</span>
                  <span>{{ formatShanghaiTime(latestSnapshot?.snapshot_time || detail.crawl_time) }}</span>
                </div>
              </div>

              <div
                v-if="latestSnapshot?.seller_user_id || sellerInfo?.['卖家ID']"
                class="text-sm"
              >
                <span class="text-slate-500">{{ t('sellerSubscription.colSeller') }}：</span>
                <Button variant="link" class="h-auto p-0 text-primary" @click="openSellerDetail">
                  {{ latestSnapshot?.seller_user_id || sellerInfo?.['卖家ID'] }}
                </Button>
              </div>

              <p v-if="displayDescription" class="whitespace-pre-wrap text-sm leading-relaxed text-slate-700">
                {{ displayDescription }}
              </p>
            </div>
          </div>

          <div v-if="imageUrls.length > 1" class="grid grid-cols-2 gap-2 sm:grid-cols-4 md:grid-cols-6">
            <a
              v-for="(url, index) in imageUrls"
              :key="`${url}-${index}`"
              :href="url"
              target="_blank"
              rel="noopener noreferrer"
              class="block overflow-hidden rounded-lg border border-slate-100"
            >
              <img :src="url" :alt="`${displayTitle} ${index + 1}`" class="h-24 w-full object-cover" />
            </a>
          </div>
        </CardContent>
      </Card>

      <Card v-if="dataSummary" class="app-surface border-none">
        <CardHeader>
          <CardTitle class="text-base">{{ t('sellerSubscription.dataProbeTitle') }}</CardTitle>
        </CardHeader>
        <CardContent class="space-y-3 text-sm">
          <p class="text-slate-600">{{ t('sellerSubscription.dataProbeHint') }}</p>
          <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div class="rounded-lg bg-slate-50 px-3 py-2">
              <div class="text-xs text-slate-500">{{ t('sellerSubscription.probeHasRecord') }}</div>
              <div class="font-semibold">{{ dataSummary.has_record ? t('common.yes') : t('common.no') }}</div>
            </div>
            <div class="rounded-lg bg-slate-50 px-3 py-2">
              <div class="text-xs text-slate-500">{{ t('sellerSubscription.probeImageCount') }}</div>
              <div class="font-semibold">{{ dataSummary.image_count }}</div>
            </div>
            <div class="rounded-lg bg-slate-50 px-3 py-2">
              <div class="text-xs text-slate-500">{{ t('sellerSubscription.probeDescLength') }}</div>
              <div class="font-semibold">{{ dataSummary.description_length }}</div>
            </div>
            <div class="rounded-lg bg-slate-50 px-3 py-2">
              <div class="text-xs text-slate-500">{{ t('sellerSubscription.probeSkuData') }}</div>
              <div class="font-semibold">{{ dataSummary.has_sku_data ? t('common.yes') : t('common.no') }}</div>
            </div>
            <div v-if="detailApiSummary?.has_detail_api" class="rounded-lg bg-slate-50 px-3 py-2">
              <div class="text-xs text-slate-500">{{ t('sellerSubscription.probeDetailApiSku') }}</div>
              <div class="font-semibold">{{ detailApiSummary.sku_count }}</div>
            </div>
          </div>
          <div class="space-y-2">
            <div>
              <span class="text-slate-500">{{ t('sellerSubscription.probeTopKeys') }}：</span>
              <span class="font-mono text-xs">{{ dataSummary.top_level_keys.join(', ') || '-' }}</span>
            </div>
            <div>
              <span class="text-slate-500">{{ t('sellerSubscription.probeProductKeys') }}：</span>
              <span class="font-mono text-xs">{{ dataSummary.product_fields.join(', ') || '-' }}</span>
            </div>
            <div>
              <span class="text-slate-500">{{ t('sellerSubscription.probeSellerKeys') }}：</span>
              <span class="font-mono text-xs">{{ dataSummary.seller_fields.join(', ') || '-' }}</span>
            </div>
            <div v-if="detail.result_item_id" class="text-xs text-slate-500">
              result_items.id={{ detail.result_item_id }} · {{ detail.result_filename }}
            </div>
          </div>
        </CardContent>
      </Card>

      <Card class="app-surface border-none">
        <CardHeader class="flex flex-row items-center justify-between gap-2">
          <CardTitle class="text-base">{{ t('sellerSubscription.detailApiRawTitle') }}</CardTitle>
          <div class="flex gap-2">
            <Button
              v-if="detailApiJsonText"
              variant="outline"
              size="sm"
              class="gap-1"
              @click="copyText(detailApiJsonText, t('sellerSubscription.detailApiCopied'))"
            >
              <Copy class="h-3.5 w-3.5" />
              {{ t('sellerSubscription.copyRaw') }}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <p v-if="detailApiSummary?.has_detail_api" class="mb-3 text-xs text-slate-500">
            {{ t('sellerSubscription.detailApiRawHint') }}
            <span v-if="detail.detail_api?.captured_at"> · {{ formatShanghaiTime(detail.detail_api.captured_at) }}</span>
          </p>
          <pre
            v-if="detailApiJsonText"
            class="max-h-[560px] overflow-auto rounded-lg bg-slate-950 p-4 text-xs leading-relaxed text-slate-100"
          >{{ detailApiJsonText }}</pre>
          <p v-else class="py-6 text-center text-sm text-slate-400">
            {{ t('sellerSubscription.noDetailApiRaw') }}
          </p>
        </CardContent>
      </Card>

      <Card class="app-surface border-none">
        <CardHeader class="flex flex-row items-center justify-between gap-2">
          <CardTitle class="text-base">{{ t('sellerSubscription.rawDataTitle') }}</CardTitle>
          <div class="flex gap-2">
            <Button
              v-if="rawJsonText"
              variant="outline"
              size="sm"
              class="gap-1"
              @click="copyText(rawJsonText, t('sellerSubscription.rawCopied'))"
            >
              <Copy class="h-3.5 w-3.5" />
              {{ t('sellerSubscription.copyRaw') }}
            </Button>
            <Button variant="outline" size="sm" @click="showRawJson = !showRawJson">
              {{ showRawJson ? t('sellerSubscription.hideRaw') : t('sellerSubscription.showRaw') }}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <p class="mb-3 text-xs text-slate-500">{{ t('sellerSubscription.recordRawHint') }}</p>
          <pre
            v-if="showRawJson && rawJsonText"
            class="max-h-[480px] overflow-auto rounded-lg bg-slate-950 p-4 text-xs leading-relaxed text-slate-100"
          >{{ rawJsonText }}</pre>
          <p v-else-if="!rawJsonText" class="py-6 text-center text-sm text-slate-400">
            {{ t('sellerSubscription.noRawRecord') }}
          </p>
        </CardContent>
      </Card>

      <Card class="app-surface border-none">
        <CardHeader>
          <CardTitle class="text-base">{{ t('sellerSubscription.metricTrend') }}</CardTitle>
        </CardHeader>
        <CardContent>
          <ItemTrendChart v-if="trendPoints.length" :points="trendPoints" />
          <p v-else class="py-8 text-center text-sm text-slate-400">{{ t('sellerSubscription.noTrend') }}</p>
        </CardContent>
      </Card>
    </template>
  </div>
</template>
