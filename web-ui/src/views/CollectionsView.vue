<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import * as collectionsApi from '@/api/collections'
import type { CollectionItem } from '@/types/collection.d.ts'
import { Button } from '@/components/ui/button'
import { toast } from '@/components/ui/toast'
import { RefreshCw, ExternalLink, Trash2, Bookmark, Package } from 'lucide-vue-next'
import { formatDateTime } from '@/i18n'

const router = useRouter()
const { t } = useI18n()

const collections = ref<CollectionItem[]>([])
const isLoading = ref(true)
const deletingId = ref<number | null>(null)

async function loadCollections() {
  isLoading.value = true
  try {
    const res = await collectionsApi.listCollections()
    collections.value = res.items || []
  } catch (error: any) {
    toast({
      title: t('collections.list.loadFailed'),
      description: error?.message || String(error),
      variant: 'destructive',
    })
  } finally {
    isLoading.value = false
  }
}

function openDetail(id: number) {
  router.push({ name: 'CollectionDetail', params: { id } })
}

async function handleDelete(id: number) {
  deletingId.value = id
  try {
    await collectionsApi.deleteCollection(id)
    collections.value = collections.value.filter((c) => c.id !== id)
    toast({ title: t('collections.list.deleted') })
  } catch (error: any) {
    toast({
      title: t('collections.list.deleteFailed'),
      description: error?.message || String(error),
      variant: 'destructive',
    })
  } finally {
    deletingId.value = null
  }
}

function skuCount(item: CollectionItem): number {
  return item.skus?.length || 0
}

function skuStatusTone(status: string): string {
  switch (status) {
    case 'done':
      return 'text-emerald-600 bg-emerald-50'
    case 'failed':
      return 'text-rose-600 bg-rose-50'
    case 'running':
      return 'text-amber-600 bg-amber-50'
    default:
      return 'text-slate-500 bg-slate-50'
  }
}

const totalCount = computed(() => collections.value.length)
const doneCount = computed(() => collections.value.filter((c) => c.sku_fetch_status === 'done').length)

onMounted(loadCollections)
</script>

<template>
  <div class="space-y-6">
    <div class="flex flex-wrap items-center gap-3">
      <h1 class="text-2xl font-bold text-slate-800">{{ t('collections.list.title') }}</h1>
      <div class="ml-auto flex items-center gap-3">
        <span class="text-sm text-slate-500">
          {{ t('collections.list.totalCount', { count: totalCount }) }}
          <span class="text-emerald-600 ml-1">{{ t('collections.list.doneCount', { count: doneCount }) }}</span>
        </span>
        <Button variant="outline" size="sm" :disabled="isLoading" @click="loadCollections">
          <RefreshCw class="w-4 h-4 mr-1" :class="{ 'animate-spin': isLoading }" />
          {{ t('common.refresh') }}
        </Button>
      </div>
    </div>

    <div v-if="isLoading" class="app-surface p-8 text-center text-slate-500">
      {{ t('common.loading') }}
    </div>

    <div v-else-if="collections.length === 0" class="app-surface p-12 text-center">
      <Bookmark class="w-12 h-12 mx-auto text-slate-300 mb-3" />
      <p class="text-slate-500">{{ t('collections.list.empty') }}</p>
    </div>

    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <div
        v-for="item in collections"
        :key="item.id"
        class="app-surface p-4 cursor-pointer hover:shadow-md transition-shadow"
        @click="openDetail(item.id)"
      >
        <div class="flex items-start gap-3">
          <Package class="w-5 h-5 text-slate-400 mt-0.5 shrink-0" />
          <div class="flex-1 min-w-0">
            <h3 class="font-semibold text-slate-800 text-sm leading-snug truncate">
              {{ item.summary?.title || t('common.unnamed') }}
            </h3>
            <p v-if="item.summary?.price_display" class="text-rose-600 font-bold mt-1">
              {{ item.summary.price_display }}
            </p>
          </div>
          <span
            class="text-xs px-2 py-0.5 rounded-full font-medium shrink-0"
            :class="skuStatusTone(item.sku_fetch_status)"
          >
            {{ item.sku_fetch_status }}
          </span>
        </div>

        <div class="mt-3 flex items-center gap-3 text-xs text-slate-400">
          <span>{{ t('collections.list.skuCount', { count: skuCount(item) }) }}</span>
          <span v-if="item.collected_at">·</span>
          <span v-if="item.collected_at">{{ formatDateTime(item.collected_at) }}</span>
        </div>

        <div class="mt-3 flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            class="text-xs"
            :disabled="deletingId === item.id"
            @click.stop="handleDelete(item.id)"
          >
            <Trash2 class="w-3.5 h-3.5 mr-1" />
            {{ t('common.delete') }}
          </Button>
          <Button
            v-if="item.summary?.link"
            variant="ghost"
            size="sm"
            class="text-xs ml-auto"
            as-child
          >
            <a :href="item.summary.link" target="_blank" rel="noopener noreferrer" @click.stop>
              <ExternalLink class="w-3.5 h-3.5 mr-1" />
              {{ t('collections.detail.openXianyu') }}
            </a>
          </Button>
        </div>
      </div>
    </div>
  </div>
</template>
