import { beforeEach } from 'vitest'

beforeEach(() => {
  localStorage.clear()
  localStorage.setItem('app_locale', 'zh-CN')
})
