<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  getSellerMetricItems,
  type SellerItemsSortBy,
  type SellerItemsSortOrder,
  type SellerMetricItem,
} from '@/api/sellerSubscriptions'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Search, LineChart } from 'lucide-vue-next'
import PaginationBar from '@/components/common/PaginationBar.vue'
import { formatShanghaiTime } from '@/lib/datetime'

const props = defineProps<{
  sellerId?: string
  showSeller?: boolean
  sellerNameMap?: Record<string, string>
}>()

const emit = defineEmits<{
  (e: 'item-click', item: SellerMetricItem): void
}>()

const { t } = useI18n()
const items = ref<SellerMetricItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const search = ref('')
const sortBy = ref<SellerItemsSortBy>('snapshot_time')
const sortOrder = ref<SellerItemsSortOrder>('desc')
const isLoading = ref(false)
const loadError = ref('')
let searchTimer: ReturnType<typeof setTimeout> | null = null

function formatPrice(value?: number | null) {
  if (value === null || value === undefined) return '-'
  return Number.isInteger(value) ? String(value) : value.toFixed(2)
}

async function load() {
  isLoading.value = true
  loadError.value = ''
  try {
    const res = await getSellerMetricItems({
      sellerId: props.sellerId,
      page: page.value,
      pageSize: pageSize.value,
      search: search.value.trim() || undefined,
      sortBy: sortBy.value,
      sortOrder: sortOrder.value,
    })
    items.value = res.items || []
    total.value = res.total || 0
  } catch (e) {
    items.value = []
    total.value = 0
    loadError.value = (e as Error).message
  } finally {
    isLoading.value = false
  }
}

function toggleSort(column: SellerItemsSortBy) {
  if (sortBy.value === column) {
    sortOrder.value = sortOrder.value === 'desc' ? 'asc' : 'desc'
  } else {
    sortBy.value = column
    sortOrder.value = 'desc'
  }
  page.value = 1
  load()
}

function onSearchInput() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    page.value = 1
    load()
  }, 300)
}

function onPageChange(nextPage: number) {
  page.value = nextPage
  load()
}

function onPageSizeChange(size: number) {
  pageSize.value = size
  page.value = 1
  load()
}

// 删除/筛选后当前页可能超出范围，自动回退到最后一页
watch([total, pageSize], () => {
  const maxPage = Math.max(1, Math.ceil(total.value / pageSize.value))
  if (page.value > maxPage) {
    page.value = maxPage
    load()
  }
})

watch(
  () => props.sellerId,
  () => {
    page.value = 1
    search.value = ''
    load()
  },
)

onMounted(load)
</script>

<template>
  <div>
    <div class="mb-3 flex flex-wrap items-center gap-2">
      <div class="relative">
        <Search class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <Input
          v-model="search"
          class="h-9 w-64 pl-9"
          :placeholder="t('sellerSubscription.searchItems')"
          @input="onSearchInput"
        />
      </div>
      <div class="ml-auto flex items-center gap-2 text-sm text-slate-500">
        <span>{{ t('sellerSubscription.colPrice') }}</span>
        <Button
          variant="outline"
          size="sm"
          class="h-8 px-2 text-xs"
          :class="sortBy === 'price' ? 'border-primary text-primary' : ''"
          @click="toggleSort('price')"
        >
          {{ sortBy === 'price' ? (sortOrder === 'desc' ? '↓' : '↑') : '↕' }}
        </Button>
        <span>{{ t('sellerSubscription.colWant') }}</span>
        <Button
          variant="outline"
          size="sm"
          class="h-8 px-2 text-xs"
          :class="sortBy === 'want_count' ? 'border-primary text-primary' : ''"
          @click="toggleSort('want_count')"
        >
          {{ sortBy === 'want_count' ? (sortOrder === 'desc' ? '↓' : '↑') : '↕' }}
        </Button>
        <span>{{ t('sellerSubscription.colView') }}</span>
        <Button
          variant="outline"
          size="sm"
          class="h-8 px-2 text-xs"
          :class="sortBy === 'view_count' ? 'border-primary text-primary' : ''"
          @click="toggleSort('view_count')"
        >
          {{ sortBy === 'view_count' ? (sortOrder === 'desc' ? '↓' : '↑') : '↕' }}
        </Button>
      </div>
    </div>

    <p v-if="loadError" class="mb-3 text-sm text-rose-600">{{ loadError }}</p>

    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="text-left text-slate-500">
            <th v-if="props.showSeller" class="py-2">{{ t('sellerSubscription.colSeller') }}</th>
            <th class="py-2">{{ t('sellerSubscription.colTitle') }}</th>
            <th class="cursor-pointer" @click="toggleSort('price')">
              {{ t('sellerSubscription.colPrice') }}
              <span class="text-xs">{{ sortBy === 'price' ? (sortOrder === 'desc' ? '↓' : '↑') : '↕' }}</span>
            </th>
            <th class="cursor-pointer" @click="toggleSort('want_count')">
              {{ t('sellerSubscription.colWant') }}
              <span class="text-xs">{{ sortBy === 'want_count' ? (sortOrder === 'desc' ? '↓' : '↑') : '↕' }}</span>
            </th>
            <th class="cursor-pointer" @click="toggleSort('view_count')">
              {{ t('sellerSubscription.colView') }}
              <span class="text-xs">{{ sortBy === 'view_count' ? (sortOrder === 'desc' ? '↓' : '↑') : '↕' }}</span>
            </th>
            <th>{{ t('sellerSubscription.colStatus') }}</th>
            <th>{{ t('sellerSubscription.colSnapshot') }}</th>
            <th class="text-right">{{ t('sellerSubscription.colActions') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="isLoading" class="border-t border-slate-100">
            <td :colspan="props.showSeller ? 8 : 7" class="py-8 text-center text-slate-400">{{ t('common.loading') }}</td>
          </tr>
          <tr
            v-for="item in items"
            :key="`${item.item_id}-${item.snapshot_time}`"
            class="cursor-pointer border-t border-slate-100 hover:bg-slate-50"
            @click="emit('item-click', item)"
          >
            <td v-if="props.showSeller" class="whitespace-nowrap py-2 pr-3 text-xs text-slate-500">
              {{ props.sellerNameMap?.[item.seller_user_id] || item.seller_user_id }}
            </td>
            <td class="max-w-[280px] py-2 pr-3 font-medium text-primary">
              <span class="line-clamp-1 hover:underline">{{ item.title || item.item_id }}</span>
            </td>
            <td>{{ formatPrice(item.price) }}</td>
            <td>{{ item.want_count ?? '-' }}</td>
            <td>{{ item.view_count ?? '-' }}</td>
            <td>
              <Badge v-if="item.item_status" variant="secondary">{{ item.item_status }}</Badge>
              <span v-else>-</span>
            </td>
            <td class="whitespace-nowrap text-xs text-slate-500">{{ formatShanghaiTime(item.snapshot_time) }}</td>
            <td class="text-right">
              <Button size="sm" variant="ghost" class="h-8 gap-1 text-xs" @click.stop="emit('item-click', item)">
                <LineChart class="h-3.5 w-3.5" />
                {{ t('sellerSubscription.viewHistory') }}
              </Button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-if="!isLoading && !items.length" class="py-8 text-center text-slate-400">
        {{ t('sellerSubscription.empty') }}
      </p>
    </div>

    <div v-if="total > pageSize" class="mt-4 border-t border-slate-100 pt-3">
      <PaginationBar
        :page="page"
        :page-size="pageSize"
        :total="total"
        @update:page="onPageChange"
        @update:page-size="onPageSizeChange"
      />
    </div>
  </div>
</template>
