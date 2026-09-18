<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import type { ShopAnalyticsShopRow } from '@/api/shopAnalytics'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

type SortKey = 'view' | 'want' | 'items'

const props = defineProps<{
  rows: ShopAnalyticsShopRow[]
}>()

const { t } = useI18n()
const router = useRouter()
const sortKey = ref<SortKey>('view')
const sortDir = ref<'desc' | 'asc'>('desc')

function formatCount(value: number | null | undefined) {
  if (value === null || value === undefined) return '—'
  return value.toLocaleString('zh-CN')
}

function toggleSort(key: SortKey) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'desc' ? 'asc' : 'desc'
    return
  }
  sortKey.value = key
  sortDir.value = 'desc'
}

const sortedRows = computed(() => {
  const rows = [...props.rows]
  const getter: Record<SortKey, (row: ShopAnalyticsShopRow) => number> = {
    view: (row) => row.view_sum,
    want: (row) => row.want_sum,
    items: (row) => row.item_count,
  }
  const pick = getter[sortKey.value]
  rows.sort((left, right) => {
    const diff = pick(left) - pick(right)
    return sortDir.value === 'desc' ? -diff : diff
  })
  return rows
})

function sortMark(key: SortKey) {
  if (sortKey.value !== key) return '↕'
  return sortDir.value === 'desc' ? '↓' : '↑'
}

function openShop(row: ShopAnalyticsShopRow) {
  router.push({ name: 'SellerDetail', params: { sellerUserId: row.seller_user_id } })
}
</script>

<template>
  <Table>
    <TableHeader>
      <TableRow>
        <TableHead>{{ t('shopAnalytics.colShop') }}</TableHead>
        <TableHead>
          <button
            type="button"
            class="inline-flex items-center gap-1 font-medium hover:text-slate-900"
            @click="toggleSort('items')"
          >
            {{ t('shopAnalytics.colItems') }}
            <span aria-hidden="true">{{ sortMark('items') }}</span>
          </button>
        </TableHead>
        <TableHead>
          <button
            type="button"
            class="inline-flex items-center gap-1 font-medium hover:text-slate-900"
            @click="toggleSort('want')"
          >
            {{ t('shopAnalytics.colWant') }}
            <span aria-hidden="true">{{ sortMark('want') }}</span>
          </button>
        </TableHead>
        <TableHead>
          <button
            type="button"
            class="inline-flex items-center gap-1 font-medium hover:text-slate-900"
            @click="toggleSort('view')"
          >
            {{ t('shopAnalytics.colView') }}
            <span aria-hidden="true">{{ sortMark('view') }}</span>
          </button>
        </TableHead>
        <TableHead class="text-right">{{ t('shopAnalytics.viewShop') }}</TableHead>
      </TableRow>
    </TableHeader>
    <TableBody>
      <TableRow
        v-for="row in sortedRows"
        :key="row.seller_user_id"
        class="cursor-pointer"
        @click="openShop(row)"
      >
        <TableCell>
          <div class="flex flex-wrap items-center gap-2">
            <span class="font-medium text-slate-800">{{ row.shop_name }}</span>
            <Badge v-if="!row.enabled" variant="outline">{{ t('common.disabled') }}</Badge>
          </div>
        </TableCell>
        <TableCell>{{ formatCount(row.item_count) }}</TableCell>
        <TableCell>{{ formatCount(row.want_sum) }}</TableCell>
        <TableCell class="font-semibold text-slate-800">{{ formatCount(row.view_sum) }}</TableCell>
        <TableCell class="text-right text-primary">→</TableCell>
      </TableRow>
      <TableRow v-if="!sortedRows.length">
        <TableCell colspan="5" class="py-8 text-center text-slate-400">
          {{ t('common.empty') }}
        </TableCell>
      </TableRow>
    </TableBody>
  </Table>
</template>
