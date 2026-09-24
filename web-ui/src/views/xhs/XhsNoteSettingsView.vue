<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { getNoteSchedule, listNoteAccounts, saveNoteSchedule, type NoteAccount, type NoteSchedule } from '@/api/xhsNotes'
import XhsScheduleCard from '@/components/xhs/XhsScheduleCard.vue'
import { Label } from '@/components/ui/label'
import { toast } from '@/components/ui/toast'

const { t } = useI18n()
const schedule = ref<NoteSchedule>({ cron: '0 9 * * *', enabled: false, account_id: null, next_run_at: null })
const accounts = ref<NoteAccount[]>([])
const saving = ref(false)
const dailyOnly = ['daily', 'weekly', 'monthly']

async function load() {
  try {
    const [current, rows] = await Promise.all([getNoteSchedule(), listNoteAccounts()])
    schedule.value = current
    accounts.value = rows
  } catch (error) {
    toast({ title: t('common.error'), description: error instanceof Error ? error.message : t('xhs.loadFailed'), variant: 'destructive' })
  }
}

async function save(payload: { cron: string; enabled: boolean }) {
  saving.value = true
  try {
    schedule.value = await saveNoteSchedule(payload.cron, payload.enabled, schedule.value.account_id)
    toast({ title: t('xhs.scheduleSaved') })
  } catch (error) {
    toast({ title: t('xhs.scheduleFailed'), description: error instanceof Error ? error.message : '', variant: 'destructive' })
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="space-y-4 p-4">
    <h1 class="text-xl font-semibold">{{ t('xhs.notesSettings') }}</h1>
    <div class="grid max-w-md gap-2">
      <Label>{{ t('xhs.noteAccount') }}</Label>
      <p v-if="accounts.length === 0" class="text-sm text-muted-foreground">{{ t('xhs.noteAccountEmpty') }}</p>
      <select v-else v-model="schedule.account_id" class="h-9 rounded-md border bg-background px-3 text-sm">
        <option v-for="account in accounts" :key="account.id" :value="account.id">{{ account.name }}</option>
      </select>
    </div>
    <XhsScheduleCard
      :cron="schedule.cron"
      :enabled="schedule.enabled"
      :next-run-at="schedule.next_run_at"
      :saving="saving"
      :frequencies="dailyOnly"
      @save="save"
    />
  </div>
</template>
