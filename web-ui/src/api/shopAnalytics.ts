import { http } from '@/lib/http'

export async function getShopOverview(cycle = '1d') {
  return await http('/api/shop-analytics/overview', { params: { cycle } })
}

export async function getShopDistribution(cycle = '1d', type = 'source') {
  return await http('/api/shop-analytics/distribution', { params: { cycle, type } })
}

export async function getShopTrend(metric = 'showPv', days = 30, cycle = '1d') {
  return await http('/api/shop-analytics/trend', { params: { metric, days, cycle } })
}

export async function collectShopAnalytics() {
  return await http('/api/shop-analytics/collect', { method: 'POST' })
}
