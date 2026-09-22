<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { collectXhsProduct, ignoreXhsFailures, listXhsFailures, removeXhsProduct, type XhsProduct } from '@/api/xhs'
import { Button } from '@/components/ui/button'
import { toast } from '@/components/ui/toast'
import { formatDateTime } from '@/i18n'

const { t } = useI18n()
const items = ref<XhsProduct[]>([])
const loading = ref(false)

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

async function retry(productId: string) {
  try {
    const summary = await collectXhsProduct(productId)
    toast({
      title: summary.stopped ? t('xhs.stopped') : t('xhs.retryDone'),
      variant: summary.stopped ? 'destructive' : 'default',
    })
    await load()
  } catch (error) {
    toast({ title: t('common.error'), description: error instanceof Error ? error.message : t('xhs.collectFailed'), variant: 'destructive' })
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

onMounted(load)
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
              <Button size="sm" variant="outline" @click="retry(item.id)">{{ t('xhs.retry') }}</Button>
              <Button size="sm" variant="ghost" @click="ignore(item.id)">{{ t('xhs.ignore') }}</Button>
              <Button size="sm" variant="ghost" @click="remove(item.id)">{{ t('common.delete') }}</Button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
