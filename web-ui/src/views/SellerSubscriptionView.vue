<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  addSellerSubscription,
  deleteSellerSubscription,
  getSellerMetricItems,
  listSellerSubscriptions,
  runSellerSubscriptions,
  updateSellerSubscription,
  updateSellerSubscriptionSchedule,
  type SellerMetricItem,
  type SellerSubscription,
  type SellerSubscriptionSchedule,
} from '@/api/sellerSubscriptions'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { toast } from '@/components/ui/toast'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

const { t } = useI18n()
const subscriptions = ref<SellerSubscription[]>([])
const schedule = ref<SellerSubscriptionSchedule | null>(null)
const items = ref<SellerMetricItem[]>([])
const sellerFilter = ref('')
const isLoading = ref(false)
const isSubmitting = ref(false)
const error = ref('')
const isAddDialogOpen = ref(false)
const sellerUrlInput = ref('')
const noteInput = ref('')
const cronInput = ref('0 8 * * *')
let pollTimer: ReturnType<typeof setInterval> | null = null

const selectedSeller = computed(() =>
  subscriptions.value.find((item) => item.seller_user_id === sellerFilter.value) || null,
)

const displayName = (row: SellerSubscription) =>
  row.profile_nickname || row.nickname || row.seller_user_id

function formatTime(value?: string | null) {
  if (!value) return '-'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

async function load() {
  isLoading.value = true
  error.value = ''
  try {
    const overview = await listSellerSubscriptions()
    subscriptions.value = overview.items || []
    schedule.value = overview.schedule || null
    if (schedule.value?.cron) cronInput.value = schedule.value.cron
    const itemRes = await getSellerMetricItems(sellerFilter.value || undefined)
    items.value = itemRes.items || []
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    isLoading.value = false
  }
}

async function handleAddSeller() {
  if (!sellerUrlInput.value.trim()) {
    toast({ title: t('sellerSubscription.addRequired'), variant: 'destructive' })
    return
  }
  isSubmitting.value = true
  try {
    await addSellerSubscription({
      seller_url: sellerUrlInput.value.trim(),
      note: noteInput.value.trim(),
    })
    toast({ title: t('sellerSubscription.added') })
    isAddDialogOpen.value = false
    sellerUrlInput.value = ''
    noteInput.value = ''
    await load()
  } catch (e) {
    toast({ title: t('common.error'), description: (e as Error).message, variant: 'destructive' })
  } finally {
    isSubmitting.value = false
  }
}

async function toggleEnabled(row: SellerSubscription) {
  try {
    await updateSellerSubscription(row.id, { enabled: !row.enabled })
    row.enabled = !row.enabled
  } catch (e) {
    toast({ title: t('common.error'), description: (e as Error).message, variant: 'destructive' })
  }
}

async function handleDelete(row: SellerSubscription) {
  try {
    await deleteSellerSubscription(row.id)
    toast({ title: t('sellerSubscription.deleted') })
    if (sellerFilter.value === row.seller_user_id) sellerFilter.value = ''
    await load()
  } catch (e) {
    toast({ title: t('common.error'), description: (e as Error).message, variant: 'destructive' })
  }
}

async function saveSchedule() {
  isSubmitting.value = true
  try {
    const result = await updateSellerSubscriptionSchedule({
      enabled: schedule.value?.enabled,
      cron: cronInput.value.trim(),
      item_limit: schedule.value?.item_limit ?? 100,
    }) as { schedule: SellerSubscriptionSchedule }
    schedule.value = result.schedule
    toast({ title: t('sellerSubscription.scheduleSaved') })
  } catch (e) {
    toast({ title: t('common.error'), description: (e as Error).message, variant: 'destructive' })
  } finally {
    isSubmitting.value = false
  }
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(async () => {
    try {
      const overview = await listSellerSubscriptions()
      schedule.value = overview.schedule || schedule.value
      if (!schedule.value?.is_running) {
        subscriptions.value = overview.items || subscriptions.value
        const itemRes = await getSellerMetricItems(sellerFilter.value || undefined)
        items.value = itemRes.items || []
        stopPolling()
        if (schedule.value?.last_run_ok) {
          toast({
            title: t('sellerSubscription.runFinished'),
            description: schedule.value.last_run_summary || undefined,
          })
        } else if (schedule.value?.last_run_summary) {
          toast({
            title: t('sellerSubscription.runFailed'),
            description: schedule.value.last_run_summary,
            variant: 'destructive',
          })
        }
      }
    } catch {
      // ignore transient poll errors
    }
  }, 5000)
}

async function handleRunNow() {
  try {
    const result = await runSellerSubscriptions() as { message?: string }
    toast({
      title: result.message || t('sellerSubscription.runStarted'),
      description: t('sellerSubscription.runStartedHint'),
    })
    if (schedule.value) schedule.value.is_running = true
    startPolling()
  } catch (e) {
    toast({ title: t('common.error'), description: (e as Error).message, variant: 'destructive' })
  }
}

onMounted(load)
onUnmounted(stopPolling)
</script>

<template>
  <div class="space-y-6">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 class="text-2xl font-black text-slate-900">{{ t('sellerSubscription.title') }}</h1>
        <p class="text-sm text-slate-500">{{ t('sellerSubscription.description') }}</p>
      </div>
      <div class="flex flex-wrap gap-2">
        <Button variant="outline" @click="load">{{ t('common.refresh') }}</Button>
        <Button variant="outline" :disabled="schedule?.is_running" @click="handleRunNow">
          {{ schedule?.is_running ? t('sellerSubscription.running') : t('sellerSubscription.runNow') }}
        </Button>
        <Button @click="isAddDialogOpen = true">{{ t('sellerSubscription.addSeller') }}</Button>
      </div>
    </div>

    <div
      v-if="schedule?.last_run_summary"
      class="rounded-xl border px-4 py-3 text-sm"
      :class="schedule.last_run_ok ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-amber-200 bg-amber-50 text-amber-900'"
    >
      <p class="font-medium">
        {{ schedule.last_run_ok ? t('sellerSubscription.lastRunOk') : t('sellerSubscription.lastRunFailed') }}
        <span v-if="schedule.last_run_at" class="ml-2 font-normal opacity-80">
          {{ formatTime(schedule.last_run_at) }}
        </span>
      </p>
      <p class="mt-1">{{ schedule.last_run_summary }}</p>
      <p v-if="schedule.last_run_saved" class="mt-1 text-xs opacity-80">
        {{ t('sellerSubscription.lastRunSaved', { count: schedule.last_run_saved }) }}
      </p>
    </div>

    <Card class="app-surface border-none">
      <CardHeader>
        <CardTitle class="text-base">{{ t('sellerSubscription.scheduleTitle') }}</CardTitle>
      </CardHeader>
      <CardContent class="grid gap-4 md:grid-cols-4">
        <div class="space-y-2">
          <Label>{{ t('sellerSubscription.cron') }}</Label>
          <Input v-model="cronInput" placeholder="0 8 * * *" />
        </div>
        <div class="flex items-end gap-3">
          <div class="space-y-2">
            <Label>{{ t('sellerSubscription.scheduleEnabled') }}</Label>
            <div class="flex h-10 items-center">
              <Switch
                :checked="schedule?.enabled ?? true"
                @update:checked="(value: boolean) => schedule && (schedule.enabled = value)"
              />
            </div>
          </div>
        </div>
        <div class="flex items-end">
          <Button :disabled="isSubmitting" @click="saveSchedule">{{ t('common.save') }}</Button>
        </div>
        <p class="text-xs text-slate-500 md:col-span-4">
          {{ t('sellerSubscription.scheduleHint', { limit: schedule?.item_limit ?? 100 }) }}
        </p>
      </CardContent>
    </Card>

    <p v-if="error" class="text-sm text-rose-600">{{ error }}</p>

    <Card class="app-surface border-none">
      <CardHeader class="flex flex-row items-center justify-between">
        <CardTitle>{{ t('sellerSubscription.sellersTitle') }}</CardTitle>
        <Badge variant="secondary">{{ subscriptions.length }}</Badge>
      </CardHeader>
      <CardContent>
        <p v-if="isLoading" class="text-sm text-slate-500">{{ t('common.loading') }}</p>
        <div v-else class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-left text-slate-500">
                <th class="py-2">{{ t('sellerSubscription.colSeller') }}</th>
                <th>{{ t('sellerSubscription.colUserId') }}</th>
                <th>{{ t('sellerSubscription.shopLevel') }}</th>
                <th>{{ t('sellerSubscription.followers') }}</th>
                <th>{{ t('sellerSubscription.itemCount') }}</th>
                <th>{{ t('sellerSubscription.colLastCaptured') }}</th>
                <th>{{ t('sellerSubscription.colStatus') }}</th>
                <th class="text-right">{{ t('sellerSubscription.colActions') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in subscriptions"
                :key="row.id"
                class="border-t border-slate-100"
                :class="sellerFilter === row.seller_user_id ? 'bg-slate-50' : ''"
              >
                <td class="py-2 font-medium text-slate-800">
                  <button class="text-left hover:text-primary" @click="sellerFilter = row.seller_user_id; load()">
                    {{ displayName(row) }}
                  </button>
                </td>
                <td class="font-mono text-xs text-slate-500">{{ row.seller_user_id }}</td>
                <td>{{ row.shop_level || '-' }}</td>
                <td>{{ row.followers ?? '-' }}</td>
                <td>{{ row.item_count ?? '-' }}</td>
                <td>{{ formatTime(row.last_captured_at || row.profile_captured_at) }}</td>
                <td>
                  <Badge :variant="row.enabled ? 'default' : 'secondary'">
                    {{ row.enabled ? t('common.enabled') : t('common.disabled') }}
                  </Badge>
                </td>
                <td class="space-x-2 text-right">
                  <Button size="sm" variant="outline" @click="toggleEnabled(row)">
                    {{ row.enabled ? t('common.disabled') : t('common.enabled') }}
                  </Button>
                  <Button size="sm" variant="destructive" @click="handleDelete(row)">
                    {{ t('common.delete') }}
                  </Button>
                </td>
              </tr>
            </tbody>
          </table>
          <p v-if="!subscriptions.length" class="py-8 text-center text-slate-400">
            {{ t('sellerSubscription.emptySellers') }}
          </p>
        </div>
      </CardContent>
    </Card>

    <Card class="app-surface border-none">
      <CardHeader class="flex flex-row items-center justify-between gap-3">
        <CardTitle>{{ t('sellerSubscription.itemsTitle') }}</CardTitle>
        <select v-model="sellerFilter" class="h-9 rounded-md border px-3 text-sm" @change="load">
          <option value="">{{ t('sellerSubscription.allSellers') }}</option>
          <option v-for="row in subscriptions" :key="row.id" :value="row.seller_user_id">
            {{ displayName(row) }}
          </option>
        </select>
      </CardHeader>
      <CardContent>
        <p v-if="selectedSeller" class="mb-3 text-xs text-slate-500">
          {{ t('sellerSubscription.filteredBy', { seller: displayName(selectedSeller) }) }}
        </p>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-left text-slate-500">
                <th class="py-2">{{ t('sellerSubscription.colTitle') }}</th>
                <th>{{ t('sellerSubscription.colPrice') }}</th>
                <th>{{ t('sellerSubscription.colWant') }}</th>
                <th>{{ t('sellerSubscription.colView') }}</th>
                <th>{{ t('sellerSubscription.colSeller') }}</th>
                <th>{{ t('sellerSubscription.colSnapshot') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in items" :key="`${item.item_id}-${item.snapshot_time}`" class="border-t border-slate-100">
                <td class="py-2 font-medium text-slate-800">{{ item.title || item.item_id }}</td>
                <td>{{ item.price ?? '-' }}</td>
                <td>{{ item.want_count ?? '-' }}</td>
                <td>{{ item.view_count ?? '-' }}</td>
                <td>{{ item.seller_user_id }}</td>
                <td>{{ formatTime(item.snapshot_time) }}</td>
              </tr>
            </tbody>
          </table>
          <p v-if="!items.length" class="py-8 text-center text-slate-400">{{ t('sellerSubscription.empty') }}</p>
        </div>
      </CardContent>
    </Card>

    <Dialog v-model:open="isAddDialogOpen">
      <DialogContent class="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle>{{ t('sellerSubscription.addSeller') }}</DialogTitle>
          <DialogDescription>{{ t('sellerSubscription.addSellerHint') }}</DialogDescription>
        </DialogHeader>
        <div class="space-y-4 py-2">
          <div class="space-y-2">
            <Label>{{ t('sellerSubscription.sellerUrl') }}</Label>
            <Textarea
              v-model="sellerUrlInput"
              class="min-h-[100px]"
              :placeholder="t('sellerSubscription.sellerUrlPlaceholder')"
            />
          </div>
          <div class="space-y-2">
            <Label>{{ t('sellerSubscription.note') }}</Label>
            <Input v-model="noteInput" :placeholder="t('sellerSubscription.notePlaceholder')" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" @click="isAddDialogOpen = false">{{ t('common.cancel') }}</Button>
          <Button :disabled="isSubmitting" @click="handleAddSeller">
            {{ isSubmitting ? t('common.loading') : t('common.save') }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>
