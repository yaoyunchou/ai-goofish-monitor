<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  getSellerSubscriptionStats,
  runSellerSubscriptions,
  type SellerSubscriptionSchedule,
  type SellerSubscriptionStats,
} from '@/api/sellerSubscriptions'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { toast } from '@/components/ui/toast'
import { Activity, Play, Settings2, Store, Package } from 'lucide-vue-next'
import SellerScheduleDialog from '@/components/sellers/SellerScheduleDialog.vue'
import { formatShanghaiTime } from '@/lib/datetime'
import { useSellerSubscriptionConsoleLog } from '@/composables/useSellerSubscriptionConsoleLog'

const { t } = useI18n()
const stats = ref<SellerSubscriptionStats | null>(null)
const isLoading = ref(false)
const error = ref('')
const isScheduleDialogOpen = ref(false)
const logContainer = ref<HTMLElement | null>(null)
let pollTimer: ReturnType<typeof setInterval> | null = null

const {
  logs: consoleLogs,
  loadLatestTail,
  startPolling: startLogPolling,
  stopPolling: stopLogPolling,
} = useSellerSubscriptionConsoleLog()

const schedule = computed(() => stats.value?.schedule ?? null)
const consoleLogEnabled = computed(() => Boolean(stats.value?.console_log_enabled))
const scheduleJobMissing = computed(
  () => Boolean(schedule.value?.enabled) && !schedule.value?.next_run_at,
)

async function load() {
  isLoading.value = true
  error.value = ''
  try {
    stats.value = await getSellerSubscriptionStats()
    syncConsoleLogPolling()
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    isLoading.value = false
  }
}

function syncConsoleLogPolling() {
  if (consoleLogEnabled.value) {
    startLogPolling()
  } else {
    stopLogPolling()
  }
}

async function scrollConsoleLogToBottom() {
  await nextTick()
  if (logContainer.value) {
    logContainer.value.scrollTop = logContainer.value.scrollHeight
  }
}

watch(consoleLogs, () => {
  scrollConsoleLogToBottom()
})

