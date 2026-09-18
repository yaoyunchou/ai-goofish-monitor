import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { i18n } from '@/i18n'
import WantViewTrendChart from './WantViewTrendChart.vue'

const hollowThenSolid = [
  { date: '2026-09-11', want: null, view: null },
  { date: '2026-09-12', want: null, view: null },
  { date: '2026-09-13', want: null, view: null },
  { date: '2026-09-14', want: null, view: null },
  { date: '2026-09-15', want: null, view: null },
  { date: '2026-09-16', want: 100, view: 2000 },
  { date: '2026-09-17', want: 8344, view: 65071 },
]

describe('WantViewTrendChart', () => {
  it('keeps a 7-day X axis and omits circles on hollow null days', () => {
    const wrapper = mount(WantViewTrendChart, {
      props: {
        points: hollowThenSolid,
        dualAxis: true,
        connectNulls: false,
        title: '想要 / 浏览趋势',
      },
      global: { plugins: [i18n] },
    })

    expect(wrapper.find('svg').exists()).toBe(true)
    const dateLabels = wrapper
      .findAll('svg text')
      .map((node) => node.text())
      .filter((text) => /^\d{2}-\d{2}$/.test(text))
    expect(dateLabels).toEqual(['09-11', '09-12', '09-13', '09-14', '09-15', '09-16', '09-17'])
    expect(wrapper.findAll('circle')).toHaveLength(4)
    expect(wrapper.text()).not.toContain('showPv')
  })

  it('does not render SVG zeros when every day is hollow', () => {
    i18n.global.locale.value = 'zh-CN'
    const wrapper = mount(WantViewTrendChart, {
      props: {
        points: hollowThenSolid.map((point) => ({ ...point, want: null, view: null })),
        dualAxis: true,
      },
      global: { plugins: [i18n] },
    })
    expect(wrapper.find('svg').exists()).toBe(false)
    expect(wrapper.text()).toContain(String(i18n.global.t('sellerSubscription.noTrend')))
    expect(wrapper.text()).not.toMatch(/\b0\b/)
  })
})
