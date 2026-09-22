<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { createXhsShop, listXhsShops, type XhsShopList } from '@/api/xhs'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { toast } from '@/components/ui/toast'

const { t } = useI18n()
const data = ref<XhsShopList | null>(null)
const shopName = ref('')
const loading = ref(false)

function showDelta(value: number | null | undefined, incomplete?: boolean) {
  if (value === null || value === undefined) return '—'
  const text = value > 0 ? `+${value}` : String(value)
  return incomplete ? `${text}*` : text
}

async function load() {
  loading.value = true
  try {
    data.value = await listXhsShops()
  } catch (error) {
    toast({ title: t('common.error'), description: error instanceof Error ? error.message : t('xhs.loadFailed'), variant: 'destructive' })
  } finally {
    loading.value = false
  }
}

async function createShop() {
  const name = shopName.value.trim()
  if (!name) return
  try {
    await createXhsShop(name)
    shopName.value = ''
    await load()
  } catch (error) {
    toast({ title: t('common.error'), description: error instanceof Error ? error.message : t('xhs.addFailed'), variant: 'destructive' })
  }
}

onMounted(load)
</script>

<template>
  <div class="space-y-4 p-4">
    <div>
      <h1 class="text-xl font-semibold">{{ t('xhs.shopsTitle') }}</h1>
      <p class="text-sm text-muted-foreground">{{ t('xhs.shopsHint') }}</p>
    </div>
    <div class="flex flex-wrap gap-2">
      <Input v-model="shopName" class="max-w-xs" :placeholder="t('xhs.newShopPlaceholder')" @keyup.enter="createShop" />
      <Button @click="createShop">{{ t('xhs.newShop') }}</Button>
    </div>
    <p v-if="loading" class="text-sm text-muted-foreground">{{ t('xhs.loading') }}</p>
    <p v-else-if="!data?.items.length" class="text-sm text-muted-foreground">{{ t('xhs.shopsEmpty') }}</p>
    <div class="grid gap-3 md:grid-cols-2">
      <RouterLink v-for="shop in data?.items || []" :key="shop.id" :to="`/xhs/shops/${shop.id}`">
        <Card class="h-full hover:bg-muted/30">
          <CardHeader>
            <CardTitle class="text-base">{{ shop.name }}</CardTitle>
          </CardHeader>
          <CardContent class="grid grid-cols-2 gap-2 text-sm">
            <div>{{ t('xhs.colProduct') }} {{ shop.product_count }}</div>
            <div>{{ t('xhs.colSold') }} {{ shop.sold_total ?? '—' }}</div>
            <div>{{ t('xhs.colToday') }} {{ showDelta(shop.today, shop.today_incomplete) }}</div>
            <div>{{ t('xhs.colYesterday') }} {{ showDelta(shop.yesterday, shop.yesterday_incomplete) }}</div>
            <div>{{ t('xhs.colHour') }} {{ showDelta(shop.last_hour, shop.last_hour_incomplete) }}</div>
          </CardContent>
        </Card>
      </RouterLink>
    </div>
    <Card v-if="data && data.unassigned.product_count">
      <CardHeader>
        <CardTitle class="text-base">{{ t('xhs.unassigned') }} · {{ data.unassigned.product_count }}</CardTitle>
      </CardHeader>
      <CardContent class="space-y-2 text-sm">
        <RouterLink
          v-for="item in data.unassigned.items"
          :key="item.id"
          class="block hover:underline"
          :to="`/xhs/${item.id}`"
        >
          {{ item.title || item.id }}
        </RouterLink>
      </CardContent>
    </Card>
  </div>
</template>
