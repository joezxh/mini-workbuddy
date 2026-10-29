/**
 * 关键字检索兜底：AI 不可用时，仍按 code / 名称 / 别名 命中对象与关系。
 *
 * 双向往返匹配是刻意的：用户常把实体名写进一句话里（「订单和客户怎么关联」），
 * 整句不会被空格切开，所以既要做「实体包含词」，也要做「词包含实体」。
 * 纯函数、不依赖 i18n，摘要文案由调用方按语言组装。
 */
export interface Searchable {
  code: string
  name?: string | null
  aliases?: string[] | null
}

export interface KeywordHits {
  objectCodes: string[]
  relationCodes: string[]
}

/** 单字实体的误命中太吵，短于 2 个字符的词条/词元一律不参与比较 */
const MIN_TERM = 2
const SPLIT = /[^\p{L}\p{N}_]+/u

/** 按非字母数字切词（中文整句会保留为一个词元，交给反向匹配处理） */
export function queryTokens(query: string): string[] {
  return (query || '')
    .toLowerCase()
    .split(SPLIT)
    .filter((tok) => tok.length >= MIN_TERM)
}

/** 一个条目可用于比对的词条：code、名称、每个别名 */
function termsOf(item: Searchable): string[] {
  return [item.code, item.name, ...(item.aliases || [])]
    .map((v) => (v || '').trim().toLowerCase())
    .filter((v) => v.length >= MIN_TERM)
}

function hit(item: Searchable, tokens: string[]): boolean {
  const terms = termsOf(item)
  if (!terms.length) return false
  return tokens.some((tok) => terms.some((term) => term.includes(tok) || tok.includes(term)))
}

function collect(items: Searchable[], tokens: string[]): string[] {
  const seen = new Set<string>()
  for (const item of items) {
    if (item.code && !seen.has(item.code) && hit(item, tokens)) seen.add(item.code)
  }
  return [...seen]
}

/** 命中对象 / 关系的 code 列表（保持入参顺序，自动去重） */
export function keywordHits(
  query: string,
  objects: Searchable[],
  relations: Searchable[],
): KeywordHits {
  const tokens = queryTokens(query)
  if (!tokens.length) return { objectCodes: [], relationCodes: [] }
  return {
    objectCodes: collect(objects, tokens),
    relationCodes: collect(relations, tokens),
  }
}
