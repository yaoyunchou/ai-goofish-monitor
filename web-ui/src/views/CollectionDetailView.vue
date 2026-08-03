<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import * as collectionsApi from '@/api/collections'
import type { CollectionItem } from '@/types/collection.d.ts'
import { Button } from '@/components/ui/button'
import { toast } from '@/components/ui/toast'
import { ArrowLeft, ExternalLink, RefreshCw } from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const collection = ref<CollectionItem | null>(null)
const isLoading = ref(true)
const isRefreshing = ref(false)
let pollTimer: ReturnType<typeof setInterval> | null = null

const collectionId = computed(() => Number(route.params.id))

const title = computed(() => {
  const summaryTitle = collection.value?.summary?.title
  if (summaryTitle) return summaryTitle
  const product = collection.value?.record?.['商品信息'] as Record<string, unknown> | undefined
  return String(product?.['商品标题'] || '')
})
const link = computed(() => collection.value?.summary?.link || '')

async function loadCollection(silent = false) {
  if (!silent) isLoading.value = true
  try {
    collection.value = await collectionsApi.getCollection(collectionId.value)
  } catch (error: any) {
    toast({
      title: t('collections.detail.loadFailed'),
      description: error?.message || String(error),
      variant: 'destructive',
    })
  } finally {
    if (!silent) isLoading.value = false
  }
}

async function handleRefresh() {
  isRefreshing.value = true
  try {
    const res = await collectionsApi.refreshCollectionSkus(collectionId.value)
    collection.value = res.collection
    toast({ title: t('collections.detail.refreshStarted') })
  } catch (error: any) {
    toast({
      title: t('collections.detail.refreshFailed'),
      description: error?.message || String(error),
      variant: 'destructive',
    })
  } finally {
    isRefreshing.value = false
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(async () => {
    if (!collection.value) return
    if (!['pending', 'running'].includes(collection.value.sku_fetch_status)) {
      stopPolling()
      return
    }
    await loadCollection(true)
  }, 2500)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

onMounted(async () => {
  await loadCollection()
  startPolling()
})

onUnmounted(stopPolling)
</script>

<template>
  <div class="space-y-6">
    <div class="flex flex-wrap items-center gap-3">
      <Button variant="outline" size="sm" @click="router.push({ name: 'Results' })">
        <ArrowLeft class="w-4 h-4 mr-1" />
        {{ t('collections.detail.back') }}
      </Button>
      <h1 class="text-2xl font-bold text-slate-800">{{ t('collections.detail.title') }}</h1>
      <div class="ml-auto flex gap-2">
        <Button variant="outline" size="sm" :disabled="isRefreshing" @click="handleRefresh">
          <RefreshCw class="w-4 h-4 mr-1" :class="{ 'animate-spin': isRefreshing }" />
          {{ t('collections.detail.refreshSkus') }}
        </Button>
        <Button v-if="link" variant="default" size="sm" as-child>
          <a :href="link" target="_blank" rel="noopener noreferrer">
            <ExternalLink class="w-4 h-4 mr-1" />
            {{ t('collections.detail.openXianyu') }}
          </a>
        </Button>
      </div>
    </div>

    <div v-if="isLoading" class="app-surface p-8 text-center text-slate-500">
      {{ t('common.loading') }}
    </div>

    <template v-else-if="collection">
      <div class="app-surface p-5 space-y-2">
        <h2 class="text-lg font-semibold text-slate-800 leading-snug">{{ title }}</h2>
        <p class="text-sm text-slate-500">
          {{ t('collections.detail.status') }}:
          <span class="font-medium text-slate-700">{{ collection.sku_fetch_status }}</span>
          <span v-if="collection.sku_error" class="text-rose-600 ml-2">{{ collection.sku_error }}</span>
        </p>
        <p v-if="collection.summary?.price_display" class="text-rose-600 text-xl font-bold">
          {{ collection.summary.price_display }}
        </p>
      </div>

      <div class="app-surface overflow-hidden">
        <div class="border-b border-slate-100 px-5 py-3 font-semibold text-slate-700">
          {{ t('collections.detail.skuTableTitle') }}
          <span class="text-sm font-normal text-slate-400 ml-2">({{ collection.skus.length }})</span>
        </div>
        <div v-if="['pending', 'running'].includes(collection.sku_fetch_status)" class="p-8 text-center text-slate-500">
          {{ t('collections.detail.fetchingSkus') }}
        </div>
        <div v-else-if="collection.skus.length === 0" class="p-8 text-center text-slate-500">
          {{ t('collections.detail.noSkus') }}
        </div>
        <div v-else class="overflow-x-auto">
          <table class="min-w-full text-sm">
            <thead class="bg-slate-50 text-left text-slate-500">
              <tr>
                <th class="px-5 py-3 font-medium">{{ t('collections.detail.colSpec') }}</th>
                <th class="px-5 py-3 font-medium">{{ t('collections.detail.colPrice') }}</th>
                <th class="px-5 py-3 font-medium">{{ t('collections.detail.colSkuId') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(sku, index) in collection.skus" :key="sku.sku_id || index" class="border-t border-slate-100">
                <td class="px-5 py-3 text-slate-800">{{ sku.label }}</td>
                <td class="px-5 py-3 text-rose-600 font-semibold">{{ sku.price_display || '—' }}</td>
                <td class="px-5 py-3 text-slate-400 font-mono text-xs">{{ sku.sku_id || '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>
