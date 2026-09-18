<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Button } from '@/components/ui/button'
import { ChevronLeft, ChevronRight } from 'lucide-vue-next'

const props = defineProps<{
  page: number
  pageSize: number
  total: number
}>()

const emit = defineEmits<{
  (e: 'update:page', page: number): void
  (e: 'update:pageSize', size: number): void
}>()

const { t } = useI18n()

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))

const pageNumbers = computed(() => {
  const max = totalPages.value
  let start = Math.max(1, props.page - 2)
  let end = Math.min(max, start + 4)
  start = Math.max(1, end - 4)
  const pages: number[] = []
  for (let i = start; i <= end; i++) pages.push(i)
  return pages
})

const hasPrev = computed(() => props.page > 1)
const hasNext = computed(() => props.page < totalPages.value)

function goTo(page: number) {
  if (page < 1 || page > totalPages.value || page === props.page) return
  emit('update:page', page)
}
</script>

<template>
  <div class="flex flex-wrap items-center justify-between gap-3 text-sm">
    <p class="text-xs text-slate-500">
      {{ t('pagination.total', { total, pageSize }) }}
    </p>

    <div class="flex items-center gap-1">
      <Button
        variant="outline"
        size="sm"
        class="h-8 w-8 p-0"
        :disabled="!hasPrev"
        :aria-label="t('pagination.prev')"
        @click="goTo(page - 1)"
      >
        <ChevronLeft class="h-4 w-4" />
      </Button>

      <template v-for="num in pageNumbers" :key="num">
        <Button
          variant="outline"
          size="sm"
          class="h-8 min-w-8 px-2"
          :class="num === page ? 'bg-primary text-white border-primary' : ''"
          @click="goTo(num)"
        >
          {{ num }}
        </Button>
      </template>

      <Button
        variant="outline"
        size="sm"
        class="h-8 w-8 p-0"
        :disabled="!hasNext"
        :aria-label="t('pagination.next')"
        @click="goTo(page + 1)"
      >
        <ChevronRight class="h-4 w-4" />
      </Button>

      <select
        class="ml-2 h-8 rounded-md border bg-white px-2 text-xs"
        :value="pageSize"
        :aria-label="t('pagination.pageSize')"
        @change="emit('update:pageSize', Number(($event.target as HTMLSelectElement).value))"
      >
        <option :value="20">20 / 页</option>
        <option :value="50">50 / 页</option>
        <option :value="100">100 / 页</option>
      </select>
    </div>
  </div>
</template>
