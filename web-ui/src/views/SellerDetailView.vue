<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  getItemMetricHistory,
  getSellerDetail,
  getSellerMetricItems,
  updateSellerSubscription,
  type SellerDetail,
  type SellerMetricHistoryPoint,
  type SellerMetricItem,
} from '@/api/sellerSubscriptions'
import { formatShanghaiTime } from '@/lib/datetime'
import { normalizeSubscriptionEnabled } from '@/lib/subscription'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { toast } from '@/components/ui/toast'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs'
import { ArrowLeft, ExternalLink } from 'lucide-vue-next'
import SellerItemsTable from '@/components/sellers/SellerItemsTable.vue'
import ItemTrendChart, { type ItemTrendPoint } from '@/components/sellers/ItemTrendChart.vue'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const sellerUserId = computed(() => String(route.params.sellerUserId || ''))
const activeTab = ref<string>(String(route.query.tab || 'items'))
const detail = ref<SellerDetail | null>(null)
const isLoading = ref(false)
const loadError = ref('')

const isNoteDialogOpen = ref(false)
const noteInput = ref('')
const isNoteSaving = ref(false)

// 指标历史 tab
const historyItems = ref<SellerMetricItem[]>([])
const selectedItemId = ref('')
const historyPoints = ref<SellerMetricHistoryPoint[]>([])
const historyLoading = ref(false)

const subscription = computed(() => detail.value?.subscription ?? null)
const profile = computed(() => detail.value?.profile ?? null)

const displayName = computed(() =>
  profile.value?.nickname || subscription.value?.nickname || sellerUserId.value,
)

const profileMeta = computed(() => {
  const json = (profile.value?.profile_json ?? {}) as Record<string, unknown>
  return [
    { label: t('sellerSubscription.profileSignature'), value: json['卖家个性签名'] },
    { label: t('sellerSubscription.profileCredit'), value: json['卖家信用等级'] },
    { label: t('sellerSubscription.profileScore'), value: json['店铺积分'] },
    { label: t('sellerSubscription.profileFollowing'), value: json['关注数'] },
  ].filter((item) => item.value !== undefined && item.value !== null && item.value !== '')
})

const selectedItemTitle = computed(() =>
  historyItems.value.find((item) => item.item_id === selectedItemId.value)?.title || '',
)

const trendPoints = computed<ItemTrendPoint[]>(() =>
  historyPoints.value.map((point) => ({
    date: point.snapshot_time || '',
    want: point.want_count ?? null,
    view: point.view_count ?? null,
  })),
)

async function loadDetail() {
  isLoading.value = true
  loadError.value = ''
  try {
    const res = await getSellerDetail(sellerUserId.value)
    if (res.subscription) {
      res.subscription.enabled = normalizeSubscriptionEnabled(res.subscription.enabled)
    }
    detail.value = res
  } catch (e) {
    detail.value = null
    loadError.value = (e as Error).message
  } finally {
    isLoading.value = false
  }
}

async function loadHistoryItems() {
  try {
    const res = await getSellerMetricItems({
      sellerId: sellerUserId.value,
      page: 1,
      pageSize: 100,
      sortBy: 'want_count',
      sortOrder: 'desc',
    })
    historyItems.value = res.items || []
    const firstItem = historyItems.value[0]
    if (!selectedItemId.value && firstItem) {
      selectedItemId.value = firstItem.item_id
    }
    if (selectedItemId.value) await loadHistory()
  } catch {
    historyItems.value = []
  }
}

async function loadHistory() {
  if (!selectedItemId.value) {
    historyPoints.value = []
    return
  }
  historyLoading.value = true
  try {
    const res = await getItemMetricHistory(selectedItemId.value)
    historyPoints.value = res.items || []
  } catch {
    historyPoints.value = []
  } finally {
    historyLoading.value = false
  }
}

const isTogglingEnabled = ref(false)

