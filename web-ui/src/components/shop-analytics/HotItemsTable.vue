<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import type { ShopAnalyticsHotItem } from '@/api/shopAnalytics'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

const props = defineProps<{
  rows: ShopAnalyticsHotItem[]
}>()

const { t } = useI18n()
const router = useRouter()

function formatCount(value: number | null | undefined) {
  if (value === null || value === undefined) return '—'
  return value.toLocaleString('zh-CN')
}

function openItem(row: ShopAnalyticsHotItem) {
  router.push({ name: 'SellerItemDetail', params: { itemId: row.item_id } })
}
</script>

<template>
  <Table>
    <TableHeader>
      <TableRow>
        <TableHead>{{ t('shopAnalytics.colTitle') }}</TableHead>
        <TableHead>{{ t('shopAnalytics.colShop') }}</TableHead>
        <TableHead>{{ t('shopAnalytics.colWant') }}</TableHead>
        <TableHead>{{ t('shopAnalytics.colView') }}</TableHead>
      </TableRow>
    </TableHeader>
    <TableBody>
      <TableRow
        v-for="row in props.rows"
        :key="row.item_id"
        class="cursor-pointer"
        @click="openItem(row)"
      >
        <TableCell>
          <span class="line-clamp-2 font-medium text-slate-800" :title="row.title || row.item_id">
            {{ row.title || row.item_id }}
          </span>
        </TableCell>
        <TableCell class="text-slate-600">{{ row.shop_name }}</TableCell>
        <TableCell>{{ formatCount(row.want_count) }}</TableCell>
        <TableCell class="font-semibold text-slate-800">{{ formatCount(row.view_count) }}</TableCell>
      </TableRow>
      <TableRow v-if="!props.rows.length">
        <TableCell colspan="4" class="py-8 text-center text-slate-400">
          {{ t('common.empty') }}
        </TableCell>
      </TableRow>
    </TableBody>
  </Table>
</template>
