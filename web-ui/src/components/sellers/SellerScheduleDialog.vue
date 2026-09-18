<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  updateSellerSubscriptionSchedule,
  type SellerSubscriptionSchedule,
} from '@/api/sellerSubscriptions'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { toast } from '@/components/ui/toast'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

const props = defineProps<{
  open: boolean
  schedule: SellerSubscriptionSchedule | null
}>()

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'saved', schedule: SellerSubscriptionSchedule): void
}>()

const { t } = useI18n()
const cronInput = ref('0 8 * * *')
const enabled = ref(true)
const itemLimit = ref(100)
const runHeadless = ref(true)
const isSaving = ref(false)

function resolveRunHeadless(schedule: SellerSubscriptionSchedule | null): boolean {
  if (!schedule) return true
  if (schedule.run_headless === null || schedule.run_headless === undefined) {
    return schedule.run_headless_effective ?? true
  }
  return schedule.run_headless
}

function syncFormFromSchedule() {
  cronInput.value = props.schedule?.cron || '0 8 * * *'
  enabled.value = props.schedule?.enabled ?? true
  itemLimit.value = props.schedule?.item_limit ?? 100
  runHeadless.value = resolveRunHeadless(props.schedule)
}

watch(
  () => props.open,
  (open) => {
    if (open) syncFormFromSchedule()
  },
)

watch(
  () => props.schedule,
  () => {
    if (props.open) syncFormFromSchedule()
  },
)

async function save() {
  isSaving.value = true
  try {
    const result = (await updateSellerSubscriptionSchedule({
      enabled: enabled.value,
      cron: cronInput.value.trim(),
      item_limit: itemLimit.value,
      run_headless: runHeadless.value,
    })) as { schedule: SellerSubscriptionSchedule }
    toast({ title: t('sellerSubscription.scheduleSaved') })
    emit('saved', result.schedule)
    emit('update:open', false)
  } catch (e) {
    toast({ title: t('common.error'), description: (e as Error).message, variant: 'destructive' })
  } finally {
    isSaving.value = false
  }
}
</script>

<template>
  <Dialog :open="open" @update:open="(value: boolean) => emit('update:open', value)">
    <DialogContent class="sm:max-w-[520px]">
      <DialogHeader>
        <DialogTitle>{{ t('sellerSubscription.scheduleTitle') }}</DialogTitle>
        <DialogDescription>
          {{ t('sellerSubscription.scheduleHint', { limit: itemLimit }) }}
        </DialogDescription>
      </DialogHeader>
      <div class="space-y-4 py-2">
        <div class="space-y-2">
          <Label>{{ t('sellerSubscription.cron') }}</Label>
          <Input v-model="cronInput" placeholder="0 8 * * *" />
        </div>
        <div class="flex items-center justify-between gap-4 rounded-xl border px-4 py-3">
          <div>
            <p class="text-sm font-medium text-slate-800">{{ t('sellerSubscription.scheduleEnabled') }}</p>
            <p class="mt-0.5 text-xs text-slate-500">{{ t('sellerSubscription.scheduleEnabledHint') }}</p>
          </div>
          <Switch v-model="enabled" />
        </div>
        <div class="space-y-2">
          <Label>{{ t('sellerSubscription.itemLimit') }}</Label>
          <Input v-model.number="itemLimit" type="number" min="1" max="500" />
        </div>
        <div class="flex items-center justify-between gap-4 rounded-xl border px-4 py-3">
          <div>
            <p class="text-sm font-medium text-slate-800">{{ t('sellerSubscription.runHeadless') }}</p>
            <p class="mt-0.5 text-xs text-slate-500">{{ t('sellerSubscription.runHeadlessHint') }}</p>
          </div>
          <Switch v-model="runHeadless" />
        </div>
      </div>
      <DialogFooter>
        <Button variant="outline" @click="emit('update:open', false)">{{ t('common.cancel') }}</Button>
        <Button :disabled="isSaving" @click="save">
          {{ isSaving ? t('common.loading') : t('common.save') }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