async function setEnabled(enabled: boolean) {
  const sub = subscription.value
  if (!sub || sub.enabled === enabled || isTogglingEnabled.value) return
  isTogglingEnabled.value = true
  try {
    const result = await updateSellerSubscription(sub.id, { enabled })
    sub.enabled = normalizeSubscriptionEnabled(result.item.enabled)
    toast({
      title: enabled
        ? t('sellerSubscription.collectEnabledToast', { name: displayName.value })
        : t('sellerSubscription.collectDisabledToast', { name: displayName.value }),
      description: t('sellerSubscription.collectToggleHint'),
    })
  } catch (e) {
    toast({ title: t('common.error'), description: (e as Error).message, variant: 'destructive' })
  } finally {
    isTogglingEnabled.value = false
  }
}

function openNoteDialog() {
  noteInput.value = subscription.value?.note || ''
  isNoteDialogOpen.value = true
}

async function saveNote() {
  const sub = subscription.value
  if (!sub) return
  isNoteSaving.value = true
  try {
    await updateSellerSubscription(sub.id, { note: noteInput.value.trim() })
    sub.note = noteInput.value.trim()
    toast({ title: t('sellerSubscription.noteSaved') })
    isNoteDialogOpen.value = false
  } catch (e) {
    toast({ title: t('common.error'), description: (e as Error).message, variant: 'destructive' })
  } finally {
    isNoteSaving.value = false
  }
}

function onItemClick(item: SellerMetricItem) {
  router.push({
    name: 'SellerItemDetail',
    params: { itemId: item.item_id },
    query: { from: 'seller', sellerUserId: sellerUserId.value },
  })
}

watch(activeTab, (tab) => {
  router.replace({ query: { ...route.query, tab } })
})

onMounted(() => {
  loadDetail()
  loadHistoryItems()
})
</script>

