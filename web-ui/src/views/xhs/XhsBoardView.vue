<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  collectAllXhs,
  collectXhsProduct,
  listXhsProducts,
  removeXhsProduct,
  updateXhsLabels,
  xhsCoverSrc,
  type XhsProduct,
} from '@/api/xhs'
import { Button } from '@/components/ui/button'
import { toast } from '@/components/ui/toast'

const { t } = useI18n()
const items = ref<XhsProduct[]>([])
const categoryFilter = ref('')
const loading = ref(false)

const categories = computed(() => {
  const names = new Set<string>()
  for (const item of items.value) {
    if (item.category) names.add(item.category)
  }
  return [...names]
})

const visibleItems = computed(() => {
  if (!categoryFilter.value) return items.value
  return items.value.filter((item) => item.category === categoryFilter.value)
})

function showDelta(value: number | null | undefined, incomplete?: boolean) {
  if (value === null || value === undefined) return '—'
  const text = value > 0 ? `+${value}` : String(value)
  return incomplete ? `${text}*` : text
}

async function load() {
  loading.value = true
  try {
    items.value = await listXhsProducts()
  } catch (error) {
    toast({ title: t('common.error'), description: error instanceof Error ? error.message : t('xhs.loadFailed'), variant: 'destructive' })
  } finally {
    loading.value = false
  }
}

async function saveLabels(item: XhsProduct, patch: { shop_name?: string | null; category?: string | null; tags?: string[] }) {
  try {
    await updateXhsLabels(item.id, {
      shop_name: patch.shop_name === undefined ? item.assigned_shop_name || null : patch.shop_name,
      category: patch.category === undefined ? item.category || null : patch.category,
      tags: patch.tags ?? item.tags ?? [],
    })
    await load()
  } catch (error) {
    toast({ title: t('common.error'), description: error instanceof Error ? error.message : t('xhs.addFailed'), variant: 'destructive' })
  }
}

async function collectOne(productId: string) {
  try {
    const summary = await collectXhsProduct(productId)
    if (summary.stopped) {
      toast({ title: t('xhs.stopped'), variant: 'destructive' })
    }
    await load()
  } catch (error) {
    toast({ title: t('common.error'), description: error instanceof Error ? error.message : t('xhs.collectFailed'), variant: 'destructive' })
  }
}

async function collectAll() {
  try {
    const summary = await collectAllXhs()
    if (summary.stopped) {
      toast({ title: t('xhs.stopped'), variant: 'destructive' })
    } else {
      toast({ title: t('xhs.collected', { saved: summary.saved }) })
    }
    await load()
  } catch (error) {
    toast({ title: t('common.error'), description: error instanceof Error ? error.message : t('xhs.collectFailed'), variant: 'destructive' })
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
        <h1 class="text-xl font-semibold">{{ t('xhs.title') }}</h1>
        <p class="text-sm text-muted-foreground">{{ t('xhs.subtitle') }}</p>
      </div>
      <div class="flex flex-wrap gap-2">
        <Button as-child>
          <RouterLink to="/xhs/add">{{ t('xhs.addTitle') }}</RouterLink>
        </Button>
        <Button variant="outline" :disabled="loading" @click="collectAll">{{ t('xhs.collectAll') }}</Button>
      </div>
    </div>

    <div v-if="categories.length" class="flex flex-wrap gap-2">
      <Button size="sm" :variant="categoryFilter ? 'outline' : 'default'" @click="categoryFilter = ''">{{ t('xhs.filterAll') }}</Button>
      <Button
        v-for="name in categories"
        :key="name"
        size="sm"
        :variant="categoryFilter === name ? 'default' : 'outline'"
        @click="categoryFilter = name"
      >
        {{ name }}
      </Button>
    </div>

    <div class="overflow-x-auto rounded-lg border">
      <table class="w-full min-w-[760px] text-sm">
        <thead class="bg-muted/40 text-left">
          <tr>
            <th class="p-3">{{ t('xhs.colProduct') }}</th>
            <th class="p-3">{{ t('xhs.colSold') }}</th>
            <th class="p-3">{{ t('xhs.colToday') }}</th>
            <th class="p-3">{{ t('xhs.colYesterday') }}</th>
            <th class="p-3">{{ t('xhs.colHour') }}</th>
            <th class="p-3"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!visibleItems.length">
            <td class="p-4 text-muted-foreground" colspan="6">{{ loading ? t('xhs.loading') : t('xhs.empty') }}</td>
          </tr>
          <tr v-for="item in visibleItems" :key="item.id" class="border-t">
            <td class="p-3">
              <div class="flex items-center gap-2">
                <img
                  v-if="item.cover_url"
                  :src="xhsCoverSrc(item.cover_url)"
                  alt=""
                  class="h-10 w-10 rounded object-cover"
                />
                <div>
                  <RouterLink class="font-medium hover:underline" :to="`/xhs/${item.id}`">
                    {{ item.title || item.id }}
                  </RouterLink>
                  <div class="text-xs text-muted-foreground">
                    <span v-if="item.assigned_shop_name">{{ item.assigned_shop_name }}</span>
                    <span v-else>{{ t('xhs.unassigned') }}</span>
                    <span v-if="item.shop_name"> · {{ t('xhs.pageShop') }} {{ item.shop_name }}</span>
                    <span v-if="item.category"> · {{ item.category }}</span>
                  </div>
                  <div class="mt-1 flex flex-wrap items-center gap-1">
                    <button
                      v-for="tag in item.tags || []"
                      :key="tag"
                      type="button"
                      class="rounded-full bg-muted px-2 py-0.5 text-xs"
                      @click="saveLabels(item, { tags: (item.tags || []).filter((value) => value !== tag) })"
                    >
                      {{ tag }} ×
                    </button>
                    <input
                      class="h-7 w-24 rounded border bg-background px-2 text-xs"
                      :placeholder="t('xhs.addTag')"
                      @keyup.enter="saveLabels(item, { tags: [...(item.tags || []), ($event.target as HTMLInputElement).value.trim()].filter(Boolean) }); ($event.target as HTMLInputElement).value = ''"
                    />
                  </div>
                </div>
              </div>
            </td>
            <td class="p-3">{{ item.sold_total ?? '—' }}</td>
            <td class="p-3">{{ showDelta(item.today, item.today_incomplete) }}</td>
            <td class="p-3">{{ showDelta(item.yesterday, item.yesterday_incomplete) }}</td>
            <td class="p-3">{{ showDelta(item.last_hour, item.last_hour_incomplete) }}</td>
            <td class="p-3 text-right">
              <Button size="sm" variant="outline" @click="collectOne(item.id)">{{ t('xhs.collect') }}</Button>
              <Button size="sm" variant="ghost" @click="remove(item.id)">{{ t('common.delete') }}</Button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <p class="text-xs text-muted-foreground">{{ t('xhs.incompleteHint') }}</p>
  </div>
</template>
