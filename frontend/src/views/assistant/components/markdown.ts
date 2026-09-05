/** Markdown 渲染工具 —— 全局单例
 *
 * 安全：所有 HTML 输出经 DOMPurify 清洗，防止 XSS。
 * 增强：支持 ```echarts fence 渲染交互式图表（需调用 mountECharts 挂载）。
 */
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import 'highlight.js/styles/github.css'
import DOMPurify from 'dompurify'
import * as echarts from 'echarts'

const md = new MarkdownIt({
  html: true,  // 允许 HTML（支持 data-ref 标签）
  linkify: true,
  typographer: true,
  highlight: (code: string, lang: string): string => {
    const validLang = lang && hljs.getLanguage(lang) ? lang : ''
    const hl = validLang
      ? hljs.highlight(code, { language: validLang, ignoreIllegals: true }).value
      : md.utils.escapeHtml(code)
    const copyBtn = `<button class="hljs-copy-btn" onclick="navigator.clipboard.writeText(this.closest('.hljs-block').querySelector('code').innerText).then(()=>{this.textContent='已复制';setTimeout(()=>this.textContent='复制',1500)})">复制</button>`
    return `<pre class="hljs-block"><div class="hljs-header"><span class="hljs-lang">${validLang || 'code'}</span>${copyBtn}</div><code class="hljs${validLang ? ' language-' + validLang : ''}">${hl}</code></pre>`
  },
})

// 链接新窗口打开
md.renderer.rules.link_open = (tokens: any, idx: any, options: any, _: any, self: any) => {
  tokens[idx].attrSet('target', '_blank')
  tokens[idx].attrSet('rel', 'noopener noreferrer')
  return self.renderToken(tokens, idx, options)
}

// echarts fence 占位符缓存（key = 占位 ID，value = option JSON）
const _echartOptions: Map<string, Record<string, any>> = new Map()

/**
 * 渲染 Markdown 为安全 HTML。
 * ```echarts fence 会被替换为 <div data-echart-id="xxx"></div> 占位符。
 * 调用方需在 v-html 渲染后调用 mountECharts(container) 挂载图表。
 */
export function renderMarkdown(text: string): string {
  if (!text) return ''
  _echartOptions.clear()

  // 预处理：提取 ```echarts {...} ``` 块，替换为占位符
  const processed = text.replace(
    /```echarts\s*\n([\s\S]*?)```/g,
    (_match, jsonStr: string) => {
      try {
        const option = JSON.parse(jsonStr.trim())
        const id = `echart-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
        _echartOptions.set(id, option)
        return `<div data-echart-id="${id}" class="echart-placeholder" style="width:100%;height:300px;"></div>`
      } catch {
        return `<pre>echarts JSON 解析失败</pre>`
      }
    }
  )

  const rawHtml = md.render(processed)
  return DOMPurify.sanitize(rawHtml, {
    ADD_TAGS: ['data-ref', 'data-entity', 'data-entity-id'],
    ADD_ATTR: ['data-ref', 'data-entity', 'data-entity-id', 'data-entity-type', 'data-echart-id'],
    ALLOW_DATA_ATTR: true,
  })
}

/** 在 v-html 渲染后的容器中挂载所有 echarts 占位符 */
export function mountECharts(container: HTMLElement) {
  const placeholders = container.querySelectorAll('[data-echart-id]')
  placeholders.forEach((el) => {
    const id = el.getAttribute('data-echart-id')
    if (!id) return
    const option = _echartOptions.get(id)
    if (!option) return
    const chart = echarts.init(el as HTMLElement)
    chart.setOption(option)
  })
}

export { md }
