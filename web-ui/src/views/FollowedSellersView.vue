<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import * as sellersApi from '@/api/sellers'
import type { FollowedSeller } from '@/api/sellers'
import { Button } from '@/components/ui/button'
import { toast } from '@/components/ui/toast'
import { formatDateTime } from '@/i18n'
import { UserCheck, RefreshCw, Trash2, MapPin, Package, TrendingUp, Star } from 'lucide-vue-next'

const { t } = useI18n()
const router = useRouter()
const sellers = ref<FollowedSeller[]>([])
const isLoading = ref(false)
const refreshingId = ref<string | null>(null)

async function load() {
  isLoading.value = true
  try {
    const res = await sellersApi.listSellers()
    sellers.value = res.items || []
  } catch (e: any) {
    toast({ title: '加载失败', description: e?.message || String(e), variant: 'destructive' })
  } finally {
    isLoading.value = false
  }
}

async function refreshOne(sid: string) {
  refreshingId.value = sid
  try {
    await sellersApi.refreshSeller(sid)
    toast({ title: '刷新已启动' })
    setTimeout(load, 3000)
  } catch (e: any) {
    toast({ title: '刷新失败', description: e?.message, variant: 'destructive' })
  } finally {
    refreshingId.value = null
  }
}

async function refreshAll() {
  isLoading.value = true
  try {
    await sellersApi.refreshAllSellers()
    toast({ title: '全部刷新已启动' })
    setTimeout(load, 5000)
  } catch (e: any) {
    toast({ title: '刷新失败', description: e?.message, variant: 'destructive' })
  } finally {
    isLoading.value = false
  }
}

async function unfollow(sid: string) {
  if (!confirm('确认取消关注？')) return
  try {
    await sellersApi.unfollowSeller(sid)
    sellers.value = sellers.value.filter(s => s.seller_id !== sid)
    toast({ title: '已取消关注' })
  } catch (e: any) {
    toast({ title: '操作失败', description: e?.message, variant: 'destructive' })
  }
}

function statusColor(s: string) {
  if (s === 'done') return 'bg-emerald-50 text-emerald-600'
  if (s === 'failed') return 'bg-rose-50 text-rose-600'
  if (s === 'running') return 'bg-amber-50 text-amber-600'
  return 'bg-slate-100 text-slate-500'
}

onMounted(load)
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center gap-3">
      <UserCheck class="w-6 h-6 text-primary" />
      <h1 class="text-2xl font-bold text-slate-800">{{ t('sellers.title') }}</h1>
      <div class="ml-auto">
        <Button variant="outline" size="sm" :disabled="isLoading" @click="refreshAll">
          <RefreshCw class="w-4 h-4 mr-1" :class="{ 'animate-spin': isLoading }" />{{ t('sellers.refreshAll') }}
        </Button>
      </div>
    </div>

    <div v-if="isLoading && sellers.length === 0" class="app-surface p-8 text-center text-slate-500">{{ t('common.loading') }}</div>

    <div v-else-if="sellers.length === 0" class="app-surface p-12 text-center">
      <UserCheck class="w-12 h-12 mx-auto text-slate-300 mb-3" />
      <p class="text-slate-400">{{ t('sellers.empty') }}</p>
    </div>

    <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <div v-for="s in sellers" :key="s.seller_id"
        class="app-surface p-5 cursor-pointer hover:shadow-md transition-shadow"
        @click="router.push({ name: 'SellerDetail', params: { sellerId: s.seller_id } })">
        <div class="flex items-start gap-3 mb-3">
          <img v-if="s.portrait_url" :src="s.portrait_url" class="w-12 h-12 rounded-full object-cover" :alt="s.unique_name" />
          <div v-else class="w-12 h-12 rounded-full bg-slate-200 flex items-center justify-center"><UserCheck class="w-6 h-6 text-slate-400" /></div>
          <div class="flex-1 min-w-0">
            <p class="font-semibold text-slate-800 truncate">{{ s.unique_name || s.seller_id }}</p>
            <p v-if="s.city" class="text-xs text-slate-500 flex items-center gap-1"><MapPin class="w-3 h-3" />{{ s.city }}</p>
          </div>
          <span class="px-2 py-0.5 rounded text-xs font-medium shrink-0" :class="statusColor(s.last_fetch_status)">{{ s.last_fetch_status }}</span>
        </div>

        <p v-if="s.xianyu_summary" class="text-xs text-slate-500 mb-3 line-clamp-2">{{ s.xianyu_summary }}</p>

        <div class="grid grid-cols-3 gap-2 text-center text-sm mb-3">
          <div><Package class="w-4 h-4 mx-auto text-slate-400 mb-0.5" /><p class="font-bold text-slate-700">{{ s.item_count ?? '—' }}</p><p class="text-xs text-slate-400">在售</p></div>
          <div><TrendingUp class="w-4 h-4 mx-auto text-slate-400 mb-0.5" /><p class="font-bold text-slate-700">{{ s.has_sold_num ?? '—' }}</p><p class="text-xs text-slate-400">已售</p></div>
          <div><Star class="w-4 h-4 mx-auto text-amber-400 mb-0.5" /><p class="font-bold text-slate-700">{{ s.new_good_ratio_rate || '—' }}</p><p class="text-xs text-slate-400">好评</p></div>
        </div>

        <div class="flex items-center justify-between text-xs text-slate-400">
          <span v-if="s.last_fetch_at">{{ formatDateTime(s.last_fetch_at) }}</span>
          <span v-else>未拉取</span>
          <span class="font-mono">{{ s.cron }}</span>
        </div>

        <div class="flex gap-2 mt-3" @click.stop>
          <Button variant="outline" size="sm" class="flex-1" :disabled="refreshingId === s.seller_id" @click="refreshOne(s.seller_id)">
            <RefreshCw class="w-3.5 h-3.5 mr-1" :class="{ 'animate-spin': refreshingId === s.seller_id }" />刷新
          </Button>
          <Button variant="outline" size="sm" @click="unfollow(s.seller_id)">
            <Trash2 class="w-3.5 h-3.5" />
          </Button>
        </div>
      </div>
    </div>
  </div>
</template>
