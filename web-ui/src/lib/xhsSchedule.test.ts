import { describe, expect, it } from 'vitest'
import { buildXhsCron, classifyXhsNextRun, parseXhsCron } from './xhsSchedule'

describe('xhs schedule choice', () => {
  it('maps common intervals without exposing cron', () => {
    expect(parseXhsCron('0 * * * *').frequency).toBe('h1')
    expect(parseXhsCron('*/30 * * * *').frequency).toBe('m30')
    expect(parseXhsCron('@hourly').frequency).toBe('h1')
    expect(buildXhsCron('h2', '09:00', '')).toBe('0 */2 * * *')
  })

  it('turns a daily clock time into cron and back', () => {
    expect(parseXhsCron('30 9 * * *')).toMatchObject({
      frequency: 'daily',
      time: '09:30',
      cron: '30 9 * * *',
    })
    expect(buildXhsCron('daily', '09:30', '')).toBe('30 9 * * *')
    expect(buildXhsCron('daily', '09:30:00', '')).toBe('30 9 * * *')
    expect(() => buildXhsCron('daily', '25:00', '')).toThrow()
  })

  it('maps weekly and monthly choices onto the scheduler weekday', () => {
    expect(parseXhsCron('30 9 * * mon')).toMatchObject({
      frequency: 'weekly',
      weekday: 'mon',
      time: '09:30',
    })
    expect(parseXhsCron('0 9 * * 0')).toMatchObject({ frequency: 'weekly', weekday: 'mon' })
    expect(parseXhsCron('0 9 * * 6')).toMatchObject({ frequency: 'weekly', weekday: 'sun' })
    expect(buildXhsCron('weekly', '09:30', '', 'fri')).toBe('30 9 * * fri')
    expect(parseXhsCron('15 8 1 * *')).toMatchObject({
      frequency: 'monthly',
      monthDay: 1,
      time: '08:15',
    })
    expect(buildXhsCron('monthly', '08:15', '', 'mon', 15)).toBe('15 8 15 * *')
    expect(parseXhsCron('@weekly')).toMatchObject({ frequency: 'weekly', weekday: 'mon', time: '00:00' })
    expect(parseXhsCron('@monthly')).toMatchObject({ frequency: 'monthly', monthDay: 1, time: '00:00' })
    expect(() => buildXhsCron('monthly', '09:00', '', 'mon', 32)).toThrow()
  })

  it('keeps an unusual rule until the user picks a common frequency', () => {
    expect(parseXhsCron('0 9 * * 1-5').frequency).toBe('custom')
    expect(buildXhsCron('custom', '09:00', '0 9 * * 1-5')).toBe('0 9 * * 1-5')
  })

  it('describes the next run as today, tomorrow, or a calendar day in Shanghai', () => {
    const now = new Date('2026-09-22T11:30:00+08:00')
    expect(classifyXhsNextRun('2026-09-22T12:00:00+08:00', now)).toEqual({
      kind: 'today',
      time: '12:00',
    })
    expect(classifyXhsNextRun('2026-09-23T00:00:00+08:00', new Date('2026-09-22T23:30:00+08:00'))).toEqual({
      kind: 'tomorrow',
      time: '00:00',
    })
    expect(classifyXhsNextRun('2026-09-24T09:05:00+08:00', now)).toEqual({
      kind: 'date',
      time: '09:05',
      month: 9,
      day: 24,
    })
    expect(classifyXhsNextRun(null, now)).toBeNull()
  })
})
