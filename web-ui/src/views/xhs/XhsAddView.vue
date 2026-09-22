<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  addXhsProduct,
  downloadXhsTemplate,
  importXhsProducts,
  listXhsProducts,
  listXhsShops,
} from '@/api/xhs'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { toast } from '@/components/ui/toast'

const { t } = useI18n()
const lines = ref('')
const shopName = ref('')
const category = ref('')
const tagDraft = ref('')
const draftTags = ref<string[]>([])
const shopOptions = ref<string[]>([])
const categories = ref<string[]>([])
const fileInput = ref<HTMLInputElement | null>(null)
const saving = ref(false)
const results = ref<{ line: string; ok: boolean; reason?: string }[]>([])

const parsedLines = computed(() =>
  lines.value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean),
)

function pushDraftTag() {
  const tag = tagDraft.value.trim()
  if (!tag || draftTags.value.includes(tag)) {
    tagDraft.value = ''
    return
  }
  draftTags.value = [...draftTags.value, tag]
  tagDraft.value = ''
}

async function loadOptions() {
  try {
    const [products, shops] = await Promise.all([listXhsProducts(), listXhsShops()])
    shopOptions.value = shops.items.map((shop) => shop.name)
    categories.value = [...new Set(products.map((item) => item.category).filter((name): name is string => Boolean(name)))]
  } catch {
    shopOptions.value = []
    categories.value = []
  }
}

async function addLines() {
  pushDraftTag()
  const urls = parsedLines.value
  if (!urls.length) return
  saving.value = true
  results.value = []
  try {
    for (const url of urls) {
      try {
        await addXhsProduct({
          url,
          shop_name: shopName.value.trim() || null,
          category: category.value.trim() || null,
          tags: draftTags.value,
        })
        results.value.push({ line: url, ok: true })
      } catch (error) {
        results.value.push({
          line: url,
          ok: false,
          reason: error instanceof Error ? error.message : t('xhs.addFailed'),
        })
      }
    }
    const failed = results.value.filter((item) => !item.ok).length
    toast({
      title: t('xhs.addDone', { ok: results.value.length - failed, failed }),
      variant: failed ? 'destructive' : 'default',
    })
    if (failed < results.value.length) lines.value = ''
  } finally {
    saving.value = false
  }
}

async function downloadTemplate() {
  try {
    await downloadXhsTemplate()
  } catch (error) {
    toast({ title: t('common.error'), description: error instanceof Error ? error.message : t('xhs.loadFailed'), variant: 'destructive' })
  }
}

async function onImport(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  saving.value = true
  try {
    const result = await importXhsProducts(file)
    results.value = result.failed.map((item) => ({
      line: t('xhs.importRow', { row: item.row }),
      ok: false,
      reason: item.reason,
    }))
    toast({
      title: t('xhs.importResult', { added: result.added, updated: result.updated, failed: result.failed.length }),
      variant: result.failed.length ? 'destructive' : 'default',
    })
  } catch (error) {
    toast({ title: t('common.error'), description: error instanceof Error ? error.message : t('xhs.addFailed'), variant: 'destructive' })
  } finally {
    saving.value = false
  }
}

onMounted(loadOptions)
</script>

<template>
  <div class="space-y-4 p-4">
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 class="text-xl font-semibold">{{ t('xhs.addTitle') }}</h1>
        <p class="text-sm text-muted-foreground">{{ t('xhs.addPageHint') }}</p>
      </div>
      <Button variant="outline" as-child>
        <RouterLink to="/xhs">{{ t('xhs.goBoard') }}</RouterLink>
      </Button>
    </div>

    <Card>
      <CardHeader>
        <CardTitle class="text-base">{{ t('xhs.addLinesTitle') }}</CardTitle>
      </CardHeader>
      <CardContent class="space-y-3">
        <Textarea v-model="lines" class="min-h-48 font-mono" :placeholder="t('xhs.addLinesPlaceholder')" />
        <div class="flex flex-wrap gap-2">
          <Input v-model="shopName" class="max-w-xs" list="xhs-add-shops" :placeholder="t('xhs.shopPlaceholder')" />
          <Input v-model="category" class="max-w-xs" list="xhs-add-categories" :placeholder="t('xhs.categoryPlaceholder')" />
          <Input v-model="tagDraft" class="max-w-xs" :placeholder="t('xhs.tagPlaceholder')" @keyup.enter="pushDraftTag" />
        </div>
        <datalist id="xhs-add-shops">
          <option v-for="name in shopOptions" :key="name" :value="name" />
        </datalist>
        <datalist id="xhs-add-categories">
          <option v-for="name in categories" :key="name" :value="name" />
        </datalist>
        <div v-if="draftTags.length" class="flex flex-wrap gap-2">
          <button
            v-for="tag in draftTags"
            :key="tag"
            type="button"
            class="rounded-full bg-muted px-2 py-0.5 text-xs"
            @click="draftTags = draftTags.filter((item) => item !== tag)"
          >
            {{ tag }} ×
          </button>
        </div>
        <div class="flex flex-wrap gap-2">
          <Button :disabled="saving || !parsedLines.length" @click="addLines">{{ t('xhs.addLines') }}</Button>
          <Button variant="outline" :disabled="saving" @click="lines = ''">{{ t('xhs.clearLines') }}</Button>
        </div>
      </CardContent>
    </Card>

    <Card>
      <CardHeader>
        <CardTitle class="text-base">{{ t('xhs.importExcel') }}</CardTitle>
      </CardHeader>
      <CardContent class="flex flex-wrap gap-2">
        <Button variant="outline" :disabled="saving" @click="downloadTemplate">{{ t('xhs.downloadTemplate') }}</Button>
        <Button variant="outline" :disabled="saving" @click="fileInput?.click()">{{ t('xhs.importExcel') }}</Button>
        <input ref="fileInput" class="hidden" type="file" accept=".xlsx" @change="onImport" />
      </CardContent>
    </Card>

    <div v-if="results.length" class="overflow-x-auto rounded-lg border">
      <table class="w-full text-sm">
        <tbody>
          <tr v-for="(item, index) in results" :key="index" class="border-t first:border-t-0">
            <td class="p-3">{{ item.line }}</td>
            <td class="p-3" :class="item.ok ? 'text-muted-foreground' : 'text-destructive'">
              {{ item.ok ? t('xhs.addOk') : item.reason }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
