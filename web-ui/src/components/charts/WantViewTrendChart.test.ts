import { mount, type VueWrapper } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
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

const CHART_WIDTH = 720
const CHART_HEIGHT = 220

/**
 * jsdom 不做布局，getBoundingClientRect 恒为 0，
 * 命中测试需要先把 SVG 尺寸打桩成 720x220（与 viewBox 1:1）。
 */
function stubChartRect(wrapper: VueWrapper) {
  const svg = wrapper.find('svg').element as SVGSVGElement
  svg.getBoundingClientRect = () =>
    ({ x: 0, y: 0, top: 0, left: 0, width: CHART_WIDTH, height: CHART_HEIGHT, right: CHART_WIDTH, bottom: CHART_HEIGHT, toJSON: () => ({}) }) as DOMRect
}

/** 悬停到第 index 个数据点对应的 X 坐标 */
async function hoverIndex(wrapper: VueWrapper, index: number, y = CHART_HEIGHT / 2) {
  const svg = wrapper.find('svg')
  const clientX = pointX(index)
  await svg.trigger('pointermove', { clientX, clientY: y })
}

/** 与组件 resolveX 一致的 X 坐标（非双轴内边距 24） */
function pointX(index: number) {
  const usableWidth = CHART_WIDTH - 24 - 24
  return 24 + (usableWidth / (hollowThenSolid.length - 1)) * index
}

describe('WantViewTrendChart', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

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

  it('shows a tooltip with the hovered day values on pointer move', async () => {
    i18n.global.locale.value = 'zh-CN'
    const wrapper = mount(WantViewTrendChart, {
      props: { points: hollowThenSolid, dualAxis: true },
      attachTo: document.body,
      global: { plugins: [i18n] },
    })
    stubChartRect(wrapper)

    expect(wrapper.find('[data-testid="trend-tooltip"]').exists()).toBe(false)

    await hoverIndex(wrapper, 6)
    const tooltip = wrapper.find('[data-testid="trend-tooltip"]')
    expect(tooltip.exists()).toBe(true)
    expect(tooltip.text()).toContain('09-17')
    expect(tooltip.text()).toContain((8344).toLocaleString())
    expect(tooltip.text()).toContain((65071).toLocaleString())

    // 移到 16 日应换成当天数值
    await hoverIndex(wrapper, 5)
    expect(wrapper.find('[data-testid="trend-tooltip"]').text()).toContain('09-16')

    wrapper.unmount()
  })

  it('snaps to the nearest data day even when the pointer sits between points', async () => {
    const wrapper = mount(WantViewTrendChart, {
      props: { points: hollowThenSolid, dualAxis: true },
      attachTo: document.body,
      global: { plugins: [i18n] },
    })
    stubChartRect(wrapper)

    // 落在第 5、6 天之间，但更靠近第 6 天（09-17）
    const svg = wrapper.find('svg')
    await svg.trigger('pointermove', {
      clientX: (pointX(5) + pointX(6)) / 2 + 20,
      clientY: CHART_HEIGHT / 2,
    })
    expect(wrapper.find('[data-testid="trend-tooltip"]').text()).toContain('09-17')

    wrapper.unmount()
  })

  it('clears the tooltip on pointer leave and supports arrow-key navigation', async () => {
    const wrapper = mount(WantViewTrendChart, {
      props: { points: hollowThenSolid, dualAxis: true },
      attachTo: document.body,
      global: { plugins: [i18n] },
    })
    stubChartRect(wrapper)

    const svg = wrapper.find('svg')

    // End -> 最后一天（09-17）
    await svg.trigger('keydown', { key: 'End' })
    expect(wrapper.find('[data-testid="trend-tooltip"]').text()).toContain('09-17')

    // ← 应落到 09-16
    await svg.trigger('keydown', { key: 'ArrowLeft' })
    expect(wrapper.find('[data-testid="trend-tooltip"]').text()).toContain('09-16')

    // 再往左全是空心日，应停在原地而不是显示空值
    await svg.trigger('keydown', { key: 'ArrowLeft' })
    expect(wrapper.find('[data-testid="trend-tooltip"]').text()).toContain('09-16')

    // → 回到 09-17
    await svg.trigger('keydown', { key: 'ArrowRight' })
    expect(wrapper.find('[data-testid="trend-tooltip"]').text()).toContain('09-17')

    await svg.trigger('pointerleave')
    expect(wrapper.find('[data-testid="trend-tooltip"]').exists()).toBe(false)

    wrapper.unmount()
  })

  it('can render a single series when the other one is disabled', () => {
    const wrapper = mount(WantViewTrendChart, {
      props: {
        points: hollowThenSolid,
        dualAxis: false,
        showWant: false,
        title: '浏览趋势',
      },
      global: { plugins: [i18n] },
    })

    expect(wrapper.find('svg').exists()).toBe(true)
    // 只剩「浏览」一条线：09-16 与 09-17 各一个圆点
    expect(wrapper.findAll('circle')).toHaveLength(2)
    expect(wrapper.text()).not.toContain('想要')
    expect(wrapper.text()).toContain('浏览')
  })
})
