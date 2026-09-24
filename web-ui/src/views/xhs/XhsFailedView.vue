<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { collectXhsProduct, getXhsCollectStatus, ignoreXhsFailures, listXhsFailures, removeXhsProduct, type XhsProduct } from '@/api/xhs'
import { Button } from '@/components/ui/button'
import { toast } from '@/components/ui/toast'
import { formatDateTime } from '@/i18n'

const { t } = useI18n()
const items = ref<XhsProduct[]>([])
const loading = ref(false)
const retryingId = ref('')
const serverRunning = ref(false)
let statusTimer = 0

const busy = computed(() => Boolean(retryingId.value) || serverRunning.value)

async function load() {
  loading.value = true
  try {
    items.value = await listXhsFailures()
  } catch (error) {
    toast({ title: t('common.error'), description: error instanceof Error ? error.message : t('xhs.loadFailed'), variant: 'destructive' })
  } finally {
    loading.value = false
  }
}

async function refreshCollectStatus() {
  try {
    serverRunning.value = (await getXhsCollectStatus()).running
  } catch {
    return
  }
}

async function retry(productId: string) {
  if (busy.value) return
  retryingId.value = productId
  toast({ title: t('xhs.collectStarted') })
  try {
    const summary = await collectXhsProduct(productId)
    await load()
    const row = items.value.find((item) => item.id === productId)
    if (summary.saved > 0 && !summary.failed) {
      toast({ title: t('xhs.retryDone') })
    } else if (summary.stopped) {
      toast({ title: t('xhs.stopped'), description: summary.error || row?.last_error || '', variant: 'destructive' })
    } else {
      toast({
        title: t('xhs.retryFailed'),
        description: summary.error || row?.last_error || t('xhs.collectFailed'),
        variant: 'destructive',
      })
    }
  } catch (error) {
    toast({ title: t('common.error'), description: error instanceof Error ? error.message : t('xhs.collectFailed'), variant: 'destructive' })
  } finally {
    retryingId.value = ''
    await refreshCollectStatus()
  }
}

async function ignore(productId: string) {
  try {
    await ignoreXhsFailures([productId])
    await load()
  } catch (error) {
    toast({ title: t('common.error'), description: error instanceof Error ? error.message : t('xhs.loadFailed'), variant: 'destructive' })
  }
}

async function remove(productId: string) {
  await removeXhsProduct(productId)
  await load()
}

onMounted(() => {
  load()
  refreshCollectStatus()
  statusTimer = window.setInterval(refreshCollectStatus, 3000)
})

onUnmounted(() => {
  window.clearInterval(statusTimer)
})
</script>

<template>
  <div class="space-y-4 p-4">
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 class="text-xl font-semibold">{{ t('xhs.failedTitle') }}</h1>
        <p class="text-sm text-muted-foreground">{{ t('xhs.failedHint') }}</p>
      </div>
      <Button variant="outline" :disabled="loading" @click="load">{{ t('common.refresh') }}</Button>
    </div>
    <div v-if="busy" class="flex items-center gap-2 rounded-lg border border-primary/30 bg-primary/5 px-3 py-2 text-sm">
      <span class="h-2 w-2 animate-pulse rounded-full bg-primary" />
      {{ t('xhs.collectingBanner') }}
    </div>
    <div class="overflow-x-auto rounded-lg border">
      <table class="w-full min-w-[720px] text-sm">
        <thead class="bg-muted/40 text-left">
          <tr>
            <th class="p-3">{{ t('xhs.colProduct') }}</th>
            <th class="p-3">{{ t('xhs.colId') }}</th>
            <th class="p-3">{{ t('xhs.colFailedAt') }}</th>
            <th class="p-3">{{ t('xhs.colReason') }}</th>
            <th class="p-3"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!items.length">
            <td class="p-4 text-muted-foreground" colspan="5">{{ loading ? t('xhs.loading') : t('xhs.failedEmpty') }}</td>
          </tr>
          <tr v-for="item in items" :key="item.id" class="border-t">
            <td class="p-3">
              <RouterLink class="font-medium hover:underline" :to="`/xhs/${item.id}`">{{ item.title || item.id }}</RouterLink>
              <div class="text-xs text-muted-foreground">{{ item.assigned_shop_name || item.shop_name || t('xhs.unassigned') }}</div>
            </td>
            <td class="p-3 font-mono text-xs">{{ item.id }}</td>
            <td class="p-3">{{ item.updated_at ? formatDateTime(item.updated_at) : '—' }}</td>
            <td class="p-3">{{ item.last_error || '—' }}</td>
            <td class="p-3 text-right">
              <Button size="sm" variant="outline" :disabled="busy" @click="retry(item.id)">
                {{ retryingId === item.id || serverRunning ? t('xhs.collecting') : t('xhs.retry') }}
              </Button>
              <Button size="sm" variant="ghost" @click="ignore(item.id)">{{ t('xhs.ignore') }}</Button>
              <Button size="sm" variant="ghost" @click="remove(item.id)">{{ t('common.delete') }}</Button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
