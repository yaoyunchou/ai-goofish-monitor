export const XHS_FREQUENCY_OPTIONS = ['m15', 'm30', 'h1', 'h2', 'h4', 'h6', 'h12', 'daily', 'weekly', 'monthly'] as const

export const XHS_WEEKDAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'] as const

export type XhsFrequency = (typeof XHS_FREQUENCY_OPTIONS)[number] | 'custom'
export type XhsWeekday = (typeof XHS_WEEKDAYS)[number]

type IntervalFrequency = 'm15' | 'm30' | 'h1' | 'h2' | 'h4' | 'h6' | 'h12'

const INTERVAL_CRONS: Record<IntervalFrequency, string> = {
  m15: '*/15 * * * *',
  m30: '*/30 * * * *',
  h1: '0 * * * *',
  h2: '0 */2 * * *',
  h4: '0 */4 * * *',
  h6: '0 */6 * * *',
  h12: '0 */12 * * *',
}

export interface XhsScheduleChoice {
  frequency: XhsFrequency
  /** HH:mm。间隔频率下保留默认值，便于切到每天 / 每周 / 每月。 */
  time: string
  /** APScheduler 3 的星期名。0 是周一，所以不存数字。 */
  weekday: XhsWeekday
  monthDay: number
  cron: string
}

export interface XhsNextRunParts {
  kind: 'today' | 'tomorrow' | 'date'
  time: string
  month?: number
  day?: number
}

function normalizeCron(cron: string): string {
  return cron.trim().replace(/\s+/g, ' ')
}

function pad(value: number): string {
  return String(value).padStart(2, '0')
}

function choice(
  frequency: XhsFrequency,
  cron: string,
  extra: Partial<Pick<XhsScheduleChoice, 'time' | 'weekday' | 'monthDay'>> = {},
): XhsScheduleChoice {
  return {
    frequency,
    time: extra.time ?? '09:00',
    weekday: extra.weekday ?? 'mon',
    monthDay: extra.monthDay ?? 1,
    cron,
  }
}

function clockFrom(minute: number, hour: number): string | null {
  if (!Number.isInteger(minute) || !Number.isInteger(hour)) return null
  if (minute < 0 || minute > 59 || hour < 0 || hour > 23) return null
  return `${pad(hour)}:${pad(minute)}`
}

function readClock(time: string): { minute: number; hour: number } {
  const match = /^(\d{2}):(\d{2})(?::\d{2})?$/.exec(time.trim())
  if (!match) throw new Error('invalid time')
  const hour = Number(match[1])
  const minute = Number(match[2])
  if (clockFrom(minute, hour) === null) throw new Error('invalid time')
  return { minute, hour }
}

function weekdayFromCron(token: string): XhsWeekday | null {
  const name = token.toLowerCase()
  if ((XHS_WEEKDAYS as readonly string[]).includes(name)) return name as XhsWeekday
  if (/^\d$/.test(token)) {
    const index = Number(token)
    return XHS_WEEKDAYS[index] ?? null
  }
  return null
}

