<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import * as collectionsApi from '@/api/collections'
import type { CollectionItem, CollectionDetailData } from '@/types/collection.d.ts'
import { Button } from '@/components/ui/button'
import { toast } from '@/components/ui/toast'
import { formatDateTime } from '@/i18n'
import { ArrowLeft, ExternalLink, RefreshCw, MapPin, Eye, Heart, Package, Truck, ShieldCheck, Star, Clock, TrendingUp, UserCheck } from 'lucide-vue-next'
import * as sellersApi from '@/api/sellers'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const collection = ref<CollectionItem | null>(null)
const isLoading = ref(true)
const isRefreshing = ref(false)
const activeImage = ref(0)
let pollTimer: ReturnType<typeof setInterval> | null = null

const collectionId = computed(() => Number(route.params.id))
const detail = computed<CollectionDetailData>(() => collection.value?.detail_data || {})
const itemDO = computed(() => detail.value?.itemDO || {})
const sellerDO = computed(() => detail.value?.sellerDO || {})
const title = computed(() => itemDO.value?.title || collection.value?.summary?.title || '')
const link = computed(() => collection.value?.summary?.link || '')
const price = computed(() => collection.value?.summary?.price_display || itemDO.value?.soldPrice || '')
const recordData = computed(() => collection.value?.record as Record<string, any> || {})
const productInfo = computed(() => recordData.value?.['商品信息'] as Record<string, any> || {})
const sellerInfo = computed(() => recordData.value?.['卖家信息'] as Record<string, any> || {})
const aiAnalysis = computed(() => recordData.value?.['ai_analysis'] as Record<string, any> || {})

