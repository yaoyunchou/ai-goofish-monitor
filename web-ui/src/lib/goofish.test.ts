import { describe, expect, it } from 'vitest'
import { buildGoofishItemUrl } from './goofish'

describe('buildGoofishItemUrl', () => {
  it('builds canonical item detail url', () => {
    expect(buildGoofishItemUrl('1083008241172')).toBe(
      'https://www.goofish.com/item?id=1083008241172',
    )
  })

  it('encodes unsafe item id fragments', () => {
    expect(buildGoofishItemUrl('a/b?c')).toBe(
      'https://www.goofish.com/item?id=a%2Fb%3Fc',
    )
  })
})
