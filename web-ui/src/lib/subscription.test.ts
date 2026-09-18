import { describe, expect, it } from 'vitest'
import { normalizeSellerSubscription, normalizeSubscriptionEnabled } from './subscription'

describe('normalizeSubscriptionEnabled', () => {
  it('parses booleans and common string forms', () => {
    expect(normalizeSubscriptionEnabled(true)).toBe(true)
    expect(normalizeSubscriptionEnabled(false)).toBe(false)
    expect(normalizeSubscriptionEnabled('true')).toBe(true)
    expect(normalizeSubscriptionEnabled('false')).toBe(false)
    expect(normalizeSubscriptionEnabled('1')).toBe(true)
    expect(normalizeSubscriptionEnabled('0')).toBe(false)
  })
})

describe('normalizeSellerSubscription', () => {
  it('normalizes enabled on item', () => {
    expect(normalizeSellerSubscription({ id: 1, enabled: 'true' }).enabled).toBe(true)
  })
})
