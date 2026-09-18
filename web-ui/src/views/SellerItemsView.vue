<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { listSellerSubscriptions, type SellerMetricItem } from '@/api/sellerSubscriptions'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import SellerItemsTable from '@/components/sellers/SellerItemsTable.vue'

const router = useRouter()

const { t } = useI18n()
const sellerFilter = ref('')
const sellers = ref<{ seller_user_id: string; display_name: string }[]>([])

const sellerNameMap = computed(() => {
  const map: Record<string, string> = {}
  for (const seller of sellers.value) {
    map[seller.seller_user_id] = seller.display_name
  }
  return map
})

async function loadSellers() {
  try {
    const overview = await listSellerSubscriptions()
    sellers.value = (overview.items || []).map((row) => ({
      seller_user_id: row.seller_user_id,
      display_name: row.profile_nickname || row.nickname || row.seller_user_id,
    }))
  } catch {
    sellers.value = []
  }
}

function onItemClick(item: SellerMetricItem) {
  router.push({
    name: 'SellerItemDetail',
    params: { itemId: item.item_id },
    query: { from: 'items' },
  })
}

onMounted(loadSellers)
</script>

<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-2xl font-black text-slate-900">{{ t('sellerItems.title') }}</h1>
      <p class="text-sm text-slate-500">{{ t('sellerItems.description') }}</p>
    </div>

    <Card class="app-surface border-none">
      <CardHeader class="flex flex-row flex-wrap items-center justify-between gap-3">
        <CardTitle class="text-base">{{ t('sellerItems.tableTitle') }}</CardTitle>
        <select
          v-model="sellerFilter"
          class="h-9 min-w-[220px] rounded-md border bg-white px-3 text-sm"
        >
          <option value="">{{ t('sellerItems.filterAll') }}</option>
          <option v-for="seller in sellers" :key="seller.seller_user_id" :value="seller.seller_user_id">
            {{ seller.display_name }}
          </option>
        </select>
      </CardHeader>
      <CardContent>
        <SellerItemsTable
          :seller-id="sellerFilter || undefined"
          :show-seller="true"
          :seller-name-map="sellerNameMap"
          @item-click="onItemClick"
        />
      </CardContent>
    </Card>
  </div>
</template>
