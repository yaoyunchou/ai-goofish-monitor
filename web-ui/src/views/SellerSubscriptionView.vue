<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  addSellerSubscription,
  deleteSellerSubscription,
  listSellerSubscriptions,
  updateSellerSubscription,
  type SellerSubscription,
} from '@/api/sellerSubscriptions'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { toast } from '@/components/ui/toast'
import { ChevronRight, Pencil, Plus, Search } from 'lucide-vue-next'
import PaginationBar from '@/components/common/PaginationBar.vue'
import { formatShanghaiTime } from '@/lib/datetime'
import {
  normalizeSellerSubscription,
  normalizeSubscriptionEnabled,
} from '@/lib/subscription'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

const { t } = useI18n()
const router = useRouter()
const subscriptions = ref<SellerSubscription[]>([])
const search = ref('')
const statusFilter = ref<'all' | 'enabled' | 'disabled'>('all')
const sellerPage = ref(1)
const sellerPageSize = ref(10)
const isLoading = ref(false)
const isSubmitting = ref(false)
const error = ref('')
const isAddDialogOpen = ref(false)
const isEditDialogOpen = ref(false)
const editingRow = ref<SellerSubscription | null>(null)
const sellerUrlInput = ref('')
const noteInput = ref('')
const editNoteInput = ref('')
const editEnabled = ref(true)
const editFormKey = ref(0)
const togglingIds = ref(new Set<number>())

function findSubscription(id: number) {
  return subscriptions.value.find((item) => item.id === id) ?? null
}

function applySubscriptionPatch(row: SellerSubscription, patch: Partial<SellerSubscription>) {
  const index = subscriptions.value.findIndex((item) => item.id === row.id)
  const merged = normalizeSellerSubscription({ ...row, ...patch })
  if (index >= 0) {
    subscriptions.value[index] = merged
  }
  Object.assign(row, merged)
  return merged
}

const displayName = (row: SellerSubscription) =>
  row.profile_nickname || row.nickname || row.seller_user_id

const filteredSellers = computed(() => {
  const keyword = search.value.trim().toLowerCase()
  return subscriptions.value.filter((row) => {
    if (statusFilter.value === 'enabled' && !row.enabled) return false
    if (statusFilter.value === 'disabled' && row.enabled) return false
    if (!keyword) return true
    const name = displayName(row).toLowerCase()
    const userId = (row.seller_user_id || '').toLowerCase()
    const note = (row.note || '').toLowerCase()
    return name.includes(keyword) || userId.includes(keyword) || note.includes(keyword)
  })
})

const totalPages = computed(() =>
  Math.max(1, Math.ceil(filteredSellers.value.length / sellerPageSize.value)),
)

const pagedSellers = computed(() => {
  if (sellerPage.value > totalPages.value) sellerPage.value = totalPages.value
  const start = (sellerPage.value - 1) * sellerPageSize.value
  return filteredSellers.value.slice(start, start + sellerPageSize.value)
})

function onFilterChange() {
  sellerPage.value = 1
}