const images = computed(() => {
  // 优先 detail_data.itemDO.imageInfos，兜底 record.商品信息.商品图片列表
  const fromDetail = (itemDO.value?.imageInfos || []).map(i => i.url).filter((u): u is string => !!u)
  if (fromDetail.length > 0) return fromDetail
  const fromRecord = productInfo.value?.['商品图片列表'] as string[] || []
  const mainImg = productInfo.value?.['商品主图链接'] as string
  if (fromRecord.length > 0) return fromRecord
  if (mainImg) return [mainImg]
  return []
})
const labels = computed(() => {
  // 优先 detail_data.itemDO，兜底 DB 结构化列 item_labels
  const ext = (itemDO.value?.itemLabelExtList || []).map((l: any) => ({ label: l.propertyText || '', value: l.valueText || '' }))
  const cpv = (itemDO.value?.cpvLabels || []).map((l: any) => ({ label: l.propertyName || '', value: l.valueName || '' }))
  const fromDetail = [...ext, ...cpv].filter(l => l.label && l.value)
  if (fromDetail.length > 0) {
    const seen = new Set<string>()
    return fromDetail.filter(l => {
      const key = `${l.label}:${l.value}`
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
  }
  return (collection.value?.item_labels || []) as { label: string; value: string }[]
})
const tags = computed(() => {
  const fromDetail = [...(itemDO.value?.commonTags || []), ...(itemDO.value?.priceRelativeTags || [])].map(t => t.text || '').filter(Boolean)
  if (fromDetail.length > 0) return fromDetail
  return (collection.value?.common_tags || []) as string[]
})
const recommendTags = computed(() => (itemDO.value?.recommendTagList || []).map(t => t.text || '').filter(Boolean))
const publishDate = computed(() => {
  const ts = itemDO.value?.gmtCreate
  if (!ts) return '—'
  return new Date(ts).toLocaleDateString('zh-CN')
})
const categoryPath = computed(() => {
  const cat = itemDO.value?.itemCatDTO
  if (!cat) return ''
  return [cat.catId, cat.channelCatId, cat.leafId].filter(Boolean).join(' / ')
})
const sellerRegisterDate = computed(() => {
  const ts = sellerDO.value?.registerTime
  if (!ts) return ''
  return new Date(ts).toLocaleDateString('zh-CN')
})
const sellerItems = computed(() => sellerDO.value?.sellerItems || [])
const sellerRemarks = computed(() => sellerDO.value?.remarkDO || null)
// 闲鱼个人主页 URL：优先 pageUserId，回退 userId / sellerId
const sellerHomePage = computed(() => {
  const uid = sellerDO.value?.pageUserId || sellerDO.value?.userId || sellerDO.value?.sellerId
  if (!uid) return ''
  return `https://www.goofish.com/personal?userId=${uid}`
})
// SKU 列表（来自 detail_data.itemDO.skuList / idleItemSkuList）
const detailSkus = computed(() => {
  const list = itemDO.value?.skuList || itemDO.value?.idleItemSkuList || []
  return list.map(s => {
    const props = (s.propertyList || []).map(p => `${p.propertyText}:${p.valueText}`).join(' / ')
    const price = s.priceInCent ? `¥${(s.priceInCent / 100).toFixed(2)}` : (s.price ? `¥${(s.price / 100).toFixed(2)}` : '—')
    return { skuId: s.skuId, props, price, quantity: s.quantity, image: s.propertyImage?.url }
  })
})
// trackParams（顶层）
const trackParams = computed(() => detail.value?.trackParams || {})
// buyerDO
const buyerDO = computed(() => detail.value?.buyerDO || {})
// configInfo
const configInfo = computed(() => detail.value?.configInfo || {})
// 分享数据中的图片
const shareImages = computed(() => {
  const raw = itemDO.value?.shareData?.shareInfoJsonString
  if (!raw) return []
  try {
    const obj = JSON.parse(raw)
    return (obj.images || []).map((i: any) => i.image).filter(Boolean)
  } catch { return [] }
})
const shareContent = computed(() => {
  const raw = itemDO.value?.shareData?.shareInfoJsonString
  if (!raw) return ''
  try {
    const obj = JSON.parse(raw)
    return obj.contentParams?.mainParams?.content || ''
  } catch { return '' }
})
const fetchMethod = computed(() => (collection.value?.sku_meta as Record<string, unknown> | undefined)?.fetch_method as string || '')

async function loadCollection(silent = false) {
  if (!silent) isLoading.value = true
  try {
    collection.value = await collectionsApi.getCollection(collectionId.value)
    await checkFollowStatus()
  } catch (error: any) {
    toast({ title: t('collections.detail.loadFailed'), description: error?.message || String(error), variant: 'destructive' })
  } finally {
    if (!silent) isLoading.value = false
  }
}

// 关注卖家相关
const isFollowing = ref(false)
const followLoading = ref(false)
const followedSellerId = computed(() => {
  const v = sellerDO.value?.sellerId || sellerDO.value?.pageUserId || sellerDO.value?.userId || ''
  return v ? String(v) : ''
})

async function checkFollowStatus() {
  if (!followedSellerId.value) { isFollowing.value = false; return }
  try {
    await sellersApi.getSeller(followedSellerId.value)
    isFollowing.value = true
  } catch {
    isFollowing.value = false
  }
}

async function toggleFollowSeller() {
  if (!followedSellerId.value) {
    toast({ title: '无法关注', description: '缺少卖家ID', variant: 'destructive' })
    return
  }
  followLoading.value = true
  try {
    if (isFollowing.value) {
      await sellersApi.unfollowSeller(followedSellerId.value)
      isFollowing.value = false
      toast({ title: '已取消关注' })
    } else {
      await sellersApi.followSeller({
        seller_id: followedSellerId.value,
        seller_name: sellerDO.value?.uniqueName || sellerDO.value?.nick || '',
        avatar_url: sellerDO.value?.portraitUrl || sellerDO.value?.avatarUrl || '',
        city: sellerDO.value?.city || '',
      })
      isFollowing.value = true
      toast({ title: '已关注卖家' })
    }
  } catch (e: any) {
    toast({ title: '操作失败', description: e?.message, variant: 'destructive' })
  } finally {
    followLoading.value = false
  }
}

async function handleRefresh() {
  isRefreshing.value = true
  try {
    const res = await collectionsApi.refreshCollectionSkus(collectionId.value)
    collection.value = res.collection
    toast({ title: t('collections.detail.refreshStarted') })
    startPolling()
  } catch (error: any) {
    toast({ title: t('collections.detail.refreshFailed'), description: error?.message || String(error), variant: 'destructive' })
  } finally {
    isRefreshing.value = false
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(async () => {
    if (!collection.value || !['pending','running'].includes(collection.value.sku_fetch_status)) { stopPolling(); return }
    await loadCollection(true)
  }, 2500)
}

function stopPolling() { if (pollTimer) { clearInterval(pollTimer); pollTimer = null } }
onMounted(async () => { await loadCollection(); startPolling() })
onUnmounted(stopPolling)
</script>

<template>
  <div class="space-y-6">
    <div class="flex flex-wrap items-center gap-3">
      <Button variant="outline" size="sm" @click="router.push({ name: 'Collections' })">
        <ArrowLeft class="w-4 h-4 mr-1" />{{ t('collections.detail.back') }}
      </Button>
      <h1 class="text-2xl font-bold text-slate-800">{{ t('collections.detail.title') }}</h1>
      <div class="ml-auto flex gap-2">
        <Button variant="outline" size="sm" :disabled="isRefreshing" @click="handleRefresh">
          <RefreshCw class="w-4 h-4 mr-1" :class="{ 'animate-spin': isRefreshing }" />{{ t('collections.detail.refreshSkus') }}
        </Button>
        <Button v-if="link" variant="default" size="sm" as-child>
          <a :href="link" target="_blank" rel="noopener noreferrer">
            <ExternalLink class="w-4 h-4 mr-1" />{{ t('collections.detail.openXianyu') }}
          </a>
        </Button>
      </div>
    </div>

    <div v-if="isLoading" class="app-surface p-8 text-center text-slate-500">{{ t('common.loading') }}</div>

    <template v-else-if="collection">
      <div class="app-surface px-5 py-3 flex flex-wrap items-center gap-3 text-sm">
        <span class="text-slate-500">{{ t('collections.detail.status') }}:</span>
        <span class="px-2 py-0.5 rounded-full font-medium text-xs" :class="{ 'bg-emerald-50 text-emerald-600': collection.sku_fetch_status === 'done', 'bg-rose-50 text-rose-600': collection.sku_fetch_status === 'failed', 'bg-amber-50 text-amber-600': ['pending','running'].includes(collection.sku_fetch_status) }">{{ collection.sku_fetch_status }}</span>
        <span v-if="fetchMethod" class="text-slate-400 text-xs">via {{ fetchMethod }}</span>
        <span v-if="collection.sku_error" class="text-rose-600 ml-2">{{ collection.sku_error }}</span>
        <span v-if="collection.sku_fetched_at" class="text-slate-400 ml-auto text-xs">{{ formatDateTime(collection.sku_fetched_at) }}</span>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div class="app-surface p-5">
          <div v-if="images.length > 0" class="space-y-3">
            <div class="aspect-square rounded-xl overflow-hidden bg-slate-100"><img :src="images[activeImage]" class="w-full h-full object-contain" :alt="title" /></div>
            <div v-if="images.length > 1" class="flex gap-2 overflow-x-auto pb-1">
              <button v-for="(img, i) in images" :key="i" class="w-16 h-16 rounded-lg overflow-hidden border-2 shrink-0 transition-colors" :class="i === activeImage ? 'border-primary' : 'border-transparent hover:border-slate-300'" @click="activeImage = i"><img :src="img" class="w-full h-full object-cover" :alt="`${title} ${i+1}`" /></button>
            </div>
          </div>
          <div v-else class="aspect-square flex items-center justify-center text-slate-300"><Package class="w-16 h-16" /></div>
        </div>

        <div class="app-surface p-5 space-y-4">
          <div>
            <div class="flex items-center gap-2 mb-1">
              <span v-if="itemDO.descTag" class="px-2 py-0.5 rounded text-xs font-medium bg-amber-50 text-amber-600">{{ itemDO.descTag }}</span>
              <span v-if="itemDO.itemStatusStr" class="px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-500">{{ itemDO.itemStatusStr }}</span>
            </div>
            <h2 class="text-xl font-bold text-slate-800 leading-snug">{{ title }}</h2>
            <div class="flex items-baseline gap-3 mt-2">
              <p v-if="price" class="text-rose-600 text-3xl font-bold">{{ price }}</p>
              <span v-if="itemDO.originalPrice && String(itemDO.originalPrice) !== String(itemDO.soldPrice)" class="text-slate-400 text-base line-through">¥{{ itemDO.originalPrice }}</span>
              <span v-if="itemDO.resellDiscount" class="px-2 py-0.5 rounded text-xs font-medium bg-rose-50 text-rose-600">{{ itemDO.resellDiscount }}</span>
            </div>
          </div>
          <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <div class="bg-slate-50 rounded-lg p-3 text-center"><Heart class="w-4 h-4 mx-auto text-rose-400 mb-1" /><p class="text-lg font-bold text-slate-700">{{ itemDO.wantCnt ?? '—' }}</p><p class="text-xs text-slate-400">{{ itemDO.wantCntUnit || '想要' }}</p></div>
            <div class="bg-slate-50 rounded-lg p-3 text-center"><Eye class="w-4 h-4 mx-auto text-slate-400 mb-1" /><p class="text-lg font-bold text-slate-700">{{ itemDO.browseCnt ?? '—' }}</p><p class="text-xs text-slate-400">浏览</p></div>
            <div class="bg-slate-50 rounded-lg p-3 text-center"><Star class="w-4 h-4 mx-auto text-amber-400 mb-1" /><p class="text-lg font-bold text-slate-700">{{ itemDO.collectCnt ?? '—' }}</p><p class="text-xs text-slate-400">收藏</p></div>
            <div class="bg-slate-50 rounded-lg p-3 text-center"><Package class="w-4 h-4 mx-auto text-slate-400 mb-1" /><p class="text-lg font-bold text-slate-700">{{ itemDO.quantity ?? '—' }}</p><p class="text-xs text-slate-400">库存</p></div>
            <div class="bg-slate-50 rounded-lg p-3 text-center"><TrendingUp class="w-4 h-4 mx-auto text-slate-400 mb-1" /><p class="text-lg font-bold text-slate-700">{{ itemDO.soldCnt ?? '—' }}</p><p class="text-xs text-slate-400">已售</p></div>
            <div class="bg-slate-50 rounded-lg p-3 text-center"><Clock class="w-4 h-4 mx-auto text-slate-400 mb-1" /><p class="text-sm font-bold text-slate-700">{{ publishDate }}</p><p class="text-xs text-slate-400">发布</p></div>
          </div>
          <div v-if="labels.length > 0">
            <p class="text-xs text-slate-400 mb-1.5">商品分类（itemLabelExtList + cpvLabels）</p>
            <div class="flex flex-wrap gap-2"><span v-for="(l,i) in labels" :key="i" class="px-3 py-1 rounded-full text-xs font-medium bg-blue-50 text-blue-600">{{ l.label }}: {{ l.value }}</span></div>
          </div>
          <div v-if="tags.length > 0">
            <p class="text-xs text-slate-400 mb-1.5">通用标签（commonTags）</p>
            <div class="flex flex-wrap gap-2"><span v-for="(tag,i) in tags" :key="i" class="px-3 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-600">{{ tag }}</span></div>
          </div>
          <div v-if="recommendTags.length > 0">
            <p class="text-xs text-slate-400 mb-1.5">推荐标签（recommendTagList）</p>
            <div class="flex flex-wrap gap-2"><span v-for="(tag,i) in recommendTags" :key="i" class="px-3 py-1 rounded-full text-xs font-medium bg-purple-50 text-purple-600">{{ tag }}</span></div>
          </div>
          <div class="space-y-1.5 text-sm text-slate-500">
            <div v-if="itemDO.transportFee !== undefined" class="flex items-center gap-2"><Truck class="w-4 h-4 text-slate-400" /><span>运费: ¥{{ itemDO.transportFee }}</span></div>
            <div v-if="itemDO.itemId" class="flex items-center gap-2"><Package class="w-4 h-4 text-slate-400" /><span>商品ID: <span class="font-mono text-xs">{{ itemDO.itemId }}</span></span></div>
            <div v-if="itemDO.categoryId" class="flex items-center gap-2"><Package class="w-4 h-4 text-slate-400" /><span>分类ID: <span class="font-mono text-xs">{{ itemDO.categoryId }}</span></span></div>
            <div v-if="categoryPath" class="flex items-center gap-2"><Package class="w-4 h-4 text-slate-400" /><span>分类路径: {{ categoryPath }}</span></div>
          </div>
        </div>
      </div>

      <div v-if="itemDO.desc" class="app-surface p-5"><h3 class="font-semibold text-slate-700 mb-3">商品描述（desc）</h3><p class="text-sm text-slate-600 whitespace-pre-line leading-relaxed">{{ itemDO.desc }}</p></div>

      <!-- SKU 参数信息 guideProdParamInfo -->
      <div v-if="itemDO.guideProdParamInfo?.layerData?.head" class="app-surface p-5">
        <h3 class="font-semibold text-slate-700 mb-3">{{ itemDO.guideProdParamInfo.title || '产品参数' }}</h3>
        <div class="space-y-2">
          <div v-if="itemDO.guideProdParamInfo.layerData.head.title" class="text-sm text-slate-600">{{ itemDO.guideProdParamInfo.layerData.head.title }}</div>
          <div v-if="itemDO.guideProdParamInfo.layerData.head.sku?.length" class="flex flex-wrap gap-2">
            <span v-for="(s,i) in itemDO.guideProdParamInfo.layerData.head.sku" :key="i" class="px-2 py-1 rounded text-xs bg-slate-100 text-slate-600">{{ s }}</span>
          </div>
          <div v-if="itemDO.guideProdParamInfo.layerData.head.price" class="text-rose-600 font-bold">{{ itemDO.guideProdParamInfo.layerData.head.price }}</div>
        </div>
      </div>

      <!-- AI Analysis (from original scrape) -->
      <div v-if="aiAnalysis && Object.keys(aiAnalysis).length > 0" class="app-surface p-5">
        <h3 class="font-semibold text-slate-700 mb-3">AI 分析（爬取时）</h3>
        <div class="space-y-2 text-sm">
          <div v-if="aiAnalysis.is_recommended !== undefined" class="flex items-center gap-2">
            <span class="px-2 py-0.5 rounded text-xs font-medium" :class="aiAnalysis.is_recommended ? 'bg-emerald-50 text-emerald-600' : 'bg-rose-50 text-rose-600'">{{ aiAnalysis.is_recommended ? '推荐' : '不推荐' }}</span>
            <span v-if="aiAnalysis.value_score !== undefined" class="text-slate-500">价值评分: {{ aiAnalysis.value_score }}</span>
          </div>
          <p v-if="aiAnalysis.reason" class="text-slate-600 whitespace-pre-line">{{ aiAnalysis.reason }}</p>
        </div>
      </div>

      <!-- Original Scrape Data (record fallback) -->
      <div v-if="recordData && Object.keys(recordData).length > 0" class="app-surface p-5">
        <h3 class="font-semibold text-slate-700 mb-3">原始爬取数据</h3>
        <div class="grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm">
          <div v-if="productInfo['商品ID']"><p class="text-slate-400 text-xs">商品ID</p><p class="font-mono text-slate-600 text-xs">{{ productInfo['商品ID'] }}</p></div>
          <div v-if="productInfo['商品标签']?.length"><p class="text-slate-400 text-xs">商品标签</p><p class="text-slate-600">{{ (productInfo['商品标签'] as string[]).join('、') }}</p></div>
          <div v-if="productInfo['发布时间']"><p class="text-slate-400 text-xs">发布时间</p><p class="text-slate-600">{{ productInfo['发布时间'] }}</p></div>
          <div v-if="productInfo['成色']"><p class="text-slate-400 text-xs">成色</p><p class="text-slate-600">{{ productInfo['成色'] }}</p></div>
          <div v-if="sellerInfo['卖家昵称']"><p class="text-slate-400 text-xs">卖家</p><p class="text-slate-600">{{ sellerInfo['卖家昵称'] }}</p></div>
          <div v-if="sellerInfo['卖家信用']"><p class="text-slate-400 text-xs">卖家信用</p><p class="text-slate-600">{{ sellerInfo['卖家信用'] }}</p></div>
          <div v-if="sellerInfo['实名认证'] !== undefined"><p class="text-slate-400 text-xs">实名认证</p><p class="text-slate-600">{{ sellerInfo['实名认证'] ? '是' : '否' }}</p></div>
          <div v-if="sellerInfo['注册时长']"><p class="text-slate-400 text-xs">注册时长</p><p class="text-slate-600">{{ sellerInfo['注册时长'] }}</p></div>
          <div v-if="sellerInfo['卖家好评率']"><p class="text-slate-400 text-xs">好评率</p><p class="text-slate-600">{{ sellerInfo['卖家好评率'] }}</p></div>
          <div v-if="sellerInfo['卖家城市']"><p class="text-slate-400 text-xs">城市</p><p class="text-slate-600">{{ sellerInfo['卖家城市'] }}</p></div>
          <div v-if="sellerInfo['想要人数']"><p class="text-slate-400 text-xs">想要人数</p><p class="text-slate-600">{{ sellerInfo['想要人数'] }}</p></div>
        </div>
      </div>

      <!-- SKU 规格列表（skuList / idleItemSkuList） -->
      <div v-if="detailSkus.length > 0" class="app-surface p-5">
        <h3 class="font-semibold text-slate-700 mb-4">SKU 规格列表（skuList，{{ detailSkus.length }} 个）</h3>
        <div class="overflow-x-auto">
          <table class="min-w-full text-sm">
            <thead class="bg-slate-50 text-left text-slate-500">
              <tr><th class="px-4 py-3 font-medium">SKU图</th><th class="px-4 py-3 font-medium">规格属性</th><th class="px-4 py-3 font-medium">价格</th><th class="px-4 py-3 font-medium">库存</th><th class="px-4 py-3 font-medium">SKU ID</th></tr>
            </thead>
            <tbody>
              <tr v-for="(sku,i) in detailSkus" :key="i" class="border-t border-slate-100">
                <td class="px-4 py-3"><img v-if="sku.image" :src="sku.image" class="w-12 h-12 rounded object-cover" :alt="sku.props" /><span v-else class="text-slate-300">—</span></td>
                <td class="px-4 py-3 text-slate-800">{{ sku.props || '—' }}</td>
                <td class="px-4 py-3 text-rose-600 font-semibold">{{ sku.price }}</td>
                <td class="px-4 py-3 text-slate-500">{{ sku.quantity ?? '—' }}</td>
                <td class="px-4 py-3 text-slate-400 font-mono text-xs">{{ sku.skuId || '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 分享数据（shareData） -->
      <div v-if="shareContent || shareImages.length > 0" class="app-surface p-5">
        <h3 class="font-semibold text-slate-700 mb-3">分享数据（shareData）</h3>
        <p v-if="shareContent" class="text-sm text-slate-600 whitespace-pre-line mb-3">{{ shareContent }}</p>
        <div v-if="shareImages.length > 0" class="grid grid-cols-4 sm:grid-cols-6 gap-2">
          <img v-for="(img,i) in shareImages" :key="i" :src="img" class="w-full aspect-square object-cover rounded" :alt="`分享图 ${Number(i)+1}`" />
        </div>
      </div>

      <!-- 跟踪参数（trackParams） -->
      <div v-if="Object.keys(trackParams).length > 0" class="app-surface p-5">
        <h3 class="font-semibold text-slate-700 mb-3">跟踪参数（trackParams）</h3>
        <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 text-sm">
          <div v-if="trackParams.sellerId"><p class="text-slate-400 text-xs">卖家ID</p><p class="font-mono text-xs text-slate-600">{{ trackParams.sellerId }}</p></div>
          <div v-if="trackParams.categoryId"><p class="text-slate-400 text-xs">分类ID</p><p class="font-mono text-xs text-slate-600">{{ trackParams.categoryId }}</p></div>
          <div v-if="trackParams.channelCatId"><p class="text-slate-400 text-xs">频道分类</p><p class="font-mono text-xs text-slate-600">{{ trackParams.channelCatId }}</p></div>
          <div v-if="trackParams.rootChannelCatId"><p class="text-slate-400 text-xs">根分类</p><p class="font-mono text-xs text-slate-600">{{ trackParams.rootChannelCatId }}</p></div>
          <div v-if="trackParams.buyerId"><p class="text-slate-400 text-xs">买家ID</p><p class="font-mono text-xs text-slate-600">{{ trackParams.buyerId }}</p></div>
          <div v-if="trackParams.itemId"><p class="text-slate-400 text-xs">商品ID</p><p class="font-mono text-xs text-slate-600">{{ trackParams.itemId }}</p></div>
          <div v-if="trackParams.mainPic"><p class="text-slate-400 text-xs">主图</p><img :src="trackParams.mainPic" class="w-10 h-10 rounded object-cover" /></div>
          <div v-if="trackParams.medal_id"><p class="text-slate-400 text-xs">勋章</p><p class="font-mono text-xs text-slate-600">{{ trackParams.medal_id }}</p></div>
        </div>
      </div>

      <!-- 买家信息（buyerDO） -->
      <div v-if="buyerDO.buyerId" class="app-surface p-5">
        <h3 class="font-semibold text-slate-700 mb-3">买家信息（buyerDO）</h3>
        <div class="grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm">
          <div v-if="buyerDO.buyerId"><p class="text-slate-400 text-xs">买家ID</p><p class="font-mono text-xs text-slate-600">{{ buyerDO.buyerId }}</p></div>
          <div v-if="buyerDO.isShopUser !== undefined"><p class="text-slate-400 text-xs">店铺用户</p><p class="text-slate-600">{{ buyerDO.isShopUser ? '是' : '否' }}</p></div>
          <div v-if="buyerDO.isCollected !== undefined"><p class="text-slate-400 text-xs">已收藏</p><p class="text-slate-600">{{ buyerDO.isCollected ? '是' : '否' }}</p></div>
          <div v-if="buyerDO.isSuperFavored !== undefined"><p class="text-slate-400 text-xs">超级关注</p><p class="text-slate-600">{{ buyerDO.isSuperFavored ? '是' : '否' }}</p></div>
          <div v-if="buyerDO.attentionState !== undefined"><p class="text-slate-400 text-xs">关注状态</p><p class="text-slate-600">{{ buyerDO.attentionState }}</p></div>
        </div>
      </div>

      <!-- 配置信息（configInfo） -->
      <div v-if="Object.keys(configInfo).length > 0" class="app-surface p-5">
        <h3 class="font-semibold text-slate-700 mb-3">配置信息（configInfo）</h3>
        <div class="flex flex-wrap gap-2">
          <span v-for="(val, key) in configInfo" :key="key" class="px-2 py-1 rounded text-xs bg-slate-100 text-slate-600">{{ key }}: {{ val }}</span>
        </div>
      </div>

      <div v-if="sellerDO.sellerId || sellerDO.userId || sellerDO.pageUserId" class="app-surface p-5">
        <div class="flex items-center gap-3 mb-4">
          <img v-if="sellerDO.portraitUrl || sellerDO.avatarUrl" :src="sellerDO.portraitUrl || sellerDO.avatarUrl" class="w-12 h-12 rounded-full object-cover" :alt="sellerDO.uniqueName" />
          <div class="flex-1">
            <div class="flex items-center gap-2">
              <h3 class="font-semibold text-slate-700">{{ sellerDO.uniqueName || sellerDO.nick || '—' }}</h3>
              <a v-if="sellerHomePage" :href="sellerHomePage" target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 hover:underline">
                <ExternalLink class="w-3.5 h-3.5" />个人主页
              </a>
            </div>
            <p v-if="sellerDO.xianyuSummary" class="text-xs text-slate-500 mt-0.5">{{ sellerDO.xianyuSummary }}</p>
          </div>
          <Button size="sm" :variant="isFollowing ? 'secondary' : 'default'" :disabled="followLoading" @click="toggleFollowSeller">
            <UserCheck class="w-4 h-4 mr-1" />{{ isFollowing ? '已关注' : '关注卖家' }}
          </Button>
        </div>
        <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4 text-sm">
          <div v-if="sellerDO.sellerId"><p class="text-slate-400 text-xs mb-1">卖家ID</p><p class="font-mono text-xs text-slate-600">{{ sellerDO.sellerId }}</p></div>
          <div v-if="sellerDO.userId && sellerDO.userId !== sellerDO.sellerId"><p class="text-slate-400 text-xs mb-1">用户ID</p><p class="font-mono text-xs text-slate-600">{{ sellerDO.userId }}</p></div>
          <div v-if="sellerDO.pageUserId && sellerDO.pageUserId !== sellerDO.sellerId && sellerDO.pageUserId !== sellerDO.userId"><p class="text-slate-400 text-xs mb-1">主页ID</p><p class="font-mono text-xs text-slate-600">{{ sellerDO.pageUserId }}</p></div>
          <div v-if="sellerDO.city"><p class="text-slate-400 text-xs mb-1">城市</p><p class="font-medium text-slate-700 flex items-center gap-1"><MapPin class="w-3.5 h-3.5" />{{ sellerDO.city }}</p></div>
          <div v-if="sellerDO.publishCity && sellerDO.publishCity !== sellerDO.city"><p class="text-slate-400 text-xs mb-1">发货城市</p><p class="font-medium text-slate-700">{{ sellerDO.publishCity }}</p></div>
          <div v-if="sellerDO.hasSoldNumInteger !== undefined"><p class="text-slate-400 text-xs mb-1">已售</p><p class="font-medium text-slate-700">{{ sellerDO.hasSoldNumInteger }} 件</p></div>
          <div v-if="sellerDO.itemCount !== undefined"><p class="text-slate-400 text-xs mb-1">在售</p><p class="font-medium text-slate-700">{{ sellerDO.itemCount }} 件</p></div>
          <div v-if="sellerDO.replyRatio24h"><p class="text-slate-400 text-xs mb-1">24h回复率</p><p class="font-medium text-slate-700">{{ sellerDO.replyRatio24h }}</p></div>
          <div v-if="sellerDO.replyIn24hRatioDouble !== undefined"><p class="text-slate-400 text-xs mb-1">24h回复率(精确)</p><p class="font-medium text-slate-700">{{ (sellerDO.replyIn24hRatioDouble * 100).toFixed(1) }}%</p></div>
          <div v-if="sellerDO.replyInterval"><p class="text-slate-400 text-xs mb-1">回复间隔</p><p class="font-medium text-slate-700">{{ sellerDO.replyInterval }}</p></div>
          <div v-if="sellerDO.avgReply30dLong !== undefined"><p class="text-slate-400 text-xs mb-1">30天平均回复</p><p class="font-medium text-slate-700">{{ sellerDO.avgReply30dLong }} 秒</p></div>
          <div v-if="sellerDO.lastVisitTime"><p class="text-slate-400 text-xs mb-1">最近在线</p><p class="font-medium text-slate-700 flex items-center gap-1"><Clock class="w-3.5 h-3.5" />{{ sellerDO.lastVisitTime }}</p></div>
          <div v-if="sellerDO.userRegDay !== undefined"><p class="text-slate-400 text-xs mb-1">注册天数</p><p class="font-medium text-slate-700">{{ sellerDO.userRegDay }} 天</p></div>
          <div v-if="sellerRegisterDate"><p class="text-slate-400 text-xs mb-1">注册时间</p><p class="font-medium text-slate-700 text-xs">{{ sellerRegisterDate }}</p></div>
          <div v-if="sellerDO.newGoodRatioRate"><p class="text-slate-400 text-xs mb-1">好评率</p><p class="font-medium text-slate-700">{{ sellerDO.newGoodRatioRate }}</p></div>
          <div v-if="sellerRemarks && (sellerRemarks.sellerGoodRemarkCnt || sellerRemarks.sellerDefaultRemarkCnt || sellerRemarks.sellerBadRemarkCnt)"><p class="text-slate-400 text-xs mb-1">评价</p><p class="font-medium text-slate-700">好评 {{ sellerRemarks.sellerGoodRemarkCnt ?? 0 }} / 中评 {{ sellerRemarks.sellerDefaultRemarkCnt ?? 0 }} / 差评 {{ sellerRemarks.sellerBadRemarkCnt ?? 0 }}</p></div>
          <div v-if="sellerDO.zhimaAuth"><p class="text-slate-400 text-xs mb-1">芝麻认证</p><p class="font-medium text-emerald-600"><ShieldCheck class="w-4 h-4 inline" /> 已认证</p></div>
        </div>
        <div v-if="sellerDO.identityTags?.length || sellerDO.sellerInfoTags?.length" class="mt-3 flex flex-wrap gap-2"><span v-for="(tag,i) in [...(sellerDO.identityTags || []), ...(sellerDO.sellerInfoTags || [])]" :key="i" class="px-2 py-0.5 rounded text-xs bg-slate-100 text-slate-500">{{ tag.text }}</span></div>
        <div v-if="sellerDO.signature" class="mt-3 text-sm text-slate-500 italic">签名: {{ sellerDO.signature }}</div>
        <div v-if="sellerDO.levelTags?.length || sellerDO.idleFishCreditTag?.iconUrl" class="mt-3 flex flex-wrap items-center gap-2">
          <img v-if="sellerDO.idleFishCreditTag?.iconUrl" :src="sellerDO.idleFishCreditTag.iconUrl" class="h-8" alt="闲鱼信用" />
          <template v-for="(lvTag,i) in (sellerDO.levelTags || [])" :key="`lv-${i}`">
            <img v-if="lvTag.iconUrl" :src="lvTag.iconUrl" class="h-8" :alt="`等级标签 ${Number(i)+1}`" />
          </template>
        </div>
      </div>

      <div v-if="sellerItems.length > 0" class="app-surface p-5">
        <h3 class="font-semibold text-slate-700 mb-4">卖家其他在售 ({{ sellerItems.length }})</h3>
        <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          <a v-for="(item,i) in sellerItems.filter(s => s.itemId)" :key="i" :href="`https://www.goofish.com/item?id=${item.itemId}`" target="_blank" rel="noopener noreferrer" class="border border-slate-100 rounded-lg p-2 hover:border-slate-300 transition-colors block">
            <img v-if="item.iconUrl" :src="item.iconUrl" class="w-full aspect-square object-cover rounded mb-2" :alt="item.title" />
            <p class="text-xs text-slate-600 truncate">{{ item.title || item.text }}</p>
          </a>
        </div>
      </div>

      <div class="app-surface overflow-hidden">
        <div class="border-b border-slate-100 px-5 py-3 font-semibold text-slate-700">{{ t('collections.detail.skuTableTitle') }}<span class="text-sm font-normal text-slate-400 ml-2">({{ collection.skus.length }})</span></div>
        <div v-if="['pending','running'].includes(collection.sku_fetch_status)" class="p-8 text-center text-slate-500">{{ t('collections.detail.fetchingSkus') }}</div>
        <div v-else-if="collection.skus.length === 0" class="p-8 text-center text-slate-500">{{ t('collections.detail.noSkus') }}</div>
        <div v-else class="overflow-x-auto">
          <table class="min-w-full text-sm">
            <thead class="bg-slate-50 text-left text-slate-500"><tr><th class="px-5 py-3 font-medium">{{ t('collections.detail.colSpec') }}</th><th class="px-5 py-3 font-medium">{{ t('collections.detail.colPrice') }}</th><th class="px-5 py-3 font-medium">库存</th><th class="px-5 py-3 font-medium">{{ t('collections.detail.colSkuId') }}</th></tr></thead>
            <tbody><tr v-for="(sku,index) in collection.skus" :key="sku.sku_id || index" class="border-t border-slate-100"><td class="px-5 py-3 text-slate-800">{{ sku.label }}</td><td class="px-5 py-3 text-rose-600 font-semibold">{{ sku.price_display || '—' }}</td><td class="px-5 py-3 text-slate-500">{{ sku.quantity ?? '—' }}</td><td class="px-5 py-3 text-slate-400 font-mono text-xs">{{ sku.sku_id || '—' }}</td></tr></tbody>
          </table>
        </div>
      </div>

      <!-- 完整原始 JSON（可折叠） -->
      <details class="app-surface p-5">
        <summary class="font-semibold text-slate-700 cursor-pointer select-none">完整原始 JSON（detail_data 全量数据）</summary>
        <pre class="mt-3 text-xs text-slate-500 overflow-x-auto bg-slate-50 rounded-lg p-3 max-h-96 overflow-y-auto">{{ JSON.stringify(detail, null, 2) }}</pre>
      </details>
    </template>
  </div>
</template>