export function parseXhsCron(cron: string): XhsScheduleChoice {
  const normalized = normalizeCron(cron)
  const alias = normalized.toLowerCase()
  if (alias === '@hourly') return choice('h1', INTERVAL_CRONS.h1)
  if (alias === '@daily' || alias === '@midnight') return choice('daily', '0 0 * * *', { time: '00:00' })
  if (alias === '@weekly') return choice('weekly', '0 0 * * mon', { time: '00:00', weekday: 'mon' })
  if (alias === '@monthly') return choice('monthly', '0 0 1 * *', { time: '00:00', monthDay: 1 })

  for (const [frequency, expression] of Object.entries(INTERVAL_CRONS) as Array<[IntervalFrequency, string]>) {
    if (normalized === expression) return choice(frequency, expression)
  }

  const weekly = /^(\d{1,2}) (\d{1,2}) \* \* ([A-Za-z]+|\d)$/.exec(normalized)
  const weeklyMinute = weekly?.[1]
  const weeklyHour = weekly?.[2]
  const weeklyDay = weekly?.[3]
  if (weeklyMinute && weeklyHour && weeklyDay) {
    const time = clockFrom(Number(weeklyMinute), Number(weeklyHour))
    const weekday = weekdayFromCron(weeklyDay)
    if (time && weekday) {
      const { minute, hour } = readClock(time)
      return choice('weekly', `${minute} ${hour} * * ${weekday}`, { time, weekday })
    }
  }

  const monthly = /^(\d{1,2}) (\d{1,2}) (\d{1,2}) \* \*$/.exec(normalized)
  const monthlyMinute = monthly?.[1]
  const monthlyHour = monthly?.[2]
  const monthlyDayText = monthly?.[3]
  if (monthlyMinute && monthlyHour && monthlyDayText) {
    const time = clockFrom(Number(monthlyMinute), Number(monthlyHour))
    const monthDay = Number(monthlyDayText)
    if (time && monthDay >= 1 && monthDay <= 31) {
      const { minute, hour } = readClock(time)
      return choice('monthly', `${minute} ${hour} ${monthDay} * *`, { time, monthDay })
    }
  }

  const daily = /^(\d{1,2}) (\d{1,2}) \* \* \*$/.exec(normalized)
  if (daily) {
    const time = clockFrom(Number(daily[1]), Number(daily[2]))
    if (time) {
      const { minute, hour } = readClock(time)
      return choice('daily', `${minute} ${hour} * * *`, { time })
    }
  }

  return choice('custom', normalized || INTERVAL_CRONS.h1)
}

export function buildXhsCron(
  frequency: XhsFrequency,
  time: string,
  customCron: string,
  weekday: XhsWeekday = 'mon',
  monthDay = 1,
): string {
  if (frequency === 'custom') {
    const cron = normalizeCron(customCron)
    if (!cron) throw new Error('invalid schedule')
    return cron
  }
  if (frequency !== 'daily' && frequency !== 'weekly' && frequency !== 'monthly') {
    return INTERVAL_CRONS[frequency]
  }

  const { minute, hour } = readClock(time)
  if (frequency === 'daily') return `${minute} ${hour} * * *`
  if (frequency === 'weekly') {
    if (!(XHS_WEEKDAYS as readonly string[]).includes(weekday)) throw new Error('invalid weekday')
    return `${minute} ${hour} * * ${weekday}`
  }
  if (!Number.isInteger(monthDay) || monthDay < 1 || monthDay > 31) throw new Error('invalid day')
  return `${minute} ${hour} ${monthDay} * *`
}

function shanghaiParts(date: Date): { ymd: string; month: number; day: number; time: string } | null {
  if (Number.isNaN(date.getTime())) return null
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(date)
  const read = (type: Intl.DateTimeFormatPartTypes) => parts.find((part) => part.type === type)?.value ?? ''
  let hour = read('hour')
  if (hour === '24') hour = '00'
  const month = Number(read('month'))
  const day = Number(read('day'))
  const year = read('year')
  if (!year || !month || !day || !hour) return null
  return {
    ymd: `${year}-${pad(month)}-${pad(day)}`,
    month,
    day,
    time: `${hour}:${read('minute').padStart(2, '0')}`,
  }
}

function nextShanghaiDay(ymd: string): string {
  const [yearText, monthText, dayText] = ymd.split('-')
  const year = Number(yearText)
  const month = Number(monthText)
  const day = Number(dayText)
  const next = new Date(Date.UTC(year, month - 1, day + 1))
  return `${next.getUTCFullYear()}-${pad(next.getUTCMonth() + 1)}-${pad(next.getUTCDate())}`
}

/** 把下次执行时间收成「今天 / 明天 / 某月某日」加钟点，时区固定北京。 */
export function classifyXhsNextRun(value: string | null | undefined, now = new Date()): XhsNextRunParts | null {
  if (!value) return null
  const target = shanghaiParts(new Date(value))
  const current = shanghaiParts(now)
  if (!target || !current) return null
  if (target.ymd === current.ymd) return { kind: 'today', time: target.time }
  if (target.ymd === nextShanghaiDay(current.ymd)) return { kind: 'tomorrow', time: target.time }
  return { kind: 'date', time: target.time, month: target.month, day: target.day }
}