async function load() {
  isLoading.value = true
  error.value = ''
  try {
    const overview = await listSellerSubscriptions()
    subscriptions.value = (overview.items || []).map((item) => normalizeSellerSubscription(item))
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

async function setEnabled(row: SellerSubscription, enabled: boolean) {
  const targetEnabled = normalizeSubscriptionEnabled(enabled)
  if (normalizeSubscriptionEnabled(row.enabled) === targetEnabled || togglingIds.value.has(row.id)) {
    return
  }
  togglingIds.value.add(row.id)
  try {
    const result = await updateSellerSubscription(row.id, { enabled: targetEnabled })
    applySubscriptionPatch(row, result.item)
    if (editingRow.value?.id === row.id) {
      editEnabled.value = normalizeSubscriptionEnabled(result.item.enabled)
      editFormKey.value += 1
    }
    toast({
      title: targetEnabled
        ? t('sellerSubscription.collectEnabledToast', { name: displayName(row) })
        : t('sellerSubscription.collectDisabledToast', { name: displayName(row) }),
      description: t('sellerSubscription.collectToggleHint'),
    })
  } catch (e) {
    toast({ title: t('common.error'), description: (e as Error).message, variant: 'destructive' })
  } finally {
    togglingIds.value.delete(row.id)
  }
}

function syncEditFormFromRow(row: SellerSubscription) {
  editingRow.value = row
  editNoteInput.value = row.note || ''
  editEnabled.value = normalizeSubscriptionEnabled(row.enabled)
  editFormKey.value += 1
}

function openEditDialog(row: SellerSubscription) {
  if (togglingIds.value.has(row.id)) {
    toast({
      title: t('common.loading'),
      description: t('sellerSubscription.collectToggleSaving'),
    })
    return
  }
  const latest = findSubscription(row.id) ?? row
  syncEditFormFromRow(latest)
  isEditDialogOpen.value = true
}

watch(isEditDialogOpen, async (open) => {
  if (!open || !editingRow.value) return
  await nextTick()
  const latest = findSubscription(editingRow.value.id)
  if (latest) syncEditFormFromRow(latest)
})

async function handleEditSeller() {
  const row = editingRow.value
  if (!row) return
  isSubmitting.value = true
  try {
    const result = await updateSellerSubscription(row.id, {
      note: editNoteInput.value.trim(),
      enabled: editEnabled.value,
    })
    applySubscriptionPatch(row, result.item)
    toast({
      title: t('sellerSubscription.noteSaved'),
      description: editEnabled.value
        ? t('sellerSubscription.collectEnabledToast', { name: displayName(row) })
        : t('sellerSubscription.collectDisabledToast', { name: displayName(row) }),
    })
    isEditDialogOpen.value = false
  } catch (e) {
    toast({ title: t('common.error'), description: (e as Error).message, variant: 'destructive' })
  } finally {
    isSubmitting.value = false
  }
}

async function handleDelete(row: SellerSubscription) {
  try {
    const result = await deleteSellerSubscription(row.id)
    // 后端会级联清理该卖家的商品/画像/健康度数据，message 里带清理数量
    toast({ title: t('sellerSubscription.deleted'), description: result?.message })
    onFilterChange()
    await load()
  } catch (e) {
    toast({ title: t('common.error'), description: (e as Error).message, variant: 'destructive' })
  }
}

function goToDetail(row: SellerSubscription) {
  router.push({ name: 'SellerDetail', params: { sellerUserId: row.seller_user_id } })
}

onMounted(load)
</script>

<template>
  <div class="space-y-6">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 class="text-2xl font-black text-slate-900">{{ t('sellerSubscription.sellersTitle') }}</h1>
        <p class="text-sm text-slate-500">{{ t('sellerSubscription.description') }}</p>
      </div>
      <div class="flex flex-wrap gap-2">
        <Button variant="outline" @click="load">{{ t('common.refresh') }}</Button>
        <Button class="gap-1" @click="isAddDialogOpen = true">
          <Plus class="h-4 w-4" />
          {{ t('sellerSubscription.addSeller') }}
        </Button>
      </div>
    </div>

    <p v-if="error" class="text-sm text-rose-600">{{ error }}</p>

    <Card class="app-surface border-none">
      <CardHeader class="flex flex-row flex-wrap items-center justify-between gap-3">
        <CardTitle>{{ t('sellerSubscription.sellersTitle') }}</CardTitle>
        <Badge variant="secondary">{{ filteredSellers.length }} / {{ subscriptions.length }}</Badge>
      </CardHeader>
      <CardContent>
        <p class="mb-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs leading-relaxed text-slate-600">
          {{ t('sellerSubscription.sellersListHint') }}
        </p>

        <div class="mb-3 flex flex-wrap items-center gap-2">
          <div class="relative">
            <Search class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <Input
              v-model="search"
              class="h-9 w-64 pl-9"
              :placeholder="t('sellerSubscription.searchSellers')"
              @input="onFilterChange"
            />
          </div>
          <select v-model="statusFilter" class="h-9 rounded-md border bg-white px-3 text-sm" @change="onFilterChange">
            <option value="all">{{ t('sellerSubscription.filterAll') }}</option>
            <option value="enabled">{{ t('common.enabled') }}</option>
            <option value="disabled">{{ t('common.disabled') }}</option>
          </select>
        </div>

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
                <th>{{ t('sellerSubscription.colCollect') }}</th>
                <th class="text-right">{{ t('sellerSubscription.colActions') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in pagedSellers"
                :key="row.id"
                class="cursor-pointer border-t border-slate-100 hover:bg-slate-50"
                @click="goToDetail(row)"
              >
                <td class="py-2 font-medium text-slate-800">
                  <div class="flex items-center gap-2">
                    <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-sm font-black text-primary">
                      {{ displayName(row).slice(0, 1).toUpperCase() }}
                    </div>
                    <div class="min-w-0">
                      <p class="truncate">{{ displayName(row) }}</p>
                      <p v-if="row.note" class="truncate text-xs text-slate-400">{{ row.note }}</p>
                    </div>
                  </div>
                </td>
                <td class="font-mono text-xs text-slate-500">{{ row.seller_user_id }}</td>
                <td>{{ row.shop_level || '-' }}</td>
                <td>{{ row.followers ?? '-' }}</td>
                <td>{{ row.item_count ?? '-' }}</td>
                <td class="whitespace-nowrap text-xs text-slate-500">
                  {{ formatShanghaiTime(row.last_captured_at || row.profile_captured_at) }}
                </td>
                <td @click.stop>
                  <div
                    class="flex max-w-[11rem] items-center gap-2"
                    :title="t('sellerSubscription.collectToggleHint')"
                  >
                    <Switch
                      :model-value="normalizeSubscriptionEnabled(row.enabled)"
                      :disabled="togglingIds.has(row.id)"
                      @update:model-value="(value: boolean) => setEnabled(row, value)"
                    />
                    <div class="min-w-0">
                      <p class="text-xs font-medium text-slate-700">
                        {{
                          row.enabled
                            ? t('sellerSubscription.collectEnabled')
                            : t('sellerSubscription.collectDisabled')
                        }}
                      </p>
                      <p class="truncate text-[11px] text-slate-400">
                        {{ t('sellerSubscription.collectToggleLabel') }}
                      </p>
                    </div>
                  </div>
                </td>
                <td class="text-right" @click.stop>
                  <div class="flex items-center justify-end gap-1">
                    <Button
                      size="sm"
                      variant="outline"
                      class="h-8 gap-1 px-2"
                      :disabled="togglingIds.has(row.id)"
                      @click="openEditDialog(row)"
                    >
                      <Pencil class="h-3.5 w-3.5" />
                      {{ t('common.edit') }}
                    </Button>
                    <Button size="sm" variant="ghost" class="h-8 w-8 p-0" @click="goToDetail(row)">
                      <ChevronRight class="h-4 w-4" />
                    </Button>
                    <Button size="sm" variant="destructive" @click="handleDelete(row)">
                      {{ t('common.delete') }}
                    </Button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
          <p v-if="!pagedSellers.length" class="py-8 text-center text-slate-400">
            {{ subscriptions.length ? t('sellerSubscription.noMatch') : t('sellerSubscription.emptySellers') }}
          </p>
        </div>

        <div v-if="filteredSellers.length > sellerPageSize" class="mt-4 border-t border-slate-100 pt-3">
          <PaginationBar
            :page="sellerPage"
            :page-size="sellerPageSize"
            :total="filteredSellers.length"
            @update:page="(page: number) => (sellerPage = page)"
            @update:page-size="(size: number) => { sellerPageSize = size; sellerPage = 1 }"
          />
        </div>
      </CardContent>
    </Card>

    <Dialog v-model:open="isEditDialogOpen">
      <DialogContent class="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle>{{ t('sellerSubscription.editSeller') }}</DialogTitle>
          <DialogDescription>{{ t('sellerSubscription.editSellerHint') }}</DialogDescription>
        </DialogHeader>
        <div v-if="editingRow" class="space-y-4 py-2">
          <div class="rounded-xl border border-slate-100 bg-slate-50 px-4 py-3 text-sm text-slate-700">
            {{ displayName(editingRow) }}
            <span class="ml-2 font-mono text-xs text-slate-400">{{ editingRow.seller_user_id }}</span>
          </div>
          <div class="space-y-2">
            <Label>{{ t('sellerSubscription.note') }}</Label>
            <Input v-model="editNoteInput" :placeholder="t('sellerSubscription.notePlaceholder')" />
          </div>
          <div class="flex items-center justify-between gap-4 rounded-xl border px-4 py-3">
            <div>
              <p class="text-sm font-medium text-slate-800">{{ t('sellerSubscription.collectToggleLabel') }}</p>
              <p class="mt-0.5 text-xs text-slate-500">{{ t('sellerSubscription.collectToggleHint') }}</p>
            </div>
            <Switch
              :key="`edit-enabled-${editFormKey}`"
              v-model="editEnabled"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" @click="isEditDialogOpen = false">{{ t('common.cancel') }}</Button>
          <Button :disabled="isSubmitting" @click="handleEditSeller">
            {{ isSubmitting ? t('common.loading') : t('common.save') }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

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
