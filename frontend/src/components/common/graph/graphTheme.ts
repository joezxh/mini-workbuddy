/**
 * 图谱工作台的视觉字典：节点调色板 / 显示名 / 权重分档 / 属性摘要格式。
 * 原 views/kms/kg/kgTheme.ts，2026-11-01 起供图谱知识库与标准中心共用（spec §3.2）。
 *
 * 原型约定：类型色是语义色（部门蓝、供应商绿、产品橙、仓库紫、客户青），
 * 不随主题变化；未登记的类型按名称哈希落到同一套色板，保证图谱与表格同色。
 */

export interface TypeTone {
  /** 节点填充 / 分布条颜色 */
  color: string;
  /** 标签文字色 */
  fg: string;
  /** 标签底色 */
  bg: string;
  /** 标签描边 */
  border: string;
}

/** 原型 TYPES 调色板（顺序即哈希回退顺序） */
export const TYPE_PALETTE: TypeTone[] = [
  { color: '#3371fc', fg: '#0958d9', bg: '#e6f0ff', border: '#bcd8ff' }, // 部门
  { color: '#52c41a', fg: '#389e0d', bg: '#f6ffed', border: '#b7eb8f' }, // 供应商
  { color: '#fa8c16', fg: '#d46b08', bg: '#fff7e6', border: '#ffd591' }, // 产品
  { color: '#722ed1', fg: '#531dab', bg: '#f9f0ff', border: '#efdbff' }, // 仓库
  { color: '#08979c', fg: '#08979c', bg: '#e6fffb', border: '#87e8de' }, // 客户
];

/** 未登记类型的中性色 */
export const NEUTRAL_TONE: TypeTone = {
  color: '#8f959e',
  fg: '#646a73',
  bg: '#f5f7fa',
  border: '#e5e6eb',
};

/** 已知类型码 -> 调色板下标（CDM 对象标准编码的常见前缀） */
const KNOWN_TYPES: Record<string, number> = {
  OBJ_DEPT: 0,
  OBJ_SUPPLIER: 1,
  OBJ_PRODUCT: 2,
  OBJ_WAREHOUSE: 3,
  OBJ_CUSTOMER: 4,
};

/** 已知类型码 -> 中文显示名（CDM 未下发显示名时的兜底） */
const KNOWN_LABELS: Record<string, string> = {
  OBJ_DEPT: '部门',
  OBJ_SUPPLIER: '供应商',
  OBJ_PRODUCT: '产品',
  OBJ_WAREHOUSE: '仓库',
  OBJ_CUSTOMER: '客户',
};

function hashIndex(code: string, size: number): number {
  let h = 0;
  for (let i = 0; i < code.length; i += 1) {
    h = (h * 31 + code.charCodeAt(i)) % 100000;
  }
  return h % size;
}

/** 类型码 -> 类型色（未知类型按哈希落色，保证同码同色） */
export function typeTone(code?: string | null): TypeTone {
  if (!code) return NEUTRAL_TONE;
  const known = KNOWN_TYPES[code];
  if (known !== undefined) return TYPE_PALETTE[known];
  return TYPE_PALETTE[hashIndex(code, TYPE_PALETTE.length)];
}

/** 类型码 -> 展示名（去 OBJ_ 前缀；已知类型给中文名） */
export function typeLabel(code?: string | null): string {
  if (!code) return '';
  if (KNOWN_LABELS[code]) return KNOWN_LABELS[code];
  return code.replace(/^OBJ_/, '').replace(/_/g, ' ');
}

/** 权重分档（原型三色阈值）：ok ≥0.8 / warn 0.5–0.8 / err <0.5 */
export function weightLevel(weight?: number | null): 'ok' | 'warn' | 'err' {
  const w = Number(weight ?? 0);
  if (w >= 0.8) return 'ok';
  if (w >= 0.5) return 'warn';
  return 'err';
}

/** 权重条颜色 */
export function weightColor(weight?: number | null): string {
  const level = weightLevel(weight);
  if (level === 'ok') return '#52c41a';
  if (level === 'warn') return '#faad14';
  return '#ff4d4f';
}

/** 属性摘要：原型为「键:值　键:值」，最多两项，超出加 +N */
export function propertySummary(props?: Record<string, unknown> | null): string {
  const entries = Object.entries(props || {});
  if (!entries.length) return '';
  const head = entries
    .slice(0, 2)
    .map(([k, v]) => `${k}:${String(v)}`)
    .join('\u3000');
  return entries.length > 2 ? `${head} +${entries.length - 2}` : head;
}

/** 权重显示：保留两位小数（原型 0.92 / 0.71） */
export function formatWeight(weight?: number | null): string {
  if (weight === null || weight === undefined) return '—';
  return Number(weight).toFixed(2);
}
