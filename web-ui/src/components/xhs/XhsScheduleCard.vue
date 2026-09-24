<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { toast } from '@/components/ui/toast'
import {
  XHS_FREQUENCY_OPTIONS,
  XHS_WEEKDAYS,
  buildXhsCron,
  classifyXhsNextRun,
  parseXhsCron,
  type XhsFrequency,
  type XhsWeekday,
} from '@/lib/xhsSchedule'

const props = defineProps<{
  cron: string
  enabled: boolean
  nextRunAt?: string | null
  saving?: boolean
  frequencies?: readonly string[]
}>()

const emit = defineEmits<{
  save: [payload: { cron: string; enabled: boolean }]
}>()

const { t } = useI18n()
const enabled = ref(props.enabled)
const frequency = ref<XhsFrequency>('h1')
const dailyTime = ref('09:00')
const weekday = ref<XhsWeekday>('mon')
const monthDay = ref(1)
const customCron = ref('0 * * * *')
const frequencyOptions = computed(() => props.frequencies ?? XHS_FREQUENCY_OPTIONS)
const monthDays = Array.from({ length: 31 }, (_, index) => index + 1)

function applyCron(cron: string) {
  const parsed = parseXhsCron(cron)
  frequency.value = parsed.frequency
  dailyTime.value = parsed.time
  weekday.value = parsed.weekday
  monthDay.value = parsed.monthDay
  customCron.value = parsed.cron
}

watch(() => props.cron, applyCron, { immediate: true })
watch(() => props.enabled, (value) => {
  enabled.value = value
})

const needsClock = computed(() => frequency.value === 'daily' || frequency.value === 'weekly' || frequency.value === 'monthly')

const summary = computed(() => {
  const time = dailyTime.value || '--:--'
  if (frequency.value === 'daily') return t('xhs.summary.daily', { time })
  if (frequency.value === 'weekly') {
    return t('xhs.summary.weekly', { weekday: t(`xhs.weekday.${weekday.value}`), time })
  }
  if (frequency.value === 'monthly') {
    const key = monthDay.value >= 29 ? 'xhs.summary.monthlySkip' : 'xhs.summary.monthly'
    return t(key, { day: monthDay.value, time })
  }
  return t(`xhs.summary.${frequency.value}`)
})

const nextRunText = computed(() => {
  if (!enabled.value) return t('xhs.nextOff')
  const parts = classifyXhsNextRun(props.nextRunAt)
  if (!parts) return t('xhs.nextPending')
  if (parts.kind === 'today') return t('xhs.nextToday', { time: parts.time })
  if (parts.kind === 'tomorrow') return t('xhs.nextTomorrow', { time: parts.time })
  return t('xhs.nextDate', { month: parts.month, day: parts.day, time: parts.time })
})

function onFrequency(value: unknown) {
  const next = String(value ?? '')
  if (next === 'custom' || (XHS_FREQUENCY_OPTIONS as readonly string[]).includes(next)) {
    frequency.value = next as XhsFrequency
  }
}

function onWeekday(value: unknown) {
  const next = String(value ?? '')
  if ((XHS_WEEKDAYS as readonly string[]).includes(next)) weekday.value = next as XhsWeekday
}

function onMonthDay(value: unknown) {
  const next = Number(value)
  if (Number.isInteger(next) && next >= 1 && next <= 31) monthDay.value = next
}

function submit() {
  try {
    emit('save', {
      cron: buildXhsCron(frequency.value, dailyTime.value, customCron.value, weekday.value, monthDay.value),
      enabled: enabled.value,
    })
  } catch {
    toast({ title: t('xhs.invalidTime'), variant: 'destructive' })
  }
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between gap-4 rounded-lg border px-4 py-3">
      <div>
        <p class="text-sm font-medium">{{ t('xhs.scheduleEnabled') }}</p>
        <p class="mt-1 text-sm text-muted-foreground">{{ summary }}</p>
      </div>
      <Switch v-model="enabled" />
    </div>
    <div class="flex flex-wrap items-end gap-3">
      <div class="grid gap-1.5">
        <Label>{{ t('xhs.frequencyLabel') }}</Label>
        <Select :model-value="frequency" @update:model-value="onFrequency">
          <SelectTrigger class="w-48">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem v-if="frequency === 'custom'" value="custom">{{ t('xhs.frequency.custom') }}</SelectItem>
            <SelectItem v-for="item in frequencyOptions" :key="item" :value="item">
              {{ t(`xhs.frequency.${item}`) }}
            </SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div v-if="frequency === 'weekly'" class="grid gap-1.5">
        <Label>{{ t('xhs.weekdayLabel') }}</Label>
        <Select :model-value="weekday" @update:model-value="onWeekday">
          <SelectTrigger class="w-36">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem v-for="day in XHS_WEEKDAYS" :key="day" :value="day">
              {{ t(`xhs.weekday.${day}`) }}
            </SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div v-if="frequency === 'monthly'" class="grid gap-1.5">
        <Label>{{ t('xhs.monthDayLabel') }}</Label>
        <Select :model-value="String(monthDay)" @update:model-value="onMonthDay">
          <SelectTrigger class="w-32">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem v-for="day in monthDays" :key="day" :value="String(day)">
              {{ t('xhs.monthDayOption', { day }) }}
            </SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div v-if="needsClock" class="grid gap-1.5">
        <Label for="xhs-daily-time">{{ t('xhs.dailyTime') }}</Label>
        <Input id="xhs-daily-time" v-model="dailyTime" class="w-36" type="time" step="60" />
      </div>
      <Button variant="outline" :disabled="saving" @click="submit">{{ t('xhs.saveSchedule') }}</Button>
    </div>
    <p class="text-sm text-muted-foreground">{{ nextRunText }}</p>
  </div>
</template>