watch(consoleLogEnabled, (enabled) => {
  if (enabled) {
    loadLatestTail().then(() => scrollConsoleLogToBottom())
    startLogPolling()
  } else {
    stopLogPolling()
  }
})

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
      stats.value = await getSellerSubscriptionStats()
      const current = stats.value?.schedule
      if (!current?.is_running) {
        stopPolling()
        if (current?.last_run_ok) {
          toast({
            title: t('sellerSubscription.runFinished'),
            description: current.last_run_summary || undefined,
          })
        } else if (current?.last_run_summary) {
          toast({
            title: t('sellerSubscription.runFailed'),
            description: current.last_run_summary,
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
    const result = (await runSellerSubscriptions()) as { message?: string }
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

function handleScheduleSaved(saved: SellerSubscriptionSchedule) {
  if (stats.value) stats.value.schedule = saved
}

onMounted(async () => {
  await load()
  if (schedule.value?.is_running) startPolling()
})
onUnmounted(() => {
  stopPolling()
  stopLogPolling()
})
</script>

<template>
  <div class="space-y-6">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 class="text-2xl font-black text-slate-900">{{ t('sellerCollection.title') }}</h1>
        <p class="text-sm text-slate-500">{{ t('sellerCollection.description') }}</p>
      </div>
      <div class="flex flex-wrap gap-2">
        <Button variant="outline" @click="load">{{ t('common.refresh') }}</Button>
        <Button variant="outline" class="gap-1" @click="isScheduleDialogOpen = true">
          <Settings2 class="h-4 w-4" />
          {{ t('sellerSubscription.scheduleTitle') }}
        </Button>
        <Button :disabled="schedule?.is_running" class="gap-1" @click="handleRunNow">
          <Play class="h-4 w-4" />
          {{ schedule?.is_running ? t('sellerSubscription.running') : t('sellerSubscription.runNow') }}
        </Button>
      </div>
    </div>

    <p v-if="error" class="text-sm text-rose-600">{{ error }}</p>

    <div
      v-if="schedule?.is_running"
      class="rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800"
    >
      <p class="flex items-center gap-2 font-medium">
        <Activity class="h-4 w-4 animate-pulse" />
        {{ t('sellerSubscription.running') }}
      </p>
      <p class="mt-1">{{ t('sellerSubscription.runStartedHint') }}</p>
    </div>
    <div
      v-else-if="schedule?.last_run_summary"
      class="rounded-xl border px-4 py-3 text-sm"
      :class="schedule.last_run_ok ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-amber-200 bg-amber-50 text-amber-900'"
    >
      <p class="font-medium">
        {{ schedule.last_run_ok ? t('sellerSubscription.lastRunOk') : t('sellerSubscription.lastRunFailed') }}
        <span v-if="schedule.last_run_at" class="ml-2 font-normal opacity-80">
          {{ formatShanghaiTime(schedule.last_run_at) }}
        </span>
      </p>
      <p class="mt-1">{{ schedule.last_run_summary }}</p>
      <p v-if="schedule.last_run_saved" class="mt-1 text-xs opacity-80">
        {{ t('sellerSubscription.lastRunSaved', { count: schedule.last_run_saved }) }}
      </p>
    </div>

    <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <Card class="app-surface border-none">
        <CardContent class="p-5">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-xs font-bold text-slate-400 uppercase tracking-wider">
                {{ t('sellerCollection.stats.sellers') }}
              </p>
              <h3 class="mt-1 text-2xl font-black text-slate-800">
                {{ isLoading ? '-' : (stats?.seller_count ?? 0) }}
              </h3>
            </div>
            <div class="rounded-2xl bg-primary/10 p-3">
              <Store class="h-6 w-6 text-primary" />
            </div>
          </div>
        </CardContent>
      </Card>
      <Card class="app-surface border-none">
        <CardContent class="p-5">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-xs font-bold text-slate-400 uppercase tracking-wider">
                {{ t('sellerCollection.stats.items') }}
              </p>
              <h3 class="mt-1 text-2xl font-black text-slate-800">
                {{ isLoading ? '-' : (stats?.item_count ?? 0) }}
              </h3>
            </div>
            <div class="rounded-2xl bg-emerald-500/10 p-3">
              <Package class="h-6 w-6 text-emerald-500" />
            </div>
          </div>
        </CardContent>
      </Card>
      <Card class="app-surface border-none">
        <CardContent class="p-5">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-xs font-bold text-slate-400 uppercase tracking-wider">
                {{ t('sellerCollection.stats.lastRun') }}
              </p>
              <h3 class="mt-1 text-base font-bold text-slate-800">
                {{ formatShanghaiTime(schedule?.last_run_at) }}
              </h3>
            </div>
            <div class="rounded-2xl bg-amber-500/10 p-3">
              <Activity class="h-6 w-6 text-amber-500" />
            </div>
          </div>
        </CardContent>
      </Card>
      <Card class="app-surface border-none">
        <CardContent class="p-5">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-xs font-bold text-slate-400 uppercase tracking-wider">
                {{ t('sellerCollection.stats.schedule') }}
              </p>
              <h3 class="mt-1 text-base font-bold text-slate-800">
                <Badge :variant="schedule?.enabled ? 'default' : 'secondary'" class="mr-2">
                  {{ schedule?.enabled ? t('common.enabled') : t('common.disabled') }}
                </Badge>
                <span class="font-mono text-sm">{{ schedule?.cron || '-' }}</span>
              </h3>
            </div>
            <div class="rounded-2xl bg-purple-500/10 p-3">
              <Settings2 class="h-6 w-6 text-purple-500" />
            </div>
          </div>
        </CardContent>
      </Card>
    </div>

    <Card class="app-surface border-none">
      <CardHeader class="flex flex-row flex-wrap items-center justify-between gap-3">
        <CardTitle class="text-base">{{ t('sellerCollection.scheduleCard.title') }}</CardTitle>
        <Button variant="outline" size="sm" @click="isScheduleDialogOpen = true">
          {{ t('common.edit') }}
        </Button>
      </CardHeader>
      <CardContent>
        <p v-if="isLoading" class="text-sm text-slate-500">{{ t('common.loading') }}</p>
        <div v-else class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <div class="rounded-xl border border-slate-100 px-4 py-3">
            <p class="text-xs text-slate-400">{{ t('sellerCollection.scheduleCard.cron') }}</p>
            <p class="mt-1 font-mono text-sm font-semibold text-slate-800">{{ schedule?.cron || '-' }}</p>
          </div>
          <div
            class="rounded-xl border px-4 py-3"
            :class="scheduleJobMissing ? 'border-amber-300 bg-amber-50' : 'border-slate-100'"
          >
            <p class="text-xs text-slate-400">{{ t('sellerCollection.scheduleCard.nextRun') }}</p>
            <p
              v-if="schedule?.next_run_at"
              class="mt-1 text-sm font-semibold text-slate-800"
            >
              {{ formatShanghaiTime(schedule.next_run_at) }}
            </p>
            <p
              v-else-if="scheduleJobMissing"
              class="mt-1 text-sm font-semibold text-amber-800"
            >
              {{ t('sellerCollection.scheduleCard.jobMissing') }}
            </p>
            <p v-else class="mt-1 text-sm font-semibold text-slate-800">-</p>
          </div>
          <div class="rounded-xl border border-slate-100 px-4 py-3">
            <p class="text-xs text-slate-400">{{ t('sellerCollection.scheduleCard.limit') }}</p>
            <p class="mt-1 text-sm font-semibold text-slate-800">{{ schedule?.item_limit ?? '-' }}</p>
          </div>
          <div class="rounded-xl border border-slate-100 px-4 py-3">
            <p class="text-xs text-slate-400">{{ t('sellerCollection.scheduleCard.strategy') }}</p>
            <p class="mt-1 text-sm font-semibold text-slate-800">{{ schedule?.account_strategy || '-' }}</p>
          </div>
          <div class="rounded-xl border border-slate-100 px-4 py-3">
            <p class="text-xs text-slate-400">{{ t('sellerCollection.scheduleCard.account') }}</p>
            <p class="mt-1 font-mono text-xs font-semibold text-slate-800">
              {{ schedule?.account_state_file || '-' }}
            </p>
          </div>
          <div class="rounded-xl border border-slate-100 px-4 py-3">
            <p class="text-xs text-slate-400">{{ t('sellerCollection.scheduleCard.browserMode') }}</p>
            <p class="mt-1 text-sm font-semibold text-slate-800">
              {{
                (schedule?.run_headless ?? schedule?.run_headless_effective)
                  ? t('sellerCollection.scheduleCard.headless')
                  : t('sellerCollection.scheduleCard.headed')
              }}
            </p>
          </div>
        </div>
        <p
          v-if="!isLoading && scheduleJobMissing"
          class="mt-3 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm font-medium text-amber-900"
        >
          {{ t('sellerCollection.scheduleCard.jobMissingHint') }}
        </p>
      </CardContent>
    </Card>

    <div
      v-if="!consoleLogEnabled"
      class="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600"
    >
      <p class="font-medium text-slate-800">{{ t('sellerCollection.consoleLog.disabledTitle') }}</p>
      <p class="mt-1 text-xs">{{ t('sellerCollection.consoleLog.disabledHint') }}</p>
    </div>

    <Card v-if="consoleLogEnabled" class="app-surface border-none">
      <CardHeader class="flex flex-row flex-wrap items-center justify-between gap-3 pb-2">
        <div>
          <CardTitle class="text-base">{{ t('sellerCollection.consoleLog.title') }}</CardTitle>
          <p class="mt-1 text-xs text-slate-500">{{ t('sellerCollection.consoleLog.hint') }}</p>
        </div>
        <Button variant="outline" size="sm" @click="loadLatestTail().then(() => scrollConsoleLogToBottom())">
          {{ t('common.refresh') }}
        </Button>
      </CardHeader>
      <CardContent>
        <pre
          ref="logContainer"
          class="max-h-[420px] min-h-[200px] overflow-auto rounded-lg bg-slate-950 p-4 font-mono text-xs leading-relaxed text-slate-100 whitespace-pre-wrap break-all"
        >{{ consoleLogs || t('sellerCollection.consoleLog.empty') }}</pre>
      </CardContent>
    </Card>

    <SellerScheduleDialog
      :open="isScheduleDialogOpen"
      :schedule="schedule"
      @update:open="(value: boolean) => (isScheduleDialogOpen = value)"
      @saved="handleScheduleSaved"
    />
  </div>
</template>
