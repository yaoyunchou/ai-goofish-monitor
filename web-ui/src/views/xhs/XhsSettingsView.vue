<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { getXhsSchedule, saveXhsSchedule, type XhsSchedule } from '@/api/xhs'
import XhsScheduleCard from '@/components/xhs/XhsScheduleCard.vue'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { toast } from '@/components/ui/toast'

const { t } = useI18n()
const schedule = ref<XhsSchedule>({ cron: '0 * * * *', enabled: false, next_run_at: null })
const saving = ref(false)

async function load() {
  try {
    schedule.value = await getXhsSchedule()
  } catch (error) {
    toast({ title: t('common.error'), description: error instanceof Error ? error.message : t('xhs.loadFailed'), variant: 'destructive' })
  }
}

async function save(payload: { cron: string; enabled: boolean }) {
  saving.value = true
  try {
    schedule.value = await saveXhsSchedule(payload.cron, payload.enabled)
    toast({ title: t('xhs.scheduleSaved') })
  } catch (error) {
    toast({ title: t('common.error'), description: error instanceof Error ? error.message : t('xhs.scheduleFailed'), variant: 'destructive' })
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="space-y-4 p-4">
    <div>
      <h1 class="text-xl font-semibold">{{ t('xhs.settingsTitle') }}</h1>
      <p class="text-sm text-muted-foreground">{{ t('xhs.settingsHint') }}</p>
    </div>
    <Card>
      <CardHeader>
        <CardTitle class="text-base">{{ t('xhs.scheduleTitle') }}</CardTitle>
        <p class="text-sm text-muted-foreground">{{ t('xhs.scheduleHint') }}</p>
      </CardHeader>
      <CardContent>
        <XhsScheduleCard
          :cron="schedule.cron"
          :enabled="schedule.enabled"
          :next-run-at="schedule.next_run_at"
          :saving="saving"
          @save="save"
        />
      </CardContent>
    </Card>
  </div>
</template>
