<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { collectNotes, listNotes, removeNote, type XhsNote } from '@/api/xhsNotes'
import { Button } from '@/components/ui/button'
import { toast } from '@/components/ui/toast'

const { t } = useI18n()
const items = ref<XhsNote[]>([])
const loading = ref(false)
const collecting = ref(false)

function deltaText(value: number | null | undefined) {
  if (value === null || value === undefined) return t('xhs.deltaNone')
  return value > 0 ? `+${value}` : String(value)
}

async function load() {
  loading.value = true
  try {
    items.value = await listNotes()
  } catch (error) {
    toast({ title: t('common.error'), description: error instanceof Error ? error.message : t('xhs.loadFailed'), variant: 'destructive' })
  } finally {
    loading.value = false
  }
}

async function collectAll() {
  collecting.value = true
  try {
    const summary = await collectNotes()
    toast({ title: summary.error || t('xhs.collected', { saved: summary.saved }) })
    await load()
  } catch (error) {
    toast({ title: t('xhs.collectFailed'), description: error instanceof Error ? error.message : '', variant: 'destructive' })
  } finally {
    collecting.value = false
  }
}

async function collectOne(id: string) {
  collecting.value = true
  try {
    await collectNotes(id)
    await load()
  } catch (error) {
    toast({ title: t('xhs.collectFailed'), description: error instanceof Error ? error.message : '', variant: 'destructive' })
  } finally {
    collecting.value = false
  }
}

async function remove(id: string) {
  await removeNote(id)
  await load()
}

onMounted(load)
</script>

<template>
  <div class="space-y-4 p-4">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 class="text-xl font-semibold">{{ t('xhs.notesTitle') }}</h1>
        <p class="text-sm text-muted-foreground">{{ t('xhs.notesHint') }}</p>
      </div>
      <div class="flex gap-2">
        <RouterLink to="/xhs/notes/add" class="inline-flex h-9 items-center rounded-md border px-3 text-sm">{{ t('xhs.notesAdd') }}</RouterLink>
        <RouterLink to="/xhs/notes/settings" class="inline-flex h-9 items-center rounded-md border px-3 text-sm">{{ t('xhs.notesSettings') }}</RouterLink>
        <Button :disabled="collecting" @click="collectAll">{{ t('xhs.notesCollect') }}</Button>
      </div>
    </div>
    <p v-if="loading" class="text-sm text-muted-foreground">{{ t('xhs.loading') }}</p>
    <p v-else-if="items.length === 0" class="text-sm text-muted-foreground">{{ t('xhs.notesEmpty') }}</p>
    <div v-else class="overflow-x-auto rounded-lg border">
      <table class="w-full text-sm">
        <thead class="bg-muted/40 text-left">
          <tr>
            <th class="p-3">{{ t('xhs.colProduct') }}</th>
            <th class="p-3">{{ t('xhs.colLike') }}</th>
            <th class="p-3">{{ t('xhs.colCollect') }}</th>
            <th class="p-3">{{ t('xhs.colComment') }}</th>
            <th class="p-3">{{ t('xhs.colView') }}</th>
            <th class="p-3"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="note in items" :key="note.id" class="border-t">
            <td class="p-3">
              <p class="font-medium">{{ note.title || note.id }}</p>
              <p class="text-xs text-muted-foreground">{{ note.author_name || note.snapshot_day || '' }}</p>
              <p v-if="note.last_error" class="text-xs text-destructive">{{ note.last_error }}</p>
            </td>
            <td class="p-3">{{ note.metrics.liked_count ?? t('xhs.deltaNone') }} <span class="text-muted-foreground">{{ deltaText(note.deltas.liked_count) }}</span></td>
            <td class="p-3">{{ note.metrics.collected_count ?? t('xhs.deltaNone') }} <span class="text-muted-foreground">{{ deltaText(note.deltas.collected_count) }}</span></td>
            <td class="p-3">{{ note.metrics.comment_count ?? t('xhs.deltaNone') }} <span class="text-muted-foreground">{{ deltaText(note.deltas.comment_count) }}</span></td>
            <td class="p-3">{{ note.metrics.view_count ?? t('xhs.deltaNone') }} <span class="text-muted-foreground">{{ deltaText(note.deltas.view_count) }}</span></td>
            <td class="p-3 text-right">
              <Button size="sm" variant="outline" :disabled="collecting" @click="collectOne(note.id)">{{ t('xhs.notesCollectOne') }}</Button>
              <Button size="sm" variant="ghost" @click="remove(note.id)">{{ t('xhs.notesRemove') }}</Button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
