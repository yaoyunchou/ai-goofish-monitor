<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { addNote, listNoteAccounts, type NoteAccount } from '@/api/xhsNotes'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from '@/components/ui/toast'

const { t } = useI18n()
const router = useRouter()
const url = ref('')
const accountId = ref<number | null>(null)
const accounts = ref<NoteAccount[]>([])
const saving = ref(false)

onMounted(async () => {
  accounts.value = await listNoteAccounts()
  accountId.value = accounts.value[0]?.id ?? null
})

async function submit() {
  saving.value = true
  try {
    await addNote(url.value.trim(), accountId.value)
    toast({ title: t('xhs.notesAdd') })
    await router.push('/xhs/notes')
  } catch (error) {
    toast({ title: t('xhs.addFailed'), description: error instanceof Error ? error.message : '', variant: 'destructive' })
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="mx-auto max-w-xl space-y-4 p-4">
    <h1 class="text-xl font-semibold">{{ t('xhs.notesAdd') }}</h1>
    <div class="grid gap-2">
      <Label>{{ t('xhs.noteUrl') }}</Label>
      <Input v-model="url" placeholder="https://www.xiaohongshu.com/explore/..." />
    </div>
    <div class="grid gap-2">
      <Label>{{ t('xhs.noteAccount') }}</Label>
      <p v-if="accounts.length === 0" class="text-sm text-muted-foreground">{{ t('xhs.noteAccountEmpty') }}</p>
      <select v-else v-model="accountId" class="h-9 rounded-md border bg-background px-3 text-sm">
        <option v-for="account in accounts" :key="account.id" :value="account.id">{{ account.name }}</option>
      </select>
    </div>
    <Button :disabled="saving || !url.trim()" @click="submit">{{ t('common.save') }}</Button>
  </div>
</template>
