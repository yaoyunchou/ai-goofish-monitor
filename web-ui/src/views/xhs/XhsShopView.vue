<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { getXhsShop, xhsCoverSrc, type XhsProduct, type XhsShopSummary } from '@/api/xhs'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

const route = useRoute()
const { t } = useI18n()
const shop = ref<(XhsShopSummary & { items: XhsProduct[] }) | null>(null)
const errorText = ref('')
const shopId = computed(() => String(route.params.shopId || ''))

function showDelta(value: number | null | undefined, incomplete?: boolean) {
  if (value === null || value === undefined) return '—'
  const text = value > 0 ? `+${value}` : String(value)
  return incomplete ? `${text}*` : text
}

async function load() {
  errorText.value = ''
  try {
    shop.value = await getXhsShop(shopId.value)
  } catch (error) {
    shop.value = null
    errorText.value = error instanceof Error ? error.message : t('xhs.loadFailed')
  }
}

onMounted(load)
watch(shopId, load)
</script>

<template>
  <div class="space-y-4 p-4">
    <div>
      <RouterLink class="text-sm text-muted-foreground hover:underline" to="/xhs/shops">{{ t('xhs.backShops') }}</RouterLink>
      <h1 class="text-xl font-semibold">{{ shop?.name || shopId }}</h1>
      <p class="text-sm text-muted-foreground">{{ t('xhs.soldHint') }}</p>
    </div>
    <p v-if="errorText" class="text-sm text-destructive">{{ errorText }}</p>
    <div v-if="shop" class="grid gap-3 sm:grid-cols-4">
      <Card>
        <CardHeader><CardTitle>{{ t('xhs.colSold') }}</CardTitle></CardHeader>
        <CardContent>{{ shop.sold_total ?? '—' }}</CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>{{ t('xhs.colToday') }}</CardTitle></CardHeader>
        <CardContent>{{ showDelta(shop.today, shop.today_incomplete) }}</CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>{{ t('xhs.colYesterday') }}</CardTitle></CardHeader>
        <CardContent>{{ showDelta(shop.yesterday, shop.yesterday_incomplete) }}</CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>{{ t('xhs.colHour') }}</CardTitle></CardHeader>
        <CardContent>{{ showDelta(shop.last_hour, shop.last_hour_incomplete) }}</CardContent>
      </Card>
    </div>
    <div class="overflow-x-auto rounded-lg border">
      <table class="w-full min-w-[640px] text-sm">
        <thead class="bg-muted/40 text-left">
          <tr>
            <th class="p-3">{{ t('xhs.colProduct') }}</th>
            <th class="p-3">{{ t('xhs.colSold') }}</th>
            <th class="p-3">{{ t('xhs.colToday') }}</th>
            <th class="p-3">{{ t('xhs.colYesterday') }}</th>
            <th class="p-3">{{ t('xhs.colHour') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in shop?.items || []" :key="item.id" class="border-t">
            <td class="p-3">
              <div class="flex items-center gap-2">
                <img v-if="item.cover_url" :src="xhsCoverSrc(item.cover_url)" alt="" class="h-10 w-10 rounded object-cover" />
                <div>
                  <RouterLink class="font-medium hover:underline" :to="`/xhs/${item.id}`">{{ item.title || item.id }}</RouterLink>
                  <div class="text-xs text-muted-foreground">
                    <span v-if="item.category">{{ item.category }}</span>
                    <span v-if="item.tags?.length"> · {{ item.tags.join('、') }}</span>
                  </div>
                </div>
              </div>
            </td>
            <td class="p-3">{{ item.sold_total ?? '—' }}</td>
            <td class="p-3">{{ showDelta(item.today, item.today_incomplete) }}</td>
            <td class="p-3">{{ showDelta(item.yesterday, item.yesterday_incomplete) }}</td>
            <td class="p-3">{{ showDelta(item.last_hour, item.last_hour_incomplete) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
