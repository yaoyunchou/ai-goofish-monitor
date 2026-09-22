<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { listXhsDelisted, type XhsProduct } from '@/api/xhs'
import { toast } from '@/components/ui/toast'
import { formatDateTime } from '@/i18n'

const { t } = useI18n()
const items = ref<XhsProduct[]>([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    items.value = await listXhsDelisted()
  } catch (error) {
    toast({ title: t('common.error'), description: error instanceof Error ? error.message : t('xhs.loadFailed'), variant: 'destructive' })
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="space-y-4 p-4">
    <div>
      <h1 class="text-xl font-semibold">{{ t('xhs.delistedTitle') }}</h1>
      <p class="text-sm text-muted-foreground">{{ t('xhs.delistedHint') }}</p>
    </div>
    <div class="overflow-x-auto rounded-lg border">
      <table class="w-full min-w-[640px] text-sm">
        <thead class="bg-muted/40 text-left">
          <tr>
            <th class="p-3">{{ t('xhs.colProduct') }}</th>
            <th class="p-3">{{ t('xhs.colId') }}</th>
            <th class="p-3">{{ t('xhs.colDelistedAt') }}</th>
            <th class="p-3">{{ t('xhs.colDelistStatus') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!items.length">
            <td class="p-4 text-muted-foreground" colspan="4">{{ loading ? t('xhs.loading') : t('xhs.delistedEmpty') }}</td>
          </tr>
          <tr v-for="item in items" :key="item.id" class="border-t">
            <td class="p-3">
              <RouterLink class="font-medium hover:underline" :to="`/xhs/${item.id}`">{{ item.title || item.id }}</RouterLink>
              <div class="text-xs text-muted-foreground">{{ item.assigned_shop_name || item.shop_name || t('xhs.unassigned') }}</div>
            </td>
            <td class="p-3 font-mono text-xs">{{ item.id }}</td>
            <td class="p-3">{{ item.updated_at ? formatDateTime(item.updated_at) : '—' }}</td>
            <td class="p-3">{{ item.last_error || t('xhs.delistedStatus') }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
