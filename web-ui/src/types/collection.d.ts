export interface CollectionSku {
  sku_id: string
  label: string
  price: number | null
  price_display: string
  properties?: Array<Record<string, unknown>>
  in_stock?: boolean
  quantity?: number | null
  source?: string
}

export interface CollectionDetailData {
  itemDO?: {
    itemId?: number | string
    title?: string
    desc?: string
    descTag?: string
    soldPrice?: string
    originalPrice?: string
    transportFee?: string
    quantity?: number
    soldCnt?: number
    wantCnt?: number
    wantCntUnit?: string
    browseCnt?: number
    collectCnt?: number
    favorCnt?: number
    simpleItem?: boolean
    itemStatusStr?: string
    gmtCreate?: number
    resellDiscount?: string
    categoryId?: number
    imageInfos?: Array<{
      url?: string
      major?: boolean
      widthSize?: number
      heightSize?: number
    }>
    cpvLabels?: Array<{
      propertyName?: string
      valueName?: string
    }>
    itemLabelExtList?: Array<{
      propertyText?: string
      valueText?: string
    }>
    commonTags?: Array<{
      text?: string
    }>
    priceRelativeTags?: Array<{
      text?: string
    }>
    recommendTagList?: Array<{
      text?: string
    }>
    descRelativeTags?: Array<{
      text?: string
    }>
    itemCatDTO?: {
      catId?: number
      channelCatId?: number
      leafId?: number
    }
    guideProdParamInfo?: {
      title?: string
      layerData?: {
        head?: {
          sku?: string[]
          price?: string
          title?: string
        }
      }
    }
    trackParams?: Record<string, string>
    skuList?: Array<{
      skuId?: number | string
      price?: number
      priceInCent?: number
      quantity?: number
      propertyList?: Array<{
        propertyText?: string
        valueText?: string
      }>
      propertyImage?: {
        url?: string
      }
    }>
    idleItemSkuList?: Array<{
      skuId?: number | string
      price?: number
      priceInCent?: number
      quantity?: number
      propertyList?: Array<{
        propertyText?: string
        valueText?: string
      }>
      propertyImage?: {
        url?: string
      }
    }>
    shareData?: {
      shareInfoJsonString?: string
    }
    richTextDesc?: string
    bargained?: boolean
    itemType?: string
    tradeAccessType?: number
    descTagColor?: string
    charitableTag?: { iconUrl?: string }
    secuGuide?: {
      secuTitle?: string
      secuContent?: string
      secuBtm?: string
    }
    spuBottomBarItem?: {
      title?: string
      targetUrl?: string
    }
    reportUrl?: string
  }
  trackParams?: Record<string, string>
  buyerDO?: {
    buyerId?: number | string
    isShopUser?: boolean
    isCollected?: boolean
    isSuperFavored?: boolean
    attentionState?: number
  }
  configInfo?: Record<string, string>
  serverTime?: string
  sellerDO?: {
    sellerId?: number | string
    userId?: number | string
    pageUserId?: number | string
    nick?: string
    uniqueName?: string
    avatarUrl?: string
    portraitUrl?: string
    city?: string
    publishCity?: string
    userRegDay?: number
    hasSoldNumInteger?: number
    replyRatio24h?: string
    replyInterval?: string
    lastVisitTime?: string
    itemCount?: number
    newGoodRatioRate?: string
    zhimaAuth?: boolean
    xianyuSummary?: string
    registerTime?: number
    avgReply30dLong?: number
    idleFishCreditTag?: { iconUrl?: string }
    remarkDO?: {
      sellerGoodRemarkCnt?: number
      sellerDefaultRemarkCnt?: number
      sellerBadRemarkCnt?: number
    }
    sellerItems?: Array<{
      itemId?: number | string
      title?: string
      text?: string
      iconUrl?: string
      link?: string
    }>
    identityTags?: Array<{
      text?: string
      iconUrl?: string
      link?: string
    }>
    sellerInfoTags?: Array<{
      text?: string
      iconUrl?: string
    }>
    levelTags?: Array<{
      iconUrl?: string
    }>
    signature?: string
    replyIn24hRatioDouble?: number
  }
}

export interface CollectionItem {
  id: number
  result_item_id: number
  collected_at: string
  sku_fetch_status: 'pending' | 'running' | 'done' | 'failed'
  sku_fetched_at?: string | null
  sku_error?: string | null
  skus: CollectionSku[]
  sku_meta?: Record<string, unknown>
  detail_data?: CollectionDetailData
  item_labels?: Array<{ label: string; value: string }>
  common_tags?: string[]
  seller_id?: string | null
  summary?: {
    title?: string
    price_display?: string
    link?: string
    item_id?: string
    result_filename?: string
  }
  record?: Record<string, unknown>
}
