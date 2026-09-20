<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import * as sellersApi from '@/api/sellers'
import type { FollowedSeller, SellerItem } from '@/api/sellers'
import { Button } from '@/components/ui/button'
import { toast } from '@/components/ui/toast'
import { ArrowLeft, RefreshCw, ExternalLink, Heart, Eye, Star, TrendingUp, MapPin, Package } from 'lucide-vue-next'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const seller = ref<FollowedSeller | null>(null)
const items = ref<SellerItem[]>([])
const isLoading = ref(false)
const isRefreshing = ref(false)
const sortBy = ref<'want_cnt' | 'browse_cnt' | 'sold_cnt' | 'price'>('want_cnt')

const sellerId = computed(() => String(route.params.sellerId || ''))

async function load() {
  isLoading.value = true
  try {
    const res = await sellersApi.getSeller(sellerId.value, sortBy.value)
    seller.value = res.seller
    items.value = res.items || []
  } catch (e: any) {
    toast({ title: '加载失败', description: e?.message, variant: 'destructive' })
  } finally {
    isLoading.value = false
  }
}

async function refresh() {
  isRefreshing.value = true
  try {
    await sellersApi.refreshSeller(sellerId.value)
    toast({ title: '刷新已启动' })
    setTimeout(load, 4000)
  } catch (e: any) {
    toast({ title: '刷新失败', description: e?.message, variant: 'destructive' })
  } finally {
    isRefreshing.value = false
  }
}

async function changeSort(s: typeof sortBy.value) {
  sortBy.value = s
  await load()
}

onMounted(load)
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center gap-3">
      <Button variant="outline" size="sm" @click="router.push({ name: 'FollowedSellers' })">
        <ArrowLeft class="w-4 h-4 mr-1" />{{ t('sellers.back') }}
      </Button>
      <h1 class="text-2xl font-bold text-slate-800">{{ t('sellers.detail') }}</h1>
      <div class="ml-auto">
        <Button variant="outline" size="sm" :disabled="isRefreshing" @click="refresh">
          <RefreshCw class="w-4 h-4 mr-1" :class="{ 'animate-spin': isRefreshing }" />{{ t('sellers.refresh') }}
        </Button>
      </div>
    </div>

    <div v-if="isLoading && !seller" class="app-surface p-8 text-center text-slate-500">{{ t('common.loading') }}</div>

    <template v-else-if="seller">
      <!-- Seller info card -->
      <div class="app-surface p-5">
        <div class="flex items-center gap-4 mb-4">
          <img v-if="seller.portrait_url" :src="seller.portrait_url" class="w-16 h-16 rounded-full object-cover" :alt="seller.unique_name" />
          <div v-else class="w-16 h-16 rounded-full bg-slate-200 flex items-center justify-center"><Package class="w-8 h-8 text-slate-400" /></div>
          <div class="flex-1">
            <h2 class="text-xl font-bold text-slate-800">{{ seller.unique_name || seller.seller_id }}</h2>
            <p v-if="seller.xianyu_summary" class="text-sm text-slate-500 mt-0.5">{{ seller.xianyu_summary }}</p>
            <div class="flex items-center gap-3 mt-1 text-xs text-slate-400">
              <span v-if="seller.city" class="flex items-center gap-1"><MapPin class="w-3 h-3" />{{ seller.city }}</span>
              <span v-if="seller.user_reg_day">注册 {{ seller.user_reg_day }} 天</span>
              <span class="font-mono">cron: {{ seller.cron }}</span>
            </div>
          </div>
          <a :href="`https://www.goofish.com/personal?userId=${seller.seller_id}`" target="_blank" rel="noopener noreferrer"
            class="inline-flex items-center gap-1 text-xs text-blue-600 hover:underline">
            <ExternalLink class="w-3.5 h-3.5" />个人主页
          </a>
        </div>
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
          <div class="bg-slate-50 rounded-lg p-3 text-center"><Package class="w-4 h-4 mx-auto text-slate-400 mb-1" /><p class="text-lg font-bold text-slate-700">{{ seller.item_count ?? '—' }}</p><p class="text-xs text-slate-400">在售</p></div>
          <div class="bg-slate-50 rounded-lg p-3 text-center"><TrendingUp class="w-4 h-4 mx-auto text-slate-400 mb-1" /><p class="text-lg font-bold text-slate-700">{{ seller.has_sold_num ?? '—' }}</p><p class="text-xs text-slate-400">已售</p></div>
          <div class="bg-slate-50 rounded-lg p-3 text-center"><Star class="w-4 h-4 mx-auto text-amber-400 mb-1" /><p class="text-lg font-bold text-slate-700">{{ seller.new_good_ratio_rate || '—' }}</p><p class="text-xs text-slate-400">好评率</p></div>
          <div class="bg-slate-50 rounded-lg p-3 text-center"><Heart class="w-4 h-4 mx-auto text-rose-400 mb-1" /><p class="text-lg font-bold text-slate-700">{{ seller.remark_good_cnt ?? '—' }}</p><p class="text-xs text-slate-400">好评数</p></div>
        </div>
      </div>

      <!-- Sort tabs -->
      <div class="flex gap-2">
        <Button v-for="opt in [{k:'want_cnt',l:'想要数'},{k:'browse_cnt',l:'浏览数'},{k:'sold_cnt',l:'已售数'},{k:'price',l:'价格'}]" :key="opt.k"
          :variant="sortBy === opt.k ? 'default' : 'outline'" size="sm" @click="changeSort(opt.k as any)">
          {{ opt.l }}
        </Button>
      </div>

      <!-- Items grid -->
      <div v-if="items.length === 0 && !isLoading" class="app-surface p-8 text-center text-slate-500">
        暂无商品数据，请点击"刷新"拉取
      </div>
      <div v-else class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
        <a v-for="item in items" :key="item.item_id"
          :href="`https://www.goofish.com/item?id=${item.item_id}`" target="_blank" rel="noopener noreferrer"
          class="app-surface overflow-hidden hover:shadow-md transition-shadow block">
          <div class="aspect-square bg-slate-100">
            <img v-if="item.pic_url" :src="item.pic_url" class="w-full h-full object-cover" :alt="item.title" />
          </div>
          <div class="p-3 space-y-2">
            <p class="text-sm text-slate-700 line-clamp-2">{{ item.title }}</p>
            <p class="text-rose-600 font-bold text-lg">{{ item.price ? `¥${item.price}` : '—' }}</p>
            <div class="flex items-center gap-3 text-xs text-slate-400">
              <span v-if="item.want_cnt !== null && item.want_cnt !== undefined" class="flex items-center gap-1"><Heart class="w-3 h-3" />{{ item.want_cnt }}</span>
              <span v-if="item.browse_cnt !== null && item.browse_cnt !== undefined" class="flex items-center gap-1"><Eye class="w-3 h-3" />{{ item.browse_cnt }}</span>
              <span v-if="item.sold_cnt" class="flex items-center gap-1"><TrendingUp class="w-3 h-3" />{{ item.sold_cnt }}</span>
              <span v-if="item.status" class="ml-auto px-1.5 py-0.5 rounded text-xs" :class="item.status === '在售' ? 'bg-emerald-50 text-emerald-600' : 'bg-slate-100 text-slate-500'">{{ item.status }}</span>
            </div>
          </div>
        </a>
      </div>
    </template>
  </div>
</template>
