import { onUnmounted, ref } from 'vue'
import { getLogs } from '@/api/logs'

/** 与后端 SELLER_SUBSCRIPTION_JOB_ID 一致 */
export const SELLER_SUBSCRIPTION_LOG_TASK_ID = -1

const MAX_LOG_CHARS = 120_000
const TRIM_LOG_CHARS = 80_000

export function useSellerSubscriptionConsoleLog() {
  const logs = ref('')
  const currentPos = ref(0)
  const isPolling = ref(false)
  let pollTimer: number | ReturnType<typeof setInterval> | null = null

  function appendLogs(content: string) {
    if (!content) return
    logs.value += content
    if (logs.value.length > MAX_LOG_CHARS) {
      logs.value = logs.value.slice(-TRIM_LOG_CHARS)
    }
  }

  async function fetchIncremental() {
    try {
      const data = await getLogs(currentPos.value, SELLER_SUBSCRIPTION_LOG_TASK_ID)
      if (data.new_pos < currentPos.value) {
        logs.value = ''
      }
      if (data.new_content) {
        appendLogs(data.new_content)
      }
      currentPos.value = data.new_pos
    } catch {
      // ignore transient errors during polling
    }
  }

  async function loadLatestTail() {
    logs.value = ''
    currentPos.value = 0
    await fetchIncremental()
  }

  function startPolling(intervalMs = 2000) {
    if (pollTimer) return
    isPolling.value = true
    fetchIncremental()
    pollTimer = window.setInterval(fetchIncremental, intervalMs)
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
    isPolling.value = false
  }

  onUnmounted(stopPolling)

  return {
    logs,
    isPolling,
    loadLatestTail,
    startPolling,
    stopPolling,
    fetchIncremental,
  }
}
