/** 闲鱼商品详情页链接（与后端 parsers.py 一致） */
export function buildGoofishItemUrl(itemId: string): string {
  return `https://www.goofish.com/item?id=${encodeURIComponent(itemId)}`
}