<template>
  <div class="space-y-6">
    <div class="flex flex-wrap items-center gap-2">
      <Button variant="ghost" size="sm" class="gap-1" @click="router.push('/seller-subscriptions/sellers')">
        <ArrowLeft class="h-4 w-4" />
        {{ t('common.back') }}
      </Button>
      <h1 class="text-2xl font-black text-slate-900">{{ t('sellerSubscription.detailTitle') }}</h1>
    </div>

    <p v-if="loadError" class="text-sm text-rose-600">{{ loadError }}</p>

    <Card v-if="isLoading" class="app-surface border-none">
      <CardContent class="py-10 text-center text-sm text-slate-400">{{ t('common.loading') }}</CardContent>
    </Card>

    <template v-else-if="detail && subscription">
      <Card class="app-surface border-none">
        <CardContent class="p-5">
          <div class="flex flex-wrap items-start justify-between gap-4">
            <div class="flex items-start gap-4">
              <div class="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 text-xl font-black text-primary">
                {{ (displayName || '?').slice(0, 1).toUpperCase() }}
              </div>
              <div>
                <div class="flex flex-wrap items-center gap-2">
                  <h2 class="text-xl font-black text-slate-900">{{ displayName }}</h2>
                  <Badge v-if="profile?.shop_level" variant="secondary">{{ profile.shop_level }}</Badge>
                  <Badge :variant="subscription.enabled ? 'default' : 'secondary'">
                    {{ subscription.enabled ? t('common.enabled') : t('common.disabled') }}
                  </Badge>
                </div>
                <p class="mt-1 font-mono text-xs text-slate-500">{{ subscription.seller_user_id }}</p>
                <p v-if="subscription.note" class="mt-1 text-sm text-slate-500">{{ subscription.note }}</p>
              </div>
            </div>
            <div class="flex flex-wrap items-center gap-2">
              <div
                class="flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2"
                :title="t('sellerSubscription.collectToggleHint')"
              >
                <Switch
                  :model-value="normalizeSubscriptionEnabled(subscription.enabled)"
                  :disabled="isTogglingEnabled"
                  @update:model-value="setEnabled"
                />
                <div>
                  <p class="text-xs font-medium text-slate-700">
                    {{
                      subscription.enabled
                        ? t('sellerSubscription.collectEnabled')
                        : t('sellerSubscription.collectDisabled')
                    }}
                  </p>
                  <p class="text-[11px] text-slate-400">{{ t('sellerSubscription.collectToggleLabel') }}</p>
                </div>
              </div>
              <Button variant="outline" size="sm" @click="openNoteDialog">{{ t('common.editNote') }}</Button>
              <Button
                v-if="subscription.seller_url"
                variant="outline"
                size="sm"
                class="gap-1"
                as="a"
                :href="subscription.seller_url"
                target="_blank"
                rel="noopener"
              >
                <ExternalLink class="h-3.5 w-3.5" />
                {{ t('sellerSubscription.openProfile') }}
              </Button>
            </div>
          </div>

          <div class="mt-5 grid gap-3 text-center sm:grid-cols-2 lg:grid-cols-6">
            <div class="rounded-xl border border-slate-100 bg-slate-50/60 px-3 py-2">
              <p class="text-xs text-slate-400">{{ t('sellerSubscription.followers') }}</p>
              <p class="mt-1 text-lg font-black text-slate-800">{{ profile?.followers ?? '-' }}</p>
            </div>
            <div class="rounded-xl border border-slate-100 bg-slate-50/60 px-3 py-2">
              <p class="text-xs text-slate-400">{{ t('sellerSubscription.itemCount') }}</p>
              <p class="mt-1 text-lg font-black text-slate-800">{{ profile?.item_count ?? '-' }}</p>
            </div>
            <div class="rounded-xl border border-slate-100 bg-slate-50/60 px-3 py-2">
              <p class="text-xs text-slate-400">{{ t('sellerSubscription.praiseRatio') }}</p>
              <p class="mt-1 text-lg font-black text-slate-800">
                {{ profile?.praise_ratio != null ? `${profile.praise_ratio}%` : '-' }}
              </p>
            </div>
            <div class="rounded-xl border border-slate-100 bg-slate-50/60 px-3 py-2">
              <p class="text-xs text-slate-400">{{ t('sellerSubscription.ratingCount') }}</p>
              <p class="mt-1 text-lg font-black text-slate-800">{{ profile?.rating_count ?? '-' }}</p>
            </div>
            <div class="rounded-xl border border-slate-100 bg-slate-50/60 px-3 py-2">
              <p class="text-xs text-slate-400">{{ t('sellerSubscription.colLastCaptured') }}</p>
              <p class="mt-1 text-sm font-bold text-slate-800">
                {{ formatShanghaiTime(profile?.captured_at || subscription.last_captured_at) }}
              </p>
            </div>
            <div class="rounded-xl border border-slate-100 bg-slate-50/60 px-3 py-2">
              <p class="text-xs text-slate-400">{{ t('sellerSubscription.profileCapturedAt') }}</p>
              <p class="mt-1 text-sm font-bold text-slate-800">{{ formatShanghaiTime(profile?.captured_at) }}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Tabs v-model="activeTab" class="w-full">
        <TabsList class="mb-4 flex w-full gap-1 overflow-x-auto">
          <TabsTrigger value="items">{{ t('sellerSubscription.tabItems') }}</TabsTrigger>
          <TabsTrigger value="history">{{ t('sellerSubscription.tabHistory') }}</TabsTrigger>
          <TabsTrigger value="profile">{{ t('sellerSubscription.tabProfile') }}</TabsTrigger>
        </TabsList>

        <TabsContent value="items">
          <Card class="app-surface border-none">
            <CardHeader>
              <CardTitle class="text-base">{{ t('sellerSubscription.itemsTitle') }}</CardTitle>
            </CardHeader>
            <CardContent>
              <SellerItemsTable :seller-id="sellerUserId" @item-click="onItemClick" />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="history">
          <Card class="app-surface border-none">
            <CardHeader>
              <CardTitle class="text-base">{{ t('sellerSubscription.tabHistory') }}</CardTitle>
            </CardHeader>
            <CardContent>
              <div class="mb-4 flex flex-wrap items-center gap-3">
                <Label class="shrink-0">{{ t('sellerSubscription.selectItem') }}</Label>
                <select
                  v-model="selectedItemId"
                  class="h-9 min-w-[260px] flex-1 rounded-md border bg-white px-3 text-sm"
                  @change="loadHistory"
                >
                  <option v-for="item in historyItems" :key="item.item_id" :value="item.item_id">
                    {{ item.title || item.item_id }}
                  </option>
                </select>
              </div>

              <p v-if="historyLoading" class="py-8 text-center text-sm text-slate-400">{{ t('common.loading') }}</p>
              <template v-else-if="selectedItemId">
                <p v-if="selectedItemTitle" class="mb-3 text-sm font-medium text-slate-700">{{ selectedItemTitle }}</p>
                <ItemTrendChart :points="trendPoints" />
                <p v-if="!trendPoints.length" class="mt-2 text-center text-xs text-slate-400">
                  {{ t('sellerSubscription.noHistory') }}
                </p>
              </template>
              <p v-else class="py-8 text-center text-sm text-slate-400">
                {{ t('sellerSubscription.noItemsForHistory') }}
              </p>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="profile">
          <Card class="app-surface border-none">
            <CardHeader>
              <CardTitle class="text-base">{{ t('sellerSubscription.tabProfile') }}</CardTitle>
            </CardHeader>
            <CardContent>
              <div v-if="profileMeta.length || profile" class="grid gap-3 sm:grid-cols-2">
                <div class="rounded-xl border border-slate-100 px-4 py-3">
                  <p class="text-xs text-slate-400">{{ t('sellerSubscription.shopLevel') }}</p>
                  <p class="mt-1 text-sm font-semibold text-slate-800">{{ profile?.shop_level || '-' }}</p>
                </div>
                <div class="rounded-xl border border-slate-100 px-4 py-3">
                  <p class="text-xs text-slate-400">{{ t('sellerSubscription.praiseRatio') }}</p>
                  <p class="mt-1 text-sm font-semibold text-slate-800">
                    {{ profile?.praise_ratio != null ? `${profile.praise_ratio}%` : '-' }}
                  </p>
                </div>
                <div class="rounded-xl border border-slate-100 px-4 py-3">
                  <p class="text-xs text-slate-400">{{ t('sellerSubscription.followers') }}</p>
                  <p class="mt-1 text-sm font-semibold text-slate-800">{{ profile?.followers ?? '-' }}</p>
                </div>
                <div class="rounded-xl border border-slate-100 px-4 py-3">
                  <p class="text-xs text-slate-400">{{ t('sellerSubscription.itemCount') }}</p>
                  <p class="mt-1 text-sm font-semibold text-slate-800">{{ profile?.item_count ?? '-' }}</p>
                </div>
                <div class="rounded-xl border border-slate-100 px-4 py-3">
                  <p class="text-xs text-slate-400">{{ t('sellerSubscription.ratingCount') }}</p>
                  <p class="mt-1 text-sm font-semibold text-slate-800">{{ profile?.rating_count ?? '-' }}</p>
                </div>
                <div class="rounded-xl border border-slate-100 px-4 py-3">
                  <p class="text-xs text-slate-400">{{ t('sellerSubscription.colSnapshot') }}</p>
                  <p class="mt-1 text-sm font-semibold text-slate-800">{{ formatShanghaiTime(profile?.captured_at) }}</p>
                </div>
                <div
                  v-for="item in profileMeta"
                  :key="item.label"
                  class="rounded-xl border border-slate-100 px-4 py-3"
                >
                  <p class="text-xs text-slate-400">{{ item.label }}</p>
                  <p class="mt-1 text-sm font-semibold text-slate-800">{{ String(item.value) }}</p>
                </div>
              </div>
              <p v-if="!profile && !profileMeta.length" class="py-8 text-center text-sm text-slate-400">
                {{ t('sellerSubscription.noProfile') }}
              </p>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </template>

    <Card v-else class="app-surface border-none">
      <CardContent class="py-10 text-center text-sm text-slate-400">{{ t('sellerSubscription.notFound') }}</CardContent>
    </Card>

    <Dialog v-model:open="isNoteDialogOpen">
      <DialogContent class="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>{{ t('common.editNote') }}</DialogTitle>
        </DialogHeader>
        <div class="space-y-2 py-2">
          <Label>{{ t('sellerSubscription.note') }}</Label>
          <Textarea v-model="noteInput" :placeholder="t('sellerSubscription.notePlaceholder')" />
        </div>
        <DialogFooter>
          <Button variant="outline" @click="isNoteDialogOpen = false">{{ t('common.cancel') }}</Button>
          <Button :disabled="isNoteSaving" @click="saveNote">
            {{ isNoteSaving ? t('common.loading') : t('common.save') }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>
